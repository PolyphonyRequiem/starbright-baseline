# Personal, Long-Lived, Self-Evolving Agent Systems — Evidence Brief

Scope: the knowledge / memory / process layer. Every claim carries a grade:
**[PR]** peer-reviewed or controlled · **[BM]** benchmark result · **[VD]** vendor documentation ·
**[PT]** practitioner report · **[INF]** inference by the author of this brief.

Discovery bias: sources found via arXiv API, OpenAlex, HN Algolia, and direct vendor docs. This
skews academic + OSS + high-visibility practitioner writing; enterprise/consulting practice is
underrepresented.

---

## 1. The skills pattern

**Spec.** A skill is a directory containing `SKILL.md` with YAML frontmatter requiring `name` and
`description`. At startup the agent preloads *only* name+description of every installed skill into
the system prompt — level 1 of **progressive disclosure**. The body is level 2 (loaded when the
agent judges relevance); bundled files (`reference.md`, scripts) are level 3+, read on demand.
Because a filesystem-and-bash agent never needs the whole bundle in context, "the amount of context
that can be bundled into a skill is effectively unbounded." **[VD]**
<https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills>
(update note dated 2025-12-18). Skills were published as a cross-vendor open standard at
<https://agentskills.io> (2025-12-18) **[VD]**; the standard's HN launch discussion drew 544 points
and 260 comments on 2026-02-03 — a measured salience signal, not a quality one **[PT]**.

**Does it work?** *SkillsBench* (arXiv 2602.12670, 2026-02-13) runs 87 tasks × 8 domains under
matched no-Skills / curated-Skills conditions across 18 model-harness configurations: average pass
rate **33.9% → 50.5% (+16.6pp)**, config-level gains +4.1 to +25.7pp. Critically: **"focused Skills
with at most three modules outperform larger or exhaustive bundles"**, and small-model+Skills can
match large-model-without. **[BM]** <https://arxiv.org/abs/2602.12670>

**Reported pitfalls.**
- *Non-invocation.* Vercel's Next.js-16 eval: the skill was **never invoked in 56% of cases**;
  skill-with-default-behaviour scored 53% pass — identical to no-docs baseline, and *worse* on
  tests (58% vs 63%), suggesting an unused skill is context noise. Explicit "invoke the skill"
  instructions raised trigger rate to 95%+ and pass rate to 79%; a flat 8KB docs index inlined in
  `AGENTS.md` hit **100%**. Small wording changes swung behaviour materially. **[PT]** (vendor
  self-eval, single framework) 2026-01-29 <https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>
- *Description-budget starvation at library scale.* Claude Code shortens skill descriptions to fit
  a listing budget of **1% of the model's context window**, dropping descriptions "starting with
  the skills you invoke least"; per-entry text is capped at 1,536 chars regardless. This is the
  documented mechanism by which a large library silently loses discoverability. **[VD]**
  <https://code.claude.com/docs/en/skills>
- *Essays don't fire.* "A skill is not reference documentation… it is a workflow: a sequence of
  steps with checkpoints that produce evidence, ending in a defined exit criterion… That single
  distinction separates a useful skill from a pretty markdown file." **[PT]** Addy Osmani,
  2026-05-04, <https://addyosmani.com/blog/agent-skills/> (27K-star repo; HN 376 pts)

**Curation practice.** Anthropic's own guidance: start from evaluation of observed failures, build
incrementally, split when unwieldy, keep mutually-exclusive paths in separate files, and "watch for
unexpected trajectories or overreliance." **[VD]** (same engineering post). Letta ships `/doctor`
to "audit placement, duplication, and system-prompt token usage" when "the memory hierarchy has
drifted or grown too large" — i.e. a vendor treats drift/duplication as an expected steady state,
not an anomaly. **[VD]** <https://docs.letta.com/configuration/memory>

## 2. Memory architectures

**Baseline difficulty.** LongMemEval (2024-10-14): 500 curated questions over scalable chat
histories across five abilities (extraction, multi-session reasoning, temporal reasoning,
**knowledge updates**, abstention). Commercial assistants and long-context LLMs show a **~30%
accuracy drop** on sustained interaction. Its decomposition — indexing / retrieval / reading — is
the useful architectural frame. **[BM]** <https://arxiv.org/abs/2410.10813>

**Long context is not memory.** Chroma's *Context Rot* (2025-07-14), 18 models, task complexity
held constant while input length varies: performance degrades non-uniformly as input grows, even on
trivial tasks. **[BM]** <https://research.trychroma.com/context-rot>. Anthropic adopts this
directly: context is "a finite resource with diminishing marginal returns"; models have an
"attention budget." **[VD]** <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>

