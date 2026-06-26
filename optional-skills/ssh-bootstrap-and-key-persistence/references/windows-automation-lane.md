# Windows SSH automation notes

Session-derived lesson: a Windows SSH path that works from Hermes running inside Git-Bash/MSYS may fail when reused from Task Scheduler or other non-interactive Windows contexts.

## Durable pattern

Use two lanes mentally:

1. **Interactive lane (Git-Bash / Hermes terminal)**
   - convenient aliases in `~/.ssh/config`
   - MSYS-style paths like `/c/Users/<user>/.ssh/...`
   - `ssh <alias>` is fine for human-operated sessions

2. **Automation lane (Task Scheduler / cmd.exe / services)**
   - use native binaries explicitly:
     - `C:\Windows\System32\OpenSSH\ssh.exe`
     - `C:\Windows\System32\OpenSSH\scp.exe`
   - use explicit arguments:
     - `-i C:\Users\<user>\.ssh\id_ed25519_<host>`
     - `-o BatchMode=yes`
     - `-o StrictHostKeyChecking=accept-new`
     - `-o ConnectTimeout=10`
     - `user@host`
   - do not depend on `/c/...` path translation or Git-Bash-flavored config handling

## Why this matters

A scheduled backup script initially worked when run manually from Hermes/git-bash, but failed from Windows Scheduled Task because the non-interactive environment did not reliably reproduce the Bash-side SSH config/path assumptions. The durable fix was not "SSH is broken" — it was to use the native Windows OpenSSH executables with explicit host/user/key arguments.

## DHCP / rediscovery note

If the LAN host's IP can move, pair the SSH alias with a lightweight rediscovery helper (ARP scan, DHCP reservation, or DNS update path). Do not rely on one remembered IP forever.

## Verification recipe

Verify both lanes separately:
- interactive: `ssh <alias> 'whoami && hostname'`
- automation: invoke the exact scheduled/scripted command path and check exit code/log output
