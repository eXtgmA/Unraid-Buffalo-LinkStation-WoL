# Buffalo LinkStation WoL & Backup Automator for Unraid

A Python-based automation script designed for **Unraid** users to use a **Buffalo LinkStation (LS-WVL series)** as a scheduled backup target. It handles the proprietary Buffalo "RAKURAKU" Wake-on-LAN protocol, keeps the NAS awake during long transfers, and synchronizes data using `rsync`.

## Features

  * **Dual-Mode WoL:** Sends both Buffalo proprietary packets and standard Magic Packets to ensure the NAS wakes up from "AUTO" mode.
  * **Keep-Alive Service:** Runs a background thread to prevent the LinkStation from falling asleep during long `rsync` sessions (overcomes the 5-minute AUTO-shutdown).
  * **Smart Wait:** Pings the NAS and waits for it to be ready before attempting to mount or sync.
  * **Unassigned Devices Integration:** Automatically triggers a mount for remote SMB/NFS shares via Unraid's Unassigned Devices plugin.
  * **English Logging:** Clear console output for Unraid's User Scripts logs.

## Prerequisites

1.  **Buffalo LinkStation:** Physical Power Switch must be set to **AUTO**.
2.  **Unraid OS:** With the **User Scripts** plugin installed.
3.  **Python 3:** Installed on Unraid (e.g., via the **NerdTools** plugin).
4.  **Unassigned Devices Plugin:** To manage the remote share mount.

## Configuration

Before running the script, update the following variables in the `CONFIGURATION` section:

| Variable | Description |
| :--- | :--- |
| `MAC` | The MAC address of your LinkStation (e.g., `12:34:45:6A:BC:DE`). |
| `DEST_IP` | The static IP address of your LinkStation. |
| `BROADCAST_IP` | Your network's broadcast address (usually ends in `.255`). |
| `SOURCE_PATH` | The local Unraid path you want to back up (e.g., `/mnt/user/Photos/`). |
| `TARGET_PATH` | The remote mount path (e.g., `/mnt/remotes/BUFFALO_BACKUP/`). |

## Installation

1.  Go to **Settings** \> **User Scripts** in your Unraid WebGUI.
2.  Click **Add New Script** and name it (e.g., `Buffalo_Backup`).
3.  Edit the script and paste the content of `backup_to_buffalo.py`.
4.  Adjust the configuration variables mentioned above.
5.  Set a schedule (e.g., **Custom**: `0 3 */3 * *` for every 3 days at 3:00 AM).

## How it Works

1.  **Wake Phase:** The script sends 5 bursts of WoL packets (Buffalo + Standard). It then pings the NAS every 10 seconds until it responds.
2.  **Maintenance Phase:** Once online, a background thread starts. It sends a "Keep-Alive" signal every 2 minutes.
3.  **Mount Phase:** It checks if the `TARGET_PATH` is mounted. If not, it calls the Unassigned Devices mount command.
4.  **Sync Phase:** `rsync` mirrors the data from source to target.
5.  **Sleep Phase:** Once `rsync` finishes, the Keep-Alive thread stops. Without signals, the LinkStation will automatically shut down after 5 minutes.

## Technical Details: The "RAKURAKU" Protocol

Buffalo LinkStations use a specific UDP packet on **Port 22936** to wake up or stay awake in "AUTO" mode. The packet structure is:

  * **Header:** `RAKURAKU` (8 bytes)
  * **Padding:** 12 null bytes (`\x00`)
  * **Payload:** The 6-byte binary MAC address.

## License

This project is released under the [MIT License](https://www.google.com/search?q=LICENSE).
