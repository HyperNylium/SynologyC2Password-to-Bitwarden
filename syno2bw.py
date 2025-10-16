import os
import sys
import csv
from datetime import datetime



def clean_path(path_input: str) -> str:
    """Clean and normalize the provided file path"""
    if not path_input:
        return None

    # Remove surrounding quotes
    path_cleaned = path_input.strip().strip('"').strip("'")

    # Handle Windows paths with backslashes
    path_cleaned = path_cleaned.replace('\\', os.sep).replace('/', os.sep)

    return path_cleaned

def validate_input_file(file_path: str) -> bool:
    """Validate the provided file path"""
    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' was not found.")
        return False

    if not os.path.isfile(file_path):
        print(f"Error: '{file_path}' is not a file.")
        return False

    try:
        # Quick test to see if file is readable
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1)
        return True
    except Exception as e:
        print(f"Error: Cannot read file '{file_path}': {e}")
        return False

def is_value_present(value) -> bool:
    """Check if a value is present and not NaN-like"""
    if value is None:
        return False

    # Handle NaN-like strings and blanks
    text = str(value).strip()
    return text.lower() not in ("", "nan", "none", "null")


print("""
    Welcome to the Synology C2 Password Manager to Bitwarden CSV file formatter!
    This script will help you convert your Synology C2 Password Manager exported CSV file to a Bitwarden/Vaultwarden compatible CSV file.

    Please do remember that if you want to exit the script at any time, you can press 'Ctrl + C' to stop the execution/exit the program at any time :)
    Please follow the instructions below to proceed.
""")

cwd = os.getcwd() # Get the current working directory to use as default path
today = datetime.today().strftime('%Y%m%d')
default_c2_filename = f"C2Password_Export_{today}.csv" # Synology's default export filename format
default_c2_filepath = os.path.join(cwd, default_c2_filename)
default_bitwarden_filepath = os.path.join(cwd, "bitwarden_file.csv")
bitwarden_fieldnames = ["folder", "favorite", "type", "name", "notes", "fields", "reprompt", "login_uri", "login_username", "login_password", "login_totp"]

# Get the path to the Synology C2 password manager exported CSV file
while True:
    c2_password_export_path = input(f"Enter the path to your exported Synology C2 Password Manager CSV file\n(default value if blank: {default_c2_filepath})\n--> ").strip()

    # Set the default path if the user does not provide one (blank input)
    if not c2_password_export_path:
        c2_password_export_path = default_c2_filepath
    else:
        c2_password_export_path = clean_path(c2_password_export_path)

    print(f"Path to Synology C2 Password manager CSV file set to: {c2_password_export_path}\n")
    
    # Validate the input file
    if validate_input_file(c2_password_export_path):
        break
    else:
        print("Please try again with a valid file path.\n")

# Get the path to save the Bitwarden/Vaultwarden compatible CSV file
bitwarden_output_path = input(f"Enter where you would like to save the Bitwarden compatible CSV file\n(default value if blank: {default_bitwarden_filepath})\n--> ").strip()

# Set the default path if the user does not provide one (blank input)
if not bitwarden_output_path:
    bitwarden_output_path = default_bitwarden_filepath
else:
    bitwarden_output_path = clean_path(bitwarden_output_path)

    # Checks to see if the provided path is a directory or a path without a file extension and appends a default filename to said path if so
    if os.path.isdir(bitwarden_output_path) or (not os.path.splitext(bitwarden_output_path)[1] and not os.path.exists(bitwarden_output_path)):
        bitwarden_output_path = os.path.join(bitwarden_output_path, "bitwarden_file.csv")
        print("Directory detected. Adding default filename automatically.")

# Output the path to the Bitwarden/Vaultwarden compatible CSV file
print(f"Bitwarden compatible CSV file save path set to: {bitwarden_output_path}\n")

# Ensure the output directory exists
os.makedirs(os.path.dirname(bitwarden_output_path), exist_ok=True)

