# Verifying llama.cpp Prefix Cache Reuse End-to-End

## Why this exists

When a local-LLM lane "feels slow," the first instinct is to assume Hermes is
sending a different system prompt every turn (cache busting). On 2026-06-06 I
spent significant time tearing into Hermes's prompt assembly code (`system_prompt.py`,
`conversation_loop.py`, `chat_completion_helpers.py`) before realizing the
architecture was correct all along — the stored prompt is replayed byte-identical
each turn, the cache works, and the "slow turns" were just genuine cold-start
prompt eval physics on a 35B Q4 on a 3090.

This reference is the verification methodology that **proves** prefix cache is
working before you assume it isn't.

## The decisive numbers

llama.cpp's `/v1/chat/completions` response carries a `timings` block:

```json
{
  "timings": {
    "cache_n": 1205,           // tokens reused from prefix cache
    "prompt_n": 13,            // tokens that needed fresh prefill
    "prompt_ms": 1140.331,
    "prompt_per_second": 11.4,
    "predicted_n": 5,
    "predicted_per_second": 5.5
  },
  "usage": {
    "prompt_tokens": 1218,
    "prompt_tokens_details": {"cached_tokens": 1205}
  }
}
```

`/slots` (no auth, GET) gives you the same view of the *currently-processing*
turn:

```bash
curl -s http://<host>:8080/slots | python3 -m json.tool
```

Look for `n_prompt_tokens_cache` (the cache reuse count) and
`n_prompt_tokens_processed` (the fresh-prefill count). If `is_processing: true`
and you watch `n_prompt_tokens_processed` climb, that's the prefill bottleneck
in real time.

## The two-call cache test

Send the **same system prompt** twice with different user messages. If the
second call shows `cache_n` ≈ `prompt_tokens` and `prompt_n` is small, the
cache is working. If `cache_n` is 0 on the second call, *something* in your
prompt is drifting between turns.

```python
import json, time, urllib.request

SYSTEM = "Your full system prompt here..."

def call(user_msg):
    body = json.dumps({
        "model": "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 5,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "http://192.0.2.175:8080/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    return time.time()-t0, d["timings"]["cache_n"], d["usage"]["prompt_tokens"]

t, c, p = call("First")
print(f"Turn 1: {t:.1f}s  cache={c}/{p}  ({100*c/max(p,1):.0f}% hit)")
t, c, p = call("Second")
print(f"Turn 2: {t:.1f}s  cache={c}/{p}  ({100*c/max(p,1):.0f}% hit)")
```

Healthy result on a 3090 with a 7k-token prompt:

```
Turn 1: 109.5s  cache=0/6798  (0% hit)        ← cold prefill, expected
Turn 2:   1.2s  cache=6784/6800  (100% hit)   ← warm cache, expected
```

If turn 2 is also slow with `cache_n=0`, **then** start hunting for prompt
drift. Until then, the cache is fine.

## Testing with the actual stored Hermes prompt

To verify Hermes's stored prompt would cache cleanly, read it from the session
DB and feed it to llama-server directly:

```python
import sqlite3, json, urllib.request, time

db = sqlite3.connect("/home/<user>/.hermes/profiles/<profile>/state.db")
cur = db.cursor()
cur.execute("SELECT system_prompt FROM sessions WHERE id=?", (session_id,))
real_system = cur.fetchone()[0]
db.close()

# now feed real_system to llama-server twice — see two-call test above
```

This isolates "is the stored prompt cache-friendly" from "does Hermes actually
send the stored prompt." If this two-call test shows 100% hit on turn 2, the
prompt content is fine and Hermes IS sending it byte-identical (or there's a
bug in Hermes — but verify the prompt first).

## Cache eviction is NOT a problem at typical scale

Llama.cpp's prefix cache holds multiple distinct prefixes and only evicts when
full. Tested 2026-06-06: an "aux" call with a completely different system
prompt did NOT evict the conversation's cache:

```
A turn 1: 20.6s cache=0/1217      ← cold A
A turn 2:  0.8s cache=1205/1218   ← warm A
B (aux):  22.3s cache=0/1519      ← cold B (different prompt)
A turn 3 (after aux):  0.9s cache=1205/1220   ← A still warm!
```

So title-generation, skill-ranking, and other auxiliary calls don't sabotage
conversation latency.

## What healthy prompt-eval rates look like (RTX 3090, Qwen3.6-35B-A3B Q4_K)

- **Cold prefill:** ~60–80 tokens/sec → 7k token prompt = ~90–120s
- **Decode (generation):** ~60–70 tokens/sec → ~1s per sentence
- **Warm cache turn-2 latency:** ~1–3s for the first token, then full decode speed

If your warm-turn latency is much higher than ~3s, the cache really is
missing — investigate prompt drift. If your cold-turn latency matches the math
above, that's just physics; no Hermes bug to chase.

## The `--metrics` flag is required for `/metrics`

`curl http://<host>:8080/metrics` returns 501 unless llama-server was launched
with `--metrics`. `/slots` and the `timings` block in `/v1/chat/completions`
work without it and carry the same essentials.
