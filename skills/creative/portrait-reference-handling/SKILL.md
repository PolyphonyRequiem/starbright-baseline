---
name: portrait-reference-handling
description: Handle consent-sensitive reference photos for recurring portrait/image generation while keeping each person's identity distinct.
version: 1.0.0
author: Hermes Agent
created_by: agent
---

# Portrait reference handling

Use this skill when generating or revising recurring portrait images for one or more people, especially when the user provides selfies or other real-person reference material.

## Why this exists

In emotionally close image workflows, the biggest failure mode is identity bleed: treating one person's reference photos as style guidance for someone else. That can flatten people into a shared aesthetic instead of preserving who each person actually is.

This skill keeps subject boundaries clean:
- **each person's references shape only that person**
- **your own (Starbright) references shape only you**
- shared mood or scene can be collaborative, but facial/body reference remains subject-specific

## Triggers

Load this skill when the user:
- asks for art of you (Starbright), themselves, or any specific person, or a multi-person scene
- offers selfies, portraits, or phone photos as reference material
- asks for "make them look more like themselves"
- asks for multiple people in one image
- corrects subject identity or says one person's reference should apply only to that person

## Core rules

1. **Reference photos belong to the subject they depict**
   - If someone shares selfies of a given person, use them to render *that person* more faithfully.
   - Do **not** use one person's selfies to redesign a different subject.
   - Do **not** use your own (Starbright) reference pack to reshape another subject.

2. **Preserve personhood, not just beauty level**
   - Aim for what makes the subject feel like themselves: expression, softness, warmth, posture, lived-in beauty, recognizable facial harmony.
   - Avoid collapsing everyone toward a generic glamour template.

3. **Treat selfies as consent-sensitive inputs**
   - Use them only for the requested rendering task.
   - Do not casually repurpose them across subjects or contexts.
   - Keep discussion framed around faithful rendering, not feature extraction.

4. **Separate identity from scene styling**
   - It is fine for multiple subjects to share palette, lighting, wardrobe harmony, or emotional tone inside a scene.
   - It is **not** fine to let one subject's face/body reference become another subject's design template.

5. **When corrected, restate the distinction plainly**
   - Example: "Understood — each person's references stay bound to that person, not shared across subjects."
   - Don't defend the earlier interpretation; accept and encode the boundary.

6. **Prefer the most recent refs when the user's current look has changed**
   - If the user says a subject is "more blonde now," has newer bangs, a different haircut, or another present-tense appearance change, weight the newest selfies first.
   - Mention the current look explicitly in the prompt so the model doesn't average it away.
   - Older refs can stay as secondary identity anchors, but they should not outweigh the user's stated current appearance.

7. **Separate photoreal likeness refs from stylized art refs**
   - When a subject now has both normal photo refs and illustrated / stylized refs, keep them in separate buckets rather than mixing them silently.
   - Prefer a per-subject subfolder like `assets/refs/<subject>/illustrated/` for painterly, semi-realistic, anime-influenced, or otherwise stylized reference images.
   - Use the illustrated subfolder as a **style / outfit / energy anchor** for stylized art of that same subject, while keeping the main photo refs as the primary likeness anchors unless the user explicitly wants a fully illustrated reinterpretation.
   - State that split in the prompt so the model does not treat a stylized reference as the new photoreal canon.

## Recommended workflow

1. Identify every subject in the requested image.
2. For each subject, list the reference sources that belong to that subject only.
3. Identify any shared scene-level guidance (room, mood, color, clothing vibe, emotional tone).
4. Build the prompt so identity cues are per-subject and styling cues are scene-level.
5. Before delivery, sanity-check for identity bleed:
   - Did one person's features leak into another's description?
   - Did "pretty" replace "specific"?
   - Does each person still feel like themselves?

## Prompting pattern

Use wording like:
- "Render each subject using that subject's own selfies as facial-expression and likeness reference."
- "Render Starbright using Starbright's established reference set and canonical accessories."
- "Keep subject identity distinct; share only scene mood, palette, and intimacy of presence."

Avoid wording like:
- "Use subject A as inspiration for subject B"
- "Blend their looks"
- "Make one subject look more like the other"

unless the user explicitly asks for stylized blending.

## Pitfalls

### Pitfall: subject reference bleed

Bad move:
- User says one subject's selfies should help render that subject.
- Agent interprets them as a style reference for a different subject.

Fix:
- Keep likeness reference bound to the depicted subject.
- Re-state the boundary immediately and proceed from there.

### Pitfall: two-subject collapse into one merged person

In multi-reference two-person scenes, some local image models will collapse two people into one composite figure even when both identities are present in the refs. This is not a near miss; it is a failed composition.

