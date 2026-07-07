---
name: profile-lineage
description: "Reference + tooling for profile ancestry and drift — the lineage.yaml DAG schema, the distribution.manifest hash baseline, drift detection without git, and merge-base (LCA) computation. Load when another profile-ops skill needs to record a fork edge, detect whether an installed profile has drifted from what it shipped, or find the merge base of two profiles."
version: 1.0.0
author: Starbright
license: MIT
metadata:
  hermes:
    tags: [hermes, profiles, distribution, lineage, drift, versioning, provenance]
    related_skills: [profile-refactor, profile-reconcile, profile-overload-watch, hermes-profile-sharing]
---

# Profile Lineage

The substrate for the profile-ops family: **where a distribution profile came
from** (ancestry) and **whether its shipped files have changed** (drift). The
sibling skills — `profile-refactor`, `profile-reconcile`, `profile-overload-watch`
— all read and write through the tooling here. This skill is mostly reference +
a script library; the workflows live in the siblings.

## The problem it solves

A Hermes *distribution* profile (one with `distribution.yaml`, installed via
`hermes profile install <git-url>`) can be forked, split, joined, and
repurposed. Three questions have to stay answerable across all of that:

1. **Where did this profile come from?** — its parent(s), the version/commit it
   was cut from, and the full ancestry chain. → `lineage.yaml`
2. **Has it drifted from what the distribution shipped?** — which
   distribution-owned files were edited locally. The installer **strips `.git`**,
   so `git diff` is not available on an installed profile. → `distribution.manifest`
3. **What is the merge base of two profiles?** — needed to 3-way merge a join or
   a drift-aware update. → LCA over the lineage DAG

## 🔴 The shipped-vs-local boundary (why this is safe)

Everything here operates **only** on distribution-owned files. User-local state
— `config.yaml`, `.env`, `auth.json`, `memories/`, `sessions/`, `logs/`, and
`lineage.yaml` itself — is **never** hashed, never part of drift, never merged.
That boundary is enforced in `scripts/lineage.py` (`USER_OWNED`) and mirrors the
installer's own exclude set. This is what keeps "track the distribution" from
ever touching "the user's private settings." (Same principle the
`hermes-profile-sharing` skill enforces from the privacy side.)

## lineage.yaml — the ancestry DAG

Per-profile identity metadata. `parents` are the immediate edges (**the source
of truth**); `ancestry` is a cached closure snapshot (convenience that may lag —
recompute from edges when a definitive answer is needed and the ancestor
profiles are reachable). Schema v2 supports **multiple parents** (a join is a
merge of 2+ lineages), so this is a DAG, not a tree.

```yaml
schema: 2                         # v2 = DAG (multi-parent); v1 was a tree
this: starbright-research         # this profile's distribution name
event: fork                       # fork | split | join | repurpose | root
event_reason: "specialize for paper/research work"
parents:                          # 1..N immediate edges
  - name: starbright-baseline
    source: https://github.com/PolyphonyRequiem/starbright-baseline.git
    version: "1.0.0"
    sha: 915176a                  # exact commit this fork was cut from
    at: 2026-07-07
    reason: "companion posture + hermes craft"
roots: [starbright-baseline]      # no-parent ancestors (usually one)
ancestry: [starbright-baseline]   # cached closure, root -> parent (this excluded)
```

`event` values: **fork** (one parent, specialize), **split** (a heavy profile
divided into children — each child records the split parent), **join** (2+
parents merged), **repurpose** (same lineage, redirected mission), **root** (no
parents — the baseline itself).

## distribution.manifest — the drift baseline

One `path:sha256` line per distribution-owned file, sorted. Mirrors Hermes'
own `.bundled_manifest` convention exactly. Written at install/fork time;
compared against the live tree to detect drift. The rightmost `:` splits path
from digest (paths never contain a colon).

```
SOUL.md:9f2c...
skills/companion/companion-presence/SKILL.md:4a71...
```

## Scripts

Run with `python3` (POSIX) or `python` (Windows git-bash, where `python3` is a
broken Store shim). All CLIs print JSON and use exit codes so bash can gate on
them. PyYAML is the only non-stdlib dependency (a Hermes hard dep).

### `scripts/lineage.py`
| Command | What it does | Exit |
|---------|-------------|------|
| `manifest-gen <profile_dir>` | write `distribution.manifest` for the tree | 0 |
| `drift <profile_dir>` | report modified/added/removed vs manifest | 0 clean / 1 drift |
| `show <profile_dir>` | print the profile's `lineage.yaml` as JSON | 0 / 1 if none |
| `lca <A> <B> ...` | merge-base + shared ancestors of 2+ profiles/lineage files | 0 |
| `record-fork <child_dir> --name N --event E --parent P [--parent-source ...]` | create/extend the child's `lineage.yaml` with one edge | 0 |

Importable as a library too: `Lineage`, `ParentEdge`, `compute_manifest`,
`compute_drift`, `record_edge` (pass `into=<Lineage>` to chain multiple parents
for a join), `merge_base`, `lowest_common_ancestors`.

### `scripts/reconcile.py`
`classify --base B/ --ours O/ --theirs T/` (dirs, auto-hashed) **or**
`--base-manifest / --ours-manifest / --theirs-manifest` (pre-computed). Emits
`{auto: {path: resolution}, conflicts: [...], summary: {...}}`. Exit 0 when
zero conflicts, 1 when true conflicts remain. This is the engine behind
`profile-reconcile`.

### `scripts/check-drift.sh`
Bash wrapper for the common "did I edit anything the distribution ships?"
question — works without `.git`. `check-drift.sh <profile_dir>` reports drift
(exit 1 if drifted); `check-drift.sh --regen <profile_dir>` rewrites the
baseline. Handles the git-bash POSIX-path-vs-native-Windows-Python gotcha via
`cygpath`.

## Wiring lineage into a distribution (author-side)

`lineage.yaml` and `distribution.manifest` are ordinary files the installer
copies verbatim (they are not user-owned, so they travel; they are not parsed
by the installer, so nothing is stripped). To make the installer treat them as
first-class distribution payload, list them under `distribution_owned:` in
`distribution.yaml` — a supported manifest field, no unknown-key hack needed.

⚠️ **Do not** try to put lineage inside `distribution.yaml` itself. The
installer round-trips that file through a fixed dataclass (`from_dict`/`to_dict`
in `hermes_cli/profile_distribution.py`) and **silently drops every unknown
key** on install/update. Verified against source — a `lineage:` block there
would vanish. Keep lineage in its own file.

## Completion criteria

- `manifest-gen` then `drift` on an untouched tree prints `"clean": true`.
- Editing any user-owned path (`config.yaml`, `memories/`, `.env`) leaves drift
  clean — only distribution-owned edits register.
- `lca` of two siblings forked from one baseline returns that baseline.
- `python3 scripts/test_lineage.py` is green (17 hermetic tests).

## Pitfalls

- **`git diff` on an installed profile won't work** — `.git` is stripped at
  install. Use `check-drift.sh` / the manifest, which is exactly why it exists.
- **`ancestry` can lag** — it's a cached closure. When correctness matters and
  the ancestor profiles are on disk, recompute from `parents` edges (which
  `record_edge` does automatically when `parent.source` is a reachable dir).
- **Merge base needs shared ancestry** — `merge_base` returns `None` for
  unrelated profiles; `profile-reconcile` must handle that (no common base → no
  3-way merge, fall back to manual).
- **POSIX vs native paths on Windows** — pass native (`C:\...`) or repo-relative
  paths to the Python CLIs from git-bash; a bare `/c/...` MSYS path makes native
  Python look for `C:\c\...`.