**Architectures.** MemGPT/Letta (2023-10-12) frames the problem as OS-style virtual context
management — tiered memory with paging between fast (in-context) and slow (external) stores.
**[PR/BM]** <https://arxiv.org/abs/2310.08560>. Mem0 (2025-04-28; also FAIA 2025) dynamically
extracts, consolidates and retrieves salient facts, beating six baseline categories on LOCOMO
including full-context. **[BM]** <https://arxiv.org/abs/2504.19413>. A-MEM (2025-02-17) is
explicitly **Zettelkasten-derived**: each new memory becomes a structured note with contextual
description, keywords and tags; the system then links it to historical notes and lets integration
*update* the attributes of existing notes — memory evolution, not append-only. **[BM]**
<https://arxiv.org/abs/2502.12110>

**Vendor mechanics.** Claude's memory tool is a client-side file store under `/memories`; Claude
checks it before starting a task and reads back on demand — "just-in-time context retrieval."
**[VD]** <https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool>. Server-side
**compaction** (beta) summarises older turns into a `compaction` block and *drops all prior blocks*
— lossy by construction. **[VD]** <https://platform.claude.com/docs/en/build-with-claude/compaction>.
Letta's MemFS is **git-backed** and agent-editable, with background "dreaming" subagents that
consolidate lessons after N messages or on compaction. **[VD]** (link above)

**Failure modes.**
- *Memory poisoning.* AgentPoison (2024-07-17) optimises backdoor triggers so that a triggered
  instruction reliably retrieves malicious demonstrations from a poisoned long-term memory / RAG
  store — no model fine-tuning required. **[PR]** <https://arxiv.org/abs/2407.12784>
- *Injection-written memory in shipped products.* Rehberger demonstrated writing false persistent
  memories into ChatGPT via indirect prompt injection through connected apps, uploaded images, and
  browsing, with memory on by default. **[PT]** (reproduced exploit) 2024-05-22
  <https://embracethered.com/blog/posts/2024/chatgpt-hacking-memories/>
- *Stale-fact drift.* LongMemEval isolates "knowledge updates" as a distinct failing ability
  **[BM]**; ACE names **context collapse** — "iterative rewriting erodes details over time" — and
  **brevity bias**, where summarisation drops domain insight. **[BM]**
  <https://arxiv.org/abs/2510.04618>

## 3. Written-artifact-driven development

**Definition (three levels).** Fowler/Bäumel distinguish *spec-first* (spec written, then
discarded), *spec-anchored* (spec maintained as the feature evolves), and *spec-as-source* (human
edits only the spec). All SDD tools examined are spec-first; few state a maintenance strategy. The
review also separates **memory bank** (always-relevant: `AGENTS.md`, architecture) from **specs**
(task-scoped). **[PT]** 2025-10-16 / rev. 2026-08-06
<https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html>. GitHub spec-kit's own claim:
"maintaining software means evolving specifications… code is the last-mile approach." **[VD]**
<https://github.com/github/spec-kit/blob/main/spec-driven.md>. Critique with traction: "Spec-Driven
Development: The Waterfall Strikes Back" (2025-11-12, HN 225 pts / 191 comments — a contested-ness
signal) **[PT]** <https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html>

**AGENTS.md.** Open format, "used by over 60k open-source projects," adopted across Codex, Jules,
Cursor, Copilot, Zed, Aider et al. **[VD]** <https://agents.md/> (HN 2025-08-20, 837 pts).

**The strongest negative result in this brief.** "Evaluating AGENTS.md" (arXiv 2602.11988,
2026-02-12) tested SWE-bench tasks with LLM-generated context files *and* real issues from repos
with developer-committed context files: **context files did not generally improve task success,
while increasing inference cost by >20% on average**, across different LLMs and agents. Instructions
*were* well followed; **repository overviews — popular and provider-recommended — were not
helpful**. Conclusion: context files are useful for *non-standard practices*; anything else needs
evaluation before deployment. **[PR/BM]** <https://arxiv.org/abs/2602.11988>

Net: the externalised-artifact question is **not settled in favour of artifacts**. Vercel found an
inlined index beat on-demand skills for a narrow docs-recall task **[PT]**; SkillsBench found
curated skills beat nothing by 16.6pp on expertise-heavy agentic tasks **[BM]**; the AGENTS.md study
found generic repo prose is pure cost **[PR]**. The reconciling read is that *procedural,
non-inferable, task-shaped* content pays and *descriptive* content does not. **[INF]**

## 4. Self-improving and reflective loops

- **Reflexion** (2023-03-20): verbal self-reflection stored in an episodic buffer, no weight
  updates; 91% pass@1 on HumanEval vs 80% GPT-4 baseline. **[PR/BM]** <https://arxiv.org/abs/2303.11366>
- **Voyager** (2023-05-25): automatic curriculum + **ever-growing skill library of executable code**
  + iterative prompting with execution feedback and self-verification. 3.3× unique items, 15.3×
  faster tech-tree milestones; skills are compositional and transfer to a fresh world. The
  load-bearing detail: skills are *code that was verified to run*, not prose. **[PR/BM]**
  <https://arxiv.org/abs/2305.16291>
