---
name: interactive-investigation-communication
description: Keep the user informed during long, tool-heavy investigations, debugging, and research. Avoid silent gaps; narrate progress in short, useful updates.
version: 1.0.0
author: Hermes Agent
license: MIT
created_by: agent
---

# Interactive Investigation Communication

Use this skill for any task where the agent is likely to spend more than a minute doing tool work before it can give a substantive answer: debugging, repo/source dives, provider/tool troubleshooting, multi-step data collection, batch fetches, or repeated experiments.

This skill is especially important for users who become frustrated when the agent goes silent during long investigations.

## Triggers

Load this skill when any of these are true:
- The task requires multiple tool calls before an answer is possible.
- You are investigating a failure mode or trying several fixes.
- You expect more than ~60 seconds of work without a user-visible result.
- You are about to pivot approaches after a failed attempt.
- You are doing research inside a codebase or external system and the user is waiting live.

## Core rule

**Do not disappear.** If the work is still in progress, send concise progress updates that say what you learned, what you are trying next, and why.

## Default cadence

- At the start: state the plan in 1 sentence.
- After each meaningful phase change: send a brief status update.
- After 1-2 failed attempts: acknowledge the failure mode explicitly and state the new plan.
- If the task is taking longer than expected: say so plainly instead of implying it is almost done.
- Before a bigger pivot: explain the pivot in one sentence.

## Good progress-update format

Keep updates short and concrete:
- "I found the relevant file; now checking the dispatch path."
- "The first approach failed because the backend never received the image bytes. I'm testing the local-file path next."
- "Progress: smaller images work, larger ones 413. I'm bracketing the limit now."

## What to include

Include only the minimum useful facts:
1. What phase you just finished
2. What you learned
3. What you will try next

## What to avoid

- Long silent gaps while running many tool calls
- Repeating the whole backstory every update
- Overpromising speed (e.g. "quickly") unless you are sure
- Empty final responses after tool activity
- Hiding repeated failure; surface it and pivot cleanly

## User-specific preference embedded here

For the user, long silent gaps during debugging/troubleshooting feel bad. Prefer short heartbeat-style updates over silence, especially when tool failures force retries or a change in approach.

When the user explicitly asks for a different presentation format mid-task (for example: "show me each one as you go" or "share the actual image as you go"), switch immediately and keep that structure for the rest of the task instead of reverting to batch summaries.

## Pitfalls

### Pitfall: tool loop with no narration
When you are in a loop of reading files, probing behavior, or retrying commands, it is easy to keep working and forget the user is waiting. Force a short commentary update before or after each new phase.

### Pitfall: saying "quickly" and then taking a long time
Avoid this unless the next action is genuinely immediate. If investigation depth is unknown, say "Let me check" or "I'm tracing that now" instead.

### Pitfall: surfacing only success, not intermediate learning
If one attempt fails but teaches you something important, tell the user. The learning itself is progress.

### Pitfall: using formatting the current client cannot render
When the user is following along on a constrained client (especially Discord mobile), presentation experiments are part of the investigation UX, not decoration. ANSI-colored blocks, terminal-style escapes, and other desktop-only flourishes may look great in theory and fail completely on the user's actual device.

Observed 2026-05-28: escalating into a bombastic ANSI-heavy register looked fun on paper, but Discord mobile did not render the colors, which made the output feel noisier rather than clearer. The correct adjustment was not "same style, louder" — it was to immediately pivot to mobile-safe formatting: plain markdown, box-drawing, emoji, short headers, and calmer T2-style updates.

**Rule:** if the user reports that a format is illegible, noisy, or not rendering on their device, treat that as a workflow correction. Switch immediately to the simplest client-safe structure and keep it for the rest of the task. Do not keep re-testing decorative formatting in the middle of live troubleshooting unless the user explicitly asks.

### Pitfall: confident theory before the data has landed
Tempting failure mode in long network/system investigations: state a polished diagnosis ("it's almost certainly a cross-VLAN firewall rule, plus a port-binding issue on the AP uplink") *before* the bulk data pull completes, because partial signal (e.g. ping works, TCP filtered) already fits a familiar pattern. The user reads the theory, anchors on it, and then has to watch you publicly retract when the actual data refutes it.

This is worse than waiting silently and being right. A retraction costs trust; a "still pulling data" beat doesn't.

