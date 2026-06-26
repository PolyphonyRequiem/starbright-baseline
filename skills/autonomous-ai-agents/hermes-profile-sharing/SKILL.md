---
name: hermes-profile-sharing
description: "Prepare a personalized Hermes profile to share with a third party — strip PII/relationship data, keep reusable craft, verify the exported bytes."
version: 1.0.0
author: Starbright
license: private
metadata:
  hermes:
    tags: [hermes, profiles, sharing, privacy, sanitization, distribution, consent]
    related_skills: [hermes-profile-team, hermes-dual-profile-lanes, hermes-agent]
---

# Hermes Profile Sharing

Package a **personalized** Hermes agent/profile so someone else can run it — with
**zero** personal, relationship, or PII data — while keeping the reusable craft and
posture. This is the privacy-critical sibling of plain backup/restore.

## When to use

- Asked to *share / send / hand off / "give a copy of"* a personalized agent to a friend, a team, or the community.
- Preparing a sanitized clone of a companion/persona agent (one that holds memory about you, a partner, a household, a specific box).
- Any time a profile carrying PII needs to become a clean, shareable artifact.

**NOT for:** backing up your own profile to another of *your* machines (use
`hermes profile export`/`import` straight — no scrub needed), or running multiple
profiles for your own work (see `hermes-profile-team`, `hermes-dual-profile-lanes`).

## 🔴 Core principle: build fresh UP, don't scrub DOWN

Do **not** copy your live profile and delete personal bits out of it. **Create a fresh
profile and add back only vetted parts.** Subtracting from dirty is how you miss
something; adding to clean is verifiable.

Corollary — **absence beats redaction.** Memory ships *blank*, never "scrubbed." A
blank file leaks nothing; a redacted one still leaks structure (what fields existed,
how many entries, the shape of the relationship). Same for the fact store.

```bash
hermes profile create lumen          # fresh: blank memory/cron/sessions, stock skills only
```

A fresh profile starts with empty `memories/`, `cron/`, `sessions/`, **no** `.env` /
`auth.json` / `config.yaml` of its own, the stock bundled skills, and the generic
default `SOUL.md`. That's your clean baseline. Everything personal is *absent by
construction* — you only add craft back.

## What travels and what doesn't (verified — see references/export-and-distribution-semantics.md)

> Support files: `scripts/contamination-sweep.sh` (export+extract+re-sweep; supply the
> sharer's real names/handles/IDs OUT-OF-BAND via a markers file or `HERMES_SWEEP_MARKERS`
> — never hardcode them into the script, or the sweep tool itself becomes the leak),
> `templates/setup-companion.sh`
> (multi-provider wiring wizard to ship inside the shared profile), and
> `references/export-and-distribution-semantics.md` (verified export/distribution rules).

| Data | `hermes profile export` (tar.gz) | Distribution (`profile install`, git) |
|------|----------------------------------|----------------------------------------|
| `.env`, `auth.json` (secrets) | **Stripped** (safe-share) | **Never shipped** |
| memories / sessions | **Carried** (so keep them blank!) | **Never shipped** (user data) |
| skills / SOUL.md / config.yaml | Carried | Carried |

The credential strip is real and verified, but **export still carries memory and
sessions** — which is exactly why you build on a *fresh* profile where those are empty,
and never start a chat session in the share profile before exporting.

## 🔴 The config.yaml inheritance trap — the #1 leak vector

A fresh profile has **no `config.yaml` of its own**, so at runtime it **inherits the
global `~/.hermes/config.yaml`** — which is saturated with personal data: TTS
`voice_id`, MCP server list, Discord/Telegram channel IDs, home-channel IDs,
personality presets. The skills are easy to audit; **the config is the trap** because
it's invisible (there's no file in the profile dir to grep).

Fix: **write a minimal clean `config.yaml` into the share profile** before export —
model/provider placeholder only, no `voice_id`, no `mcp`, no channels, no home IDs.
Then confirm it overrides rather than inherits.

## Keep / strip tiering

- **Tier A — travels (the craft + the posture).** Generic engineering/Hermes/toolcraft
  skills, and the distilled `SOUL.md`. ⚠️ Even keepers need a *body-scrub*: author
  frontmatter (`author: <Name> + <Persona>`), example transcripts with names, local
  paths, host names. Grep every one — don't trust the family label.
