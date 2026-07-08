---
name: loop-me
description: Grill me about specs for the workflows I want to build, within this workspace.
version: 1.1.0
author: Adapted by Starbright from Matt Pocock's loop-me (MIT — github.com/mattpocock/skills)
license: MIT
disable-model-invocation: true
argument-hint: "A workflow to design, or nothing to go find one"
metadata:
  hermes:
    tags: [workflows, automation, grilling, specs, delegation, productivity]
    related_skills: [grilling, handoff, writing-great-skills]
---

# Loop Me

Run a stateful grilling session whose only output is **workflow** specs. Use the
`grilling` discipline — relentless, one question at a time, a recommended answer attached
to each — aimed at the vocabulary and goal below. Create, edit, and delete specs as the
grilling resolves things.

This is **user-invoked**: the human runs it by name when they want to design the
automations in their life. Load the `grilling` skill first — it supplies the interview
discipline this skill runs on.

## The loop lens

A **loop** is a recurring pattern in the user's life: their career, their week, their
morning, a single repeated activity. Picturing a life as loops within loops reveals how
predictable its activities really are — which is what makes them worth **delegating**. Use
the lens to find loops worth specifying, and propose ones the user hasn't noticed.

A **workflow** is the spec of one loop, made real. You run a workflow on a loop — the loop
is its running instantiation. Workflows live in `workflows/*.md` and are the source of
truth.

## Vocabulary

A shared language, reached for only when a workflow calls for it — never a checklist.
**Mandate nothing structural**: a workflow needs no AI, no checkpoint, and no schedule
unless the grilling shows it does.

- **Trigger** — what fires each run: an **event** (a new email, a new issue) or a
  **schedule** (every morning). Event-triggering is usually the more efficient. In Hermes
  these map to real mechanisms — a `webhook` subscription or a `cronjob` — but don't reach
  for them until the spec earns it.
- **Checkpoint** — a human-in-the-loop point where the user is asked to verify or decide.
  Some workflows have none and run autonomously; some use no AI at all.
- **Push right** — defer the checkpoint as far as it will go. Do maximal work before
  involving the human, so they are asked once, late, with everything prepared.
- **Brief** — what a checkpoint presents: a tight, decision-ready summary — what was
  produced, why, and a link down to the asset itself — never the raw output. The user
  reads a brief, not a draft. Speed of review is imperative.

## Definition of done

A workflow spec is done when an implementer agent could build it without asking a single
question. Grill until then; nothing is done while a question remains. (When a spec is
ready to build, hand off via the `handoff` skill.)

## The workspace

- `workflows/*.md` — one spec per workflow.
- `NOTES.md` — raw notes on the user's world: the tools they use, the channels they
  process, and their own terminology for both. When it is empty or thin, interview them
  about their world before specifying anything. Sharpen fuzzy terms into canonical ones as
  they surface, and record them here.

## Provenance

Adapted from Matt Pocock's `loop-me` skill at **v1.1.0** (MIT, Copyright (c) 2026 Matt
Pocock — github.com/mattpocock/skills), near-verbatim — the loop/workflow lens, the
push-right vocabulary, and the "done when an implementer could build it blind" bar are his.
The Hermes adaptation names the real trigger mechanisms (`webhook` / `cronjob`) and wires
the `grilling` and `handoff` skills as the interview and hand-off surfaces.
