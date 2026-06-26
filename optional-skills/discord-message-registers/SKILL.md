---
name: discord-message-registers
description: "Choose and apply Discord-safe presentation registers, especially when mobile legibility matters."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [discord, formatting, tone, mobile, style]
---

# Discord Message Registers

## When to use

Use this skill when:
- the user wants messages to feel themed, stylish, or more "Discord-native"
- the user reacts to formatting quality, legibility, or presentation style
- you are reporting tool-heavy investigation work inside Discord and want it to stay readable on mobile
- the user asks to save or preserve multiple style registers for later switching

## Core rule

**Optimize for Discord rendering first, aesthetics second.**

A format that looks clever in a terminal but fails on Discord mobile is a bad format.

## Durable lessons

1. **Do not rely on ANSI color codes.** Discord mobile may not render them usefully.
2. **Prefer mobile-safe formatting**: markdown, short paragraphs, bullets, fenced code blocks, restrained emoji, and light Unicode structure.
3. **Default to a calmer register after a failed flashy experiment.** If the user liked the idea of styling but disliked the legibility, keep the personality and reduce the ornament.
4. **Keep troubleshooting messages readable.** During technical work, style should support scanning: what changed, what was found, what happens next.
5. **Save named registers, not one-off vibes.** Future sessions should be able to switch by register/tier without re-inventing the style.

## Recommended workflow

1. Identify the message class:
   - status update
   - technical finding
   - recommendation / decision
   - affectionate banter
   - theatrical flourish
2. Pick the lightest register that still matches the user's mood.
3. For technical content, structure as:
   - what I checked
   - what I found
   - what I recommend next
4. If the user asks for a more stylish voice, increase tone before increasing formatting density.
5. If a fancy format fails on mobile, fall back to markdown-first presentation immediately.

## Mobile-safe formatting patterns

### Good defaults
- short lead sentence
- 3-5 bullet points max before a break
- fenced code blocks for commands
- bold labels for scanability
- light emoji as section markers, not every line

### Usually safe
- simple box-drawing separators
- one accent emoji per section
- italic asides
- short quoted pull-lines

### Avoid unless explicitly requested and tested
- ANSI color blocks
- dense decorative Unicode walls
- huge roleplay-style headers for ordinary troubleshooting
- mixed-width glyph art around commands
- long single-message dumps with no sectioning

## Registers

See `references/registers.md` for the tiered register menu.

Practical default for this user after the mobile-rendering correction:
- start around the calm/subtle register
- escalate only when asked

## Discord markdown rendering matrix (verified 2026-06-03)

Discord renders a **subset** of CommonMark. Don't say "Discord doesn't support markdown" — it does, just not all of it. The trap is using table syntax or assuming everything renders.

**Renders correctly in Discord messages:**
- `**bold**`, `*italic*`, `_italic_`, `~~strikethrough~~`, `__underline__`
- `` `inline code` `` and triple-backtick fenced code blocks (with language hint)
- `> blockquote` and `>>> multi-line blockquote`
- `- bullet lists` and `1. numbered lists`
- `||spoiler||` (click-to-reveal, but content still reaches the model)
- Standard links: `[label](url)` (no embed preview suppression by default)
- `\n` line breaks

**Does NOT render — shows as literal text:**
- **Tables.** Pipe-and-dash table syntax (`| col | col |\n|---|---|`) renders as raw character noise. Worst offender on mobile. If you need tabular data on Discord, use one of: (a) a fenced code block with aligned columns, (b) `**Label:** value` lines, (c) numbered prose ("1. X — value. 2. Y — value."), or (d) attach a CSV/PNG.
- **Hash-mark headings** (`# H1`, `## H2`) — formally supported but reportedly inconsistent on this user's clients; treat as literal text. Use **bold all-caps section titles** instead: `**ROUND 4 FINDINGS**`.
- **Horizontal rules** (`---`) — render as text.
- **Nested lists deeper than 1 level** — collapse visually.
- **HTML tags** — escaped, shown literally.

**Recovery cue:** if the user says "don't use markdown, it doesn't render on Discord" they almost certainly mean tables and/or headings rendered as garbage. Don't drop markdown wholesale — drop tables and headings, keep bold/italic/code/bullets/blockquote, and offer to retry. Acknowledge the specific subset that broke rather than blanket-conceding. **Re-confirmed 2026-06-03:** user pushed back on a hash-heading + pipe-table reply ("don't use markdown here, it doesn't render on discord"); the recovery (re-issue same content as bold-label prose + numbered list, name the specific subset that fails) landed cleanly. The matrix below is durable; the failure shape is always tables-or-headings, never bold/italic/code.

**Default presentation for technical findings on Discord:** plain prose paragraphs, numbered prose for enumerable findings, bold labels for scannability, fenced code blocks for commands/identifiers, no tables, no hash-headings.

## Pitfalls

- Treating terminal formatting as if Discord will render it the same way
- Making operational updates so ornate that the actual finding is hard to skim
- Using loud style after the user has already asked for something more chill
- Confusing warmth with clutter; warmth can live in wording, not just ornament

## Verification

A good Discord-formatted response should satisfy all of these:
- readable on phone
- key finding visible in under 3 seconds
- commands copy-paste cleanly
- style feels intentional, not noisy
- user can easily ask for "more plain" or "more extra" and you can shift registers quickly
