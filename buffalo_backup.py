#!/usr/bin/python3 -u
import socket
import time
import os
import subprocess
import threading

# --- CONFIGURATION ---
MAC = "12:34:56:A8:CD:DE"         # Your LinkStation MAC
DEST_IP = "192.168.XXX.XXX"       # Your LinkStation Static IP
BROADCAST_IP = "192.168.XXX.255"  # Your Broadcast IP

SOURCE_PATH = "/mnt/user/YOUR_SOURCE/"
TARGET_PATH = "/mnt/remotes/BUFFALO_BACKUP/"

# Global flag for the background keep-alive service
keep_running = True

def send_combined_wol():
    """Sends Buffalo RAKURAKU + Standard WoL packets."""
    clean_mac = MAC.replace(':', '').replace('-', '')
    mac_bytes = bytes.fromhex(clean_mac)
    
    # 1. Buffalo Packet (26 Bytes)
    buffalo_data = b'RAKURAKU' + b'\x00' * 12 + mac_bytes
    # 2. Standard Magic Packet (102 Bytes)
    standard_data = b'\xff' * 6 + mac_bytes * 16
    
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Send Buffalo & Standard WoL to broadcasts
        s.sendto(buffalo_data, (BROADCAST_IP, 22936))
        s.sendto(buffalo_data, ('255.255.255.255', 22936))
        for port in [7, 9]:
            s.sendto(standard_data, (BROADCAST_IP, port))
            s.sendto(standard_data, ('255.255.255.255', port))

def keep_alive_worker():
    """Background thread sending signals every 2 minutes to keep NAS awake."""
    while keep_running:
        send_combined_wol()
        # Optional: print("[Keep-Alive] Signal sent", flush=True)
        time.sleep(120) 

def is_online(ip):
    """Check if the NAS responds to ping."""
    status = subprocess.run(['ping', '-c', '1', '-W', '1', ip], capture_output=True)
    return status.returncode == 0

# --- MAIN PROCESS ---

print(f"--- Backup Task Started: {time.ctime()} ---", flush=True)

# 1. WAKE UP PHASE
print(f"Waking up LinkStation ({MAC})...", flush=True)
online = False
for attempt in range(1, 41): # Max 40 attempts (~6-7 minutes)
    send_combined_wol()
    if is_online(DEST_IP):
        online = True
        print(f"\n[OK] LinkStation is ONLINE!", flush=True)
        break
    print(".", end="", flush=True)
    time.sleep(10)

if not online:
    print(f"\n[ERROR] LinkStation {DEST_IP} not reachable. Aborting.", flush=True)
    exit(1)

# 2. START KEEP-ALIVE SERVICE
# Start background thread to prevent NAS from sleeping during rsync
t = threading.Thread(target=keep_alive_worker)
t.daemon = True # Thread terminates when main script ends
t.start()

# 3. MOUNT CHECK
print("Waiting 15s for SMB services to initialize...", flush=True)
time.sleep(15)

if not os.path.ismount(TARGET_PATH):
    print(f"[INFO] Attempting to mount {TARGET_PATH}...", flush=True)
    # Trigger Unassigned Devices mount
    subprocess.run(["/usr/local/sbin/rc.unassigned", "mount", TARGET_PATH])
    time.sleep(5)

if not os.path.exists(TARGET_PATH):
    print(f"[ERROR] Target path {TARGET_PATH} not found/mounted!", flush=True)
    exit(1)

# 4. DATA SYNCHRONIZATION (RSYNC)
print("Starting rsync synchronization (Keep-Alive active)...", flush=True)
try:
    # -a: Archive, -v: Verbose, --delete: Mirror source to target
    rsync_cmd = ["rsync", "-av", "--delete", SOURCE_PATH, TARGET_PATH]
    # This block waits until rsync is finished
    subprocess.run(rsync_cmd, check=True)
    print("--- Backup successfully completed! ---", flush=True)
except subprocess.CalledProcessError as e:
    print(f"[ERROR] rsync failed: {e}", flush=True)

# 5. CLEANUP & SHUTDOWN
keep_running = False # Stop the keep-alive thread
print("Keep-Alive service stopped. NAS will sleep in approx. 5 minutes.", flush=True)
print(f"--- Backup Task Finished: {time.ctime()} ---", flush=True)
