# Discord REST API — curl Recipes

Concrete, copy-pasteable recipes for the operations that Hermes's built-in `send_message` tool cannot perform. All recipes assume `DISCORD_BOT_TOKEN` is loaded into the shell.

## Loading the token (git-bash on Windows)

```bash
set -a; source ~/.hermes/.env; set +a
```

Verify with `echo "${DISCORD_BOT_TOKEN:+set}"` — should print `set`. If `curl` returns `{"message": "401: Unauthorized"}`, the token did not load into the current subshell; rerun the `source` line in the same `terminal()` call as the curl.

## Why these are needed (not in `send_message`)

| Operation | `send_message` | curl |
|---|---|---|
| Send message to existing channel | ✓ | ✓ |
| Open a DM channel with a user ID | ✗ | ✓ |
| Read channel messages | ✗ | ✓ |
| Send message > 2000 chars | ✗ (errors) | ✗ (Discord limit) |

`send_message` resolves targets it already knows about. New DM channels and message reads must go through REST.

## Open a DM channel (one-time per user)

Given a Discord user ID (the snowflake — not the channel ID), POST to `/users/@me/channels` to materialize a DM channel. The response includes the channel ID you'll use forever after.

```bash
curl -s -X POST "https://discord.com/api/v10/users/@me/channels" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"recipient_id":"USER_ID_HERE"}'
```

The response `id` field is the DM channel ID. Save it to memory so you don't redo this dance next session:

> Example memory: `<Name> (Discord user ID 000000000000000001, DM channel ID 000000000000000002) — to DM them, send to discord:000000000000000002 (the DM channel, NOT the user ID).`

Once saved, future DMs go through `send_message(target="discord:<dm-channel-id>", message="...")` — no curl needed.

### What goes wrong if you skip this

- `send_message(target="discord:<user-id>", ...)` → `Discord API error (404): Unknown Channel` (Discord treats the ID as a channel ID, and user IDs are not channels).
- `send_message(target="discord:<username>", ...)` → `Could not resolve '<username>' on discord` (the adapter does not look up usernames).

## Send a message

Prefer `send_message` once you have the channel ID. Use curl only when `send_message` is unavailable or you need a feature it doesn't expose.

```bash
curl -s -X POST "https://discord.com/api/v10/channels/$CHANNEL_ID/messages" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/payload.json
```

Where `/tmp/payload.json` is `{"content": "..."}`. Use a file (not inline `-d`) when the message contains quotes, newlines, or shell metacharacters — it's much safer than escaping.

### 2000-char limit

Discord rejects messages over 2000 characters with `BASE_TYPE_MAX_LENGTH`. Options:

1. Trim aggressively — collapse bullet lists into inline `·`-separated runs.
2. Split into multiple messages.
3. Attach as a file (`multipart/form-data` with `payload_json` + `files[0]`).

## Read channel messages

```bash
curl -s -o /c/Users/$USER/AppData/Local/Temp/messages.json \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  "https://discord.com/api/v10/channels/$CHANNEL_ID/messages?limit=50"
```

Then parse with `execute_code`:

```python
import json, datetime
with open(r'C:\Users\<user>\AppData\Local\Temp\messages.json', encoding='utf-8') as f:
    msgs = json.load(f)
for m in reversed(msgs):  # API returns newest-first; reverse for chronological
    ts = datetime.datetime.fromisoformat(m['timestamp'].replace('Z', '+00:00'))
    author = m['author'].get('global_name') or m['author']['username']
    edited = ' (edited)' if m.get('edited_timestamp') else ''
    print(f"[{ts:%Y-%m-%d %H:%M}] {author}{edited}:\n{m['content']}\n")
```

Pagination: pass `&before=<message_id>` or `&after=<message_id>` for the next page.

### Empty `content` field?

Message Content Intent is OFF. Fix in Developer Portal → Bot → Privileged Gateway Intents → toggle MESSAGE CONTENT INTENT ON → Save. Then verify with a single message fetch — if `content` is populated, you're good.

## Cross-platform path gotcha (git-bash on Windows)

The `execute_code` sandbox runs as a Windows subprocess, so it does NOT understand git-bash's `/tmp/` or `/c/Users/...` paths. When writing a file from `terminal()` that you intend to read from `execute_code`, save it under a native Windows path:

```bash
# In terminal() — works for both git-bash AND the sandbox
curl -s -o /c/Users/danie/AppData/Local/Temp/messages.json ...
# That's the same as C:\Users\danie\AppData\Local\Temp\messages.json from Python's POV.
```

Then in `execute_code`, open with the Windows path: `open(r'C:\Users\danie\AppData\Local\Temp\messages.json')`.

## Other useful endpoints

| Need | Endpoint |
|---|---|
| Get user info | `GET /users/{user_id}` |
| Get channel info | `GET /channels/{channel_id}` |
| Get guild members | `GET /guilds/{guild_id}/members?limit=N` (needs Server Members Intent) |
| List guild channels | `GET /guilds/{guild_id}/channels` |
| React to message | `PUT /channels/{cid}/messages/{mid}/reactions/{emoji}/@me` |
| Edit message | `PATCH /channels/{cid}/messages/{mid}` |
| Delete message | `DELETE /channels/{cid}/messages/{mid}` |

Full reference: https://discord.com/developers/docs/reference