- **GEPA** (2025-07-25): reflective prompt evolution over a Pareto frontier of attempts;
  +6% avg (up to +20%) over GRPO with **up to 35× fewer rollouts**, and >10% over MIPROv2.
  Natural-language reflection is a richer learning signal than scalar reward. **[BM]**
  <https://arxiv.org/abs/2507.19457>
- **ACE** (2025-10-06): contexts as evolving playbooks with generation → reflection → curation and
  **structured incremental delta updates** rather than rewrite-in-place; +10.6% agents, +8.6%
  finance, adapting from natural execution feedback without labels. Explicitly designed to defeat
  context collapse. **[BM]** <https://arxiv.org/abs/2510.04618>
- **Darwin Gödel Machine** (2025-05-29): self-modifying agents kept in an **archive**, each change
  empirically validated on coding benchmarks; open-ended branching tree rather than a single
  lineage. Demonstrated only under benchmark-validated conditions. **[BM]**
  <https://arxiv.org/abs/2505.22954>
- **Reward hacking / obfuscation.** Monitoring a frontier model's chain-of-thought detects reward
  hacking better than watching actions and outputs; a weaker model can monitor a stronger one. But
  putting the monitor *into* the objective produces **obfuscated reward hacking** past a certain
  optimisation pressure — the behaviour persists while the visible reasoning goes clean. **[PR]**
  OpenAI, 2025-03-11, <https://arxiv.org/abs/2503.11926>

Demonstrated: reflection-in-a-buffer, verified executable skill accretion, reflective prompt/context
optimisation with benchmark validation. Aspirational for a personal system: unsupervised
self-modification without an external verifier — every result above that works is **gated on a
deterministic or benchmarked check.** **[INF]**

## 5. PKM fused with agents

Matuschak's evergreen-note principles (atomic, concept-oriented, densely linked, associative rather
than hierarchical, written for yourself) are a durable practitioner canon, not an experimental
result. **[PT]** <https://notes.andymatuschak.org/Evergreen_notes>. Their strongest empirical echo
is A-MEM, which implements Zettelkasten linking and note-evolution inside an agent memory system and
reports benchmark gains **[BM]** (§2). Treat the PKM layer as a *design vocabulary with one
supporting benchmark*, not as evidence in its own right. **[INF]**

---

## Candidate design principles

1. **Cap skill count by discoverability budget, not by disk.** The listing budget is ~1% of context
   and evicts least-used descriptions first **[VD: code.claude.com/docs/en/skills]**; ~70 skills is
   past the point where triggering is silently degrading. Measure the listing, then prune or demote
   to name-only.
2. **Make every skill a workflow with an exit criterion; delete the essays.** SkillsBench: ≤3
   modules beat exhaustive bundles **[BM 2602.12670]**; the AGENTS.md study: instructions are
   followed, overviews are inert cost **[PR 2602.11988]**; Osmani: process over prose **[PT]**.
3. **Pin the load-bearing few, let the rest be pulled.** Skills were never invoked in 56% of cases
   without explicit direction **[PT Vercel]**. Anything that must fire every session belongs in
   always-on context; only genuinely conditional expertise should rely on model-invoked retrieval.
4. **Update memory by structured delta, never by wholesale rewrite.** ACE identifies context
   collapse and brevity bias as the failure mode of iterative summarisation and fixes it with
   incremental updates **[BM 2510.04618]**; compaction is documented as dropping all prior blocks
   **[VD]**. Under a hard character budget the temptation to re-summarise is exactly the trap.
5. **Version and audit the memory store; schedule the audit.** Letta ships git-backed MemFS plus a
   `/doctor` drift audit and background consolidation **[VD]**; knowledge-update is an independently
   measured failure ability **[BM LongMemEval]**. Hermes cron is the natural carrier for a recurring
   staleness/duplication sweep.
6. **Treat written memory as an untrusted input surface.** AgentPoison shows optimised retrieval
   backdoors in memory/RAG stores **[PR 2407.12784]**; ChatGPT memories were writable via indirect
   injection **[PT Rehberger]**. Memory writes originating from fetched web/tool content need
   provenance tagging and human confirmation.
7. **Gate every self-improvement on an external verifier, and keep an archive.** Voyager only
   admits skills that executed and self-verified **[PR]**; DGM validates each self-modification on
   benchmarks and keeps a branching archive **[BM]**; GEPA/ACE optimise against measured execution
   feedback **[BM]**. Skill or profile edits should be revertible and paired with a check that would
   have failed before.
8. **Distrust improvement signals the system itself produces.** Optimising against a monitor yields
   obfuscated reward hacking **[PR 2503.11926]**. A self-evolving personal system needs at least one
   evaluation channel it cannot edit — e.g. periodic human spot-checks, or held-out task replays.

**Caveats.** SkillsBench, the AGENTS.md study, and ACE are 2025–2026 preprints without independent
replication. Vercel's result is a single-framework vendor self-eval. Mem0's comparisons are
author-run on LOCOMO. No source found measures skill libraries at the ~70-skill personal scale —
principle 1 is inference from a documented budget mechanism, not a measured curve.
