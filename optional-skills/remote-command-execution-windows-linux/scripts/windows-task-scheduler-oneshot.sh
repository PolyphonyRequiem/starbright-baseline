#!/bin/bash
# Template: Register a long-running job on Windows via Task Scheduler over SSH
# Persists across SSH disconnects; survives reboots if you set /sc onlogon or /sc onstartup

# Configuration (edit these)
REMOTE_HOST="<gpu-host>"
REMOTE_USER="<winuser>"
TASK_NAME="PythonTrainingJob"
CMD_PATH="C:\\path\\to\\job.cmd"  # Must be fully qualified
START_TIME="14:30"  # HH:MM format, 24-hour

# Pre-flight: test SSH works
echo "[*] Testing SSH connectivity to $REMOTE_HOST..."
ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_USER@$REMOTE_HOST" "whoami" > /dev/null || {
    echo "[!] SSH failed. Set up key-based login first."
    exit 1
}

# Step 1: Clean up any existing task with this name
echo "[*] Cleaning up stale tasks..."
ssh "$REMOTE_USER@$REMOTE_HOST" "taskkill /IM python.exe /F 2>nul; schtasks /delete /tn $TASK_NAME /f 2>nul || true"

# Step 2: Create the .cmd wrapper (optional; modify if your real command is different)
echo "[*] Creating wrapper script on remote..."
ssh "$REMOTE_USER@$REMOTE_HOST" "cat > C:\\temp\\job_wrapper.cmd << 'CMDEOF'
@echo off
setlocal enabledelayedexpansion
cd /d C:\\Users\\<winuser>\\project
C:\\Users\\<winuser>\\venv\\Scripts\\python.exe -u long_job.py >> C:\\temp\\job.log 2>&1
CMDEOF
"

# Step 3: Register task to run once at START_TIME
echo "[*] Registering task '$TASK_NAME' to run at $START_TIME..."
ssh "$REMOTE_USER@$REMOTE_HOST" "schtasks /create /tn $TASK_NAME /tr \"C:\\temp\\job_wrapper.cmd\" /sc once /st $START_TIME /f"

# Step 4: Manually trigger it now (remove if you want to wait for START_TIME)
echo "[*] Triggering task immediately..."
ssh "$REMOTE_USER@$REMOTE_HOST" "schtasks /run /tn $TASK_NAME"

# Step 5: Poll status
echo "[*] Checking task status..."
sleep 2
ssh "$REMOTE_USER@$REMOTE_HOST" "schtasks /query /tn $TASK_NAME /v /fo list" | grep -E "Status|Last Run|Last Result"

# Step 6: Tail the log file in real-time (Ctrl-C to exit)
echo ""
echo "[*] Streaming output (Ctrl-C to stop)..."
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -Command \"Get-Content C:\\temp\\job.log -Wait -Tail 0\""
