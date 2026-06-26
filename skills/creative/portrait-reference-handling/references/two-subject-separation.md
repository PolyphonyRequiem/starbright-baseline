# Two-subject separation in portrait generation

Use this when a multi-reference image is supposed to show two distinct people but the model keeps collapsing them into one merged figure.

## Failure pattern

Common bad outputs:
- one blended face that averages both subjects
- a single torso with ambiguous ownership
- overlapping or fused shoulders / chest / hips
- a two-person scene that reads as one glamorous person instead of two people in relation

## Prompt pattern that helps

State the separation as composition, not just identity:
- "two distinct people"
- "two separate faces"
- "two separate torsos"
- "two separate body positions"
- "subject A asleep and reclining"
- "subject B awake and leaning over them"
- "one supported above, one resting below"

Asymmetric role language helps more than repeating names.

## Workflow adjustments

1. Prefer subject-specific refs over pair refs when fusion starts happening.
2. If a paired photo causes bleed, remove it for the next pass.
3. Reduce ref count if the stack is too heavy and the model starts averaging identities.
4. Lower resolution / steps for faster debugging passes before spending minutes on a larger render.
5. Treat merged-person outputs as failed composition, not acceptable approximations.

## Good negative prompt cues

- single person
- merged bodies
- fused faces
- one composite person
- siamese anatomy
- duplicated limbs
- ambiguous limb ownership

## Verification

Before showing the image to the user, check:
- can you point to two separate faces?
- can you point to two separate torsos?
- does the asymmetric role split remain legible?
- does the image read as two distinct people rather than one person with extra limbs or blended features?
