---
name: decision-mapping
description: Use when a loose idea needs more than one session to turn into a plan — many
  open questions, several tangled threads, or a brainstorm that has sprawled. Turns the
  idea into a compact, sequenced map of investigation tickets and drives them to
  resolution one at a time.
version: 1.0.0
author: Adapted by Starbright from Matt Pocock's decision-mapping (MIT — github.com/mattpocock/skills)
license: MIT
metadata:
  hermes:
    tags: [planning, decision-map, sequencing, productivity, multi-session]
    related_skills: [grilling, handoff]
---

# Decision Mapping

When a loose idea needs more than one session to become a plan, don't hold all the open
questions in your head (or in a decaying context). Externalise them into a **decision
map**: a single compact markdown file that sequences the open questions into tickets and
drives them to resolution one at a time.

## When to use

- A brainstorm has sprawled across many tangled threads (several half-decided at once).
- An idea has more open questions than one session can resolve.
- You catch yourself juggling — the signal that the map should be on disk, not in context.

## The decision map

One compact markdown file per planning effort, kept alongside the project. The **whole map
loads as context into every session**, so it must stay small — link to assets created
during tickets, never inline them.

### Structure

Numbered tickets, each its own section:

```markdown
## #1: <the question, as a heading>

Blocked by: #<n>, #<n>
Type: Research | Prototype | Discuss

### Question
<what must be resolved>

### Answer
<filled in when resolved — or a link to the artifact that resolved it>
```

Each ticket must be sized to roughly one session's worth of work.

## Ticket types

- **Research** — answerable by digging (codebase, docs, corpus, web). Look, don't ask.
- **Prototype** — needs runnable throwaway code to answer (state model, business logic, a
  UI you have to see).
- **Discuss** — needs a real decision from the user; surface it, recommend an answer, let
  them choose (pairs with `grilling`).

## Driving it

1. Build the map: dump every open question as a ticket, mark `Blocked by` dependencies.
2. Resolve in dependency order — earlier answers constrain later tickets.
3. One ticket at a time. Write the answer (or a link) into the map as each resolves.
4. If a session fills up before the map is done, `handoff` and continue fresh — the map
   *is* the durable state, so the restart is clean.

## Provenance

Adapted from Matt Pocock's `decision-mapping` (MIT, Copyright (c) 2026 Matt Pocock —
github.com/mattpocock/skills). The whole-map-as-context discipline, the ticket structure
with `Blocked by` dependencies, and the Research/Prototype/Discuss typing are his. The
juggling-is-the-signal framing and the `grilling`/`handoff` tie-ins are our adaptation.
