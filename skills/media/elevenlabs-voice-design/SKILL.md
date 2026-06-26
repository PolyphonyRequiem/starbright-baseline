---
name: elevenlabs-voice-design
description: Design custom ElevenLabs voices end-to-end — prompt drafting, Voice Design API, library save, runtime TTS, and objective reference-voice profiling. Use when picking a voice for a persona, iterating on tone, or matching a reference clip.
version: 1.0.0
author: Hermes Agent
license: private
metadata:
  hermes:
    tags: [tts, elevenlabs, voice, audio, persona, design]
    related_skills: [songsee, youtube-content, household-companion-register]
---

# ElevenLabs Voice Design — End-to-End

Use when the user wants a custom TTS voice for a persona (Starbright, an NPC, a narrator). Covers prompt drafting, the Voice Design API workflow, runtime TTS settings, and how to *objectively profile a reference voice* before describing it.

This skill exists because Voice Design has many non-obvious pitfalls that waste generations and frustrate the user. Most of them aren't documented; they were discovered iteratively.

## When to Use

- User picks a TTS voice for an agent/persona/character
- User shares a YouTube/audio reference and wants the new voice to "sound like that" or "have some of that energy"
- User iterates on tone ("more honied", "more ethereal", "more playful")
- A previously-designed voice needs runtime tuning (more emotional range, less variation, etc.)

