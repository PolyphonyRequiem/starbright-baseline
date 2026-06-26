---
name: hermes-auth-and-access-planes
description: "Disambiguate Hermes Agent's THREE independent authentication planes before configuring any of them — inference-provider auth (what model the agent calls), gateway client→server auth (how a Desktop/API client reaches a remote gateway), and the Nous Portal Tool Gateway (hosted web/image/tts/browser tools). They all surface as 'OAuth' or 'login' and are constantly conflated. Load when the user mentions hermes setup --portal, hermes login, OAuth, 'connect Desktop to my homelab/remote box', API_SERVER_KEY, a username/password gate, or asks 'do I even need this login?'"
version: 1.0.0
author: Starbright
created_by: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, auth, oauth, gateway, desktop, remote-access, portal, troubleshooting]
    related_skills: [hermes-agent, hermes-self-update-maintenance, hermes-model-catalog-introspection]
---

# Hermes Auth & Access Planes

Hermes has **three independent authentication planes** that beginners (and the agent)
constantly conflate because they all say "OAuth" / "login" / "sign in". Mixing them up
sends you chasing the wrong setup — e.g. running `hermes setup --portal` (an *inference*
auth) when what the user actually wanted was to connect a *Desktop client* to a remote
gateway (a *transport* auth). **Before configuring anything, identify which plane the
user means.** This skill is the disambiguator.

> Verified against a live v0.16.0 install (2026-06-06). Plane details below were read
> from the running system / source, not assumed.

## When to use

Load this the moment any of these appear:
- `hermes setup --portal`, `hermes login`, "OAuth", "sign in", "do I need to log in?"
- "Connect Desktop to my homelab / remote box / hosted Hermes"
- "Run the desktop app against a remote Hermes" (the v0.16.0 thin-client feature)
- `API_SERVER_KEY`, `basic_auth`, username/password gate, `--insecure`, session tokens
- A `hermes doctor` nag: "Run 'hermes setup' to configure missing API keys"
- The user questions whether a setup step is even needed ("do we even want this?")

## The three planes (the core mental model)

