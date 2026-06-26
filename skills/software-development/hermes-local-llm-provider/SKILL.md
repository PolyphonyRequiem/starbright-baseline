---
name: hermes-local-llm-provider
description: Connect Hermes Agent to a local OpenAI-compatible LLM server (especially llama.cpp), verify GPU-backed serving, and resolve context/window mismatches cleanly.
---

# Hermes Local LLM Provider

## When to use
- The user wants Hermes to talk to a local model instead of a hosted provider.
- A local llama.cpp or similar server already exposes an OpenAI-compatible endpoint.
- You need a separate "intimate/private/local" lane while keeping the normal hosted default model.
- Hermes reaches the local server but fails on provider syntax, context-length gates, or startup sizing.

## Core idea
Treat this as **two separate layers** that both must be right:
1. **Serving layer** — the local runtime must actually load the model, fit on GPU/CPU, and expose a working `/v1` API.
2. **Hermes layer** — Hermes must point at that endpoint with the right provider/base_url/api_mode/context metadata.

Do not stop after only one layer works.

## Steps
0. **BEFORE launching anything, check if a local server is already running.**
   - On Windows: `ssh <gpu-host> 'cmd /c "netstat -ano | findstr :8080"'`
   - On Linux: `ss -ltnp | grep 8080`
   - Then `curl http://<host>:8080/v1/models` and `curl http://<host>:8080/health`.
   - A prior session may have left llama-server running with the exact model you need. Skipping this step led to a near-duplicate setup tonight (2026-06-02): we spent time freeing VRAM for a server that was already healthy and serving the intended GGUF.

1. **Prove the local server works before touching Hermes.**
   - Check a health endpoint if available.
   - Hit `/v1/models` or equivalent.
   - Verify GPU usage with `nvidia-smi` if using CUDA.
   - Confirm an actual completion request succeeds.

2. **Configure Hermes runtime fields explicitly.**
   - Set Hermes to use `provider: custom` for raw runtime use.
   - Set `model.base_url` to the local OpenAI-compatible endpoint, including `/v1`.
   - Set `model.api_mode` to `chat_completions` for llama.cpp-style OpenAI endpoints.

3. **Remember the custom-provider naming split.**
   - Named entries under `custom_providers:` are useful metadata and UI/model-switcher helpers.
   - The `/model custom:<name>:<model>` shorthand is for switching/picker UX.
   - The raw runtime provider field still needs the correct underlying provider shape; do not blindly write the UI shorthand into `model.provider` and assume runtime will accept it.

4. **Handle context in two places.**
   - Hermes may require a larger declared context window than the server auto-detects.
   - Add `model.context_length` when Hermes needs an override.
   - Also add per-model metadata under `custom_providers[].models.<model>.context_length` when you want a durable model-specific declaration.
   - But do **not** confuse Hermes metadata with the server's real live context cache: the server must still be launched with a large enough `-c` value.

5. **If Hermes says the request exceeds context size, fix the server, not just config.**
   - Hermes can be correctly configured and still fail if the running local server only started with a tiny live context (for example 4K).
   - Relaunch the runtime with a larger `-c` value and then retest Hermes.

6. **On GPU fits, verify stale processes before declaring the model too large.**
   - Check for leftover `llama-cli`, `llama-server`, Ollama, or other inference processes already occupying VRAM.
   - Kill stale local inference processes and re-measure free VRAM before judging fit.

7. **For borderline VRAM fits, use a larger context carefully and verify by measurement.**
   - After relaunch, check the health endpoint and `nvidia-smi` again.
   - Do not assume a launch succeeded just because the process exists.

8. **Always cross-check `model.default` against what `/v1/models` actually reports BEFORE declaring success.**
   - The server may have multiple GGUF files in its directory but only one loaded.
   - Hit `/v1/models` and verify the `id` field matches `model.default` exactly.
   - If they don't match, the server hasn't loaded your intended model — either the server needs to be restarted with the correct file, or your config points to the wrong model name.

9. **Fix mismatches with `hermes config set`, then verify Hermes itself can answer.**
   - Use `hermes config set model.default <actual-id>` and `hermes config set model.provider <provider-name>` to align.
   - Do NOT assume the session picks up the new config without a reset — the running session is already bound to the old model.
   - The final verification is always: confirm Hermes successfully completes a query through the local provider.

10. **End with an actual Hermes query.**
   - The last verification is not curl-only.
   - Run Hermes itself against the local model and confirm it returns a clean answer.