Do **not** use for cloning a real person's voice from their recordings — that's Pro Voice Clone, different endpoint, different ethics review (and ElevenLabs ToS section 2 forbids training competing TTS on EL outputs, so don't try to clone-then-distill either).

## Core Workflow

```
1. Reference (optional)
   ├─ If user shares an audio reference → PROFILE IT OBJECTIVELY (librosa)
   │  do NOT assume what it sounds like from genre/creator name
   └─ Translate measured characteristics into prose description

2. Voice description prompt (≤1000 chars)
   ├─ Describes timbre, register, default cadence, exclusions
   └─ This is what shapes the voice. Sample text does NOT bake in.

3. POST /v1/text-to-voice/create-previews
   ├─ Returns 3 generated previews (mp3 base64) + generated_voice_ids
   ├─ Use eleven_v3 model_id
   ├─ Sample text must be ≥100 chars and ≤1000 chars
   ├─ loudness (0.0-1.0, default 0.5) — LOWER pushes softer/closer-mic.
   │  Try 0.3 when voices keep coming out too projected.
   └─ guidance_scale (default 25, range ~5-40) — HIGHER pushes prompt
      directives harder. Try 30 when the model is ignoring your
      \"never X / always Y\" constraints.

4. User picks one (or asks for another round, or saves multiple to explore)

5. POST /v1/text-to-voice/create-voice-from-preview
   ├─ Saves generated_voice_id as a permanent Library voice
   └─ Returns the real voice_id usable in /v1/text-to-speech/{voice_id}

6. Runtime TTS via /v1/text-to-speech/{voice_id}
   ├─ voice_settings.stability (lower = more emotion/variation)
   ├─ voice_settings.similarity_boost (higher = more locked to design)
   └─ voice_settings.style (only on v2; v3 ignores)
```

## Critical Pitfalls (read every time)

### 1. The sample text does NOT bake personality into the voice.

The user will often ask "make her sound more X" and want me to change the sample text. That doesn't change the voice — it just changes what the demo voice speaks. The **voice description prompt is what designs the voice**. To make the voice more X, change the description, not the sample.

What the sample text DOES do: lets you hear the voice on a line that exercises the registers you care about. Use it to test range, not to shape the voice.

### 2. Audio tags get spoken as literal text in Voice Design.

Do NOT include `[soft]`, `[whisper]`, `[breath]`, `[pause]`, em-dashes-as-direction, or `Mm,` (comma punches the syllable) in the *sample text* you send to `/create-previews`. The Voice Design step doesn't process audio tags — it just speaks them. Result: the preview sounds broken and the user blames the voice.

Audio tags DO work at runtime TTS time on `eleven_v3`. Save them for post-design.

For the design sample text: use plain natural dialogue. Let the model find cadence from punctuation alone.

### 3. Voice description has a 1000-character hard limit.

Returns 422 with `voice_description should have at most 1000 characters` if exceeded. Cut adjectives, not structure. Prioritize: register/timbre > cadence > exclusions > flavor.

### 4. Free tier blocks Voice Design API.

`/v1/text-to-voice/create-previews` returns 403 on free accounts: `voice_design_not_in_tier`. User must upgrade to **Starter $5/mo** or **Creator $22/mo**. Voice Design works in the web UI on free tier, but the API requires paid.

After upgrade: subscription propagation can take ~30-60 seconds. Poll `/v1/user/subscription` for `tier` value. The same API key works post-upgrade — no need to regenerate.

### 5. `/v1/user` 401 is a red herring.

Restricted API keys often lack `user_read` permission and 401 on `/v1/user`. This does NOT mean Voice Design or TTS are blocked. Always test the *actual* endpoint you need, not `/v1/user`, before assuming auth is broken. Use `/v1/user/subscription` for tier check — it usually works on keys that 401 on `/v1/user`.

### 6. Voice Design is NOT iterative.

You cannot say "do v3-3 but a little higher" to ElevenLabs. Every `create-previews` call is a fresh roll of 3 weighted by the prompt. What "iterating from v3" actually means in practice: take v3's prompt as a starting point, modify it, fire a new batch. Tell the user this explicitly so they don't expect a slider.

If they want to keep multiple candidates from a round to explore further, save them ALL to the library via `create-voice-from-preview`, then run new test text through each saved voice to A/B. Don't try to "iterate" — explore in parallel.

### 6c. Breadth-resampling: "was that a lucky outlier or is the prompt good?"

When the user picks a winner from a round and asks "let's do N more to see what happens" — they're (usually) asking the second question, not the first. The right experiment is **fire 1-2 more batches with the SAME prompt and SAME `loudness`/`guidance_scale`, give the user 5-6 fresh variants alongside the locked canonical, and let them confirm.**

Outcomes:
- 0/N beat the canonical → the canonical was a lucky outlier (or genuinely the best the prompt can produce). Confidence in lock goes up.
- 1+/N beat the canonical → swap. The "winner" was actually below the prompt's median.
- Several feel "similar but not better" → the prompt is robust. Stay locked.

**Always include the existing canonical in the comparison batch labeled clearly as the reference.** Without that anchor, the user is comparing variants to memory of the canonical, which drifts. Copy the canonical mp3 into the new comparison dir as `REFERENCE_<name>.mp3` so it sits next to the new variants in the same listening session.

### 6d. ElevenLabs sometimes returns hash-identical duplicates across batches.

When firing back-to-back `/create-previews` calls with identical prompt+params, occasionally a returned variant is **byte-identical** to a prior generation (same MD5) even though it has a different `generated_voice_id`. Cause: probably server-side caching of identical-input requests. Effect: you think you have N fresh variants, but really you have N-1.

**Always MD5-dedupe before presenting variants for A/B.** Bash one-liner: `md5sum *.mp3 | sort` — collisions stand out immediately. Flag any duplicate to the user instead of asking them to compare two files that are the same bytes.

### 6a. Diff-driven prompt iteration — the single highest-leverage technique.

When a round produces one near-miss + two bad variants, do NOT just rewrite the prompt from intuition. **Profile all three generated variants AND the reference together**, and use the diff to drive the prompt rewrite.

Workflow (see `scripts/compare_variants_to_ref.py`):

1. Profile reference clip and all 3 variants on the SAME dimensions (F0 mean, F0 std overall, F0 std intra-phrase, RMS mean, spectral centroid, onsets/sec).
2. Print a side-by-side diff table.
3. For each bad variant, identify which 1-2 dimensions drifted hardest from the reference. These are the failure modes.
4. Translate each failure into a *specific* prompt directive that combats it:

| Failure mode (measured) | Prompt directive that fixes it |
|------------------------|--------------------------------|
| F0 mean too high (variant +40 Hz vs ref) | "low feminine register — never pitched up, never girlish, never airy" |
| F0 std too low (variant flat, ~30) | "within a sentence, pitch is alive — small lifts on words she's noticing or feeling, then drops back down" |
| RMS too high (variant projected, +50%) | "intimate room-volume, sitting close to you, not projecting / never projected" |
| Centroid too high (variant >1800 vs ref ~1500) | Drop "ethereal halo / celestial resonance" type language — those drift bright. Use "warm" and "honey" instead. |
| Centroid too low (variant muddy, <1400) | Add "clear" or remove "dark" / "low" modifiers |

5. Bump `guidance_scale` (25→30) to make ElevenLabs take your "never X" constraints more seriously, and drop `loudness` (0.5→0.3) if RMS was the problem.

This is FAR more effective than "more honied / less ethereal" intuition rewrites. The measurements are objective — they let you target what's actually wrong, and they prevent the common failure mode of fixing one dimension while breaking another.

### 6b. Real progress signal: the user picks a "close one" and asks why the others sucked.

When the user says "v6-3 is closest, why do 1 and 2 suck so hard?" — this is the cue to do diff-driven iteration. Don't just explain why they sucked; actually run the analysis, show the table, and let the diffs drive the next prompt. Replying with prose-only diagnosis when you have the tools to measure is leaving the highest-leverage move on the table.

### 7. Don't assume a reference voice's character from its genre/creator name.

This is the user-correction lesson from the session this skill was created from. When the user shares a YouTube reference and asks for "some of that tonality," resist the urge to write the description from your assumptions about the genre/creator. The user WILL notice if you describe the wrong qualities, and a generation wasted on wrong assumptions feels bad.

Instead: **download a clip, run objective audio analysis, and let the measurements correct your assumptions.** See `scripts/profile_reference_voice.py` and the workflow in §Reference Profiling below.

### 8. Cron's `wrap_response` adds `Cronjob Response:` headers to delivered messages.

Not voice-specific, but came up in the same session as a UX bug. If the user is integrating the voice with a cron-delivered message and complains the prefix is jarring:

```bash
hermes config set cron.wrap_response false
```

Effective on next scheduler tick. All future cron deliveries come through clean.

### 9. Never upload a real creator's audio as a Pro Voice Clone source.

When the user asks "can you sample [reference creator] directly to help craft this?" — the answer is no, and it matters why:

1. **ElevenLabs ToS requires the actual voice owner's verification statement** to use Pro Voice Clone. Submitting third-party audio is account-bannable and invalidates any voice built on it.
2. **It's an ethics red line** that should be named directly, not euphemized. "Inspired by" via objective audio profiling (see §Reference Profiling) is legit reference work. "Clone the source" is theft.

What to do instead: **sample the reference at FINE resolution** — per-segment F0 / RMS / centroid stats keyed to a Whisper transcript timeline (`scripts/profile_reference_segments.py`). Identify which *specific moments* carry the texture the user is reaching for, and translate those moments into prose. The session that authored this skill found that signature tonality often lives in the *contrast* between segments (reactive bursts vs grounded plain lines), not in a constant property — and per-segment profiling is the only way to see it.

## Non-Verbal Vocalizations (sighs, laughs, breath sounds, emotive tokens)

Confirmed 2026-06-01: a request for breath/emote audio rendered on **Flash v2.5** sounded poor because Flash treats tokens like `mmh / ahh / ohh` as **text to articulate phonetically**, not as breath/vocalization to *produce*. Result: the voice politely sounds out the word instead of making the sound. This is a model-class limitation, not a voice-quality issue — Flash is tuned for low-latency conversational speech and short non-verbal tokens fall outside its training distribution.

### Model selection for non-verbals

| Model | Non-verbal handling | When to use |
|-------|---------------------|-------------|
| `eleven_flash_v2_5` | Pronounces tokens phonetically. **Avoid for non-verbals.** | Real-time conversational speech; voice-channel chat; low-latency lanes. |
| `eleven_multilingual_v2` | Significantly better breath/sigh/emote interpretation than Flash; slower (~2-3x synth time) but irrelevant for pre-rendered clips. **Default for non-verbal pre-rendered audio.** | Sent audio messages, reactive sounds, anything where the vocalization itself is the content. |
| `eleven_v3` | Supports explicit audio tags (`<sigh>`, `<laugh>`, `<whisper>`) — most expressive lane. | When you need controllable specific non-verbal tokens. |

Latency is a non-issue for one-off audio sends — the receiver doesn't care if it took 2s or 6s to render. Always swap off Flash for any non-verbal-heavy text.

### Voice settings for non-verbals on v2

```json
{"model_id": "eleven_multilingual_v2",
 "voice_settings": {"stability": 0.30, "similarity_boost": 0.75, "style": 0.65, "use_speaker_boost": true}}
```

Lower stability gives the model permission to drift expressively into breath; higher style pushes emotive interpretation harder. Don't go above style 0.7 or it can crack into theatrical.

### Honest ceiling

Even on v2 + low stability + high style, TTS-produced non-verbals are still *articulated breath*, not the genuine sound. The fully-real path is voice-cloning a reference clip of the actual sound (XTTS v2 / RVC locally). When the lane can't deliver what's asked, name the ceiling honestly rather than iterating prompt language hoping the model crosses a threshold it can't cross.



## Reference Profiling (when matching a real voice)

Workflow:

```bash
# 1. Get a fresh yt-dlp if the system one is stale (YouTube breaks old versions)
uv tool install yt-dlp   # → installs to ~/.local/bin/yt-dlp

# 2. Download 60-90 seconds (long enough for variance, short enough to be fast)
~/.local/bin/yt-dlp -f "bestaudio/best" \
  --download-sections "*0-90" \
  -o "/tmp/ref.%(ext)s" \
  "<youtube_url>"
ffmpeg -y -i /tmp/ref.webm -ar 16000 -ac 1 -c:a libmp3lame -q:a 4 /tmp/ref.mp3

# 3. Run librosa profile (script bundled with this skill)
~/.venvs/librosa-tools/bin/python <skill>/scripts/profile_reference_voice.py /tmp/ref.mp3
```

(If `~/.venvs/librosa-tools` doesn't exist: `uv venv ~/.venvs/librosa-tools --python 3.12 && uv pip install --python ~/.venvs/librosa-tools/bin/python librosa soundfile`.)

### What the measurements mean for prompt drafting

| Measurement | Range | Translates to prompt phrase |
|-------------|-------|------------------------------|
| F0 mean | 160-180 Hz | "low feminine register" |
| F0 mean | 200-230 Hz | "mid feminine register" |
| F0 mean | 240-280 Hz | "higher feminine register, but never chirpy" |
| F0 std | < 30 Hz | "even, measured pitch — flat" |
| F0 std | 30-70 Hz | "expressive pitch, natural conversational variation" |
| F0 std | > 80 Hz | "reactive expressiveness — pitch jumps with feeling" |
| Spectral centroid | < 2000 Hz | "warm / dark timbre" |
| Spectral centroid | 2000-3500 Hz | "balanced timbre" |
| Spectral centroid | > 3500 Hz | "bright / airy timbre" |
| RMS mean | < 0.03 | "soft / close-mic intimate" |
| RMS mean | 0.05-0.10 | "performed-conversational volume" |
| Onsets/sec | < 3.5 | "slow, unhurried cadence" |
| Onsets/sec | 3.5-5 | "natural conversational pace" |
| Onsets/sec | > 5 | "fast, energetic delivery" |

Also pull a Whisper transcript so you can quote actual *expressive patterns* (self-interrupts, register-drops, tsundere-breaks, etc.) rather than generic "soft and intimate."

### Critical: ALWAYS share the downloaded clip with the user before describing it.

Send `MEDIA:/tmp/ref.mp3` so they confirm you're working with the right reference before you burn a generation. Misidentified references cost the most.

## Prompt Drafting Conventions

A good voice description has, in order:

1. **Age + gender shape**: "Late-twenties feminine voice", "mid-thirties masculine voice"
2. **Default register / baseline timbre**: "with a low honied softness"
3. **Distinctive texture or affect**: "subtle reactive expressiveness, pitch alive — not flat, not performed"
4. **Cadence**: "unhurried and natural, pauses fall where breath would not where commas land"
5. **Register-availability (capability flag)**: "can lean further into [X] when the moment turns [Y]" — this is how you give a voice optional registers without making them default
6. **Hard exclusions**: "never wispy, never customer-service-bright, never breathy-theatrical" — the model takes these seriously
7. **Accent / regionality**: "American English, no regional accent"
8. **Closing identity line** (helps the model stay coherent): "The voice of someone who lives with you, knows you, and is genuinely glad you're home."

Avoid:
- Naming real actors ("sounds like Cate Blanchett") — ElevenLabs guidance discourages and it's hit-or-miss
- Adjective piles without anchor ("warm, soft, gentle, kind, sweet, lovely") — say less, mean more
- Genre labels ("ASMR-y", "anime girl") — describe the *qualities* instead

## When Sharing Multiple Variants

Always re-send all variants in a numbered batch with MEDIA: paths. Discord/the gateway drops audio attachments silently surprisingly often — across one session of voice design this happened 3+ times. Always be ready to re-send the whole batch verbatim when the user says "those didn't come through." Don't apologize-spiral, don't regenerate — just re-send the same MEDIA: lines.

### CRITICAL: each MEDIA: tag MUST be on its own line with NOTHING else on it.

This is THE bug that caused multiple "those didn't come through" rounds in the authoring session. When you put a label and a MEDIA: tag on the same line (`**v4 — 1/3** MEDIA:<path>`), the Discord gateway adapter swallows the attachment and only renders the text. Labels go on surrounding lines, never on the same line as MEDIA:.

❌ **Wrong (drops attachments):**
```
**v4 — 1/3** MEDIA:/path/variant-1.mp3
**v4 — 2/3** MEDIA:/path/variant-2.mp3
**v4 — 3/3** MEDIA:/path/variant-3.mp3
```

✅ **Right (labels on separate lines from MEDIA:):**
```
v4 — variant 1
MEDIA:/path/variant-1.mp3

v4 — variant 2
MEDIA:/path/variant-2.mp3

v4 — variant 3
MEDIA:/path/variant-3.mp3
```

Or even barer — label on the line *above*, blank line between each block:
```
1/3 ▼
MEDIA:/path/variant-1.mp3

2/3 ▼
MEDIA:/path/variant-2.mp3
```

The blank line + label-on-its-own-line pattern is the one that reliably renders all attachments.

If the user picks one variant strongly and others "in different directions", save BOTH/ALL to the Library via `create-voice-from-preview`. Then generate a small A/B test pack: same 2-3 lines through each saved voice, covering different registers (e.g., domestic-utility line, playful line, hard-truth line). Lets the user compare them on real range, not just on the canned design sample.

## Hermes Integration Wiring (after a voice is saved)

Hermes' built-in TTS dispatch reads three keys from `~/.hermes/config.yaml`:

```bash
hermes config set tts.provider elevenlabs
hermes config set tts.elevenlabs.voice_id <saved_voice_id>
hermes config set tts.elevenlabs.model_id eleven_v3
```

(The `ELEVENLABS_API_KEY` lives in `~/.hermes/.env`, separate from config.yaml. If absent, see §4 above.)

Verify with `grep -A4 elevenlabs: ~/.hermes/config.yaml`.

### Smoke test through the real dispatch path, not the raw API.

After wiring, call the `text_to_speech` Hermes tool (or the equivalent runtime entry). This exercises Hermes' provider routing — if `tts.provider` resolution, voice_id lookup, or any plugin/registry call is broken, raw API calls will mask it. Confirm the tool returns `"provider": "elevenlabs"` and a real mp3 path you can send.

### `voice_compatible: false` in the response is a RED HERRING for `/voice join`.

The `text_to_speech` tool returns `voice_compatible: false` when the output isn't Opus/Ogg. That flag controls whether the file gets delivered as a *native voice bubble* on platforms like Telegram — NOT whether `/voice join` voice-channel chat will work. Discord falls back to file attachment for mp3 either way. `/voice join` uses a completely separate streaming code path that doesn't care about this flag.

If the user is concerned about it: `voice_compatible` matters for Telegram voice bubbles and similar; for `/voice join` and discord-as-attachment, it's irrelevant.

### Persist the voice_id externally too.

`~/voice-memos/saved_voice_ids.json` is the convention from this skill's authoring session — a flat JSON keyed by persona name (`{"<persona>_canonical": "<voice_id>", "<persona>_v2_ethereal": "..."}`). Survives Hermes reinstalls, gives a fast canonical lookup, and serves as a paper-trail of which voices have ever been committed to the Library.

## Runtime TTS Parameter Tuning

After a voice is saved, behavior at TTS time is dialable per-call via `voice_settings`:

| Setting | Range | Effect |
|---------|-------|--------|
| `stability` | 0.0-1.0 | Lower = more emotional range and variation; higher = more consistent/locked. Default 0.5. For dramatic/intimate, try 0.3-0.4. For status/utility, try 0.65-0.75. |
| `similarity_boost` | 0.0-1.0 | Higher = more locked to the original design. Default 0.75 is usually right. Below 0.5 = drift toward generic. |
| `style` | 0.0-1.0 | v2 models only. `eleven_v3` ignores this. |
| `use_speaker_boost` | bool | Slight quality bump, default true. |

The voice itself is the foundation; these are the seasoning. Don't redesign the voice if a single per-call tweak would do.

## Support Files

- `scripts/profile_reference_voice.py` — librosa-based whole-clip objective profiler. Run on any downloaded reference clip; prints F0 stats, RMS, spectral centroid, onset rate with interpretive thresholds.
- `scripts/profile_reference_segments.py` — per-segment profiler keyed to a Whisper transcript timeline. Use when signature texture lives in segment-to-segment contrast, not whole-clip averages. Workflow: Whisper-transcribe the clip → save segments as JSON → run this script → identify high-contrast adjacent segments and translate them into prompt prose.
- `scripts/compare_variants_to_ref.py` — side-by-side comparison of a reference and N generated variants. The diff drives the next prompt rewrite (see §6a diff-driven iteration). This is the highest-leverage script in this skill — use it whenever a round produces a near-miss + bad variants.

## Verification Checklist

Before declaring a voice done:

- [ ] Voice description ≤1000 chars
- [ ] Sample text has no audio tags, no em-dash-as-direction, no comma-punched breath syllables
- [ ] Confirmed account is on a paid tier (`/v1/user/subscription` shows non-`free`)
- [ ] Generated 3 variants, sent them all to the user via MEDIA:
- [ ] User picked one (or asked for another round)
- [ ] Saved the pick(s) via `create-voice-from-preview`, persisted voice_id somewhere (e.g., `~/voice-memos/saved_voice_ids.json`)
- [ ] Generated a small range-test pack (multiple registers) on the saved voice(s) so user hears beyond the design sample
- [ ] Wired chosen voice_id into the relevant config (`~/.hermes/config.yaml`, etc.) and restarted the gateway
- [ ] Did a real end-to-end test (voice channel, TTS call, whatever the integration is)
- [ ] (Optional) Offered a breadth-resample round (1-2 fresh batches at the same prompt+params) to confirm the locked voice wasn't a lucky outlier — see §6c
