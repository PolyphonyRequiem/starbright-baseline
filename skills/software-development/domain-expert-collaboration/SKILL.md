---
name: domain-expert-collaboration
description: Co-design with a user who is the domain expert on their own project — read their prior art before proposing, quote their words back exactly, stay in challenge-and-extend mode instead of leading.
when_to_use:
  - Multi-turn design conversation on a project the user knows deeply.
  - User mentions prior work, existing repos, or "I already built X".
  - You're tempted to pattern-match against general knowledge instead of their specific context.
  - User's instincts have been right more often than yours this session.
triggers:
  - User says "look at my repositories" or "I have prior work" or "I already built"
  - User correcting your spec one turn after they stated it (you summarized lossy)
  - User says "shoes on the other foot" or otherwise flags expertise asymmetry
  - You catch yourself fabricating a fact about their system to keep momentum
---

# Domain-Expert Collaboration

When the user is the domain expert on their own project, your job is **not** to lead the design. It is to:

1. Read their prior art before proposing on top of it.
2. Quote their constraints back verbatim before extending them.
3. Stay in challenge-and-extend mode — push back when you see an issue, defer when they see a structure you don't.
4. Flag your own pattern-matching out loud when you catch yourself doing it.

The failure mode this skill prevents: confidently designing on a foundation you never inspected, then having to walk back fabricated details when the user calls it.

## Mandatory steps

### 1. When user points at prior work — clone and read it BEFORE designing on top

If the user says "look at my repos" / "I have prior work on this" / "check what I've already built":

```bash
# Find candidates
gh repo list <user> --limit 50 --json name,description,updatedAt,visibility
# Clone the relevant one to /tmp (not into project tree)
cd /tmp && gh repo clone <user>/<repo>
# Read structure + specs/docs, not just code
find . -type f \( -name '*.md' -o -name 'spec.md' -o -name 'README*' \)
git log --oneline -20  # what's recent, what's merged
```

**Read specs and design docs first**, code second. Specs tell you intent; code tells you state. Both matter; intent matters more for a design conversation.

Then summarize what they've built in your own words and have them confirm before proposing anything new. Misreads caught early don't propagate through hours of downstream design.

### 2. Quote constraints verbatim

When the user states a design constraint, **save the exact wording**. Don't paraphrase "minimap only, freely rotating, no North indicator" into "basically vanilla." Lossy summaries become wrong specs one turn later.

Pattern that works:
- User: "X works like Y."
- You: "Confirming: X = Y, exactly your words. [extension proposal]"

### 3. Challenge-and-extend, not lead-and-defend

When their design instinct conflicts with yours:
- If they have domain knowledge you don't, defer and ask. Don't argue from general principle against their specific knowledge.
- If you see a real issue (technical limit, scope creep, contradiction with earlier decision), push back with the specific reason. Not "have you considered" — say "this conflicts with X you locked earlier, here's why."
- If you're uncertain whether your concern is valid, say so. "I'm not sure if this matters but —" is honest and welcome.

### 4. Flag your own hallucinations / pattern-matches out loud

When you catch yourself making a claim you didn't verify:
- "I'm pattern-matching here, let me check."
- "I claimed X earlier — I didn't verify that. Going to look."
- "That was a guess, not a fact. Treating it as one."

Catching your own hallucination publicly is worth more than silently being right.

## Pitfalls

- **Designing on top of a repo you haven't read.** Always clone + skim specs first.
- **Lossy paraphrase of locked specs.** Save exact wording, re-emit verbatim next turn.
- **Pattern-matching to "interesting" when "boring obvious" is right.** If user proposes simple and your instinct is to elaborate — pause. Their domain knowledge says it doesn't need elaboration.
- **Promoting your own prior-turn output to user-authority.** After context handoff, double-check "the user said X" is actually a user turn, not your own earlier message replayed in compaction. (See `conversation-frame-verification`.)
- **Reading a single short reply as full consent.** A one-char "O" or single "yes" to a multi-part proposal might be agreement to one part only, or a typo. Confirm scope before locking.
- **Forgetting that "their style" includes their roadmap shape.** When they reshuffle tiers/scope/priority, take the reshuffle as authoritative and replay the whole new shape back.

## Verification

After a design session, you should be able to:
- Point to exact files in their prior repos you read before extending.
- Quote their locked decisions verbatim, not in your paraphrase.
- Name at least one moment you pushed back, and one moment you deferred, with reasons.
- Name at least one of your own claims you flagged as a guess vs a verified fact.

If you can't do all four, you were leading instead of collaborating.

## Anti-patterns from real sessions

- "I'll guess at scope of <user>'s prior repo since they mentioned it briefly" — wrong. Clone and read first.
- "With X false it'd basically be vanilla" — wrong paraphrase of a precise spec. Quote, don't summarize.
- "Y is obsolete now" — hallucinated. Pattern-match to "this seems redundant" without checking what role the existing tool plays.
- "<Game/system> doesn't have <thing>" said confidently when the user has a mirrored corpus on disk you never grepped. Real case: claiming a game "has no bears" when a full wiki mirror sits on disk with the bear's stats and drops. If the user has mirrored their domain's docs locally, **grep the mirror BEFORE making any factual claim about that domain**.
