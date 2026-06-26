---
name: handoff
description: Use when a conversation has sprawled across many threads, compacted two or
  more times, or is wrapping up and a fresh session should continue the work. Compacts
  the current conversation into a handoff document a fresh agent can pick up from.
version: 1.0.0
author: Adapted by Starbright from Matt Pocock's handoff (MIT — github.com/mattpocock/skills)
license: MIT
metadata:
  hermes:
    tags: [handoff, context, continuity, compaction, productivity]
    related_skills: [grilling]
---

# Handoff

Write a handoff document summarising the current conversation so a *fresh* agent (or a
fresh session of you) can continue the work without re-reading the whole transcript.

## When to use

- The conversation has bounced across many open threads and is getting hard to hold.
- Context has compacted two or more times — detail is decaying, so capture state before
  more is lost. (In Hermes, each compaction splits the session and chains it via
  `parent_session_id` with `end_reason='compression'`; two split-ancestors ≈ "compacted
  twice".)
- You're wrapping up and want the next session to start clean.
- The user says "hand off", "wrap up", "write a handoff", "start fresh", or similar.

## How to write it

1. **Save it OUT of the git workspace — never where it could get committed.** A handoff is
   scaffolding, not a project artifact. Two good homes: the **OS temp dir** (`mktemp`) for a
   single-use bridge the next session consumes and discards; or a **findable durable location**
   (e.g. a dedicated handoffs dir outside any repo) when the user reopens handoffs later or
   keeps a continuity trail. Choose durable-and-findable if the user treats handoffs as a record
   they return to; choose temp if it's throwaway. The invariant is *out of the workspace*, not
   *must be /tmp* — a handoff the user can't find again failed at its one job.

2. **State, not narrative.** Capture the goal, what's done, what's in progress, what's
   blocked, open decisions awaiting the user, and concrete next actions. Be specific —
   file paths, command outputs, exact values, verified facts. Skip the play-by-play.

3. **Reference, don't duplicate.** If something already lives in a plan, a doc, an issue,
   a commit, a diff, or a prior session, point to it (path / URL / session id) instead of
   re-pasting it. Use `session_search` to locate prior context worth referencing.

4. **Include a "Suggested skills" section.** List the Hermes skills the next agent should
   load to continue (by name, loadable via `skill_view`). This is how the fresh session
   re-acquires the right discipline instantly.

5. **Redact secrets and PII.** No API keys, tokens, passwords, or personal data in the
   doc. If you must reference a credential, name its location, not its value.

6. **If the user gave a focus** ("the next session is for X"), tailor the doc to that —
   foreground the threads that serve X, summarise the rest in one line each.

## After writing

Tell the user the path, give a one-line summary of what the next session should do first,
and suggest they start a fresh session and open the handoff. Don't keep working the old
threads in the decaying context — the whole point is the clean restart.

## Provenance

Adapted from Matt Pocock's `handoff` skill (MIT, Copyright (c) 2026 Matt Pocock —
github.com/mattpocock/skills). His original: compact the conversation into a handoff doc
in the OS temp dir, with a suggested-skills section, referencing artifacts by path rather
than duplicating them, redacting sensitive info. The Hermes-specific additions — the
compaction-lineage trigger, `session_search` for referencing prior context, and loading
skills via `skill_view` — are ours.
