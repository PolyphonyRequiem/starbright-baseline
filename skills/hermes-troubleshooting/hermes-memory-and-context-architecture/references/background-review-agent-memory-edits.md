# The Background-Review Agent and Memory Edits

## What it is

After every foreground reply that meets the heuristic (`agent/background_review.py`), Hermes spawns a **separate agent process** with the prompt:

> "Review the conversation above and consider saving to memory if appropriate. Focus on..."

This is the agent that actually authors most edits to `~/.hermes/memories/USER.md` and `MEMORY.md`. It runs in its own thread (`bg-review:` prefix in `agent.log`), gets its own `AIAgent` instance and its own session_id, and its tool calls are NOT persisted to the foreground session's message thread in `state.db`.

In practice: when the user asks "what did you update my profile with most recently?", the literal answer is "the background-review agent did, and from my foreground vantage point I cannot see its tool_calls list." You have to reconstruct the edit from file mtime + agent.log grep.

## How to reconstruct what bg-review wrote (worked example, 2026-06-05)

User asked: *"What did you update my user profile with most recently?"*

### Step 1 — disk-write timestamp (ground truth)
```
stat -c '%y  %n' ~/.hermes/memories/USER.md ~/.hermes/memories/MEMORY.md
```
Output:
```
2026-06-05 22:35:37.786375747 -0700  /home/<user>/.hermes/memories/USER.md
2026-06-05 22:10:00.593806457 -0700  /home/<user>/.hermes/memories/MEMORY.md
```
USER.md mtime is 22:35:37 — that's the most recent write.

### Step 2 — match to agent.log
```
grep "2026-06-05 22:3[3-7]" ~/.hermes/logs/agent.log | grep "tool memory"
```
Found:
```
2026-06-05 22:35:32,765 WARNING ... Tool memory returned error (0.00s): {"success": false, "error": "Replacement would put memory at 1,387/1,375 chars. Shorten the new content or remove other entries first."}
2026-06-05 22:35:37,789 INFO  ... tool memory completed (0.00s, 1501 chars)
```
The bg-review tried at 22:35:32, got rejected for exceeding the 1,375-char USER cap, retried at 22:35:37 with a tighter version, succeeded. The 1,501 char count is the tool RESPONSE size (the success message + remaining-budget info), not the file size.

### Step 3 — read the current file
```
read_file ~/.hermes/memories/USER.md
```
Now you can present the current state. To show the *diff* you'd need the previous content, which Hermes doesn't snapshot by default — the bg-review's assistant message holding the `old_text`/`content` args is in its own ephemeral session and is not durably persisted.

### Step 4 — name it honestly to the user
"The most recent write was at 22:35:37 PDT tonight, made by the background-review agent (a separate process that runs silently after my replies). It tried once and was rejected for exceeding the USER cap, then retried with a tighter version. Here's the current content: ..."

## Why the foreground session's state.db doesn't carry the edit

The bg-review agent uses `agent_init.py`'s `AIAgent` constructor with `session_id=None` (or a derived bg-review session id, depending on version), and writes to `state.db` go under THAT session_id — not the user-facing one. So:

```python
# In foreground session 20260605_072838_e054d1a9:
cur.execute("SELECT * FROM messages WHERE session_id=? AND tool_name='memory'", (sid,))
# → returns 0 rows even though the foreground turn definitely triggered a memory edit
```

The records do exist somewhere in state.db (the bg-review writes go through the same `SessionDB`), they're just under a different session_id. If you really need the bg-review's exact tool args, search by timestamp window across ALL sessions:

```python
cur.execute("""
  SELECT id, session_id, role, tool_name, timestamp, substr(content,1,800)
  FROM messages
  WHERE timestamp BETWEEN ? AND ?
""", (target_ts - 60, target_ts + 60))
```

This may or may not return rows depending on bg-review persistence settings; the file mtime + agent.log path is more reliable.

## The "abbreviation surprise" pitfall

The bg-review agent is aggressively character-conscious because it lives under the 1,375 / 2,200 char caps. To pack more facts into one `§` block it will:

- Drop articles and qualifiers (`the user is colorblind` → `D: colorblind`)
- Abbreviate domain jargon (`executive function` → `EF`, `vulnerability` → `vuln`, `competency` → `comp`)
- Merge two semantically-related facts into one comma-separated clause

This is fine for retrieval and storage but can create a usability surprise: the user reads their profile, sees `high-EF`, and asks "what does EF mean?" because they don't think in those abbreviations — bg-review does.

**Rule for the bg-review agent (encoded here as a target for future bg-review prompts and as a foreground correction signal):** when compressing to fit, prefer dropping a qualifier or merging entries over inventing new abbreviations. If you MUST abbreviate, only use abbreviations the user has used themselves in the conversation being reviewed. The 2026-06-05 case: `executive function` was already familiar to the user from the `the user-ef-errand-nudge-chain` skill, but compressed in the USER profile to `high-EF` it read as a typo for "electromagnetic frequency" until I explained.

If you (foreground agent) read your own USER.md and find a confusing abbreviation, that's a signal that the next bg-review pass should expand it back out — patch the entry on the next memory write to be self-explanatory.
