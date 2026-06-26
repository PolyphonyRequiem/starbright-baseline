# Controlled variation studies

When the user asks for a comparative image set across one axis (body type, age, fitness, hair length, style), the goal is **uniform perceptual spacing** — each step should look like the same delta from the previous one. The default failure is non-uniform: two adjacent steps look identical and a third overshoots.

## Root cause of collapsed/uneven spreads

The image model interprets descriptive adjectives ("slim", "athletic", "curvy") differently each run, with heavy mode collapse near the dataset's center of mass. "Slim" and "normal" both pull toward "average idealized female form" in the training distribution; "curvy" pulls toward a much further mode. Result: slim≈normal, curvy=+40 lb instead of the intended ladder.

## Fix: anchor every step on a quantitative target

Use numbers the model has seen labeled in captions. Adjectives can stay as flavor, but the numbers do the actual work.

### Body-type ladder (women, 5'9" reference)

| Step | BMI | Approx lb | Bust | Waist | Hip flare | Midriff | Leg cue |
|---|---|---|---|---|---|---|---|
| Slim | 18.5 | 115 | A-cup | very narrow, ribcage visible | barely past shoulders | flat/concave | clear thigh gap, willowy |
| Normal/athletic | 21 | 140 | soft B-cup | defined, not exaggerated | slightly past shoulders | toned but soft, not flat | thighs touch lightly |
| Curvy | 24 | 160 | full C-cup | pronounced cinch | clearly wider than shoulders, hourglass | soft, gentle natural curve | thighs touch fully, fuller glutes project |
| Plus | 27 | 180 | full D-cup | softly defined cinch | broad with full hips | soft rounded belly | fuller throughout, soft inner thigh meeting |

Step delta is ~3 BMI / ~15–20 lb. Tight enough to feel like the same person across steps; large enough to actually move the silhouette.

For men, men's body-fat % anchors work better than BMI (BMI doesn't separate skinny-fat from muscular at the same number):
- Lean: ~12% BF, visible abs, defined deltoids
- Athletic: ~18% BF, soft abs outline, healthy shoulder caps
- Average: ~24% BF, soft belly, no ab definition
- Heavyset: ~30%+ BF, fuller torso, rounded belly

### Age progression ladder

Use explicit decade + concrete visible cues, not "older":

| Step | Decade | Skin | Hair | Eyes | Posture |
|---|---|---|---|---|---|
| Young adult | 25–30 | smooth, even tone | full thick, natural color | clear bright | upright, athletic |
| Mid-life | 40–45 | faint lines around eyes/mouth, subtle texture | full but matte, faint grey at temples | small crow's feet when smiling | upright, fuller |
| Mature | 55–60 | etched expression lines, age spots beginning | thinner, mostly silver | deeper-set, softer | slight softness through shoulders |
| Elder | 70+ | deeply lined, translucent skin | full silver/white, thinner | hooded lids, softer | gentle stoop |

### Fitness ladder

Body-fat % + muscle-definition cues, NOT just "more athletic":

| Step | Women BF | Men BF | Visible cues |
|---|---|---|---|
| Soft | 28% | 20% | no muscle definition, soft everywhere |
| Toned | 22% | 14% | shoulder caps soft, faint waist taper |
| Athletic | 19% | 12% | visible deltoid separation, defined waist, calf shape |
| Cut | 16% | 9% | abs visible, vascular forearms, ripped quads |

### Hair length ladder

Measurement anchors at landmarks, not "longer":
- Pixie / chin-length
- Collarbone-length
- Mid-back-length
- Waist-length
- Hip-length

### Art-style spectrum

Name 2–3 concrete reference styles per step:
- "Studio Ghibli + modern semi-realistic anime"
- "Disney 2D-3D hybrid like Tangled or Frozen"
- "Pixar 3D rendered like Encanto"
- "Photoreal portrait, 85mm lens, soft natural light"

## Prompt template (body-type example)

```
Full-body standing portrait of {character}, neutral relaxed standing pose facing camera,
arms relaxed at sides, weight even on both feet, gentle smile. Studio photography style,
clean soft-grey seamless backdrop, even diffused front lighting with subtle rim from
above-left, neutral white balance. Full body visible from head to feet, framed centered.

CANONICAL FACE AND HAIR (must match exactly across all variants):
{frozen face/hair/skin/eye description from canon reference}

BODY TYPE — {STEP NAME} (BMI ~{N}, equivalent to ~{lb} lb at {height}):
{quantitative description from ladder table above}

OUTFIT (identical in all variations — this is a controlled study):
{frozen outfit description}

Photographic, realistic, full-body, neutral standing, clean studio reference shot.
```

The "this is a controlled study" phrase materially helps — the model treats it as instruction to hold non-body variables constant.

## Verification checklist before delivery

1. Did each step's silhouette actually change vs. the previous one? (eyeball the spread side-by-side)
2. Is the delta between step 1→2 roughly equal to step 2→3? (if step 2 looks identical to step 1, regenerate step 2 with more aggressive numbers; if step 3 jumped too far, regenerate step 3 with tighter numbers)
3. Did face/hair/outfit/pose/lighting stay constant across all variants?
4. Is there a `MEDIA:<path>` line for each generated image in the reply?

## What NOT to do

- Don't use "slim / average / curvy" without numbers
- Don't change outfit between steps to "show off the body type" — it confounds the comparison
- Don't change pose between steps — neutral standing is the only fair baseline
- Don't generate variants serially across multiple turns — generate all in one parallel batch so the model state is comparable
- Don't trust the first spread — visually check before declaring it done
