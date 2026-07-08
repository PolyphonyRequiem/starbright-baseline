---
name: writing-great-skills
description: Reference for authoring and editing skills well — the vocabulary and
  principles that make a skill predictable. Load when writing a new skill, reviewing an
  existing one, or deciding whether something should be model-invoked or user-invoked.
version: 1.1.0
author: Adapted by Starbright from Matt Pocock's writing-great-skills (MIT — github.com/mattpocock/skills)
license: MIT
metadata:
  hermes:
    tags: [skills, authoring, meta, reference, predictability]
    related_skills: [grilling]
---

# Writing Great Skills

A skill exists to wrangle determinism out of a stochastic system. **Predictability** — the
agent taking the same *process* every run (not producing the same *output*) — is the root
virtue. Every principle below serves it.

## Invocation: model-invoked vs user-invoked

Two choices, trading different costs:

- **Model-invoked** — keeps a `description`, so the agent can fire it autonomously and
  other skills can reach it. Cost: it sits in the context window every turn (**context
  load**). Use when the agent must reach the skill on its own. Write a rich trigger
  description ("Use when the user wants…, mentions…").
- **User-invoked** — set `disable-model-invocation: true`. Only a human typing its name
  invokes it; no context load, but it spends **cognitive load** (*you* are the index that
  must remember it exists). Use for skills that only ever fire by hand.

When user-invoked skills multiply past what you can remember, cure the piled-up cognitive
load with a **router skill**: one skill that names the others and when to reach for each.

## Writing the description

A model-invoked description does two jobs — state what the skill is, and list the
**branches** that trigger it. Every word adds context load, so prune hard:

- **Front-load the leading word** — the description is where invocation work happens.
- **One trigger per branch.** Synonyms renaming a single branch are duplication. Collapse
  them; keep only genuinely distinct triggers.
- **Cut identity that's already in the body.** Keep the description to triggers plus any
  "when another skill needs…" reach clause.

## Information hierarchy

A skill mixes two content types — **steps** and **reference** — ranked by how immediately
the agent needs them:

1. **In-skill step** — an ordered action in `SKILL.md`. Each ends on a **completion
   criterion**: a *checkable* condition (can the agent tell done from not-done?) that's
   *exhaustive* where it matters ("every modified file accounted for", not "produce a
   list"). Vague criteria invite premature completion.
2. **In-skill reference** — a definition/rule/fact consulted on demand. Often a flat
   peer-set (every rule on one rung) — a fine arrangement, not a smell.
3. **External reference** — pushed into a separate file (`references/*.md`), reached by a
   **context pointer**, loaded only when the pointer fires. Keeps `SKILL.md` lean.

A demanding completion criterion drives thorough **legwork** — the digging the agent does
within the work — whether the skill is steps or reference.

## Steering behaviour: prompt the positive

**Negation backfires.** Steering by prohibition names the very thing you're banning —
*don't think of an elephant* makes the elephant more available, not less. A skill that
says "don't be verbose" has just put verbosity in the agent's working memory. Prompt the
**positive**: state the target behaviour so the banned one is never spoken. Keep a
prohibition only as a hard guardrail you genuinely can't phrase positively — and even
then, pair it with what to do *instead* ("never fabricate output; report the blocker and
try another route").

## Provenance

Adapted from Matt Pocock's `writing-great-skills` at **v1.1.0** (MIT, Copyright (c) 2026
Matt Pocock — github.com/mattpocock/skills). The predictability-as-root-virtue framing, the
context-load/cognitive-load distinction, the router-skill cure, the information-hierarchy
ladder, and the v1.1.0 **Negation / prompt-the-positive** principle are his vocabulary,
lightly condensed and Hermes-adapted (his original links a `GLOSSARY.md`; the bolded terms
here are inlined). The Hermes `references/*.md` mechanics map onto his "external
reference" tier.
