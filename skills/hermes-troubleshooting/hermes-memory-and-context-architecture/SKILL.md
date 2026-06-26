---
name: hermes-memory-and-context-architecture
description: Reference for how Hermes assembles per-turn context — MEMORY.md/USER.md always-on injection, holographic fact_store hybrid prefetch (FTS5+Jaccard+HRR×trust), pre_llm_call hooks (including the local-time injector), session_search FTS5, and how the layers compose at prompt-build time. Load BEFORE making any architectural change to memory, retrieval, or hook configuration — the cost of "tune first, verify later" is a self-imposed mistuning that bites for weeks.
version: 1.0.0
author: Hermes Agent
created_by: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, memory, holographic, hooks, context, architecture, reference]
---

# Hermes Memory & Context Architecture

How Hermes assembles the context the model sees on every turn, and the rules for changing any of it safely. This is a **reference skill** — load it before you reach for a config toggle or memory tool, not after the user catches you guessing.

## When to load

- "How does memory work here?" / "What does the agent actually see?"
- About to set `memory.*`, add/remove a hook, change `provider:`, prune `MEMORY.md` / `USER.md`, or change a `fact_store` weight
- A memory entry "should have fired" but didn't, and you want to diagnose retrieval not assume it
- About to claim "the system can/can't do X" about memory or hooks — load this and verify against the source before answering
- New session and the user is asking how their facts/preferences are surfaced
- Reasoning about **cross-profile continuity** / "one self across many profiles" / why a kanban worker or other profile can't see facts the default agent stored — see `references/per-profile-store-isolation-and-continuity.md` (each profile is a physically separate store; shared-core/scoped-satellite design + `memory_banks` lead)
- The user reports "you broke" / a cascade of `Request Entity Too Large` (HTTP 413) errors, or a session that auto-reset after repeated compression — see `references/payload-413-and-compression-cascade.md` (byte-limit vs token-limit; compaction can't fix an image-bytes 413)

## The four context layers, in order of assembly

Each turn, `agent/conversation_loop.py` + `agent/system_prompt.py` + `agent/memory_manager.py` build the prompt the model sees. Four sources contribute:

| Layer | Source | When injected | Stability | What it carries |
|---|---|---|---|---|
| **1. Always-on memory** | `~/.hermes/memories/MEMORY.md` (2,200 char cap) + `USER.md` (1,375 char cap) | Snapshot at session start, frozen for the session | Stable across the session | "Who the user is + persistent environment facts" |
| **2. Holographic prefetch** | `fact_store` (provider plugin) — SQLite + FTS5 + HRR vectors | Once per turn, before the LLM call, anchored on the user message | Per-turn; top-5 facts surface as a fenced `## Holographic Memory` block | Durable facts that match this turn's user message |
| **3. Pre-LLM hooks** | `hooks.pre_llm_call` in `config.yaml` — external scripts | Per turn, output appended to the current user message | Per-turn | Wall-clock time (local-time injector), any other custom side-channel context |
| **4. Volatile prompt tail** | `agent/system_prompt.py::build_system_prompt` — date line, session id, model, provider | Per turn at the tail of the system prompt | **Date-only**, not minute-precision (prefix-cache stability) | "Conversation started: Day, Month DD, YYYY" + agent identity |

**Implication**: the model has *no passive minute-precision time awareness* by default. The date-line is byte-stable across the day on purpose (preserves prefix-cache KV across rebuild paths: compression boundary, fresh-agent gateway turns, session resume). For minute precision you need either the pre_llm_call timestamp hook (layer 3) or an active `date` shell call.

## Holographic prefetch — what actually runs

When `memory.provider: holographic` is set, every turn runs this pipeline once:

```
user_message
    ↓
fact_store.search(query=user_message, min_trust=0.3, limit=5)
    ↓  (retrieval.py::FactRetriever.search)
1. FTS5 candidates (limit*3) over facts table
2. Jaccard token-overlap rerank (content + tags)
3. HRR vector similarity rerank (if numpy present)
4. score = (fts_w*fts + jac_w*jac + hrr_w*hrr) * trust_score
5. optional temporal_decay = 0.5^(age_days / half_life)
    ↓
top-5 results → formatted as `- [trust] content` lines
    ↓
wrapped in "## Holographic Memory" fenced block
    ↓
injected into current turn's prompt (memory_manager.prefetch_all)
```

**Default weights** (set in `retrieval.py::FactRetriever.__init__`):
- `fts_weight: 0.4`, `jaccard_weight: 0.3`, `hrr_weight: 0.3`
- If numpy is missing the HRR slot auto-redistributes to FTS+Jaccard
- `temporal_decay_half_life: 0` (disabled) by default

**Three things this means for the agent in practice**:
1. **A fact surfaces when the user message contains tokens that match the fact's content or tags.** Not "automatically remembered always" — *retrieved on relevance*. If the user message has no overlap with the fact, the fact will not be in this turn's prompt.
2. **Prefetch runs ONCE per turn, anchored on the user message — not on each tool call.** A fact whose tags would match `"comfy render"` won't fire if the turn opens with `"hi, mornin"` and the render question comes only in the assistant's reasoning. This is deliberate (10× cheaper than per-tool-call prefetch).
3. **`trust_score` is a multiplier on relevance.** A high-trust fact wins ties; a low-trust fact must score very well on text similarity to surface. Calling `fact_feedback` after using a fact is how trust gets trained — actually do it after acting on a retrieved fact, not just when the user explicitly says it was helpful.

## Holographic stores are PER-PROFILE isolated (the continuity topology)

The pipeline above describes retrieval *within one store*. On a multi-profile
box there is **no single store** — each profile has its own physically separate
SQLite file. `db_path` defaults to `$HERMES_HOME/memory_store.db`, and
`$HERMES_HOME` differs per profile (default → `~/.hermes`; a profile →
`~/.hermes/profiles/<name>`). Docs confirm local-storage providers are
"isolated per profile" (`memory-providers.md`). So:

- `memory.provider: holographic` can be set in *every* profile (universal
  capability) while every profile still writes to a **different file**.
- A fact the foreground `default` agent stores is **invisible** to a
  `engineering-profile` kanban worker, and vice versa. Separate ponds, not
  one lake. This is the storage topology, not a retrieval bug.
- The db is created **lazily on first write** — a profile can be configured
  for holographic and have **no store file yet**. "Configured" ≠ "has facts."

**Why this matters:** any "one continuous presence across many profiles /
roles" goal (the ambient-presence / multi-profile-self vision) is blocked by
this topology by default. The roles fragment into separate selves that don't
share a past — "two strangers wearing one name." Do NOT naively "point every
profile at one `db_path`" though: intimate/private lanes
(`private-profile`, `companion-profile`) hold consent-sensitive facts that
must not bleed into engineering/QA contexts. Target shape is **shared CORE +
scoped SATELLITES** with a user-gated shared-vs-scoped taxonomy. The
`memory_banks` table in every store's schema is a partition lead worth
verifying against `holographic.py` before designing a build.

**Audit it (don't infer):** run
`scripts/audit_holographic_stores.py` — inventories every profile's provider,
fact count, db presence, and schema (read-only; counts only, never dumps fact
bodies from private lanes). Two diagnostic gotchas it encodes: the `sqlite3`
CLI binary is **not** guaranteed installed (use python3's stdlib `sqlite3`
module), and reading `memory.provider` per profile needs a **block-aware
parse** (`grep -A3 '^memory:'` misses the provider line ~5 lines down). Full
topology, option space, and migration guardrails:
`references/per-profile-store-isolation-and-continuity.md`.

## Always-on memory — MEMORY.md and USER.md

Two files, both in `~/.hermes/memories/`, both snapshot-loaded at session start and frozen for the session (changes via the `memory` tool are persisted to disk immediately but only appear in the *next* session's prompt):

| File | Cap | For | Format |
|---|---|---|---|
| `MEMORY.md` | 2,200 chars | Agent's notes — environment, conventions, lessons | Entries separated by `§` delimiter, header shows usage % |
| `USER.md` | 1,375 chars | User profile — identity, prefs, communication style | Same `§` format |

Both have **hard caps enforced at write time**. When full, the `memory` tool returns an error with the current entries listed so you can identify what to consolidate. The right move is *replace + merge*, not delete-then-add: substring-matching `old_text` identifies the entry to replace, the new `content` packs multiple related facts into one entry.

**Don't pre-emptively prune always-on memory to make room for a fact whose retrieval mechanism you haven't verified.** See pitfall "Tune first, verify later" below.

### Who actually edits MEMORY.md / USER.md (it's usually NOT the foreground agent)

A foreground turn rarely calls the `memory` tool. Most edits are made by the **background-review agent** — a separate `claude-opus-*` process that runs silently after the foreground reply is delivered, prompted with `"Review the conversation above and consider saving to memory if appropriate. Focus on..."`. It uses its **own session_id and thread** (you'll see `bg-review:` threads in `agent.log`), and its writes show up as `tool memory completed` log lines that the foreground session never produced. Implications for diagnosis:

1. **"What did you most recently update?" cannot be answered from session-DB messages alone** — the bg-review agent doesn't persist its tool calls to the foreground session's message thread in `state.db`. The reliable trail is:
   - `~/.hermes/memories/USER.md` and `MEMORY.md` **file mtime** (ground truth — the disk write is atomic)
   - Cross-reference with `grep "tool memory completed" ~/.hermes/logs/agent.log | tail` for the timestamp + session_id + char count of each edit
   - The 1,375-char USER cap and 2,200-char MEMORY cap are enforced at write time and rejections show up as `WARNING ... Tool memory returned error: Replacement would put memory at X/Y chars`
2. **The bg-review agent's compression is aggressive** — it will rewrite multiple `§`-separated entries on the same call to make room for a new fact under the hard cap. The foreground agent often won't recognize what was changed unless it diffs the file. A common shape: bg-review packs multiple semantic facts into one `§` block using terse abbreviations (`vuln`, `EF`, `comp`) and the user later asks "what does this mean?" — the abbreviation is bg-review's, not the user's vocabulary.
3. **Style implication**: when bg-review compresses, prefer human-readable shorthand the user already uses over your own abbreviations. `executive function` collapsing to `EF` saved characters but the user didn't recognize the abbreviation and had to ask. **Don't invent new abbreviations to save characters — drop the qualifier or merge two entries instead.**

## Pre-LLM hooks — pre_llm_call

Config wiring in `~/.hermes/config.yaml`:

```yaml
hooks:
  pre_llm_call:
  - command: python3 /home/<user>/.hermes/scripts/inject_timestamp.py
    timeout: 5
```

Each hook is a script that:
1. Reads a JSON payload on stdin (turn metadata: `source`, `platform`, etc.)
2. Prints a JSON `{"context": "..."}` on stdout
3. The `context` string is appended to the current turn's user message before the LLM call

The shipped `inject_timestamp.py` is **gated by `HERMES_ENABLE_LOCAL_TIME_CONTEXT`** env var — when truthy, emits a silent-grounding `"Current local time for grounding only: YYYY-MM-DD HH:MM:SS TZ. Use silently for temporal awareness. Do not quote, repeat, or append this timestamp in the user-facing reply."` line. When unset, the hook runs but returns `{}` — no injection. The cron-source guard also skips injection for cron-triggered turns so scheduled messages don't get the prefix.

**This is the gating point for passive wall-clock awareness.** Sleep-guard rules, after-hours nudges, anything time-of-day-dependent needs this hook enabled — the date-only system prompt line is NOT enough.

## session_search — FTS5 over past conversations

Not part of per-turn context assembly, but adjacent: `session_search` queries the full SQLite session store (`~/.hermes/state.db`) with FTS5. Returns actual messages, no LLM summarization. Three calling shapes (discovery / scroll / browse). Useful when "we talked about this before" needs verification — reach for it before claiming a past behavior, decision, or workflow exists or doesn't.

## The verify-before-tuning rule

**Most important rule in this skill, and the reason it exists.**

When the user asks "is X working?" / "how does Y work?" / "should we change Z?" about memory or hooks, **read the source before answering, and verify the actual runtime state before changing anything.** Inferring from documentation, system prompt notes, or prior session memory is not enough. The cost of "tune first, verify later" is a self-imposed mistuning that bites for weeks because:

- Memory and hook behavior is **lazy-loaded and env-gated**. A hook can be wired in config and still be no-op'd by an unset env var (see the `inject_timestamp.py` example above).
- Always-on memory is **session-frozen**. A bad edit doesn't show up until the next session, and by then the cause is forgotten.
- Holographic retrieval is **probabilistic**. A fact "not firing" can be a tag-mismatch, a trust-score issue, a min_trust gate, or a real bug. Diagnose with `fact_store search`, don't assume.
- **The system prompt note that says "89 facts stored with entity resolution"** is not a guarantee the next turn will surface the right one. Verify via the tool, not via inference.

Recovery contract when you've claimed something about memory architecture and the user pushes back:
1. STOP. Do not "fix" by changing config or memory.
2. Read the source: `~/.hermes/hermes-agent/plugins/memory/holographic/`, `~/.hermes/hermes-agent/agent/{memory_manager,conversation_loop,system_prompt}.py`, `~/.hermes/scripts/inject_timestamp.py`, `~/.hermes/config.yaml`.
3. Inspect runtime state: env vars on the running gateway process, config.yaml hook wiring, fact_store search results for the actual query shape that would fire.
4. Report what's actually true (correcting the prior claim explicitly).
5. THEN make the change, with the verified mechanism named in the change rationale.

See `references/holographic-prefetch-mechanics.md` for the full traced pipeline with file/line citations, and `references/timestamp-hook-gating-and-pitfalls.md` for the per-turn injector with worked examples.

## Pitfalls

### Tune first, verify later

**The exact failure shape that motivated this skill (2026-06-03)**: agent claimed "the holographic prefetch only fires probabilistically and the sleep-guard fact won't actually surface — let me prune USER.md to free always-on space for a sleep rule." User stopped the change and asked "read the manual first." Verification revealed: (a) holographic prefetch IS reliable on token-overlap, (b) the sleep guard would have fired on late-night user messages, (c) the real architectural gap was passive time awareness, not memory retrieval, and the fix was a one-line env var (`HERMES_ENABLE_LOCAL_TIME_CONTEXT=1`) for an existing pre_llm_call hook the agent didn't know was already wired. **Always-on memory would have been mistuned to solve a non-problem if the user hadn't intervened.**

### Claiming "no X exists" without grepping plugins + scripts + config

`~/.hermes/plugins/` (user plugins), `~/.hermes/scripts/` (user scripts), `~/.hermes/config.yaml::hooks` (hook wiring) are user-side and live outside the bundled `hermes-agent/` checkout. A claim like "Hermes has no time injection mechanism" based on grepping only the bundled source is wrong by construction — the user can wire any hook via config. Before claiming a capability is absent, check all four locations: bundled `agent/` source, `plugins/memory/<provider>/`, `~/.hermes/plugins/`, `~/.hermes/scripts/`, and the `hooks:` block in `config.yaml`.

### Confusing "the fact is stored" with "the fact will surface"

`fact_store add` puts a fact in the SQLite store. That is necessary but not sufficient for the model to see it next turn. The fact will surface IF the next user message has token overlap with `content` or `tags` AND scores above the `min_trust` floor after rerank. When storing a fact intended to fire on a specific trigger, **bias the tags toward words the user is likely to use in the trigger message** — e.g. a sleep-guard fact should tag `sleep, late, evening, night, tired, bed, 9pm, 10pm, 11pm, hours, insomnia`, not just `accountability, the user, standing-rule`. Tag for retrieval, not just for categorization.

### Changing prefix-cache-stable surfaces casually

The date-line in the system prompt is **deliberately** date-only — minute-precision would invalidate the prefix-cache KV on every rebuild path. Same logic applies to any change in the "stable" or "context" layer of `build_system_prompt`. If you want per-turn variability, put it in the *user message envelope* (the pre_llm_call hook does exactly this) — not in the system prompt. The cost of breaking prefix-cache stability is real and pervasive: every cron run, every fresh gateway turn, every session resume pays the full cache-miss tax forever.

### USER.md and MEMORY.md edits don't take effect until next session

If you `memory action=replace` on USER.md, the change persists to disk immediately but the running session's system prompt is still the frozen snapshot from session-start. Don't make a change and then "verify" by asking yourself within the same session whether it landed — it WON'T be in your context yet, you have to wait for `/reset` or a fresh session.

### Don't promote inferred architectural claims into long-term memory or skills

When you trace a system's behavior, write up what the *source* shows, not what you *think* it does. The "verify-before-tuning" rule applies to skill-writing too: if a SKILL.md claims a specific retrieval algorithm or hook behavior, the claim should cite the source file and the line range, not just be a recollection from a prior session. See `references/holographic-prefetch-mechanics.md` for the example shape.

## Quick reference — common questions

**"Does the agent know what time it is?"** Date yes, minute no — unless `HERMES_ENABLE_LOCAL_TIME_CONTEXT=1` is set in the gateway's environment AND the `inject_timestamp.py` pre_llm_call hook is wired in config.yaml.

**"Will fact #N fire on this user message?"** Run `fact_store search` with the literal user message as the query. If it returns the fact above min_trust, yes. If not, fix the fact's tags or content, not the user.

**"Why isn't MEMORY.md content showing up in my context this turn?"** It IS — system prompts are snapshotted at session start, frozen for the session. The block exists; you're looking past it. If a recent `memory action=add` doesn't show: changes only apply on next session start.

**"Can I add a custom per-turn injection?"** Yes — write a script that reads JSON on stdin, prints `{"context": "..."}` on stdout, wire it under `hooks.pre_llm_call` in `config.yaml`. Mirrors the timestamp hook exactly.

**"Should I prune USER.md to make room?"** Only after verifying that the rule you're trying to make always-on can't be served by a well-tagged holographic fact with retrieval-friendly tag words. Always-on space is precious; most rules are fine in holographic.

**"The agent 'broke' / threw a wall of `Request Entity Too Large` (413) errors / a session auto-reset on its own — what happened?"** Almost always a **byte-size** limit, not a token limit. Multi-MB images (base64) in a long session blow the request-body cap even when token count is fine. Compaction can't fix it (it summarizes text, not images), so it cascades through 3 compress attempts → `Cannot compress further` → `Auto-resetting session after compression exhaustion`. Diagnose: token count *plateaus low while 413 persists* = byte problem. The transcript survives (auto-reset ends, doesn't delete); only in-flight loop state is lost. Full mechanism + log signatures + fix in `references/payload-413-and-compression-cascade.md`.

**"What did the agent most recently add to MEMORY.md / USER.md, and when?"** Don't search the foreground session's messages — the edit was almost certainly done by the background-review agent and won't appear in the foreground session's thread. Instead: (1) `stat -c '%y %n' ~/.hermes/memories/USER.md ~/.hermes/memories/MEMORY.md` for the disk-write timestamp (ground truth), (2) `grep "tool memory completed" ~/.hermes/logs/agent.log | tail` to confirm the matching tool call + session_id + char count, (3) `read_file ~/.hermes/memories/USER.md` to see the current state. If the user is asking specifically *what changed*, only the bg-review's source assistant message would have the diff — which usually isn't persisted to state.db at all. The most honest answer combines current file content + mtime + log timestamp, named as "the most recent write, made by the background-review agent."

## See also

- `hermes-self-update-maintenance` — sibling skill, covers the upgrade pipeline; this skill covers in-session context assembly
- `hermes-agent` (bundled, protected) — user-facing config/CLI reference; this skill is the runtime-architecture counterpart

## References

- `references/holographic-prefetch-mechanics.md` — full traced pipeline with file/line citations for the per-turn hybrid retrieval
- `references/timestamp-hook-gating-and-pitfalls.md` — the inject_timestamp.py hook: wiring, env-gate, cron-source guard, worked examples for sleep-guard / after-hours nudges
- `references/background-review-agent-memory-edits.md` — the bg-review agent that actually authors most MEMORY/USER edits: how to find what it wrote, why its writes are invisible from the foreground session, and the "abbreviation surprise" pitfall
- `references/payload-413-and-compression-cascade.md` — the byte-limit vs token-limit distinction behind HTTP 413 `Request Entity Too Large`: why multi-MB images cascade through compaction into auto-reset, the log signatures, the relevant `conversation_loop.py` source lines, and the downscale-images fix
- `references/per-profile-store-isolation-and-continuity.md` — holographic stores are physically separate per profile (the cross-profile continuity topology): the verified fragmentation, the `sqlite3`-CLI-absent + block-aware-config-parse diagnostic gotchas, the `memory_banks` partition lead, the shared-core/scoped-satellite option space, and migration guardrails
- `scripts/audit_holographic_stores.py` — read-only probe inventorying every profile's holographic store (provider, fact count, db presence, schema); python3-stdlib (no `sqlite3` CLI dependency), counts only (never dumps private-lane fact bodies)