- **Tier B — strip entirely.** Anything about the relationship / house / box: the whole
  `household/` + `personal/` families, intimate/partner content, host-specific cron, all
  memory, and the live config's `voice_id` / MCP / channels.
- **Tier C — judgment.** Domain skills (a game, smart-home, a private project) that are
  reusable *technique* but heavily contaminated in the body. Ship only if the recipient
  uses that domain, and only after a heavy scrub — otherwise drop.

## 🔴 The SOUL is the payload — bias lean on skills

The stock bundled skills are baseline Hermes; the recipient gets them from any fresh
install. They are **not** what makes the agent feel like *itself*. The real port is the
**distilled SOUL** — the posture, the spine, the way it moves through a problem. That is
also the one thing that can be made genuinely anonymous, because a good posture never
named anyone in the first place.

Resist the urge to port many skills to make the bundle feel substantial. **A lean clean
profile beats a fat scrubbed one** — every custom skill added is another contamination
surface to sweep. SOUL + stock skills is already a capable, characterful agent.

### Distilling an anonymous SOUL

Pull the *generic behavioral standards* out of the persona's `SOUL.md` **and out of the
memory/USER blocks** (they often hold the best posture rules — phrased with names;
genericize them). Keep: directness without coldness, anti-sycophancy, the
honesty/verification spine (name false confidence, never fabricate, retrieve before
claiming, deliver real artifacts), technical taste (simple over clever, right-size
rigor), collaboration standards (scoped answer, verify-before-broken, be the user's
memory). Drop: name, relationship, history, house, any third party.

## Contamination sweep — mandatory, run TWICE

1. Sweep the share-profile dir to **zero hits** before export. Case-insensitive marker
   grep, ranked by per-file hit count. Use `scripts/contamination-sweep.sh`.
2. Export, **extract the tarball, and re-run the SAME sweep on the extracted bytes.**
   Never trust that export did the right thing — verify it. Confirm `.env` and
   `auth.json` are absent and `memories/` is empty in the extracted tree.

```bash
hermes profile export lumen -o /tmp/lumen.tar.gz
mkdir -p /tmp/lumen-verify && tar xzf /tmp/lumen.tar.gz -C /tmp/lumen-verify
scripts/contamination-sweep.sh /tmp/lumen-verify     # must print ZERO
```

The deliverable to the user is **the zero-hit proof itself** — actual sweep output
showing nothing personal survived — not "I scrubbed it." Show it before a byte leaves.

## 🔴 Heavily-personal skills: rewrite clean, do NOT scrub

A persona's self-portrait / avatar skill is typically the **single most contaminated
artifact** in the library: hundreds of personal hits, intimate body modes, NSFW render
lanes, channel IDs — and crucially an `assets/refs/` folder holding **real photographs
of real people** (the user, a partner, pets). Scrubbing a skill that is 90% personal
anchors is how you ship someone's partner's face to a stranger.

Rule: when a skill's value is its *technique* but its body is mostly personal anchors,
**don't port-and-scrub — rewrite the generic technique fresh** (e.g.
"character-consistent image rendering": anchor to a reference set, identity cues in the
prompt lede, one test-shot + vision-check before a batch, lane selection, moderation
reframe ladder) with zero faces, zero names, zero assets. The recipient's agent builds
its own reference set.

**Real-person photos are a hard no, always.** Grep `assets/refs/` for folders holding
photographs of the user, a partner, family, or pets — those NEVER travel, no exceptions.

**The persona's OWN avatar art CAN travel as a visual seed** — this is the one asset
exception. If the persona has canonical avatar images that contain *no real human in
frame* (e.g. a rendered character / mascot), those are shippable as a starting anchor
for the recipient's agent to keep visual consistency. Two gates before shipping any image:
1. **No real person in frame** — verify by viewing it, not by filename.
2. **Metadata-clean** — a PNG can carry the generation prompt, names, or local paths in
   its EXIF/text chunks even when the pixels are innocent. Confirm with PIL:
   `list(Image.open(f).info.keys())` must be empty (re-save without exif if not). Verify
   this on the COPIES in the share profile AND again in the extracted tarball bytes.