# Load the Synology C2 password manager exported CSV file
try:
    print(f"Loading Synology C2 data from: {c2_password_export_path}")

    # Try different encodings to handle various export formats
    encodings_to_try = ["utf-8", "utf-16", "cp1252", "iso-8859-1"]
    c2_password_data = None
    detected_columns = []

    last_error = None
    for encoding in encodings_to_try:
        try:
            with open(c2_password_export_path, "r") as f:
                sample = f.read(4096)
                f.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(sample)
                except Exception:
                    dialect = csv.excel

                reader = csv.DictReader(f, dialect=dialect)
                detected_columns = reader.fieldnames or []

                if not detected_columns:
                    raise ValueError("No columns detected")
                rows = list(reader)
                c2_password_data = rows
                break

        except UnicodeDecodeError:
            continue
        except Exception as e:
            last_error = e
            continue

    if c2_password_data is None:
        if isinstance(last_error, ValueError) and str(last_error).lower() == "no columns detected":
            print(f"Error: The file at {c2_password_export_path} is empty.")
        else:
            print("Error: Could not read the file with any of the supported encodings.")
        sys.exit()

except FileNotFoundError:
    print(f"Error: The file at {c2_password_export_path} was not found.")
    sys.exit()
except Exception as e:
    print(f"Unexpected error while reading the file: {e}")
    sys.exit()

print(f"Number of entries found: {len(c2_password_data)}")
print(f"Detected columns: {list(detected_columns)}")

# Initialize a list to store the processed data
processed_data = []
processing_errors = 0

for index, row in enumerate(c2_password_data):
    try:
        # URLs
        urls_raw = row.get("Login_URLs", "")
        login_uri = ""
        if is_value_present(urls_raw):
            urls_text = str(urls_raw).strip()
            if urls_text.lower() not in ("", "nan", "none", "null"):
                url_list = [url.strip() for url in urls_text.split("\n")]
                login_uri = ",".join(url_list)

        # Favorite
        fav_value = row.get("Favorite")
        favorite = ""
        if is_value_present(fav_value):
            favorite = str(fav_value)

        # Name
        name_value = row.get("Display_Name")
        name = f"Entry_{index+1}"
        if is_value_present(name_value) and str(name_value).strip():
            name = str(name_value)

        # Notes
        notes_value = row.get("Notes")
        notes = ""
        if is_value_present(notes_value):
            notes = str(notes_value)

        # Username
        user_value = row.get("Login_Username")
        login_username = ""
        if is_value_present(user_value):
            login_username = str(user_value)

        # Password
        pass_value = row.get("Login_Password")
        login_password = ""
        if is_value_present(pass_value):
            login_password = str(pass_value)

        # TOTP
        totp_value = row.get("Login_TOTP")
        login_totp = ""
        if is_value_present(totp_value):
            login_totp = str(totp_value)

        processed_data.append({
            "folder": "", # Leave folder empty for user to assign during import
            "favorite": favorite,
            "type": "login", # Assuming all entries are of type "login"
            "name": name,
            "notes": notes,
            "fields": "", # Add custom fields manually in Bitwarden for better accuracy
            "reprompt": 0, # Setting "Master password re-prompt" to "0" for all entries to turn off the option. User can change this later manually.
            "login_uri": login_uri,
            "login_username": login_username,
            "login_password": login_password,
            "login_totp": login_totp,
        })

    except Exception as e:
        processing_errors += 1
        print(f"Warning: Error processing row {index+1}: {e}")

if not processed_data:
    print("Error: No data could be processed.")
    sys.exit()

if processing_errors > 0:
    print(f"Encountered {processing_errors} errors while processing data.")
    print("Continuing with successfully processed entries.")

# Create a new DataFrame for Bitwarden format
bitwarden_data = processed_data

print(f"Successfully processed entries: {len(bitwarden_data)}")

# Save the translated data to a new CSV file
try:
    with open(bitwarden_output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=bitwarden_fieldnames)
        writer.writeheader()
        writer.writerows(bitwarden_data)
    print(f"The Bitwarden import file has been saved to: {bitwarden_output_path}")
    print("\nNext steps:")
    print("1. Open your Bitwarden/Vaultwarden web interface")
    print("2. Go to Tools > Import Data")
    print("3. Select 'Bitwarden (.csv)' as the file format")
    print("4. Upload the created file")
    print("\nImportant: Remember to securely delete the CSV files after importing!")

except Exception as e:
    print(f"An error occurred while saving the file: {e}")
    sys.exit()
