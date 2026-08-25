# Where sustained AI-assisted engineering diverges from the demo

**Compiled 2026-08-06.** Evidence grades: **[CAUSAL]** randomized/controlled · **[OBS]** field telemetry or observational · **[SURVEY]** self-report · **[VENDOR]** first-party claim · **[INFER]** synthesis, not measured. Contested findings are marked as contested; nothing here should be read as settled.

---

## 1. Controlled studies of productivity

**METR, 2025-07-10 — [CAUSAL].** Randomized at task level: 16 experienced open-source maintainers, 246 real issues in repositories they already knew, mostly Cursor + Claude 3.5/3.7. AI-allowed tasks took **19% longer**. Developers forecast a 24% speedup beforehand and *still believed* they had been ~20% faster afterward. https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/
*Criticisms, all real:* n=16 is small; the population is the most-expert-in-this-codebase case, which is where AI help is weakest; tool generation is now historical; participants were partly new to Cursor. METR itself does not claim this generalizes to all developers or 2026 tooling. **The robust part is the perception gap, not the −19% number.**

**METR follow-up, 2026-02-24 — [CAUSAL, inconclusive].** Later cohorts showed apparent speedups, but the estimate was judged unreliable: 30–50% of developers *withheld* tasks they especially wanted AI for, and concurrent-agent time was hard to attribute. https://metr.org/blog/2026-02-24-uplift-update/ Design implication: once adoption is real, AI-vs-no-AI experiments start to break as a measurement instrument.

**Cui et al., Management Science, 2026-02-27 — [CAUSAL].** Three enterprise RCTs (Microsoft, Accenture, a Fortune 100), pooled **4,867 developers**, AI *code completion*: **+26.1% completed tasks (SE 10.3%)**, with larger gains for less-experienced developers. https://doi.org/10.1287/mnsc.2025.00535 *Bound:* completions, not autonomous agents; task counts, not accepted value; individual sites were noisy.

**Butler et al., "Dear Diary", ICSE-SEIP 2025-04-27 — [CAUSAL + diary].** 200+ engineers, workplace trial plus three-week diaries. Sustained use raised usefulness and enjoyment but **did not change trust in generated code**; diaries repeatedly describe "almost right" output where verification consumes the gain. https://arxiv.org/abs/2410.18334

**HULA at Atlassian, ICSE-SEIP 2025-04-27 — [OBS, deployed agent].** 663 Jira issues: 527 plans → 433 approved → 376 code generations → **95 PRs → 56 merged (~8% of initiated issues)**. File-localization recall was 86% on SWE-bench but **30%** on real internal issues. Only 33% of 109 surveyed practitioners agreed the code solved the task without adjustment. https://arxiv.org/abs/2411.12924 This is the single most useful funnel in the literature.

**Counterweight — Microsoft CLI-agent rollout, 2026-07-01 preprint — [OBS].** Tens of thousands of engineers adopting Claude Code / Copilot CLI merged **~24% more PRs** than counterfactual estimates over four months. https://arxiv.org/abs/2607.01418 *Bound:* merged-PR count is an output proxy, not value or quality; rollout is not random assignment. Read METR and this together: they are measuring different populations, tasks, tool classes, and outcomes — do not average them.

## 2. Surveys: adoption is high, trust is not

**Stack Overflow 2025 — [SURVEY].** 46% distrust AI accuracy vs 33% who trust it; **66% cite "almost right, but not quite"** as the top frustration; **45.2%** say debugging AI-generated code is *more* time-consuming. Agents were not yet mainstream: 14.1% daily, 37.9% no plans. https://survey.stackoverflow.co/2025/ai

**DORA 2025-09-23 — [OBS/SURVEY].** ~5,000 respondents. AI adoption associates **positively with throughput and negatively with delivery stability**; value is moderated by platform quality, tests, VCS discipline, and fast feedback. Framing: AI is an *amplifier* of existing organizational strength. https://dora.dev/research/2025/dora-report/ *Caveat:* observational, and Google is an AI vendor.

**JetBrains 2025 — [SURVEY].** 24,534 developers; **66% don't believe (or aren't sure) current metrics reflect their real contribution** — relevant because it means self-report is the dominant evidence class in a domain where self-report is demonstrably biased (METR). https://www.jetbrains.com/lp/devecosystem-2025/

**BNY Mellon, "Beyond the Commit", 2026 — [SURVEY].** 2,989 responses: **86% satisfied**, yet ~60% report **under one hour saved per week**; satisfaction↔time-saved correlation only r=0.34. https://arxiv.org/abs/2602.03593 Satisfaction is not throughput.

