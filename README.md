# SynologyC2Password to Bitwarden formatter/translater

## Description
This script will convert/translate the Synology C2 Password export (.csv) file to a Bitwarden/Vaultwarden (.csv) importable format.

## Getting Started
We first need to export those juicy passwords from Synology C2 Password. So, lets do that!
1. Export your Synology C2 Passwords by following the steps below: \
    1.1. Open the Synology C2 Passwords web interface. \
    1.2. Click on your profile picture icon in the top right corner. \
    1.3. Click on `Export`. \
    1.4. Click on `Download`. \
    1.5. Save the file to your computer. \
![export-from-syno-step1](https://raw.githubusercontent.com/HyperNylium/SynologyC2Password-to-Bitwarden/main/imgs/export-from-syno-step1.png)
![export-from-syno-step2](https://raw.githubusercontent.com/HyperNylium/SynologyC2Password-to-Bitwarden/main/imgs/export-from-syno-step2.png)

This is where Linux users and Windows part ways. Please follow the instructions for your operating system.

### Windows
1. Download the latest version of `syno2bw.exe` from the [releases page](https://github.com/HyperNylium/SynologyC2Password-to-Bitwarden/releases) \
    1.1 Please do note that you will get a warning from Windows Defender SmartScreen. This is because I am not a verified publisher. You can safely ignore this warning by clicking on `More info` and then `Run anyway`.
2. Bring your Synology C2 Password export file to the same directory as the executable.
3. Run the executable by double-clicking on it and follow the instructions.

### Linux
1. Let's install Python 3.11: \
    1.1 Run `sudo add-apt-repository ppa:deadsnakes/ppa` \
    1.2 Run `sudo apt update` \
    1.3 Run `sudo apt install python3.11` \
    1.4 Run `sudo apt-get install python3-pip`\
    1.5 Run `nano ~/.bashrc` and add the following lines to the end of the file:
    ```bash
    alias pip311="/usr/bin/python3.11 -m pip"
    alias py311="/usr/bin/python3.11"
    ```
    1.6 Run `source ~/.bashrc`
3. Clone this repository: \
    2.1 Run `git clone https://github.com/HyperNylium/SynologyC2Password-to-Bitwarden.git` \
    2.2 Run `cd SynologyC2Password-to-Bitwarden`
4. Install the required Python packages: \
    3.1 Run `pip311 install -r requirements.txt`
5. Bring your Synology C2 Password export file to the same directory as the script: \
    4.1 Run `cp /path/to/your/exported/C2Password_Export_XXXXXXXX.csv ./c2_file.csv`
6. Run the script: \
    5.1 Run `py311 syno2bw.py` and follow the instructions.

Notes:
- The script will create a new file called `bitwarden_file.csv` in the directory you choose to save it. Make sure the user executing the script has write permissions in that directory.
- To access the Pythin 3.11 interpreter, you can run `py311` in the terminal and you can run `pip311` to access the Python 3.11 pip package manager.
- I may or may not make a bash script later in the future for Linux users just so it's more easier to use. But for now, this will do.


## Import to Bitwarden/Vaultwarden
1. Open your Bitwarden/Vaultwarden web interface.
2. Click on the `Tools` tab at the top. \
![export-from-syno-step2](https://raw.githubusercontent.com/HyperNylium/SynologyC2Password-to-Bitwarden/main/imgs/import-into-bitwarden1.png)
3. Click on `Import Data` from the `Tools` box on the left. \
![export-from-syno-step2](https://raw.githubusercontent.com/HyperNylium/SynologyC2Password-to-Bitwarden/main/imgs/import-into-bitwarden2.png)
4. Set `import destination` to `My vault` or where ever you want to import the passwords to.
5. Set `Folder` to `-- Select Folder --` or where ever you want to import the passwords to.
6. Set `File format` to `Bitwarden (.csv)`.
7. Click on `Choose file` and select the `bitwarden_file.csv` file that was created by the script/executable.
8. Click on `Import data` and you're done!

## How it all started

I was looking for a way to export my passwords from Synology C2 Password to Bitwarden. I found [this reddit post](https://www.reddit.com/r/synology/comments/1d21avn/export_c2_password_data/) which was pretty much my situation. Setup a Vaultwarden in Docker and wanted to transfer over. I only had login credentials in Synology C2 Password, no cards or notes. \
Heres my comment with my research and translation map I created: \

From [this Bitwarden help article](https://bitwarden.com/help/condition-bitwarden-import/) (area under ".csv for individual vault") I was able to find the Bitwarden headers they use and kind of map out what goes to what.

The Bitwarden CSV format has the following columns (in the order they appear):
- `folder`
- `favorite`
- `type`
- `name`
- `notes`
- `fields`
- `reprompt`
- `login_uri`
- `login_username`
- `login_password`
- `login_totp`

from Syno C2 .csv to Bitwarden .csv format that this script uses:
- `folder`: Left empty for the user to assign during import.
- `favorite`: Mapped from `Favorite`, defaulting to an empty string if missing.
- `type`: Set to `login` as we can't tell from exported Syno C2 what type of credential it is (no column header. Would need further testing).
- `name`: Mapped from `Display_Name`.
- `notes`: Mapped from `Notes`.
- `fields`: Left empty. Cannot accurately translate these to Bitwarden format. Will have to enter manually upon import.
- `reprompt`: Set to `0` (this is only for the "Master password re-prompt" option in Bitwarden and does not exist in Syno C2 Password, hence it is off when translating. `0 = off | 1 = on`).
- `login_uri`: Concatenated URLs from `Login_URLs`.
- `login_username`: Mapped from `Login_Username`.
- `login_password`: Mapped from `Login_Password`.
- `login_totp`: Mapped from `Login_TOTP`.

Now, let's talk about the things this script can't do. 
1. This translation only works for "from Synology C2 Password (.csv) -> Bitwarden (.csv)". 
2. The "type" is always assumed to be "login". That means if you have your card saved in Syno C2 Password, that will not be imported/translated and will probably give an error/crash. This only works for entries with a type of "login". When you log into Synology C2 Password, on the left-hand side there is a section called "Category". This script will only translate the items in the "Login" section. 
3. This script cannot import custom fields for accuracy's sake. You will have to manually add them into Bitwarden or Vaultwarden yourself. Could add this feature in the future if requested.

Things to know:
1. I have only tested importing my re-formatted .csv file to Vaultwarden with the `Bitwarden (.csv)` format.
2. I have done my testing with Python version 3.11.5 on Windows 11 and Python 3.11.9 on a Ubuntu 24.04 system.
3. After exporting your .csv file from Synology C2 Password please **DO NOT DELETE ANYTHING** from Synology C2 Password until you are %100 sure everything has Imported correctly into Bitwarden or Vaultwarden.
4. Does not transfer "Match detection".
5. I will see what I can do about the different types that come from Syno C2 Password (Payment Card, Identity, Bank Account, etc).


For those who want to test this out, please do give feedback! I am open to suggestions and improvements. I am not a professional programmer, so please be gentle. I am learning as I go. I hope this helps someone out there :)
