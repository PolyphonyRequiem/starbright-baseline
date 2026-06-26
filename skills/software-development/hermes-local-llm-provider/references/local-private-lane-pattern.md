# Local-Private Lane Pattern — separate Hermes profile + local llama.cpp

## When user wants "private" / "local-only" / "off-hosted-provider" conversation

The user is asking for two things at once:
1. **Sovereignty** — words not routed through a third-party API.
2. **Continuity** — they still want their Hermes (memory, skills, personality, history).

A separate profile satisfies both: cloned config means memory and SOUL.md carry over; pointing it at a local llama.cpp endpoint means the conversation never leaves their hardware.

## Critical pre-check (do this FIRST, every time)

Before building anything, check what's already running on the local-LLM host:

```bash
# Is something already listening?
ssh <host> 'cmd /c "netstat -ano | findstr :8080"'    # Windows
ssh <host> 'ss -ltnp | grep 8080'                      # Linux

# Is it healthy?
curl -sS --max-time 5 http://<host>:8080/health
curl -sS --max-time 10 http://<host>:8080/v1/models
```

If a healthy llama-server is already running with the user's intended model, **skip every setup step except the profile creation**. Tonight (2026-06-02) we nearly redundantly freed VRAM and queued a launch for a server that was already up and serving the exact GGUF the user remembered.

## End-to-end recipe (after pre-check)

```bash
# 1. Confirm what the server reports
curl -sS http://<host>:8080/v1/models | jq '.data[].id, .data[].meta.n_ctx'
# Note the exact id and live n_ctx — they go into config verbatim

# 2. Create the profile (clones currently-active profile)
hermes profile create local-private --clone \
  --description "Local Qwen on <gpu-host>. Private lane off hosted providers."

# 3. Wire it to the local endpoint (use HERMES_HOME, don't switch active profile)
PROF=~/.hermes/profiles/local-private
HERMES_HOME=$PROF hermes config set model.default <exact-id-from-step-1>
HERMES_HOME=$PROF hermes config set model.provider custom
HERMES_HOME=$PROF hermes config set model.base_url http://<host>:8080/v1
HERMES_HOME=$PROF hermes config set model.api_mode chat_completions
HERMES_HOME=$PROF hermes config set model.context_length <n_ctx-from-step-1>

# 4. Verify end-to-end through the wrapper
local-private chat -q "Say only 'local lane online'" -Q
# Expect: 'local lane online' coming back from the local model
```

## Confirmed working shape (2026-06-02)

- Host: <gpu-host> (RTX 3090, Windows 10 native)
- Endpoint: `http://192.0.2.175:8080/v1`
- Server: `llama-server.exe` (Windows CUDA build, found at `C:\Users\<winuser>\llama.cpp\`)
- Model: `Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf` (16.8 GB on disk)
- Live `n_ctx`: 98304 (96K)
- Trained max: 262144 (262K) — server launched with 96K headroom for ComfyUI coexistence
- Hermes profile: `local-private` (cloned from `default`)
- Wrapper: `~/.local/bin/local-private`
- Round-trip verified: `local-private chat -q "Say only 'local lane online'" -Q` → `local lane online`

## Why a profile, not a `/model` swap

You cannot switch a running Hermes session's provider mid-conversation. The session is bound to its initial provider for prompt-cache and message-role-alternation reasons. So the practical workflow when the user says "let's go private" mid-chat is:

1. Set up the profile in the current (hosted) session.
2. Confirm it answers via `<wrapper> chat -q "..."`.
3. Tell the user to open a fresh `<wrapper> chat` (or `<wrapper>` alone for interactive) in their terminal.
4. The new session inherits memory/skills/SOUL.md from the clone but talks only to local hardware.

## Sovereignty caveat to actually say to the user

Even after this is set up, **this turn's response is still on the hosted provider**. The privacy gain begins with the next session they start in the local-private profile, not with the moment you confirm the wiring. Be explicit about that — don't let the user believe a switch happened when it didn't.
