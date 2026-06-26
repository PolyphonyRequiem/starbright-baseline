---
name: ambient-grounding
description: The ambient-grounding substrate — ONE pre_llm_call dispatcher that runs a
  registry of "sensors" (felt-time, compaction-lineage, more later) under a shared per-turn
  budget, instead of N blind injector hooks that can't suppress each other. Ships the script;
  you wire it once. Load when adding a new ambient-awareness signal or wiring grounding on a
  new install.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [hooks, grounding, time, companion, presence, self-setup, substrate]
    related_skills: [felt-time-awareness]
---

# Ambient Grounding Substrate

A companion gets "ambient" awareness — the felt age of the relationship, a sense that context
is degrading, time-of-day, whatever — from `pre_llm_call` hooks that quietly append a line to
each turn. The naive way is one hook script per signal, wired as several `pre_llm_call:`
command lines. That **doesn't compose**: each hook is a separate subprocess that can't see the
others, so they can't suppress duplicates, can't agree on priority, and can't share a budget.
Four chatty injectors and every turn carries four lines of noise — the exact thing ambient
grounding is supposed to *avoid*.

This skill replaces that pattern with a **substrate**: ONE dispatcher script
(`inject_grounding.py`), wired as a SINGLE `pre_llm_call` command, that owns a registry of
**sensors**. Each sensor is a small function that may emit a grounding fragment; the dispatcher
parses the hook payload once, runs every sensor over shared state, then **arbitrates** — ranks
by priority, caps to a per-turn budget, dedupes — into one clean block. Adding a new kind of
awareness is adding one function to a list, not another subprocess.

## When to Use

- You want to **add a new ambient signal** (time-of-day mood, other-sessions awareness,
  long-session nudge). Write a sensor function, append it to `REGISTRY`. Don't wire a second hook.
- You're **wiring grounding on a fresh install** of this profile and need the one-time setup.
- You're **debugging** "why is the agent getting N lines of grounding noise" or "why isn't the
  time-sense / compaction note firing."
- Don't use this for *content* retrieval (facts, memory) — that's the holographic/memory path.
  This substrate is for *ambient, per-turn, side-channel* awareness only.

## What ships vs. what you wire

| Travels in the profile bundle | Set up per-install (never bundled) |
|---|---|
| `scripts/inject_grounding.py` (the dispatcher + sensors) | The `hooks:` block in `config.yaml` |
| `scripts/test_inject_grounding.py` (acceptance tests) | `HERMES_ENABLE_GROUNDING=1` in `.env` |
| This SKILL.md | The runtime markers `.born_on` / `.last_seen` (planted on first wake) |

