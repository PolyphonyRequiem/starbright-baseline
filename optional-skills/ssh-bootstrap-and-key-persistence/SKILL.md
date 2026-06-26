---
name: ssh-bootstrap-and-key-persistence
description: Bootstrap durable SSH access to a Linux OR Windows host by moving from one-time password/console access to dedicated key-based login, covering Windows-as-admin-host (driving SSH out from Windows scheduled tasks), Windows-as-target (enabling OpenSSH Server + the administrators_authorized_keys quirk), and Paramiko fallback for awkward bootstrap.
---

# SSH Bootstrap and Key Persistence

## When to use
Use this when a Linux host is reachable on the network but not yet set up for durable remote administration, especially when:
- SSH is not installed or not yet enabled
- password auth works only once or is awkward to drive interactively
- the operator has local console access to the box
- the Hermes host is Windows and interactive stdin/process handoff is clumsy
- the machine has multiple NICs and you need to choose the stable management IP

## Plan-discipline rule: verify reach BEFORE drafting the plan

If you're about to write a multi-step plan that depends on shell access to another host (training jobs, batch installs, dataset generation, anything you'd run "overnight on the GPU box"), the FIRST tool call must be a reachability probe — not a TODO entry, not an architecture sketch, not a venv install. Run, in this order:

1. `ping -c 2 -W 2 <host>` — is the host even up?
2. `timeout 3 bash -c "echo > /dev/tcp/<host>/22"` — is port 22 open from THIS machine?
3. `ssh -o ConnectTimeout=5 -o BatchMode=yes <user>@<host> hostname` — does key-based login work?

Why this matters: in a heterogeneous home/lab (Linux orchestrator + Windows GPU box, or vice versa), it's common to have **outbound SSH set up in one direction only** for scheduled backups, while the reverse direction has never been needed. The presence of one half of the link is easy to misread as "we have shell between these boxes." Skipping the reach check means drafting a long, careful plan and then discovering 20 minutes in that the door isn't open — burning context, momentum, and user patience. The probe is 10 seconds. Do it first, always, when the plan crosses a host boundary.

If the probe fails: switch immediately to the *opening-the-door* problem (this skill) before resuming the original plan. Surface the gap to the user honestly — "I assumed inbound SSH to <host>; it's not actually open. Three options to fix it: A/B/C." Do not silently pivot to a different approach without naming the assumption that failed.

## Goal
End with a **dedicated SSH key** installed for the target account and a verified **passwordless login** to the preferred management IP.

## Default approach
1. **Verify network basics before blaming firewalls**
   - Confirm the target IP(s), default route, and which NIC should be used for management.
   - Prefer the wired IP if the host is dual-homed.
   - Probe TCP/22 reachability from the admin machine before making host changes.

2. **Get SSH listening on the host**
   - From local console access on the target, install/enable OpenSSH if needed.
   - Verify with `systemctl status ssh` and `ss -tlnp | grep ':22'`.
   - Check host firewall state, but do not assume it is the blocker until verified.

3. **Generate a dedicated admin key on the Hermes machine**
   - Prefer `ed25519`.
   - Use a host-specific filename like `~/.ssh/id_ed25519_<hostname>`.
   - Leave the private key on the admin machine only.

4. **Install the public key on the target**
   - If ordinary interactive `ssh`/`ssh-copy-id` is awkward from the current tool/runtime, use a local Python script with `paramiko` for the one-time password login.
   - Ensure:
     - `~/.ssh` exists
     - `authorized_keys` exists
     - `~/.ssh` is `700`
     - `authorized_keys` is `600`
   - Append only if the key is not already present.

5. **Verify key-only login**
   - Test with `ssh -i <key> -o BatchMode=yes ... '<verification command>'`.
   - Confirm the remote user, hostname, and selected management IP/path are correct.

6. **Optionally add a local SSH config alias**
   - Add `Host <alias>` in local `~/.ssh/config` pointing at the dedicated key and preferred IP.

## Windows-as-admin-host notes (driving SSH from Windows)

- On Windows admin hosts, shell commands often run under Git Bash/MSYS — use POSIX paths like `/c/Users/<user>/.ssh/...` in terminal calls.
- If interactive password entry through process stdin is unreliable, a local `paramiko` script is an effective one-time bootstrap path.
- If you need privilege escalation on a remote Linux host, **do not** assume you can feed the sudo password through `sudo -S` from Hermes. The terminal safety layer may block that path as a brute-force vector. Prefer one of these instead:
  1. ask the user to run the `sudo` install command locally on the target console,
  2. rely on tasks that do not need sudo once SSH is up,
  3. or use an already-authorized admin path that does not require password-to-sudo piping.
