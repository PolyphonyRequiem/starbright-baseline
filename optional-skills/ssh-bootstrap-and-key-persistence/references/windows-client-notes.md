# Windows client notes for SSH bootstrap

## Git Bash / MSYS path conventions

When Hermes runs on Windows through Git Bash / MSYS, use POSIX-style paths in shell commands:

- local home: `/c/Users/<user>`
- SSH dir: `/c/Users/<user>/.ssh`
- key path in shell commands: `/c/Users/<user>/.ssh/id_ed25519_<host>`

The same files may appear as native Windows paths in file-oriented tools:

- `C:\Users\<user>\.ssh\config`
- `C:\Users\<user>\.ssh\id_ed25519_<host>`

## Example alias

```sshconfig
Host <main-host>
    HostName 192.0.2.14
    User <user>
    IdentityFile /c/Users/<winuser>/.ssh/id_ed25519_<hostname>
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    StrictHostKeyChecking accept-new
```

## Reminder

When verifying an alias, use a trivial remote command first:

```bash
ssh -o BatchMode=yes <alias> 'whoami && hostname'
```

Avoid fancy follow-up commands until the alias itself is proven; otherwise a bad remote command can masquerade as an SSH failure.
