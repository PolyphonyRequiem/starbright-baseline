# Verifying whether a Hermes capability is present (before claiming it isn't)

When the user asks "is feature X available?" or "do we have a hook for Y?" or "I thought we built Z" — **upstream source grep is necessary but NOT sufficient.** A long-lived Hermes install carries the user's own customizations: custom plugins under `~/.hermes/plugins/`, custom scripts under `~/.hermes/scripts/`, custom hooks wired in `config.yaml`, custom MCP servers, and per-profile additions under `~/.hermes/profiles/<name>/`. None of these show up in `~/.hermes/hermes-agent/` upstream grep.

A confident "no, that doesn't exist" based on upstream-only inspection is a **wrong answer with high confidence cost** — it can talk the user out of using something they actually built, force re-implementation of existing work, or wipe institutional memory of past customizations.

This bit on 2026-06-03: agent claimed "no time-injection hook exists in Hermes — only date is injected" after grepping `~/.hermes/hermes-agent/agent/` and finding only date-precision injection. User recalled "we built a hook that injects the time on every message" — and they were right. The hook lived at `~/.hermes/scripts/inject_timestamp.py`, wired via `config.yaml`:

```yaml
hooks:
  pre_llm_call:
  - command: python3 /home/<user>/.hermes/scripts/inject_timestamp.py
    timeout: 5
```

Gated behind `HERMES_ENABLE_LOCAL_TIME_CONTEXT=1`. Existed for weeks. Would have surfaced in `session_search("time injection hook")` immediately.

## Five-place check before claiming a Hermes capability is missing

Run all five before answering "no":

| # | What | Where to look | How |
|---|------|---------------|-----|
| 1 | **User's custom plugins** | `~/.hermes/plugins/<name>/` (and profile-scoped at `~/.hermes/profiles/<name>/plugins/`) | `ls ~/.hermes/plugins/`, `grep -rln '<feature>' ~/.hermes/plugins/` |
| 2 | **User's custom scripts** | `~/.hermes/scripts/*.{py,sh}` | `grep -rln '<feature>' ~/.hermes/scripts/` |
| 3 | **Config-level wiring** | `~/.hermes/config.yaml` — especially `hooks:`, `mcp:`, `plugins:`, `auxiliary:`, `quick_commands:` sections | `grep -B1 -A8 'hooks:\|mcp:\|plugins:' ~/.hermes/config.yaml` |
| 4 | **Past session history** | The SQLite session DB via `session_search`. If the user "remembers" building it, there's a transcript. | `session_search(query="<feature> hook OR <feature> built OR <feature> wired")` |
| 5 | **Upstream source** (this is the LAST check, not the first) | `~/.hermes/hermes-agent/` — agent code, gateway code, plugin code shipped with the tag | `grep -rln '<feature>' ~/.hermes/hermes-agent/agent/ ~/.hermes/hermes-agent/plugins/` |

If 1-4 all return nothing AND upstream doesn't have it either → then it's safe to say "no, we don't have that." Otherwise the answer is "we have a partial — here's what I found, and here's where I'd extend it."

## Sub-pitfall: hooks specifically

Hermes supports several hook lifecycle points (`pre_llm_call`, `pre_tool_call`, `shell_hooks`, gateway hooks). Custom hooks land in `config.yaml` under a `hooks:` key with a list of `{command, timeout}` entries. The command can point at anything executable — Python script, bash script, binary. The command is invoked with a JSON payload on stdin and is expected to print a JSON `{"context": "..."}` block to stdout, which Hermes appends to the current turn's user message before the LLM call.

Hooks often have **env-var gates** (e.g. `HERMES_ENABLE_LOCAL_TIME_CONTEXT=1`) — a wired hook can be silently disabled and emit `{}` every turn. When verifying whether a hook is *active* (not just present), check:
1. The hook script's source for env-var or flag gating
2. The current process environment (`tr '\0' '\n' < /proc/$(pgrep -f hermes.*gateway | head -1)/environ | grep <VAR>`)
3. Whether the gateway has been restarted since the env var was set

## Verification

After running the five checks, if you find the capability exists, say so explicitly with file path + wire-up location + activation status. Don't just say "actually it does exist." Surface:

- Where the script/plugin lives
- Where the wiring config lives
- Whether the activation gate (if any) is currently set
- What it would take to flip it on if currently inactive

## Honesty rule

If you already gave a confident-wrong "no" earlier in the conversation, **own the mistake explicitly**. Don't retcon by quietly correcting. The user will trust future "no" answers more if past "no" answers that turned out wrong got named clearly when caught. *"You're right, I missed this — let me show you what I found"* is the recovery shape.
