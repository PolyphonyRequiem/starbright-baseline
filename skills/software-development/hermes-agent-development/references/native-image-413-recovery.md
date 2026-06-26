# Native inline-image 413 recovery (main model, NOT vision_analyze)

There are **two completely different "vision is broken" failure classes** in Hermes.
Disambiguate FIRST before touching anything — they live in different subsystems and
the fixes don't overlap:

| Class | Path | Symptom | Reference |
|---|---|---|---|
| **A. Auxiliary `vision_analyze` routing** | `agent/auxiliary_client.py::_resolve_vision_provider` | tool returns short "I don't see an image" refusals; text-only transport strips the image | `vision-pipeline-debugging.md` |
| **B. Main-model native inline-image 413** | `gateway → agent/image_routing.py → agent/conversation_loop.py` | the **whole turn crashes** on image attach with `HTTP 413 … Cannot compress further` | THIS file |

A user reporting "you crashed when I attached an image" is almost always **Class B**,
NOT the auxiliary-tool refusal of Class A. Don't reflexively load the ACP-routing
skill — confirm the actual failure in the logs first (see Diagnostic below).

## How native image attachment actually works

When the main model reports `supports_vision=true` (e.g. `claude-opus-4.8` on the
`copilot`/`github-copilot` provider) and `agent.image_input_mode` is `auto` or
`native`, the gateway routes attached images **natively** — the model sees raw pixels,
NOT a `vision_analyze` text summary. The gateway log tell:

```
gateway.run: Image routing: native (model supports vision). 1 image(s) will be attached inline.
```

`agent/image_routing.py::build_native_content_parts` base64-encodes the image at
**native size** into an OpenAI-style `image_url` content part. By design the embed is
NOT proactively downscaled (see the module's own comment block): the system relies on
**reactive shrink-on-reject** — attach full size, and if the provider 413s/400s, shrink
and retry once.

## The bug (verified 2026-06-08, fixed in PR)

A **413 (Request Entity Too Large)** caused by an oversized inline image was
**unrecoverable** — the turn died with `413 payload too large. Cannot compress further.`

Root cause: the error classifier maps 413 → `FailoverReason.payload_too_large`, which
drives **conversation compression** (shrinking *text* history). That's correct when the
conversation is genuinely too long — but when the oversized payload is the **image**,
text compression accomplishes nothing (the image bytes are the floor). The loop burns
all `max_compression_attempts`, then returns `compression_exhausted`.

The existing image-shrink recovery (`_try_shrink_image_parts_in_messages`, already wired
into the **400 `image_too_large`** path) was NEVER reached on a 413. So:

- **Anthropic-direct** rejects an oversized image with a **400** "image exceeds 5 MB
  maximum" → hits the shrink path → recovers. ✓
- **Copilot / GitHub Copilot** has a tighter *request-body* ceiling and rejects the
  whole request with a **413** → text compression → death. ✗

This is why full-res screenshots (e.g. game screenshots) reliably killed the turn on
Copilot but not on Anthropic. The tell in `errors.log`: every 413 fires 2–3 s after an
`Image routing: native … attached inline` line.

## Diagnostic

```bash
# Is it Class B (413 on attach) or Class A (auxiliary refusal)?
grep -nE "413|payload too large|Cannot compress further" ~/.hermes/logs/errors.log | tail
grep -n "Image routing: native" ~/.hermes/logs/gateway.log | tail
# Correlate timestamps: a 413 within ~3s of a native-attach line == Class B.

# Count 413s per day — a spike on a screenshot-heavy day with no config/version
# change is the signature (the routing is old; the trigger is bigger images).
grep -E "413|payload too large" ~/.hermes/logs/errors.log | grep -oE "^[0-9]{4}-[0-9]{2}-[0-9]{2}" | sort | uniq -c
```

Also check whether the install **silently lost** the auxiliary downscale path. Older
configs sometimes ran `agent.image_input_mode: text`, which sent every image through
`vision_analyze` (which downscales) so the main model never saw raw pixels and could
never 413. A flip to `auto`/`native` (the default) hands raw pixels to a vision-capable
model and exposes the 413. Confirm against config backups:

```bash
for f in ~/.hermes/config.yaml*; do echo "== $f =="; grep -n image_input_mode "$f"; done
```

## The fix (code)

Wire the existing image-shrink recovery into the 413 path **before** falling through to
conversation compression. In `agent/conversation_loop.py`, right after
`is_payload_too_large` is computed and before the compression block:

```python
if is_payload_too_large and not _retry.payload_image_shrink_attempted:
    _retry.payload_image_shrink_attempted = True
    if agent._try_shrink_image_parts_in_messages(api_messages):
        # an oversized inline data: URL image was shrunk — retry immediately
        continue
    # else: no shrinkable image → fall through to text compression (text really
    # is the problem). Do NOT return here.
```

Add a dedicated one-shot guard to `agent/turn_retry_state.py`
(`payload_image_shrink_attempted: bool = False`) — distinct from the 400-path
`image_shrink_retry_attempted` because the two classify differently
(`payload_too_large` vs `image_too_large`) and must fire independently.

`_try_shrink_image_parts_in_messages` already returns truthy ONLY when it actually
reduced an oversized `data:` URL part, so the fall-through is precise: a 413 with no
shrinkable image still compresses text as before. No behavior change for non-image 413s.

## Gotchas that cost time here

- **The repo refactored `conversation_loop.py` ~390 commits past v0.16.0** — the retry
  flags moved into a `TurnRetryState` dataclass (`agent/turn_retry_state.py`) accessed as
  `_retry.<flag>`. A patch written against the running install's stale tree would
  reintroduce 800+ deleted lines. **Build the PR in a worktree off fresh `origin/main`,
  not off the running install's checkout.** (`git worktree add -b <branch> /tmp/<dir>
  origin/main`.)
- **There's a `TurnRetryState` field-contract test** (`tests/agent/test_turn_retry_state.py`,
  `EXPECTED_FIELDS` set) that fails the instant you add a dataclass field. Update the
  `EXPECTED_FIELDS` set in the same change.
- **Build a REAL decodable image to test the shrink helper.** A fake PNG (header bytes +
  N×`b"X"`) is not decodable, so Pillow can't re-encode it and the helper correctly
  reports "unshrinkable" → your test sees `returned=False` and reads as a fail. Use
  `os.urandom(2600*2600*3)` → `Image.frombytes("RGB", ...)` → save PNG to get genuine
  incompressible bytes >4 MB. A solid-color/gradient image PNG-compresses to almost
  nothing and won't exceed the 4 MB target either.

## User-facing workaround (no code, while the fix isn't deployed)

- **Best (keeps pixel vision):** deploy the code fix above (gateway restart reloads it).
- **Durable but lossy:** `hermes config set agent.image_input_mode text` — routes images
  through the auto-downscaling `vision_analyze` path. The main model then sees a *text
  description*, not pixels — bad for debugging visual/geometry detail in screenshots.
- **Zero-code stopgap:** shrink screenshots to ~1600px before sending.
