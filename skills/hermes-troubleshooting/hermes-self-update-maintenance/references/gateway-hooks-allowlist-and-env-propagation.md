# Gateway Hooks: Allowlist + Systemd Env Propagation

When `pre_llm_call` / `post_llm_call` / other shell hooks are wired in
`config.yaml` under `hooks:`, they run as subprocesses spawned by the
gateway. Two gates determine whether they actually do anything:

1. **Allowlist gate** — Hermes refuses to execute un-approved hook commands.
2. **Environment gate** — the hook subprocess only sees env vars the gateway
   itself was started with. When the gateway runs under systemd, the
   user's interactive `.env` does NOT auto-propagate.

Both gates fail silently in the sense that the gateway keeps running and
the hook command is logged as "skipped" or runs-but-returns-empty. The
user sees nothing in their session — they just notice the hook's
intended effect is missing. Bit 2026-06-03 chasing the
`HERMES_ENABLE_LOCAL_TIME_CONTEXT` flag, which was set in `~/.hermes/.env`
but never reached the timestamp-injection hook because:

- Allowlist was `hooks_auto_accept: false` → gateway log: `shell hook for
  pre_llm_call (...) not allowlisted — skipped`
- Even after flipping the allowlist, the systemd unit had no
  `EnvironmentFile=` line, so the hook subprocess never saw the flag

## Diagnosing

### Is the hook even firing?

```bash
journalctl --user -u hermes-gateway.service -n 200 --no-pager | grep -i hook
```

Look for one of:

- `shell hook for ... not allowlisted — skipped` → allowlist gate closed
- `shell hook for ... timed out` → hook script is slow / hanging
- No mention at all → either the hook isn't wired in `config.yaml`, or the
  gateway hasn't been restarted since wiring it

### Is the env var propagating?

```bash
systemctl --user show hermes-gateway.service -p Environment
```

This shows what the gateway process sees. If your flag isn't in the
output, the hook subprocess won't see it either.

## Fix: allowlist

```bash
hermes config set hooks_auto_accept true
```

(This rewrites `~/.hermes/config.yaml` through the protected-file
gateway. Editing the file directly is blocked by Hermes' credential
file guard, which is correct — use `hermes config set`.)

Alternative for ephemeral approval: set `HERMES_ACCEPT_HOOKS=1` for one
session.

## Fix: systemd env propagation

The user-level unit at `~/.config/systemd/user/hermes-gateway.service`
ships with three `Environment=` lines (`PATH`, `VIRTUAL_ENV`,
`HERMES_HOME`) but no `EnvironmentFile=`. Add one:

```ini
Environment="HERMES_HOME=/home/<user>/.hermes"
EnvironmentFile=-/home/<user>/.hermes/.env
```

The leading `-` on `EnvironmentFile=` makes the entry optional (no failure
if `.env` is missing). After editing the unit:

```bash
systemctl --user daemon-reload
systemctl --user restart hermes-gateway.service
```

**Heads up:** restarting the gateway interrupts in-flight sessions
(including the one you're using to do the fix). Tell the user before
firing, and expect to have to be re-pinged on the other side.

## Verification

After restart, confirm the env propagated:

```bash
systemctl --user show hermes-gateway.service -p Environment \
  | grep -oE 'YOUR_FLAG=[^ ]+'
```

Then run the hook manually with the same env to verify output shape:

```bash
HERMES_ENABLE_LOCAL_TIME_CONTEXT=1 python3 ~/.hermes/scripts/your_hook.py
```

In a fresh session, watch for the hook's effect — for time-injection,
look for the silent `Current local time for grounding only: ...` line in
the user-message envelope on the next turn. If you (the agent) can see it
in your input, the loop is closed.

## Why both gates exist

- **Allowlist gate**: arbitrary shell commands in config.yaml are
  a security surface. Default-deny is the right posture.
- **Env gate**: systemd's design — units are explicit about their
  environment so they're reproducible. Bleeding the user's interactive
  `.env` into a long-running service implicitly would surprise people who
  put secrets in `.env` that they didn't intend the gateway to see.

Both are working as designed. The trap is that a wired-but-non-functional
hook is hard to detect from the session side — you have to know to look
at the gateway log AND the systemd environment.

## Pitfalls

- **Don't put the env var only in shell rc files** (`~/.bashrc`,
  `~/.zshrc`). Systemd units don't source those. Use `~/.hermes/.env` +
  `EnvironmentFile=` for the gateway path.
- **Don't restart the gateway without warning the user** if they're
  actively chatting — it drops sessions mid-turn. Always preview.
- **Don't try to edit `~/.hermes/config.yaml` directly** to flip
  `hooks_auto_accept`. The file guard blocks it. `hermes config set` is
  the supported path.
- **Don't assume `hermes gateway restart` works** in all environments — if
  the gateway is managed by systemd, `systemctl --user restart
  hermes-gateway.service` is more reliable than the CLI subcommand, which
  may timeout waiting for active sessions to drain.
- **Don't bundle secrets the gateway shouldn't see in `~/.hermes/.env`**
  once you add `EnvironmentFile=` — that file is now visible to every
  subprocess spawned by the gateway, including LLM-driven tool calls.
  Treat it accordingly.

## Related

- The `hermes-agent` bundled skill covers the *user-facing* hooks
  configuration vocabulary. This file is the *operational* counterpart for
  long-running systemd-managed gateways.