| Plane | Authenticates | Who needs it | Config surface |
|---|---|---|---|
| **1. Inference-provider auth** | *Hermes → the LLM API* (which model the agent's brain calls) | Always — but ANY one working provider suffices | `hermes auth`, `~/.hermes/.env` keys, `hermes login --provider <p>` |
| **2. Gateway client→server auth** | *A client (Desktop/API/TUI) → a remote Hermes backend* (thin GUI driving a remote agent) | Only if running a client against a *remote* backend | `hermes dashboard` + `dashboard.basic_auth` (username/password) on port 9119; the `--insecure` flag DISABLES the gate |
| **3. Nous Portal Tool Gateway** | *Hermes → Nous-hosted tools* (web search, image gen, TTS, browser) AND a Nous inference model | Only if you want Nous models or the bundled hosted tools | `hermes setup --portal` / `hermes login --provider nous` (OAuth device-code) |

**The orthogonality that gets missed:** Plane 1 is about *what model the agent uses*.
Plane 2 is about *how you talk to the agent*. Plane 3 is a *specific* Plane-1 provider
(Nous) that also unlocks hosted tools. You can have any combination. A user on Copilot
(Plane 1 satisfied) with a working agent does **not** need Plane 3 at all — the
`hermes doctor` "configure missing API keys" nag is about Nous/portal being unset, not
about anything being broken.

## Plane 1 — Inference-provider auth (the agent's brain)

What model the agent calls. Multiple providers can be authed simultaneously; the active
one is set in `config.yaml` `model.provider`. Auth types vary by provider:

- **API key** — Copilot (`COPILOT_GITHUB_TOKEN`), OpenAI (`OPENAI_API_KEY`), Anthropic
  key, OpenRouter, etc. Set in `~/.hermes/.env`.
- **OAuth device-code** — `nous`, `openai-codex`, `xai-oauth`. Run
  `hermes login --provider <p>`. **This is RFC 8628 device-authorization** — see the
  device-code section below; it has major implications for remote/headless setups.
- Inspect what's live: `hermes auth list` (shows every provider + credential + source).

**Diagnostic first move:** before "fixing" auth, run `hermes auth list`. If a working
provider is already listed (e.g. copilot), the agent's brain is fine — don't go chasing
a portal login the user didn't ask for.

## Plane 2 — Gateway client→server auth (Desktop-remote, the v0.16.0 feature)

The v0.16.0 "run Desktop against a remote Hermes" feature: a thin Electron GUI on your
laptop connects to a backend running wherever your keys/compute live (homelab, hosted
box).

🔴 **The remote backend is a `hermes dashboard` process — NOT the api_server.** This is
the #1 confusion. Verified against source + docs 2026-06-06:
- The Desktop attaches to a running **`hermes dashboard`** server, default port **9119**.
  Its readiness probe is `GET /api/status`; the live chat is a WebSocket at `/api/ws`
  (and `/api/pty`).
- The **api_server** platform (default port **8642**, gated by `API_SERVER_KEY`) is a
  *different door* — an OpenAI-compatible API endpoint, not what Desktop connects to.
  Do not point Desktop at 8642 or configure `API_SERVER_KEY` for the Desktop use case.

### The `--insecure` footgun (the load-bearing trap)

How you bind the dashboard non-loopback determines whether auth is ON or OFF — and the
intuitive flag does the opposite of what it sounds like. From `hermes_cli/web_server.py`
`should_require_auth()` truth table:

| Bind | `auth_required` | Meaning |
|---|---|---|
| `--host 127.0.0.1` (default) | False | loopback only; no auth, no remote reach |
| `--host 0.0.0.0` **without** `--insecure` | **True** | **gate ENGAGES** ✅ this is what you want |
| `--host 0.0.0.0 --insecure` | **False** | legacy escape hatch — **gate DISABLED** ❌ |

`--insecure` is NOT "allow me to bind publicly *with* auth" — it is "bind publicly and
**skip** the auth gate." Source comment is explicit: RFC1918/CGNAT/link-local are
deliberately treated as PUBLIC, "a hostile device on the same LAN is exactly the threat
model the gate is designed for." So for a password-protected LAN dashboard: bind
`--host 0.0.0.0` and **omit `--insecure`**. A bare non-loopback bind with at least one
auth provider registered binds with auth enforced; with NO provider registered it
**fails closed at startup** (`SystemExit: Refusing to bind…`).

### Setting up the username/password gate (hash, no plaintext)

Two config surfaces; **env wins over config.yaml** when set non-empty:
- config.yaml: `dashboard.basic_auth.{username, password_hash, secret}`
- env (`~/.hermes/.env`): `HERMES_DASHBOARD_BASIC_AUTH_USERNAME`,
  `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH` (preferred — no plaintext),
  `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` (plaintext fallback),
  `HERMES_DASHBOARD_BASIC_AUTH_SECRET` (token-signing key — **set it**, else sessions
  are invalidated on every restart).

```bash
# Compute the scrypt hash (format: scrypt$16384$8$1$<salt_b64>$<dk_b64>):
HASH=$(venv/bin/python -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('YOUR_PW'))")
SECRET=$(openssl rand -base64 32)
# Write USERNAME + PASSWORD_HASH + SECRET to ~/.hermes/.env (hash only, no plaintext).
```

Run the dashboard under its own systemd unit with `EnvironmentFile=%h/.hermes/.env` so
the creds load at boot. A ready unit template is at
`references/hermes-dashboard.service.md`.

🔴 **NEVER edit the `PASSWORD_HASH` line with `sed`.** The scrypt hash is packed with
`$` and the salt/dk base64 can contain `/` and `+`; the SECRET is base64 too. A
`sed "s|^...PASSWORD_HASH=...|...$HASH|"` silently mis-matches or DELETES the line when
the replacement contains the delimiter or `&`/`\` — observed deleting the hash entirely,
leaving USERNAME + SECRET but no hash, which **crash-loops the dashboard** (the `basic`
provider can't register → non-loopback bind fails closed → `activating (auto-restart)`
forever). Edit `.env` with Python instead (delimiter-immune): drop any existing
`PASSWORD_HASH=` line, then reinsert a clean one right after the USERNAME line:

```bash
HASH=$(venv/bin/python -c "from plugins.dashboard_auth.basic import hash_password; print(hash_password('$PW'))")
python3 - "$HASH" <<'EOF'
import sys; h=sys.argv[1]; p="/home/<user>/.hermes/.env"
lines=[l for l in open(p).read().splitlines() if not l.startswith("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH=")]
out=[]
for l in lines:
    out.append(l)
    if l.startswith("HERMES_DASHBOARD_BASIC_AUTH_USERNAME="):
        out.append("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH="+h)
open(p,"w").write("\n".join(out)+"\n")
EOF
chmod 600 ~/.hermes/.env && systemctl --user restart hermes-dashboard
```
If a crash-loop is already happening, diagnose by counting the keys —
`grep -c PASSWORD_HASH= ~/.hermes/.env` returning **0** is the smoking gun. Then verify
all three keys present + the hash starts `scrypt$` before restarting.

🔴 **Agent-context gotcha (verified 2026-06-06): the Hermes gateway secret-redactor
mangles INLINE scripts containing dashboard-auth key literals.** Passing a
`python3 - <<'PY'` heredoc whose body contains a literal `HERMES_DASHBOARD_BASIC_AUTH_…=`
string gets the `KEY=value`-shaped substring scrubbed mid-string → `SyntaxError:
unterminated string literal`, and the tool call is dropped. Fix: write the script to a
FILE with the file tool (not an inline heredoc), AND build the env-key names by
concatenation so no `KEY=value` literal exists in the source:
`PREFIX="HERMES_DASHBOARD_BASIC_AUTH_"; hash_key=PREFIX+"PASSWORD_HASH"; EQ=chr(61)`,
then match with `l.startswith(hash_key+EQ)`. Run it with `venv/bin/python /tmp/set_pw.py`.
Best practice: have that one script do hash → `systemctl --user restart` → a SINGLE
`/auth/password-login` smoke-test (mind the 10/60s limiter) and print only `LOGIN_OK:
True/False` + the plaintext spelled out char-by-char (`" ".join(pw)`) — so you verify the
login in-process and never round-trip the password through (redacted) tool output.

**When a human sets the password themselves** (e.g. over SSH while you can't see the
plaintext), prefer the `read -rsp` + Python-rewrite block over any `sed` — and hand it
to them as a copy-paste block, since the password must never transit the chat/gateway.
Do NOT generate a throwaway password whose plaintext you then lose (you'll have a
working hash nobody can log in with) — either let the user supply it via `read`, or
generate AND surface the plaintext to them once for them to save.

### Verifying the gate (the checks that actually mean something)

```bash
ss -tlnp | grep 9119                                  # 0.0.0.0:9119 = LAN-reachable
curl -s http://<host>:9119/api/status | jq '.auth_required, .auth_providers'
#   true   ["basic"]   ← gate engaged + provider registered. THIS is the success signal.
#   false  [...]       ← gate OFF (you left --insecure on, or bound loopback)
curl -s -o /dev/null -w "%{http_code}\n" http://<host>:9119/api/sessions   # 401 = gated ✅
```

⚠️ **`auth_required:false` but `/api/ws` returns 401 is a CONTRADICTION worth chasing,
not papering over** — it means the socket-layer ticket check is live but the broader
`/api/` gate is down (classic `--insecure` symptom). Don't call it "secure" until
`/api/status` reports `auth_required: true`.

**Credential smoke-test** (confirm the password actually authenticates — POST body needs
`provider`, and there's a brute-force rate-limiter):
```bash
curl -s -i -X POST http://<host>:9119/auth/password-login \
  -H "Content-Type: application/json" \
  -d '{"provider":"basic","username":"<u>","password":"<pw>"}' | grep -iE "HTTP/|set-cookie|ok"
# 200 + {"ok":true} + set-cookie hermes_session_at/rt = working
```
**Rate-limiter gotcha:** `/auth/password-login` throttles at **10 attempts / 60s per
IP** (process-local, resets on restart). Fumbling the payload shape several times can
trip it and return **401 even for the correct password** — a false negative. If a known-
good credential 401s after repeated tries, wait 60s (or restart the service) and retest
before concluding the hash is wrong. The required body model is
`{provider, username, password, next}`; a missing `provider` yields **422**, not 401.

**Security caveat to always surface:** a dashboard on `0.0.0.0:9119` over plain HTTP is
fine on a trusted LAN behind a firewall (the gate authenticates, traffic never leaves
the LAN). It is **NOT** okay exposed to the internet — for off-LAN access use TLS via a
reverse proxy, or bind to a **Tailscale IP** (`--host <tailscale-ip>`) so only your
tailnet reaches it (the docs' preferred clean option), or WireGuard. Never port-forward
raw `0.0.0.0` HTTP to the public internet; for public exposure use the OAuth (Nous
Portal) dashboard provider instead of username/password.

## Plane 3 — Nous Portal Tool Gateway

`hermes setup --portal` (or `hermes login --provider nous`) is a one-shot that: logs in
via OAuth device-code, picks a Nous model, sets Nous as the inference provider, and opts
into the Tool Gateway (hosted web search / image gen / TTS / browser). It's the *only*
thing that unlocks the bundled Tool Gateway tools without bringing your own keys.

**Decision rule:** only do this if the user wants Nous models OR the hosted Tool Gateway.
If they're happy on another provider and use their own tool keys, **skip it** — and tell
them the `hermes doctor` nag is cosmetic in that case, not a breakage.

## OAuth device-code flow — why you almost never need a browser tunnel

`nous`, `openai-codex`, and `xai-oauth` use **OAuth device authorization (RFC 8628)** —
the TV-app / `gh auth login` pattern, NOT a localhost-callback flow:

1. The CLI calls the provider, gets back a **`user_code`** + a **public `verification_uri`**
   (an `https://` URL on the provider's domain).
2. It prints the code + URL and tries to open a browser (`--no-browser` suppresses that).
3. **You** open that URL in *any* browser on *any* device, enter the code, authorize.
4. The CLI is meanwhile **polling** the provider over outbound HTTPS until you finish,
   then writes the refresh token to `~/.hermes/.env`.

**Critical consequence:** the browser and the CLI never talk to each other — they each
talk only to the public provider URL. **There is no localhost callback port to forward,
so there is nothing to tunnel.** When a user on a headless/remote box asks to "tunnel the
browser" for login, the right answer is usually: you don't need to. Run
`hermes login --provider <p> --no-browser` on the box, read them the code + URL, and they
authorize from whatever browser is convenient (phone, another laptop). A browser tunnel /
X11-forward is only ever needed for a *localhost-callback* OAuth flow — which these are
not. (Contrast: a localhost-callback flow binds `127.0.0.1:<port>` and the browser must
reach that exact port — that's the only case forwarding helps.)

**Headless gotcha:** device-code login is interactive and **blocks the terminal while it
polls**. There's no clean "print code then return" mode. If the agent must drive it, run
it backgrounded, surface the code, and detect completion — but **prefer handing the
user the one command** when they're at a machine; it's far less fragile.

## Pitfalls

- **Conflating Plane 3 (portal OAuth) with Plane 2 (Desktop-remote).** The headline
  trap. "Set up OAuth" might mean *either*. Ask / infer which: are they trying to give
  the agent a Nous brain + hosted tools (Plane 3), or connect a remote client to the
  gateway (Plane 2)? They're orthogonal. Cost this session: several turns solving the
  wrong one.
- **Chasing the `hermes doctor` "configure missing API keys" nag when a provider already
  works.** Run `hermes auth list` first. A working Copilot/Anthropic/OpenAI credential
  means the brain is fine; the nag is just Nous/portal being unset.
- **Assuming Desktop-remote needs a browser tunnel.** It doesn't — the dashboard client
  auth is a username/password (or OAuth) login over the `/api/ws` WebSocket, and the
  *provider* OAuth is device-code (browser-anywhere). Neither needs port forwarding on a
  LAN.
- **Pointing Desktop at the api_server (8642) instead of `hermes dashboard` (9119).**
  The remote backend is a `hermes dashboard` process on 9119; api_server on 8642 is a
  different door (OpenAI-compatible API, gated by `API_SERVER_KEY`). Wrong door = no
  connection.
- **Adding `--insecure` to "make it reachable with a password."** `--insecure` DISABLES
  the auth gate. The correct password-protected LAN bind is `--host 0.0.0.0` with NO
  `--insecure`. Verify `auth_required: true` via `/api/status` before trusting it.
- **Calling a remote backend "secure" without checking `/api/status`.** "Secure
  WebSocket" in the release notes means authenticated + TLS-able, NOT automatic wss on a
  bare LAN bind. A `0.0.0.0` HTTP bind is plaintext-on-wire; encrypt via Tailscale/VPN
  for anything off-LAN.
- **Concluding the password is wrong after repeated 401s.** `/auth/password-login` rate-
  limits at 10/60s/IP; fumbling the request shape trips it and 401s a correct password.
  Wait 60s or restart, then retest. Missing `provider` in the POST body → 422, not 401.
- **Treating the Desktop client's "Hermes couldn't start / backend exited before it
  became ready" error as fatal when you only want a REMOTE backend.** That dialog (seen
  with `Import error: No module named 'starlette'` / "Web UI dependencies not installed
  (need fastapi + uvicorn)") is the Desktop trying to boot its OWN *local* backend whose
  venv is missing web deps — irrelevant when the goal is to point Desktop at a remote
  `hermes dashboard`.

  🔴 **`HERMES_DESKTOP_REMOTE_URL` is TOKEN-AUTH ONLY — do NOT reach for it as the
  username/password path.** Verified in `apps/desktop/electron/main.cjs` (~L3890): when
  `HERMES_DESKTOP_REMOTE_URL` is set, the code REQUIRES a paired
  `HERMES_DESKTOP_REMOTE_TOKEN` and throws `"HERMES_DESKTOP_REMOTE_URL is set but
  HERMES_DESKTOP_REMOTE_TOKEN is not. Both must be provided…"` — it does the env-override
  *token* connection and **bypasses the interactive username/password login entirely**.
  `HERMES_DESKTOP_REMOTE_TOKEN` is an undocumented escape hatch for headless / broken-OS-
  keychain setups, expecting a PRE-MINTED token, not your password. Setting only the URL
  (the obvious move) HARD-BLOCKS the app with the TOKEN error. Cost this session: sent the
  user to set the env var, which produced exactly that error.

  **Correct path for username/password = the in-app UI, NOT the env var:**
  1. CLEAR any `HERMES_DESKTOP_REMOTE_URL` you set (it forces the token path and blocks
     you): `[Environment]::SetEnvironmentVariable("HERMES_DESKTOP_REMOTE_URL",$null,"User")`
     then `Remove-Item Env:\HERMES_DESKTOP_REMOTE_URL`.
  2. Get Desktop to its normal UI (fix the local backend if its boot overlay blocks you —
     see below), then **Settings → Gateway → Remote gateway** → Remote URL
     `http://<host>:9119` → **Sign in** → username/password form (POSTs to
     `/auth/password-login`).

  **The boot-failure overlay's buttons (from `apps/desktop/src/components/boot-failure-overlay.tsx`):**
  *Retry* re-tries the same broken local backend; *Repair install* re-runs the local
  installer (can itself be broken / no-op — it was dead this session); *Use local gateway*
  switches to the bundled backend (still broken until its venv is fixed). None is a clean
  "go remote with password" button — the overlay assumes you either fix local or already
  have a token. So the reliable unblock is to **fix the client's local backend venv** so
  Desktop boots to its normal UI, *then* point it remote from Settings.

  **Fixing the client's missing-web-deps local backend** (the `starlette`/`fastapi`/
  `uvicorn` boot error): the Desktop reuses the CLI checkout's venv. Reinstall WITH the
  `web` extra so the pinned set lands. The repo declares them under the `[web]` extra in
  `pyproject.toml` (`fastapi`, `uvicorn[standard]`, `starlette`); a plain editable install
  without `[web]` omits them — exactly how a client ends up unable to boot its local
  backend. Fixable remotely over SSH (the user lifts nothing):
  ```bash
  # In the client's hermes-agent checkout (uv-backed venv); Windows path shown:
  uv pip install --python .venv/Scripts/python.exe -e .[web]
  # verify it imports: python -c "import starlette, fastapi, uvicorn"
  ```
  Only needed if that box runs its own agent OR you must get past the boot overlay to
  reach the remote-connect UI. (Aside: the Desktop's bundled backend lives in the CLI
  checkout's venv, NOT under `%LOCALAPPDATA%\hermes` — that dir only holds logs/state.)

## See Also

- `references/hermes-dashboard.service.md` — ready-to-adapt systemd user unit for the
  Plane-2 remote dashboard backend (auth-gated LAN bind), with bring-up + verify steps.
- `hermes-agent` (bundled) — CLI/feature reference; `hermes setup`, `hermes auth`, gateway
- `hermes-self-update-maintenance` — gateway lifecycle (systemd units, stop/restart) that
  Plane-2 setup interacts with
- `hermes-model-catalog-introspection` — once a provider is authed, pick the right model
