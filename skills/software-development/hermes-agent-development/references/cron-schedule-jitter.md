# Cron Schedule Jitter for Durable Randomized Jobs

Use this when adding "durable but somewhat random" timing to Hermes cron jobs.

## Why this exists

Cron jobs already persist in `~/.hermes/cron/jobs.json` with durable `next_run_at` state. For randomized recurring timing, do **not** add a second registry and do **not** sleep inside pre-run scripts.

The right shape is:
- keep the existing cron registry
- extend the stored `schedule` dict with jitter metadata
- compute a concrete randomized `next_run_at`
- persist that timestamp so restarts do not re-roll randomness for the same occurrence

## Implemented shape

Supported schedule forms:
- `every 2h jitter 30m`
- `0 9 * * * with jitter 30m`

Stored schedule metadata:
- recurring interval jobs: `{"kind": "interval", "minutes": 120, "jitter_minutes": 30, ...}`
- recurring cron jobs: `{"kind": "cron", "expr": "0 9 * * *", "jitter_minutes": 30, ...}`

Display form should stay user-readable, e.g.:
- `every 120m (jitter +0-30m)`
- `0 9 * * * (jitter +0-30m)`

## Rules

- Jitter is for **recurring** schedules only.
- Reject jitter on one-shot schedules (`30m`, ISO timestamps).
- Jitter is **one-sided forward** (`+0..N`) rather than symmetric around the base schedule.
- Roll the random offset only when computing the next fire time.
- Persist the resulting `next_run_at` so scheduler ticks and restarts stay deterministic for that already-scheduled occurrence.

## Implementation notes

1. Parse an optional trailing jitter clause from the schedule string before normal schedule parsing.
2. Keep the durable registry unchanged; add `jitter_minutes` to the schedule dict.
3. Apply jitter inside `compute_next_run(...)`, not inside `run_job(...)` and not in a pre-run script.
4. Reuse the existing `next_run_at` persistence path so the scheduler remains restart-safe.
5. Keep `advance_next_run(...)` and `mark_job_run(...)` using the same next-run calculator so recurring jobs continue to get at-most-once semantics.

## Pitfalls

- Do **not** swallow the "jitter not allowed on one-shot schedules" error inside a broad duration-parser `except ValueError:` block. Parse the duration first, then raise the jitter-specific validation error outside the fallback catch.
- Do **not** recompute jitter every tick for the same scheduled occurrence.
- Do **not** create a parallel random-job registry unless you actually need a separate parent/child materialization model.

## Verification

Add focused tests for:
- interval jitter parsing
- cron jitter parsing
- rejection on one-shot schedules
- `compute_next_run()` applying jitter deterministically under a mocked RNG
- CLI/tool output showing the jittered display string
