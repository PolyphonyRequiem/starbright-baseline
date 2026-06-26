# The 413 / payload-too-large compression cascade (byte limit ≠ token limit)

Traced 2026-06-08 from a live gateway incident on <main-host> (Discord session,
provider=copilot, model=claude-opus-4.8). The user sent "I think you broke, what
happened?" with a screenshot of a cascade of `Request Entity Too Large` errors.
This file is the full mechanism + log signatures + fix so a future session can
diagnose it in one pass instead of re-tracing.

## The core distinction — two DIFFERENT ceilings

There are two independent size limits on every model request, and they fail
differently:

| Limit | What it measures | Typical cause | What fixes it |
|---|---|---|---|
| **Context window / token budget** | TOKEN count of the messages | long text history | compaction (summarize old turns) — works |
| **Request body size (HTTP 413)** | BYTE size of the JSON request body | base64-encoded **images** in history | compaction does **NOT** help — see below |

A 413 (`Request Entity Too Large`) is a **byte-size** rejection from the provider
(or Hermes' own gateway cap), NOT a token-count rejection. Confusing the two is
the whole trap: the agent sees "too large," reaches for compaction, and compaction
can't touch the actual offender.

## Why images are almost always the culprit

Base64-encoded images are **token-cheap but byte-expensive**:
- A 4.8 MB PNG attachment becomes ~6.5 MB of base64 text inside the JSON body
  (base64 inflates ~33%).
- But that same image costs only ~1–2k **tokens** to the model.

So a session can be **well under** the token/context-window limit and STILL blow
the byte limit, purely from a few multi-megabyte screenshots stacked in history.
In the traced incident the session was 237 messages / ~185k tokens (token-fine for
a 200k window) but carried three screenshots of 3.6 MB, 4.3 MB, 4.8 MB — the bytes,
not the tokens, tripped the 413.

## Why compaction can't fix a 413 (the cascade)

Hermes' compaction summarizes **TEXT** turns. It does **not** strip or shrink
image content parts. So on a 413 the recovery loop does this
(`agent/conversation_loop.py`, `is_payload_too_large` branch ~line 2969, guarded by
`max_compression_attempts = 3` at line 1142):

1. 413 → compress. Drops/​summarizes old text: **237 → 8 messages**, ~185k → ~26k tokens. Retry. **Still 413.**
2. 413 → compress again: **8 → 6 messages**, ~26,635 → ~26,344 tokens. Retry. **Still 413.**
3. 413 → compress again: **6 → 6** (nothing left to drop). → `Cannot compress further`.
4. Compression attempts exhausted → `gateway.run: Auto-resetting session … after compression exhaustion.`

**The smoking gun in the logs:** token count *plateaus at ~26k while STILL getting
413*. 26k tokens is nothing — far under any window. If compaction keeps shrinking
tokens and the 413 persists, the payload is over a **byte** limit and the
base64 image rode through every compression pass untouched. Compressing text can
never shrink an image.

## Why the image-stripping path does NOT save you here

Hermes DOES have an image-stripping recovery path
(`agent/conversation_loop.py` ~2225–2304, `_strip_images_from_messages`), but it
fires only on **specific English rejection phrases** for text-only/multimodal-
unsupported models — e.g. `"only 'text' content type is supported"`,
`"image_url is not supported"`, `"does not support images"` — and is 4xx-gated. A
plain **413 `Request Entity Too Large` does not match any of those phrases**, so
the strip path never triggers; the request cascades into compression/​413 recovery
instead. (This is arguably a code gap: a 413 on an image-bearing payload *could*
strip/​downscale images before falling back to text compaction. If proposing a fix,
file it as a feature request — don't assert "it strips images on 413," it doesn't.)

## What auto-reset does and doesn't destroy

- **Preserved:** the full session transcript stays in `state.db` — auto-reset
  *ends* a session, it does not delete it. The pre-reset save-turn also runs
  (memories/skills get a chance to persist). Recoverable via `session_search`.
- **Lost:** any **in-flight autonomous loop state** (e.g. "iteration 7/100" of a
  running task). That does not survive a reset. A reply that was *trying* to send
  when the 413 hit is also lost — which is why the user perceives "it broke": the
  interrupt-to-answer fired, but the answer's own payload (history + a fresh
  multi-MB screenshot) was itself over the limit.

## Log signatures to grep (fast diagnosis)

```
grep -nE "413|payload too large|Cannot compress further|compression exhaustion|Auto-resetting" \
  ~/.hermes/logs/agent.log ~/.hermes/logs/errors.log | tail -40
```
- `summary=HTTP 413: Request Entity Too Large` — the rejection
- `context compression done: … messages=237->8 … rough_tokens=~26,635` then again
  `8->6` then `6->6` — the shrinking-token / persistent-413 plateau
- `ERROR … 413 payload too large. Cannot compress further.`
- `INFO gateway.run: Auto-resetting session … after compression exhaustion.`

Cross-check the offending images:
```
search_files(target='files', pattern='*', path='~/.hermes/image_cache')  # sort by size; multi-MB = suspects
```

## Relevant source (file:line, verified 2026-06-08)

- `agent/conversation_loop.py:1142` — `max_compression_attempts = 3`
- `agent/conversation_loop.py:2932` — `is_payload_too_large = (classified.reason == FailoverReason.payload_too_large)`
- `agent/conversation_loop.py:2943–2967` — special-case hint for GitHub Models (Azure)
  free tier: it caps every request at ~8K tokens (`models.inference.ai.azure.com`),
  which the system prompt alone exceeds → surfaces "not compatible" instead of
  looping compaction. (Different root cause, same 413 surface — don't conflate.)
- `agent/conversation_loop.py:2969–3010` — the payload-too-large compress/retry block
- `agent/conversation_loop.py:2225–2304` — the image-rejection-phrase strip path (does NOT fire on 413)
- `agent/error_classifier.py:158–161` — `_PAYLOAD_TOO_LARGE_PATTERNS = ["request entity too large", "payload too large", "error code: 413"]`
- `gateway/platforms/api_server.py:564–566` — Hermes' own gateway `MAX_REQUEST_BYTES` → 413
- `tools/vision_tools.py:346–349` — the vision tool's own too-large/413 detection (separate surface)

## The fix (operational — what to tell the user / do)

1. **Downscale images before attaching.** A screenshot at ~1200 px wide, webp
   quality ~80, is ~150–300 KB and keeps full diagnostic detail — vs a 4–5 MB raw
   PNG. (In-incident proof: the 170 KB error-cascade webp the user sent *sailed
   through* the same session that the 4.8 MB PNGs choked.)
2. **Put big images in a fresh session,** not one already hundreds of messages /
   100k+ tokens deep — every prior image is re-sent in the body on every turn.
3. **If it already cascaded:** the session auto-reset is recoverable — pull the
   prior context from the DB with `session_search`. Don't tell the user data is
   "lost"; tell them the session *ended* and the transcript is retrievable, only
   the in-flight loop state is gone.

## One-line takeaway

**"Too large" with shrinking tokens but a persistent 413 = a BYTE problem, not a
token problem. Look for multi-MB images in history; compaction can't fix it.**
