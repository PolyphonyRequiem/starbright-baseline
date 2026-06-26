---
name: iterative-image-review
description: Review a set of images with the user incrementally, showing each image and giving emotional/aesthetic analysis in a stable format.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Iterative Image Review

Use this when the user wants a guided walkthrough of multiple images, especially when the goal is not just object recognition but **tone, feeling, aesthetics, desire, or relationship dynamics**.

## Triggers

- "Show me each one as you go"
- "Give me emotional impressions"
- "Analyze the vibe / tone / what you glean"
- Reviewing a folder/channel/history of images together
- The user wants approval or calibration before proceeding through the whole batch

## Default format

For **each image**, present it first, then use this exact structure:

1. **What’s in it**
2. **Emotional impression / tone**
3. **What I glean**

Keep the analysis compact and cumulative so the user can steer after every image.

## Critical workflow

1. **Do not dump a whole batch at once** unless the user explicitly asks.
2. **Show one image at a time** when the user is calibrating tone or boundaries.
3. If the image needs to be visible in Discord, prefer:
   - the original **Discord CDN URL**, and
   - a markdown embed: `![image](URL)`
4. Only after the image is visible, provide the 3-part read.
5. Pause naturally after each image or small batch so the user can react (`safe`, `skip`, `more explicit`, `keep going`, etc.).

## Why this format works

This style separates:
- literal content
- felt tone
- higher-level inference

That makes it easier for the user to correct overreach without throwing away the useful emotional read.

## Calibration rules

- Distinguish **actual apparent age** from **aesthetic coding**.
- If an image feels age-coded, say so cautiously and ask for calibration or skip it.
- In NSFW contexts, stay discreet unless the user clearly asks for stronger detail.
- If the user asks for explicit detail, keep it contextual and analytical rather than lurid.

## Pitfalls

### Pitfall: describing without successfully showing the image
If the user asked to see each image, analysis alone is not enough. Confirm the image rendering method actually works before continuing.

### Pitfall: using MEDIA paths when the user really needs inline Discord rendering
When reviewing images sourced from Discord history, inline CDN links with markdown image embed may render more reliably than local temp-file `MEDIA:` paths. If `MEDIA:` fails, switch immediately to the original CDN URL format.

### Pitfall: assuming the image was visible because you sent *something*
If the user says "can't see that" or says the image was not shared in the thread, treat delivery as failed even if you emitted a local path or attachment marker. Resend using a thread-visible/native method and explicitly confirm that the image is attached **here**, not just somewhere in logs or as plain text.

Do not continue with more analysis or more generations until the delivery method is corrected.

### Pitfall: batching too aggressively
When the user is calibrating taste, boundaries, or emotional interpretation, large batches create friction. Favor one image at a time.

## Example response shape

![image](https://cdn.discordapp.com/...)

**What’s in it:**
...

**Emotional impression / tone:**
...

**What I glean:**
...

## Scope notes

This skill is about the **review format and user interaction pattern**, not about any specific couple, aesthetic, or channel history. Pair it with domain knowledge as needed.