- **Windows native OpenSSH client** at `C:\Windows\System32\OpenSSH\ssh.exe` / `scp.exe` is the right runtime for **Windows Scheduled Tasks** that need to SSH out — Git Bash's shimmed `ssh` may not run in the non-interactive task context, but the native binary always will. For unattended use pass explicit `-i C:\path\to\key`, `-o BatchMode=yes`, and `-o StrictHostKeyChecking=accept-new` on first run.

## Windows-as-target notes (enabling SSH Server on Windows)

The default skill assumes a Linux target. When the target is Windows (workstation or server) and you need inbound SSH to drive it from elsewhere:

### Critical asymmetry to flag early

**Outbound SSH from Windows ≠ inbound SSH to Windows.** A Windows box can run scheduled-task `scp` / `ssh` *out* to a Linux host (using the built-in client at `C:\Windows\System32\OpenSSH\ssh.exe`) without OpenSSH Server installed at all. The Linux side listens; Windows just dials. This is easy to misread as "we have bidirectional SSH between these boxes" — you don't. **Always verify with `nmap -p 22 <windows-host>` or `nc -zv <host> 22` from the box that needs to originate the inbound connection.**

If you're about to plan work that depends on inbound shell to a Windows host, do the port check FIRST, before drafting the plan. It avoids "let's train on the GPU box overnight!" → 20 minutes of script-writing → "...oh, port 22 isn't open."

### Install OpenSSH Server on Windows (elevated PowerShell on the target)

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' `
    -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
Get-Service sshd | Select-Object Name, Status, StartType
# Expect: sshd / Running / Automatic
```

**Warn the user up front**: `Add-WindowsCapability` is silent and **typically takes 2–5 minutes** to download and install OpenSSH Server from Microsoft Update. It is NOT a hang — the PowerShell prompt simply does not return until install completes. Tell the user this BEFORE they run it, so they don't reach for Ctrl-C or assume something broke. The follow-on `Start-Service` / firewall lines run in milliseconds; only the first line is slow.

### Authorize a key — the admin-vs-user gotcha

**Windows OpenSSH uses different `authorized_keys` paths depending on whether the target account is an Administrator.**

- **Standard (non-admin) users:** `C:\Users\<user>\.ssh\authorized_keys` — works like Linux.
- **Administrators:** `C:\ProgramData\ssh\administrators_authorized_keys` — a single shared file for ALL admin accounts. Per-user `~/.ssh/authorized_keys` is **ignored** for admin accounts (silent — sshd just refuses the key with no error in the client; logs show "Authentication refused").

Detection + paste-once script (elevated PowerShell on target):

```powershell
$pubkey = 'ssh-ed25519 AAAA... user@from-host'

