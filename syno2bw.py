###~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
###
### Author/Creator: HyperNylium
### GitHub: https://github.com/HyperNylium/
### 
### Contributor: Jonas (path handling improvements and error fixes)
### 
### Version: 1.1.0
### LastEdit: 27/9/2024
### 
### Improvements in v1.1.0:
### - Fixed path handling issues with quotes on Windows
### - Better error handling and user feedback
### - Auto-detection of directory vs file paths
### - Support for multiple text encodings
### - More robust CSV parsing
### 
### pyinstaller --onefile syno2bw.py
###~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

try:
    import pandas as pd
    import sys
    import signal
    import os
    from pathlib import Path
except ImportError as importError:
    ModuleNotFound = str(importError).split("'")[1]
    print(f"An error occurred while importing dependency '{ModuleNotFound}'.\nPlease run 'pip install -r requirements.txt' to install the required dependency.")
    sys.exit()


# Handle SIGTERM and SIGINT signals to exit the script gracefully (for linux systems)
def handle_signal(sig, frame):
    print("Shutdown signal received. Exiting the script...")
    sys.exit()


def clean_path(path_input):
    """Clean and normalize file paths, removing quotes and handling Windows paths properly"""
    if not path_input:
        return None
    
    # Remove surrounding quotes that users often add when copy-pasting paths
    path_cleaned = path_input.strip().strip('"').strip("'")
    
    # Convert to Path object for better cross-platform handling
    return Path(path_cleaned)


def validate_input_file(file_path):
    """Check if the input CSV file exists and is accessible"""
    if not file_path.exists():
        print(f"Error: The file '{file_path}' was not found.")
        return False
    
    if not file_path.is_file():
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


print("Registering SIGTERM and SIGINT to handle_signal()")
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)
print("Registered SIGTERM and SIGINT to handle_signal()")

# Store the current working directory for later use
cwd = os.getcwd()

print("""
    Welcome to the Synology C2 Password Manager to Bitwarden CSV file formatter!
    This script will help you convert your Synology C2 Password Manager exported CSV file to a Bitwarden/Vaultwarden compatible CSV file.

    Please do remember that if you want to exit the script at any time, you can press 'Ctrl + C' to stop the execution/exit the program at any time :)
    Please follow the instructions below to proceed.
""")

# Get the path to the Synology C2 password manager exported CSV file
while True:
    c2_password_export_path = input("Enter the path to your exported Synology C2 Password Manager CSV file\n(default value if blank: ./c2_file.csv)\n--> ").strip()

    # Set the default path if the user does not provide one (blank input)
    if not c2_password_export_path:
        c2_password_export_path = Path(f"{cwd}/c2_file.csv")
    else:
        c2_password_export_path = clean_path(c2_password_export_path)

    # Output the path to the Synology C2 password manager exported CSV file
    print(f"Path to Synology C2 Password manager CSV file set to: {c2_password_export_path}\n")
    
    # Validate the input file
    if validate_input_file(c2_password_export_path):
        break
    else:
        print("Please try again with a valid file path.\n")


# Get the path to save the Bitwarden/Vaultwarden compatible CSV file
bitwarden_output_path = input("Enter where you would like to save the Bitwarden compatible CSV file\n(default value if blank: ./bitwarden_file.csv)\n--> ").strip()

# Set the default path if the user does not provide one (blank input)
if not bitwarden_output_path:
    bitwarden_output_path = Path(f"{cwd}/bitwarden_file.csv")
else:
    bitwarden_output_path = clean_path(bitwarden_output_path)
    
    # If user provided a directory instead of a file, add default filename
    # This handles cases where users paste a folder path instead of a full file path
    if bitwarden_output_path.is_dir() or (not bitwarden_output_path.suffix and not bitwarden_output_path.exists()):
        bitwarden_output_path = bitwarden_output_path / "bitwarden_file.csv"
        print("Directory detected. Adding default filename automatically.")

# Output the path to the Bitwarden/Vaultwarden compatible CSV file
print(f"Bitwarden compatible CSV file save path set to: {bitwarden_output_path}\n")

