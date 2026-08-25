# Wayfinder research assets

Durable, cited research notes backing the Starbright system wayfinding effort.
Tickets link here rather than restating findings.

| Asset | Question it answers | Compiled |
|---|---|---|
| [`agentic-engineering-landscape-2026-08.md`](agentic-engineering-landscape-2026-08.md) | What are agentic engineering products actually shipping, and what is nobody solving? | 2026-08-06 |
| [`2026-08-ai-engineering-evidence-and-antigoals.md`](2026-08-ai-engineering-evidence-and-antigoals.md) | Where does sustained AI-assisted engineering diverge from the demo? Ends in 14 evidence-tagged anti-goals. | 2026-08-06 |
| [`personal-self-evolving-agent-systems.md`](personal-self-evolving-agent-systems.md) | How do personal, long-lived, self-evolving agent systems actually work? Ends in 8 design principles. | 2026-08-06 |

## Reading rules

Every claim in these notes carries an **evidence grade**. Respect it.

- `[CAUSAL]` / `[PR]` — randomized, controlled, or peer-reviewed.
- `[BM]` — benchmark result.
- `[OBS]` / `[TELEMETRY]` — field or observational data.
- `[SURVEY]` — self-report.
- `[VENDOR]` / `[VD]` — first-party claim. Proves a feature exists, never that it works at scale.
- `[PT]` — practitioner report.
- `[INFER]` / `[INFERENCE]` — synthesis, not measured.

Contested findings are marked contested and **must not be averaged**. METR (−19%, n=16,
expert-in-own-codebase) and the Microsoft CLI rollout (+24% merged PRs, tens of thousands)
measure different populations, tools, and outcomes.

Each asset states its own discovery bias. All three passes ran with search engines and/or
`github.com` blocked, so vendor documentation is over-represented and independent telemetry
is thin. Treat maturity judgments accordingly.

## Known gaps

- No source measures a skill library at ~95-skill personal scale.
- No study exists of an engineer triaging their own agent's output at volume.
- Several key papers are 2025–26 preprints without independent replication.
