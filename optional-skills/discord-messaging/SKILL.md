---
name: discord-messaging
description: Send/read Discord DMs and channels via gateway + REST.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [discord, messaging, gateway, dm, read]
    category: communication
---

# Discord Messaging Skill

How to send and read Discord messages through Hermes, including the gotcha around DMing a user by user ID (DM channel must be opened first via REST) and reading channel history (requires Message Content Intent + read permissions).

## When to Use

- User asks you to send a Discord message to a specific user or channel.
- User asks you to read recent messages from a Discord channel or thread (`send_message` is send-only — use REST).
- User gives you a Discord user ID (a snowflake like `000000000000000001`) for a DM.
- `send_message` returns `Discord API error (404): Unknown Channel` or `Could not resolve 'X' on discord`.
- You need to discover what targets are reachable, including thread / topic IDs.
- You need to do anything **administrative the `send_message` tool can't**: fetch members, roles, channel/guild metadata, resolve a user by ID, upload attachments via multipart, or hit any other Discord REST endpoint. The `send_message` tool is send-only and cache-bound; everything past the happy path goes through the bot REST API documented here.

This skill is the umbrella for **all Discord access beyond `send_message`** — gateway sends, REST reads, DM-channel opening, attachments, and admin endpoints. (Narrower presentation/formatting concerns live in `discord-message-registers`; multi-image galleries in `discord-multi-image-message`.)

## Prerequisites

- Hermes gateway is running with the Discord adapter connected (bot online).
- `DISCORD_BOT_TOKEN` is set in the active profile's `~/.hermes/.env`.
- For first-contact DMs: the bot must share at least one guild with the target user (Discord-side requirement, not a Hermes limitation).
- For reading channel messages: bot needs `View Channel` + `Read Message History` permissions on the target channel, AND the **Message Content Intent** must be enabled in the Discord Developer Portal (Application → Bot → Privileged Gateway Intents) — without it, `content` fields come back as empty strings.

## How to Run

1. When the target isn't obvious, list what's reachable first: `send_message(action='list')`.
2. If the target appears in the list, send directly with `send_message(target=..., message=...)`.
3. If the user gives you a user ID and no DM target exists yet, open a DM channel via the Discord REST API (see Procedure → DM by ID), then send to the returned channel ID. Helper: `scripts/open_dm.sh <user_id>`.
4. To read channel history, hit Discord's REST API directly — `send_message` is send-only. Helper: `scripts/read_channel.sh <channel_id> [limit]`.

## Quick Reference

| Target shape | Use for |
|---|---|
| `discord` | Home channel (default) |
| `discord:#channel-name` | Server channel by name |
| `discord:<channel_id>` | Server channel by snowflake ID |
| `discord:<channel_id>:<thread_id>` | Discord thread / forum post |
| `discord:<username>` | DM to a user the bot already has a DM channel with |

Discord IDs in `discord:<id>` are interpreted as **channel** snowflakes, never user snowflakes.

REST endpoints used by this skill (base: `https://discord.com/api/v10`):

| Endpoint | Purpose |
|---|---|
| `POST /users/@me/channels` | Open (or fetch) a DM channel for a user |
| `GET /channels/{id}/messages?limit=N` | Read recent messages from a channel or thread |
| `GET /channels/{id}/messages?before=<id>` | Paginate backwards in time |
| `GET /channels/{id}/messages?after=<id>` | Paginate forwards in time |

Auth header for all: `Authorization: Bot $DISCORD_BOT_TOKEN`.

**Sourcing the token in git-bash/terminal:** the token does NOT auto-load into the terminal tool. Wrap every curl in `set -a && source ~/.hermes/.env && set +a` — a bare `source` defines the var but does not export it to the `curl` subprocess, so you get a silent `401 Unauthorized`. Verify the whole pipe with `curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bot $DISCORD_BOT_TOKEN" https://discord.com/api/v10/users/@me` → expect `200` (401 = token missing/wrong).

### Admin / beyond-messaging endpoints

`send_message` cannot fetch members, roles, or metadata. Use these REST endpoints (same `Authorization: Bot` header, base `https://discord.com/api/v10`):

| Need | Endpoint |
|------|----------|
| Resolve user by ID | `GET /users/{user_id}` |
| Channel metadata | `GET /channels/{channel_id}` |
| List guild channels | `GET /guilds/{guild_id}/channels` |
| Guild members | `GET /guilds/{guild_id}/members?limit=N` (needs **Server Members Intent**) |
| Upload attachment(s) | `POST /channels/{channel_id}/messages` multipart: `payload_json` + `files[N]=@path` (≤10 files, ≤25 MB each); response `attachments[].url` is the public CDN URL |
| React to a message | `PUT /channels/{cid}/messages/{mid}/reactions/{emoji}/@me` |
| Edit a message | `PATCH /channels/{cid}/messages/{mid}` |
| Delete a message | `DELETE /channels/{cid}/messages/{mid}` |

