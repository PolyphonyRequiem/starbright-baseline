# Why "I made the profile leaner" doesn't speed up an active session

## Symptom

You changed a profile's config to be leaner — disabled toolsets, restricted
skills, pinned aux providers, dropped the system-prompt size. You restart the
gateway, send a message, and the next turn is *still* slow with a fat-looking
prompt.

## Root cause: Hermes correctly preserves the stored prompt for cache stability

Hermes builds the system prompt **once per session** and stores it in the
session DB at `~/.hermes/profiles/<name>/state.db`, table `sessions`, column
`system_prompt`. On every subsequent turn, the gateway constructs a fresh
`AIAgent`, reads the stored prompt back from the DB, and replays it
**byte-identical** so the upstream prefix cache stays warm. This is documented
in `agent/conversation_loop.py` around the "Stored system prompt" path.

This means: if your config gets leaner *between* turns of an existing session,
the new lean prompt is **not** what the agent sends — the old fat prompt is.
The new prompt only takes effect on **new sessions**.

This is the right behavior for cache reuse. It is the wrong behavior when you
explicitly want the lean prompt now.

## How to verify (before "fixing" anything)

Read the stored prompt length for the active session:

```python
import sqlite3
db = sqlite3.connect("/home/<user>/.hermes/profiles/<name>/state.db")
cur = db.cursor()
cur.execute("""
    SELECT id, source, LENGTH(COALESCE(system_prompt,'')) AS prompt_len,
           system_prompt IS NULL AS is_null, started_at, message_count
    FROM sessions ORDER BY started_at DESC LIMIT 5
""")
for row in cur.fetchall():
    print(row)
db.close()
```

If `prompt_len` is much larger than what the lean config should produce, the
old fat prompt is still bound to the session.

## The fix: invalidate the stored prompt for that session

NULLing the column forces a rebuild on the next turn. The first turn after the
NULL pays a cold-prefill cost (the new lean prompt enters the cache for the
first time), but every subsequent turn warm-caches at the smaller size:

```python
import sqlite3
db = sqlite3.connect("/home/<user>/.hermes/profiles/<name>/state.db")
cur = db.cursor()
cur.execute("UPDATE sessions SET system_prompt = NULL WHERE id = ?", (session_id,))
db.commit()
db.close()
```

Hermes's session-load path treats NULL as "rebuild from scratch this turn"
and logs a warning if `conversation_history` is non-empty (legacy / migration
case) — this is not an error, it's the recovery path.

## When NOT to do this

- If the user is mid-conversation and the latency is acceptable, leave the
  stored prompt alone. One cold-prefill cost for a marginal lean is bad value.
- If you're testing the *new* config, start a `/reset` (new session) instead —
  cleaner than mutating the DB.
- Never NULL the prompt of a session that is currently running a turn (race
  with the persistence write at turn end). Wait for the slot to be idle:
  `curl -s http://<host>:8080/slots | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["is_processing"])'`.

## What "lean" actually changes

These config knobs change the system prompt and benefit from a session rebuild:
- `enabled_toolsets` / `disabled_toolsets`
- `agent.tool_use_enforcement`
- `skills` allow/deny lists (inside `cli.skill_*` config — Hermes embeds a
  skills index in the system prompt)
- The volatile-tier blocks (memory, USER.md) update naturally per-session and
  don't require manual invalidation.

## Don't conflate "lean prompt" with "fast first reply"

The first reply on a freshly-rebuilt prompt is **always** a cold prefill — the
new prompt just hasn't hit the prefix cache yet. The win is on turns 2+,
which warm-cache at the smaller token count and stay fast. Set the user's
expectation accordingly: "first reply still ~30-90s, every reply after that
should feel instant."
