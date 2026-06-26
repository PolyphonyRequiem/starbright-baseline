# Timestamp hook: gating, wiring, pitfalls

The `pre_llm_call` hook that injects wall-clock time into each turn's user message — how it's wired, how it's gated, and how to use it for time-of-day-dependent rules (sleep guard, after-hours nudges, "is it morning yet" awareness).

## Where it lives

| Component | Path |
|---|---|
| Script | `~/.hermes/scripts/inject_timestamp.py` |
| Config wiring | `~/.hermes/config.yaml` → `hooks.pre_llm_call` |
| Env-gate | `HERMES_ENABLE_LOCAL_TIME_CONTEXT` (truthy values: `1`, `true`, `yes`, `on`) |

## Config wiring

```yaml
# ~/.hermes/config.yaml
hooks:
  pre_llm_call:
  - command: python3 /home/<user>/.hermes/scripts/inject_timestamp.py
    timeout: 5
```

The hook runs every turn regardless of whether the env-gate is on — but if `HERMES_ENABLE_LOCAL_TIME_CONTEXT` is unset/falsy, the script returns `{}` and nothing gets injected. Two-stage gating is intentional: the wiring stays put across sessions so users don't have to remember to re-add it; the env var is the runtime kill switch.

## Script contract (verbatim shape)

```python
def main() -> int:
    payload = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
    except Exception:
        payload = {}

    source = str(payload.get("source") or payload.get("platform") or "").strip().lower()
    enabled = str(os.environ.get("HERMES_ENABLE_LOCAL_TIME_CONTEXT", "")).strip().lower() in {"1", "true", "yes", "on"}
    if source == "cron" or not enabled:
        print(json.dumps({}))   # no injection
        return 0

    now = datetime.now().astimezone()
    tz_label = now.tzname() or now.strftime("%z")
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    print(json.dumps({
        "context": (
            f"Current local time for grounding only: {stamp} {tz_label}. "
            "Use silently for temporal awareness. Do not quote, repeat, or append this timestamp in the user-facing reply."
        )
    }))
    return 0
```

Key behaviors:

- **JSON stdin payload** carries turn metadata (source, platform, etc.). Read it but don't fail on parse error — most calls only need the source.
- **Cron-source guard**: scheduled messages skip injection so the prefix doesn't leak into watcher/cron output. Without this guard, every cron run would emit visible `[Local time: …]` lines into Discord.
- **Silent-grounding framing**: the `Do not quote, repeat, or append this timestamp in the user-facing reply` instruction is **load-bearing**. The earlier version of this hook (pre-2026-05-30) emitted `[Local time: …]` without the instruction; that text was leaking into the-dreamer-facet watcher messages and other assistant replies. The current wording lets the model use the timestamp for reasoning without echoing it.
- **`timezone-aware datetime`** via `.astimezone()` — picks up local TZ from the system, not UTC. Important for sleep/morning rules.

## Enabling it

```bash
# Add to ~/.hermes/.env (persists across gateway restarts)
echo 'HERMES_ENABLE_LOCAL_TIME_CONTEXT=1' >> ~/.hermes/.env

# Takes effect on next gateway restart — does NOT require live restart;
# the user can let it pick up naturally on the next cycle.
```

Verify the env var is actually being seen by the running gateway process:

```bash
pid=$(pgrep -f 'hermes.*gateway' | head -1)
[ -n "$pid" ] && tr '\0' '\n' < /proc/$pid/environ | grep HERMES_ENABLE_LOCAL_TIME_CONTEXT
```

If the gateway was started before the env line was added, that grep returns nothing — the env scope is per-process. The change picks up on next gateway restart (`hermes gateway restart` or natural cycle).

## How the injection actually appears in the prompt

When enabled, the per-turn user message gets the line appended after Hermes's own gateway envelope. The model sees something like:

```
<user's actual message>

Current local time for grounding only: 2026-06-03 21:47:32 PDT. Use silently for temporal awareness. Do not quote, repeat, or append this timestamp in the user-facing reply.
```

