# SynologyC2Password to Bitwarden formatter/translater

## Description
Converts a Synology C2 Password export (`.csv`) into a Bitwarden/Vaultwarden importable `.json` (logins, payment cards, and secure notes ONLY).

## Getting Started
First, let's export those juicy passwords from Synology C2 Password:
1. Open the Synology C2 Passwords web interface.
2. Click your profile icon (top right), then `Export`, then `Download`.
3. Save the file to your computer.

![export-from-syno-step1](imgs/export-from-syno-step1.png)
![export-from-syno-step2](imgs/export-from-syno-step2.png)

Now follow the steps for your OS.

### Windows
1. Download the latest `syno2bw.exe` from the [releases page](https://github.com/HyperNylium/SynologyC2Password-to-Bitwarden/releases).
    - Windows Defender SmartScreen may warn you because I'm not a verified publisher. Click `More info` then `Run anyway`.
2. Put `syno2bw.exe` in the **same folder** as your exported Synology C2 `.csv` file.
3. **Double-click `syno2bw.exe`.** That's it.
    - It finds your export, asks you to confirm, converts it, and saves `bitwarden_file.json` in the same folder.
    - The window stays open so you can read the results (and any skipped entries). Press Enter to close it.

**Tip:** You can also drag your exported `.csv` straight onto `syno2bw.exe` to convert it.

<details>
<summary>Advanced: run from a terminal</summary>

In File Explorer, type `cmd` in the folder's address bar and press Enter, then run `syno2bw.exe`.  
You can also pass the export directly: `syno2bw.exe "C:\path\to\C2Password_Export.csv"`.
</details>

### Linux/Source
1. Install Python 3.13 (3.11, 3.12, 3.13 and 3.14 works too):
   ```bash
   sudo apt update && sudo apt install software-properties-common
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install python3.13
   ```
2. Clone and enter the repo:
   ```bash
   git clone https://github.com/HyperNylium/SynologyC2Password-to-Bitwarden.git
   cd SynologyC2Password-to-Bitwarden
   ```
3. Put your C2 export `.csv` in the same folder, then run `python3.13 syno2bw.py` and follow the prompts.

Notes:
- The script writes `bitwarden_file.json` next to your export, so make sure you have write permission in that folder.
- Tested on Python 3.11 and 3.13, but it should work on 3.11+. If you hit an issue, please open one :)

## Import to Bitwarden/Vaultwarden
1. Open your Bitwarden/Vaultwarden web interface.
2. Click the `Tools` on the left side, then `Import`.

![import-into-bitwarden](imgs/import-into-bitwarden.png)

3. Under the "Destination" section, you can choose what vault or folder to import into.
4. Under the "Data" section, make sure the "File format" dropdown is set to `Bitwarden (json)`.
    This is important for the import to work correctly.
5. Click `Choose file`, pick the `bitwarden_file.json` the script made, then click `Import data`. Done!

![import-into-bitwarden-wizard](imgs/import-into-bitwarden-wizard.png)

## How it all started
I wanted to move my passwords from Synology C2 Password to a Vaultwarden instance I set up in Docker. I found [this reddit post](https://www.reddit.com/r/synology/comments/1d21avn/export_c2_password_data/) in the same situation. I only had logins, no cards or notes. Using [this Bitwarden help article](https://bitwarden.com/help/condition-bitwarden-import/) (see the ".csv for individual vault" part), I mapped the C2 fields to the Bitwarden ones.

### Field mapping (Syno C2 -> Bitwarden)

Every item shares these:

| Bitwarden field | From Synology C2 |
|---|---|
| `name` | `Display_Name` (falls back to `Entry_N`) |
| `favorite` | `Favorite` (true when it has a value) |
| `folderId` | left empty, pick the folder in the import screen |
| `notes` | `Notes` |
| `reprompt` | `0` ("Master password re-prompt" off) |

Logins also map:

| Bitwarden field | From Synology C2 |
|---|---|
| `login.uris` | `Login_URLs` (one uri per line) |
| `login.username` | `Login_Username` |
| `login.password` | `Login_Password` |
| `login.totp` | `Login_TOTP` |

Payment cards map:

| Bitwarden field | From Synology C2 (`Others`) |
|---|---|
| `card.cardholderName` | `Card_Name` |
| `card.brand` | `Card_Type` |
| `card.number` | `Card_Number` |
| `card.code` | `Card_CVV` |
| `card.expMonth` / `card.expYear` | `Card_Expiry` |
| custom field `Card_PIN` (hidden) | `Card_PIN` |
| custom field `Card_Phone` | `Card_Phone` |
| custom field `Card_URL` | `Card_URL` |

Secure notes map `Secure_Note` (from `Others`) into the note body.

### Limitations
- Outputs Bitwarden (`.json`). Import using the `Bitwarden (json)` file format.
- Converts logins, payment cards, and secure notes. Other C2 categories (Identity, Bank Account, etc) are not transferred yet. The script lists anything it skips so nothing disappears silently.
- Folders are not created. Pick a destination folder in the import screen.
- "Match detection" is not transferred.

### Good to know
- Tested importing into Vaultwarden with the `Bitwarden (.json)` format, on Python 3.11.5/3.13.11 (Windows 11) and 3.11.9 (Ubuntu 24.04).
- **DO NOT DELETE ANYTHING** from Synology C2 Password until you are 100% sure everything imported correctly.

Feedback and suggestions are welcome! I'm not a professional programmer, so please be gentle. I'm learning as I go.

I hope this helps someone out there :)