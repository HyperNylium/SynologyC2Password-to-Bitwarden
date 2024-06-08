# SynologyC2Password to Bitwarden formatter

## Description
This script will convert the Synology C2 Password export (.csv) file to a Bitwarden/Vaultwarden (.csv) importable format.

## Getting Started
We first need to export those juicy passwords from Synology C2 Password. So, lets do that!
1. Export your Synology C2 Passwords by following the steps below: \
    1.1. Open the Synology C2 Passwords web interface. \
    1.2. Click on your profile picture icon in the top right corner. \
    1.3. Click on `Export`. \
    1.4. Click on `Download`. \
    1.5. Save the file to your computer. \
![export-from-syno-step1](https://raw.githubusercontent.com/HyperNylium/SynologyC2Password-to-Bitwarden-formatter/main/imgs/export-from-syno-step1.png)
![export-from-syno-step2](https://raw.githubusercontent.com/HyperNylium/SynologyC2Password-to-Bitwarden-formatter/main/imgs/export-from-syno-step2.png)

This is where Linux users and Windows part ways. Please follow the instructions for your operating system.

### Windows
1. Download the latest version of `syno2bw.exe` from the [releases page](https://github.com/HyperNylium/SynologyC2Password-to-Bitwarden-formatter/releases) \
    1.1 Please do note that you will get a warning from Windows Defender SmartScreen. This is because I am not a verified publisher. You can safely ignore this warning by clicking on `More info` and then `Run anyway`.
2. Bring your Synology C2 Password export file to the same directory as the executable.
3. Run the executable by double-clicking on it and follow the instructions.

### Linux
1. Let's install Python 3.11: \
    1.1 Run `sudo add-apt-repository ppa:deadsnakes/ppa` \
    1.2 Run `sudo apt update` \
    1.3 Run `sudo apt install python3.11` \
    1.4 Run `nano ~/.bashrc` and add the following lines to the end of the file:
    ```bash
    alias pip311="/usr/bin/python3.11 -m pip"
    alias py311="/usr/bin/python3.11"
    ```
    1.5 Run `source ~/.bashrc`
2. Clone this repository: \
    2.1 Run `git clone https://github.com/HyperNylium/SynologyC2Password-to-Bitwarden-formatter.git` \
    2.2 Run `cd SynologyC2Password-to-Bitwarden-formatter`
3. Install the required Python packages: \
    3.1 Run `pip311 install -r requirements.txt`
4. Bring your Synology C2 Password export file to the same directory as the script: \
    4.1 Run `cp /path/to/your/exported/C2Password_Export_XXXXXXXX.csv ./c2_file.csv`
5. Run the script: \
    5.1 Run `py311 syno2bw.py` and follow the instructions.

Notes:
- The script will create a new file called `bitwarden_file.csv` in the directory you choose to save it. Make sure the user executing the script has write permissions in that directory.
- To access the Pythin 3.11 interpreter, you can run `py311` in the terminal and you can run `pip311` to access the Python 3.11 pip package manager.
- I may or may not make a bash script later in the future for Linux users just so it's more easier to use. But for now, this will do.
