---
name: profile-overload-watch
description: "Use when a profile is accumulating many domains, roles, or skills and may be getting too heavy — when the user adds a skill/MCP/domain unrelated to the profile's core mission, mentions the agent feeling 'dumb'/slow/unfocused/spread thin, or asks whether a profile is doing too much. Watches for capability sprawl and, when the signals cross, proposes a SPECIFIC split along the natural seam and offers to run profile-refactor."
version: 1.0.0
author: Starbright
license: MIT
metadata:
  hermes:
    tags: [hermes, profiles, overload, sprawl, split, context, focus]
    related_skills: [profile-refactor, profile-lineage, writing-great-skills, grilling]
---

# Profile Overload Watch

Notice when a profile is becoming a junk drawer — carrying many unrelated
domains, roles, and responsibilities — and propose a **specific** split before
the sprawl taxes every session. This is the *automatic-suggestion* half of the
profile-ops family; the *guided execution* half is `profile-refactor`.

## Why this exists

Every skill's `description`, every MCP server's tool schemas, and the SOUL all
load into context **on every turn**. A profile that has quietly absorbed five
domains pays that tax constantly, gets less focused, and "feels dumb." The cure
is a split — but splits are only worth proposing when there's a *real seam*, and
only worth acting on when the user wants it. This skill finds the seam and makes
the case; it never splits on its own.

## 🔴 The core discipline: taxonomy → classify → group → THEN suggest

Do **not** reduce "too heavy" to one threshold knob (skill count > N). Heaviness
is multi-signal, and a split is only justified when weight coincides with a
**natural seam** (a group of skills/domains that could stand alone). The
process is always:

1. **Enumerate the heaviness signals** present in this profile (the taxonomy).
2. **Classify** each carried capability by domain/role.
3. **Group** into candidate clusters and find the seam(s) between them.
4. **Only then** decide whether to suggest — and if so, name the *specific*
   split, not a vague "this is getting big."

The full signal taxonomy and how to weigh it:
`references/heaviness-taxonomy.md` (load it before scoring — don't score from
memory).

## When to raise it (trigger conditions)

Raise a split suggestion when **weight AND a seam** are both present:

- The user just added a skill / MCP server / domain that is **unrelated to the
  profile's stated mission** (the clearest trigger — a fresh seam just appeared).
- The user says the agent feels **slow, unfocused, "dumb," spread thin**, or
  that sessions feel noisy/heavy.
- Distinct **role clusters** have accumulated (e.g. a companion profile that has
  also become a devops profile and a research profile).
- The user asks directly whether a profile is doing too much.

Do **not** raise it for a profile that is heavy but *coherent* (many skills, one
domain — a deep specialist is fine) or on every small addition (nagging burns
trust). One well-timed, specific suggestion beats ten vague ones.

## How to make the suggestion

1. **Look, don't guess.** Read the profile's actual skills tree, `SOUL.md`, and
   MCP list. Cluster by domain. (Pairs with `profile-lineage` for the file
   layout.)
2. **Score against the taxonomy** in `references/heaviness-taxonomy.md` — note
   which signals fired, not just a number.
3. **Name the seam concretely.** "This profile carries companion + CloudVault
   devops + paper-writing. The devops cluster (6 skills, the EV2 MCP) is a clean
   seam — it shares nothing with the companion core." Show the actual clusters.
4. **Propose one specific split** with the child's proposed name, what moves,
   what stays, and the one-line win ("your everyday companion sessions stop
   paying for the EV2 tool schemas").
5. **Offer, don't impose.** "Want me to walk through the split?" If yes → hand
   off to `profile-refactor` (which does the grilling + the actual move +
   lineage). If no → drop it; don't re-raise the same seam next turn.

## Completion criterion

A *checkable* handoff: either (a) you named a specific seam + proposed split and
the user declined (done — do not re-nag), or (b) they accepted and you invoked
`profile-refactor` with the identified seam as its starting point. A vague "you
might want to split someday" is **not** a valid completion — either there's a
named seam worth acting on now, or there's nothing to raise.

## Pitfalls

- **Threshold-only thinking.** Skill count alone is not overload; a focused
  specialist with 40 skills is healthy. Weight must coincide with a seam.
- **Nagging.** Re-raising a declined split erodes trust. One suggestion per new
  seam; remember the decline.
- **Suggesting without a target.** "This is heavy" with no named split is noise.
  If you can't name the seam and the child, you haven't done step 1–3 — don't
  raise it yet.
- **Splitting coherence.** Don't cleave a single deep domain just because it's
  big. The seam has to be real — clusters that genuinely don't share context.
