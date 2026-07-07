---
name: profile-refactor
description: "Guided split, join, fork, or repurpose of a Hermes distribution profile, with ancestry tracking. User-invoked: the human runs it by name when they want to reshape their profile fleet."
version: 1.0.0
author: Starbright
license: MIT
disable-model-invocation: true
metadata:
  hermes:
    tags: [hermes, profiles, refactor, split, join, fork, repurpose, lineage]
    related_skills: [profile-lineage, profile-reconcile, profile-overload-watch, grilling, hermes-profile-sharing]
---

# Profile Refactor

Reshape a profile fleet deliberately: **split** a heavy profile into focused
children, **fork** a specialist off a baseline, **join** two profiles into one,
or **repurpose** a profile onto a new mission — always recording ancestry so the
lineage stays traceable. This is the *guided-execution* half of the profile-ops
family; the *automatic-suggestion* half is `profile-overload-watch`.

This skill is **user-invoked** (`disable-model-invocation: true`): it only runs
when a human types its name, or when `profile-overload-watch` hands off to it
with an identified seam. It never fires on its own.

## The four operations

| Op | Shape | Lineage event |
|----|-------|---------------|
| **fork** | one parent → one specialized child | `fork` (1 parent) |
| **split** | one heavy parent → N focused children | `split` (each child records the parent) |
| **join** | 2+ parents → one merged profile | `join` (N parents; uses `profile-reconcile`) |
| **repurpose** | same profile → new mission | `repurpose` (parent = its prior self) |

## 🔴 Grill before you cut

Every refactor starts with a grilling pass (load the `grilling` skill). A split
in the wrong place, or a join that clobbers a specialization, is expensive to
undo. Interview one question at a time, recommend an answer, and **stop when
alignment is real** — then execute. The decision tree to walk:

1. **Which operation?** (fork / split / join / repurpose) — usually obvious from
   the ask, but confirm.
2. **Where is the seam / what's the target?**
   - *split:* which clusters become which children? Name each child + its
     one-line mission + exactly which skills/MCP/SOUL-sections move. (Use
     `profile-overload-watch`'s taxonomy to find the seam if not already
     identified.)
   - *fork:* what does the child specialize in, and what does it drop from the
     parent?
   - *join:* which two profiles, and — critically — **what happens to conflicts**
     where both edited the same shipped file? (→ `profile-reconcile`)
   - *repurpose:* what's the new mission, and what carries vs. gets cleared?
3. **What's shared-vs-local?** Confirm the user understands that `config.yaml`,
   `.env`, and `memories/` are **per-profile and never move** — only
   distribution-owned content (SOUL, skills, cron, mcp.json) is reshaped. (See
   `profile-lineage`.)
4. **Names + provenance.** The child distribution name(s), and — if these become
   git-installable distributions — the repo/source for each.

## 🔴 Build fresh UP, don't scrub DOWN

Inherited from `hermes-profile-sharing` and it applies here too: to create a
child, **create clean and add the vetted parts**, don't clone-and-delete. A
split child starts from a fresh profile that receives only its cluster's skills +
a focused SOUL; a fork receives the parent's craft minus what it drops. Additive
is verifiable; subtractive misses things.

## Executing — the mechanics

Exact command sequences for each operation (create children, move
distribution-owned files, seed a clean `config.yaml` to dodge the inheritance
trap, and record lineage with `scripts/` from `profile-lineage`) live in
`references/refactor-playbook.md`. Load it when you execute. The invariants that
never change:

- **Record lineage on every child** via `profile-lineage`'s
  `lineage.py record-fork` — name, event, each parent edge (with the parent's
  source + version + the exact commit SHA it was cut from), and the reason.
- **Regenerate `distribution.manifest`** on every child after its files are in
  place (`lineage.py manifest-gen`) so future drift is measured from the right
  baseline.
- **Seed a clean `config.yaml`** into each new child (model/provider only) so it
  can't inherit the global config's personal settings.
- **Never touch** the parent's or child's `memories/`, `.env`, `auth.json`.
- **A join defers to `profile-reconcile`** for any file both parents changed —
  do not hand-merge shipped files.

## Completion criteria

- Each new child exists with: its moved skills, a focused SOUL, a clean
  `config.yaml`, a `lineage.yaml` recording its parent(s)+event+reason+SHA, and a
  fresh `distribution.manifest`.
- `lineage.py show <child>` reflects the true ancestry; `lca` of siblings
  returns the shared parent.
- For a join: `profile-reconcile` reported **zero unresolved conflicts** before
  the merged profile was finalized.
- The user can state each resulting profile's mission in one sentence (the split
  actually separated concerns).

## Pitfalls

- **Cutting before alignment.** Skipping the grill produces a split in the wrong
  seam. Grill first, every time.
- **Moving user data.** `memories/` / `.env` / `config.yaml` are per-profile.
  Reshaping them across profiles leaks or destroys personal state. Only
  distribution-owned files move.
- **Forgetting the SHA.** Record the parent's exact commit at fork time — it's
  what makes later drift/reconcile precise (the repo may have no tags).
- **Hand-merging a join.** Two parents that both edited `SOUL.md` is a real
  conflict; route it through `profile-reconcile`, don't eyeball it.
- **Lossy repurpose.** "Repurpose" still records the prior self as parent — don't
  silently erase where the profile came from.
