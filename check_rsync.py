import json
import os
import sys

lockfile_path = os.path.expanduser("~/.scheduler/head.lock")

if not os.path.exists(lockfile_path):
    print(f"Lockfile {lockfile_path} does not exist. Head node might not be running.")
    sys.exit(1)

try:
    with open(lockfile_path, 'r') as f:
        data = json.load(f)
    
    rsync_pid = data.get('rsync_pid')
    
    if rsync_pid:
        try:
            os.kill(rsync_pid, 0)
            print(f"Rsync server is running. PID: {rsync_pid}")
        except OSError:
            print(f"Rsync server PID {rsync_pid} found in lockfile, but process is not running.")
    else:
        print("Rsync PID not found in lockfile. It might not be enabled or started.")
        
except Exception as e:
    print(f"Error checking rsync status: {e}")
