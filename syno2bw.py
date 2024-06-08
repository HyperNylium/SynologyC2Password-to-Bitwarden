###~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
###
### Author/Creator: HyperNylium
###
### GitHub: https://github.com/HyperNylium/
###
### Version: 1.0.0
### LastEdit: 6/8/2024
###
### pyinstaller --onefile syno2bw.py
###~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

try:
    import pandas as pd
    import sys
    import signal
    from os import getcwd
except ImportError as importError:
    ModuleNotFound = str(importError).split("'")[1]
    print(f"An error occurred while importing dependency '{ModuleNotFound}'.\nPlease run 'pip install -r requirements.txt' to install the required dependency.")
    sys.exit()


#Handle SIGTERM and SIGINT signals to exit the script gracefully (for linux systems)
def handle_signal(sig, frame):
    print("Shutdown signal received. Exiting the script...")
    sys.exit()

print("Registering SIGTERM and SIGINT to handle_signal()")
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)
print("Registered SIGTERM and SIGINT to handle_signal()")


# Store the current working directory for later use
cwd = getcwd()

print("""
    Welcome to the Synology C2 Password Manager to Bitwarden CSV file formatter!
    This script will help you convert your Synology C2 Password Manager exported CSV file to a Bitwarden/Vaultwarden compatible CSV file.

    Please do remember that if you want to exit the script at any time, you can press 'Ctrl + C' to stop the execution/exit the program at any time :)
    Please follow the instructions below to proceed.
""")


# Get the path to the Synology C2 password manager exported CSV file
c2_password_export_path = input("Enter the path to your exported Synology C2 Password Manager CSV file\n(default value if blank: ./c2_file.csv)\n--> ").strip()

# Set the default path if the user does not provide one (blank input)
if not c2_password_export_path:
    c2_password_export_path = f"{cwd}/c2_file.csv"

# Normalize the path
c2_password_export_path = c2_password_export_path.replace('\\', '/')

# Output the path to the Synology C2 password manager exported CSV file
print(f"Path to Synology C2 Password manager CSV file set to: {c2_password_export_path}\n")



# Get the path to save the Bitwarden/Vaultwarden compatible CSV file
bitwarden_output_path = input("Enter where you would like to save the Bitwarden compatible CSV file\n(default value if blank: ./bitwarden_file.csv)\n--> ").strip()

# Set the default path if the user does not provide one (blank input)
if not bitwarden_output_path:
    bitwarden_output_path = f"{cwd}/bitwarden_file.csv"

# Normalize the path
bitwarden_output_path = bitwarden_output_path.replace('\\', '/')

# Output the path to the Bitwarden/Vaultwarden compatible CSV file
print(f"Bitwarden compatible CSV file save path set to: {bitwarden_output_path}\n")



# Load the Synology C2 password manager exported CSV file
try:
    c2_password_data = pd.read_csv(c2_password_export_path)
except FileNotFoundError:
    print(f"Error: The file at {c2_password_export_path} was not found.")
    sys.exit()
except pd.errors.EmptyDataError:
    print(f"Error: The file at {c2_password_export_path} is empty.")
    sys.exit()
except pd.errors.ParserError:
    print(f"Error: The file at {c2_password_export_path} could not be parsed.")
    sys.exit()

# Initialize a list to store the processed data
processed_data = []

# Process each row in the Synology C2 data
for index, row in c2_password_data.iterrows():
    urls = str(row['Login_URLs']).split('\n')
    login_uri = ",".join([url.strip() for url in urls])
    processed_data.append({
        'folder': '',  # Leave folder empty for user to assign during import
        'favorite': row['Favorite'] if not pd.isna(row['Favorite']) else '',  # Leave favorite as is or blank if not found
        'type': 'login',  # Assuming all entries are of type 'login'
        'name': row['Display_Name'],
        'notes': row['Notes'],
        'fields': '',  # Add custom fields manually in Bitwarden for better accuracy
        'reprompt': 0,  # Setting "Master password re-prompt" to "0" for all entries to turn off the option. User can change this later manually.
        'login_uri': login_uri,
        'login_username': row['Login_Username'],
        'login_password': row['Login_Password'],
        'login_totp': row['Login_TOTP']
    })

# Create a new DataFrame for Bitwarden format
bitwarden_data = pd.DataFrame(processed_data)

# Save the translated data to a new CSV file
try:
    bitwarden_data.to_csv(bitwarden_output_path, index=False)
    print(f"The Bitwarden import file has been saved to: {bitwarden_output_path}")
except Exception as e:
    print(f"An error occurred while saving the file: {e}")