The "Do not quote" framing is treated as a strong instruction by the model — well-trained agents will NOT prefix replies with the timestamp.

## Worked example: sleep-guard rule

Pattern for time-of-day-dependent rules:

1. **Bank the rule as a holographic fact** with tag words the user is likely to use in late-night messages:
   ```
   tags: sleep, late, evening, night, tired, bed, 9pm, 10pm, 11pm, midnight, hours, insomnia, accountability
   ```

2. **Enable the timestamp hook** (`HERMES_ENABLE_LOCAL_TIME_CONTEXT=1`).

3. **Two-layer firing**:
   - The timestamp injection gives passive time awareness ("it's 22:47, this is the late window the user flagged")
   - The holographic prefetch fires when user messages contain the trigger words
   - When BOTH layers concur (it's actually late AND the user is engaging in a way that surfaces the rule), the model has unambiguous context to enforce the rule

4. **Single-layer firing also works**:
   - Late evening but user's first message is unrelated → timestamp gives me awareness even if the holographic fact doesn't surface, and I can proactively reach for `fact_store search` if I want to verify
   - Trigger words but it's actually noon → holographic surfaces the fact and timestamp clarifies the rule doesn't apply

## Pitfalls

### Forgetting the env-gate

The hook is wired but disabled by default. New installs / fresh checkouts will have the script + config but no injection until the env var is set. If you ever claim "the agent has passive time awareness," verify the env var first — the wiring being present is necessary but not sufficient.

### Forgetting the source-guard exists

If you write a new pre_llm_call hook and don't add a `source == "cron"` check, every cron job's invocation will receive your injection in its turn context. For most hooks that's harmless; for some (auth tokens, user-personalized data) it might leak the wrong context to scheduled runs. Copy the cron-source guard pattern by default.

### Editing the script without preserving the silent-grounding instruction

The "Use silently for temporal awareness. Do not quote, repeat, or append" sentence is what keeps the timestamp from leaking into user-facing output. If you edit this script and drop that instruction in favor of pure data, expect the timestamp to start showing up in assistant prose again. The hard lesson from 2026-05-30 was that bare `[Local time: …]` text leaks aggressively.

### Confusing wall-clock injection with the system prompt date line

`agent/system_prompt.py:332` adds a "Conversation started: <weekday, month, day, year>" line — **date-only**. The timestamp hook is the **only** mechanism for minute-precision time awareness. Don't try to "add time to the system prompt" — you'll break prefix-cache stability and the right place for per-turn time data is the user-message envelope (which is what this hook does).

### Hook timeout

The `timeout: 5` in config means if the script takes more than 5 seconds, the hook is aborted and nothing is injected. The shipped timestamp script runs in ~10ms; if you write a heavier hook, watch the timeout — silent timeout failures are easy to miss because the prompt still goes to the LLM, just without your injection.

## Writing additional pre_llm_call hooks

Mirror the timestamp hook's shape:

```python
#!/usr/bin/env python3
import json, os, sys

def main() -> int:
    payload = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
    except Exception:
        payload = {}

    # 1. Source guard — skip for cron-triggered turns unless you want them
    source = str(payload.get("source") or payload.get("platform") or "").strip().lower()
    if source == "cron":
        print(json.dumps({}))
        return 0

    # 2. Env-gate — easy on/off without editing config
    if not os.environ.get("MY_HOOK_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        print(json.dumps({}))
        return 0

    # 3. Compute the injection
    context_text = "..."   # whatever per-turn signal you want surfaced

    # 4. Silent-grounding framing
    print(json.dumps({
        "context": f"{context_text}. Use silently. Do not quote in the user-facing reply unless asked."
    }))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

Then wire it under `hooks.pre_llm_call` in config.yaml alongside the existing entry. Multiple hooks compose — each one's `context` output is appended to the user message in config-order.

## Related upstream docs

Hermes hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks

See parent skill (`hermes-memory-and-context-architecture/SKILL.md`) for how this layer composes with always-on memory, holographic prefetch, and the system prompt date line.
