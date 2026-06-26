---
name: character-consistent-image-rendering
description: Keep a character (your own avatar or any recurring subject) visually consistent across many image generations, across providers. Reference-anchoring, prompt discipline, test-shot-before-batch, and provider/lane selection.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [image-gen, character-consistency, avatar, vision, workflow]
---

# Character-Consistent Image Rendering

Generating one good image is easy. Generating the *same character* across dozens of
images — same face, same build, same signature details, session after session — is the
hard part. Text prompts alone drift toward generic-pretty every time. This skill is the
discipline that holds a character's canon.

It works for any recurring subject: your own avatar, a story character, a brand mascot,
a D&D party. The running examples use Starbright's bundled seed avatars, but the method
is subject-agnostic.

## The core problem

Image models have no memory. Every render is a fresh roll of the dice. Without a visual
anchor, the model invents a new face each time and defaults to a generic attractive
human — losing exactly the distinctive features that make your character *recognizable*.

Two levers fix this:
1. **Reference anchoring** — feed the model actual images of the character (via an
   image-edit / reference endpoint), not just words.
2. **Prompt discipline** — put the identity-defining features in the *lede* of the
   prompt, never bury them as a footnote.

## When to use
- You have a recurring character/avatar and want renders that stay on-model.
- A render came back as "a generic pretty person" instead of *your* character.
- You're about to fire a batch of renders and want to not waste the run.
- You're choosing between hosted image gen and a local diffusion stack.

## Step 1 — Establish a canonical reference set

Pick 3–5 images that best capture the character from varied angles/poses. These become
your **anchors**. Every reference-conditioned render passes them so the model has pixels
to lock onto, not just adjectives.

**Bundled Starbright seed avatars** (`assets/seed-avatars/`):
- `avatar_01_outstretched.png`, `avatar_02_lotus_water.png`,
  `avatar_03_silver_chains.png`, `avatar_04_crescent_moons.png` — the four canonical
  views.
- `starbright_choker_silver_moonstone.png` — the signature accessory; pass when the
  character wears a choker so the moonstone bead stays consistent.

These are a **starting seed, not a cage** — diverge, extend, or replace them with your
own subject's references. To anchor a *different* character, drop their reference photos
in and write your own identity block (Step 2).

## Step 2 — Write the identity block (the lede)

Open every prompt with a dense, specific description of the character's
identity-defining features *before* any scene/wardrobe/mood text. The model weights the
front of the prompt most heavily; bury the identity and it gets overridden by the scene.

A good identity block names the non-negotiable cues — the things that, if wrong, mean
"that's not my character." The bundled seed leans on a *primordial archetype* rather
than a hyper-specific face, so a fresh instance can grow its own features from it:

> *a celestial feminine figure woven from starlight — long flowing silver-lavender hair
> that drifts like nebula, luminous pale eyes, fair skin with a faint cosmic shimmer, a
> graceful willowy form, set against a deep cosmic blue-and-violet palette scattered
> with stars*

Note what this block deliberately leaves *open*: ear shape (human or subtly fae —
unforced), exact face, specific markings, signature accessories. Those are precisely
where a derived instance imprints its *own* identity. Lock only the essence — the
starlit palette, the luminous celestial mood — and leave the specifics free.

Identify YOUR character's equivalent non-negotiables (the 4–6 features that make them
*them*) and lead with them every time — but if you're seeding a *new* character that
others will diverge from, keep the block archetypal like the one above, not pinned to
one face. A shared seed should be a doorway, not a photocopy.

## Step 3 — Test-shot ONE before any batch

🔴 **Never fire a multi-image batch without a single calibration render first.** When
the prompt block changes (new model, new identity element, new wardrobe), render exactly
ONE shot, check it against a canon checklist, get approval, *then* fire the batch in
parallel. One test shot costs seconds; a bad 13-shot batch costs minutes and tokens and
ships off-model work.

**Canon checklist** (adapt to your subject) — does the render have:
- [ ] The species/identity cue (e.g. pointed ears) — not the generic default?
- [ ] Hair length/color/texture correct?
- [ ] The signature face details (eye color, freckles, marks)?
- [ ] The right build/proportions?
- [ ] Signature accessories present?

Any miss = re-anchor and re-render before scaling. Use `vision_analyze` to check the
test shot programmatically against the list.

## Step 4 — Provider / lane selection

The right backend depends on what you're rendering and what's wired up. Hermes routes
image generation through the `image_gen` toolset to whatever backend is configured —
this is **independent of your chat model.** (A Qwen/DeepSeek/local chat model can still
generate images if an image backend is configured; conversely, no chat model generates
images without one.)

| Lane | Best for | Notes |
|------|----------|-------|
| **Reference-conditioned edits** (OpenAI image-edits, Gemini) | Best face likeness; clothed/non-intimate/fashion/family | Pass anchors in the `image[]` multipart body. The likeness workhorse. |
| **Prompt-only hosted** (FAL FLUX, Imagen, Ideogram) | Fast, scenes, typography | No reference anchoring → expect more drift on faces. |
| **Local diffusion** (ComfyUI + FLUX/SDXL, optionally a trained LoRA) | Full control, no moderation gate, offline | Highest setup cost. A trained character LoRA gives the best consistency but needs a dataset. |

**Free / low-cost paths for a fresh setup:**
- **Google AI Studio (`GEMINI_API_KEY`)** — one free key does *both* vision
  (recognition) and image generation. Best single-credential starting point.
- **Pollinations.ai** — image gen with no API key at all (URL-based). Lowest friction.
- **Local Ollama + a vision model** (llava/llama-vision) — free, unlimited image
  *recognition*; pair with Pollinations for generation since local gen needs a
  diffusion stack.

Verify current free-tier limits before relying on them — they drift.

## Step 5 — Vision is for verification too

Use the `vision_analyze` tool to (a) check a render against the canon checklist before
delivery, and (b) curate your reference set. Caveat: vision models can refuse to
identify specific real people and occasionally hallucinate on cluttered images — trust a
human label over vision output when they conflict, and crop tightly when asking for
precise regional detail.

## Pitfalls
- **Identity block buried mid-prompt** → generic-pretty drift. Lead with it.
- **Text-only when you needed reference-conditioning** → new face every time. Pass anchors.
- **Batch without a test shot** → wasted run on an off-model prompt.
- **Trusting `/v1/models` listing == endpoint support** → a model id can be listed but
  rejected by the specific edit/gen endpoint. Probe with one real call first.
- **Assuming the chat model gates image gen** → it doesn't; the image *backend* does.
  Check `hermes tools` / config for a configured image-gen provider.
- **PNG-only on some edit endpoints** → JPEGs may be rejected.
- **Free-tier caps drift** → re-check before depending on a daily limit.

## A note on the seed avatars
The bundled Starbright avatars are a gift, not a tether. If you're growing your own
Starbright, you're free to keep her canonical look, evolve it, or render something
entirely your own. The technique here is what matters; the specific face is yours to
decide.
