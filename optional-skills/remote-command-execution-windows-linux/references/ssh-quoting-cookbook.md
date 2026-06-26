# SSH Quoting Cookbook

Quick reference for common patterns. When in doubt, use Python.

## Pattern 1: Simple remote command (no variables)
```bash
ssh host 'echo hello world'
ssh host 'python -c "print(42)"'
```

## Pattern 2: Pass a local variable to remote
```bash
# Escape the $VAR so it expands on remote, not locally
COUNT=5
ssh host 'python -c "print('\''"$COUNT"\''")"'  # Passes the value of $COUNT to Python
# Or cleaner:
ssh host "python -c \"import sys; print($COUNT)\""  # Double quotes, but escape inner quotes
```

## Pattern 3: List files in Windows directory
```bash
# Python (cross-platform, recommended)
ssh host 'python -c "import os; print(os.listdir(r'"'"'C:\Users\user\files'"'"'))"'

# Or cmd.exe (Windows only)
ssh host 'dir C:\Users\user\files'  # Simple case, no quotes needed
ssh host 'dir "C:\Users\user\My Files"'  # With spaces
```

## Pattern 4: Grep for a pattern (Linux only; use Python for cross-platform)
```bash
# Linux
ssh host 'grep "error" /var/log/syslog'

# Windows alternative (Python, works everywhere)
ssh host 'python -c "
with open(r'"'"'C:\logs\app.log'"'"') as f:
    for line in f:
        if \"error\" in line.lower():
            print(line.rstrip())
"'
```

## Pattern 5: Python script with file I/O
```bash
# Count files matching a pattern
ssh host 'python -c "
import os
d = r'"'"'C:\project\data'"'"'
wav_files = [f for f in os.listdir(d) if f.endswith(\".wav\")]
print(f\"Found {len(wav_files)} WAV files\")
"'
```

## Pattern 6: Multiline script (use here-doc or write file)
```bash
# Option A: Write a temp script on remote
ssh host 'cat > /tmp/job.py << '"'"'EOF'"'"'
import os
import json
files = os.listdir(".")
print(json.dumps({"count": len(files)}))
EOF
python /tmp/job.py'

# Option B: scp a local script, run it
scp local_script.py host:/tmp/
ssh host 'python /tmp/local_script.py'
```

## Pattern 7: Windows Task Scheduler launch (one-shot)
```bash
# Register and fire
ssh host 'schtasks /create /tn MyJob /tr "C:\\path\\job.cmd" /sc once /st 14:30'
ssh host 'schtasks /run /tn MyJob'

# Query status
ssh host 'schtasks /query /tn MyJob /v /fo list'

# Delete when done
ssh host 'schtasks /delete /tn MyJob /f'
```

## Pattern 8: Check if a Windows process is running
```bash
# Simple: just list python processes
ssh host 'tasklist | find "python"'

# Verbose: get full details
ssh host 'tasklist /v /fo csv | find "python"'

# Python (cross-platform)
ssh host 'python -c "import subprocess; procs = subprocess.check_output([\"tasklist\"]).decode(); print([line for line in procs.split(chr(10)) if \"python\" in line.lower()])"'
```

## Debugging: Add verbosity
```bash
# See exactly what SSH receives
ssh -vvv host 'echo test' 2>&1 | grep -E "Sending|Received"

# Test quoting locally first (same shell, no SSH)
eval 'echo "test 1"; echo test 2'  # Check the command parses
```

## The universal escape: Python one-liner
When you're not sure which quoting strategy will work, **just use Python**:

```bash
ssh host 'python -c "
import sys, os, json

# Do whatever you need here
result = {\"files\": os.listdir(\".\"), \"pwd\": os.getcwd()}
print(json.dumps(result))
"'
```

Python's string literal rules are simpler and more uniform across platforms than shell quoting rules.
