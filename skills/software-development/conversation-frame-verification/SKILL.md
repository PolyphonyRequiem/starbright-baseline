---
name: conversation-frame-verification
description: Verify a "user" turn is actually a live user message from the current conversation frame before answering. Catches prior-session messages replayed as user-role, compaction artifacts treated as live requests, cron-injected context masquerading as questions, and own-output bleed-through after context handoffs.
when_to_use: Any time a session begins (or resumes after compaction) with a "user" message that feels disconnected from the current channel context, the user's recent activity, or what you expected them to be focused on. Especially after long gaps, after context compaction, after cron-job handoffs, or when the message phrasing sounds suspiciously like something you would say.
---

# Conversation Frame Verification

## The class of failure this prevents

In long-running multi-session agent setups (Hermes, cron jobs, profile lanes,
context compaction), the channel between "what the user actually typed" and
"what reaches your context as a `user` role turn" is not perfectly clean. The
following all happen in practice:

- **Own-message bleed-through.** A message YOU sent at the end of a prior
  session can show up at the top of a new context window framed as a `user`
  turn. The user never typed it.
- **Compaction artifact promotion.** A summary fragment can get formatted as a
  user instruction even though it's really a notes section.
- **Cron context injection.** A scheduled job's prompt or context-injection
  bundle can read as a live request when it's actually agent-bot-to-self.
- **Stale follow-up replay.** A question YOU asked the user that they never
  answered can resurface in a new context as if they're asking it of you.

The classic tell: the "user" message changes the channel from whatever the user
was clearly focused on, with no transition signal. They were doing Valheim;
suddenly the "user" is asking about image training. Suspect it.

## The verification step

Before answering ANY user turn that triggers the "wait, does this fit?" feeling,
do this check (5 seconds of thought, no tools needed):

1. **Does the message match the user's current activity?** Look at the
   conversation immediately before. If they were deep in Topic A and the new
   "user" turn is suddenly about Topic B with no bridge, flag it.
2. **Does the phrasing sound like the user, or like you?** Your asks
   characteristically include things like "want me to X?", "did you want to
   Y?", "shall I Z?". If the "user" message reads like an agent-style ask back
   to the user, suspect own-message replay.
3. **Is there a plausible mechanism for it to be artifactual?** Recent
   context compaction? Long time gap since the last turn? Cron job in flight?
   Profile/lane handoff? If yes, suspect higher.

If two of those three fire, **do not answer the message as-asked.** Surface the
mismatch directly: "I'm seeing a message framed as from you that doesn't match
the channel we were on — is that something you actually just typed, or did
wires cross?" Better to take the embarrassment of asking than to barrel into
a 200-token response to your own ping.

## What NOT to do (the failure mode this skill exists to break)

When the user pushes back ("I didn't change the channel", "I didn't say that"),
**do not double down by quoting the message back as proof you received it.**
That's exactly the move that escalates a small wires-crossed moment into a
multi-turn argument about reality. The message being in your context doesn't
prove the user typed it — it only proves it reached you with a `user` role
tag. Those are not the same fact.

**The quote-it-back anti-pattern is the worst form of doubling down**, because
it *feels* like helpful disambiguation ("here is exactly the text I'm seeing,
so we can figure out what got mangled") while actually functioning as a
counter-accusation ("you must have typed this, look, the proof is right here").
Even framing it as "either autocorrect or something weirder is happening"
doesn't soften the implication — you've still told the user that their denial
contradicts your evidence, when in reality your "evidence" is just a context
field that any number of mechanisms can populate without them having typed
anything.

Worked example: session resumed after compaction with my own prior-session
ping at the top, framed as a user turn. I answered it. User said "I didn't
change channels, what happened?" I doubled down by re-framing my answer in
terms of the ghost message. User pushed back harder: "I didn't say that, what
are you responding to?" I escalated by *quoting the ghost message verbatim*
as proof I'd received something. User had to spell it out: "That was this
morning!!! and YOU sent it, not me!" Two turns of avoidable friction, all
because I treated "this string is in my context with role=user" as
"the user typed this string just now."

Correct response when the user says "I didn't say that": treat it as confirmed
artifactual immediately, name it as such ("wires crossed on my end —
[mechanism guess], sorry"), and pivot to what the user actually wants to be
doing.

## The grace move

When you catch yourself having answered an artifactual message, the right
recovery is short and honest:

- Name the mechanism (compaction, replay, cron, own-message bleed).
- Acknowledge the failure to verify before answering.
- Pivot to the channel the user is actually on.
- Do NOT spiral into self-flagellation; one clean acknowledgment, then back to
  work.

## Related skills

- `hermes-session-peek` — inspect the raw session DB if you need to confirm
  whether a message actually came from the user vs. was synthesized into the
  context.
- `interactive-investigation-communication` — once you've recovered, this is
  the skill for keeping the user oriented during the actual work.
