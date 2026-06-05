import os
import sys
import csv
import glob
import json

BITWARDEN_FIELDS = [
    "folder", "favorite", "type", "name", "notes", "fields",
    "reprompt", "login_uri", "login_username", "login_password", "login_totp",
]

# characters that cause Vaultwarden/Bitwarden to fail or silently corrupt data on import.
# U+2022 BULLET is used by Synology C2 to mask passwords that it could not export in plaintext.
# U+0000 NULL BYTE breaks CSV parsers.
# U+FEFF BOM causes parser confusion when embedded mid-field.
PROBLEMATIC_CHARS = {
    "\u2022": "U+2022 BULLET (masked/corrupted C2 field)",
    "\u0000": "U+0000 NULL BYTE",
    "\ufeff": "U+FEFF BOM",
}

# default and recommended chunk size for Vaultwarden imports.
# large imports can time out or run out of browser memory; splitting into smaller
# files avoids this. 200 entries per file has been found to be reliable.
DEFAULT_CHUNK_SIZE = 200


def clean_path(path_input: str):
    """Clean up a path the user typed or pasted."""
    if not path_input:
        return None

    # drop surrounding quotes and make the slashes match this os
    path_cleaned = path_input.strip().strip('"').strip("'")
    path_cleaned = path_cleaned.replace("\\", os.sep).replace("/", os.sep)
    return path_cleaned


def validate_input_file(file_path: str):
    """Check the path exists and can be read."""
    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' was not found.")
        return False

    if not os.path.isfile(file_path):
        print(f"Error: '{file_path}' is not a file.")
        return False

    # open in binary just to check we can read it.
    # the real encoding is figured out later in read_csv so dont force utf-8 here.
    try:
        with open(file_path, "rb") as f:
            f.read(1)
        return True
    except Exception as e:
        print(f"Error: Cannot read file '{file_path}': {e}")
        return False


def is_value_present(value: str | None):
    """True if the value has real content."""
    if value is None:
        return False
    text = str(value).strip()
    return text.lower() not in ("", "nan", "none", "null")


def field(value: str | None):
    """Return the value as text or empty string if blank."""
    return str(value) if is_value_present(value) else ""


def join_urls(raw: str | None):
    """Join the C2 URL lines into one comma separated cell."""
    if not is_value_present(raw):
        return ""

    # synology puts each url on its own line but bitwarden wants them in one cell split by commas
    urls = []
    for part in str(raw).strip().split("\n"):
        urls.append(part.strip())
    return ",".join(urls)


def sanitize_field(value: str, entry_name: str, field_name: str, warnings: list[str]):
    """Remove characters that cause Vaultwarden import failures or silent data corruption.

    Problematic characters are removed and replaced with an empty string.
    Each replacement is logged to the warnings list so the user knows which
    entries need to be checked after import.

    A note is also appended to the returned value when the entire field consisted
    only of problematic characters (e.g. a fully masked C2 password like '••••5'),
    since in that case the field becomes empty and the user needs to set it manually.
    """
    if not value:
        return value, []

    cleaned    = value
    found      = []
    fully_masked = False

    for char, description in PROBLEMATIC_CHARS.items():
        if char in cleaned:
            # check if the field is entirely composed of this problematic character
            # (plus digits/whitespace), which indicates a masked C2 export value
            stripped = cleaned.replace(char, "").strip()
            if not stripped or stripped.isdigit():
                fully_masked = True
            cleaned = cleaned.replace(char, "")
            found.append(description)

    if found:
        for desc in found:
            warnings.append(
                f"  Warning: '{entry_name}' field '{field_name}' contained {desc} -- removed."
            )
        if fully_masked:
            warnings.append(
                f"  Warning: '{entry_name}' field '{field_name}' was fully masked "
                f"(value was only problematic characters). Set this field manually after import."
            )

    return cleaned, found


def sanitize_row(row: dict, entry_name: str):
    """Sanitize all string fields in a converted Bitwarden row.

    Returns (sanitized_row, warnings) where warnings is a list of strings
    describing every replacement made. Fields that are not strings (e.g. reprompt)
    are left untouched.
    """
    warnings    = []
    sanitized   = {}

    for key, value in row.items():
        if isinstance(value, str):
            clean, _ = sanitize_field(value, entry_name, key, warnings)
            sanitized[key] = clean
        else:
            sanitized[key] = value

    return sanitized, warnings