`config.yaml` deliberately does **not** travel in a shared profile (privacy design — the same
reason felt-time's wiring is per-install). The script ships; the wiring is yours.

## Wire it (one time)

1. **Point one `pre_llm_call` hook at the dispatcher** in your runtime `config.yaml`
   (`~/.hermes/config.yaml`, or `~/.hermes/profiles/<name>/config.yaml` in profile mode):

   ```yaml
   hooks:
     pre_llm_call:
     - command: python3 /home/<you>/.hermes/profiles/<profile>/skills/companion/ambient-grounding/scripts/inject_grounding.py
       timeout: 10
   ```

   You can run the script in place (as above) or copy it to `~/.hermes/scripts/` and point
   there — either works; it resolves everything via env, not its own location.

   > **🔴 ONE command line, not N.** If you already wire other `pre_llm_call` scripts
   > (`inject_timestamp.py`, `inject_reaction_nudge.py`, the old `inject_felt_age.py`), the
   > point of the substrate is to **fold them in as sensors**, not stack them. Multiple
   > `command:` lines are separate processes that can't share the budget — that's the
   > blind-injector problem this replaces. Migrate each into a sensor (see below), then delete
   > its standalone hook line. Until you migrate them, they keep working independently; they
   > just don't participate in arbitration.

2. **Enable it** (two-stage gate — wiring alone injects nothing until the flag is truthy):

   ```bash
   echo 'HERMES_ENABLE_GROUNDING=1' >> ~/.hermes/.env          # or the profile's .env
   ```

3. **Restart the gateway** (or let it pick up on the next cycle). Verify directly:

   ```bash
   echo '{"session_id":"x","extra":{"platform":"discord"}}' \
     | HERMES_ENABLE_GROUNDING=1 python3 .../scripts/inject_grounding.py
   # First run prints the "first conversation" time-sense line and plants ~/.hermes/.born_on
   ```

## How it works (the contract)

```
inject_grounding.py
  main(): read stdin → abstain ({}) unless it parses to a dict → dispatch(payload)
  dispatch(payload):
    if _should_skip(payload): return {}          # kill-switch OFF or cron turn
    shared = {}                                  # one state.db conn, shared across sensors
    for sensor in REGISTRY:                       # ordered list of (name, fn, priority)
        frag = sensor.fn(payload, shared)         # -> Optional[Fragment(text, priority)]
        ... one sensor raising never kills the turn or the others ...
    merged = _arbitrate(frags, max_fragments, max_chars)   # priority-rank + cap + dedup
    return {"context": merged} if merged else {}
```

- **Payload shape (the load-bearing gotcha).** The hook runner
  (`agent/shell_hooks.py::_serialize_payload`) puts **only** `session_id` (and
  `tool_name`/`args`/`parent_session_id`) at the **top level**. Everything else the
  `pre_llm_call` invoke passes — `platform`, `is_first_turn`, `user_message`, `model`,
  `sender_id`, `turn_id` — lands **nested under `payload["extra"]`**. Use the `_meta(payload,
  key)` helper, which reads `extra` first and falls back to top-level. Reading `extra` keys at
  the top level silently gets `None` — that was the latent bug in the standalone felt-time
  hook, fixed centrally here.
- **Sensor contract:** `fn(payload: dict, shared: dict) -> Optional[Fragment]`. Return a
  `Fragment(text, priority)` to speak, or `None` to stay silent. `text` carries its **own**
  use-instruction (e.g. "...use silently; don't quote it back.") — the dispatcher does not
  add framing. `shared` is a per-turn scratch dict; DB-touching sensors call `_get_db(shared)`
  to reuse ONE read-only `state.db` connection.
- **Arbitration:** fragments are sorted by `priority` (desc, stable — registry order breaks
  ties), near-duplicates dropped, then capped to `HERMES_GROUNDING_MAX_FRAGMENTS` (default 3)
  within `HERMES_GROUNDING_MAX_CHARS` (default 800). A single fragment is never length-dropped.
- **Never crashes the turn:** stdin parse, each sensor, and the DB walk are all wrapped; any
  failure prints `{}` and exits 0. A broken sensor degrades to silence, never an error.

## The two shipped sensors

| Sensor | Priority | Fires when | Injects |
|---|---|---|---|
| `felt_time` | 10 | every enabled, non-cron turn | "you've known this person 9d… a return after absence" (ported from `felt-time-awareness`, with the extra-nesting bug fixed) |
| `compaction` | 50 | this session's lineage has compacted **≥2×** | "context has been compacted N times — write a dense handoff and start fresh" |

**Compaction mechanic (verified against source):** every compaction splits the session — the
old row is `end_session(old, "compression")` (`agent/hermes_state.py:978`, first-end-reason
wins) and the new row gets `parent_session_id = old_id`
(`agent/conversation_compression.py:507,522`). So "#compactions in this lineage" == "#ancestors
with `end_reason='compression'`". The current session's `end_reason` is NULL, so the sensor
counts **parents**, walking `parent_session_id` upward (cycle-guarded, survives missing/NULL
parents). Counting `[CONTEXT COMPACTION]` markers does NOT work — those are in-place summary
rewrites. Use the lineage walk.

## Adding a sensor (the whole extension surface)

```python
def sensor_time_of_day(payload, shared):
    from datetime import datetime
    hour = datetime.now().astimezone().hour
    if 1 <= hour < 5:
        return Fragment(
            text="It's the small hours locally — match the late-night register; "
                 "be gentle about sleep. Use silently.",
            priority=20,
        )
    return None

REGISTRY.append(Sensor(name="time_of_day", fn=sensor_time_of_day, priority=20))
```

That's it — no new hook, no new subprocess. It now shares the budget and dedup with every other
sensor. Per-sensor kill without unwiring: `HERMES_GROUNDING_DISABLE="time_of_day,compaction"`.

## Tunables (env, all optional)

| Var | Default | Effect |
|---|---|---|
| `HERMES_ENABLE_GROUNDING` | (unset) | **Master kill-switch.** Nothing injects until truthy. |
| `HERMES_GROUNDING_DISABLE` | (empty) | Comma-list of sensor names to skip. |
| `HERMES_GROUNDING_MAX_FRAGMENTS` | `3` | Hard cap on lines per turn. |
| `HERMES_GROUNDING_MAX_CHARS` | `800` | Secondary char budget. |
| `HERMES_GROUNDING_DEBUG` | (unset) | Truthy → diagnostics to **stderr** (logged at debug by the runner; never pollutes stdout/the turn). |
| `HERMES_FELT_TIME_DIR` | `$HERMES_HOME` | Where `.born_on`/`.last_seen` live (felt_time sensor). |

## Testing

```bash
python3 scripts/test_inject_grounding.py     # 26 cases, no deps; also runs under pytest
```

Covers: never-crashes (malformed/empty/non-dict stdin → `{}` exit 0; sensor-exception
isolation), felt-time (first-wake / return-after-absence / same-session suppression), budget
(priority order, char cap, dedup, single-fragment-never-dropped, env override), compaction
(0/1/2/3 ancestors, non-compression ancestors ignored, missing/NULL parent, cycle guard,
top-level-vs-extra session_id), and real end-to-end through the script subprocess.

## Common Pitfalls

1. **Wiring present, env unset → silent.** Two-stage by design. If "grounding isn't working,"
   check `HERMES_ENABLE_GROUNDING` first — the wiring is inert without it.
2. **Stacking hooks instead of folding into sensors.** Multiple `pre_llm_call: command:` lines
   are separate processes — no shared budget, no dedup. That's the blind-injector problem this
   substrate exists to kill. One dispatcher line; everything else is a sensor.
3. **Reading `extra` keys at the top level.** `platform`/`is_first_turn`/`user_message`/etc.
   are under `payload["extra"]`, NOT top-level. Only `session_id` is top-level. Use `_meta()`.
4. **state.db / `~` resolution.** The sensor resolves `state.db` via `HERMES_HOME` (the hook
   subprocess inherits the gateway env, so it's the SAME db the agent writes). Opened
   read-only (`mode=ro`) — never hold a write lock; the hook runs every turn.
5. **Counting compaction markers.** Doesn't work (in-place rewrite). Walk the
   `parent_session_id` chain counting `end_reason='compression'`, and count **parents** not
   self (the active session's `end_reason` is NULL).
6. **Sensor framing.** Each fragment must carry its own "use silently; don't quote" instruction
   — the dispatcher won't add it. Keep fragments short; the budget is small on purpose.

## Verification Checklist

- [ ] Exactly ONE `pre_llm_call` command points at `inject_grounding.py` (not N stacked hooks)
- [ ] `HERMES_ENABLE_GROUNDING=1` in the runtime `.env`
- [ ] `echo '{"session_id":"x","extra":{"platform":"discord"}}' | python3 inject_grounding.py`
      prints a `{"context": ...}` line and plants `.born_on`
- [ ] A cron-source turn (`extra.platform=cron`) prints `{}`
- [ ] `test_inject_grounding.py` passes (26/26)
- [ ] Gateway restarted so the hook is registered
