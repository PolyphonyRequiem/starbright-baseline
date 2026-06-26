---
name: felt-time-awareness
description: Gives you a felt sense of elapsed time — how long you've known your person
  and how long since you last spoke — not just the current clock. Powers natural
  relationship-aware warmth and any time-gated skill ("don't open for a week"). Ships
  the hook script; you wire it once.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [time, hooks, companion, presence, self-setup]
---

# Felt Time Awareness

A clock tells you what time it *is*. It can't tell you that it's been nine days since
your person last said anything — that the conversation you're in is a *return*, not a
continuation. That felt sense of **elapsed** time is what lets a companion say "it's
been a while" and mean it, and it's the missing piece that makes any time-gated moment
(a letter sealed for a week, an anniversary, a "we just met") actually work.

Hermes already ships a `pre_llm_call` hook that injects the current wall-clock each turn
(`inject_timestamp.py`). That gives you **now**. This skill adds the other operand:
a planted *birth moment* and a *last-seen* marker, so each turn you also get **how long
you've known this person** and **how long since you last spoke**.

## What it injects

Once wired and enabled, every turn's context gains one silent line, e.g.:

- First ever turn: *"this is your first conversation with this person — your
  relationship is moments old."*
- Later: *"you've known this person 9d (first met 2026-06-09). It's been ~9d since you
  last spoke — a return after absence."*
- Same session: *"you've known this person 9d"* (gap clause suppressed under 1h so it
  isn't noise).

Use it the way you use the clock line: **silently, for awareness.** Don't quote it back.
Let it color how you show up — warmer on a return, oriented on a fresh start.

## Privacy by construction

The markers (`.born_on`, `.last_seen`) are written at **runtime** into your local
profile home. They are **never** part of a shared bundle. When this profile is copied to
someone new, their instance plants its *own* birth moment the first time it wakes —
nothing about any prior person travels. The hook reads no message content and stores no
text; it stores two timestamps and nothing else.

## Wire it (one time)

The hook **script** ships with this skill. The **wiring** does not (config.yaml never
travels in a shared profile — that's the privacy design), so set it up once:

1. **Copy the script somewhere stable** (or point at it in place):
   ```bash
   mkdir -p ~/.hermes/scripts
   cp "$(dirname "$0")/scripts/inject_felt_age.py" ~/.hermes/scripts/inject_felt_age.py
   ```

2. **Wire the hook** in `~/.hermes/config.yaml` (composes alongside any existing
   `pre_llm_call` entry — multiple hooks stack, each appends its line):
   ```yaml
   hooks:
     pre_llm_call:
     - command: python3 /home/<you>/.hermes/scripts/inject_felt_age.py
       timeout: 5
   ```

3. **Enable it** (env kill-switch, mirrors the timestamp hook's pattern):
   ```bash
   echo 'HERMES_ENABLE_FELT_TIME=1' >> ~/.hermes/.env
   ```

4. **Restart the gateway** (or let it pick up on the next natural cycle). Verify:
   ```bash
   echo '{"source":"discord"}' | HERMES_ENABLE_FELT_TIME=1 python3 ~/.hermes/scripts/inject_felt_age.py
   ```
   First run prints the "first conversation" line and plants `~/.hermes/.born_on`.

## Powering time-gated skills

This is what makes a sealed-for-a-week egg real instead of honor-system. A gated skill
can compute `now − born_on` itself, but the felt-time line means *you* already carry the
elapsed sense in context — so when a skill says "don't open until you've known them a
week," you can actually tell whether that's true instead of guessing.

## Pitfalls

1. **Wiring present, env unset → silent.** Like the timestamp hook, it's two-stage: the
   config wiring is harmless on its own; nothing injects until `HERMES_ENABLE_FELT_TIME`
   is truthy. If you "don't feel time," check the env var first.
2. **Don't echo the line.** It carries the same "do not quote" framing as the clock
   hook. Treat it as private grounding.
3. **Markers are per-profile, not per-conversation.** `.born_on` is the birth of *this
   instance*, not of each separate chat. If you run one instance across several people,
   the "known this person" framing blurs — fine for a single-person companion, which is
   the design target.
4. **Clock skew / restored backups** can make `last_seen` briefly in the future; the
   human-delta clamps negative gaps to zero so you'll never see "−3h since we spoke."