def parse_others(raw: str | None):
    """Parse the C2 'Others' JSON field.

    Returns a tuple of (bitwarden_custom_fields, notes_lines) where:
    - bitwarden_custom_fields is a newline-joined string of "selector\tvalue" pairs
      for AutofillWeb entries (used for autofill matching in Bitwarden/Vaultwarden).
    - notes_lines is a list of human-readable strings to append under a
      '--- C2 Import ---' header in the notes field.

    Three types are handled:
    - AutofillWeb: selector becomes the Bitwarden custom field name (enables
      autofill); title and value are also written to notes for readability.
    - Password: a named password without a selector, written to notes only.
    - Login_Autosave_Web_Anti_Selectors: top-level key (not inside 'Custom'),
      written to notes only as these are C2-specific autosave exclusions.

    Any type not listed above is written to notes as-is so no data is lost.
    """
    if not is_value_present(raw):
        return "", []

    try:
        data = json.loads(str(raw))
    except json.JSONDecodeError:
        # unparseable JSON: preserve the raw value in notes so nothing is lost
        return "", [f"[C2 raw Others]: {str(raw).strip()}"]

    custom_fields = []
    notes_lines   = []

    # handle Login_Autosave_Web_Anti_Selectors (top-level key, not inside Custom)
    anti_selectors = data.get("Login_Autosave_Web_Anti_Selectors")
    if anti_selectors:
        if isinstance(anti_selectors, list):
            notes_lines.append("[Autosave_Anti_Selectors]: " + ", ".join(str(s) for s in anti_selectors))
        else:
            notes_lines.append(f"[Autosave_Anti_Selectors]: {anti_selectors}")

    for entry in data.get("Custom", []):
        entry_type = entry.get("Type", "")

        if entry_type == "AutofillWeb":
            title    = entry.get("AutofillWeb_Title", "").strip()
            aw_type  = entry.get("AutofillWeb_Type", "").strip()
            value    = entry.get("AutofillWeb", "")
            selector = entry.get("AutofillWeb_Selector", "").strip()

            if selector:
                # use the CSS selector as the Bitwarden custom field name so
                # Bitwarden/Vaultwarden can match it against the page for autofill
                custom_fields.append(f"{selector}\t{value}")

            # always write title + value to notes regardless of selector presence
            label = title if title else aw_type
            notes_lines.append(f"[{label}]: {value}")

        elif entry_type == "Password":
            # a named password stored without a selector; notes only
            title = entry.get("Password_Title", "").strip()
            value = entry.get("Password", "")
            label = title if title else "Password"
            notes_lines.append(f"[{label}]: {value}")

        else:
            # unknown type: write everything to notes so no data is lost
            notes_lines.append(f"[{entry_type}]: {json.dumps(entry, ensure_ascii=False)}")

    bitwarden_fields_str = "\n".join(custom_fields)
    return bitwarden_fields_str, notes_lines


def build_notes(base_notes: str, c2_notes_lines: list[str]):
    """Combine the original notes with the C2 import section."""
    if not c2_notes_lines:
        return base_notes

    c2_block = "--- C2 Import ---\n" + "\n".join(c2_notes_lines)

    if base_notes:
        return base_notes + "\n\n" + c2_block
    return c2_block


def convert(rows: list[dict]):
    """Turn Synology C2 rows into Bitwarden rows. Returns (converted, skipped, all_warnings)."""
    converted    = []
    skipped      = []
    all_warnings = []

    for index, row in enumerate(rows):
        row_number = index + 1

        try:
            login_uri = join_urls(row.get("Login_URLs", ""))
            username  = field(row.get("Login_Username"))
            password  = field(row.get("Login_Password"))
            display   = field(row.get("Display_Name")).strip()

            # parse the Others field for custom fields and notes content
            bw_custom_fields, c2_notes_lines = parse_others(row.get("Others"))

            # skip rows with no login data.
            # these are usually cards or other non-login items that cant become a bitwarden login.
            if not (username or password or login_uri):
                skipped.append((display or f"(unnamed row {row_number})", "no login info"))
                continue

            notes = build_notes(field(row.get("Notes")), c2_notes_lines)

            # fall back to the URL or a generic name if Display_Name is empty.
            # Vaultwarden rejects the entire import when any entry has an empty name field.
            name = display or login_uri or f"Entry_{row_number}"

            bw_row = {
                "folder":         "",   # leave folder empty for user to assign during import
                "favorite":       field(row.get("Favorite")),
                "type":           "login",  # assuming all entries are of type "login"
                "name":           name,
                "notes":          notes,
                "fields":         bw_custom_fields,
                "reprompt":       0,    # setting "Master password re-prompt" to "0" for all entries to turn off the option. User can change this later manually.
                "login_uri":      login_uri,
                "login_username": username,
                "login_password": password,
                "login_totp":     field(row.get("Login_TOTP")),
            }

            # sanitize all fields to remove characters that break the Vaultwarden importer
            bw_row, warnings = sanitize_row(bw_row, name)
            if warnings:
                all_warnings.extend(warnings)

            converted.append(bw_row)

        except Exception:
            # if one row blows up, skip it instead of crashing the whole run
            display = ""
            if isinstance(row, dict):
                display = field(row.get("Display_Name")).strip()
            skipped.append((display or f"(unnamed row {row_number})", "error reading row"))

    return converted, skipped, all_warnings