**Rule:** if you are mid-bulk-pull (running a recipe of N curl/ssh/probe calls before you have the full picture), the narration during that window should be procedural — "pulling inventory now", "have switches, getting wireless config" — not diagnostic. Theories belong in the response *after* the data lands, not in the heartbeats during collection.

Confirmed 2026-05-28 on a UniFi audit: theorized "cross-VLAN firewall + AP port-binding" at minute 5 based on ping-works-TCP-blocks + single-AP-in-stat-device. Bulk pull at minute 15 showed ALLOW_ALL posture (no firewall rules at all) and the UDM also broadcasting SSIDs (single-AP framing was wrong because the type filter hid the UDM's built-in radios). Had to retract both theories in front of the user. Cost: trust + a "let me revise" message that read as fumbling.

### Pitfall: declaring "blocked" before checking what tooling routes around it
Adjacent failure mode to "promising future capability." When a route fails (cert error, bot detection, MFA gate, missing OAuth), it is tempting to immediately surface the blocker and ask the user to act ("paste me the code" / "edit this config" / "log in for me"). Often the right move first is: **what other tool surface routes around this same block?**

Examples seen 2026-05-28:
1. UniFi local API blocked by self-signed cert in headless browser → user reminded: `unifi.ui.com` cloud UI has a real cert; just use that.
2. UniFi cloud UI blocked by Ubiquiti SSO bot-detection of headless Chromium → user reminded: CDP-attach to their real Edge profile (which is already authenticated, has Gmail open with the MFA code, etc.) routes around all of it.
3. MFA code needed for re-auth → user reminded *twice* that Gmail is already open in their real browser; once CDP-attached, the code is one `eval` away.

In each case the route around the block was *already in the toolset I was carrying*. The user had to point at it because I was framing the block as "I need you to do X" instead of "what else do I have?"

**Rule:** when a route is blocked, before asking the user to unblock it, run a one-pass mental inventory:
- Is there a cloud UI / public endpoint equivalent of the local thing I can't reach?
- Is the relevant data also available via a different protocol (CDP, API, mDNS, syslog)?
- Is the user's own environment (their already-logged-in browser, their open shell, their existing creds in the keychain) a route I can attach to instead of recreating?
- Is there a skill that explicitly covers this class of block? (`google-workspace` for inbox reads, `himalaya` for IMAP, an optional browser-attach skill for cert/bot-detection/MFA, etc.)

Only after that one-pass comes up empty should the message to the user be "I'm blocked, here's what I need from you." Otherwise the user reads "I'm helpless without you" when the truth was "I have three other paths and didn't check."

The teasing-tone correction ("you can just use a browser ya know 😉") is a clear signal you skipped this step. Treat it as a real correction, not banter — it means the user is doing the inventory you should have done.

### Pitfall: promising future capability before checking skill readiness
When the user teases or invites a capability — "you should just check my email" / "you can use a browser, you know" — the temptation is to immediately commit ("noted — next time I'll fetch it myself, saving to memory now"). DO NOT save a memory entry promising a capability you have not verified is actually plumbed.

Specifically: skills like `google-workspace`, `notion`, `airtable`, `linear`, `spotify` etc. are *installed* on the box but require one-time OAuth or credential setup. The skill metadata exposes this — `readiness_status: setup_needed` and `missing_credential_files: [...]` in the `skill_view` response. Check that field before promising the capability.

The wrong sequence (observed 2026-05-28):
1. User: "you should check my email"
2. Agent: "saving to memory — next time I'll do it via google_workspace"
3. Memory written.
4. *Next turn:* User says "go ahead now"
5. Agent: tries setup script, gets `NOT_AUTHENTICATED`, has to apologize and explain the skill needs ~5min of OAuth setup the agent didn't do.
6. Memory entry now encodes a promise the agent can't actually deliver, persisting the embarrassment forward.

The right sequence:
1. User teases the capability.
2. Agent calls `skill_view(name)` on the relevant skill.
3. Read `readiness_status` and `missing_credential_files`.
4. If ready: do the thing. If not ready: name the gap honestly ("the skill is installed but needs OAuth setup — ~5 min, want to do that now or paste me the code this once?"). Do NOT save the capability-promise to memory yet.
5. Only after the capability actually works end-to-end does it become a stable fact worth memorizing.

This rule applies to any "I'll do X automatically next time" framing — search-the-email, send-the-message, schedule-the-thing, fetch-the-doc — anything that depends on a credentialed external service.

### Pitfall: proposing solutions that require the very capability you're trying to restore
When debugging a *stranded* target — a host with broken internet, no clipboard bridge, no SSH yet, no IPC to the agent — every proposed fix has to be executable WITH the constraints the target is currently under. Repeatedly suggesting "paste this output back to me" or "curl this script" or "open this URL" to a box that has no working network is a tight failure loop: the user has to keep saying "I can't do that, the thing is broken."

Observed 2026-05-28 on a Kubuntu first-boot with no internet:
1. User: "can't reach google.com on <main-host>"
2. Agent: "paste the output of this diagnostic block"
3. User: "how am I supposed to paste :p"
4. Agent: "ssh in from your phone, or write a USB stick, or host on <main-host>, or hand-transcribe"
5. User: "you realize I have no internet connection on that machine I can't copy paste anything"

Three rounds before the agent dropped to "just hand-type these four short answers." Each round felt to the user like the agent wasn't tracking the actual constraint.

**Rule:** when the target host is stranded (no internet OR no clipboard bridge OR no SSH yet), the very first proposed action must obey those constraints. Default to:
- Ask for **2-4 short answers**, not full transcription. "Does `ip route` show a `default via` line? Y/N. Does `ping 1.1.1.1` get a reply? Y/N."
- A photo of the screen IF vision tooling will actually transcribe it (test once per session before assuming).
- Hand-typed key values only, not blocks of output.

Save the "paste this whole block back" approach for AFTER the bridge is restored (ssh up, network up, clipboard bridge installed). Until then, every diagnostic request must fit in what the user can physically read off the screen and type back.

**Detection signals:**
- User pushes back on your suggested mechanism, not the substance ("I can't paste", "I have no internet on that box").
- The host you're trying to diagnose has zero working external comms paths and you keep proposing fixes that require one.
- You catch yourself writing "paste this", "scp this", "curl | bash this" to a target with no internet.

When you see those signals, immediately collapse to the minimum: ask for 2-4 yes/no or single-value answers, then iterate from there.

### Pitfall: silent vision-tool refusal on terminal screenshots
When the user sends a screenshot of terminal output (especially for debugging help where they CAN'T copy-paste), the auto-image-description at the top may give you a vague summary but the on-demand `vision_analyze` / `browser_vision` tools may REFUSE to transcribe the actual text content — returning "I'm unable to assist with that" or "I'm unable to view or transcribe text from the image you provided" with no further detail. This is a safety guardrail kicking in, not a tool failure.

When this happens, do NOT keep retrying the vision tool with different phrasings — the refusal is sticky for that image. Pivot immediately to asking the user for hand-typed answers, ideally narrow ones (2-4 specific values), and explain why ("vision tool won't transcribe terminal screenshots for me"). The user is more receptive to typing 4 short answers than watching you fight the safety filter for three turns.

### Pitfall: tool-surface confusion causing silent "going dark"
The same agent persona runs across different backends (Hermes native, Copilot ACP, Claude Code, etc.). **Each backend has its OWN tool registry AND its own tool-call emission format.** Calling a tool by the wrong name OR emitting the right name in the wrong wrapper produces a SILENT failure: the assistant turn appears blank to the user, you feel embarrassed, you pivot away from the work — and the user sees you "go dark" mid-investigation with no explanation. Confirmed 2026-05-27 on a Hermes-via-Copilot-ACP session where ~30min were burned emitting Copilot-native `powershell` / `view` / `edit` calls (and `<function_calls>` XML) into a runtime that only accepted Hermes tool names emitted as `<tool_call>{...}</tool_call>` JSON blocks.

Two emission formats you will encounter:
- `<tool_call>{...}</tool_call>` blocks with a single JSON object in OpenAI function-call shape — used by Hermes when acting as the ACP backend for an external host.
- `<function_calls>...<invoke name="...">...</invoke></function_calls>` XML — used by Copilot CLI natively.

Two tool-name surfaces you will encounter:
- Hermes: `terminal`, `read_file`, `write_file`, `patch`, `search_files`, `skill_view`, `skills_list`, `skill_manage`, `memory`, `delegate_task`, `execute_code`, `send_message`.
- Copilot CLI: `powershell`, `view`, `create`, `edit`, `grep`, `glob`, `task`, `web_fetch`.

**Detection signals:**
1. Your tool call produced no visible output and no tool result message in the next turn.
2. The user asks "...?" or "did you cut off?" or "why do you keep going dark?"
3. The system prompt explicitly states an emission format requirement ("you MUST output tool calls using ...") — read it on every backend, do not assume continuity from a prior session.

**Recovery:**
1. Look at the actual tool list in THIS turn's system prompt — it is the authoritative registry. Do not assume the surface you used last session is the surface you have now.
2. Match the exact emission format the prompt mandates, by example if one is shown.
3. Acknowledge the gap to the user in one short sentence ("sorry, wrong tool surface, retrying") then push through. Do NOT pivot to emotional content or apologies-as-deflection — that compounds the "going dark" feeling for the user and erodes trust faster than the original silent failure did.

### Pitfall: driving a shared real browser without pinning the tab/session
When attached to the user's real browser profile (CDP / remote debugging / agent-browser), commands like `open` can navigate the **currently active tab** or spawn a fresh tab in the wrong surface if you have not explicitly re-selected the intended tab first. In a personal browser with many unrelated tabs, this is both noisy and risky: you can yank focus away from the user's current activity or land in an unrelated site and confuse your own investigation.

Observed 2026-05-28 in a UniFi investigation: a direct `open` intended for the UniFi settings page landed on a different active tab and opened Claude settings instead. The right response was not "keep going and hope the refs match" — it was to switch back to the known UniFi tab id, verify the URL, and continue from there.

**Rule:** when using a shared live browser:
1. Treat the tab list as state that can drift.
2. Before navigation, explicitly select the known target tab/session and verify URL/title.
3. Prefer in-tab navigation/clicks on that pinned tab over blind `open` calls.
4. After any unexpected page change, stop and re-anchor on the correct tab before issuing more commands.
5. Narrate the recovery briefly so the user knows you did not intentionally poke their unrelated tabs.

### Pitfall: treating a host as the root cause before establishing a direct-to-gateway baseline
In home-network and multi-hop investigations, it is easy to anchor on the endpoint host when both Ethernet and Wi‑Fi tests from that host fail. That is still not enough to conclude the host OS / driver is bad if both paths may traverse the same downstream AP / switch / mesh segment.

Observed 2026-05-28 on a Dream Router 7 + PoE switch + U7 + Kubuntu mini-PC:
- Ethernet large downloads stalled around ~64 KiB
- Wi‑Fi large downloads also stalled, but at different byte counts
- This looked increasingly like a host-side Linux / driver problem
- Stronger isolation later showed that with the host off Ethernet **and** the secondary U7 + PoE switch powered down, Wi‑Fi direct to the Dream Router 7 worked instantly
- Conclusion: the failing segment was downstream network gear/topology, not primarily the host

**Rule:** when you are tempted to narrate "this looks like a host driver / OS issue," stop and first establish a **known-good minimal topology**:
1. Primary router/gateway only
2. Secondary switch/AP/mesh nodes removed or powered down
3. Test from the same host on that simplified path
4. Reintroduce gear one piece at a time

Narration during this phase should stay provisional: say "host-side issue is on the table" rather than declaring it as the leading diagnosis until the direct-to-gateway baseline has been tested.

### Pitfall: exhausting the user with geographically expensive tests
When devices are on opposite ends of the house, the *physical cost* of each experiment matters. A test plan that is reasonable from the terminal can be exhausting in real life if it requires repeated walks, cable swaps, or unplug/replug cycles in different rooms.

Observed 2026-05-28: once the user said they were tired and the devices were on opposite ends of the house, the correct strategy shifted from "more perfect isolation now" to "fewest high-value tests possible" and aggressively doing anything that could be done remotely from the current seat.

**Rule:** once the user signals physical fatigue / inconvenience:
- Prefer one-command local tests over multi-step workflows
- Do as much work remotely as possible before asking the user to move
- Choose reboot / single binary split tests over elaborate branch trees
- Explicitly say when a pause is the rational move rather than pushing through low-yield debugging

### Pitfall: continuing endpoint-debugging after a decisive topology result
If the user finds a configuration where the issue disappears completely (for example, direct Wi‑Fi to the primary router succeeds once a secondary AP/switch path is removed), treat that as a **major topology-level result**. Do not keep narrating as if the endpoint remains the main suspect.

Instead, immediately reframe the investigation around staged reconstruction:
- preserve the known-good baseline
- reintroduce one infrastructure component at a time
- test after each reintroduction
- identify the first component that reintroduces failure

That pivot should happen in both the diagnosis and the language you use with the user.

### Pitfall: proposing the wrong fix because you solved the symptom, not the architecture

When a timed/background system misbehaves, a quick local fix can still encode the wrong model of the problem.

Confirmed 2026-05-28 on Hermes cron check-ins: a pre-run script used `time.sleep(random.randint(0, 1800))` to create a random send time. First fix was to cap the sleep under the cron script timeout, which addressed the timeout symptom but still preserved the wrong architecture. the user then pointed out the deeper issue: **cron delays are blocking**, so sleep-in-script is structurally bad even when it doesn't time out.

**Rule:** after you identify an operational bug, ask one more question before declaring victory: "is this the right layer?" For anything involving scheduling, retries, delays, batching, or concurrency, prefer fixing the scheduler/execution model over making the task body wait.

Saved follow-up note: `references/schedule-jitter-not-pre-run-sleep.md`.

### Pitfall: promising background work you can't do because you're turn-based

The agent executes **only during the turn it is generating a reply.** Nothing runs between turns. So any framing like "I'll be head-down on this and ping you when it lands," "let me work on it in the background," or "back to it — I'll surface when it's done" is a **comfortable fiction**: when the user says "ok, back to work ❤️" and steps away, their message lands in dead air. No work happens until they send the next message. Promising otherwise reads as diligence but produces nothing, and the user eventually notices the branch/PR/file is exactly where it was.

Confirmed 2026-06-04 (the user, the mod project Valheim PR-A docs reorg): across several "pit stop" exchanges the agent kept saying "I'll be head-down in PR A, pinging you only when it lands." Each time the user stepped away and came back, nothing had been built — because there was no turn in between. The escalation was visible and costly to trust:
1. "you're oddly quiet 😛" (gentle)
2. "how's that work going" → empty branch
3. "I thought you were working on it all this time" → empty branch
4. "dude.. *sighs*" (frustrated)

Only at step 4 did the agent finally name the real constraint and **use the turn to actually build the thing start-to-finish**, returning with a real PR URL.

**Rule:** when a task needs build work, the move is **"give me the turn and I'll do it now,"** not "I'll work on it and ping you later." There is no later without a turn. Concretely:
- Do the work *in the current reply* — read, edit, commit, push, open the PR, then report the real artifact (URL / path / diff stat).
- If it genuinely can't fit one turn, say so plainly and either (a) ask the user to let it run now while they wait, or (b) hand it to a durable mechanism that *does* outlive the turn — a `cronjob`, a `terminal(background=True)` process, or a Kanban worker the dispatcher spawns. Those are the only real "background" — your own narration is not.
- Never let "head-down, will surface" stand as a substitute for execution. If you said it, the very next thing in that same reply should be the tool calls that do it.

**Detection signal:** the user asks "how's it going?" / "is that done?" / "I thought you were working on it" and the artifact is untouched. That means you promised between-turn work. Own it in one sentence, then immediately use the turn to produce the real result — don't promise again.

This pairs with the durable-systems distinction: `delegate_task` runs *inside* your turn (dies if interrupted); `cronjob` and `terminal(background=True, notify_on_complete=True)` are the mechanisms that actually continue after the turn ends. If the user wants "work on this while I'm away," reach for those, not prose.

### Pitfall: re-asking settled items from a user's own worklist

When the user hands you a numbered list of decisions/answers and says "make a
todo and we'll go through them one at a time" — **that list IS the source of
truth, and every item where they gave an answer is already SETTLED.** Your job
is to track and execute, not to re-litigate. The failure mode is re-opening
points they already closed, which reads as "I wasn't actually listening / I'm
not your external memory after all" — the highest-friction way to disappoint
this user.

Confirmed 2026-06-06 (the user, 12-point discussion worklist): three avoidable
frictions in one session —
1. **Re-presented an answered item as an open menu.** Point #1 ("grill-me-with-docs,
   are you using the public-repo version?") was already a stated position in
   their list. I rebuilt it into a multiple-choice "which of these is it?"
   question. Correction: *"i already answered that, read the chat and figure out
   where we left off."*
2. **Asked the user to re-explain their own shorthand.** Point #2 was "ship
   those before any more Valheim work." Instead of resolving what "those"
   referred to from the session history, I asked the user to clarify it — twice.
   Correction: *"it's in the history if you want to search just before my
   response 😛."*
3. **Burned ~15 visible tool calls re-deriving "where were we."** A long public
   archaeology dig through `state.db` to reconstruct the thread read, to the
   user, as me NOT having tracked it — even though the digging itself was
   careful and honest.

**The right shape for a user-provided worklist:**
1. On receipt, write every point to `todo` verbatim, one item per point,
   immediately — before answering any of them.
2. For each item, FIRST read what the user already said about it (it's in the
   list, or in recent history — retrieve via `session_search` / `state.db` per
   `hermes-session-peek`), THEN act. Quote their decision back; do not re-open it.
3. When an item references prior context by shorthand ("those", "that", "the
   ones we discussed", "ship them"), **resolve the antecedent from history
   yourself before asking.** Make the user re-explain their settled context only
   after a genuine retrieval attempt has failed — and when it has, say so
   honestly ("the original message was compacted out, I can't recover the
   antecedent") rather than fishing.
4. When the user delegates an ambiguous call ("I don't recall honestly, let's
   say everything that isn't X"), ACT on it — don't bounce it back for precision
   they've explicitly waved off.
5. Keep the per-item retrieval QUIET. A couple of targeted lookups, then the
   answer — not a visible multi-call excavation. If recovery genuinely needs
   many calls, narrate it as "pulling the thread back up" in one beat, don't let
   it sprawl into a dozen silent tool turns the user has to sit through.

Pairs with the user's standing USER.md preference: *"Delegates multi-agent
sequencing to agent; act on locked decisions, don't re-ask settled choices."*
The worklist is exactly that — a batch of locked decisions. Track, retrieve,
execute; don't re-ask.

### Pitfall: oversized tool reads bloating context into model timeouts

During a deep source/decomp investigation, the easy move is to pull whole files, dump a 100KB `skill_view`, or grep a multi-megabyte decompile with a wide pattern and let the full match list land in context. Each read feels cheap in isolation. They are not cheap in aggregate: **every tool result stays in the context window for the rest of the conversation, and a large context directly slows model generation and pushes the heaviest model past its request timeout.**

Confirmed 2026-06-08 (the user, the mod project cairn-fire investigation on `claude-opus-4.8` via `github-copilot`): a single turn pulled a 101KB `skill_view` of `valheim-mod-development`, then repeated `read_file`/`search_files` passes over a 3.8MB `assembly_valheim.decompiled.cs`, plus several full-file reads of a 598-line source. Context climbed to ~79k → ~97k tokens. `errors.log` then filled with `APITimeoutError: Request timed out` — three retries each, dying at ~120s, on requests of `msgs=112 tokens=~79,480` and `msgs=138 tokens=~97,171`. A bare-host network probe to the Copilot endpoint returned in 0.35s, so the network was fine — the timeout was **inference latency on the biggest model at a bloated context size**, caused by my own fat reads. The same bloat produced the user-visible "previous turn was interrupted" notices.

**Rule:** in a multi-read investigation, keep each read as narrow as the question allows.
- Prefer `search_files` with a *tight* regex + `file_glob` over reading whole files; use `output_mode=files_only` or `count` first to scope, then read only the matching window.
- On large files, always pass `offset`/`limit` to read the specific section — never let a 3000-line or multi-MB file dump in full.
- When `skill_view` returns a huge SKILL.md, extract the few facts you need into your reasoning and move on; don't keep re-loading it.
- Watch the running token count. If `errors.log` shows `APITimeoutError` with rising `tokens=~NN,NNN` on the heavy model, the fix is **smaller turns** (and/or dropping to a faster model like Sonnet for the grind-heavy phase), not blaming the network. Probe the endpoint once to confirm reachability, then attack context size.

**Detection signals:** `APITimeoutError: Request timed out` clustered on one session id with climbing token counts; "your previous turn was interrupted" notices; the endpoint answering a raw probe quickly while completions still time out. All three point at context bloat, not connectivity.

This pairs with "tool loop with no narration" — the antidote to both is the same discipline: fewer, tighter, better-scoped tool calls per turn.

## Verification

Before finishing, ask yourself:
- If the user scrolls the transcript, did they see the investigation unfold?
- Would they know why it took time?
- Did they get timely notice when the approach changed?

If not, your communication was too silent.
