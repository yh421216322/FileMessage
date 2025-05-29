# LAN File Sharer

## 1. Application Overview

LAN File Sharer is a desktop application designed for easy file sharing between computers on the same local area network (LAN). It allows users to share files from a designated folder, protected by a 4-digit PIN. Other users on the network running the application with the same PIN can discover each other, browse shared files, and download them.

**Core Features:**

*   **Shared Folder:** Designate a specific folder on your computer to share its contents.
*   **PIN Protection:** Secure access to your shared files using a 4-digit PIN. Only peers with the matching PIN can interact.
*   **Peer Discovery:** Automatically discover other users on the LAN running the application with the same PIN.
*   **Remote File Listing:** Browse the contents of a selected peer's shared folder.
*   **File Downloading:** Download files from discovered peers directly to your computer.

## 2. Requirements

*   **Operating System:** Windows.
*   **Python:** Required if you intend to run the application from source code or build the executable yourself. If using a pre-built executable, Python is not needed. (Python 3.8+ recommended).

## 3. Setup & Configuration

The application uses a `config.json` file (located in the same directory as the executable or `src/main.py` if running from source) to store your shared folder path and PIN hash. However, you typically **do not need to edit this file directly**. All configuration is done through the application's user interface.

*   **Setting the Shared Folder:**
    1.  Start the LAN File Sharer application.
    2.  In the top "Settings" area, you'll see "Shared Folder: Not set" (or the current path).
    3.  Click the "Select Shared Folder" button.
    4.  A dialog will appear. Browse to and select the folder you wish to share.
    5.  The application will update the path and save your selection.

*   **Setting the 4-digit PIN:**
    1.  Start the application.
    2.  In the "Settings" area, you'll see "PIN: Not set" (or "PIN: ****" if already set).
    3.  Click the "Set/Change PIN" button.
    4.  An input dialog will prompt you to "Enter a 4-digit PIN:".
    5.  Enter your desired 4-digit numeric PIN and click "OK".
    6.  If valid, the PIN will be set (or updated), and the application will save it. An invalid PIN (e.g., not 4 digits) will show an error.

**Important:** Both the Shared Folder and PIN must be set for the application's discovery and sharing features to become active.

## 4. How to Use

*   **Starting the Application:**
    *   If using the executable (`LANFileSharer.exe`), double-click it.
    *   If running from source, navigate to the `lan_file_sharer` directory in your terminal and run: `python src/main.py`.

*   **Main UI Layout:**
    *   **Settings Area (Top):** Displays the current Shared Folder path and PIN status. Contains buttons to "Select Shared Folder" and "Set/Change PIN".
    *   **Peers List (Left Pane):** Lists discovered peers on the network who are using the same PIN. Peers are typically identified by a unique ID prefix and their IP address/port.
    *   **Remote Files List (Middle Pane):** Shows files and folders from the shared directory of a peer selected from the Peers List.
    *   **Download Button (Right Pane):** A "Download Selected" button used to download files from the Remote Files list.
    *   **Status Bar (Bottom):** Displays current application status, ongoing actions (like downloading), or error messages.

*   **Discovering Peers:**
    *   Once your Shared Folder and PIN are set, the application automatically starts broadcasting its presence and listening for other peers.
    *   Peers running the application with the **exact same 4-digit PIN** on the same LAN will appear in the "Discovered Peers" list.

*   **Browsing Files:**
    1.  Select a peer from the "Discovered Peers" list by clicking on their entry.
    2.  The "Remote Files" list will populate with the contents of that peer's shared folder (initially showing the root directory).
    3.  Directory entries are prefixed with `[D]`.
    4.  To navigate into a directory, double-click its entry (e.g., `[D] MyFolder`).
    5.  To navigate to the parent directory, double-click the `.. (Parent Directory)` entry or click the "Up One Level" button.

*   **Downloading Files:**
    1.  In the "Remote Files" list, select the file you wish to download (do not select a directory).
    2.  Click the "Download Selected" button (located in the rightmost pane).
    3.  A "Save As" dialog will appear. Choose the location on your computer where you want to save the file and click "Save".
    4.  The download progress will be shown in the Status Bar.
    5.  A message will confirm completion or indicate an error.

## 5. Building from Source (Creating the EXE)

If you want to create the `LANFileSharer.exe` yourself, you'll need Python and the dependencies listed in `requirements.txt`.

**Dependencies (`requirements.txt`):**
```txt
requests
customtkinter
pyinstaller
```
(Note: `pyinstaller` is only needed for building, not for running from source if you already have the other dependencies.)

**Build Script (`build.bat`):**
Create a file named `build.bat` in the root directory of the `lan_file_sharer` project (the same directory as this README) with the following content:

```bat
@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo Running PyInstaller...
pyinstaller --onefile --windowed --name LANFileSharer --distpath ./dist --workpath ./build src/main.py
echo Build process finished. Check the 'dist' folder.
pause
```

**Build Instructions:**
1.  Ensure Python is installed and added to your system's PATH.
2.  Open a command prompt or terminal.
3.  Navigate to the `lan_file_sharer` root directory.
4.  Install PyInstaller if you haven't already: `pip install pyinstaller`
5.  Run the build script: `build.bat`
6.  If successful, the `LANFileSharer.exe` will be located in a new `dist` sub-directory.

## 6. Logging

For troubleshooting purposes, the application maintains a log file.
*   **Log File Name:** `lan_sharer.log`
*   **Default Location:** `HOME/.lan_sharer/lan_sharer.log`
    *   `HOME` refers to your user's home directory (e.g., `C:\Users\YourUsername`).
    *   The `.lan_sharer` directory is created automatically.

This log file contains information about application startup, discovery events, file operations, and any errors encountered.

## 7. Troubleshooting (Basic)

*   **Peers Not Appearing:**
    *   **PIN Mismatch:** Ensure all peers are using the exact same 4-digit PIN.
    *   **Firewall:** Your system's firewall (e.g., Windows Defender Firewall) might be blocking the application or its network communication (UDP port 60000 for discovery, TCP for file server - default 8080). You may need to create an exception for the application.
    *   **LAN Connection:** Verify all computers are connected to the same local area network. Check network cables and Wi-Fi connections.
    *   **Application Not Running/Configured:** Ensure the application is running on other peers and that their Shared Folder and PIN are set.

*   **Download Issues:**
    *   **Remote Peer Status:** The peer you are trying to download from might have closed the application or changed their PIN/shared folder. Try re-selecting the peer.
    *   **Local Disk Space:** Ensure you have enough free disk space in the chosen save location.
    *   **Network Interruption:** A poor network connection can cause downloads to fail.
    *   **File Server Error on Peer:** The remote peer's application might have encountered an issue serving the file. Check their logs if possible.

---
This README provides a guide to setting up, using, and building the LAN File Sharer application.
