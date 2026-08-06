# Map: A way of work for the Starbright system

**Status:** charting complete, unwalked. Charted 2026-08-06.

## Destination

A **working method** for designing and evolving the Starbright system — how we decide what
to build next, how we build it, how we know it worked, and how the method itself gets
revised. Bootstrapped by using it: the first thing the method builds is a real slice of the
system.

The destination is the method. The system is its byproduct.

**Override on `wayfinder`'s plan-don't-do default:** this map carries execution. A ticket may
land working artifacts, not only decisions — a method you cannot live in cannot tell you
whether the flow is right.

## Notes

**Domain.** A personal AI engineering, learning, discovery, and operations system built on
Hermes Agent, with Herdr and Conductor as existing machinery. `hyperbright` (VR) is a
separate effort that will consume this system through channels. **Channels are out of scope
here.**

**Skills every session should consult:** `wayfinder`, `grilling`, `decision-mapping`,
`decision-map-ticket-resolution`, `kiss`, `skill-library-curation`, `conductor-in-herdr`.

**Research.** [`wayfinder/research/`](research/) holds three cited, evidence-graded notes.
Cite them by grade; never average contested findings. Read the README's reading rules first.

**Standing preference.** Chat-shaped output. Lead with the actionable thing. Draft PRs
mid-flight, not only at the end.

## Pillars

Settled by grilling on 2026-08-06. These constrain every ticket. A ticket may **overturn** a
pillar with evidence — say so explicitly if you do.

1. **No home surface.** State lives in the system, not in whichever window you used. Herdr,
   VR, and this chat are windows onto one system. A window is *attended* or *autonomous*.
2. **Landed or improvised.** Behavior comes from a versioned artifact Daniel approved, or
   from stock Hermes. Anything invented mid-session is a proposal that works once. **Root is
   the floor and falling back to it is normal, not failure.**
3. **Budgeted distribution.** Landing an artifact displaces one. The skill listing has a
   context budget that evicts least-used entries silently; this profile is at ~95 skills,
   past where triggering degrades. A promotion pipeline that only adds is harmful.
4. **Tiered by shareability.** Every artifact declares a tier: **core** (both installs),
   **work-only**, **personal-only**. The tier is a property of the artifact, not the install.
   **Memory never crosses installs.**

**The eval gate.** Daniel is the evaluation channel the system cannot edit. An artifact lands
only after he has observed it fire in real work, once. Chosen deliberately over a mechanical
gate: optimizing against a self-owned monitor produces obfuscated reward hacking
([2503.11926](research/personal-self-evolving-agent-systems.md)), and he is the only observer
spanning both installs.

## Decisions so far

<!-- one line per closed ticket: gist + link. Detail lives in the ticket. -->

_None yet — the map is charted but unwalked._

## Not yet specified

In-scope fog. Graduates into tickets as the frontier advances.

- **Learning and discovery.** The destination names them; every chartable ticket so far is
  engineering and operations. What does the system do for learning that a chat does not?
- **Attention accounting.** The unit of value is accepted durable outcomes per unit of human
  attention. Nothing yet measures either term.
- **The rationale gap.** Skills capture instructions, not rejected alternatives. Where do
  decisions and their discarded options live so they survive the session?
- **Multi-window concurrency.** Two windows acting on one system at once — what arbitrates?
- **How the method revises itself.** The map's own retrospective loop.
- **Trust rules over per-item approval.** Evidence favors authoring conditional delegation
  rules; unclear what a rule looks like here or how it is expressed.

## Out of scope

- **Channels** — the protocol between hyperbright/VR and this system. Deferred by Daniel at
  the outset. This map specifies the system a channel would talk to, not the channel.
- **hyperbright itself** — the VR surface is a separate effort with its own profile.
