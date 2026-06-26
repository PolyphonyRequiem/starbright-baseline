# Vision size notes for Discord history synthesis

Derived from a real Discord-history + local-cache workflow under GPT-5.4 via GitHub Copilot ACP.

## What worked
`vision_analyze` succeeded on local images around:
- 44 KB
- 76 KB
- 84 KB
- 90 KB
- 125 KB
- 169 KB
- 334 KB
- 413 KB
- 533 KB
- 598 KB
- 841 KB
- 1.0 MB
- 1.1 MB
- 2.2 MB
- 2.3 MB
- 2.4 MB
- 2.5 MB
- 2.6 MB
- 2.7 MB
- 3.4 MB

## What failed
A local PNG around **5.0 MB** failed with:
- `Error code: 413`
- `failed to parse request`

## Practical rule
For this workflow, keep images at or below roughly **3 MB** when possible, and treat **5 MB** as risky.

## Interpretation
This is not a permanent Hermes-wide rule. It is a practical working threshold for this provider/model/path combination during Discord-history visual synthesis.
