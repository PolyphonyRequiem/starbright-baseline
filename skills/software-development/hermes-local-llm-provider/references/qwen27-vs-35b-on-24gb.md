# Qwen 27B vs 35B on a 24 GB GPU when image generation also matters

Condensed notes from a Windows + RTX 3090 session where Hermes, llama.cpp, and ComfyUI needed to coexist.

## Situation
- Installed local GGUFs at start:
  - `Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf`
  - `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`
- Goal was not just "fit a local model" but "leave enough VRAM headroom that image generation is still practical."

## What did NOT help enough
### Same 35B model, lower live context only
A separate "lite" profile pointing to the same 35B Q3 model with a lower-context llama.cpp server is real and useful, but it is not a dramatic VRAM reduction.

Important constraint discovered during verification:
- Hermes rejected `model.context_length = 16384` as below its practical minimum.
- A **64K** lane was the lowest generally valid Hermes profile target in this setup.

So a 35B "lite" lane can help, but it is still a 35B lane.

## Better move for concurrency
### Prefer a smaller model over squeezing the same big model harder
For simultaneous local text + image generation on a 24 GB card, the cleaner tradeoff was:
- move from **35B Q3** to **27B Q3_K_M**
- keep a real Hermes-valid context window (**64K**)
- run it on a separate port so it is measurable and controllable

## Concrete model picked
- Repo: `unsloth/Qwen3.6-27B-GGUF`
- File: `Qwen3.6-27B-Q3_K_M.gguf`
- Size from tree API / HEAD check: `13,586,217,184` bytes (~13.6 GB)

Other plausible nearby files from the same repo:
- `Qwen3.6-27B-Q3_K_S.gguf` — ~12.4 GB
- `Qwen3.6-27B-UD-Q3_K_XL.gguf` — ~14.5 GB
- Very low-bit IQ2 variants exist, but they are a "fit first, quality second" choice.

## Verified runtime shape
Example launch that worked for the 27B lane:

```bash
llama-server.exe \
  -m /path/to/Qwen3.6-27B-Q3_K_M.gguf \
  -c 65536 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  -ngl 99 \
  --port 8082
```

Verified result:
- `/v1/models` reported `id = Qwen3.6-27B-Q3_K_M.gguf`
- `/v1/models` reported `n_ctx = 65536`
- Hermes itself succeeded through a dedicated `qwen27` profile

## Practical recommendation
If the user says some version of:
- "Can we make the local lane lighter?"
- "I want text and image gen at the same time"
- "Should we use a lower quant or a smaller model?"

Prefer this order:
1. **Smaller model first** (e.g. 27B Q3_K_M)
2. Then lower context if needed
3. Only then consider very aggressive low-bit quants

Reason: a smaller model usually preserves the overall feel better than pushing the same larger model to very low-bit extremes, while also giving cleaner VRAM headroom.

## Pitfall
Do not claim success just because the new profile exists. The actual proof is:
1. old llama-server processes are stopped,
2. the new port reports the expected model ID and live context,
3. a real Hermes query succeeds through the new profile.
