# Holographic prefetch — traced mechanics

Source-cited walkthrough of how the holographic memory provider injects relevant facts on every turn. Use this when you need to reason about retrieval behavior, debug a "fact didn't fire" report, or decide whether a memory architecture change is needed.

## File map

```
~/.hermes/hermes-agent/
  agent/
    conversation_loop.py        # turn loop, calls memory_manager.prefetch_all
    memory_manager.py           # cross-provider prefetch coordinator
    system_prompt.py            # build_system_prompt: stable + context + volatile
  plugins/memory/
    holographic/
      __init__.py               # HolographicProvider — system_prompt_block, prefetch, sync_turn
      retrieval.py              # FactRetriever — hybrid search, probe, reason
      store.py                  # MemoryStore — SQLite + FTS5 + HRR bytes column
      holographic.py            # HRR vector ops (encode_text, bytes_to_phases, similarity)
```

## Per-turn pipeline (verbatim from source)

1. **`conversation_loop.py:760-778`** — at turn start, before tool loop:
   ```python
   # External memory provider: prefetch once before the tool loop.
   # Cheaper than prefetch_all() on each tool call (10 tool calls = 10x latency + cost).
   _ext_prefetch_cache = ""
   if agent._memory_manager:
       _ext_prefetch_cache = agent._memory_manager.prefetch_all(_query) or ""
   ```
   `_query` is the current user message. Prefetch runs **once per turn**, not per tool call.

2. **`memory_manager.py:339`** — `prefetch_all` iterates every registered provider:
   ```python
   def prefetch_all(self, query: str, *, session_id: str = "") -> str:
       """Collect prefetch context from all providers."""
   ```
   Holographic is one of several possible providers; the install can have more than one. Output is concatenated.

3. **`plugins/memory/holographic/__init__.py:206`** — holographic's contribution:
   ```python
   def prefetch(self, query: str, *, session_id: str = "") -> str:
       if not self._retriever or not query:
           return ""
       try:
           results = self._retriever.search(query, min_trust=self._min_trust, limit=5)
           if not results:
               return ""
           lines = []
           for r in results:
               trust = r.get("trust_score", r.get("trust", 0))
               lines.append(f"- [{trust:.1f}] {r.get('content', '')}")
           return "## Holographic Memory\n" + "\n".join(lines)
   ```
   **Top 5 results, filtered by `min_trust` (default 0.3), formatted as `- [trust] content`, wrapped in a fenced `## Holographic Memory` block.** No content, no injection.

4. **`retrieval.py:48-112`** — `FactRetriever.search` is the hybrid pipeline:
   ```python
   # Stage 1: Get FTS5 candidates (limit*3 for reranking headroom)
   candidates = self._fts_candidates(query, category, min_trust, limit * 3)

   # Stage 2: Rerank with Jaccard + trust + optional decay
   for fact in candidates:
       content_tokens = self._tokenize(fact["content"])
       tag_tokens = self._tokenize(fact.get("tags", ""))
       all_tokens = content_tokens | tag_tokens   # tags count toward overlap

       jaccard = self._jaccard_similarity(query_tokens, all_tokens)
       fts_score = fact.get("fts_rank", 0.0)

       # HRR similarity
       if self.hrr_weight > 0 and fact.get("hrr_vector"):
           fact_vec = hrr.bytes_to_phases(fact["hrr_vector"])
           query_vec = hrr.encode_text(query, self.hrr_dim)
           hrr_sim = (hrr.similarity(query_vec, fact_vec) + 1.0) / 2.0  # [0,1]
       else:
           hrr_sim = 0.5  # neutral

       relevance = (self.fts_weight * fts_score
                   + self.jaccard_weight * jaccard
                   + self.hrr_weight * hrr_sim)
       score = relevance * fact["trust_score"]
       if self.half_life > 0:
           score *= self._temporal_decay(fact.get("updated_at") or fact.get("created_at"))
       fact["score"] = score
   ```

## Default weights (`retrieval.py:25-46`)

```python
fts_weight=0.4
jaccard_weight=0.3
hrr_weight=0.3
hrr_dim=1024
temporal_decay_half_life=0  # disabled
```

If numpy is missing, HRR auto-redistributes: `fts_weight=0.6, jaccard_weight=0.4, hrr_weight=0.0`.

## What this means in practice

### A fact surfaces when…

- The user message tokens overlap with the fact's `content` OR `tags` (tags count!)
- The fact's `trust_score >= min_trust` (default 0.3)
- The fact scores in the top 5 after rerank

### A fact does NOT surface when…

- The user message has no token overlap with content or tags
- Trust is below min_trust
- Five higher-scoring facts crowd it out

### Single most actionable lever

**Tag for retrieval, not categorization.** If you want a fact to fire on a specific trigger, put the trigger words IN THE TAGS. A sleep-guard fact tagged `accountability, the user, standing-rule` will not fire on "I'm tired, going to bed soon" — there's no token overlap. The same fact tagged `sleep, late, evening, night, tired, bed, 9pm, 10pm, 11pm, hours, insomnia, accountability, the user` will fire reliably because the user's message tokens hit the tags.

### Diagnosis recipe when a fact "should have fired"

```python
# Use the literal user message that was supposed to trigger
fact_store(action="search", query="<the actual user message verbatim>", limit=10)
```

Then look at:
- Did the fact appear at all? (FTS5 didn't match → fix tags/content)
- Did it appear but rank low? (Trust score or competing facts → boost via `fact_feedback` after using, or reword for better token overlap)
- Was its trust below 0.3? (Either retrain via feedback or raise the floor in config)

## The system prompt note ≠ retrieval guarantee

`HolographicProvider.system_prompt_block` (`__init__.py:183-204`) emits a static line at session start:

```
# Holographic Memory
Active. <N> facts stored with entity resolution and trust scoring.
Use fact_store to search, probe entities, reason across entities, or add facts.
```

This is **awareness, not retrieval**. The model knows the store exists. Whether a specific fact appears in any given turn's `## Holographic Memory` block depends entirely on the prefetch pipeline above. Do not infer "the agent will remember X" from "the agent knows there are N facts."

## Related layers (not holographic, but co-injected)

- **`agent/system_prompt.py:332`** — appends `"Conversation started: <weekday, month, day, year>"` to the volatile layer. Date-only, deliberately. PR credit: `@iamfoz (PR #20451)`. Comment in source: "Minute-precision changes invalidate prefix-cache KV on every rebuild path."
- **`hooks.pre_llm_call`** in `config.yaml` — output appended to user message before LLM call. See `timestamp-hook-gating-and-pitfalls.md`.
- **MEMORY.md + USER.md** — `~/.hermes/memories/`, snapshot at session start, frozen, char-capped. The `memory` tool's `add/replace/remove` actions persist immediately but only show in NEXT session's prompt.

## When to reach for this reference

- Considering memory weight tuning (`fts_weight`, `jaccard_weight`, `hrr_weight`, `min_trust`, `temporal_decay_half_life`)
- A user-reported "you forgot X" where X was banked — diagnose via search recipe above before changing anything
- Writing a new fact that needs to fire on a specific trigger word
- Deciding whether a rule belongs in always-on memory (MEMORY.md/USER.md) vs holographic — holographic wins for anything that has a clear trigger phrase; always-on wins for context that must be present every turn regardless of conversation drift
