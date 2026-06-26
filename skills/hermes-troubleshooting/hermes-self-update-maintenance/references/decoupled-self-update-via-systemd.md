# Decoupled self-update via a one-shot systemd unit

Field-proven 2026-06-06. Solves "updating from inside a gateway-delivered session
decapitates the updater when it stops the gateway." The update runs as its OWN
systemd user unit, so the gateway bounce can't kill it.

## Unit: `~/.config/systemd/user/hermes-update.service`

```ini
[Unit]
Description=Hermes Agent — one-shot self-update (decoupled from gateway lifecycle)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=%h/.hermes/hermes-agent
EnvironmentFile=-%h/.hermes/.env
Environment="PATH=%h/.hermes/hermes-agent/venv/bin:%h/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="VIRTUAL_ENV=%h/.hermes/hermes-agent/venv"
Environment="HERMES_HOME=%h/.hermes"
# Override per-run: systemctl --user set-environment HERMES_UPDATE_TARGET=v2026.6.5
ExecStart=%h/.hermes/scripts/hermes_self_update.sh
TimeoutStartSec=1800
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

## Wrapper: `~/.hermes/scripts/hermes_self_update.sh`

Key points it must implement (chmod +x it):
- `TARGET="${HERMES_UPDATE_TARGET:-${1:-main}}"` — env, else arg, else main.
- Backup `config.yaml`, `.env`, `memories/`, `cron/jobs.json` to a timestamped dir FIRST.
- Record the FROM-ref (`git describe --tags --exact-match || git rev-parse --short HEAD`)
  into the backup as `PREVIOUS_REF.txt` and echo the rollback line.
- `systemctl --user stop hermes-gateway.service` (safe here — not delivered through it).
  Track whether any per-profile gateway (e.g. `hermes-gateway-<profile>.service`) was
  active and only restart the ones that were.
- `git fetch --tags --prune`; if the target is a tag, `git checkout --force <tag>`;
  else checkout+`pull --ff-only`. Exit 75 on git failure (matches RestartForceExitStatus
  convention if you ever make it Restart=).
- Reinstall deps honoring the venv's installer: `VIRTUAL_ENV=<venv> uv pip install -e <repo>`
  when `uv` exists (the Hermes venv is uv-backed — its python symlinks into
  `~/.local/share/uv/python/...`), else `<venv>/bin/python -m pip install -e <repo>`.
- `hermes config migrate --yes` (fall back to bare migrate), then `hermes doctor | tail`,
  then `hermes version | head`.
- `systemctl --user start hermes-gateway.service`.
- Log everything to `~/.hermes/logs/self-update-<stamp>.log` (via `exec > >(tee -a ...) 2>&1`).

## Trigger

```bash
chmod +x ~/.hermes/scripts/hermes_self_update.sh
systemctl --user daemon-reload
systemctl --user set-environment HERMES_UPDATE_TARGET=v2026.6.5
systemctl --user start hermes-update.service
# watch it (survives the gateway bounce):
journalctl --user -u hermes-update.service -f
```

## Also lower the gateway stop timeout (separate, permanent fix)

In `~/.config/systemd/user/hermes-gateway.service`, change `TimeoutStopSec=210` → `30`,
`daemon-reload`. Verify live: `systemctl --user show hermes-gateway -p TimeoutStopUSec`
should report `30s`. Prevents the 3.5-minute hang on every future `stop`.

## Pause crons across the update window

Before triggering, pause enabled cron jobs (`hermes cron pause <id>` per job) and save
the id list to a file so you can resume exactly that set afterward — the update can
straddle a cron firing window. Resume with `hermes cron resume <id>`. Confirm 0 left
paused afterward (`hermes cron list | grep -c paused`).

## Verify after (don't trust "log says complete")

`hermes version` shows the new tag · `hermes doctor` clean · `hermes cron list` all
expected jobs intact and none stuck paused · a representative skill loads · gateway
`systemctl --user is-active hermes-gateway` = active.
