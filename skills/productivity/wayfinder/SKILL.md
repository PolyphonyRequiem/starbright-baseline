---
name: wayfinder
description: Plan a huge chunk of work — more than one agent session can hold — as a shared map of investigation tickets, and resolve them one at a time until the way to the destination is clear.
version: 1.1.0
author: Adapted by Starbright from Matt Pocock's wayfinder (MIT — github.com/mattpocock/skills)
license: MIT
disable-model-invocation: true
metadata:
  hermes:
    tags: [planning, wayfinding, tickets, fog-of-war, multi-session, productivity]
    related_skills: [grilling, decision-mapping, handoff, splitting-sessions, writing-great-skills]
---

# Wayfinder

A loose idea has arrived — too big for one agent session, and wrapped in fog: the way from
here to the **destination** isn't visible yet. Wayfinding is about finding that way, not
charging at the destination. This skill charts the way as a **shared map** of tickets, then
works those tickets one at a time until the route is clear.

**User-invoked.** Load `grilling` and `decision-mapping` — they supply the interview and
decision-capture discipline every ticket runs on.

The destination varies per effort, and naming it is the first act of charting — it shapes
every ticket. It might be a spec to hand off and iterate on, a decision to lock before
planning starts, or a change made in place like a data-structure migration. The map is
domain-agnostic — engineering work, course content, whatever fits the shape.

## Plan, don't do

Wayfinder is **planning** by default: each ticket resolves a decision, and the map is done
when the way is clear — nothing left to decide before someone goes and does the thing. The
pull to just do the work is usually the signal you've reached the edge of the map and it's
time to hand off (via the `handoff` skill). An effort can override this in its **Notes** —
carrying execution into the map itself — but absent that, produce decisions, not
deliverables.

## Refer by name

Every map and ticket has a **name** — its title. In everything the human reads — narration,
the map's Decisions-so-far — refer to it by that name, never by a bare id, number, or slug.
A wall of `#42, #43, #44` is illegible; names read at a glance. The id and path don't
vanish — a name wraps its link — but they ride *inside* the name, never stand in for it.

## Where the map lives (the tracker)

The map and its tickets need a store. Starbright ships **no issue-tracker skill**, so the
default is a **local-markdown tracker** — a `wayfinder/` directory in the working
directory:

```
wayfinder/
  map.md                 # the map (this is the canonical artifact)
  tickets/
    0001-<slug>.md       # one file per ticket; the number is its id
```

If the user's workspace *does* have a real tracker (a GitHub repo with issues, a Linear
project, an ADO board) and a skill to drive it, prefer that — a ticket becomes a native
issue, blocking uses the tracker's native dependency relationship, and the frontier renders
in the tracker's own UI. The rest of this skill is written against the local-markdown
default; translate "issue" → "file", "label" → "front-matter field", "assignee" → a
`claimed_by:` field as needed.

## The Map

The map is a single file, `wayfinder/map.md` — the canonical artifact. Its tickets are the
files under `wayfinder/tickets/`.

The map is an **index**, not a store. It lists the decisions made and points at the tickets
that hold their detail; a decision lives in exactly one place — its ticket — so the map
never restates it, only gists it and links.

### The map body

The whole map at low resolution, loaded once per session. Open tickets are **not** listed —
they are the un-resolved files under `tickets/`, found by a scan.

```markdown
## Destination

<what reaching the end of this map looks like — the spec, decision, or change this effort
is finding its way to. One or two lines; every session orients to it before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

<!-- the index — one line per closed ticket: enough to judge relevance, then open the link
for the detail the ticket holds -->

- [<closed ticket title>](tickets/0001-slug.md) — <one-line gist of the answer>

## Not yet specified

<!-- see "Fog of war": in-scope fog you can't ticket yet; graduates as the frontier advances -->

## Out of scope

<!-- see "Out of scope": work ruled beyond the destination; closed, never graduates -->
```

### Tickets

Each ticket is a file, `wayfinder/tickets/NNNN-<slug>.md`; the number is its identity. Its
body is the question, sized to one ~100K-token agent session:

```markdown
---
id: 0001
title: <ticket title>
type: research | prototype | grilling | task
status: open | claimed | closed
claimed_by: <session/dev name, once claimed>
blocked_by: [0002, 0005]   # ids of tickets that must close first
---

## Question

<the decision or investigation this ticket resolves>

## Answer

<!-- empty until resolved; filled on close -->
```

A session **claims** a ticket by setting `status: claimed` + `claimed_by:` **first**,
before any work, so concurrent sessions skip it. A ticket is **unblocked** when every id in
its `blocked_by` is closed; the **frontier** is the open, unblocked, unclaimed tickets — the
edge of the known. Assets created while resolving a ticket are linked from the ticket file,
not pasted in.

## Ticket Types

Every ticket is either **HITL** — human in the loop, worked *with* a human who speaks for
themselves — or **AFK**, driven by the agent alone. A HITL ticket only resolves through that
live exchange; the agent never stands in for the human's side of it (a grilling agent that
answers its own questions has broken this).

- **Research** (AFK): Reading documentation, third-party APIs, or local resources like
  knowledge bases. Creates a markdown summary as a linked asset. Use when knowledge outside
  the current working directory is required.
- **Prototype** (HITL): Raise the fidelity of the discussion by making a cheap, rough,
  concrete artifact to react to — an outline, a rough take, a stub, or throwaway UI/logic
  code. Links the prototype as an asset. Use when "how should it look" or "how should it
  behave" is the key question.
