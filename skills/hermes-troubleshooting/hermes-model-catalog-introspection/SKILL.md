---
name: hermes-model-catalog-introspection
description: Query the LIVE model catalog of a Hermes provider (Copilot, OpenRouter, Nous, Anthropic, ...) to get authoritative model IDs, context windows, output limits, supported reasoning levels, thinking budgets, and capability flags before recommending or switching a model. Use this any time the user asks "can I use model X with Y?" — never guess from training data or stale memory.
version: 1.0.0
author: Hermes Agent
license: MIT
created_by: agent
metadata:
  hermes:
    tags: [hermes, providers, models, copilot, introspection, routing]
---

# Hermes Model Catalog Introspection

When the user names a model and asks whether Hermes can route to it — especially with a specific reasoning level, context window, or capability — **always hit the live provider catalog** before answering. Model SKUs, context limits, and reasoning-effort enums change month to month. Quoting from cached memory or training data is the failure mode this skill exists to prevent.

## Triggers

Load this skill when the user:
- Asks about a specific model variant ("Sonnet 4.8 xhigh", "Opus 4.7 1M", "Gemini 2.5 Pro").
- Wants to know context length, output cap, or supported reasoning levels.
- Wants to confirm a model name before issuing `/model <name>` or `hermes config set model.default`.
- Reports a model name that doesn't sound right ("Sonnet 4.8" — does that exist?).
- Asks "what's the most capable model I have access to right now?"

## Core rule

**Authoritative source for any provider is `${provider_base_url}/models`** — not the agent's training data, not a cached catalog file, not a docs page.

For Hermes itself there are two stale-able catalogs:
- `~/.hermes/cache/model_catalog.json` — a Hermes-side cache. Only knows providers Hermes has fetched recently. Often missing Copilot entirely.
- `hermes_cli.models._fetch_github_models(token)` — returns Copilot model IDs as **bare strings**, no capability metadata. Useful for ID lookup, useless for limits/reasoning.

The full capability payload only comes from the live provider endpoint.

## Recipe: query the live Copilot catalog

Copilot is the trickiest because it gates its catalog behind a token exchange. Use Hermes's own auth helpers — do **not** try to hand-roll the exchange (the `copilot_internal/v2/token` endpoint 404s without the right `User-Agent` / `Editor-Version` / `Editor-Plugin-Version` headers).

```python
# Run inside the hermes-agent venv, e.g.
#   cd ~/.hermes/hermes-agent && source venv/bin/activate && python3
import json, urllib.request
from hermes_cli.copilot_auth import (
    resolve_copilot_token,
    get_copilot_api_token,
    copilot_request_headers,
)

gh_tok, _source = resolve_copilot_token()        # returns TUPLE, not str
api_tok = get_copilot_api_token(gh_tok)          # exchanges via cached helper
headers = copilot_request_headers()              # NO positional args — kwargs only
headers["Authorization"] = f"Bearer {api_tok}"

req = urllib.request.Request("https://api.githubcopilot.com/models", headers=headers)
catalog = json.loads(urllib.request.urlopen(req, timeout=15).read())

for m in catalog["data"]:
    mid = m["id"]
    caps = m.get("capabilities", {})
    lim = caps.get("limits", {})
    sup = caps.get("supports", {})
    print(f"{mid:40s} ctx={lim.get('max_context_window_tokens')} "
          f"out={lim.get('max_output_tokens')} "
          f"reasoning={sup.get('reasoning_effort')} "
          f"thinking={sup.get('adaptive_thinking', False)}")
```

Output gives, per model:
- `id` — exact string to pass to `/model` or `model.default`.
- `capabilities.limits.max_context_window_tokens` — real context window.
- `capabilities.limits.max_output_tokens` — output cap.
- `capabilities.supports.reasoning_effort` — list of accepted enums (e.g. `["low","medium","high","xhigh","max"]`). If `xhigh` isn't in the list for a given model, `/reasoning xhigh` will silently downshift.
- `capabilities.supports.adaptive_thinking` / `max_thinking_budget` — extended-thinking knobs.
- `capabilities.supports.vision`, `tool_calls`, `parallel_tool_calls`, `structured_outputs`, `streaming`.

A self-contained runnable copy lives at `scripts/probe_copilot_catalog.py` in this skill.

## Recipe: other providers

For OpenAI-compatible providers (OpenRouter, Anthropic, Nous, DeepSeek, Z.AI, etc.):

```bash
# Resolve base_url + api_key the same way Hermes does, then:
curl -sS "${BASE_URL}/v1/models" -H "Authorization: Bearer ${API_KEY}" | jq .
```

Each provider returns differently-shaped capability data — OpenRouter is the richest (includes per-model pricing, context, modalities), Anthropic's `/v1/models` is the leanest. When the field you want isn't there, check the provider's docs page; the live endpoint is still the source of truth for which model IDs are valid *right now*.

