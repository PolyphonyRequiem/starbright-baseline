---
name: remote-command-execution-windows-linux
description: Execute remote commands reliably across Windows and Linux hosts over SSH. Covers quoting, backgrounding, tool-availability gaps, and patterns to avoid brittle shell escaping and silent process death.
---

# Remote Command Execution: Windows × Linux

## When to use
Use this skill whenever you need to run commands on a remote host over SSH and the remote host **might be Windows** or the local shell is unfamiliar (Bash on Windows, PowerShell, cmd.exe, Git Bash). This skill prevents:
- Shell quoting nightmares (`"` vs `'` vs `\"` layers of escaping)
- Silent process death (backgrounding that looks successful but actually orphans)
- Tool-availability surprises (`nohup` doesn't exist on Windows, `grep` not in PowerShell, etc.)
- Cross-platform encoding failures (cp1252 vs UTF-8 emoji crashes)

## Core principle: shell quoting is the enemy
**Every layer of quoting (Bash → SSH → remote shell) is a chance for escaping to fail.** The more layers, the more likely a quote inside a nested string breaks the whole thing. Prefer **Python one-liners** as the atomic cross-platform unit instead of shell commands.

## Trigger: "I need to run X on a Windows host"
**First action:** Confirm what shell you're running locally (Bash, PowerShell, cmd.exe) AND what shell will execute on the remote (cmd.exe by default on Windows unless you changed it, but could be PowerShell). Different combinations have different safe quoting strategies.

## Default approaches

### ✅ SAFE: Python one-liner via SSH
**Use this for any command where Python can do it.** Python escaping is uniform across all shell layers because the Python string literal doesn't get re-parsed by the remote shell.

```bash
# Counting WAV files in a directory (works on ANY host: Linux, macOS, Windows)
ssh -i ~/.ssh/id_ed25519_host user@host 'python -c "import os; d=r'\''C:\\Users\\user\\audio'\''; print(len([f for f in os.listdir(d) if f.endswith(\".wav\")]))"'
```

**Why this works:**
- The Python string is a Python literal (`r''...''`), not a shell token. It gets passed to `python -c` untouched.
- Backslashes in `C:\\Users\\...` are inside the raw string, so they don't get shell-escaped.
- Works identically on Linux (forward slashes) and Windows (backslashes).
- No intermediate shell parsing of nested quotes.

**Anatomy of the quoting:**
```
ssh host 'python -c "import os; ...; print(...)"'
          ^                                        ^
          |                                        |
          Double-quoted outer shell command to ssh
          (works the same in Bash or cmd.exe)
```

Inside Python, use `r'...'` (raw strings) for Windows paths:
```python
d = r'C:\Users\user\path'  # The \U and \p are literal backslashes, not escape sequences
```

### ⚠️ MEDIUM: PowerShell -Command (Windows only, colder starts)
If the command is Windows-specific (registry, WMI, service control) and Python won't do it:

```bash
ssh host 'powershell -Command "Get-Service sshd | Select-Object Status,StartType"'
```

**Risks:**
- PowerShell cold-starts every invocation (~5–8 seconds).
- Quoting inside `-Command` requires escaping inner double-quotes as `\"`; single quotes lose their special meaning in PowerShell.
- If anything in the command string contains a literal `"` or `\`, you'll need multiple escape layers.

**Safer variant — pass a script block instead of a raw command:**
```bash
ssh host 'powershell -Command { $service = Get-Service sshd; $service.Status }'
```

### ✅✅✅ BEST for writing a file/script remotely: base64 the payload, decode on the far side

When you need to create a `.bat` / `.ps1` / config file on a Windows host and the content has paths, quotes, or redirections, **do not** try to build it inline through `Start-Process`, a PowerShell here-string (`@"..."@`), or `Set-Content` with the body in the SSH command — every one of those re-parses through Bash → SSH → PowerShell and mangles silently (empty stdout, exit 0, no file). Confirmed the hard way 2026-06-05: four inline approaches (`Start-Process` with nested backtick-quotes, a `@"..."@` here-string, multi-line `Set-Content`) all produced empty output before base64 worked first try.

**The robust move: build the file content LOCALLY, base64-encode it, ship the base64 (which is quote-safe — only `[A-Za-z0-9+/=]`), and decode+write on the remote with .NET.**

```bash
# 1. Author the file locally with a normal heredoc — real quoting, real newlines
cat > /tmp/start-server.bat <<'EOF'
@echo off
cd /d C:\Users\me\app
server.exe -m "C:\Users\me\models\model.gguf" --host 0.0.0.0 --port 8080 > C:\Users\me\srv.log 2>&1
EOF

# 2. base64 (single line, -w0) and decode on the remote — no quoting layers survive to bite you
B64=$(base64 -w0 /tmp/start-server.bat)
ssh -o BatchMode=yes <gpu-host> "powershell -NoProfile -Command \"[IO.File]::WriteAllBytes('C:\\Users\\me\\start-server.bat', [Convert]::FromBase64String('$B64')); Write-Output 'WROTE'; Get-Content C:\\Users\\me\\start-server.bat\""
```

Why this beats `scp` for small payloads: it's a **single SSH call** (no second connection, no scp destination-path quoting), works even when scp is awkward, and `WriteAllBytes` from a base64 string writes **exact bytes** — so you also control encoding (prepend the UTF-8 BOM `EF BB BF` yourself if the file is a `.ps1`, see the PS-encoding section). The only variable interpolated into the command is `$B64`, which can't contain a shell metacharacter. After writing, always read it back (`Get-Content`) to prove it landed correctly before you execute it.

### ❌ AVOID: cmd.exe pipes over SSH
```bash
ssh host 'cmd /c "dir /b path\*.wav | find /c ".wav""'  # 🚫 fragile quoting nightmare
```

Why:
- Each `|` is parsed by cmd.exe's parser, and the quoting rules are different from Bash.
- `find /c ".wav"` is not a filter like grep; it's a count operation with its own quoting rules.
- Escape layers: Bash → SSH → cmd.exe → cmd.exe's pipe context = four chances for quotes to break.
- When it breaks, the error is cryptic (`Access denied - \\`, `Unexpected token`, etc.) with no indication of what went wrong.

**Better alternative:** Write a one-line PowerShell or Python instead.

## Backgrounding: process lifecycle management

### ✅✅✅ BEST: `Invoke-CimMethod Win32_Process Create` for true SSH-launched detach
Confirmed broken 2026-06-02 across multiple sessions: `Start-Process -WindowStyle Hidden -PassThru` launched **from an ssh-spawned PowerShell** dies when that SSH-side PowerShell exits, even with `-PassThru`. Process appears in `tasklist` for ~30s, then vanishes silently. Two separate jobs died this way (FLUX download + LoRA bake) before the cause was identified.

**Fix: use CIM (WMI) to ask the OS to spawn the process outside the SSH session tree entirely.**
```powershell
$cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\you\job.ps1'
$p = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
Write-Host ("PID " + $p.ProcessId)
```

The Win32_Process.Create method runs the new process as a child of the WMI/CIM service tree, not of the calling shell. SSH disconnect cannot touch it. This is the same mechanism `psexec` and most "really detach" tools use under the hood.

**When to use this vs Task Scheduler:**
- CIM-Create: one-shot, no schedule needed, you want the PID back immediately to log. Cleaner for "fire and verify via STATUS file."
- Task Scheduler: recurring jobs, jobs that need to survive reboot, jobs needing specific security context.

### ✅ FALLBACK: Windows `Start-Process -PassThru` (LOCAL launches only)
For background work launched from a **local** PowerShell session (RDP, console, persistent powershell.exe — NOT ssh-spawned), `Start-Process` with `-WindowStyle Hidden -PassThru` works fine. The child's parent (the local powershell.exe) sticks around so the child isn't reparented to a dying SSH session.

If you're not 100% sure the launching shell is local-persistent, **default to CIM-Create**.

```powershell
$p = Start-Process powershell.exe -ArgumentList @(
  "-NoProfile","-ExecutionPolicy","Bypass","-File","$root\job.ps1"
) -WindowStyle Hidden -PassThru
Write-Host ("PID " + $p.Id)
```

**Verify lifecycle correctly: NEVER use PID-still-alive as the success signal.**
The bake-script-vanishing failure mode that bit us hard 2026-06-02 had two indistinguishable causes from the PID-probe vantage point:
1. Script parse-crashed in 200ms — PID gone 30s later when we checked, no log written.
2. Script ran fine, finished phase fast — PID briefly visible, then long-running grandchild took over (different PID), so `Get-Process -Id <original>` returned nothing even though work was happening.

Both look identical: "PID 14544 gone." Both lead to relaunch-loop tail-chasing.

**Right verification cascade (in order):**
1. **Parse-smoke the `.ps1` BEFORE launching** (see PS-encoding section above). Eliminates failure-mode #1 entirely.
2. **Have the script itself emit a STATUS file and append-only log on every phase boundary.** The job-watcher's job is to read those artifacts, not to grep `ps`.
3. **Check the log file's mtime, not the PID's existence.** If `bake.log` has grown in the last N minutes, work is happening — could be the original PID or a grandchild, doesn't matter. If mtime is stale beyond expected phase duration, the job is truly hung.
4. **Schedule a recurring watcher cron** (`every 10m`) that reads STATUS/DONE/FAIL/log-mtime and stays silent on normal progress, pinging the user only on terminal outcomes (success, fail, hung). Pattern: `if DONE: pause-self + notify; elif FAIL: pause-self + notify with reason + last log lines; elif log-stale-N-min: pause-self + notify hung; else: exit silent`.

**Self-instrumenting job script template:**
```powershell
$ROOT   = "$env:USERPROFILE\myjob"
$LOG    = "$ROOT\job.log"
$STATUS = "$ROOT\STATUS"
$DONE   = "$ROOT\DONE"
$FAIL   = "$ROOT\FAIL"
New-Item -ItemType Directory -Force -Path $ROOT | Out-Null
Remove-Item -Force $DONE,$FAIL -ErrorAction SilentlyContinue

function Log([string]$msg) {
  $line = "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')] $msg"
  $line | Out-File -FilePath $LOG -Append -Encoding utf8
}
function SetStatus([string]$s) { $s | Out-File -FilePath $STATUS -Encoding utf8 -NoNewline; Log "STATUS -> $s" }
function Die([string]$reason) { Log "FATAL: $reason"; $reason | Out-File -FilePath $FAIL -Encoding utf8; exit 1 }

SetStatus "phase1_setup"
# ... work ...
SetStatus "phase2_train"
# ... work ...

"$result_path" | Out-File -FilePath $DONE -Encoding utf8
SetStatus "done"
```

### ❌ WRONG: SSH with trailing `&` in the command
```bash
ssh host "nohup python long_job.py &"  # 🚫 WILL DIE when SSH connection drops
```

Why: The trailing `&` backgrounds the process *inside the SSH session*, not from the local shell. When your SSH connection closes (network hiccup, timeout, or you manually exit), the session context is destroyed and the backgrounded child is sent `SIGHUP` / `SIGTERM`. It dies silently.

### ✅ MEDIUM: SSH with detached output (short jobs only)
```bash
# Run up to ~5 minutes, don't care about stdout/stderr
ssh host 'python job.py > /tmp/job.log 2>&1 &' && sleep 1
ssh host 'ps aux | grep job.py'  # Verify it's running
```

Works because the child redirects its I/O to a file, not to the SSH session's pipes. But **still fragile if the connection drops during the first few seconds** before the child detaches itself fully. For anything longer than a few minutes or mission-critical, use the next option.

### ✅✅ BEST: Windows Task Scheduler (Windows hosts, true persistence)
```bash
# Clean up any stale task
ssh host 'taskkill /IM python.exe /F 2>/dev/null || true'

# Register as a one-shot scheduled task
START_AT=$(date -d "+30 seconds" +%H:%M)
ssh host "schtasks /create /tn JobName /tr \"C:\\path\\job.cmd\" /sc once /st $START_AT /f"

# Fire it
ssh host "schtasks /run /tn JobName"

# Verify status
ssh host "schtasks /query /tn JobName /v /fo list" | grep -E "Status|Last Run"
```

**Why this works:**
- Task Scheduler service owns the process, not the SSH session. Disconnecting SSH does nothing.
- The task runs as the user who owns it (usually the current SSH user).
- You get back a task name you can query, start, stop, delete.

**Verify it's actually running (polling pattern):**
```bash
ssh host 'tasklist /fi "IMAGENAME eq python.exe"'
# Returns list of python.exe processes, or "INFO: No tasks running..."
```

Do NOT rely on schtasks status flags; poll the actual artifact your job produces (log file size, output count, etc.). `Last Run Status -2147020576` right after `/run` means the *previous* one-shot completed, not your current one failing.

### ✅✅ BEST: Linux `nohup` or systemd oneshot (Linux hosts)
```bash
ssh host 'nohup python job.py > /tmp/job.log 2>&1 &'
# Optional: start it in a tmux session so you can attach later
ssh host 'tmux new-session -d -s job "python long_job.py"'
```

## SSH quoting patterns by scenario

### Single argument, no spaces
```bash
ssh host "echo hello"  # Works in Bash, PowerShell, cmd.exe
```

### Single argument with spaces
```bash
# Bash/Linux
ssh host 'echo "hello world"'

# Windows (cmd.exe default shell)
ssh host "echo hello world"  # No inner quotes needed; cmd.exe doesn't require them

# Windows (if PowerShell is default)
ssh host 'Write-Host "hello world"'  # Single quotes protect the whole thing
```

### Multiple arguments with variables
```bash
# ❌ FRAGILE (shell expands $var locally before SSH sees it)
ssh host "echo $HOSTNAME"  

# ✅ CORRECT (shell expands on remote)
ssh host 'echo $HOSTNAME'

# ✅ ALSO CORRECT if you need local + remote vars (escape the remote var)
ssh host "echo Local is $HOSTNAME, Remote is \$HOSTNAME"
```

### Python string with quotes
```bash
# ❌ FRAGILE quoting
ssh host "python -c \"print('hello')\"" 

# ✅ CORRECT (raw string, single-quoted outer)
ssh host 'python -c "print('"'"'hello'"'"')"'
# Above parses as: ' + python -c "print(' + '"'"' + 'hello' + '"'"' + ')" + '
# i.e. 3 concatenated strings: '"..."' + "'" + '"..."'

# ✅ CLEANER (use raw string instead)
ssh host 'python -c "import sys; sys.stdout.write(\"hello\")"'
```

### Windows paths
```bash
# ❌ FRAGILE (single backslash, might be escape)
ssh host 'cmd /c "dir C:\Users\user"'  

# ✅ CORRECT (raw string if Python, or double backslash in cmd)
ssh host 'python -c "import os; os.listdir(r'"'"'C:\Users\user'"'"')"'

# ✅ OR (if you must use cmd, double backslash)
ssh host 'cmd /c "dir C:\\Users\\user"'  # Each backslash is literal
```

## Cross-platform tool availability

| Task | Linux | Windows (cmd.exe) | Windows (PowerShell) | Workaround |
|------|-------|-------------------|----------------------|------------|
| Background a process | `nohup cmd &` | ❌ (no `nohup`) | ❌ (no `nohup`) | Task Scheduler / `Start-Process` |
| Filter output lines | `grep pattern` | ❌ (no grep) | ❌ (no grep) | `findstr` (cmd) / `Select-String` (PS) |
| Find files | `find . -name "*.txt"` | `dir /s *.txt` | `Get-ChildItem -Filter` | Python `os.walk()` |
| Count lines in file | `wc -l file` | `find /c /v "" file` | `@(Get-Content file).Count` | Python |
| Edit and persist config | `sed -i 's/old/new/g'` | ❌ (no sed) | ❌ (no sed) | Python or .NET Replace |
| Monitor process | `ps aux \| grep python` | `tasklist /v` | `Get-Process \| Where-Object` | Python `psutil` |
| Run something unattended | `nohup` / `systemd` | Task Scheduler | Task Scheduler | ✅ Task Scheduler |

**For any of these:** prefer Python one-liner over platform-specific commands.

## Windows shell-folder & COM gotchas (creating shortcuts, Desktop/Startup writes)

### OneDrive-redirected Desktop hangs `GetFolderPath`
Confirmed 2026-06-01 on a Windows render box: `[Environment]::GetFolderPath("Desktop")` (and enumerating that folder) **silently hangs** when the Desktop is OneDrive-redirected. The SSH call returns empty stdout with exit 0 — looks like success, produces nothing. Same hang on `GetFolderPath` for Startup.

**Diagnose:** the real Desktop may be `%USERPROFILE%\OneDrive\Desktop`, not `%USERPROFILE%\Desktop`. Check both:
```bash
ssh host 'powershell -NoProfile -Command "Write-Output $env:USERPROFILE; Test-Path \"$env:USERPROFILE\Desktop\"; Test-Path \"$env:USERPROFILE\OneDrive\Desktop\""'
```
The authoritative path is in the registry:
```
HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders  ->  Desktop
```
**Fix:** use the **explicit** OneDrive path (`"$env:USERPROFILE\OneDrive\Desktop"`, `"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"`) instead of `GetFolderPath`. Never rely on the shell-folder API resolver when OneDrive Known Folder Move is active.

### Creating `.lnk` shortcuts via `WScript.Shell` COM — run from a `.ps1` file, not inline
Confirmed same session: building shortcuts with `New-Object -ComObject WScript.Shell` inline over `ssh host 'powershell -Command "...New-Object -ComObject..."'` **fails silently** — the nested `"` / `\"` layers through Bash → SSH → PowerShell → COM mangle the script, returning empty output with exit 0. Three inline attempts produced nothing.

**Fix:** write the PowerShell to a local `.ps1`, `scp` it over, run with `-File`, and have the script log every step + `Test-Path` each output to a file you read back:
```bash
scp -q ./make_shortcuts.ps1 host:'C:/Users/you/.hermes/bin/make_shortcuts.ps1'
ssh host 'powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\you\.hermes\bin\make_shortcuts.ps1'
ssh host 'powershell -NoProfile -Command "Get-Content C:\Users\you\.hermes\shortcuts_log.txt"'
```
This is the same "don't construct multi-stage commands as a single SSH invocation — `scp` a script over" principle from Pitfalls, applied to COM. Anything touching COM objects or nested quotes belongs in a file, full stop.

### Empty stdout + exit 0 over SSH→PowerShell is a RED FLAG, not success
When a remote PowerShell call returns `{"output": "", "exit_code": 0}`, do **not** report success. It usually means the command hung on a shell-folder resolver, died on quote-mangling, or wrote nowhere. Verify with a follow-up that reads an actual artifact (file exists + size + timestamp via the registry-confirmed path), or isolate with a plain `echo HELLO` to prove the pipe works before blaming the payload.

## Encoding pitfalls

### Windows console cp1252 crash
```python
print("✓ Success")  # 🚫 UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'
```

When a Python script runs on Windows (via SSH or locally) and writes to console, it uses cp1252 by default. Unicode characters outside that codepage crash the script.

**Fixes (in order of preference):**
1. **Python 3.7+:** `python.exe -X utf8 script.py` — flips encoding for the whole process.
2. **Env var (older Python):** `PYTHONIOENCODING=utf-8 python script.py`
3. **Script-level:** Replace Unicode with ASCII: `[OK]`, `[FAIL]`, `[->]` instead of `✓`, `✗`, `→`.

### PowerShell `.ps1` files: BOM or pure-ASCII, no exceptions
Confirmed 2026-06-02 baking a LoRA on a Windows render box: a `.ps1` authored in editor as UTF-8-without-BOM containing two em-dashes (`—`) in comments parsed fine locally but **threw cryptic parser errors on Windows PowerShell 5.x at completely unrelated lines 200+ down** — specifically chocked on `$sizeMB` ... `MB)` and `"megabytes)"` literals that have nothing to do with the em-dashes. Spent three wasted iterations renaming the variable (`$sizeMb`, then changing `"MB"` → `"megabytes"`) before realizing the real cause: WinPS 5 read the file as system codepage, the 3-byte UTF-8 em-dash sequence (`e2 80 94`) deserialized as garbage, every byte offset downstream was wrong, and the tokenizer started misclassifying `MB` / `megabytes` as numeric suffixes attached to the previous variable.

**Rule:** every `.ps1` you send to a Windows host must be one of:
- **Pure ASCII** (strip em-dashes, smart quotes, emoji from comments AND strings), OR
- **UTF-8 with BOM** (`utf-8-sig` in Python; `Out-File -Encoding utf8BOM` in PS 7+; the byte `EF BB BF` at file start)

Python helper to safely emit a Windows-bound PS1:
```python
from pathlib import Path
txt = (Path("local.ps1").read_text(encoding="utf-8")
       .replace("—","--").replace("–","-")
       .replace("'","'").replace("'","'")
       .replace(""",'"').replace(""",'"'))
assert all(ord(c) < 128 for c in txt), "still has non-ASCII"
Path("local.ps1").write_text(txt, encoding="utf-8-sig")  # BOM
```

Parse-only smoke test before launching (catches this class of bug in <1s, no side effects):
```bash
ssh host 'powershell -NoProfile -Command "try { $null = [scriptblock]::Create((Get-Content \"path\to\script.ps1\" -Raw)); Write-Host PARSE-OK } catch { Write-Host PARSE-FAIL; Write-Host $_.Exception.Message }"'
```
Always parse-smoke a PS1 immediately after `scp` before `Start-Process`-detaching it — otherwise you get the silent-detach-and-vanish failure mode in the next section.

### WSL2 UTF-16 stdout
```bash
wsl --list 2>&1 | head -5  # 🚫 Returns binary garbage: T\x00h\x00e\x00...
```

WSL tools write UTF-16 by default. Decode explicitly:
```bash
wsl --list 2>&1 | iconv -f utf-16 -t utf-8 | head -5
```

### "UTF-16 garbage" might mean WSL isn't installed at all (not a decode bug)
Confirmed 2026-06-02 on a Windows render box: an attempt to run
`ssh host 'wsl -- bash -c "..."'` returned `T\x00h\x00e\x00 \x00W\x00i\x00n\x00d\x00o\x00w\x00s\x00 \x00S\x00u\x00b\x00s\x00y\x00s\x00t\x00e\x00m\x00...`
which decodes to **"The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'."** Not a crash, not a quoting bug — the host literally has no WSL, and `wsl.exe` is a stub that writes a UTF-16 install hint and exits 0. Looks like a tool failure; is actually a "feature missing" message you can't read until decoded.

**Always probe before targeting a remote shell.** Don't assume WSL exists on a Windows host even if the user "uses Linux tools" — many Windows-native creator setups (ComfyUI, native Python, gaming rigs) have no WSL at all. Cheap probe pattern (run once per session per host, cache the answer):

```bash
ssh host 'powershell -NoProfile -Command "@{
  user = $env:USERNAME
  os   = (Get-CimInstance Win32_OperatingSystem).Caption
  wsl  = if (Get-Command wsl.exe -ErrorAction SilentlyContinue) { try { (wsl --status 2>&1 | iconv -f utf-16 -t utf-8) -replace ''\n.*'',''''  } catch { ''wsl.exe present but errored'' } } else { ''absent'' }
  py   = (Get-Command python -ErrorAction SilentlyContinue).Source
  venvs = (Get-ChildItem $env:USERPROFILE -Filter .venv -Directory -Recurse -Depth 3 -ErrorAction SilentlyContinue | Select-Object -First 5).FullName
} | ConvertTo-Json -Compress"'
```

Then route work to the shell that's actually present:
- WSL present → `wsl -- bash -c "..."` is the cleanest cross-platform layer.
- WSL absent → PowerShell + native Python; locate ComfyUI / venvs under `%USERPROFILE%\` (e.g. `C:\Users\<user>\ComfyUI\.venv\Scripts\python.exe`), not at `C:\ComfyUI\`.
- Neither Python nor WSL → tell the user; don't try to bootstrap silently.

**General principle:** when SSH-to-Windows output looks like binary garbage, decode it as UTF-16 *first* before assuming the call failed. Half the time it's just a Windows tool politely telling you something in the wrong encoding.

## Verification checklist
- [ ] Test SSH login works with `-o BatchMode=yes` (passwordless)
- [ ] Run a simple echo command remotely to verify quoting works
- [ ] If backgrounding, verify the process is actually running with `ssh host 'tasklist' / 'ps aux'` after launch
- [ ] If piping output, try one full cycle locally first (even on Bash, test the quoting)
- [ ] If using Python, test locally on the same Python version as the remote

## Pitfalls
- **Do not assume trailing `&` persists the process.** It doesn't on SSH.
- **Do not use `grep` or pipes for the primary control flow unless the remote is Linux.** Wrap it in Python instead.
- **Do not construct multi-stage commands as a single SSH invocation.** If you need `A && B && C`, write a local script, `scp` it over, then `ssh host script.sh`.
- **Do not forget to escape `$VAR` syntax.** Unescaped, it expands locally; escaped (`\$`), it expands remotely.
- **Do not trust cmd.exe default behavior on Windows machines where you didn't configure the shell.** Always verify interactively first.
- **Do not use cp1252-incompatible Unicode in Python scripts destined for Windows.** Test locally first.
- **Do not ship a `.ps1` to Windows without BOM or pure-ASCII.** Em-dashes / smart quotes in comments corrupt the byte stream and cause parser errors at unrelated lines downstream. Parse-smoke after scp.
- **Do not treat "PID gone" as failure or "PID alive" as success for `Start-Process`-detached jobs.** Original PID can exit cleanly while a grandchild does the work, OR can crash in 200ms before you check. Read log mtime + STATUS file, never `Get-Process -Id`.
- **Do not use `Start-Process -WindowStyle Hidden` over SSH and expect persistence.** It dies on SSH session teardown ~30s later. Use `Invoke-CimMethod -ClassName Win32_Process -MethodName Create @{CommandLine=...}` for true SSH-launched detach. Reserve `Start-Process` for shells you launched locally.
- **Do not use `powershell` over SSH for read-only data scans you intend to parse.** PowerShell emits PSObject CLIXML on stderr (huge `<Objs>` XML blobs) that pollute parseable output. Use `cmd /c "command"` for `dir`, `tasklist`, `netstat`, `wmic`, etc. — clean stdout, no XML noise. Reserve `powershell` for actual scripting that needs cmdlets/pipelines.

## `Start-Job` over SSH eats output — use a Tee'd file or PassThru, never `Receive-Job`

Confirmed 2026-06-05: ran `ssh <gpu-host> 'powershell -NoProfile -Command "$j = Start-Job ...; Start-Sleep 5; Stop-Job $j; Receive-Job $j"'` to capture llama-server's startup messages — got **completely empty stdout, exit 0**, even though the binary really did run and produce diagnostic output. `Start-Job` runs the script in a child PowerShell-job context whose stdout buffer never makes it back through the SSH-side parent's stdout when wrapped this way. Same failure mode as the empty-stdout-PowerShell traps elsewhere in this skill: you'll think the call did nothing.

**Fix: redirect the binary's combined output to a file with `*>&1 | Tee-Object`, then `Get-Content` the file in a separate SSH call.**
```bash
# Run foreground for N seconds, capturing everything (stdout+stderr+verbose+warning+error) to a log
ssh host 'powershell -NoProfile -Command "& C:\path\binary.exe <args> *>&1 | Tee-Object C:\Users\you\probe.log | Out-Null"' &
SSHPID=$!; sleep 8; kill $SSHPID 2>/dev/null

# Read it back in a fresh call
ssh host 'powershell -NoProfile -Command "Get-Content C:\Users\you\probe.log -Tail 40"'
```
The `*>&1` (PS 3.0+) merges all streams into stdout *before* the pipe, so `Tee-Object` captures everything the process emitted. Reading the log in a separate connection sidesteps any output-buffer weirdness from the launching call.

For \"is this binary alive and listening?\" probes specifically, **don't try to capture llama-server / a long-running daemon's first 5 seconds via Start-Job at all** — launch it detached (the `start.bat` + `Start-Process -WindowStyle Hidden` pattern from the file-shipping section), wait the realistic load time (model-load can be 30-90s for a 35B GGUF on GPU), then probe with `Get-NetTCPConnection -LocalPort N -State Listen` + an HTTP probe from the local machine. Process liveness + a listening port + a successful HTTP response is real evidence; an empty `Receive-Job` capture is not.

Confirmed 2026-06-05: `ssh 192.0.2.175` returned `Permission denied (publickey,password,keyboard-interactive)` and led to a wrong conclusion that "the key is gone." The key was fine. `~/.ssh/config` had:

```
Host <gpu-host> <gpu-host>
    HostName 192.0.2.175
    IdentityFile ~/.ssh/id_ed25519_prime
```

The `IdentityFile` directive is keyed to the **Host alias** (`<gpu-host>`), not to the bare IP. SSHing to `192.0.2.175` directly never matches that `Host` block, so the custom key is never offered and auth falls back to defaults → `Permission denied`. **Always `ssh <gpu-host>`, never `ssh <ip>`, when a config alias exists.** Before concluding "I lost access / the key broke," check:

```bash
grep -niE "<gpu-host>|<hostname>|<ip>" ~/.ssh/config     # is there a Host alias mapping the IP to a key?
ls ~/.ssh/ | grep -iE "id_|<host>"                  # does the key file actually exist?
```

If the alias exists and the key file is present, the "permission denied" was almost certainly you targeting the IP. This generalizes: **any per-host IdentityFile/User/Port only applies when you connect via the alias that owns that `Host` block.** Connecting by IP silently drops all of it.

## References
- `references/ssh-quoting-cookbook.md` — quick reference for common quoting patterns
- `references/windows-detached-job-pattern.md` — full template + cron-watcher pattern for long Windows jobs over SSH
- `scripts/windows-task-scheduler-oneshot.sh` — boilerplate template for Task Scheduler setup
- `references/python-filesystem-probes.md` — Python patterns for cross-platform file inspection