11. **When creating a "lite" companion profile for image-generation coexistence, change both profile metadata and server runtime.**
   - Give the lite profile its own `base_url`/port so it cannot silently hit the full-fat server.
   - Set the lite profile's `model.context_length` to the lowest Hermes-valid value you intend to support.
   - Launch a separate llama.cpp server for that port with a matching lower `-c` value.
   - Verify the live `n_ctx` via `/v1/models` on the lite port before telling the user it is lighter.

## Diagnosing an unreachable local lane (endpoint down mid-session)

When the user says "switch to the private/local lane" and the configured `base_url`
endpoint times out, **do not conclude "the host moved" or "the host is down" from a
single failed curl or a ping drop.** Diagnose layer by layer — the failure is almost
always "host rebooted and the model server didn't auto-start," not a relocation.

The diagnostic ladder (full probe sequence in `references/lan-lane-diagnosis.md`):

1. **ARP / layer-2 first.** `ip neigh | grep <ip>`. If the host shows `REACHABLE`
   (or even `STALE`) with a real MAC, its NIC answered an ARP — **the machine is on
   the network**, regardless of what higher layers do. A host that truly moved/left
   drops off the ARP table entirely (`FAILED`/absent).
2. **ICMP lies.** `ping` can show **100% loss while the host is perfectly alive** —
   many boxes firewall ICMP. Never declare a host down on ping loss alone when ARP
   says `REACHABLE`.
3. **SSH (port 22) open = host alive, model server just didn't start.** This is the
   decisive split. If `/dev/tcp/<ip>/22` connects but every LLM port (8080/8000/1234/
   11434/5000) is closed, the box booted fine and the *inference server process*
   isn't running. That's a "start the server" problem, not a "find the host" problem.
4. **Only if the model genuinely moved hosts:** sweep the LAN by MAC, not by stale IP.
   <gpu-host> the ARP table with a parallel ping sweep, then port-scan every live neighbor.
   No `nmap`/`arp-scan`/`fping` needed — bash `/dev/tcp` + backgrounded pings work:
   ```bash
   for i in $(seq 1 254); do (ping -c1 -W1 192.0.2.$i >/dev/null 2>&1 &); done; sleep 6
   ip neigh | grep -i 192.0.2 | grep -ivE 'FAILED|INCOMPLETE'   # live hosts
   # then for each live ip, probe candidate ports via /dev/tcp
   ```
   Beware false positives: `:8080` open on the router (`.1`) is usually a Tomcat/admin
   UI (returns 404 on `/v1/models`), and a port that accepts the TCP connect but
   **hangs with zero bytes** on `/v1/models` is a different service squatting the port
   or a server still warming — not necessarily your lane.

