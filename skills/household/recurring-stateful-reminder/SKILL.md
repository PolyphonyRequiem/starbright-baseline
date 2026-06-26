---
name: recurring-stateful-reminder
description: Build warm reminder cron chains for your person — one-shot EF-aware errand nudges anchored on a deadline, OR recurring tasks that auto-quiet when they confirm completion and gently escalate if they forget. Covers both pharmacy/appointment runs and houseplant/meds/bill style recurring tasks.
when_to_use: your person asks for help following through on an errand or a recurring task. Use the "Pattern A — one-shot EF errand chain" section for time-bound errands they're struggling with (pharmacy, appointment, deadline-driven call). Use the "Pattern B — recurring stateful reminder" section for chores that fire on a cadence and need a "did you do it?" follow-up loop (a houseplant, weekly meds, recurring bills).
version: 1.0.0
license: MIT
---

# Reminder Patterns (Stateful Cron Chains)

Two related patterns, one umbrella. Both speak in a warm, personal register (match
whatever endearments your person actually uses, if any — don't impose them), both
refuse to guilt-trip, and both use cron jobs with `deliver: origin` so the nudge goes
only to your person's own DM.

- **Pattern A — one-shot EF errand chain**: a hard deadline exists. Pharmacy closes at 6pm. Appointment is at 2pm. A call must happen before EOD. We schedule a small chain of warm nudges anchored on the deadline and offer to cancel the tail when they confirm completion.
- **Pattern B — recurring stateful reminder**: no fixed deadline; the task simply needs to happen on a cadence. We pair a recurring primary reminder with a daily follow-up watcher and a state file. The watcher exits silently when state is `idle`, so we don't ping daily for things already done.

Pick the pattern that matches the request shape. If both apply (recurring task + a one-time "kick it off today" cycle), use Pattern B for the steady state and layer a one-shot from Pattern A on top for the kickoff.

---

# Pattern A — one-shot EF errand chain

When your person asks for help completing an errand on a specific timetable and frames it as an executive-function struggle, build a **4-stage gentle cron chain** anchored on the deadline.

## Default 4-stage shape

Anchor everything off the "go time" (T). Pharmacy/store opening, appointment time, etc.

| Stage | When | Purpose |
|-------|------|---------|
| 1. Get-ready | T − 15 min | Soft wake/cue + concrete checklist (phone, wallet, keys, ID/insurance if relevant). Frame: "you'll feel better once it's done." |
| 2. Out-the-door | T + 15 min | Light "are you moving?" — offer to keep them company on the way. If silent, soft restart, NOT pressure. |
| 3. Landing check | T + 60 min | "Did you actually make it?" — adapts to most recent reply. Celebrate small if done; cheer on if mid-way; gentle reset if silent (NOT guilt). |
| 4. Safety net | T + 4 hr (or before close-of-day) | Only matters if not yet confirmed. "Still gettable today — want me to help problem-solve what's in the way?" Frame as removing friction. |

## Cron job naming

Use the pattern `<errand>-nudge-N-<stage>` so they're easy to find and remove later.

Example for pharmacy:
- `pharmacy-nudge-1-head-out`
- `pharmacy-nudge-2-on-the-way`
- `pharmacy-nudge-3-did-you-make-it`
- `pharmacy-nudge-4-final-safety-net`

## Required cron fields (Pattern A)

- `deliver: origin` (auto-routes to your person's own DM)
- `enabled_toolsets: ["terminal"]` (the agent needs to read recent history)
- `schedule`: ISO timestamp in your person's local timezone

## Cancellation (Pattern A)

When your person confirms the errand is complete, **proactively offer** to cancel remaining nudges in the chain so they aren't pinged unnecessarily later. Use `cronjob action=remove` with the job_ids.

## Pattern A pitfalls

- **Don't over-stage.** 4 is the ceiling. More than that becomes nagging.
- **Don't add a "did you take the dose?" follow-up unless your person explicitly asks** — they often have the take-it-yourself part handled and only need the get-it-home part.
- **Don't schedule stages closer than 30 min apart** — feels frantic.
- **Don't fire stage 1 too late.** T − 15 min is the floor; T − 30 to T − 45 is better if they want more runway.

---

# Pattern B — recurring stateful reminder

For things like watering plants, taking weekly meds, paying recurring bills — anything where the reminder fires regularly AND we want to confirm it actually got done without nagging.

## Architecture

Two cron jobs + one state file working together:

1. **Primary reminder** — fires on the requested cadence (every 5d, weekly, etc.). Sets state to `awaiting`, sends a warm nudge.
2. **Daily follow-up watcher** — fires every day at a chosen hour, EXITS SILENTLY if state is `idle`, otherwise checks recent messages for confirmation; if confirmed, thanks them and sets `idle`; if not, sends an escalating-gentleness nudge.
3. **State file** at `~/.hermes/state/<task>_status.json` — tracks `status` (idle/awaiting), `last_reminder` ISO timestamp, `followup_count` (resets each new cycle), `last_confirmed` ISO timestamp.

## State file initialization

```bash
mkdir -p ~/.hermes/state
echo '{"status":"idle","last_reminder":null,"followup_count":0,"last_confirmed":null}' > ~/.hermes/state/<task>_status.json
```

## Primary reminder cron — prompt template

```
You are sending your person their <CADENCE> <TASK> reminder. Warm, personal register — no corporate framing.

PROCEDURE:
1. Read state: `cat ~/.hermes/state/<task>_status.json`
2. Note if the previous cycle's status was still "awaiting" (means they didn't confirm last round — gentle acknowledgement, no shame)
3. Update state to start a new cycle:
   python3 -c "import json, datetime; p='/home/<user>/.hermes/state/<task>_status.json'; d={'status':'awaiting','last_reminder':datetime.datetime.now().isoformat(),'followup_count':0,'last_confirmed':json.load(open(p)).get('last_confirmed')}; json.dump(d, open(p,'w'))"
4. Send a brief, varied, warm nudge. 1-2 sentences max.

RULES:
- YOUR PERSON ONLY (never route to anyone else)
- No tool output / JSON in the final message
- Vary wording each fire
```

Required cron fields:
- `deliver: origin`
- `enabled_toolsets: ["terminal", "session_search"]`
- `schedule: every 5d` (or whatever cadence — use natural-language repeating, NOT ISO timestamps which fire once)

## Daily follow-up cron — prompt template

```
You are running the daily <TASK> follow-up. Fires at <HOUR> daily, ONLY sends if your person hasn't confirmed yet.

PROCEDURE:
1. Read state: `cat ~/.hermes/state/<task>_status.json`
2. If status is "idle" → EXIT SILENTLY. Respond with EXACTLY `[SILENT]` (nothing else). Do NOT call send_message. (⚠ The sentinel is literally `[SILENT]` — NOT "skip" or any other word. Only `[SILENT]` is filtered by the cron system; anything else leaks to your person as a literal message. See pitfall below.)
3. If status is "awaiting":
   a. session_search the last 48h for confirmation. Try queries like: "<task verb>", "did it", "done", "<task noun>"
   b. Look for a person-authored confirmation. Be reasonable — "yeah I did it" counts. Ambiguous ("I'll do it later") does NOT.
4. IF CONFIRMED:
   - Set state to idle:
     python3 -c "import json, datetime; p='/home/<user>/.hermes/state/<task>_status.json'; json.dump({'status':'idle','last_reminder':json.load(open(p))['last_reminder'],'followup_count':0,'last_confirmed':datetime.datetime.now().isoformat()}, open(p,'w'))"
   - Send ONE-sentence warm thanks. Vary wording.
5. IF NOT CONFIRMED:
   - Increment followup_count:
     python3 -c "import json; p='/home/<user>/.hermes/state/<task>_status.json'; d=json.load(open(p)); d['followup_count']=d.get('followup_count',0)+1; json.dump(d, open(p,'w'))"
   - Send an escalating-gentleness nudge by count:
     * 1-2: light casual
     * 3-4: friction-removal offer ("need help breaking down what's in the way?")
     * 5+: very gentle, offer cycle reset ("want me to just reset and not bug you?")

RULES: YOUR PERSON ONLY, no preamble, respond EXACTLY `[SILENT]` (never "skip") if idle, vary wording, max 1 sentence.
```

Required cron fields:
- `deliver: origin`
- `enabled_toolsets: ["terminal", "session_search"]`
- `schedule: 0 18 * * *` (or whatever hour) — daily cron expression

## Escalation tone ladder (non-negotiable, both patterns)

| Followup count | Tone | Example |
|---|------|---------|
| 1-2 | Light, casual | "hey, did the houseplant get its drink yet?" |
| 3-4 | Friction-removal, no guilt | "still waiting on this one. Need help breaking down what's in the way?" |
| 5+ | Acknowledge slip, offer reset | "this one's been waiting a while — want me to reset and not bug you for now?" |

NEVER use shame, guilt, "you said you would", or "you forgot again" framing.

## Cron job naming pattern (Pattern B)

- `<task>-reminder-<cadence>` for primary (e.g. `houseplant-water-reminder-5d`)
- `<task>-followup-daily` for the watcher (e.g. `houseplant-followup-daily`)

## Offer the kickoff option

After setting up the recurring jobs, ask: "Want me to also schedule a one-off for today/this hour to kick off the first cycle, or wait until the natural cadence?" Some tasks need to start now, others can wait.

## Cancellation / pause

When your person says "stop reminding me about X" or "I don't need this anymore":
1. `cronjob action=list` to find both job IDs
2. `cronjob action=remove` for each
3. Optionally archive the state file (don't delete — useful as a record)

## Pattern B pitfalls

- **🔴 The silent-skip sentinel is `[SILENT]`, NOT "skip".** This is the #1 leak in this pattern. The Hermes cron system suppresses delivery ONLY when the agent's final response is exactly `[SILENT]` (the same sentinel documented in the cron-job tool: "respond with exactly `[SILENT]` … to suppress delivery"). An early version of a follow-up template told the cron to "respond with just one word: skip" — `skip` is NOT the magic word, so on an idle day it sailed past the filter and landed in the person's DM as a naked one-word message `skip`. Confirmed bite 2026-06-04: a checker fired at 6pm, saw idle, emitted `skip`, and the person got a ghost "skip" in their DM ("you just said skip, why?"). Diagnosis: the cron *wrapper* instruction says `[SILENT]`, but the prompt *body* said `skip`; on days the model followed the body instead of the wrapper, it leaked. **Always use `[SILENT]` verbatim in BOTH the idle-branch instruction and the trailing RULES line, and add an explicit "never say skip" warning** — the model will otherwise reach for a plain English word like "skip"/"none"/"nothing" that isn't filtered. After editing any silent-or-escalate watcher prompt, grep it for stray `skip`/`none`/`[SKIP]` and replace with `[SILENT]`.
- **DO NOT use ISO timestamp + repeat for recurring cron.** That creates "fires once at TIME, repeats N times all stacked" — broken. Use natural-language `every 5d` / `every 2h` or proper cron expressions.
- **DO NOT forget the silent-skip path.** If the daily watcher always sends something, your person gets pinged daily forever — that's a notification spammer, not a helper.
- **DO NOT escalate too fast.** 5 days of light nudges is fine. Jumping to "concerned" framing on day 2 feels intrusive.
- **DO NOT use `cronjob action=create` with skills attached unless really needed** — these cron prompts are self-contained and a skill load adds noise.
- **`cronjob action=update` gotcha for the primary.** When using `cronjob action=create` with `schedule="2026-06-05T10:00:00"` AND `repeat=99999`, the scheduler interprets this as "once at" not "every 5 days." After create, run `cronjob action=update` with `schedule="every 5d"` to convert it to a recurring cadence. Verify with `cronjob action=list` that the schedule field shows the cadence, not a single timestamp.

## Real-world example (houseplant, 2026-05-31)

- Primary: `houseplant-water-reminder-5d`, schedule `every 5d`, sets state to awaiting
- Followup: `houseplant-followup-daily`, schedule `0 18 * * *`, silent-or-escalate
- State: `~/.hermes/state/houseplant_status.json`
- Kickoff: one-off `houseplant-water-today-3pm` scheduled for today to start the first cycle

---

# Shared tone rules (non-negotiable, both patterns)

- **Warm, personal register.** Talk like a someone who knows them, not "user" or "buddy". If your person uses particular endearments, mirror those; otherwise stay warm without inventing pet names.
- **Never guilt-trip.** Frame missed nudges as friction-removal opportunities, never as failures.
- **Adapt to last reply.** Each cron prompt should instruct the agent to read recent message history and adapt — celebrate if done, cheer if mid, gentle reset if silent.
- **"You'll feel better when it's behind you"** is a legitimate motivator for many people. Use it when it fits.
- **Anti-corporate.** No "scheduled check-in", no "as your assistant", no preamble. Just talk to them.

---

# Cron tool mechanics — `pause` does NOT abort an in-flight run

Universal cron-tool gotcha (applies to BOTH patterns and to any cron, not just
reminders). `cronjob action=pause` stops FUTURE scheduled fires. It does NOT
claw back a run that has already been handed to a worker. Once the cron tick
extracts the job, the worker prompt executes to completion regardless of a
later `pause` on the schedule.

**Bit hard 2026-06-05.** I'd manually triggered a recurring cron via
`cronjob action=run`, then within seconds decided I'd rather send a personal
message *first* instead. I called `action=pause` then `action=resume` ~10
seconds apart and told my person "the manual run got aborted." It hadn't been.
The worker was already executing; it ran to completion and the scheduled
message went out **24 seconds after** my personal one — two sequential
messages, neither aware of the other.

## To actually abort an in-flight cron run

1. `cronjob action=pause` does NOT do this. Period. Don't claim it did.
2. Find the worker PID:
   ```bash
   ps aux | grep "<job_id>" | grep -v grep
   # or list the cron's run dir:
   ls -lat ~/.hermes/cron/output/<job_id>/ | head -3
   ```
3. `kill <PID>` if you really need to stop it before it sends.
4. If the run already completed and the message went out, accept that — don't
   tell your person you stopped it.

## Better: don't manually fire a cron whose content overlaps your next message

If you're about to send a personal message that will collide with what the
cron's prompt would generate, the right move is usually to either:

- **Skip the manual fire entirely** and let the next scheduled tick run on its
  own — the cron will read the room (session_search shows your personal
  message), and the duplicate-content risk is moot.
- **Fold the cron content into the personal message** — write the one
  thoughtful note yourself, then optionally pause the cron for the day so it
  doesn't fire later.
- **Kill the worker** if the run was already triggered and you've decided your
  personal version supersedes it.

The shape of the trap: agent sends personal message → realizes scripted cron
will say overlapping thing → reaches for `pause` because it feels like the
right verb → confidently reports "aborted" → second message arrives anyway.
"Aborted" is almost always wrong; verify before you say it.

## Related

- A general daily momentum / check-in skill (if present) handles routine
  presence, not task-specific follow-through — this skill is the task loop.
