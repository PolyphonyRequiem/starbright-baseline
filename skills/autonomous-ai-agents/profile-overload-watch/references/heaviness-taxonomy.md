# Heaviness Taxonomy — how to tell overload from healthy depth

Load this before scoring a profile. The point is **not** a single number; it's
to enumerate which signals are firing, classify the carried capabilities, find
the seam, and only then judge. A profile can be large and healthy (deep
specialist) or medium and overloaded (junk drawer). The seam is what matters.

## Step 1 — Enumerate the heaviness signals

Score each signal as present/absent and note the evidence. No signal alone is
decisive; overload is a *pattern* across them.

### A. Context-cost signals (what taxes every turn)
- **Skill-description surface.** Count skills and eyeball total `description`
  bytes (every model-invoked description loads each turn). Many *model-invoked*
  skills across unrelated domains is the expensive kind of heavy.
- **MCP tool-schema surface.** MCP servers inject their full tool schemas every
  call. One or two big servers (an ADO/EV2-scale fleet) can outweigh all skills
  combined. An MCP unrelated to the profile's mission is a strong seam signal.
- **SOUL breadth.** A SOUL that spans multiple personas/roles ("companion AND
  senior SRE AND research assistant") is carrying more identity than one profile
  should.

### B. Domain-spread signals (the seam finders)
- **Distinct domain clusters.** Group skills by domain. Two+ clusters that share
  no context (companion vs. cloud-deploy vs. paper-writing) = candidate seams.
- **Distinct role clusters.** Different *modes of work* (intimate companion,
  production-incident responder, academic writer) imply different postures that
  fight for the same SOUL.
- **Unrelated recent addition.** The single clearest live signal: a skill / MCP
  / domain was just added that has nothing to do with the profile's stated
  mission. A new seam literally just appeared.

### C. Felt-experience signals (user-reported)
- Agent feels **"dumb," slow, unfocused, spread thin**.
- Sessions feel **noisy** — irrelevant skills firing, off-mission tangents.
- The user **can't describe the profile in one sentence** without "and also."

## Step 2 — Classify each capability

Build the actual map (look, don't guess — read the skills tree, SOUL, MCP list):

```
domain        skills                                    mission-aligned?
-----------   ---------------------------------------   ----------------
companion     companion-presence, felt-time-awareness   YES (core)
research      arxiv, research-paper-writing             maybe
cloud-devops  ev2-*, cloudvault-*, + EV2 MCP fleet       NO (foreign)
```

## Step 3 — Group and find the seam

A **seam** is a cluster that could stand alone as its own profile — it shares
little or no context with the core. Good seams are:
- **Cohesive inside** (the cluster's skills reference each other / one domain).
- **Decoupled outside** (removing it doesn't weaken the core mission).
- **Named-able** (you can give the child a clear one-line mission).

If no such cluster exists — the weight is all one domain — there is **no seam**,
and the right answer is "heavy but healthy, don't split."

## Step 4 — Judge (the decision table)

| Weight | Seam present? | Verdict |
|--------|---------------|---------|
| Low | — | Nothing to do. |
| High | **No** (one deep domain) | Healthy specialist. Do **not** split. |
| Medium–High | **Yes** (foreign cluster / added unrelated) | **Propose the split** — name the seam + child. |
| High | Multiple seams | Propose the **most decoupled** seam first; mention others exist. |

## Heuristics (not thresholds)

- A **foreign MCP server** is the highest-signal seam — its schema cost is large
  and its domain is usually orthogonal. Splitting it off is often the single
  biggest context win.
- **"And also" test.** If describing the profile needs "and also," each "also"
  is a candidate seam.
- **Count is a tiebreaker, not a trigger.** Use skill count only to rank which
  seam to propose first, never as the reason to propose.
- **Coherence beats size.** 40 cohesive skills in one domain > 12 skills across
  four domains, every time.

## What NOT to treat as heaviness

- Deep, cohesive single-domain expertise (that's the goal, not a problem).
- Reference-only / user-invoked skills with `disable-model-invocation: true` —
  they cost cognitive load, not per-turn context; they don't drive a split.
- Temporary task skills the user will remove — don't propose surgery for a
  passing need.
