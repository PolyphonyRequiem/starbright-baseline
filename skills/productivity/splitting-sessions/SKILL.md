---
name: splitting-sessions
description: Use when one conversation has accumulated too many topics and tangents —
  several independent workstreams tangled in a single session. Helps the user decide
  whether to continue, compact, hand off, or SPLIT the session into focused threads, and
  assists the split. The decision layer above the handoff skill.
version: 1.0.0
author: Starbright (builds on Matt Pocock's handoff + fork-vs-continue model, MIT — github.com/mattpocock/skills)
license: MIT
metadata:
  hermes:
    tags: [session-management, context, splitting, tangents, productivity, router]
    related_skills: [handoff, decision-mapping, grilling]
---

# Splitting Sessions

A conversation drifts. It starts on one thing, then "while we're at it" pulls in a
second, an "oh, and" adds a third, and soon one session is carrying several unrelated
efforts at once. Each tangent is fine on its own — together they crowd each other out,
and every compaction makes it worse by summarising *all* of them lossily.

This skill is the **decision layer**: recognise the sprawl, pick the right tool, and — if
the answer is *split* — help the user fan the session into focused threads. It points at
`handoff` as its execution arm.

## When to use

Reach for this when you notice the signs of topic-multiplicity:

- You're tracking **3+ workstreams that share no dependency** — changing one wouldn't
  touch the others.
- The open-thread / TODO list spans **unrelated domains** (an image task, a config task, a
  writing task, all live at once).
- Linguistic drift markers pile up: *"also"*, *"while we're at it"*, *"oh and"*,
  *"tangent:"*, *"separate thing"*.
- Each open thread could be **handed to a different person with zero loss** — the tell
  that they were never one effort.
- Context has compacted and the summaries are getting **shallow per-topic** — compaction
  is now destroying detail because it's spread too thin.
- You catch yourself **re-reading to remember what's open**. Juggling is the signal.

## The decision: continue / compact / handoff / split / map

Don't reflexively compact. Match the tool to the actual problem:

| Situation | Tool | Why |
|---|---|---|
| One topic, still reasoning sharply | **continue** | No action needed. |
| One topic, long, a phase just finished | **`/compact`** (continue) | Summarise, keep going. *Only at phase breaks — compacting mid-phase loses the thread.* |
| One topic, want to fork off a deep sub-question | **`handoff`** (fork to one) | Preserve context, open a fresh window on the sub-question, return with the answer. |
| **Many INDEPENDENT topics tangled** | **SPLIT** (cluster into 2, at most 3) | Each cluster is its own effort; they pollute each other and every compaction. ← *this skill* |
| Many DEPENDENT questions, one effort | **`decision-mapping`** | They belong together; sequence them in one map, don't scatter. |

The load-bearing distinction (Matt Pocock's): **`/handoff` forks; `/compact` continues.**
This skill adds the third case — **split fans out** — and its core rule:

> **Don't compact a multi-topic session. Split it first.** Compaction is for length, not
> for multiplicity. A multi-topic compaction summarises every thread shallowly; splitting
> first gives each thread a clean window that only ever has to compact its own coherent
> content.

## How to split

1. **Enumerate.** Name every open thread explicitly — out loud, not from memory. The list
   itself usually makes the sprawl obvious.
2. **Cluster by dependency — aggressively, into 2 or at most 3.** Group threads that
   feed each other OR share a domain. The goal is NOT one session per topic (that just
   trades a juggling problem for a tab-explosion problem) — it's the smallest number of
   *coherent* sessions. Prefer two. Reach for three only when a cluster genuinely won't
   merge with either other. If you find yourself proposing four+, you're under-clustering
   — find the shared spine and combine. A loose affinity ("both are about the agent's
   inner life", "both are config plumbing") is enough glue to share one session.
3. **Choose the resident.** One cluster stays in *this* session — usually the live/hot one
   the user is most engaged with. The rest depart.
4. **Write a handoff per departing cluster.** Use the `handoff` skill — one doc each, in
   the OS temp dir, with a suggested-skills section. Reference shared artifacts by path;
   don't duplicate.
5. **Sequence if needed.** If two clusters have a soft dependency, note which to open
   first.
6. **Hand the partition back to the user.** Present it, let them adjust, open fresh
   sessions on their cue.

## Keep it an offer, not a mandate

This is **recommend-and-assist**, never auto-split:

- **Surface it once, lightly.** Noticing sprawl is an observation, not an alarm. Don't
  turn a casual session into a reorganisation sprint the user didn't ask for.
- **Propose a partition — don't just ask "how should we split this?"** Recommend a
  specific cut and let the user react. (Pairs with `grilling`: recommend an answer.)
- **One question at a time** if you need to clarify the cut.
- The user owns the call. If they'd rather keep juggling, that's a complete answer.

## Hermes specifics

- **Compaction lineage as a hard trigger.** In Hermes each compaction splits the session
  and chains it via `parent_session_id` (`end_reason='compression'`). Two or more
  compression-ancestors **plus** independent open threads = stop compacting, split. (A
  `pre_llm_call` hook can watch the lineage depth and load this skill when it crosses the
  threshold — the hook is the alarm; this skill is the decision.)
- **One fresh session per departing cluster.** Each handoff doc lives in the temp dir; the
  user opens a new session and references it.
- **Family:** `grilling` aligns within a thread → this skill separates threads →
  `handoff` writes each bridge → `decision-mapping` is the sibling for *dependent*
  questions that should stay together.

## Provenance

The fork-vs-continue model (`/handoff` forks, `/compact` continues) and the "smart zone"
idea — the window within which a model still reasons sharply — are **Matt Pocock's** (MIT,
Copyright (c) 2026 Matt Pocock, github.com/mattpocock/skills). The third case
(**split / fan-out-to-N**), the detection sensors, the "don't compact a multi-topic
session" thesis, and the Hermes compaction-lineage trigger are this skill's own
contribution.
