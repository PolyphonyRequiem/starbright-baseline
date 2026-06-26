# Clean worktree PR prep from a dirty Hermes checkout

Use this when the main `hermes-agent` checkout has unrelated local changes but you want a reviewable PR branch containing only one focused change.

## Workflow

1. In the dirty checkout, export a focused patch for only the intended files.
2. Create a fresh worktree from `origin/main` on a new branch.
3. Apply the focused patch in the clean worktree.
4. Inspect `git status` and `git diff` immediately — if upstream drift moved some files, `git apply` can partially fail.
5. Manually port any missing hunks into the clean worktree instead of falling back to the dirty checkout.
6. Run targeted tests from the clean worktree.
7. Commit from the clean worktree once the diff contains only the intended files.

## Windows / Hermes specifics

- Hermes worktrees on this host may not have their own `.venv/`.
- Keep the shell working directory on the worktree, but invoke the main checkout's dev interpreter directly, e.g.:

```bash
'/c/Users/danie/projects/hermes-agent/.venv/Scripts/python.exe' -m pytest tests/tools/test_cronjob_tools.py tests/hermes_cli/test_cron.py -o addopts= -q
```

This runs tests against the worktree code while reusing the existing dev environment.

## Pitfalls

- A successful `git worktree add` does **not** mean your exported patch applied cleanly.
- `git apply` may land some hunks and reject others after upstream drift; always verify the resulting diff before testing.
- Do not record missing GitHub auth, missing `gh`, or unset git identity as durable skill rules; those are environment state, not procedure.
