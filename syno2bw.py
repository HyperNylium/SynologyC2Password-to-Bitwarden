import os
import sys
import csv
import glob
import json
import uuid


# bitwarden item type numbers
LOGIN_TYPE = 1
SECURE_NOTE_TYPE = 2
CARD_TYPE = 3

# bitwarden custom field type numbers
TEXT_FIELD = 0
HIDDEN_FIELD = 1

# card types we know how to name the bitwarden way
CARD_BRANDS = {
    "visa": "Visa",
    "mastercard": "Mastercard",
    "amex": "Amex",
    "american express": "Amex",
    "discover": "Discover",
    "diners club": "Diners Club",
    "jcb": "JCB",
    "maestro": "Maestro",
    "unionpay": "UnionPay",
    "rupay": "RuPay",
}


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


def build_uris(raw: str | None):
    """Turn the C2 URL lines into the bitwarden uris list."""

    if not is_value_present(raw):
        return []

    # synology puts each url on its own line. bitwarden wants a list of uri objects.
    uris = []
    for part in str(raw).strip().split("\n"):
        cleaned = part.strip()
        if cleaned:
            uris.append({"match": None, "uri": cleaned})

    return uris


def custom_field(name: str, value: str | None, field_type: int):
    """Make one bitwarden custom field."""

    return {
        "name": name,
        "value": field(value),
        "type": field_type
    }


def parse_expiry(raw: str | None):
    """Pull month and year out of a card expiry like 01/28. Returns (month, year, raw_if_bad)."""

    text = field(raw).strip()
    if not text:
        return "", "", ""

    # a good expiry looks like MM/YY or MM/YYYY
    parts = text.split("/")
    if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
        month = parts[0].strip()
        year = parts[1].strip()

        # two digit year like 28 means 2028
        if len(year) == 2:
            year = "20" + year

        month_number = int(month)
        if 1 <= month_number <= 12:
            return str(month_number), year, ""

    # could not read it so hand back the raw text to keep it
    return "", "", text


def normalize_brand(raw: str | None):
    """Match the card type to a bitwarden brand name."""

    text = field(raw).strip()
    if not text:
        return ""

    known = CARD_BRANDS.get(text.lower())
    if known:
        return known

    # not a known brand
    return "Other"


def parse_others(raw: str | None):
    """Read the Others column json. Returns a dict or None if there is nothing usable."""

    if not is_value_present(raw):
        return None

    try:
        data = json.loads(str(raw))
    except (ValueError, TypeError):
        return None

    if isinstance(data, dict):
        return data

    return None


def base_item(item_type: int, name: str, notes: str, favorite: bool):
    """Build the parts every bitwarden item shares."""

    return {
        "id": str(uuid.uuid4()),
        "organizationId": None,
        "folderId": None,  # leave empty so the user picks the folder during import
        "type": item_type,
        "name": name,
        "notes": notes or None,
        "favorite": favorite,
        "fields": [],
        "reprompt": 0,  # master password re-prompt off. user can turn it on later.
        "collectionIds": None,
    }


def build_login(row: dict, name: str, notes: str, favorite: bool):
    """Build a bitwarden login item from a C2 row."""

    item = base_item(LOGIN_TYPE, name, notes, favorite)
    item["login"] = {
        "uris": build_uris(row.get("Login_URLs")),
        "username": field(row.get("Login_Username")) or None,
        "password": field(row.get("Login_Password")) or None,
        "totp": field(row.get("Login_TOTP")) or None,
    }
    return item


def build_card(row: dict, others: dict, name: str, notes: str, favorite: bool):
    """Build a bitwarden card item from a C2 row and its Others data."""

    item = base_item(CARD_TYPE, name, notes, favorite)

    exp_month, exp_year, bad_expiry = parse_expiry(others.get("Card_Expiry"))

    item["card"] = {
        "cardholderName": field(others.get("Card_Name")) or None,
        "brand": normalize_brand(others.get("Card_Type")) or None,
        "number": field(others.get("Card_Number")).replace(" ", "") or None,
        "expMonth": exp_month or None,
        "expYear": exp_year or None,
        "code": field(others.get("Card_CVV")) or None,
    }

    # bitwarden cards have no slot for these so keep them as custom fields
    extra_fields = [
        ("Card_PIN", others.get("Card_PIN"), HIDDEN_FIELD),
        ("Card_Phone", others.get("Card_Phone"), TEXT_FIELD),
        ("Card_URL", others.get("Card_URL"), TEXT_FIELD),
    ]
    for field_name, value, field_type in extra_fields:
        if is_value_present(value):
            item["fields"].append(custom_field(field_name, value, field_type))

    # if the expiry did not parse keep the raw text so it is not lost
    if bad_expiry:
        item["fields"].append(custom_field("Card_Expiry", bad_expiry, TEXT_FIELD))

    return item