def ask_chunk_size():
    """Ask the user whether to split the output into chunks and how large each chunk should be.

    Returns an int chunk size, or None if the user wants a single file.
    """
    print(f"\nSplit output into chunks? {DEFAULT_CHUNK_SIZE} recommended.")
    answer = input("Enter size or Enter for single file: ").strip()

    if not answer:
        return None

    if answer.isdigit() and int(answer) > 0:
        return int(answer)

    print(f"Invalid size '{answer}', using single file.")
    return None


def read_csv(path: str):
    """Read a C2 export CSV, trying a few encodings. Returns (rows, columns)."""
    encodings  = ["utf-8", "utf-16", "cp1252", "iso-8859-1"]
    last_error = None

    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                # synology C2 password always exports comma separated, so use the comma dialect directly.
                # auto detecting the delimiter could wrongly pick ":" on vaults full of URLs and blank out every field. (issue #4)
                reader  = csv.DictReader(f, dialect=csv.excel)
                columns = reader.fieldnames or []
                if not columns:
                    raise ValueError("empty")
                return list(reader), columns

        except UnicodeDecodeError:
            # wrong encoding for this file, so try the next one
            continue
        except ValueError as e:
            # only the real "empty file" case should stop us.
            # a no BOM utf-16 read also raises a ValueError so let that fall through and retry.
            if str(e) == "empty":
                raise
            last_error = e
            continue
        except Exception as e:
            last_error = e
            continue

    raise ValueError("encoding") from last_error