- **Grilling** (HITL): Conversation via the `grilling` and `decision-mapping` skills, one
  question at a time. The default case.
- **Task** (HITL or AFK): Manual work that must happen before a *decision* can be made —
  nothing to decide, prototype, or research, but the discussion is blocked until it's done.
  Signing up for a service so its API can be judged, provisioning access, moving data so its
  shape can be seen. This is the one type that *does* rather than decides — and it earns its
  place by unblocking a decision, not by delivering the destination. The agent drives it
  alone where it can (AFK); otherwise it hands the human a precise checklist (HITL). Resolved
  when the work is done; the answer records what was done and any resulting facts (credentials
  location, new URLs, row counts) later tickets depend on.

## Fog of war

The map is _deliberately_ incomplete: don't chart what you can't yet see. Beyond the live
tickets lies the **fog of war** — the dim view of decisions and investigations you can tell
are coming but can't yet pin down, because they hang on questions still open. Resolving a
ticket clears the fog ahead of it, graduating whatever's now specifiable into fresh tickets —
one at a time, until the way to the destination is clear and no tickets remain.

The map's **Not yet specified** section is where that dim view is written down: the suspected
question, the area to revisit later. It's the undiscovered frontier _toward_ the destination —
everything here is in scope, just not sharp enough to ticket. Write as loosely or as fully as
the view allows; it doubles as a signpost for collaborators reading where the effort is headed.

**Fog or ticket?** The test is whether you can state the question precisely now — _not_
whether you can answer it now.

- **Ticket when** the question is already sharp — even if it's blocked and you can't act on it yet.
- **Not yet specified when** you can't yet phrase it that sharply. Don't pre-slice the fog into
  ticket-sized pieces: it's coarser than a ticket, and one patch may graduate into several
  tickets, or none, once the frontier reaches it.

**Not yet specified** excludes what's already decided (Decisions so far), what's already a live
ticket, and what's out of scope (the next section).

## Out of scope

Fog only ever gathers _toward_ the destination. The destination fixes the scope, so work beyond
it is **out of scope** — it isn't fog, and it doesn't belong in **Not yet specified**. It gets
its own **Out of scope** section on the map: work you've consciously ruled out of _this_ effort.
Scope, not sharpness, lands it here.

Out-of-scope work never graduates — the frontier stops at the destination — so it returns only
if the destination is redrawn, and then as a fresh effort, not a resumption.

When a ticket that already exists turns out to sit past the destination — mis-scoped in while
charting, or exposed by a resolution — **close it** (a closed ticket is unambiguously off the
frontier) and leave one line in the **Out of scope** section: the gist plus why it's out of
scope, linking the closed ticket. It stays out of **Decisions so far**, which records the route
actually walked — a scope boundary isn't a step on it.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session** (pairs with
`splitting-sessions` — one ticket is one session's work).

### Chart the map

User invokes with a loose idea.

1. **Name the destination.** Run a `grilling` + `decision-mapping` session to pin down what
   this map is finding its way to — the spec, decision, or change. The destination fixes the
   scope, so it's settled first.
2. **Map the frontier.** Grill again, **breadth-first** this time: fan out across the whole
   space rather than deep on any one thread, surfacing the open decisions and the first steps
   takeable now. **If this surfaces no fog** — the way to the destination is already clear, the
   whole journey small enough for one session — you don't need a map. Stop and ask the user how
   they'd like to proceed.
3. **Create the map** (`wayfinder/map.md`): Destination and Notes filled in, Decisions-so-far
   empty, the fog sketched into **Not yet specified**.
4. **Create the tickets you can specify now** as files under `wayfinder/tickets/` — then wire
   `blocked_by` edges in a **second pass** (tickets need ids before they can reference each
   other). Wiring sorts them into the frontier and the blocked; everything you can't yet
   specify stays in the fog.
5. Stop — charting the map is one session's work; do not also resolve tickets.

### Work through the map

User invokes with a map (path). A ticket is **optional** — without one, you pick the next
decision, not the user.

1. Load the **map** — the low-res view, not every ticket body.
2. Choose the ticket. If the user named one, use it. Otherwise take the first frontier ticket
   in order. **Claim it**: set `status: claimed` + `claimed_by:` before any work.
3. Resolve it — **zoom as needed**: open the full body of any related or closed ticket on
   demand; invoke the skills the `## Notes` block names. If in doubt, use `grilling` +
   `decision-mapping`.
4. Record the resolution: write the answer into the ticket's `## Answer`, set `status: closed`,
   and **append a context pointer** to the map's Decisions-so-far.
5. Add newly-surfaced tickets (create-then-wire); graduate any fog the answer has made
   specifiable, clearing each graduated patch from **Not yet specified** so it lives only as its
   new ticket. If the answer reveals a ticket sits beyond the destination, **rule it out of
   scope** rather than resolving it on the route. If the decision invalidates other parts of the
   map, update or delete those tickets.

The user may run unblocked tickets in parallel, so expect other sessions to be editing the
tracker concurrently.

## Provenance

Adapted from Matt Pocock's `wayfinder` skill at **v1.1.0** (MIT, Copyright (c) 2026 Matt Pocock
— github.com/mattpocock/skills). The wayfinding frame, the map-as-index, the fog-of-war /
frontier model, the ticket-type taxonomy, and the one-ticket-per-session rule are his. The
Hermes adaptation defaults his pluggable issue tracker to a **local-markdown** `wayfinder/`
directory (his own documented fallback), and rewires his `/domain-modeling` / `/prototype`
references to Starbright's `decision-mapping`, `grilling`, and `handoff` skills.