def build_secure_note(others: dict, name: str, notes: str, favorite: bool):
    """Build a bitwarden secure note item from a C2 row and its Others data."""

    secure_text = field(others.get("Secure_Note"))

    # the secure note body is the main content.
    # if the Notes column also has text we keep both joined together.
    if notes and secure_text:
        combined = notes + "\n\n" + secure_text
    elif secure_text:
        combined = secure_text
    else:
        combined = notes

    item = base_item(SECURE_NOTE_TYPE, name, combined, favorite)
    item["secureNote"] = {"type": 0}
    return item


def convert(rows: list[dict]):
    """Turn Synology C2 rows into Bitwarden items. Returns (items, skipped)."""

    items = []
    skipped = []

    for index, row in enumerate(rows):
        row_number = index + 1

        try:
            display = field(row.get("Display_Name")).strip()
            name = display or f"Entry_{row_number}"
            notes = field(row.get("Notes"))
            favorite = is_value_present(row.get("Favorite"))
            others = parse_others(row.get("Others"))

            item_type = ""
            if others is not None:
                item_type = str(others.get("Type", "")).strip().lower()

            match item_type:
                case "card":
                    items.append(build_card(row, others, name, notes, favorite))

                case "secure":
                    items.append(build_secure_note(others, name, notes, favorite))

                case _:  # default to login if the type is unknown or missing
                    username = field(row.get("Login_Username"))
                    password = field(row.get("Login_Password"))
                    uris = build_uris(row.get("Login_URLs"))

                    if username or password or uris:
                        items.append(build_login(row, name, notes, favorite))
                    elif others is not None:
                        reason = f"unsupported type '{others.get('Type')}'"
                        skipped.append((name, reason))
                    else:
                        skipped.append((name, "no login info"))

        except Exception:
            # if one row blows up, skip it instead of crashing the whole run
            display = ""
            if isinstance(row, dict):
                display = field(row.get("Display_Name")).strip()
            skipped.append((display or f"(unnamed row {row_number})", "error reading row"))

    return items, skipped


def read_csv(path: str):
    """Read a C2 export CSV, trying a few encodings. Returns (rows, columns)."""

    encodings = ["utf-8", "utf-16", "cp1252", "iso-8859-1"]
    last_error = None

    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                # synology C2 password always exports comma separated, so use the comma dialect directly.
                # auto detecting the delimiter could wrongly pick ":" on vaults full of URLs and blank out every field. (issue #4)
                reader = csv.DictReader(f, dialect=csv.excel)
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


def save(items: list[dict], path: str):
    """Write items to a Bitwarden JSON file without overwriting an existing file."""

    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    # if the name is taken add "_2", "_3", etc before the extension
    base, extension = os.path.splitext(path)
    target = path
    counter = 2
    while os.path.exists(target):
        target = f"{base}_{counter}{extension}"
        counter += 1

    # bitwarden wants folders and items. we leave folders empty on purpose.
    payload = {"folders": [], "items": items}

    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

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
    folders = []
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
        answer = input("\nDrag your CSV onto this program, or paste its path:\n--> ").strip()
        cleaned = clean_path(answer)
        if cleaned and validate_input_file(cleaned):
            return cleaned

        print("Please try again with a valid file path.")


def main():
    print("Synology C2 Password  ->  Bitwarden converter")
    print("------------------------------------")
    print("Converts a Synology C2 Password export into a Bitwarden JSON file.")
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

    items, skipped = convert(rows)
    if not items:
        print("\nError: none of the entries could be converted.")
        print("Nothing to import, so no file was written.")
        finish(1)

    # save the new file next to the export the user picked
    export_folder = os.path.dirname(os.path.abspath(input_path))
    out_path = os.path.join(export_folder, "bitwarden_file.json")

    try:
        saved = save(items, out_path)
    except Exception as e:
        print(f"\nError saving the Bitwarden file: {e}")
        finish(1)

    print(f"\nConverted {len(items)} entries.")
    print(f"Saved: {saved}")

    if skipped:
        print(f"\nSkipped {len(skipped)} (NOT transferred):")
        for name, reason in skipped:
            print(f"  - {name}  ({reason})")
        print("\nAdd these to Bitwarden manually if needed.")

    print("\nNext steps:")
    print("  1. Open your Bitwarden/Vaultwarden web interface")
    print("  2. Go to Tools > Import Data")
    print("  3. Choose file format: Bitwarden (json)")
    print(f"  4. Upload: {saved}")
    print("\nImportant: securely delete the JSON files after importing!")

    finish(0)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        finish(1)