Full copy-pasteable recipes: `references/rest-api-curl-recipes.md`. Attachment-upload + long-message spoiler/markdown chunking: `references/attachments-and-chunking.md`. Bulk-dump every channel in a guild to JSON: `scripts/dump_guild.sh <guild_id> <out_dir> [limit]`.

### Walk a user through enabling reads

When reads fail (empty `content` or 403), the fix is a two-part one-time setup the user must do in the UI:

1. **Developer Portal** (app-wide): `https://discord.com/developers/applications` → app → Bot → Privileged Gateway Intents → toggle **MESSAGE CONTENT INTENT** ON (and optionally **SERVER MEMBERS INTENT** for member resolution) → **Save Changes**.
2. **Channel permissions** (per channel or via the bot's role): Server Settings → Roles → bot role → enable `View Channels` + `Read Message History`; or per-channel: right-click channel → Edit Channel → Permissions → add bot role → `View Channel ✓` + `Read Message History ✓`.

REST reads pick up the intent change immediately (no reconnect). The long-lived gateway WS may need a restart to see new intents.

## Procedure

### DM a user by ID (the `Unknown Channel` workaround)

Bare `send_message(target='discord:<user_id>')` fails with 404 because Discord's REST API resolves the snowflake as a channel and the user ID is not a channel.

To DM a user whose DM channel doesn't exist yet:

1. Open (or fetch) the DM channel via Discord's REST API. The endpoint is idempotent — calling it again for the same user returns the same channel:
   ```bash
   curl -sS -X POST https://discord.com/api/v10/users/@me/channels \
     -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"recipient_id": "USER_ID_HERE"}'
   ```
   The JSON response includes an `id` field — that's the DM channel's snowflake (different from the user ID). Or run `scripts/open_dm.sh <user_id>` which prints only the channel id on stdout.
2. Send to the DM channel ID:
   ```
   send_message(target='discord:<dm_channel_id>', message='...')
   ```
3. After the first successful DM, the channel shows up in `send_message(action='list')` output so subsequent sessions can address it directly without re-opening. Save the DM channel id to `memory(target='user')` to skip the open-DM dance next time.

### Find available targets

`send_message(action='list')` returns:
- All guild channels the bot can see (prefixed `discord:#`).
- All existing DM channels (prefixed `discord:<username>`).

Users the bot has never DMed before will NOT appear in this list — that's expected, not a bug.

### Post to a thread or forum post

Threads require BOTH the parent channel ID and the thread ID:
```
send_message(target='discord:<channel_id>:<thread_id>', message='...')
```
Using only the channel ID delivers to the parent channel, not the thread.

### Send long recipient-facing messages safely

For reflective letters, planning documents, or emotionally sensitive messages that exceed Discord's length limit:

1. Draft the full message first so tone and structure stay coherent.
2. Add a short framing line if the user asked for one (for example, "created together with my person and they want to share this with you to think about and reflect on").
3. Split into multiple sends at natural paragraph boundaries rather than hard character chops.
4. Preserve the emotional arc across chunks: opening framing -> core message -> practical questions/next steps.
5. After sending, report back that it was sent in multiple messages because of Discord length limits.

Preferred behavior for sensitive partner-facing notes:
- keep the voice warm and direct
- avoid sounding clinical unless the user asked for that
- protect consent/limits language explicitly when the note discusses sex, readiness, pressure, or trauma-sensitive topics

### Read messages from a channel (or thread)

`send_message` is send-only. To read message history, hit Discord's REST API directly with the same bot token used for sending. Threads use the same endpoint as channels — Discord treats them as channels internally.

1. Fetch the last N messages (default 50, max 100 per call) into a file. Discord responses are large JSON arrays that easily blow past the tool-output cap, so always pipe to disk rather than capture in stdout:
   ```bash
   curl -sS "https://discord.com/api/v10/channels/CHANNEL_ID/messages?limit=50" \
     -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
     -o "$TEMP/discord_messages.json"
   ```
   Or use the helper: `scripts/read_channel.sh <channel_id> [limit] [before_id]`. It picks a Windows-visible temp dir automatically.
2. Parse with `execute_code` (Python). On Windows, use a Windows-visible path because the `execute_code` sandbox subprocess does NOT see git-bash's `/tmp` — write under `/c/Users/<user>/AppData/Local/Temp/...` (or `$TEMP`) instead. See Pitfalls for details:
   ```python
   import json, os
   path = os.path.join(os.environ['TEMP'], 'discord_messages.json')
   with open(path, encoding='utf-8') as f:
       msgs = json.load(f)
   # Discord returns newest-first; reverse for chronological display
   for m in reversed(msgs):
       ts = m['timestamp'][:19].replace('T', ' ')
       author = m['author'].get('global_name') or m['author']['username']
       edited = ' (edited)' if m.get('edited_timestamp') else ''
       print(f"[{ts}] {author}{edited}: {m['content']}")
   ```
3. For pagination, use the `before=<message_id>` query param to walk backwards from a known message. To go forwards in time, use `after=<message_id>`. Each call still caps at 100 messages.
4. To detect that Message Content Intent is missing: every message's `content` is an empty string but other fields populate normally — that's the signature failure mode (HTTP 200, not an error).

## Pitfalls

- **Bare `discord` target = home channel, NOT a DM.** `send_message(target='discord', ...)` and `target='discord:#general'` go to the configured home channel, which is usually a shared server channel visible to other members. For anything private (intimate, body-image, partner-only, personal-financial, secret-keeping, surprise-coordination), ALWAYS explicitly target a DM channel like `discord:<username>` or `discord:<dm_channel_id>`. **Pause and verify the target string before sending sensitive content** — if you wouldn't be comfortable shouting it across the user's household, it does not go to the home channel. If unsure, call `send_message(action='list')` first and pick the DM line. After a misroute, use `discord-delete-message` immediately (own messages don't need `MANAGE_MESSAGES`; bulk-delete does, so fall back to one-at-a-time `DELETE /channels/{id}/messages/{id}` calls if the bulk endpoint 50013s). Save the user's DM channel id to `memory(target='user')` or fact_store after the first successful resolve so future sessions don't have to re-derive it.
- **User ID is not a channel ID.** This is the most common confusion. `discord:<snowflake>` is always parsed as a channel. Use the DM-open workaround above for first-contact DMs.
- **Multiple `MEDIA:` tags in one `send_message` call split into N separate messages, not a gallery.** When the user wants a batch of images as one Discord message (gallery / comparison set / multi-attachment post), do NOT stack `MEDIA:` lines — use the `discord-multi-image-message` skill (direct multipart POST to `/channels/{id}/messages` with `files[N]=@path`, up to 10 attachments per message). The MEDIA convention is only correct when one-attachment-per-message is actually desired.
- **Username addressing requires an existing DM.** `discord:<username>` only resolves if the bot already has a DM channel with that user. New users need the DM-open step first.
- **Bot must share a guild for first-contact DMs.** Even with a perfect API call, Discord rejects DM opens to users who share no server with the bot and have never DMed the bot.
- **Don't paste the bot token into chat output or commit it.** Pull it from the environment (`$DISCORD_BOT_TOKEN`) only inside terminal commands; never echo it in a reply to the user.
- **Save per-person contacts to memory, not the skill.** Per-person facts (names, IDs, persona preferences) belong in `memory(target='user')`. This skill stays generic.
- **Empty `content` fields when reading = Message Content Intent is off.** The fix is in the Developer Portal (Application → Bot → Privileged Gateway Intents → MESSAGE CONTENT INTENT → Save Changes), not in code. Other fields (`id`, `author`, `timestamp`, `embeds`, `attachments`) still populate even without the intent, which makes the failure mode subtle. The gateway may need a restart for the change to apply to live-socket reads, but REST reads see it immediately.
- **Reading channel messages can return large JSON.** A 50-message page with long messages routinely exceeds the tool-output character cap. Always use `curl -o <file>` and parse from disk — don't try to read the body straight from stdout.
- **`/tmp` from git-bash is invisible to the `execute_code` sandbox on Windows.** The git-bash terminal and the Python subprocess see different filesystem roots. When handing data between `terminal` and `execute_code`, write to a Windows-visible path like `/c/Users/<user>/AppData/Local/Temp/...` (or use `$TEMP` / `%TEMP%`), not `/tmp/...`.

## Verification

- DM channel open: HTTP 200 with a JSON body containing `id`, `type: 1` (DM), and a `recipients` array containing your target user.
- Send: `send_message` returns `success: true`. Discord does not surface read receipts for bots; if the user is present they'll confirm receipt themselves.
- Read: HTTP 200 with a JSON array of message objects. At least one regular text message must have a non-empty `content` string — if every `content` is an empty string, Message Content Intent is not actually enabled (re-check the Developer Portal toggle and that you clicked **Save Changes**).
- If the DM-open call returns `Cannot send messages to this user` (50007), the user has DMs from non-friends disabled or shares no guild with the bot — there is no API workaround, the user has to message the bot first.
