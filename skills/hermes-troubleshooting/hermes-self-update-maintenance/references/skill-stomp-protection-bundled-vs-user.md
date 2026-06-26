# Will an update stomp my skill edits? (bundled vs. user copies + hash-gated sync)

A recurring question on a git-installed Hermes: *"did you create this skill, or am
I at risk of an update overwriting my edits?"* Answer it from **source + the live
manifest**, never from memory — the protection is real but conditional, and the
*inverse* risk (silently pinned off upstream) is the part people miss.

Verified live 2026-06-07 against `tools/skills_sync.py` + the on-disk manifest.

## The two-copy model

A skill that ships with Hermes exists in **two places**:

| Copy | Path | Git-tracked? | Role |
|---|---|---|---|
| **Bundled** | `~/.hermes/hermes-agent/skills/<cat>/<name>/` | YES (in the repo checkout) | The seed/source. A `git pull`/checkout CAN change it. |
| **User** | `~/.hermes/skills/<cat>/<name>/` | NO (plain dir) | **What the agent actually loads at runtime.** Where your edits live. |

`SKILLS_DIR = HERMES_HOME / "skills"` (`tools/skills_sync.py:40`, `tools/skills_hub.py:50`).
The user dir is **not** inside the git checkout, so a repo pull cannot directly
overwrite it. The only thing that copies bundled→user is the **seeding/sync pass**,
and that pass is hash-gated.

## The hash-gated sync (why your edits survive)

On startup/update, `sync_skills()` reconciles bundled→user using a manifest of
`{skill_name: origin_hash}`. The decision table (from the module docstring, verified):

- **NEW** (not in manifest): copied to user dir, origin hash recorded.
- **EXISTING** (in manifest + present in user dir):
  - user copy hash **== origin hash** → you never touched it → **safe to update**
    from bundled if bundled changed; new origin hash recorded.
  - user copy hash **!= origin hash** → you customized it → **SKIP** (your copy is
    left alone).
- **DELETED by user** (in manifest, absent from user dir): **respected, not re-added.**
- **REMOVED from bundled** (in manifest, gone from repo): cleaned from manifest.

So: **the moment you edit a user skill, its dir hash diverges from the recorded
origin hash, and every future sync SKIPs it.** Durable, not one-shot — each new edit
re-diverges.

Manifest: `~/.hermes/skills/.bundled_manifest`, v2 format `name:hash` per line
(v1 plain-name lines auto-migrate). Hash is an MD5 over file contents +
relative paths (`_dir_hash()`).

Opt-out marker: `~/.hermes/skills/.no-bundled-skills` — if present, seeding is
disabled entirely (nothing bundled gets copied/updated). `hermes skills` has the
sync/opt-out controls (`set_bundled_skills_opt_out`, `remove_pristine_bundled_skills`).

## Verification recipe (prove protection, don't assume it)

Compute the user copy's hash the way the sync does and compare to the manifest:

```python
import sys, os; sys.path.insert(0, os.path.expanduser('~/.hermes/hermes-agent'))
from tools.skills_sync import _dir_hash, _read_manifest
from pathlib import Path
name = 'kanban-orchestrator'                      # the skill in question
user_dir = Path(os.path.expanduser(f'~/.hermes/skills/devops/{name}'))
cur = _dir_hash(user_dir)
origin = _read_manifest().get(name, '(absent)')
print('origin :', origin)
print('current:', cur)
print('PROTECTED (diverged → SKIP)' if cur != origin else 'AT RISK (matches → could be overwritten)')
```

`cur != origin` → user-modified → sync SKIPs it → **safe**. `(absent)` from manifest
→ it's a purely user-created skill the seeder never tracked → also safe (nothing to
copy over it).

Cross-check whether a skill is bundled at all:
- In manifest / has a twin under `~/.hermes/hermes-agent/skills/` → shipped skill you've
  forked.
- User-only (no bundled twin, not in manifest) → you authored it; zero stomp risk.
- `references/` files inside a skill dir aren't tracked separately — they ride with the
  skill dir's hash, so editing/adding one ALSO diverges the dir and protects the whole
  skill.

## The inverse risk people miss: a forked skill is PINNED off upstream

Protection cuts both ways. Once your user copy diverges, the sync skips it **forever**
— so it will **never** receive upstream improvements to that bundled skill. If Nous
ships a better `kanban-orchestrator`, your modified copy silently stays on your fork.

This is usually **fine and desired** for skills you've localized with machine-specific
verified facts (repo paths, base-branch names, profile rosters) — you *want* them
pinned. But name the tradeoff to the user: edits safe ✓, auto-upstream-inheritance off
✗. If they ever want to re-sync one to upstream, diff bundled↔user first
(`diff -r ~/.hermes/hermes-agent/skills/<path> ~/.hermes/skills/<path>`) so the local
facts aren't lost, then reset via the `hermes skills` sync/reset path.

## What NOT to conclude

- ❌ "I edited a skill, an update will overwrite it." Only if its hash still matches the
  manifest origin (i.e. you didn't really change the loaded copy). Verify before
  worrying.
- ❌ "It's git-tracked so a pull stomps it." The *bundled* copy is tracked; the *loaded*
  user copy isn't. The pull changes the seed, not your runtime skill — and the gated
  sync won't propagate it over your edits.
- ❌ Editing the bundled copy under `~/.hermes/hermes-agent/skills/` "to be safe." That's
  the one that git CAN overwrite, and it's not even the copy that loads. Always edit the
  **user** copy under `~/.hermes/skills/`.
