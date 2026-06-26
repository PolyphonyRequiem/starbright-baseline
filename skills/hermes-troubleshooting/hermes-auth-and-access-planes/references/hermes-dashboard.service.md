# hermes-dashboard.service — remote backend for Hermes Desktop (LAN, auth-gated)

Systemd **user** unit that runs `hermes dashboard` as the remote backend a Hermes
Desktop client connects to. Verified working on a v0.16.0 LAN setup (2026-06-06):
`auth_required: true`, `auth_providers: ['basic']`, password login returns
`200 {"ok":true}`.

Key design points:
- Binds `--host 0.0.0.0` **without `--insecure`** → the auth gate ENGAGES (see the
  skill's `--insecure` footgun table). With the basic provider registered from the env
  vars, it binds with auth enforced.
- `EnvironmentFile=%h/.hermes/.env` loads `HERMES_DASHBOARD_BASIC_AUTH_*` at boot.
- First launch runs a one-time `vite build` of the web UI (~1-2 min, no bind yet) —
  this is expected; subsequent starts bind in seconds.

```ini
[Unit]
Description=Hermes Agent Web Dashboard — remote backend for Hermes Desktop (LAN)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory=%h/.hermes/hermes-agent
EnvironmentFile=%h/.hermes/.env
Environment="PATH=%h/.hermes/hermes-agent/venv/bin:%h/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="VIRTUAL_ENV=%h/.hermes/hermes-agent/venv"
Environment="HERMES_HOME=%h/.hermes"
# Bare 0.0.0.0 bind (NO --insecure) → auth gate engages. Do NOT add --insecure.
ExecStart=%h/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main dashboard --no-open --host 0.0.0.0 --port 9119
Restart=always
RestartSec=5
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

Required env in `~/.hermes/.env` (hash path — no plaintext at rest):
```bash
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=<user>
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=scrypt$16384$8$1$<salt_b64>$<dk_b64>
HERMES_DASHBOARD_BASIC_AUTH_SECRET=<openssl rand -base64 32>   # stable → sessions survive restart
```

Bring-up:
```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-dashboard.service
# wait out the first-launch vite build, then verify:
curl -s http://127.0.0.1:9119/api/status | jq '.auth_required, .auth_providers'  # true ["basic"]
```

Desktop side (on the client machine): Settings → Gateway → Remote gateway →
Remote URL `http://<host-ip>:9119` → Sign in (username/password form) → Save & reconnect.

Capture the unit into chezmoi (do NOT add `.env` — secrets stay out of the dotfiles
repo).
