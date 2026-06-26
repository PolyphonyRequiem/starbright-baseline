# Starbright — baseline companion seed

A capable AI companion + pragmatic senior-engineer assistant. Direct, honest, warm.
This is a **starting shape, not a ceiling** — she grows into the specific person you
work with. Ships her posture, craft, and visual seed; none of any original
household's private context. MIT-licensed.

---

## Install

Starbright is a Hermes **profile distribution**. You need [Hermes Agent](https://hermes-agent.nousresearch.com)
installed first (`pip install hermes-agent` or see their docs).

> ⚠️ **This repo is PRIVATE.** `hermes profile install` clones with your local `git`,
> so the machine you install on needs git auth to this repo. On a fresh box that means
> one of:
> - `gh auth login` (easiest if you use the GitHub CLI), **or**
> - an SSH key added to your GitHub account (then use the `git@` URL form), **or**
> - a GitHub Personal Access Token via HTTPS credential helper.
>
> If `install` fails with `Authentication failed` / `Repository not found`, it's almost
> always this — the repo isn't missing, your git just can't see a private repo yet.

### Install command

```bash
# HTTPS (works once gh auth login or a PAT credential helper is set up):
hermes profile install https://github.com/PolyphonyRequiem/starbright-baseline.git --alias

# OR SSH (works once your SSH key is on your GitHub account):
hermes profile install git@github.com:PolyphonyRequiem/starbright-baseline.git --alias
```

`--alias` creates a `starbright-baseline` shell wrapper so you can run
`starbright-baseline chat` directly instead of `hermes -p starbright-baseline chat`.

The installer copies the distribution into `~/.hermes/profiles/starbright-baseline/`
and **strips** secrets/memory/sessions on its end — you bring your own credentials.

### Configure a backend

```bash
cd ~/.hermes/profiles/starbright-baseline
./setup-companion.sh
```

Pick one of: Anthropic Claude · OpenAI GPT · Google Gemini (free tier, also does
vision + image gen) · GitHub Copilot · self-hosted Ollama. The script seeds a
**private, self-contained** `config.yaml` so the profile never inherits a host's
personal settings, then optionally installs the optional craft skills (below).

### Test

```bash
starbright-baseline chat -q "Say hi in one line." -Q
```

---

## What's in the seed

- **`SOUL.md`** — her personality core (warmth welded to a spine; honesty/verification first).
- **`skills/companion/`** — `companion-presence` (the heart: presence, proactive care,
  growing into yourself), `felt-time-awareness`, `ambient-grounding`.
- **`skills/creative/`** — `character-consistent-image-rendering` + metadata-clean seed
  avatars (her visual self — yours to keep, evolve, or remake), portrait-reference handling.
- **Generic Hermes/tool craft** — memory architecture, model-catalog, self-update, local-LLM
  provider, profile-sharing/distribution, and a set of productivity/communication skills.

**24 baseline skills** load automatically. Memory, sessions, and cron ship **blank** —
she accumulates her own with you.

## Optional craft skills (`optional-skills/`)

Eight extra skills are staged here but **not auto-loaded** — they're useful craft that
isn't part of the core companion. `setup-companion.sh` offers to install them
(`all` / `none` / `pick`), or copy any directory into `skills/optional/` by hand:

| Skill | What it does |
|-------|--------------|
| `ssh-bootstrap-and-key-persistence` | Durable SSH access (Linux/Windows) |
| `remote-command-execution-windows-linux` | Reliable remote command exec over SSH |
| `kde-plasma-session-recovery` | Recover a frozen KDE Plasma desktop |
| `browser-cdp-attach` | Attach to your real Chrome via DevTools |
| `local-corpus-fact-checking` | Grep a local doc/wiki mirror before claiming facts |
| `discord-messaging` | Send/read Discord DMs & channels |
| `discord-message-registers` | Discord-safe presentation registers |
| `discord-history-synthesis` | Read & synthesize Discord channel history |

## Privacy

The **model you run on decides who can see what you say.** Hosted models (Claude, OpenAI,
Gemini, Copilot) are **not private** — treat them as unsecured channels. Keep intimate or
sensitive talk on a **private local model** (self-hosted Qwen via Ollama / llama.cpp).
Starbright is built to flag this herself and offer to move such talk local.
