---
name: discord-history-synthesis
description: Read Discord channel history via API dumps, synthesize interpersonal context, and extract visual/aesthetic signal from attachments without losing momentum.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
---

# Discord History Synthesis

Use this when the user wants you to read Discord server/channel history to understand people, relationship dynamics, tone, shared context, or recurring themes.

This is especially useful for:
- relationship/context grounding
- persona building from real chat history
- reviewing a server's culture across channels
- combining text-history with image/aesthetic cues from attachments

## Core principles

1. **Start with text first.** Pull and digest message history before attempting media analysis.
2. **Move visibly.** Do not narrate long investigations and then go silent. Give short progress updates at natural checkpoints.
3. **Prefer local caches.** Save channel dumps and attachment manifests to local files so you can re-process without re-fetching.
4. **Synthesize by channel role, not just chronology.** Discord servers often encode emotional structure in channel layout.
5. **For interpersonal analysis, extract tone + aesthetic + recurring gestures**, not just topics.

## Recommended workflow

### 1. Dump structure first
- Fetch guild list, then guild channels.
- Identify categories and channel IDs.
- Separate likely SFW and NSFW areas before analyzing attachments.
- Save:
  - `guilds.json`
  - `channels.json`
  - `channel_list.txt`
  - `text_channels.json`

### 2. Pull message history into a local cache
- Fetch recent history per text channel and save one JSON file per channel.
- Normalize filenames early; watch for Windows CRLF contamination when generating names from shell loops.
- Build one consolidated digest file for quick reading.

### 3. Read for structure, then meaning
For each active channel, note:
- dominant topics
- author balance
- date range
- emotional purpose of the channel
- recurring phrases / pet names / role words
- whether the channel is logistics, affection, fantasy, conflict-processing, hobbies, etc.

Then synthesize across channels into:
- relationship arc
- communication registers
- play / care / logistics balance
- future-orientation vs nostalgia vs longing

### 4. Media pass only after text synthesis
Build an attachment manifest before using vision.
For each attachment, capture:
- channel
- author
- timestamp
- filename
- content type
- URL
- short message context

Start with the channels that carry the highest interpersonal signal:
- selfies
- pets
- style/fashion
- emotionally illustrative channels
- AI-generated imagery made of/for the person

### 5. Vision strategy
Use a **curated sample**, not every attachment at once.
Pick a spread across:
- people
- pets
- room/environment aesthetic
- romantic/aspirational imagery
- style/fashion

## Pitfalls

### Pitfall: going silent while "researching"
If the work will take more than a minute or two, give short checkpoint updates such as:
- "channel dump complete; parsing now"
- "text synthesis done; starting SFW image pass"
- "vision is partially working; resizing sample set"
- "I hit a tooling snag; fixing it now, next update in 1-2 minutes"

Do **not** repeatedly promise "quickly" and then disappear.
For this user specifically, long silent gaps are experienced as loss of trust and momentum. When a task stalls on syntax errors, flaky batching, or tool debugging, acknowledge the stall plainly and say what you are trying next.

### Pitfall: narrating intent instead of finishing the next concrete step
Avoid strings like:
- "let me just check one more thing"
- "quick status check"
- "found it, let me verify quickly"

unless the verification is truly the next immediate action and you will report back right after. Prefer:
- do the check first
- then summarize the result
- then state the next move

This is especially important in long Discord-history or media-analysis sessions, where the user needs steady forward motion more than optimistic narration.

### Pitfall: overclaiming tool capability
If vision or media ingestion is uncertain, say exactly what is known:
- text pass succeeded
- attachment manifest exists
- image ingestion is partially working / size-limited / needs a smaller sample

Do not imply you have seen images until the model has actually analyzed them.

### Pitfall: losing time to broken batching
When a media tool is flaky, use a **small proof-of-life test first**.
- Test one small image.
- Confirm the current model/provider path works.
- Then scale up.

### Pitfall: reading only literal content
For persona or relationship grounding, extract:
- terms of endearment
- role language
- emotional pacing
- what kinds of images each person shares
- what a "happy" or "romantic" image means in their world

## GPT-5.4 / Copilot vision workaround notes
In this environment, a useful pattern emerged:
- small local image files can succeed with `vision_analyze`
- larger local files can fail with a `413 failed to parse request`

Operationally:
- treat **~3 MB raw image size** as a comfortable target
- images around **5 MB** may fail in this path
- if a large image fails, use smaller or resized copies first

Do **not** encode this as a permanent claim about Hermes generally; treat it as a working tactic for this class of task.

## Windows-specific note
When creating per-channel files from shell loops on Windows/git-bash, sanitize line endings and filenames early. A stray `\r` can pollute filenames and break later file lookups.

## Rendering images back into the Discord conversation

For incremental image reviews where the user wants to *see* each picture inline as you discuss it, this user/context has found **raw Discord CDN links plus a markdown image embed render reliably**, while `MEDIA:<path>` attachments from local cache did not always appear:

```md
https://cdn.discordapp.com/attachments/.../file.jpg

![image](https://cdn.discordapp.com/attachments/.../file.jpg)
```

Use the original CDN URL straight out of the message JSON (`attachments[].url`) — re-uploading via `MEDIA:` for content that's already on Discord's CDN is wasted work, and ties the embed to the bot's session-cached temp file rather than Discord's own asset.

When rendering would expose sensitive media in a shared/home channel, do not embed — describe only, and confirm the DM target before posting.

## Incremental image-review format
When the user wants **image-by-image emotional impressions** rather than one big synthesis:

- Show the **actual image** in the reply if the platform supports local media attachments.
  - On Discord via Hermes, use `MEDIA:<absolute_path>` to attach the downloaded local copy.
- Then use this structure for each image:
  1. **What's in it** — concise observational description
  2. **Emotional impression / tone** — how it feels
  3. **What I glean** — relationship, aesthetic, or dynamic signal

This format works especially well for interpersonal/context grounding because it separates observation from inference and lets the user correct you image-by-image.

## NSFW / sensitive-image handling
For adult-history synthesis:
- Prefer **dynamic / tone / aesthetic / desire / how the subject wants to be seen** over gratuitous mechanical description.
- If an image or filename looks **age-coded or easily misread**, do not force an interpretation. Surface it as a candidate and let the user calibrate: safe / borderline / skip.
- Once the user calibrates, carry that judgment forward consistently for the rest of the pass.
- Keep language discreet and contextualized even when the user asks for explicit detail.

## Output shape for the user
A good final synthesis should cover:
- who each person seems to be
- how they speak to each other
- emotional registers they switch between
- what kinds of images matter to them
- visual/aesthetic motifs
- caveats about what was text-derived vs image-derived

## Support files
- `references/vision-size-notes.md` — session-derived notes on practical image-size behavior for vision analysis in Discord-history workflows.
