# Detached long-running jobs on a Windows host over SSH

When the right shape is "kick off a multi-hour job on Windows, disconnect, get pinged when it ends." Verified end-to-end 2026-06-02 launching an SDXL LoRA training run on a Windows render box from a Linux orchestrator.

## When this pattern fits
- Job takes >5 minutes (anything shorter, just run foreground with a generous SSH timeout)
- You'll disconnect / lose network / want to do other work
- Job has discrete phases you can checkpoint
- You don't need full multi-user Task Scheduler persistence (job is fine to live with the interactive user)

## When this pattern does NOT fit
- Job must survive user logoff or reboot → use Windows Task Scheduler instead (see `scripts/windows-task-scheduler-oneshot.sh`)
- Job is multi-second → just run foreground
- You need stdin interaction → use a different transport entirely (terminal session, RDP)

## Architecture

```
[Linux orchestrator]                 [Windows host]
        │
        │ 1. scp job.ps1                       
        ├──────────────────────────────►  C:\Users\u\myjob\job.ps1
        │ 2. parse-smoke (exit fast on encoding bugs)
        ├──────────────────────────────►  powershell -Command "[scriptblock]::Create(...)"
        │ 3. detached launch
        ├──────────────────────────────►  Start-Process powershell -ArgumentList -File job.ps1 -WindowStyle Hidden -PassThru
        │                                          │
        │                                          ▼
        │                                  job.ps1 writes STATUS / log / DONE / FAIL files
        │
        │ 4. schedule recurring watcher cron (every 10m)
        ├──────────────────────────────►  reads STATUS / DONE / FAIL / log mtime over SSH
        │                                  ── silent on normal progress
        │                                  ── pings user on DONE / FAIL / stale-log
        │                                  ── pauses self on terminal outcome
```

## Step-by-step recipe

### 1. Write the job script with built-in self-instrumentation

`bake_v1.ps1` (skeleton):

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
  Write-Host $line  # also goes to console if run foreground for debug
}
function SetStatus([string]$s) { $s | Out-File -FilePath $STATUS -Encoding utf8 -NoNewline; Log "STATUS -> $s" }
function Die([string]$reason)  { Log "FATAL: $reason"; $reason | Out-File -FilePath $FAIL -Encoding utf8; exit 1 }

Log "=== job starting ==="

SetStatus "phase1_setup"
# ... real work, redirect tool output: ... 2>&1 | Out-File -FilePath $LOG -Append
if ($LASTEXITCODE -ne 0) { Die "setup failed rc=$LASTEXITCODE" }

SetStatus "phase2_train"
# ... real work ...
if ($LASTEXITCODE -ne 0) { Die "train failed rc=$LASTEXITCODE" }

SetStatus "phase3_verify"
$out = Get-ChildItem ... | Select-Object -First 1
if (-not $out) { Die "no output produced" }

$out.FullName | Out-File -FilePath $DONE -Encoding utf8
SetStatus "done"
Log "=== job COMPLETE ==="
exit 0
```

Critical conventions:
- **One STATUS file, atomic-overwritten on every phase**. Watcher reads this to know what's happening.
- **One append-only LOG file**. Tool output redirected here so the watcher can tail it.
- **DONE file written only on real success** with the result path inside.
- **FAIL file written only on terminal failure** with the human-readable reason.
- **All output paths uniform** — watcher knows exactly where to look without parsing.

### 2. Author it safely from a Linux box (BOM + ASCII)

Em-dashes and smart quotes corrupt WinPS 5 parsing in non-obvious ways (see umbrella SKILL.md). Always emit Windows-safe:

```python
from pathlib import Path
src = Path("bake_v1.ps1")
txt = src.read_text(encoding="utf-8")
# Strip non-ASCII that breaks WinPS 5 parser
txt = (txt.replace("—","--").replace("–","-")
          .replace("'","'").replace("'","'")
          .replace(""",'"').replace(""",'"'))
assert all(ord(c) < 128 for c in txt), \
    f"still has non-ASCII at: {[(i,c) for i,c in enumerate(txt) if ord(c) > 127][:3]}"
src.write_text(txt, encoding="utf-8-sig")  # BOM
```

### 3. scp + parse-smoke before launching

```bash
scp -q ./bake_v1.ps1 <gpu-host>:myjob/