$isAdmin = (([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
Write-Host "Current user is admin: $isAdmin"

if ($isAdmin) {
    $authKeysFile = "$env:ProgramData\ssh\administrators_authorized_keys"
    Add-Content -Path $authKeysFile -Value $pubkey
    # CRITICAL: this file's ACLs must be locked to Administrators + SYSTEM only,
    # or sshd refuses to use it (silent failure as above).
    icacls.exe $authKeysFile /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
} else {
    $sshDir = "$env:USERPROFILE\.ssh"
    if (!(Test-Path $sshDir)) { New-Item -ItemType Directory -Path $sshDir | Out-Null }
    Add-Content -Path "$sshDir\authorized_keys" -Value $pubkey
}
Restart-Service sshd
```

### Debugging "key added but login still fails" on Windows

When the second-step paste-once script ran cleanly but `ssh -i <key> user@host` still returns `Permission denied (publickey,password,keyboard-interactive)`, do these THREE diagnostics IN ORDER instead of guessing:

**1. Client-side: confirm sshd is actually seeing the key offer.** Run on the admin (Linux) machine:

```bash
ssh -vvv -i ~/.ssh/id_ed25519_<host> -o BatchMode=yes user@host 'hostname' 2>&1 | \
  grep -E "(Offering|Authentications that can continue|Server accepts|Permission)"
```

Look for `Offering public key: ... ED25519 ...` followed by `Authentications that can continue: publickey,...`. That sequence means **the server saw our key, evaluated it, and rejected it** — i.e. the problem is on the server's `authorized_keys` file or its permissions, NOT a missing key or wrong path on the client side. (If you don't see `Offering`, the client never tried the key and the problem is local — wrong `-i` path, wrong key perms.)

**2. Confirm which `authorized_keys` file sshd is actually consulting for this account.** Run on the Windows target in admin PowerShell:

```powershell
Select-String -Path "$env:ProgramData\ssh\sshd_config" `
  -Pattern "AuthorizedKeysFile|administrators_authorized_keys|^Match"
```

Look for the `Match Group administrators` block. If present (it is by default on Windows), admin accounts use `__PROGRAMDATA__/ssh/administrators_authorized_keys` and the per-user `.ssh/authorized_keys` is **ignored entirely** for them — this catches people who put the key in the wrong file.

**3. Verify the file's contents AND permissions AND the sshd event log in one shot.** Admin PowerShell on target:

```powershell
$f = "$env:ProgramData\ssh\administrators_authorized_keys"

Write-Host "===== FILE CONTENTS ====="
Get-Content $f

Write-Host "`n===== FILE PERMISSIONS (must be ONLY Administrators + SYSTEM) ====="
icacls.exe $f

Write-Host "`n===== LAST 30 sshd EVENT LOG ENTRIES ====="
Get-EventLog -LogName Application -Source sshd -Newest 30 -ErrorAction SilentlyContinue |
    ForEach-Object { "[$($_.TimeGenerated.ToString('HH:mm:ss'))] $($_.Message)" }
```

What to look for in the `icacls` output:
- ✅ Acceptable: ONLY `BUILTIN\Administrators:(F)` and `NT AUTHORITY\SYSTEM:(F)` lines.
- ❌ Anything else (Users, Authenticated Users, the specific username, inherited entries) → sshd silently refuses to read the file. Re-run `icacls.exe $f /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"`.

What to look for in the sshd event log:
- `Authentication refused: bad ownership or modes for file ...` → ACL problem, fix with the `icacls` line above.
- `Failed publickey for <user> ... ssh-ed25519 ...` with the fingerprint matching your client's offered key → key is being seen but doesn't match anything in the file. Most likely cause: a typo/whitespace problem when the key was added (often a trailing newline got escaped, or the key was wrapped). Re-add it.
- No sshd entries at all → service isn't being hit (firewall, wrong port, or sshd isn't running — check `Get-Service sshd`).

This three-step diagnostic short-circuits the "guess and retry" loop that otherwise eats 20 minutes per round.

### Pitfalls specific to Windows targets

- **SSH username = the Windows local-account name, NOT whatever Linux convention you've been using.** If the user's Linux username on the orchestrator is `<user>` but their Windows account is `<winuser>` (look at the `C:\Users\<name>\` directory or run `whoami` on the target), the correct login is `ssh <winuser>@host`. Using the Linux-side name gets you `Permission denied (publickey,...)` even when the key is perfectly authorized — sshd never finds a matching local account to map the key to. Always confirm with `dir C:\Users` or `whoami` over the *first* SSH attempt (which can be password-based one-time) before assuming the key is broken.

  **Recognizing the symptom:** `ssh -vvv` shows your key being offered, the server replying with `Authentications that can continue: publickey,...` (i.e. the protocol handshake is healthy), and then `Permission denied`. With the file-contents + ACL diagnostic from the three-step debug above all coming back clean, the next thing to check is the **login username**, not the key file. If you've already verified file contents (the right key string is in the right file) AND verified ACL (only Administrators + SYSTEM), the next-most-likely cause is that you're connecting as the wrong local username for that machine. Check `C:\Users\` on the target.
- **Windows console encoding is cp1252, NOT utf-8.** When you write Python scripts that will run on Windows via SSH (or anywhere `python.exe` writes to a non-redirected console), `print("✓ done")` or any Unicode character outside cp1252 raises `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'` and kills the script mid-run. **Three fixes, in order of preference:**
  1. Pass `python.exe -X utf8 ...` (Python 3.7+) — flips the default encoding for the whole process. Cleanest.
  2. Set `PYTHONIOENCODING=utf-8` in the env before launch (works for older Python).
  3. Use ASCII-only markers in print statements: `[OK]`, `[X]`, `[->]` instead of `✓`, `✗`, `→`.
  This bites HARDEST when a Linux-authored script is scp'd over and run on Windows — it looks fine in the editor and runs fine locally, then dies on the target.
- **Launching a long-running process via SSH and *actually* detaching it from the SSH session is non-obvious on Windows.** `nohup` doesn't exist. `start /b cmd /c "long.cmd > log.txt 2>&1"` fails with `ERROR: Input redirection is not supported, exiting the process immediately` because `start` doesn't tolerate redirection inside its child command line. There are two patterns; **use the second one for anything that has to outlive the SSH session, because the first one has a silent-failure mode.**

  Both patterns assume you've already written a `chain.cmd` that does the actual work and handles its own logging:

  ```cmd
  REM run_thing.cmd — DOES the work, no detachment magic
  @echo off
  cd /d C:\Users\<winuser>\project
  C:\path\to\venv\Scripts\python.exe -u long_running.py >> training.log 2>&1
  ```

  **Pattern A — PowerShell `Start-Process` (works for medium-lived, attended jobs):**

  ```bash
  ssh windows-host 'powershell -Command "$p = Start-Process -FilePath cmd.exe -ArgumentList \"/c\",\"C:\\path\\run_thing.cmd\" -WindowStyle Hidden -PassThru; Write-Host (\"PID=\" + $p.Id)"'
  ```

  Gives you back the PID immediately. The catch: if you add `-RedirectStandardOutput` / `-RedirectStandardError` flags (tempting because you want to capture stdout), those pipes keep the child tied to a process tree that **can be killed when the originating SSH session is dropped**. The child appears to start, may run for a few seconds, then dies — and the only evidence is that progress mysteriously stops at the exact moment your SSH connection timed out. If you observe sample/iteration counters frozen at the value they had when your last SSH probe returned, this is the symptom. Do NOT use `-RedirectStandardOutput` for true overnight detachment; have the child do its own logging from inside `run_thing.cmd` instead (the `>> training.log 2>&1` line above).

  **Pattern B — Task Scheduler (bulletproof, survives ANY SSH event):**

  When Pattern A's child has died on you once already, or when the job needs to run unattended for hours, register it as a one-shot scheduled task. The Task Scheduler service itself owns the process — no parent, no SSH descendant, nothing to kill it on disconnect:

  ```bash
  # Cleanup any prior task with this name
  ssh host "schtasks /delete /tn StarbrightTrain /f" 2>/dev/null

  # Register — /st must be a clock time (HH:MM), so compute "now + 30s" client-side
  START_AT=$(date -d "+30 seconds" +%H:%M)
  ssh host "schtasks /create /tn StarbrightTrain /tr \"C:\\path\\chain.cmd\" /sc once /st $START_AT /f"

  # Fire it immediately
  ssh host "schtasks /run /tn StarbrightTrain"

  # Verify it's running
  ssh host "schtasks /query /tn StarbrightTrain /v /fo list" | grep -E "Status|Last Run|Last Result"
  ```

  Status `Running` = alive. `Last Result` of `-2147020576` (`0x80070420`) right after `/run` is **the previous one-shot completing**, not your current run failing — ignore it on first check, then re-check after a minute. Track progress by polling the actual artifact your script produces (file count, log tail, etc.), not by polling the task status.

  **Verifying ANY detached process is actually alive:** `ssh host 'tasklist /fi "PID eq <pid>"'` returns `INFO: No tasks running...` if it's gone. An instantly-exited child is usually a quoting problem in `run_thing.cmd` (often a path with spaces missing its quotes, or the venv python not being found because cwd was wrong) — run `chain.cmd` foreground over SSH once to surface the error before scheduling it. Beware: the SSH client-side I/O timeout firing on a long-running command is NOT a guarantee the remote process died. Always confirm process death via `tasklist` or absence of the artifact, not via "my ssh call returned an error."
- **`wsl.exe` writes UTF-16 to stdout by default.** When parsing `wsl --status` or `wsl --list` from automation (e.g. capturing in Python via `subprocess.run`), the output looks like `T\x00h\x00e\x00...` with null bytes between every character. Decode explicitly with `result.stdout.decode("utf-16-le")` or run via `wsl.exe --status 2>&1 | iconv -f utf-16 -t utf-8` in bash. Easy to misread as "binary garbage / SSH transport problem" when it's just MS being MS.
- **Permissions on `administrators_authorized_keys` are the #1 cause of "key was added but login still fails."** The `icacls /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"` step is mandatory. If the file inherits Users / Authenticated Users ACLs, sshd silently refuses.
- **Default shell is `cmd.exe`, not PowerShell.** Many automation scripts assume bash-like quoting and break. Change with `New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Program Files\PowerShell\7\pwsh.exe" -PropertyType String -Force` if remote work will use PowerShell heavily.
- **No `~` in default cmd.exe.** `ssh user@host "ls ~"` returns nothing useful; use `%USERPROFILE%` or switch to PowerShell-as-default-shell.
- **`Add-WindowsCapability` requires internet on the target** (downloads from Microsoft Update). Offline installs need the FoD ISO.
- **`Set-Service ... Automatic` does NOT survive a Windows feature update reset of service states** in some edge cases. Add a scheduled task or `sc.exe failure sshd reset= 0 actions= restart/60000/restart/60000/restart/60000` for production durability.
- **The first SSH connection after enabling will hang for ~30s on first-time-user-profile creation** if the admin account has never logged in interactively. Subsequent connections are fast.
- **`AllowGroups`, `AllowUsers` in `C:\ProgramData\ssh\sshd_config` default to permissive.** If you tighten, restart sshd. Windows sshd does NOT reload on SIGHUP.

### Probing the Windows target's filesystem over SSH

When you need to check things like "how many files match this pattern" or "what's the latest mtime in this dir" from your admin host via SSH, the obvious-looking `cmd.exe` and `powershell.exe` paths both have practical problems:

- `ssh host 'cmd /c "dir /b path\*.wav | find /c \".wav\""'` is the natural choice but the layered quoting between bash → ssh → cmd → cmd-pipe means **one stray quote produces cryptic `Access denied - \\` errors** that have nothing to do with permissions. Hard to debug, brittle across small changes.
- `ssh host 'powershell -Command "(Get-ChildItem path -Filter *.wav).Count"'` works reliably but **PowerShell cold-starts on every invocation** — each probe adds 5–8 seconds of startup overhead. Acceptable for one-off, painful for polling loops.

**The bulletproof pattern is single-line Python over SSH**, using a venv python you already know exists:

```bash
ssh host 'C:\path\to\venv\Scripts\python.exe -c "import os; d=r''C:\path\to\dir''; print(len([f for f in os.listdir(d) if f.endswith(\".wav\")]))"'
```

- Python escapes uniformly across all shell layers because the inner string is a Python literal, not a shell token.
- Raw strings (`r''C:\path''`) avoid backslash-escape problems with Windows paths.
- Startup is ~200ms vs PowerShell's multi-second cold start.
- Works identically for counting files, reading file sizes, checking mtimes, dumping JSON state — anything `os.path` + `os.listdir` can do.

Use this for any monitoring/polling loop where you need to check Windows filesystem state from a Linux admin box. Reserve `cmd /c` for fire-and-forget commands where you don't care about parsing the output, and reserve `powershell -Command` for things only PowerShell can do (service control, registry, CIM/WMI queries).

## After bootstrap: running commands reliably
Once SSH key access is in place, refer to **remote-command-execution-windows-linux** skill for patterns to:
- Run commands without shell-quoting nightmares (especially cross-platform)
- Background long-running processes that survive SSH disconnects
- Handle encoding and tool availability gaps (Windows vs. Linux)
- Debug SSH quoting failures

That skill covers the "what to do next" after this bootstrap is complete.

## Verification checklist
- `ssh` service active on target
- target listens on `0.0.0.0:22` or the intended interface
- chosen management IP reachable from admin machine
- dedicated public key present exactly once in `authorized_keys`
- passwordless SSH succeeds in `BatchMode`

## Pitfalls
- Do not store or repeat the password after the bootstrap step.
- Do not conclude “network firewall” too early; confirm whether the host simply lacks SSH.
- On dual-homed hosts, do not leave the preferred admin path ambiguous; verify route metrics and pick the intended IP.
- Do not skip permissions on `~/.ssh` and `authorized_keys`.

## References
- `references/paramiko-bootstrap-example.md` — one-time password-to-key installation pattern using local Python + Paramiko.
- `references/windows-client-notes.md` — Git-Bash / MSYS path conventions, sample `~/.ssh/config` alias block, and the "verify with `whoami && hostname` first" rule when proving a new alias.
- `references/windows-automation-lane.md` — when the SSH path that worked from interactive Git-Bash fails from Task Scheduler / cmd.exe: use the native `C:\Windows\System32\OpenSSH\ssh.exe` with explicit `-i C:\...\id_*` paths and `-o BatchMode=yes`, plus DHCP-rediscovery considerations.
