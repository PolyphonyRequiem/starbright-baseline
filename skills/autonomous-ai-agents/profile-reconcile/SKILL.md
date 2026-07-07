---
name: profile-reconcile
description: "Reconcile a profile against another lineage — merge two parents in a join, or pull an upstream distribution update into a locally-drifted fork — resolving true conflicts one at a time with the human. User-invoked."
version: 1.0.0
author: Starbright
license: MIT
disable-model-invocation: true
metadata:
  hermes:
    tags: [hermes, profiles, reconcile, merge, drift, update, conflicts, lineage]
    related_skills: [profile-lineage, profile-refactor, hermes-profile-sharing]
---

# Profile Reconcile

Three-way merge for distribution profiles. Two callers need it:

1. **Join** — `profile-refactor` merges 2+ parents into one profile; where both
   parents changed the same shipped file, that's a conflict to resolve.
2. **Drift-aware update** — you have a fork with local edits to
   distribution-owned files, and upstream shipped new changes. Pulling naively
   would clobber your edits (or vice-versa). Reconcile merges them.

Same engine for both: base + two sides → auto-resolve what only one side
touched, and bring the human in for **true conflicts** only. User-invoked
(`disable-model-invocation: true`) — it changes shipped files, so a human drives.

## The model (base / ours / theirs)

Every reconcile is a 3-way merge with a **merge base** — the common ancestor
both sides diverged from:

| Scenario | base | ours | theirs |
|----------|------|------|--------|
| Join (parentA + parentB) | their LCA (`lineage.py lca`) | parentA | parentB |
| Drift-aware update | the commit the fork was cut from (lineage `parent.sha`) | local fork | upstream |

If there's **no shared ancestry** (`lca` returns none), there's no 3-way merge —
tell the user and fall back to a manual, file-by-file decision. Don't fabricate
a base.

## 🔴 Never blind-pick a conflict

The whole point is that the machine does the safe 80% and the human decides the
risky 20%. `reconcile.py classify` splits every file into:

- **auto** — changed on only one side (or identically on both). Safe to apply
  mechanically: `ours-only`, `theirs-only`, `add-ours`, `add-theirs`,
  `unchanged`, `same-edit`.
- **conflicts** — both sides diverged differently (`edit-vs-edit`,
  `edit-vs-delete`, `add-both-differ`). **These go to the human, one at a time.**

Apply the auto set without ceremony. For each conflict, grill-style: show it,
propose a resolution with reasoning, wait for the decision. Never auto-pick a
true conflict, even when one side "looks obviously right."

## Workflow

1. **Establish the base.**
   ```bash
   LINEAGE=".../profile-lineage/scripts/lineage.py"
   RECON=".../profile-lineage/scripts/reconcile.py"
   python "$LINEAGE" lca "$H/<sideA>" "$H/<sideB>"   # join: -> merge_base
   # update: base = the fork's parent.sha checkout (fetch it into a temp dir)
   ```
2. **Classify.**
   ```bash
   python "$RECON" classify --base "$BASE" --ours "$OURS" --theirs "$THEIRS"
   # exit 0 = zero conflicts (apply auto set, done)
   # exit 1 = conflicts remain (resolve interactively)
   ```
3. **Apply the auto set** — copy each `auto` file from the side its resolution
   names (`ours-only`→ours, `theirs-only`/`add-theirs`→theirs, etc.) into the
   result profile.
4. **Resolve conflicts one at a time.** For each entry in `conflicts`:
   - Show the file, its `kind`, and the actual content of base/ours/theirs (diff
     them — the classifier gives you the hashes; read the files for the human).
   - **Propose a merge** with reasoning (often a genuine content merge, not a
     pick — e.g. two SOUL edits that can both land).
   - Wait for the user's decision. Apply it. Move to the next.
5. **Finalize.** Write the merged files, then via `profile-lineage`:
   `manifest-gen` the result (new drift baseline) and, for a join,
   `record-fork` both parents (event=join).
6. **Verify zero conflicts remain** — re-run `classify` against the merged
   result if useful; confirm `drift` is intentional.

## Completion criteria

- Every file classified; the **auto** set applied verbatim; **every** conflict
  resolved by an explicit human decision (none auto-picked).
- The merged profile has a fresh `distribution.manifest` and correct
  `lineage.yaml` (join: both parents recorded).
- For a drift-aware update: the user's intentional local edits survived (or were
  consciously dropped), and upstream's changes landed — verified by reading the
  merged files, not assumed.

## Pitfalls

- **No merge base.** Unrelated profiles have no LCA — `reconcile` can't 3-way
  them. Say so; go manual. Don't invent a base.
- **Auto-applying a conflict.** `edit-vs-edit` is never safe to pick blind, even
  when a side looks right. The classifier deliberately routes it to the human.
- **Losing local drift on update.** The reason drift-aware update exists is to
  protect the fork's edits. Confirm each `ours-only` survived; a plain
  `hermes profile update` would have overwritten them.
- **Merging user-owned files.** `reconcile.py` only sees distribution-owned
  files (config/.env/memories/lineage.yaml are excluded by `profile-lineage`).
  Never widen it to merge those — they're per-profile.
- **Skipping lineage on a join.** A merged profile with no `join` edges loses the
  fact that it has two parents. Record both.
