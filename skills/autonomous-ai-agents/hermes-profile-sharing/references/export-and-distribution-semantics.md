# Export & Distribution Semantics (verified against local Hermes docs)

Verified 2026-06-18 against `~/.hermes/hermes-agent/website/docs/`. Re-grep before
relying on these if the install has been updated since.

## Two distinct primitives — don't conflate them

| | `hermes profile export` / `import` | Profile **distribution** (`install`/`update`/`info`) |
|--|------------------------------------|------------------------------------------------------|
| Purpose | Local backup/restore, or one-shot hand-off | Versioned sharing via a **git repo** |
| Format | `.tar.gz` | git repository (`distribution.yaml` at root) |
| Secrets (`.env`, `auth.json`) | **Stripped** ("stripped for safe sharing") | **Never** part of a distribution |
| memories / sessions | **Carried** | **Never shipped** (user data) |
| Best for sharing a clone | Yes (simplest: send the tarball) | Yes, if you want versioned updates over git |

Doc anchors (paths at time of writing):
- `website/docs/reference/profile-commands.md` L241+ (`export`), L296 (`.env`/`auth.json`
  never in a distribution), L299-301 (recipient user-data preserved).
- `website/docs/reference/faq.md` L788-796 — the `hermes backup` vs `profile export`
  table: export **Excludes** credentials ("stripped for safe sharing"); `hermes backup`
  (full-machine `.zip`) **Includes** them. Never use `hermes backup` to share.
- `website/docs/user-guide/profile-distributions.md` L68-70 — export/import is for local
  backup; memories/sessions/auth are "user data, not distribution content. Never shipped."

## The load-bearing nuance

`profile export` **strips secrets but CARRIES memories and sessions.** So the credential
strip does *not* save you from memory leaks. The defense is structural: build the share
copy on a **fresh** profile (blank memory/sessions by construction) and never open a chat
session in it before exporting. Then re-verify the extracted bytes anyway.

## Fresh-profile baseline (what `hermes profile create <name>` yields)

Observed 2026-06-18 on `hermes profile create lumen`:
- Created `~/.hermes/profiles/<name>/` with empty `memories/`, `cron/`, `sessions/`.
- **No** `config.yaml`, `.env`, or `auth.json` in the profile dir.
- Synced the stock bundled skills (74 in this build) — public Hermes skills only; none
  of the user's custom household/personal skills came across.
- Default generic `SOUL.md` (the stock "You are Hermes Agent…" prompt).
- Created a wrapper at `~/.local/bin/<name>`.

## The config.yaml inheritance trap

Because the fresh profile has no `config.yaml`, at runtime it **inherits the global
`~/.hermes/config.yaml`**, which carries personal data invisible to a profile-dir grep:
TTS `voice_id`, the MCP server list, Discord/Telegram channel + home IDs, personality
preset. **Write a minimal clean `config.yaml` into the share profile** (model/provider
placeholder; no voice_id/mcp/channels/homes) and confirm it overrides the global.

## Image gen vs. image recognition on the recipient's box (verified)

From `website/docs/user-guide/features/vision.md` and `image-generation.md`:
- **Image generation** is its own subsystem: the `image_gen` toolset → a backend (FAL,
  Nous Portal tool gateway, or a direct OpenAI key). Independent of the chat model.
  `fal-ai/qwen-image` is just one FAL model. No backend wired up → `image_generate` is
  dead and any OpenAI-edits script errors. A ported rendering skill must say this loudly.
- **Image recognition / vision:** vision-capable models (Qwen-**VL**, GPT-4V, Claude,
  Gemini, MiMo-VL) receive **real pixels**; text-only models route images through the
  `vision_analyze` auxiliary (an aux vision model describes the image as text). So "the
  agent can see" via two different paths depending on the model — but generation never
  runs through the chat model at all.