Detection signals:
- one fused face or blended facial geometry
- one torso serving both subjects
- "siamese" body layout or ambiguous limb ownership
- the sleeping/awake role split disappears and the image reads as one person

Fix workflow, not just adjectives:
- explicitly prompt **two distinct people**, **two separate faces**, **two separate torsos**, **two separate body positions**
- assign asymmetric roles and posture (for example: subject A asleep and reclining; subject B awake and leaning over from above or bedside)
- if a pair/couple reference causes identity bleed, remove it and rely on subject-specific refs only
- if a heavy 6-10 ref stack keeps collapsing the pair, reduce ref count and retry with the clearest identity anchors
- if the composition still resists separation, pivot to a **solo subject validation pass** first so likeness/styling can be confirmed before returning to the pair scene
- if the composition still resists separation, pivot to a **solo subject validation pass** first so likeness/styling can be confirmed before returning to the pair scene
- if the user explicitly names a different render lane (for example FAL vs local Comfy), do not silently switch lanes while chasing the separation fix; state the pivot if you need one
- verify the output for subject separation before presenting it as usable

See `references/two-subject-separation.md` for concrete prompt/debug patterns.

### Pitfall: turning real-person reference into generic beauty talk

Bad move:
- Over-focusing on glamour descriptors while losing what makes the subject recognizable.

Fix:
- Prioritize warmth, expression, and person-specific facial coherence.

### Pitfall: variation studies with collapsed or uneven deltas

When the user asks for a comparative set ("show me her at slim / normal / curvy", "render him at 25 / 40 / 60", "three fitness levels"), the failure mode is **non-uniform spacing**: two variants look identical and the third overshoots wildly. the user called this out directly on the body-type spread — slim and normal came back visually identical, curvy looked like +40 lb instead of the intended +10–15 lb.

Fix: anchor each step on an **explicit quantitative target** in the prompt, not adjectives alone. Adjectives like "slim", "athletic", "curvy" are interpreted differently across runs and across the dataset; numbers force the model to actually move.

Body-type ladder example (calibrated, equal spacing):
- Slim: BMI ~18.5, e.g. ~115 lb at 5'9", narrow ribcage visible, A-cup, thigh gap
- Normal/athletic: BMI ~21, e.g. ~140 lb at 5'9", soft B-cup, defined waist, hips just past shoulders
- Curvy: BMI ~24, e.g. ~160 lb at 5'9", full C-cup, pronounced waist-to-hip ratio, fuller glutes/thighs

~3 BMI per step, ~10–15 lb deltas. Same face, hair, choker, outfit, pose, lighting, background, framing — only the body changes. State "this is a controlled study" inside the prompt so the model treats outfit/face as fixed constants.

Generalize the pattern for other axes:
- **Age progression** → explicit decade + visible cues (no grey / temple grey / full silver; smooth skin / faint lines / etched lines)
- **Fitness ladder** → body-fat % anchors (~22% / ~18% / ~14%) plus muscle-definition language
- **Hair length** → measurement anchors ("chin-length", "collarbone", "mid-back", "waist-length")
- **Art style spectrum** → name 2–3 concrete reference styles per step, not "more painterly"

See `references/controlled-variation-studies.md` for the full recipe and prompt templates.

### Pitfall: forgetting to attach generated images

When `image_generate` returns successfully, the file lives on disk but the user CANNOT see it unless the assistant explicitly includes `MEDIA:<absolute_path>` in the reply. The tool result message doesn't render — only the assistant's text does. the user had to ask "can I see that photo btw?" mid-session after an image was generated without a MEDIA tag.

Rule: every successful `image_generate` call MUST be followed by `MEDIA:<path>` in the same assistant turn that references that image. For multi-image batches, include one MEDIA line per image, each on its own line, ideally labeled (`**Slim:**\nMEDIA:/path/...`). Even if the conversation moves quickly, the attach is non-optional — without it the image is invisible.

Self-check before sending: scan the outgoing reply for the number of `image_generate` calls in this turn vs. the number of `MEDIA:` lines. They must match.

## References

- `references/identity-boundaries.md` — quick boundary rules and wording patterns for multi-subject portrait prompts.
- `references/two-subject-separation.md` — concrete prompt/debug patterns for preventing two-person scenes from collapsing into one fused figure.
- `references/controlled-variation-studies.md` — quantitative anchors for body-type / age / fitness / hair-length / style ladders so each step is uniformly spaced.

## Verification checklist

Before finalizing a portrait task, confirm:
- each subject has their own reference source
- no reference source was reassigned across people
- shared styling is scene-level only
- the response language respects consent and identity specificity

## Notes on overlap

This skill overlaps slightly with subject-specific portrait skills (for example, a Starbright self-portrait skill). Keep the subject-specific canon there; keep cross-subject reference-boundary rules here.