# Ensure the output directory exists
bitwarden_output_path.parent.mkdir(parents=True, exist_ok=True)

# Load the Synology C2 password manager exported CSV file
try:
    print(f"Loading Synology C2 data from: {c2_password_export_path}")
    
    # Try different encodings to handle various export formats
    encodings_to_try = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252']
    c2_password_data = None
    
    for encoding in encodings_to_try:
        try:
            c2_password_data = pd.read_csv(c2_password_export_path, encoding=encoding)
            print(f"File successfully loaded with {encoding} encoding")
            break
        except UnicodeDecodeError:
            continue
    
    if c2_password_data is None:
        print("Error: Could not read the file with any of the supported encodings.")
        sys.exit()
        
except FileNotFoundError:
    print(f"Error: The file at {c2_password_export_path} was not found.")
    sys.exit()
except pd.errors.EmptyDataError:
    print(f"Error: The file at {c2_password_export_path} is empty.")
    sys.exit()
except pd.errors.ParserError as e:
    print(f"Error: The file at {c2_password_export_path} could not be parsed: {e}")
    sys.exit()
except Exception as e:
    print(f"Unexpected error while reading the file: {e}")
    sys.exit()

print(f"Number of entries found: {len(c2_password_data)}")
print(f"Detected columns: {list(c2_password_data.columns)}")

# Initialize a list to store the processed data
processed_data = []
processing_errors = 0

# Process each row in the Synology C2 data
for index, row in c2_password_data.iterrows():
    try:
        # Handle multiple URLs properly - some entries have multiple URLs separated by newlines
        urls_raw = str(row.get('Login_URLs', ''))
        if urls_raw and urls_raw != 'nan':
            urls = urls_raw.split('\n')
            login_uri = ",".join([url.strip() for url in urls if url.strip()])
        else:
            login_uri = ''
        
        processed_data.append({
            'folder': '',  # Leave folder empty for user to assign during import
            'favorite': str(row.get('Favorite', '')) if pd.notna(row.get('Favorite')) else '',
            'type': 'login',  # Assuming all entries are of type 'login'
            'name': str(row.get('Display_Name', f'Entry_{index+1}')),
            'notes': str(row.get('Notes', '')) if pd.notna(row.get('Notes')) else '',
            'fields': '',  # Add custom fields manually in Bitwarden for better accuracy
            'reprompt': 0,  # Setting "Master password re-prompt" to "0" for all entries to turn off the option. User can change this later manually.
            'login_uri': login_uri,
            'login_username': str(row.get('Login_Username', '')) if pd.notna(row.get('Login_Username')) else '',
            'login_password': str(row.get('Login_Password', '')) if pd.notna(row.get('Login_Password')) else '',
            'login_totp': str(row.get('Login_TOTP', '')) if pd.notna(row.get('Login_TOTP')) else ''
        })
        
    except Exception as e:
        processing_errors += 1
        print(f"Warning: Error processing row {index+1}: {e}")

if processing_errors > 0:
    print(f"Encountered {processing_errors} errors while processing data.")
    print("Continuing with successfully processed entries.")

if not processed_data:
    print("Error: No data could be processed.")
    sys.exit()

# Create a new DataFrame for Bitwarden format
bitwarden_data = pd.DataFrame(processed_data)

print(f"Successfully processed entries: {len(bitwarden_data)}")

# Save the translated data to a new CSV file
try:
    bitwarden_data.to_csv(bitwarden_output_path, index=False, encoding='utf-8')
    print(f"The Bitwarden import file has been saved to: {bitwarden_output_path}")
    print(f"\nNext steps:")
    print(f"1. Open your Bitwarden/Vaultwarden web interface")
    print(f"2. Go to Tools > Import Data")
    print(f"3. Select 'Bitwarden (.csv)' as the file format")
    print(f"4. Upload the created file")
    print(f"\nImportant: Remember to securely delete the CSV files after importing!")
    
except Exception as e:
    print(f"An error occurred while saving the file: {e}")
    sys.exit()
