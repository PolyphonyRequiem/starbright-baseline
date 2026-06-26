# Q3 vs Q4 Model Name Mismatch

## Session: 2026-05-28
**Symptom:** Config pointed to `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` but local server only served `Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf`.

## What happened
- Both Q3 and Q4 GGUF files existed on disk in `~/models/qwen36/`.
- The local llama.cpp server was only running the Q3 variant (~16.9GB).
- Hermes config was set to the Q4 model name — mismatch with server's actual serving model.
- Fix: queried `/v1/models` to discover the actual running model ID, then updated `model.default` to match.

## How to detect
```bash
curl -s http://localhost:8080/v1/models | jq '.data[].id'
```
Compare the output against `model.default` in config. If they don't match, the server is serving a different model than Hermes expects.

## Lesson
Always verify `/v1/models` after any config change. The server's reported model ID must match the config's `model.default` exactly.
