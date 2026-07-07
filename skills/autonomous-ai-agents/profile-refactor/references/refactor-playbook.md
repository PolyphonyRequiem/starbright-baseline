# Refactor Playbook — exact command sequences

Load when executing a `profile-refactor` operation. Assumes the `profile-lineage`
scripts are reachable; adjust `$LINEAGE` to their real path. Use `python3` on
POSIX, `python` on Windows git-bash. `$H` = the Hermes profiles dir
(`~/.hermes/profiles` or, on this host, `~/AppData/Local/hermes/profiles`).

```bash
LINEAGE="$H/<active-profile>/skills/autonomous-ai-agents/profile-lineage/scripts/lineage.py"
```

## Common invariants (all operations)

For every **new child** profile:

```bash
# 1. clean config so it can't inherit the global config's personal settings
hermes -p <child> config set model.provider <provider>
hermes -p <child> config set model.default  <model>

# 2. record lineage — one call per parent edge
python "$LINEAGE" record-fork "$H/<child>" \
  --name <child> --event <fork|split|join|repurpose> \
  --event-reason "<why>" \
  --parent <parent-name> \
  --parent-source <git-url-or-local-dir> \
  --parent-version <ver> \
  --parent-sha "$(git -C <parent-repo> rev-parse --short HEAD)" \
  --reason "<what this parent contributes>"

# 3. regenerate the drift baseline from the child's final file set
python "$LINEAGE" manifest-gen "$H/<child>"
```

Never touch a child's or parent's `memories/`, `.env`, `auth.json`. Only
distribution-owned files (SOUL.md, skills/, cron/, mcp.json) move.

## FORK — one parent → one specialized child

```bash
# fresh child (build UP): create clean, then add the parent's craft minus drops
hermes profile create <child> --no-skills
# copy only the skills the specialist keeps:
cp -r "$H/<parent>/skills/<kept-cluster>" "$H/<child>/skills/<...>"
# write a focused SOUL (edit down from parent's, or fresh)
$EDITOR "$H/<child>/SOUL.md"
# then the common invariants (clean config, record-fork event=fork, manifest-gen)
```

## SPLIT — one heavy parent → N focused children

Find the seams first (use `profile-overload-watch`'s taxonomy). Then, per child:

```bash
for child in <childA> <childB>; do
  hermes profile create "$child" --no-skills
  # move THIS child's cluster only
  cp -r "$H/<parent>/skills/<cluster-for-$child>" "$H/$child/skills/"
  # focused SOUL per child
  # common invariants, event=split, --parent <parent>
done
```

Decide with the user whether the parent survives as a slimmed core or is retired.
If retired, the children carry its lineage forward via their `split` edges — do
not delete the parent until the children are verified.

## JOIN — 2+ parents → one merged profile

A join is a 3-way merge; defer conflicts to `profile-reconcile`.

```bash
# 1. find the merge base
python "$LINEAGE" lca "$H/<parentA>" "$H/<parentB>"   # -> merge_base

# 2. classify what each parent changed vs the base
RECON="$(dirname "$LINEAGE")/reconcile.py"
python "$RECON" classify \
  --base "$H/<merge_base>" --ours "$H/<parentA>" --theirs "$H/<parentB>"
# exit 0 = no conflicts (auto-merge safe); exit 1 = true conflicts -> profile-reconcile

# 3. create the joined child, apply auto-resolved files, then run profile-reconcile
#    for each true conflict (agent proposes, user confirms — one at a time).

# 4. record BOTH parents (chain the edges):
python "$LINEAGE" record-fork "$H/<child>" --name <child> --event join \
  --event-reason "unify" --parent <parentA> --parent-source <...> --parent-sha <...>
python "$LINEAGE" record-fork "$H/<child>" --name <child> --event join \
  --parent <parentB> --parent-source <...> --parent-sha <...>
# (the CLI upserts the second parent onto the existing lineage.yaml)

python "$LINEAGE" manifest-gen "$H/<child>"
```

## REPURPOSE — same profile → new mission

No new profile dir; the profile keeps its identity but redirects. Record the
prior self as parent so the pivot is traceable.

```bash
# capture the pre-repurpose SHA if the profile is a git distribution
OLD_SHA="$(git -C "$H/<profile>" rev-parse --short HEAD 2>/dev/null || echo local)"
# reshape skills/SOUL for the new mission (add/remove clusters, rewrite SOUL)
# record the pivot:
python "$LINEAGE" record-fork "$H/<profile>" --name <profile> --event repurpose \
  --event-reason "<old mission> -> <new mission>" \
  --parent <profile> --parent-version <old-ver> --parent-sha "$OLD_SHA" \
  --reason "prior mission"
python "$LINEAGE" manifest-gen "$H/<profile>"
```

## Verify (every operation)

```bash
python "$LINEAGE" show "$H/<child>"          # lineage correct?
python "$LINEAGE" drift "$H/<child>"          # baseline clean right after build?
# for splits/forks from a shared parent:
python "$LINEAGE" lca "$H/<childA>" "$H/<childB>"   # -> the shared parent
```

The user should be able to state each resulting profile's mission in one
sentence. If they can't, the seam was wrong — revisit the grill.