**The honest landing + durable fix.** Once you've localized it ("host up, server
down"), the real fix is usually a remote restart over SSH — but if there's **no key
on the box yet** (`Permission denied (publickey,password)`), you cannot do it without
the user. Don't hand a half-asleep / wind-down user a terminal to SSH in and restart a
daemon just to reach a lane. State the diagnosis plainly, defer to morning, and offer
the *durable* fix: install an SSH key on the box (a one-time bootstrap from password to key auth) **and**
an auto-start unit (systemd service / `@reboot` / Windows service) so the lane never
greets them cold after a reboot again. The recurring fault here is environmental
(server didn't auto-start) — capture the auto-start fix, never "the local lane is
broken."

## llama-server exits silently during model load ("fitting params to device memory")

Confirmed 2026-06-05 on a 24GB card: a fresh llama-server launch repeatedly **exited within ~40s** with the log frozen at:
```
common_init_result: fitting params to device memory ...
common_init_result: (for bugs during this step try to reproduce them with -fit off, or provide --verbose logs if the bug only occurs with -fit on)
```
No error line, no OOM message — the process is just *gone* on the next `Get-Process` check. Diagnosing this:

1. **The crash does NOT flush an error to the redirected log.** A hard CUDA/allocation fault during load can kill the process before stdout/stderr buffers flush to the `> log 2>&1` file. So "log ends mid-load + process exited" is the *signature of an OOM/fit failure*, not a mystery. Don't keep waiting for an error that will never be written.

2. **Read the GPU line in the log correctly — system RAM ≠ VRAM.** The startup log prints something like `CPU : Intel(R) ... (65449 MiB, 48940 MiB free)` — that 65449 is **system RAM**, easy to misread as a 64GB GPU. Get the real VRAM from `nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader` (note: pass **one** `--query-*` switch per call — combining `--query-gpu` and `--query-compute-apps` errors with "Only one --query-* switch can be used at a time"). The decisive number is `memory.free`, and on a desktop Windows box the compositor + Edge/WebView + OneDrive + ComfyUI/Python can already be holding 10GB+ of a 24GB card.

3. **A Q3 ~16GB GGUF does NOT fit in ~14GB free VRAM with `-ngl 999`.** `-ngl 999` forces *all* layers onto GPU; if they don't fit, the new-llama.cpp auto-fit (`-fit on`, the default) bails at exactly the line above. Fixes, in order of preference:
   - **Free VRAM first** (best): stop the idle GPU squatters — but note the two respawn traps below (Ollama service, ComfyUI process).
   - **Lower the offload**: `-ngl <N>` (e.g. 40–60 for a 35B-A3B on 24GB) so the remainder spills to CPU RAM. Slower but it loads.
   - **`-fit off`** disables the autosizer the log itself suggests, but it does NOT create VRAM that isn't there — if you still over-request `-ngl`, it OOMs anyway (confirmed: `-fit off -ngl 55` still died when ~10GB was already occupied). `-fit off` is for working around autosizer *bugs*, not for overcommitting memory.
   - **Use the smaller quant/model**: a Q3_K_M 27B (~12.7GB) seats where a Q3_K_XL 35B (~15.7GB) won't (see `references/qwen27-vs-35b-on-24gb.md`).

4. **Verify "alive" the right way.** `Start-Process`-launched llama-server can report `procs: 1` two seconds after launch (process exists, loading weights) and be **gone** 40s later (load failed). As with any detached Windows job, do not trust the 2-second PID check — re-probe after the expected load time with `Get-Process llama-server` AND check whether `:8080` actually bound (`Get-NetTCPConnection -State Listen -LocalPort 8080`). Port bound = load succeeded; process gone = it died loading.

**The honest landing for a wind-down user.** If freeing VRAM means killing the user's Edge/ComfyUI/desktop apps, or the model simply won't seat tonight, this is iterative GPU-fit debugging — not a 2-minute fix. Don't disappear into it while the user is waiting in bed. State the diagnosis ("host up, server won't seat the model in the free VRAM"), defer the real fix (free VRAM / pick the smaller quant / set an auto-start) to when you can see it properly, and capture the durable fix as auto-start config, never "the local lane is broken."

## Context Window Guidance

For creative/intimate/long-session writing, 32K context is insufficient — Hermes's own prompt overhead plus a developing scene will exceed 32K quickly. Target 64K minimum, 96K preferred.

On an RTX 3090 (24GB), the practical path is:
- Drop from UD-Q4_K_XL (~20.8GB) to UD-Q3_K_XL (~16.9GB) — same model, smaller quant
- Run with quantized KV cache (`--cache-type-k q8_0 --cache-type-v q8_0`)
- This frees enough VRAM to serve 96K context comfortably (confirmed: ~19.2GB used, 5GB free)

The Hermes config can declare `context_length = 262144` (model family max) to bypass Hermes's internal 64K gate — the live server `-c` value is the real ceiling.

## Setting up a separate profile cleanly (recommended pattern)

When the user wants a private/intimate/local lane that doesn't disrupt their daily Hermes setup, **don't switch the default profile** — create a dedicated one. Mid-session model swaps are not possible in a running Hermes chat anyway (the session is bound to its initial provider).

```bash
# Create profile (clones config + .env + SOUL.md from currently-active profile)
hermes profile create local-intimate --clone \
  --description "Local Qwen on <gpu-host> via llama.cpp. Private lane off hosted providers."

# Configure WITHOUT switching active profile — use HERMES_HOME override per-command
HERMES_HOME=~/.hermes/profiles/local-intimate hermes config set model.default <gguf-id-from-/v1/models>
HERMES_HOME=~/.hermes/profiles/local-intimate hermes config set model.provider custom
HERMES_HOME=~/.hermes/profiles/local-intimate hermes config set model.base_url http://<host>:8080/v1
HERMES_HOME=~/.hermes/profiles/local-intimate hermes config set model.api_mode chat_completions
HERMES_HOME=~/.hermes/profiles/local-intimate hermes config set model.context_length <live-n-ctx>

# Profile creation auto-installs a wrapper at ~/.local/bin/<profile-name>
# Use the wrapper directly — it's cleaner than `hermes --profile <name> chat`
local-intimate chat -q "Say only 'local lane online'" -Q
```

**Key invariants:**
- `hermes profile create NAME` takes `--clone` (clone the active profile) or `--clone-from SOURCE` — NOT a positional source arg. `hermes profile create foo default` errors out as "unrecognized arguments: default".
- The auto-created wrapper at `~/.local/bin/<name>` is the canonical invocation. Always.
- `HERMES_HOME=<profile-path> hermes config set ...` is the safest way to mutate a non-active profile without `hermes profile use` side effects.
- `model.context_length` must match the live `n_ctx` reported by `/v1/models` exactly. The skill's earlier rule (no lower than 64K) still applies.

## "Slow turns" diagnostic ladder — verify before fixing

When the user says the local lane "feels slow," resist the urge to start
restructuring Hermes's prompt assembly code. Walk this ladder first; the
architecture is almost always fine and the answer is usually physics or a
gateway lifecycle event, not a Hermes bug.

1. **Distinguish cold first-turn from warm follow-ups.** A cold turn on
   Qwen3.6-35B-A3B Q4 with a 7k-token prompt on a 3090 is genuinely 90–120s
   of prompt eval. That's not a bug, that's prefill physics at ~70 tokens/sec.
   Ask: is the user complaining about the FIRST reply of a session, or about
   reply N where N>1?
2. **Check for an interrupted previous turn.** Grep `agent.log` for
   `reason=interrupted_during_api_call` near the time of the complaint. If a
   gateway restart killed her mid-stream, the next turn is a fresh cold start
   AND the user saw a truncated reply — both feel like "slowness" to the user
   but the cause is the interrupt, not throughput.
3. **Read `/slots` LIVE while she's replying.**
   `curl -s http://<host>:8080/slots` shows `n_prompt_tokens_processed` climbing
   in real time. If `n_prompt_tokens_cache > 0`, the cache IS hitting — any
   remaining latency is decode speed (~60 t/s = 1s per sentence). If
   `n_prompt_tokens_cache == 0`, **then** investigate cache misses.
4. **Run the two-call cache test** from
   `references/prefix-cache-verification.md` against the live llama-server.
   If turn-2 hits 99–100% cache, the prompt content is cache-friendly and
   Hermes IS sending it byte-identical. If turn-2 also misses, then there's
   prompt drift — only THEN dig into Hermes's prompt assembly.
5. **If config got leaner mid-session, suspect the stored-prompt gotcha** —
   see `references/lean-config-active-session-gotcha.md`. The active session
   is correctly replaying the OLD fat prompt (good for cache stability, bad
   if you wanted the new lean version applied now). NULL the stored prompt
   to force a rebuild.

The lesson learned the hard way 2026-06-06: I assumed prefix caching was
broken based on a single observation of `n_prompt_tokens_cache: 0` and
started reading `system_prompt.py` looking for the bug. The slot was
showing 0 because that turn was a cold-start *after a gateway restart* —
the cache had been wiped, not a code bug. Always measure twice (cold then
warm) before assuming the architecture is wrong.

## Pitfall: cloud fallback on a privacy-scoped local lane leaks the user's message

When the user wants a hosted fallback (copilot/openrouter/etc.) behind a *private/
intimate/local-only* lane, a bare `fallback_providers` entry defeats the lane's
entire purpose. Verified 2026-06-09 against `fallback-providers.md` +
`gateway/run.py`: Hermes fallback is **turn-scoped and preserves the conversation —
it re-sends the user's current message to the fallback provider** — and it triggers on
**connection errors** (HTTP 429/5xx/401/403/404 AND connection drops). A local server
that's simply down (port closed after a reboot) is a connection error, so the failover
fires and transmits whatever the user just typed to the cloud. For a privacy lane that
is the exact leak you were hired to prevent.

Treat fallback + a firewall as ONE system:
- The only hook that can block a message **before** the model/cloud call is the
  **`pre_gateway_dispatch` plugin hook** (can return `{"action":"skip"|"rewrite"}`).
- `pre_llm_call` (shell hook) is **inject-only — it CANNOT block.** A "refuse if
  sensitive" instruction there is too late; the content is already in the outbound
  payload. Don't sell it as a firewall.
- Gate plain chat only — let `/`-prefixed slash/quick commands pass, since they
  dispatch after the hook and you don't want to block the command that recovers the lane.
- Probe the local endpoint in the hook and **fail closed** (probe error → treat as
  down/refuse, never allow), because hook exceptions otherwise fall through to normal
  dispatch = the message flows.

For the worked end-to-end design (plugin layout, `SessionSource`/`MessageEvent` fields,
adapter send signature, `/start-local` quick_commands, and the down-state A/B/C menu)
see the `<gpu-host>-intimate-lane-bringup` skill's
`references/cloud-fallback-privacy-firewall.md`.

- **Pitfall: adding `fallback_providers` to a PRIVATE local lane leaks content to the cloud.**
  `fallback_providers` is turn-scoped and **re-sends the user's message to the fallback** (fires on rate-limit, 5xx, auth, AND connection-refused). On a local-only privacy/intimate lane, a bare cloud fallback ships whatever the user just typed to the cloud provider the instant the local server hiccups. If you want a fallback for *availability*, you MUST pair it with a front-door firewall: a `pre_gateway_dispatch` **plugin** hook (the only hook that can block BEFORE the model is called — `pre_llm_call` can only inject, too late) that probes the local server and blocks/rewrites sensitive inbound when it's down. Full pattern: `<gpu-host>-intimate-lane-bringup` skill, `references/privacy-firewall-and-fallback.md`.

- **Pitfall: a profile plugin silently does nothing because `plugins.enabled` is an opt-in allow-list.**
  When `plugins.enabled` in `config.yaml` is a populated list, ONLY listed plugins load; an unlisted user plugin under `~/.hermes/profiles/<name>/plugins/` is **discovered-but-disabled** (logs `Skipping 'X' (not in plugins.enabled)` at DEBUG). Files on disk + a gateway restart is NOT proof it's active. Verify by the **enabled** count in `Plugin discovery complete: N found, M enabled` rising by 1 (found rising ≠ enabled), plus the plugin's own register log line. Fix: add the plugin's manifest `name` to `plugins.enabled`.

- **Pitfall: aux tasks pinned to a NAMED-custom provider fail CLOSED (this is good — no transcript leak).**
  When `auxiliary.<task>.provider` points at a `custom_providers` entry (e.g. `provider: local`) and the local server is down, the named-custom branch in `auxiliary_client.py` returns a client pointed at the local base_url and the call simply connection-refuses — it does **NOT** fall through to the cloud auto-chain (`_resolve_api_key_provider`). That fallthrough exists only in the *anonymous* `provider: custom` branch. So compression (which sends transcript history), title-gen, vision, etc. pinned to a named-custom local provider can't silently leak to the cloud when local is down. Rely on this; don't build redundant defense against it.

- **Pitfall: `hermes gateway restart` refuses from inside a running gateway.**
  Restarting a *different* profile's gateway from within an agent session that is itself running under a gateway gets `Refusing to restart the gateway from inside the gateway process` (restart-loop guard). Use `systemctl --user restart hermes-gateway-<profile>.service` instead.

## Common pitfalls
- **Pitfall: calling a profile "lightweight" without changing the live server runtime.**
  A second Hermes profile pointing at the same 35B server is not lighter by itself. If VRAM sharing with image generation matters, lower the server's live `-c` (or use a genuinely smaller model) and point the lightweight profile at that separate endpoint.

- **Pitfall: dropping below Hermes's own minimum context floor.**
  Hermes may reject very small local contexts even if llama.cpp serves them successfully. In practice, a `model.context_length` below **64K** is not a valid general-purpose Hermes lane; use **64K as the lowest "lite" target** unless you have a specialized non-Hermes caller.

- **Pitfall: measuring VRAM while two llama-server instances are up.**
  If both the full lane and the lite lane are still running, VRAM readings are misleading and the second server may sit in a long "Loading model" state. Stop stale local servers before judging whether the lite lane actually fits.

- **Pitfall: using docs/UI shorthand as the runtime provider string.**
  `custom:<name>` may be a switcher/menu syntax, not the literal low-level provider field Hermes runtime expects.

- **Pitfall: declaring a huge context in Hermes while the server is still running with a tiny `-c`.**
  This only moves the failure later. The server's real context must accommodate Hermes's prompt.

- **Pitfall: treating an OOM as final before checking stale GPU users.**
  Old local inference processes can make a model look impossible when it actually fits after cleanup.

- **Pitfall: stopping after `/health` works.**
  A healthy server is not the same thing as a healthy Hermes integration.

- **Pitfall: assuming `nvidia-smi --query-compute-apps` shows VRAM per process.**
  On consumer Windows GPUs (RTX 3090, etc.), `--query-compute-apps=pid,process_name,used_memory` reports `N/A` for `used_memory` — the per-process accounting only works on data-center GPUs (A100/H100). To find what's holding VRAM on a 3090/4090, run `nvidia-smi` plain and parse the process table, or shell into the suspected owner and check directly.

- **Pitfall: assuming `taskkill /F /IM ollama.exe` actually frees the GPU.**
  Ollama installs as a Windows service that auto-respawns within seconds. Killing the .exe is theatre — the service brings it right back. If you need Ollama actually gone, stop the service (`sc stop "Ollama"` if it exists) or accept that it will respawn but typically without a loaded model (so the VRAM hit is small).

- **Pitfall: ComfyUI's `/free` endpoint only releases the loaded model, not the process.**
  POSTing to `http://comfyui:8188/free` with `{"unload_models":true,"free_memory":true}` only frees a few hundred MB if ComfyUI hasn't been actively serving — the bulk of its VRAM is the loaded model. If you need real headroom, taskkill the ComfyUI parent PID (the python.exe listening on :8188), not just the model.

- **Pitfall: mid-session provider swap.**
  You cannot change a running Hermes chat's provider mid-conversation. The session is bound to its initial provider for the lifetime of the conversation (preserves prompt caching, role alternation). To switch lanes, you must start a new session — either `/reset` in the same profile, or invoke a different profile entirely. Plan accordingly when offering the user a "switch to local" option mid-chat.

- **Pitfall: assuming the Hermes config model name matches what the server is actually serving.**
  The server may have multiple GGUF files but only one loaded. Always hit `/v1/models` to see what the server *actually* reports before writing `model.default`. The name in Hermes config must match the `id` field from `/v1/models` exactly. A mismatch means Hermes will try to call a model the server doesn't know about.

- **Pitfall: switching config models without verifying the new model is actually loaded.**
  After changing `model.default`, still hit `/v1/models` and confirm the reported model ID matches your config. If it doesn't, the server hasn't loaded it yet.

## Verification checklist
- Local endpoint `/health` or equivalent returns success.
- `/v1/models` returns the expected model — **cross-check the `id` field against `model.default` in config.**
- **Model name alignment:** If the `id` from `/v1/models` differs from `model.default`, fix with `hermes config set` and verify Hermes itself can answer through the corrected provider.
- `nvidia-smi` shows the model really loaded where expected.
- A direct completion request works.
- Hermes itself successfully answers through the local provider.

## Verification checklist
- Local endpoint `/health` or equivalent returns success.
- `/v1/models` returns the expected model.
- `nvidia-smi` shows the model really loaded where expected.
- A direct completion request works.
- Hermes itself successfully answers through the local provider.

## References
- `references/prefix-cache-verification.md` — how to verify llama.cpp's prefix cache is actually reusing tokens end-to-end (the `cache_n` / `n_prompt_tokens_cache` numbers, the two-call test, healthy throughput rates on a 3090). Run this BEFORE assuming Hermes has a prompt-cache bug.
- `references/lean-config-active-session-gotcha.md` — why making a profile leaner doesn't speed up an *existing* session (Hermes correctly replays the stored fat prompt for cache stability), and the SQL fix to NULL the stored prompt and force a rebuild.
- `references/lan-lane-diagnosis.md` — diagnosing an unreachable local lane: ARP/layer-2 vs ICMP vs SSH-open, the host-moved/host-down/server-down decision table, and LAN sweep probes using only stock bash `/dev/tcp` (no nmap).
- `references/local-private-lane-pattern.md` — recipe for spinning up a private companion profile against a local llama.cpp endpoint mid-session, so sensitive conversation never leaves the user's hardware.
- `references/windows-3090-qwen-xl-llamacpp.md` — concrete Windows + 3090 + llama.cpp + Qwen XL integration notes from a successful session.
- `references/q3-q4-model-mismatch.md` — session where config pointed to Q4 but server was only serving Q3; how to detect and fix.
- `references/qwenlite-image-coexistence.md` — how to build a truly lighter companion Hermes profile for sharing a 24 GB GPU with image generation.
- `references/qwen27-vs-35b-on-24gb.md` — why a smaller 27B model can be a better concurrent text+image lane than squeezing the same 35B harder.
