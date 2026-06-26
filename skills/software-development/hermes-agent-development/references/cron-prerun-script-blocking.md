# Cron Pre-Run Script Blocking — Why Jitter Belongs in the Scheduler

## The bug

Confirmed 2026-05-28 on `~/.hermes/scripts/random_delay.py` used as the
pre-run script for the `Starbright evening check-in` cron jobs:

```python
import random
import time
time.sleep(random.randint(0, 1800))   # 0-30 min random delay
```

Intent: have evening check-ins arrive at a different random minute each
night so the timing doesn't feel mechanical.

Effect: cron run for that job consistently reports

```
Script timed out after 120s: C:\Users\danie\.hermes\scripts\random_delay.py
```

…and (worse) the entire scheduler tick is held while the sleep runs,
because pre-run scripts execute inline before the agent for that job is
launched.

## Why pre-run scripts can't be a jitter mechanism

Two independent reasons, either of which is fatal:

1. **120-second hard timeout.** Anything over ~2 min always times out.
   For check-in jitter (intended 0-30 min spread), that means jitter is
   effectively *off* — most runs hit the cap, the timeout triggers,
   the script output is empty / errored, and the agent runs immediately
   anyway.
2. **The scheduler tick blocks.** Pre-run scripts run inline. While one
   pre-run script is sleeping, **every other job queued for the same
   tick is also waiting.** A 30-minute random sleep on one job is a
   30-minute delay on the entire scheduler. That is structurally wrong
   regardless of timeout limits.

Pre-run scripts are designed for **fast deterministic data collection**
whose stdout is injected as the agent's prompt context — HTTP probe,
config read, small computation, recent log scrape. Sleeping is the
opposite of what they're for.

## What "fix the script" looked like (and why it's still wrong)

Capping the sleep to 0-90s stays under the 120s timeout, so the script
itself stops erroring out — but the structural problem remains: every
job behind it on the same tick is still blocked for up to 90s. The
quick fix is a workaround, not a real solution.

The real fix is to **remove the pre-run script entirely** and move
jitter into the framework.

## The right shape: schedule-time jitter

Randomization belongs at `next_run_at` computation, not at job-run time.
When the scheduler computes when the job should next fire, add a
uniform-random offset:

```python
# pseudo, somewhere around cron/scheduler.py's next_run_at calculator
base_next = compute_cron_next(job.schedule, now)
jitter = job.schedule_jitter  # e.g. timedelta(minutes=30) — opt-in per job
if jitter:
    offset = timedelta(seconds=random.uniform(0, jitter.total_seconds()))
    job.next_run_at = base_next + offset
else:
    job.next_run_at = base_next
```

Properties of this shape:

- **Non-blocking.** The wait happens *between* ticks, not *inside* one.
  Nothing else is held up.
- **Visible.** `hermes cron list` shows the jittered `next_run_at`, so
  the user can see when the job will actually fire.
- **No timeout interaction.** The 120s pre-run cap is irrelevant
  because there is no pre-run script.
- **Composes with other pre-run scripts.** A job can still have a
  pre-run script for data collection AND have schedule jitter — they
  don't fight each other.

## Suggested design knobs (if implementing)

- `schedule_jitter: str | timedelta | None` per-job, opt-in.
- Direction: `+jitter only` (forward) is simpler and matches existing
  intent ("don't fire exactly on the hour"). `±jitter` around the base
  is a possible future extension.
- Global default: probably off; jitter is per-job intent, not a
  framework default.
- Serialization: keep the jittered `next_run_at` in `cron/jobs.json`
  so it survives gateway restarts.
- Display: show base schedule and effective `next_run_at` separately
  in `cron list`, e.g. `every 8:30pm (jitter +0-30m) → 8:51pm`.

## Pitfalls to avoid in implementation

- Don't recompute jitter on every tick — pick once per scheduled fire,
  persist it, and only roll a new offset when computing the *next*
  fire after this one runs.
- Don't add jitter to one-shot jobs (`repeat: once`) silently — that
  surprises users who scheduled a specific time. Either honor the
  literal time or require explicit opt-in.
- Don't move randomness into the agent prompt — every layer above the
  scheduler should see a deterministic fire time. The randomness is
  *when*, not *what*.

## Migration

To clean up the existing pre-run script approach without breaking
behavior:

1. Strip the script reference from each affected cron job:
   `cronjob action=update job_id=<id> script=""`.
2. Delete `~/.hermes/scripts/random_delay.py` once no jobs reference it.
3. Once schedule jitter ships in the framework, set
   `schedule_jitter: "30m"` (or similar) on the same jobs.

## Related

- `hermes-agent-development` SKILL.md pitfall on pre-run script
  blocking — this is the canonical reference for that pitfall.
- The cron docs at
  https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
  should grow a short "use the schedule, not the script, for jitter"
  section once jitter is implemented.
