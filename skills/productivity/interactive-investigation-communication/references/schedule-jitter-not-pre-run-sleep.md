# Schedule-time jitter, not pre-run sleep

Confirmed 2026-05-28 while debugging evening check-in cron timing.

## What went wrong

A cron pre-run script (`random_delay.py`) attempted to implement random delivery time by sleeping for a random duration before the actual job prompt ran.

Two separate problems emerged:

1. **Hermes cron pre-run scripts have a 120s hard timeout.**
   - A script sleeping up to 30 minutes (`time.sleep(random.randint(0, 1800))`) will almost always time out.
   - This surfaced as `Script timed out after 120s` in the cron run context.

2. **Even if the timeout were raised, pre-run sleep is the wrong architecture.**
   - Cron delays are blocking.
   - Sleeping inside a pre-run script stalls the scheduler tick / job execution path instead of simply changing when the job is scheduled to fire.

## Durable lesson

For cron randomness, the right abstraction is **schedule jitter**, not sleep.

Meaning:
- keep the job itself immediate when its tick starts
- randomize `next_run_at` / the fire time in the scheduler
- never implement timing variation by `sleep()` inside a pre-run script

## Practical operator rule

If you want a job to arrive at a variable time:
- **preferred:** add scheduler-level jitter (future feature / implementation path)
- **acceptable fallback:** multiple fixed cron jobs at staggered times, selected by some deterministic rule
- **avoid:** `time.sleep()` in cron scripts

## Design sketch for future scheduler work

A clean model would be something like:

- `schedule: 30 20 * * *`
- `schedule_jitter: 30m`
- scheduler computes a randomized `next_run_at` in `[base, base + jitter]`
- `cron list` shows the actual jittered `next_run_at`

This avoids blocking and makes the randomness visible and debuggable.

## Why save this

This is not just a one-off script bug. It is a class-level cron design lesson:
**timing variation belongs in scheduling, not in task startup.**
