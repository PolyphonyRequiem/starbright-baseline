# Windows 3090 + llama.cpp + Hermes + Unsloth Qwen 3.6 XL

## Successful session shape
- Host: Windows 10
- GPU: RTX 3090 24 GB
- Runtime: llama.cpp Windows CUDA build
- Model: `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`
- Local server endpoint: `http://127.0.0.1:8080/v1`

## Working binary/runtime notes
- Ollama installed cleanly but was not the chosen runtime for the exact Unsloth GGUF.
- Official llama.cpp Windows CUDA release worked.
- `llama-cli.exe --list-devices` should show the 3090 after the CUDA runtime DLL bundle is present.
- On Windows, stale `llama-cli.exe` / `llama-server.exe` processes can keep most of VRAM allocated even after a failed experiment. Check and clear them before judging fit.

## Model fit notes
- `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` size observed: `22,360,456,160` bytes.
- On a clean 3090, this exact model can load with a 32K server context when launched carefully.
- A 4K server context is not enough for Hermes itself because Hermes's prompt/request can already exceed that.

## Hermes integration notes
- Runtime succeeded only after treating Hermes and llama.cpp as separate layers.
- Hermes needed explicit local-endpoint configuration and a context-length override.
- The named `custom_providers` metadata was useful, but not sufficient by itself.
- The low-level runtime provider still needed to be set to `custom` with the local `base_url`.
- Final proof was a real `hermes chat` request, not just curl.

## Durable lesson
When hooking Hermes to a local model, a failure can come from:
1. wrong provider syntax,
2. missing context metadata,
3. the server's actual live `-c` being too small,
4. stale GPU processes consuming VRAM.

Treat those as four separate checks, in that order.
