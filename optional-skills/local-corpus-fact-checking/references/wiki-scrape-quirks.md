# Wiki-scrape quirks observed in real corpora

Notes on parsing pitfalls encountered when building constellations from
mirrored markdown corpora. Add to this file as new quirks surface.

## Category headers with internal underscores

**Symptom:** Most pages land in the "misc" bucket after running the builder
script, even though the corpus is well-categorized.

**Cause:** Wiki scrapers commonly emit category headers like:

```
_Categories: Points_of_interest, Crafting_structures_
```

Where the leading and trailing `_` are markdown italic markers wrapping the
WHOLE line, and the category names themselves contain internal underscores
representing spaces. A naive regex:

```python
re.compile(r"^_Categories:\s*([^_]+?)_\s*$")
```

stops at the FIRST underscore inside the category name, capturing only
`Points` and dropping the rest of the categories on that line.

**Fix:** Anchor on end-of-line, not on the bounding underscore:

```python
re.compile(r"^_Categories:\s*(.+?)_\s*$", re.MULTILINE)
```

The `(.+?)` is non-greedy but `_\s*$` anchors the match to the last
underscore before end-of-line, which is the italic close marker.

**Real impact:** First Valheim wiki constellation pass routed 1035/1811
(57%) pages to misc. After this regex fix: 218/1811 (12%) — clean.

## Duplicate pages with case differences

Some scrapers emit both `Abyssal_harpoon.md` and `Abyssal_Harpoon.md` for
the same content (one from a link target, one from the canonical page).
Filesystems may treat these as different files. For routing purposes both
get processed; for player-facing references prefer the page with more body
content. Don't dedupe at constellation-build time — let `references/index.md`
list both and let the consumer pick.

## URL-encoded special characters in filenames

Pages whose titles contain `:` (e.g. `Mead base: Tasty`) may be saved by
the scraper as either:

- `Mead_base:_Tasty.md` (literal colon — works on Linux/macOS)
- `Mead_base%3A_Tasty.md` (URL-encoded)
- `Mead_base_Tasty.md` (colon stripped)

Survey the corpus for `*:*` and `*%*` filenames before assuming a single
convention. Document the convention used.

## Stub pages with only a category header

Some wiki pages exist as stubs — just the title and a category line, no
body. The builder script handles these fine (blurb falls back to category
list), but downstream `cat` operations will return near-empty files.
Document this in the domain SKILL.md so consumers don't extrapolate.

## Scraper date matters

Mirrored corpora are point-in-time snapshots. Always preserve the scrape
date in the umbrella SKILL.md ("Scraped: YYYY-MM <release-era>"). When the
domain releases new content, the corpus is wrong for that content until
rescraped. State the limitation explicitly when answering questions about
recent patches.
