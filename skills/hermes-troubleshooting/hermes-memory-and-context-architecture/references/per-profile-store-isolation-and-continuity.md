# Holographic stores are per-profile isolated — the continuity topology

The umbrella SKILL.md describes holographic prefetch as if there is *one*
fact store. On a multi-profile box there is not. **Each profile has its own
physically separate SQLite store**, and that isolation is the single most
important fact when reasoning about cross-profile memory / continuity.

## The verified mechanism (<main-host>, 2026-06-16)

- `memory.provider: holographic` is set in `default` **and** every profile
  under `~/.hermes/profiles/<name>/` — the *capability* is universal.
- But `db_path` defaults to `$HERMES_HOME/memory_store.db`, and
  `$HERMES_HOME` differs per profile (default → `~/.hermes`; a profile →
  `~/.hermes/profiles/<name>`). So every profile writes to a **different
  file**. Docs confirm: local-storage providers (Holographic, ByteRover)
  are "isolated per profile" —
  `website/docs/user-guide/features/memory-providers.md`.
- Result on a multi-profile box at audit time: **separate ponds**, not one lake.
  e.g. `default` 151 facts, `assistant-a` 18, `assistant-b` 7,
  `planner` 6, and several other profiles each with their own small
  store; some profiles show 0 (db exists, empty); and **some profiles
  configured but with no db file yet** — the db is
  created lazily on first write, so "configured" ≠ "has a store."

So a fact written by the foreground `default` agent is **invisible** to a
secondary-profile kanban worker, and vice versa. This is not a bug in
retrieval — it is the storage topology.

## The two diagnostic gotchas that bit (capture so they don't again)

1. **`sqlite3` CLI is not guaranteed installed.** It was absent on
   <main-host>. Use python3's stdlib `sqlite3` module instead — always
   present. The packaged `scripts/audit_holographic_stores.py` does this.
   (Do NOT write a memory/skill saying "sqlite3 is broken" — it's an
   environment-state absence, not a durable fact. The durable lesson is
   *prefer the python3 stdlib probe.*)
2. **Reading `memory.provider` per profile needs a block-aware parse.** A
   naive `grep -A3 '^memory:' config.yaml` MISSES the provider line — the
   key sits ~5 lines under the `memory:` block. The audit script walks the
   top-level `memory:` block with a small state machine. The first grep
   attempt in the session returned `<inherit/none>` for everything and was
   wrong; the block-aware read showed all 16 profiles on holographic.

## The schema lead: `memory_banks`

Every store's schema is:
`facts, sqlite_sequence, entities, fact_entities, facts_fts,
facts_fts_data, facts_fts_idx, facts_fts_docsize, facts_fts_config,
memory_banks`.

The **`memory_banks` table is a partition lead.** If holographic already
supports bank-scoped facts AND `fact_store` exposes bank selection +
cross-bank reads, then a "shared household-continuity CORE + per-profile
private SATELLITES" design could be **mostly config, not a build**. This is
a hypothesis to verify against
`~/.hermes/hermes-agent/plugins/memory/holographic/holographic.py`, not yet
a confirmed capability.

## The continuity design tension (do NOT just merge all ponds)

When the goal is Starbright-as-one-continuous-presence across many profiles,
the naive fix ("point every profile at one `db_path`") is wrong, because
**some scopes must stay isolated**:

- Intimate / private lanes (`private-profile`, `companion-profile`) hold
  consent-sensitive content that must NOT bleed into engineering / QA /
  tutor contexts.
- A client-codebase profile's facts shouldn't leak into the household.

Target shape: **shared CORE + scoped SATELLITES**, with an explicit policy
for which facts are shared vs scoped. Defining that taxonomy is a
values/privacy decision → **gate it on the user.** The mechanism to
implement it is plumbing → recommend + proceed once the taxonomy is signed
off. When auditing the private-lane stores, **count only — never dump fact
bodies** (the audit script enforces this).

## The option space (for a design memo, all to be verified against source)

1. **Single shared `db_path`** — all/some profiles → one file. Must address
   SQLite concurrency under real concurrent writers (kanban workers + cron
   watchers): WAL mode, `busy_timeout`, how the plugin opens connections.
2. **Shared physical DB + `memory_banks`** — shared core bank + per-profile
   private banks. Verify `fact_store` bank selection + cross-bank reads.
3. **Per-profile dbs + a sync/replication process** propagating
   shared-tagged facts. Must address dedup, trust-score merge, eventual
   consistency.
4. **Multi-host horizon** — a single SQLite file on a network share is a
   corruption footgun. Multi-host sharing likely needs a memory SERVICE or
   replication, NOT a shared file. Cloud providers (Honcho/Mem0/etc.) solve
   multi-host natively but trade away local-only privacy — strong prior
   toward staying local on a private "soul device" with an intimate lane.
   Stage it: single-host-now and multi-host-later may be different
   mechanisms.

Guardrail for any eventual migration: **verified backups of every store
touched first** (assume these dbs are NOT in chezmoi — likely gitignored),
and **preserve trust scores + entity links** across the move.

## Quick audit

`python3 ~/.hermes/skills/hermes-troubleshooting/hermes-memory-and-context-architecture/scripts/audit_holographic_stores.py`

Prints the per-profile provider + fact-count + db-presence table and flags
the `memory_banks` lead. Read-only, content-safe.
