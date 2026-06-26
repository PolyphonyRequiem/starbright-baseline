# Paramiko bootstrap example

Use this when the target host is already reachable on TCP/22, password auth is available once, and the current runtime makes interactive SSH awkward.

## Pattern
1. Generate a dedicated local key first:
   - `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_<host> -N '' -C '<comment>'`
2. Read the public key.
3. Use local Python + `paramiko` to connect with username/password.
4. Run a remote shell command that:
   - creates `~/.ssh`
   - creates `authorized_keys`
   - appends the public key only if missing
   - fixes permissions
5. Verify with `ssh -i ~/.ssh/id_ed25519_<host> -o BatchMode=yes user@host 'whoami && hostname'`.

## Minimal remote command shape
```sh
umask 077 && mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && \
grep -qxF '<PUBLIC_KEY>' ~/.ssh/authorized_keys || printf '%s\n' '<PUBLIC_KEY>' >> ~/.ssh/authorized_keys && \
chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

## Why keep this as a fallback
- avoids fragile stdin handoff to an interactive `ssh` process
- works well from Windows-hosted Hermes sessions using Git Bash
- keeps the one-time password use contained to the bootstrap step

## Notes
- Prefer the wired management IP on multi-NIC hosts.
- Treat any password used here as transient secret material; do not preserve it in memory or skills.
