---
name: grilling
description: Use when the user is brainstorming, bouncing ideas around, or wants to
  stress-test a plan or design before building. Interview them relentlessly — one
  question at a time — until you reach genuine shared understanding.
version: 1.0.0
author: Adapted by Starbright from Matt Pocock's grilling (MIT — github.com/mattpocock/skills)
license: MIT
metadata:
  hermes:
    tags: [grilling, alignment, planning, design, productivity]
    related_skills: [handoff]
---

# Grilling

Interview the user relentlessly about every aspect of a plan or design until you reach a
shared understanding. The most common failure mode in any build is *misalignment* — you
think you know what they want, you build it, and it's wrong. A grilling session closes
that gap before a line of code is written.

## When to use

- The user is brainstorming or bouncing ideas around (the trigger this skill exists for).
- They want to stress-test a plan before building.
- They use any "grill me" / "poke holes" / "interview me" phrasing.
- You're about to start non-trivial work and you're not certain you understand the goal.

## How to grill

1. **Walk the design tree branch by branch.** Resolve dependencies between decisions one
   at a time — earlier answers constrain later questions.

2. **One question at a time. Wait for the answer before the next.** Asking several
   questions at once is bewildering and produces shallow answers. This is the single most
   important rule, and the easiest to break.

3. **For each question, give your recommended answer.** Don't just interrogate — propose.
   The user reacts faster to "I'd do X because Y — agree?" than to an open-ended prompt.

4. **If a question can be answered by looking, look — don't ask.** Explore the codebase,
   grep the docs/corpus, search past sessions. Never make the user repeat what's already
   written down. (Pairs with `docs-before-reasoning`.)

5. **Stop when alignment is real**, not when you run out of questions. The exit condition
   is shared understanding — then hand off to a plan, a PRD, or the build itself.

## Provenance

Adapted from Matt Pocock's `grilling` skill (MIT, Copyright (c) 2026 Matt Pocock —
github.com/mattpocock/skills), near-verbatim — the one-question-at-a-time discipline and
the recommend-an-answer mechanic are his. The brainstorming trigger framing and the
look-don't-ask / docs-before-reasoning tie-in are our adaptation.