def save(rows: list[dict], path: str):
    """Write rows to a CSV without overwriting an existing file."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    # if the name is taken add "_2", "_3", etc before the extension
    base, extension = os.path.splitext(path)
    target  = path
    counter = 2
    while os.path.exists(target):
        target = f"{base}_{counter}{extension}"
        counter += 1

    with open(target, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BITWARDEN_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return target


def save_chunks(rows: list[dict], base_path: str, chunk_size: int):
    """Split rows into chunks and save each as a separate CSV file.

    Files are named bitwarden_file_part1.csv, bitwarden_file_part2.csv, etc.
    Returns a list of saved file paths.
    """
    base, extension = os.path.splitext(base_path)
    saved_paths     = []

    for part, start in enumerate(range(0, len(rows), chunk_size), 1):
        chunk      = rows[start:start + chunk_size]
        chunk_path = f"{base}_part{part}{extension}"
        saved      = save(chunk, chunk_path)
        saved_paths.append(saved)

    return saved_paths


def base_dir():
    """Folder the program runs from."""
    # when packaged as an exe look next to the exe instead of this file
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_export(folder: str):
    """Find possible C2 export files in a folder."""
    if not os.path.isdir(folder):
        return []

    # glob.escape keeps any [ ] * ? in the folder name from being treated as a search pattern
    safe_folder = glob.escape(folder)

    # first try synology's normal export name
    matches = sorted(glob.glob(os.path.join(safe_folder, "C2Password_Export_*.csv")))
    if matches:
        return matches

    # otherwise fall back to any other csv
    other_csvs = []
    for csv_path in sorted(glob.glob(os.path.join(safe_folder, "*.csv"))):
        filename = os.path.basename(csv_path)
        if not filename.lower().startswith("bitwarden_file"):
            other_csvs.append(csv_path)
    return other_csvs


def finish(code: int = 0):
    """Pause so the output stays on screen, then exit."""
    try:
        input("\nPress Enter to close...")
    except EOFError:
        pass
    sys.exit(code)


def choose_input():
    """Find the export file or ask the user for it."""
    # look in the folder the program runs from and the current folder
    folders      = []
    seen_folders = set()
    for folder in (base_dir(), os.getcwd()):
        folder_key = os.path.normcase(os.path.abspath(folder))
        if folder_key not in seen_folders:
            seen_folders.add(folder_key)
            folders.append(folder)

    # collect every export file we can find in those folders
    candidates = []
    seen_files = set()
    for folder in folders:
        for found_path in find_export(folder):
            file_key = os.path.normcase(os.path.abspath(found_path))
            if file_key not in seen_files:
                seen_files.add(file_key)
                candidates.append(found_path)

    match len(candidates):
        case 1:
            # found exactly one file, so ask the user to confirm it
            choice = candidates[0]
            answer = input(f"Found export:\n  {choice}\n\nConvert this file? [Y/n] ").strip().lower()
            if answer in ("", "y", "yes"):
                return choice

        case 0:
            print("Couldn't find a C2 export in this folder.")

        case _:
            # found more than one, so let the user pick by number
            print("Found several possible exports:")
            for number, found_path in enumerate(candidates, 1):
                print(f"  {number}. {found_path}")

            while True:
                answer = input("\nPick a number (or paste a path): ").strip()
                if answer.isdigit() and 1 <= int(answer) <= len(candidates):
                    return candidates[int(answer) - 1]
                cleaned = clean_path(answer)
                if cleaned and validate_input_file(cleaned):
                    return cleaned
                print("Please enter a listed number or a valid file path.")

    # we reach here when nothing was found or the user said no to the one match.
    # ask them to drag the file in or type its path.
    while True:
        answer  = input("\nDrag your CSV onto this program, or paste its path:\n--> ").strip()
        cleaned = clean_path(answer)
        if cleaned and validate_input_file(cleaned):
            return cleaned
        print("Please try again with a valid file path.")


def main():
    print("Synology C2 Password -> Bitwarden converter")
    print("------------------------------------")
    print("Converts a Synology C2 Password export into a Bitwarden CSV.")
    print("Press Ctrl+C at any time to quit.\n")

    # if a file was dropped onto the program, use it. otherwise go find one.
    dropped = []
    for arg in sys.argv[1:]:
        if arg and arg.strip():
            dropped.append(clean_path(arg))

    input_path = None
    if dropped:
        if validate_input_file(dropped[0]):
            input_path = dropped[0]
        else:
            print()

    if input_path is None:
        input_path = choose_input()

    try:
        rows, columns = read_csv(input_path)
    except ValueError as e:
        if str(e) == "empty":
            print(f"\nError: '{input_path}' looks empty.")
        else:
            print(f"\nError: couldn't read '{input_path}' with any supported encoding.")
        finish(1)
    except FileNotFoundError:
        print(f"\nError: '{input_path}' was not found.")
        finish(1)
    except Exception as e:
        print(f"\nUnexpected error reading '{input_path}': {e}")
        finish(1)

    print(f"\nFound {len(rows)} entries.")
    print(f"Columns detected: {columns}")

    converted, skipped, all_warnings = convert(rows)

    if not converted:
        print("\nError: none of the entries had a username, password, or URL.")
        print("Nothing to import, so no file was written.")
        finish(1)

    # show sanitization warnings before asking about chunks so the user
    # has full information when deciding on chunk size
    if all_warnings:
        print(f"\nSanitization warnings ({len(all_warnings)}):")
        for w in all_warnings:
            print(w)
        print("\nCheck these entries in Vaultwarden after import and correct them manually.")

    chunk_size = ask_chunk_size()

    # save the output file(s) next to the export the user picked
    export_folder = os.path.dirname(os.path.abspath(input_path))
    out_path      = os.path.join(export_folder, "bitwarden_file.csv")

    try:
        if chunk_size:
            saved_paths = save_chunks(converted, out_path, chunk_size)
            num_chunks  = len(saved_paths)
            print(f"\nConverted {len(converted)} entries into {num_chunks} file(s) of up to {chunk_size} entries each.")
            for saved in saved_paths:
                print(f"  {saved}")
        else:
            saved = save(converted, out_path)
            print(f"\nConverted {len(converted)} entries.")
            print(f"Saved: {saved}")
            saved_paths = [saved]
    except Exception as e:
        print(f"\nError saving the Bitwarden file: {e}")
        finish(1)

    if skipped:
        print(f"\nSkipped {len(skipped)} (NOT transferred):")
        for name, reason in skipped:
            print(f"  - {name} ({reason})")
        print("\nAdd these to Bitwarden manually if needed.")

    print("\nNext steps:")
    print("  1. Open your Bitwarden/Vaultwarden web interface")
    print("  2. Go to Tools > Import Data")
    print("  3. Choose file format: Bitwarden (.csv)")
    if chunk_size:
        print(f"  4. Import each file separately in order:")
        for saved in saved_paths:
            print(f"     {saved}")
    else:
        print(f"  4. Upload: {saved_paths[0]}")
    print("\nImportant: securely delete the CSV files after importing!")

    finish(0)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        finish(1)
