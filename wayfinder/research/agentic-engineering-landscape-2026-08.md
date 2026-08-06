# Agentic AI Engineering Workflows & Orchestration — State of Play, August 2026

**Retrieved:** 2026-08-06. Every claim is tagged: `[VENDOR]` vendor documentation/claim · `[REPORTING]` independent reporting · `[TELEMETRY]` observational telemetry · `[SURVEY]` survey · `[INFERENCE]` my own reasoning from the cited material.

**Retrieval note / discovery bias:** this pass is built almost entirely from **first-party vendor documentation and changelogs** fetched directly (`.md` twins, `llms.txt` indexes, `r.jina.ai` chrome-stripping). Search engines and `github.com` were blocked or rate-limited during the pass, so the **independent-reporting and telemetry lanes are thin**. Read the maturity judgments accordingly: documentation proves a feature *exists*, never that it works reliably at scale.

---

## Claude Code / Claude Agent SDK (Anthropic)

**What it does now.** Claude Code ships across terminal, IDE, desktop app, and browser `[VENDOR]` (https://code.claude.com/docs/llms.txt, retrieved 2026-08-06). The concrete primitives:

- **Skills** — `SKILL.md` files, progressive-disclosure (body loads only when used), invoked as `/name` or auto-selected. Custom commands have been **merged into** skills; `.claude/commands/*.md` and `.claude/skills/*/SKILL.md` now produce the same thing. Claude Code declares conformance to the **Agent Skills open standard** (https://agentskills.io) and lists its own extensions: invocation control, subagent execution, dynamic context injection `[VENDOR]` (https://code.claude.com/docs/en/skills.md).
- **Subagents** — separate context window, own system prompt, restricted tool set, independent permissions; built-ins Explore/Plan/general-purpose; explicitly framed as **context preservation + constraint enforcement + cost routing** (route to Haiku) `[VENDOR]` (https://code.claude.com/docs/en/sub-agents.md).
- **Agent view** (`claude agents`) — one screen for many detached background sessions, grouped **Needs input / Working / Completed**. Documented against v2.1.140 `[VENDOR]` (https://code.claude.com/docs/en/agent-view.md).
- **Agent teams** — peer sessions with a fixed lead, inter-agent messaging, shared tasks. **Experimental and disabled by default** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), documented at v2.1.178 `[VENDOR]` (https://code.claude.com/docs/en/agent-teams.md).
- **Agent SDK** — Claude Code as a Python/TS library: same agent loop, tools, context management, plus hooks, file checkpointing, in-process MCP custom tools, cost tracking, and a hosting guide covering subprocess architecture, session persistence, multi-tenant isolation `[VENDOR]` (https://code.claude.com/docs/en/agent-sdk/overview.md; https://code.claude.com/docs/llms.txt).
- **Managed Agents** — hosted harness on Anthropic infrastructure, positioned for "long-running tasks and asynchronous work" where you don't want to run your own sandbox/session infra; also on Claude Platform on AWS `[VENDOR]` (https://platform.claude.com/docs/en/managed-agents/overview.md). Skills are a first-class API object with versioning (`Create Skill (Beta)`, `Create Skill Version (Beta)`) `[VENDOR]` (https://platform.claude.com/docs/llms.txt). **MCP tunnels** now ship as deployable infrastructure with Docker Compose/Helm, console management, and a security doc `[VENDOR]` (same index).

**Admission against interest — the most decision-relevant text I found.** The agent-teams limitations list is unusually candid `[VENDOR]` (https://code.claude.com/docs/en/agent-teams.md): no session resumption for in-process teammates (`/resume` leaves the lead messaging teammates that no longer exist); "task status can lag" and blocks dependent tasks, requiring manual status edits; one team per session, **no nested teams**, lead is fixed and non-transferable; permissions set at spawn; split panes need tmux/iTerm2 (not Windows Terminal). `[INFERENCE]` Multi-peer-agent coordination is the least finished part of the most advanced product in this space — the durable-state, resumability, and task-ledger problems are exactly the ones a workflow engine already solves.

**Direction.** Local session → detached background sessions → hosted managed agents, with skills as the portable capability unit and MCP as the tool bus `[INFERENCE]` from the doc set above.

**Interaction model.** Terminal-first, IDE/desktop/web secondary; single-session chat with delegated subagents; a fleet dashboard (`claude agents`) for background work.

---

## OpenAI Codex / Agents SDK

**Codex.** CLI + IDE extension + desktop app + cloud, with a documented **markdown twin for every page** and a machine-oriented condensed manual `[VENDOR]` (https://learn.chatgpt.com/llms.txt).

- **Codex cloud** — isolated per-repo environments with configured dependencies/secrets, parallel tasks, started from web, **GitHub, Linear, or Slack**, and a review-summary-and-diff → PR handoff `[VENDOR]` (https://learn.chatgpt.com/docs/cloud.md).
- **Subagents** — "enabled by default" in current local Codex releases; parallel spawning with results collected into one response; `/agent` in the CLI to inspect/switch agent threads; custom agents definable locally with their own model config and instructions; delegation triggerable from `AGENTS.md` or skill instructions. Vendor states plainly: subagent workflows "consume more tokens than comparable single-agent runs" `[VENDOR]` (https://learn.chatgpt.com/docs/agent-configuration/subagents.md).
- **Configuration surface** — `AGENTS.md` custom instructions, a **Rules** doc controlling which commands run outside the sandbox, an agent-approvals-and-security doc covering sandboxing/approvals/network controls, plus **Build skills** and **Build plugins** pages spanning ChatGPT *and* Codex `[VENDOR]` (https://learn.chatgpt.com/llms.txt).
- **Codex App Server** — an embed protocol for putting Codex inside your own product `[VENDOR]` (same index). `[INFERENCE]` This is the OpenAI analogue of the Agent SDK's "harness as a library" move.

**Agents SDK (Python).** Small primitive set: Agents, **Agents-as-tools / Handoffs**, Guardrails, built-in tracing. Now also documents **Sandbox agents** ("specialists inside real isolated workspaces with manifest-defined files, sandbox client choice, and **resumable sandbox sessions**") and realtime/voice agents `[VENDOR]` (https://openai.github.io/openai-agents-python/, page timestamp 2026-08-06).

**Interaction model.** Terminal + IDE + hosted-cloud + chat-app, converging on issue-tracker/Slack entry points and PR-shaped output.

---

## GitHub Copilot (agent mode, CLI, cloud agent)

- **Cloud agent** — background work in an **ephemeral GitHub Actions environment**: researches a repo, produces an implementation plan, changes code on a branch, iterates, then opens a PR. Entry points: agents panel on github.com, Issues, VS Code, `@copilot` mention on an existing PR, and **assignment of security-campaign alerts**. Available on all paid Copilot plans; excluded for managed user accounts `[VENDOR]` (https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent).
- **Automations** — run the cloud agent on a schedule or in response to events such as an issue being opened `[VENDOR]` (https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-automations; retrieved page rendered navigation only — **structure-confirmed, body not verified**).
- **Copilot CLI** — interactive TUI *and* a **programmatic** interface; Linux/macOS/Windows via PowerShell or WSL; can act on GitHub.com (e.g. open PRs) `[VENDOR]` (https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli). `[INFERENCE]` The programmatic mode is precisely what makes Copilot usable as a *headless provider* under an external orchestrator — which is what the user's Conductor already does.
- **VS Code** — two agent surfaces: a dedicated **Agents window** (`code --agents`) described as "agent-first… for orchestrating tasks across **multiple projects**", and the in-editor Chat view; plus a distinct **Plan agent** that produces a reviewable plan before any file changes; integrated-browser end-to-end verification `[VENDOR]` (https://code.visualstudio.com/docs/agents/overview; https://code.visualstudio.com/docs/copilot/chat/chat-agent-mode).
- **Agent HQ** — GitHub's stated platform direction: third-party coding agents (Anthropic, OpenAI, Google, Cognition, xAI) running inside GitHub under one Copilot subscription, with a **mission control** command center, agentic code review, a governance control plane, and a metrics dashboard `[VENDOR]` (https://github.blog/news-insights/company-news/welcome-home-agents/, **2025-10-28**). `[INFERENCE]` Dated ~10 months before this report; treat the multi-vendor roster as announced intent and verify per-agent availability before designing on it.

**Interaction model.** PR/issue-native and repo-scoped; the review artifact is the diff, and the gate is code review.

---

## Cursor

Cloud agents run in **isolated VMs with full dev environments** (cloned repos, deps, secrets, startup commands, network), support **MCP**, can drive desktop/browser, and work in **multi-repo** workspaces opening PRs in each repo they change. Launchable from iOS/iPad, web, desktop, Slack, `@cursor` on GitHub/Bitbucket PRs and issues, Linear, and an **API** `[VENDOR]` (https://cursor.com/docs/cloud-agent). Recent changelog shows the surface expanding away from the editor: iPad app with pinned parallel agent chats, a full PR **review** surface (comments, checks, approvals, reviewer changes) on mobile, an **Inbox** for what needs your attention, and a **plugin marketplace** including first-party Gmail/Drive/Calendar plugins `[VENDOR]` (https://cursor.com/changelog).

`[INFERENCE]` Cursor is no longer positioning primarily as an IDE; the changelog's centre of gravity is fleet management + review + non-code tool access.

---

## Devin / Cognition

Devin is documented as an autonomous AI software engineer with the heuristic "if you can do it in three hours, Devin can most likely do it", targeting parallel ticket work (Linear/Jira), migrations/refactors, PR review, codebase Q&A, tests, docs. Vendor's own success conditions: **explicit completion criteria, easy verification (CI passes, deploy check), decomposition for harder tasks**; most successful workflows start from a **Slack or Teams thread** `[VENDOR]` (https://docs.devin.ai/get-started/devin-intro). The API surface is substantial and org-shaped — sessions, **Knowledge** entries (CRUD), **Playbooks** (CRUD), attachments, RBAC/multi-org, PATs, v1→current migration guide `[VENDOR]` (https://docs.devin.ai/llms.txt). `[INFERENCE]` Playbooks + Knowledge are Cognition's answer to the skills/memory layer, but org-owned and API-managed rather than file-in-repo.

Company direction (all `[VENDOR]`, https://cognition.ai/blog): acquired **TierZero** explicitly for "everything that keeps software running once it ships… bring their work on **automations** into Devin" (2026-07-20); acquired The Interaction Company / Poke (2026-07-23); one year post-Windsurf merger (2026-07-14); publishes its own frontier model **Fable 5** with a "Fusion" architecture and cost-per-*task* rather than cost-per-token framing (2026-07-13); enterprise/government distribution deals (LTM 2026-07-28; U.S. DOE MOU 2026-07-22).

**Interaction model.** Ticket- and Slack-triggered autonomous background work, delivered as PRs; vertically integrated down to the model.

---

## Amp (Sourcegraph)

Amp's changelog is the densest single evidence source for where "long-running multi-agent" is actually landing `[VENDOR]` (https://ampcode.com/news):

- **Orbs** — remote unsupervised machines per thread, preloaded with code/plugins/tools; 32GB/16 cores at $1.32/hr billed per minute; `amp -ox "…"` spawns a thread in an orb; `amp sync <thread>` pulls changes local; sizes configurable (2026-07-03) `[VENDOR]` (https://ampcode.com/news/agents-in-orbs).
- **Agent-to-agent** (2026-07-17) — agents spawn other agents locally, in orbs, or on other machines, and **exchange messages and files** across threads (https://ampcode.com/news/from-agent-to-agent).
- **Self-scheduling** (2026-07-21) — an agent sets its own schedule, wakes with its saved prompt **and full prior context**, e.g. "every hour, use the inference-error-triage **skill**… spin up a new thread to fix… report to #bugs" (https://ampcode.com/news/schedule).
- **Slack** (2026-07-20), **Puck** meta-agent (2026-07-20), **Multiplayer** shared control of an orb (2026-07-22), **Event-driven orbs** (2026-07-23), **OIDC workload identity for orbs** (2026-07-14), effort dial low/medium/high/ultra (2026-07-09), **Portals into Orbs** live-reload preview (2026-08-06).
- Notable vendor essay: *"Who Cares About the Model? We swapped the default model overnight. Nobody complained."* (2026-07-29) `[VENDOR]` — `[INFERENCE]` a vendor arguing the harness, not the model, is the product.

**Interaction model.** Thread-as-unit-of-work, terminal + Slack + web, remote sandboxes as the default execution substrate, agents as durable schedulable processes.

---

## OpenHands (All Hands AI)

Restructured into: **Agent Canvas** (browser UI + backend server for agents and automations, single `agent-canvas` command, self-hostable), **OpenHands Cloud** (managed; GitHub/GitLab/Bitbucket + Slack/Jira/Linear, multi-user, RBAC, budgeting enforcement, usage reporting), **OpenHands Enterprise** (source-available, self-host in VPC via Kubernetes, license required beyond one month), and the **Software Agent SDK** as the engine underneath everything. The former CLI and local GUI are now labelled **Legacy** `[VENDOR]` (https://docs.all-hands.dev/). SDK claims: MIT-licensed, any LLM, task planning/decomposition, automatic context compression, security analysis, OpenAI-compatible endpoint so an OpenHands agent can be driven from any chat UI/IDE/voice client; claims top-tier SWE-bench/SWT-bench/multi-SWE-bench performance `[VENDOR]` (https://docs.openhands.dev/sdk). `[INFERENCE]` The benchmark claim is vendor self-report and benchmark-bounded; the *architecturally* interesting part is the OpenAI-compatible surface, which makes OpenHands drop-in behind an existing orchestrator.

---

## Orchestration layers: workflow engines and DAG-shaped agent runners

- **LangGraph** — self-described "low-level orchestration framework and runtime for building, managing, and deploying **long-running, stateful agents**", whose named core capabilities are **durable execution, streaming, human-in-the-loop, and persistence**, and whose pitch is mixing deterministic hand-coded steps with LLM-driven steps *in the same graph* so parts stay "predictable and auditable". Sits under **Deep Agents** (planning, subagents, filesystem tools, context management) and beside **LangSmith** (observability/eval) `[VENDOR]` (https://docs.langchain.com/oss/python/langgraph/overview). Named users (Klarna, Uber, J.P. Morgan) are a vendor logo claim, not adoption evidence.
- **Temporal** — now ships an **AI Cookbook**: durable agentic loops with Claude and OpenAI tool calling, structured outputs, LiteLLM provider-switching, HTTP-retry extraction, and a **durable MCP server** recipe `[VENDOR]` (https://docs.temporal.io/ai-cookbook). `[INFERENCE]` A general-purpose durable-execution engine explicitly courting agent workloads is the clearest signal that the industry has decided agent orchestration is a *workflow* problem — retries, checkpoints, timers, human gates — rather than a novel one.
- **Vendor-native orchestration** is also real: Claude Code agent view + agent teams, Codex subagents/`/agent`, VS Code Agents window, GitHub Agent HQ mission control, Cursor Inbox, Amp Puck. `[INFERENCE]` Each is a fleet *console* over its own runtime; none is a portable engine.

**Explicit non-confirmation:** I found no vendor documentation in this pass describing a cross-vendor DAG runner with checkpoint/resume semantics over heterogeneous agent providers. That gap is the space the user's Conductor occupies.

---

## Skills / MCP / subagents ecosystem

- **Agent Skills** is now a **cross-vendor standard with its own site, spec, best-practices, description-optimization, eval guidance, script bundling, a client showcase, and an "add skills support to your agent" implementation guide** — plus a Discord and a public repo (`agentskills/agentskills`) `[VENDOR]` (https://agentskills.io/llms.txt; https://agentskills.io/specification.md). Adopted-and-extended by Claude Code `[VENDOR]` (https://code.claude.com/docs/en/skills.md); OpenAI ships parallel "Build skills" and "Build plugins" docs spanning ChatGPT and Codex `[VENDOR]` (https://learn.chatgpt.com/llms.txt).
- **MCP** — spec version **2025-11-25** is current; JSON-RPC 2.0, stateful connections, capability negotiation, host/client/server roles, explicitly modelled on LSP `[VENDOR]` (https://modelcontextprotocol.io/specification/2025-11-25.md). Supported by Claude, Codex, Cursor cloud agents, VS Code; Anthropic now ships **MCP tunnels** as deployable infra with Helm/Compose and a security doc `[VENDOR]` (https://platform.claude.com/docs/llms.txt).
- **Subagents** are now table stakes: Claude (own context/tools/permissions, background-capable), Codex (default-on, `/agent`, custom agents), OpenAI Agents SDK (handoffs + agents-as-tools), OpenHands (task decomposition), Amp (agent-to-agent spawn/message/file transfer), LangChain Deep Agents. `[INFERENCE]` Convergent — but the sources were selected as the best-known products, so absence of counterexamples is weak evidence.

---

## Synthesis

**What the market has converged on (five things, all multi-vendor observed):**

1. **The harness is the product, not the model.** Skills, subagents, context compaction, hooks, checkpointing, and sandboxes are what vendors ship and differentiate on — Amp says so outright (2026-07-29) `[VENDOR]`; Anthropic, OpenAI, and All Hands all now sell the harness as a library (Agent SDK / App Server / Software Agent SDK) `[VENDOR]`. `[INFERENCE]`
2. **Ephemeral remote sandboxes are the default execution substrate** for anything long-running: Copilot's Actions-backed environment, Codex cloud environments, Cursor VMs, Amp orbs, OpenHands Cloud `[VENDOR], all`.
3. **Entry points have left the editor.** Every product listed now starts work from issue trackers, Slack/Teams, mobile, or an API — Cursor, Codex, Devin, Amp, Copilot `[VENDOR]`. The IDE is one client among several.
4. **The output artifact is a PR/diff and the gate is human code review.** Uniform across Copilot, Codex, Cursor, Devin, Amp `[VENDOR]`.
5. **A fleet console has appeared in every product** — `claude agents`, VS Code Agents window, Agent HQ mission control, Cursor Inbox, Amp threads — organized around *"which agents need my input"* `[VENDOR]`. `[INFERENCE]` Attention routing, not task execution, is the newest shared UX primitive.
6. **Skills (`SKILL.md`) + MCP have become the two portable interop layers**, with a real cross-vendor spec behind each `[VENDOR]`.

**What it is NOT solving:**

- **Durable multi-agent coordination.** Anthropic's own limitations list — no resumption of in-process teammates, lagging task status blocking dependents, no nested teams, fixed lead, permissions frozen at spawn — is the state of the art, and it is labelled experimental and off by default `[VENDOR]`. Meanwhile Temporal and LangGraph sell exactly the missing properties (durable execution, persistence, human-in-the-loop gates) as general infrastructure `[VENDOR]`. `[INFERENCE]` Nobody has merged the coding-agent harness with a real workflow engine; that seam is where an external conductor earns its keep.
- **Cross-vendor orchestration.** Agent HQ is the only announced attempt (2025-10-28) and it is GitHub-hosted and Copilot-subscription-bound `[VENDOR]`. No portable checkpoint/resume format exists across providers *(non-confirmation: none found in this pass)*.
- **Human-gate semantics beyond "review the diff."** No product surveyed documents typed approval gates, resumable checkpoints a human can rewind to across sessions, or an evidence packet for a decision. Claude ships file checkpointing inside the SDK `[VENDOR]`; that is file state, not decision state.
- **Rationale and decision memory.** Skills, Devin Knowledge/Playbooks, and `AGENTS.md` capture *instructions*; nothing surveyed captures rejected alternatives, assumptions, or provenance as a first-class durable object `[INFERENCE]`.
- **Cost/attention accounting.** Only OpenAI explicitly warns that subagents burn more tokens `[VENDOR]`, and only Amp publishes concrete sandbox pricing `[VENDOR]`. Intervention rate, review burden, and rework are unmeasured across all of them in this evidence set.
- **Independent verification generally.** The DORA "State of AI-assisted Software Development" report is the standing `[SURVEY]` reference (https://dora.dev/research/2025/dora-report/) but is **2025** data; I found no 2026 independent telemetry on multi-agent engineering outcomes in this pass. Treat every effectiveness claim above as vendor-sourced.