ssh <gpu-host> 'powershell -NoProfile -Command "
  try {
    $null = [scriptblock]::Create((Get-Content \"$env:USERPROFILE\myjob\bake_v1.ps1\" -Raw))
    Write-Host PARSE-OK
  } catch {
    Write-Host PARSE-FAIL
    Write-Host $_.Exception.Message
  }
"' 2>&1 | tr -d '\000' | grep -v -E '^(<|#<|<Obj)' | head -10
```

If `PARSE-FAIL`: do NOT launch. Read the error, fix the script locally, re-scp, re-smoke. This catches the entire "PID vanishes silently" failure class up-front.

### 4. Detached launch via Start-Process -PassThru

Encoded-command form to dodge SSH quoting hell:

```python
import base64
ps = r"""
$root = "$env:USERPROFILE\myjob"
$p = Start-Process powershell.exe -ArgumentList @(
  "-NoProfile","-ExecutionPolicy","Bypass","-File","$root\bake_v1.ps1"
) -WindowStyle Hidden -PassThru
Write-Host ("PID " + $p.Id)
"""
b64 = base64.b64encode(ps.encode("utf-16le")).decode()
# Then over SSH:
#   ssh <gpu-host> "powershell -NoProfile -EncodedCommand {b64}"
```

The wrapper PS process exits immediately. The detached child survives SSH disconnect.

### 5. Verify launch by ARTIFACT, not by PID

```bash
sleep 20
ssh <gpu-host> 'powershell -NoProfile -Command "
  Write-Host ---status:
  Get-Content \"$env:USERPROFILE\myjob\STATUS\" -ErrorAction SilentlyContinue
  Write-Host ---log-mtime:
  (Get-Item \"$env:USERPROFILE\myjob\job.log\" -ErrorAction SilentlyContinue).LastWriteTime
  Write-Host ---tail:
  Get-Content \"$env:USERPROFILE\myjob\job.log\" -Tail 10 -ErrorAction SilentlyContinue
"' 2>&1 | tr -d '\000' | grep -v -E '^(<|#<|<Obj)' | head -30
```

If STATUS has progressed past the initial phase AND log mtime is recent (within a minute or two): job is healthy, disconnect. If STATUS is missing or log is empty: parse-failed at runtime even though it parse-smoked — capture the FAIL file or run foreground to see the live error.

### 6. Schedule a recurring watcher cron

```python
cronjob(
    action="create",
    name="myjob-watcher",
    schedule="every 10m",
    deliver="local",
    enabled_toolsets=["terminal", "file", "cronjob"],
    prompt="""
Check myjob on Windows host. Run:

  ssh <gpu-host> 'powershell -NoProfile -Command "$root = \"$env:USERPROFILE\myjob\"; Write-Host STATUS:; Get-Content \"$root\STATUS\" -ErrorAction SilentlyContinue; Write-Host DONE:; Test-Path \"$root\DONE\"; Write-Host FAIL:; Test-Path \"$root\FAIL\"; Write-Host FAIL_CONTENT:; Get-Content \"$root\FAIL\" -ErrorAction SilentlyContinue; Write-Host MTIME:; (Get-Item \"$root\job.log\" -ErrorAction SilentlyContinue).LastWriteTime; Write-Host TAIL:; Get-Content \"$root\job.log\" -Tail 8 -ErrorAction SilentlyContinue"' 2>&1 | tr -d '\000'

Decide and act:
- DONE=True → pause self (list-then-remove pattern), notify user with result path, optionally scp artifact back to local host
- FAIL=True → pause self, notify user with FAIL content + last 8 log lines, do NOT relaunch
- MTIME stale >90 min → pause self, notify user that job is hung at STATUS X
- Otherwise → exit silent. User may be asleep.

Identify yourself by job name. Stay quiet during normal progress.
"""
)
```

`schedule="every 10m"` makes it recurring — if you pass `"10m"` you get a one-shot, which is wrong for this pattern. Always `update` immediately if you got that wrong on `create`.

## Failure modes observed in real use

| Symptom | Real cause | Fix |
|---|---|---|
| "PID gone" 30s after launch, no log file | `.ps1` parse-failed at startup due to encoding bug | Parse-smoke + BOM-on-write |
| "PID gone" 30s after launch, log file present and growing | Original wrapper PID exited cleanly; grandchild owns the work | Stop checking PID, check log mtime |
| STATUS stuck at phase2 for hours | Tool inside that phase legitimately hung (e.g. pip waiting on network) | Watcher's stale-log threshold catches this; user manually kills + investigates |
| Empty stdout + exit 0 from `ssh <gpu-host> 'powershell ...'` | Quoting mangled — command silently ate itself | Run as `-EncodedCommand` (base64 UTF-16LE) instead of inline string |
| Unicode garbage like `T\x00h\x00e\x00...` from a Windows tool | UTF-16LE output, not a crash — pipe through `iconv -f utf-16 -t utf-8` OR (if it's a `wsl` invocation) the host has no WSL at all |

## Why not just Task Scheduler?

Task Scheduler is the right answer when:
- Job must outlive interactive logon / user reboot
- Job needs to run as SYSTEM or a different user
- Job is part of a permanent recurring schedule

Start-Process + watcher is the right answer when:
- Job is a one-shot you'll launch and forget
- Job is fine running as the interactive user
- You want zero registration footprint on the Windows host
- You're orchestrating from Linux and Task Scheduler's XML is a pain to template

Both are valid. Don't pick Task Scheduler reflexively just because the job is long.