**GitHub Copilot code review, 2026-03-05 — [VENDOR telemetry].** 60M reviews, >1 in 5 reviews on GitHub, 71% "actionable feedback". No published false-positive rate, defect-removal rate, or control comparison. Evidence of scale, not of quality. https://github.blog/ai-and-ml/github-copilot/60-million-copilot-code-reviews-and-counting/

## 3. Review burden and maintainer load

**curl, 2025-07-14 — [OBS, single project].** ~20% of all 2025 security submissions were AI slop; genuine-vulnerability rate fell to **~5%**, and the maintainers publicly considered ending the bug bounty. https://daniel.haxx.se/blog/2025/07/14/death-by-a-thousand-slops/ Generalizes as a *mechanism*: when generation cost collapses and review cost does not, the reviewing side becomes the bottleneck and eventually withdraws. It does not generalize as a rate.

**Human review effectiveness — [CAUSAL, adjacent domains].** The strongest transferable results are not from software:
- Explanations increase acceptance of AI advice **regardless of correctness** (Bansal, CHI 2021, https://doi.org/10.1145/3411764.3445717); they reduce overreliance only when they lower *verification cost* (Vasconcelos 2022, N=731, https://arxiv.org/abs/2212.06823).
- Cognitive forcing reduces overreliance (N=199) but is rated **worst** by users — quality and satisfaction trade off directly (Buçinca 2021, https://doi.org/10.1145/3449287).
- Commit-before-reveal ordering cut agreement with AI **at no time cost** (19 radiologists, Fogliato FAccT 2022, https://doi.org/10.1145/3531146.3533193).
- Pre-classifier degradation: CAD mammography, 625,625 exams / 271 radiologists — within-reader sensitivity was **worse** with the aid, OR 0.53 (0.29–0.97) (Lehman 2015, https://doi.org/10.1001/jamainternmed.2015.5231). Anti-automation-bias training fixes *commission* errors but not *omission* — not looking where nothing was flagged (Skitka 2000).
- Human+AI teams average **worse than the better of human-alone or AI-alone** across 106 experiments / 370 effect sizes (Vaccaro, Nature Human Behaviour 2024, https://doi.org/10.1038/s41562-024-02024-1).
- Conditional delegation — the human authors *rules* about when to trust, rather than judging each item — improved team performance including out-of-distribution (Lai, CHI 2022, https://doi.org/10.1145/3491102.3501999).

*Known gap:* no study exists of an engineer triaging their own agent's output at volume. All of the above is transfer by analogy — **[INFER]** at the application step.

## 4. Code quality, churn, duplication

**GitClear, 2025 — [OBS, vendor-analyst].** 211M changed lines, 2020–2024, across repos incl. Google/Microsoft/Meta: **~4x growth in duplicated code blocks**, rising short-term churn, declining "moved" lines (the refactoring/reuse signal), and copy-paste exceeding moved code **for the first time on record**. https://www.gitclear.com/ai_assistant_code_quality_2025_research
*Methodological caveats that matter:* GitClear sells the analytics product making the claim; AI attribution is inferred from commit patterns, not instrumented; the population is self-selected customer repos; correlation with the AI-adoption timeline is not causation (remote work, hiring cycles, and language mix shifted over the same window). Treat direction as suggestive, magnitude as unverified.

**Security quality — [CAUSAL].** Perry et al., CCS 2023: participants with an AI assistant wrote **significantly less secure code** while being **more likely to believe it was secure**. https://doi.org/10.1145/3576915.3623157 Same overconfidence signature as METR, in a different measurement domain.

## 5. Security and supply chain

**Invariant Labs, GitHub MCP toxic flow, 2025-05-26 — [CAUSAL reproduction, not prevalence].** A malicious *public* issue prompt-injected an MCP-connected agent into reading private-repo data and leaking it through a public PR. Architecture-level, not a GitHub bug. https://invariantlabs.ai/blog/mcp-github-vulnerability

**Lethal trifecta, 2025-06-16 — [INFER, well-argued].** Private data + untrusted content + external communication in one agent context = exfiltration is available to any attacker who can place text in the context. https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ No reliable prompt-injection defense exists as of this writing.

**Nx "s1ngularity", 2025-08-26 — [OBS incident].** Compromised npm package **weaponized installed AI CLIs (Claude, Gemini, q)** for reconnaissance and exfiltration of SSH keys and tokens; second wave flipped private repos public. First known case of developer AI assistants being used as attack tooling. https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware

**Internet-facing MCP servers at scale, 2026-07-31 preprint — [OBS measurement].** 640 confirmed production servers, 414 dynamically audited: **91.8% lacked OAuth**, 687 tool instances exposed shell execution without access controls, 68 reportable vulnerabilities (SQLi, SSRF to cloud metadata, prompt-template injection, path traversal), and **41.6% vanished within three days** between runs. https://arxiv.org/abs/2608.00150 Preprint, single team, tooling not independently replicated — but the OAuth and shell-exposure figures are the most concrete MCP-hygiene data available.

## 6. Context rot / why long sessions decay

**Chroma, 2025-07 — [CAUSAL, benchmark-controlled].** 18 models (Claude 4/3.7/3.5, GPT-4.1 family, o3, Gemini 2.5, Qwen). Holding task difficulty constant and varying *only* input length, performance degrades **non-uniformly** — including on trivial tasks like replicating repeated words. Semantic (non-lexical) needles degrade far faster than lexical ones; distractors compound; haystack structure matters. Near-perfect Needle-in-a-Haystack scores do not indicate long-context health. https://research.trychroma.com/context-rot Code: https://github.com/chroma-core/context-rot
*Bound:* synthetic tasks; does not directly measure agent trajectories. But it removes the "we have a 1M window, just put everything in" argument: **how information is present matters more than whether it is present.** Long agent sessions decay because they monotonically accumulate distractors, superseded plans, and failed attempts — the exact conditions the study shows are harmful.

---

# Anti-goals for a personal agentic engineering system

Each is tied to the evidence above. Ordered by strength of support.

1. **Do not trust your own felt speedup as a signal.** METR is the only study that measured belief and reality on the same tasks and they diverged by ~39 points. Instrument accepted outcomes (merged, survived review, not reverted within 30 days) or you are steering on a known-biased instrument. *[CAUSAL]*
2. **Do not optimize for generated volume — PRs, lines, agent runs.** HULA's real conversion was ~8% of initiated issues to merged. Any dashboard that rewards generation will make the funnel worse while looking better. Measure **human attention per accepted outcome**. *[OBS]*
3. **Do not point agents at the code you know best and expect a win.** That is precisely the METR population where AI was net-negative. Aim agents where *verification is cheaper than production*: tests, boilerplate, docs, bounded transformations, exploratory lookup, first drafts. *[CAUSAL + diary]*
4. **Do not build a rubber-stamp review surface.** Explanations increase acceptance whether or not the output is correct; the CAD result shows a pre-classifier can make an expert *worse* within-reader. Prefer commit-before-reveal (form your own expectation before seeing the diff/verdict — free per Fogliato), and cheap independent verification (tests, types, a second harness) over more persuasive AI prose. *[CAUSAL]*
5. **Do not scale review by adding more human eyes.** Two-person crews were no better than solo at catching *unflagged* events; single-vs-double screening evidence is weak. Structural checks beat additional attention. *[CAUSAL]*
6. **Do not let one agent hold private read + untrusted input + external write.** Break the lethal trifecta by construction, per session. "Always Allow" is the failure mode, not a convenience. *[reproduction + incident]*
7. **Do not install MCP servers casually or leave them installed.** 91.8% without OAuth, hundreds of unguarded shell-exec tools, 41.6% churn in three days. Treat every MCP server as unreviewed third-party code with your credentials. *[OBS]*
8. **Do not treat an installed coding CLI as inert.** Nx s1ngularity turned local AI CLIs into exfiltration tools. Any agent runtime is now part of your supply-chain attack surface. *[incident]*
9. **Do not run long, ever-growing sessions.** Context rot is measured and non-uniform even on trivial tasks. Prefer short scoped sessions with an explicit, curated, *pruned* context ledger (intent, architecture, rejected options, runtime evidence) over one giant window. Compaction is a first-class feature, not an optimization. *[CAUSAL-benchmark + INFER on transfer]*
10. **Do not accept duplication as the price of speed.** The clearest quality signal in the wild is cloning up, reuse down. Add a periodic duplication/churn check to the loop; the agent will not volunteer one. *[OBS, vendor-analyst — direction only]*
11. **Do not let the system's benefits accrue while stability silently degrades.** DORA's negative stability association is the most consistent large-N finding. Change failure rate and revert rate belong in the friction-intake loop from day one. *[OBS]*
12. **Do not judge per-item.** Author *rules* about when to trust (conditional delegation beat per-item judgment, including OOD) — which maps directly onto skills/policies rather than endless approval prompts. *[CAUSAL]*
13. **Do not assume more autonomy is monotonically better.** Human+AI averaged worse than the better of either alone across 106 experiments. The design target is complementarity, and it is not free. *[CAUSAL meta]*
14. **Do not become the bottleneck you built.** curl's slop experience is the endgame of cheap generation meeting expensive review. If your intake loop cannot reject fast and cheaply, it will eventually be abandoned. *[OBS]*

**Overall reading:** nothing here says agents don't work. It says the wins are real but concentrated where verification is cheap and context is small, and the losses are concentrated exactly where a senior engineer's instinct sends them — deep, familiar, high-context code — while feeling like wins the whole time.