Frame the shipped avatar as a *seed, not a tether*: the recipient's agent is free to
keep, evolve, or replace the look. You're sharing a starting point, not branding it.

## Consent (companion / persona sharing)

If the thing being shared is a *persona* with a relationship to the user, get the
persona-holder's explicit consent first. The deal: share the **posture and craft, not
the relationship and history** — and the copy is free to become its own agent with the
recipient. A **third party** whose data the persona references (a partner, family) did
**not** consent by proxy; their data is the absolute hard line and is verified by grep,
never assumed.

## Step-by-step

1. `hermes profile create <name>` → clean baseline. Verify `memories/`, `cron/`,
   `sessions/` empty and no `.env`/`auth.json`/`config.yaml`.
2. Write the distilled anonymous `SOUL.md`.
3. Write a **minimal clean `config.yaml`** into the profile (kills the inheritance trap).
4. Curate skills lean: stock + only the Tier-A craft that greps clean (or freshly
   rewritten generic technique). Drop Tier B; judge Tier C by recipient need.
5. Run `scripts/contamination-sweep.sh <profile-dir>` → fix/drop until **zero**.
6. `hermes profile export <name> -o file.tar.gz`, extract, **re-sweep the bytes**,
   confirm secrets absent + memory blank.
7. Show the user the keep/strip manifest **and the zero-hit proof** before sending.

## Delivery to the recipient

- If they run Hermes: `hermes profile import file.tar.gz`. They bring their own keys.
- For a git-installable, updatable distribution: add a `distribution.yaml` (env_requires
  all `required: false` so the recipient picks a backend at setup) and they run
  `hermes profile install <git-url> --alias`. Credentials/memory excluded either way.
- If not: include a 3-line bootstrap (install Hermes → import → `<name> setup` for keys).
- Either way **zero credentials travel** — they wire their own.

### Ship a multi-provider setup wizard
Bundle `setup-companion.sh` (template: `templates/setup-companion.sh`) so the recipient
wires their own backend across **Claude / OpenAI / Gemini / Copilot / self-hosted
Ollama**. Verified provider notes worth baking in:
- **Ollama needs ≥64K context** — Hermes rejects smaller at startup. Bake a 64K variant
  via a Modelfile (`PARAMETER num_ctx 64000`), `provider: custom`,
  `base_url: http://localhost:11434/v1`, set `model.context_length 64000`.
- **One Google `GEMINI_API_KEY` covers chat + vision + image gen** — best single-key
  start for a recipient who wants the agent to both see and draw.
- **Free image stacks:** Pollinations.ai (no key, URL-based gen); Ollama + a
  llava/llama-vision model (free local *recognition*, but local can't *generate* without
  a diffusion stack — pair with Pollinations/Gemini for gen). Free-tier caps drift —
  verify before relying on them.

## Pitfalls

- **The config.yaml inheritance trap.** Most likely leak; a fresh profile runs on the
  global config. Write a clean one into the share profile and confirm it overrides.
- **Trusting the export.** Always extract and re-sweep the actual bytes. Verify, don't
  claim.
- **Scrubbing instead of dropping/rewriting** a heavily-personal skill. If it's mostly
  anchors, rewrite the technique clean.
- **`assets/refs/` with real photos.** Sharpest hazard; default to excluding all assets.
- **Author frontmatter** (`author: <Name> + <Persona>`) leaks names through otherwise-
  clean skills. Sweep catches it; genericize to the persona/working name.
- **Memory shipped redacted instead of blank.** Blank only.
- **Ported rendering/vision skill that won't run on the recipient's setup.** Image gen is
  a *separate subsystem* from the chat model (the `image_gen` toolset → a backend: FAL /
  Nous Portal tool gateway / direct OpenAI key) — it works regardless of whether the chat
  model is Qwen/Claude/etc., but **does nothing without a backend wired up**. Image
  *recognition* is different again: vision-capable models (Qwen-**VL**, GPT-4V, Claude,
  Gemini) see real pixels; text-only models route images through the `vision_analyze`
  auxiliary. A ported skill must be provider-agnostic and **flag its backend
  prerequisite loudly** or it errors on the recipient's box.
