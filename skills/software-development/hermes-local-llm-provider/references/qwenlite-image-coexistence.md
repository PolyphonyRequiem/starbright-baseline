# Lightweight companion profile for local Qwen + image generation

Distilled from a Windows 10 + RTX 3090 session using Hermes profiles, llama.cpp, ComfyUI, and Qwen 3.6 35B Q3.

## Durable lessons
- A separate Hermes profile is **not** lighter unless it talks to a separate server runtime with a lower live `-c`.
- For Hermes itself, a `model.context_length` below **64K** is not a practical/valid local lane; a 16K llama.cpp server may answer curl requests but Hermes will reject it.
- To preserve GPU headroom for image generation, create a separate port for the lite lane and verify its live `n_ctx` independently via `/v1/models`.
- When testing fit, stale full-fat llama-server processes can make the lite lane look impossible. Kill or stop prior servers before measuring VRAM.

## Concrete shape that worked
- Full lane (`qwen`): `http://localhost:8080/v1`
- Lite lane (`qwenlite`): `http://localhost:8081/v1`
- Model: `Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf`
- Lite lane target context: **65536**
- Verified live `n_ctx` on lite port: **65536**
- Verified Hermes round-trip: `hermes -p qwenlite chat -q 'Reply with exactly: hermes qwenlite ready' --quiet`

## Example launcher shape
```sh
llama-server.exe \
  -m /c/Users/<winuser>/models/qwen36/Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf \
  -c 65536 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  -ngl 99 \
  --port 8081
```

## Verification checklist
1. `curl http://127.0.0.1:8081/v1/models` shows the expected model ID.
2. The same response reports `meta.n_ctx = 65536`.
3. `hermes -p qwenlite ...` succeeds, not just raw curl.
4. GPU memory is measured only after stale llama-server processes are gone.
