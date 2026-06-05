import os
import sys
import csv
import glob

BITWARDEN_FIELDS = [
    "folder", "favorite", "type", "name", "notes", "fields",
    "reprompt", "login_uri", "login_username", "login_password", "login_totp",
]


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


def has_custom_fields(raw: str | None):
    """Return True if the Others column contains any AutofillWeb or Password entries."""
    if not is_value_present(raw):
        return False
    try:
        import json
        data = json.loads(str(raw))
        return bool(data.get("Custom"))
    except (json.JSONDecodeError, AttributeError):
        return False


def categorize_incomplete(rows: list[dict]):
    """Split rows into five groups based on what data is missing.

    Groups:
      1 - no username, no password, no custom fields, no URL  (recommend discard)
      2 - no username, no password, no custom fields, URL present  (recommend discard)
      3 - username or password missing (but not both), no custom fields
      4 - no username and no password, but custom fields present
      5 - username and password present, but no URL

    Rows that have username or password AND a URL are considered complete
    and are not returned here.

    Returns a dict mapping group number to list of (row_index, row, reason) tuples.
    row_index is 1-based to match the source CSV line numbers shown to the user.
    """
    groups = {1: [], 2: [], 3: [], 4: [], 5: []}

    for index, row in enumerate(rows):
        row_number = index + 1
        username   = field(row.get("Login_Username"))
        password   = field(row.get("Login_Password"))
        url        = join_urls(row.get("Login_URLs"))
        customs    = has_custom_fields(row.get("Others"))

        has_user = bool(username)
        has_pass = bool(password)
        has_url  = bool(url)

        if not has_user and not has_pass and not customs and not has_url:
            groups[1].append((row_number, row, "no username, no password, no custom fields, no URL"))
        elif not has_user and not has_pass and not customs and has_url:
            groups[2].append((row_number, row, "no username, no password, no custom fields"))
        elif (not has_user or not has_pass) and not (not has_user and not has_pass) and not customs:
            reason = "no username" if not has_user else "no password"
            groups[3].append((row_number, row, reason))
        elif not has_user and not has_pass and customs:
            groups[4].append((row_number, row, "no username, no password (credentials in custom fields only)"))
        elif has_user or has_pass:
            if not has_url:
                groups[5].append((row_number, row, "no URL"))

    return groups


GROUP_LABELS = {
    1: "Group 1: No data at all (no username, password, custom fields, or URL)",
    2: "Group 2: URL only (no username, password, or custom fields)",
    3: "Group 3: Incomplete credentials (username or password missing)",
    4: "Group 4: Credentials in custom fields only (no standard username/password)",
    5: "Group 5: No URL",
}

GROUP_RECOMMENDED_DISCARD = {1, 2}


def prompt_group(group_num: int, entries: list[tuple]):
    """Show a group to the user and return the set of row indices to discard."""
    print(f"\n{GROUP_LABELS[group_num]} -- {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")

    if group_num in GROUP_RECOMMENDED_DISCARD:
        print("Recommended action: discard all")

    for pos, (row_number, row, reason) in enumerate(entries, 1):
        name = field(row.get("Display_Name")) or f"(row {row_number})"
        print(f"  [{pos}] {name}  --  {reason}")

    print("Enter numbers to DISCARD, 'drop' to discard all, or Enter to keep all: ", end="")

    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return set()

    if answer == "drop":
        return {row_number for row_number, _, _ in entries}

    if not answer:
        return set()

    to_discard = set()
    for token in answer.split():
        if token.isdigit():
            pos = int(token)
            if 1 <= pos <= len(entries):
                row_number = entries[pos - 1][0]
                to_discard.add(row_number)
            else:
                print(f"  (ignored: {pos} is out of range)")
        else:
            print(f"  (ignored: '{token}' is not a number)")

    return to_discard


def review_incomplete(rows: list[dict]):
    """Interactively review incomplete entries and return the set of row indices to discard.

    Row indices are 1-based to match CSV line numbers.
    Only groups that contain at least one entry are shown.
    """
    groups = categorize_incomplete(rows)

    any_incomplete = any(entries for entries in groups.values())
    if not any_incomplete:
        return set()

    print("\n--- Incomplete entries review ---")
    print("The following entries are missing some data. Review each group and")
    print("choose which entries to discard. Default is to keep all.\n")

    discard_indices = set()
    for group_num in sorted(groups.keys()):
        entries = groups[group_num]
        if entries:
            discard_indices |= prompt_group(group_num, entries)

    return discard_indices


def convert(rows: list[dict], discard_indices: set[int]):
    """Turn Synology C2 rows into Bitwarden rows. Returns (converted, skipped)."""
    converted = []
    skipped   = []

    for index, row in enumerate(rows):
        row_number = index + 1

        try:
            login_uri = join_urls(row.get("Login_URLs", ""))
            username  = field(row.get("Login_Username"))
            password  = field(row.get("Login_Password"))
            display   = field(row.get("Display_Name")).strip()
            customs   = has_custom_fields(row.get("Others"))

            # discard entries the user explicitly chose to drop during review
            if row_number in discard_indices:
                skipped.append((display or f"(unnamed row {row_number})", "discarded by user"))
                continue

            # skip rows with absolutely no login data and no custom fields.
            # with interactive review these should already be in discard_indices,
            # but this acts as a safety net if review was skipped.
            if not (username or password or login_uri or customs):
                skipped.append((display or f"(unnamed row {row_number})", "no login info"))
                continue

            converted.append({
                "folder":         "",   # leave folder empty for user to assign during import
                "favorite":       field(row.get("Favorite")),
                "type":           "login",  # assuming all entries are of type "login"
                "name":           display or f"Entry_{row_number}",
                "notes":          field(row.get("Notes")),
                "fields":         "",   # add custom fields manually in Bitwarden for better accuracy
                "reprompt":       0,    # setting "Master password re-prompt" to "0" for all entries to turn off the option. User can change this later manually.
                "login_uri":      login_uri,
                "login_username": username,
                "login_password": password,
                "login_totp":     field(row.get("Login_TOTP")),
            })

        except Exception:
            # if one row blows up, skip it instead of crashing the whole run
            display = ""
            if isinstance(row, dict):
                display = field(row.get("Display_Name")).strip()
            skipped.append((display or f"(unnamed row {row_number})", "error reading row"))

    return converted, skipped


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

    # interactively review incomplete entries before converting
    discard_indices = review_incomplete(rows)

    converted, skipped = convert(rows, discard_indices)

    if not converted:
        print("\nError: none of the entries had a username, password, or URL.")
        print("Nothing to import, so no file was written.")
        finish(1)

    # save the new file next to the export the user picked
    export_folder = os.path.dirname(os.path.abspath(input_path))
    out_path      = os.path.join(export_folder, "bitwarden_file.csv")

    try:
        saved = save(converted, out_path)
    except Exception as e:
        print(f"\nError saving the Bitwarden file: {e}")
        finish(1)

    print(f"\nConverted {len(converted)} entries.")
    print(f"Saved: {saved}")

    if skipped:
        print(f"\nSkipped {len(skipped)} (NOT transferred):")
        for name, reason in skipped:
            print(f"  - {name} ({reason})")
        print("\nAdd these to Bitwarden manually if needed.")

    print("\nNext steps:")
    print("  1. Open your Bitwarden/Vaultwarden web interface")
    print("  2. Go to Tools > Import Data")
    print("  3. Choose file format: Bitwarden (.csv)")
    print(f"  4. Upload: {saved}")
    print("\nImportant: securely delete the CSV files after importing!")

    finish(0)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        finish(1)