## Switching model + reasoning from Discord / a session

Once you've confirmed the SKU and that the reasoning enum is supported, the in-session route is two slash commands:

```
/model <exact-id-from-catalog>
/reasoning <none|minimal|low|medium|high|xhigh|show|hide>
```

Both take effect on the **next** turn (the current turn finishes on the previous setting). `/reasoning` levels not in the model's `supports.reasoning_effort` list will be quietly clamped — that's why you check the catalog first.

Persistent equivalent (sticks across sessions):

```bash
hermes config set model.default <exact-id-from-catalog>
hermes config set model.reasoning_effort xhigh
```

## Pitfalls

### Pitfall: trusting a model name from memory or user paraphrase
A user once asked about "Sonnet 4.8 xhigh, 936K model" — the live catalog had **no** Sonnet 4.8 (only `claude-opus-4.8`), and the context was 1M, not 936K (the 936K they saw was probably the post-system-prompt usable budget some UI was reporting). Confirming the SKU before recommending a switch caught the name mismatch in one tool call instead of letting them issue `/model claude-sonnet-4.8` and watch it fail silently or fall back to a different model.

**Rule:** before answering "yes you can set model X with Y reasoning," run the catalog probe. State the exact ID, exact context, exact supported reasoning enums. Correct the user's name if it's off — they will thank you for catching it rather than feel corrected.

### Pitfall: hand-rolling the Copilot token exchange
The endpoint `https://api.github.com/copilot_internal/v2/token` returns `404 Not Found` for any `User-Agent` / `Editor-Version` / `Editor-Plugin-Version` combo other than the very specific strings VS Code / Copilot CLI / Hermes use. Don't waste turns iterating on headers — `hermes_cli.copilot_auth.get_copilot_api_token(raw_token)` already handles it correctly and caches the result with refresh.

### Pitfall: function signatures
Two signatures in `hermes_cli.copilot_auth` that have bitten this skill once already:

- `resolve_copilot_token()` returns a **tuple `(token, source)`**, not a bare string. Unpack it.
- `copilot_request_headers(*, is_agent_turn=True, is_vision=False)` takes **only keyword arguments**. `copilot_request_headers(api_tok)` raises `TypeError`. Set `headers["Authorization"] = f"Bearer {api_tok}"` after the call.

### Pitfall: the Hermes-side cache is incomplete
`~/.hermes/cache/model_catalog.json` only knows providers that have been fetched recently through Hermes's own picker. As of 2026-06-04 on this host it had only `openrouter` and `nous` — Copilot wasn't in it at all. Don't grep that file expecting Copilot/Anthropic/Gemini data; go to the live endpoint.

### Pitfall: `_fetch_github_models` returns strings, not dicts
`hermes_cli.models._fetch_github_models(token)` returns a list of bare model-ID strings like `["claude-opus-4.8", "claude-sonnet-4.6", ...]`. It's fine for "does this ID exist?" but contains no capability data. For limits / reasoning / thinking budgets you must hit `https://api.githubcopilot.com/models` directly with the bearer token.

### Pitfall: dedicated reasoning-level SKUs are smaller-context
On Copilot: `claude-opus-4.7-high` and `claude-opus-4.7-xhigh` are **200K context** SKUs that hard-pin the reasoning level. The same-generation `claude-opus-4.7` (plain) is **1M context** and accepts `reasoning_effort` as a runtime knob (`["low","medium","high","xhigh","max"]`). If the user wants 1M + xhigh, route to the plain SKU and set `/reasoning xhigh`, not the `-xhigh` variant. Same pattern applies to the 4.8 line.

### Pitfall: silent reasoning downshift
If you set `/reasoning xhigh` on a model whose `supports.reasoning_effort` list doesn't include `xhigh`, it gets quietly clamped (usually to `high` or the model's max). The user thinks they're running xhigh, the bill says otherwise. Always cross-check the model's enum list before recommending the level.

### Pitfall: switching mid-task wastes the prompt cache
Switching `/model` or `/reasoning` mid-conversation resets prompt caching, which on long tool-heavy sessions (PRs, debugging) is a real cost. When the user asks to switch in the middle of work, mention the cache reset and let them choose whether to flip now or at the next natural break. Don't switch silently.

## Support files

- `scripts/probe_copilot_catalog.py` — runnable self-contained probe. Prints all Copilot models with full capability data. Run with `cd ~/.hermes/hermes-agent && source venv/bin/activate && python3 ~/.hermes/skills/hermes-troubleshooting/hermes-model-catalog-introspection/scripts/probe_copilot_catalog.py`.

## Verification

After answering a "can I use model X" question:
- Did you cite the **exact** model ID from the live catalog (not paraphrased)?
- Did you state the actual context window and the supported reasoning levels?
- If the user's name was wrong, did you correct it openly rather than route to the wrong SKU?
- If they want to switch mid-task, did you flag the prompt-cache reset?
