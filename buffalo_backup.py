#!/usr/bin/python3 -u
import socket
import time
import os
import subprocess
import threading

# =================================================================
# --- CONFIGURATION ---
# =================================================================
MAC = "12:34:56:A8:CD:DE"             # MAC of LinkStation
DEST_IP = "192.168.XXX.XXX"           # IP of LinkStation
BROADCAST_IP = "192.168.XXX.255"      # Your Broadcast IP

# SMB SETTINGS
REMOTE_SHARE_NAME = "share"           # The folder name ON the Buffalo NAS
SMB_USER = "admin"                    # Your Buffalo username
SMB_PASS = "password"                 # Your Buffalo password

# PATHS
SOURCE_PATH = "/mnt/user/YOUR_SOURCE"
MOUNT_ROOT = "/mnt/remotes/BUFFALO_BACKUP"
TARGET_PATH = os.path.join(MOUNT_ROOT, "YOUR_TARGET/")

# Global flag for the background keep-alive service
keep_running = True

# =================================================================
# --- HELPER FUNCTIONS ---
# =================================================================

def send_combined_wol():
    """Sends Buffalo RAKURAKU + Standard Magic Packets."""
    clean_mac = MAC.replace(':', '').replace('-', '')
    mac_bytes = bytes.fromhex(clean_mac)
    
    buffalo_data = b'RAKURAKU' + b'\x00' * 12 + mac_bytes
    standard_data = b'\xff' * 6 + mac_bytes * 16
    
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Port 22936 is specific to Buffalo 'Wake-on-LAN' listeners
        s.sendto(buffalo_data, (BROADCAST_IP, 22936))
        s.sendto(buffalo_data, ('255.255.255.255', 22936))
        for port in [7, 9]:
            s.sendto(standard_data, (BROADCAST_IP, port))
            s.sendto(standard_data, ('255.255.255.255', port))

def is_online(ip):
    """Check if the NAS responds to ping."""
    status = subprocess.run(['ping', '-c', '1', '-W', '1', ip], capture_output=True)
    return status.returncode == 0

def is_smb_ready(ip):
    """Check if the SMB port 445 is open."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        return s.connect_ex((ip, 445)) == 0

def keep_alive_worker():
    """Thread to prevent LinkStation from sleeping during transfer."""
    while keep_running:
        send_combined_wol()
        time.sleep(120) 

# =================================================================
# --- MAIN PROCESS ---
# =================================================================

print(f"--- Backup Task Started: {time.ctime()} ---", flush=True)

# 1. WAKE UP PHASE
print(f"Waking up LinkStation ({MAC})...", flush=True)
online = False
for attempt in range(1, 41):
    send_combined_wol()
    if is_online(DEST_IP):
        online = True
        print(f"\n[OK] LinkStation is ONLINE (Ping responsive)!", flush=True)
        break
    print(".", end="", flush=True)
    time.sleep(10)

if not online:
    print(f"\n[ERROR] LinkStation {DEST_IP} not reachable. Aborting.", flush=True)
    exit(1)

# 2. START KEEP-ALIVE SERVICE
t = threading.Thread(target=keep_alive_worker)
t.daemon = True
t.start()

# 3. SMB READINESS CHECK
print("Waiting for SMB services to initialize...", flush=True)
smb_ready = False
for _ in range(15): 
    if is_smb_ready(DEST_IP):
        smb_ready = True
        print("[OK] SMB Port 445 is OPEN.", flush=True)
        break
    print("s", end="", flush=True)
    time.sleep(10)

if not smb_ready:
    print("\n[ERROR] NAS is up, but SMB service failed to start.", flush=True)
    exit(1)

# 4. MOUNTING PHASE (Native Linux Mount)
print(f"Ensuring {MOUNT_ROOT} is mounted...", flush=True)
if not os.path.exists(MOUNT_ROOT):
    os.makedirs(MOUNT_ROOT, exist_ok=True)

if not os.path.ismount(MOUNT_ROOT):
    # Try direct mount with SMB 1.0 (Required for older Buffalo models)
    mount_options = f"username={SMB_USER},password={SMB_PASS},iocharset=utf8,vers=1.0"
    mount_cmd = ["mount", "-t", "cifs", f"//{DEST_IP}/{REMOTE_SHARE_NAME}", MOUNT_ROOT, "-o", mount_options]
    
    print(f"[INFO] Mounting //{DEST_IP}/{REMOTE_SHARE_NAME}...", flush=True)
    result = subprocess.run(mount_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"[WARN] Failed with '{REMOTE_SHARE_NAME}'. Trying fallback to 'share'...", flush=True)
        mount_cmd[3] = f"//{DEST_IP}/share"
        result = subprocess.run(mount_cmd, capture_output=True, text=True)

if os.path.ismount(MOUNT_ROOT):
    print("[OK] Mount successful.", flush=True)
else:
    print(f"[FATAL] Mount failed! Linux Error: {result.stderr}", flush=True)
    exit(1)

# Ensure subfolder exists
if not os.path.exists(TARGET_PATH):
    os.makedirs(TARGET_PATH, exist_ok=True)

# 5. DATA SYNCHRONIZATION (RSYNC)
print(f"Starting rsync: {SOURCE_PATH} -> {TARGET_PATH}", flush=True)
try:
    # -a: Archive, -v: Verbose, --delete: Mirror source to target
    rsync_cmd = ["rsync", "-av", "--delete", SOURCE_PATH, TARGET_PATH]
    subprocess.run(rsync_cmd, check=True)
    print("--- Backup successfully completed! ---", flush=True)
except subprocess.CalledProcessError as e:
    print(f"[ERROR] rsync failed: {e}", flush=True)

# 6. CLEANUP
keep_running = False
print(f"--- Backup Task Finished: {time.ctime()} ---", flush=True)
