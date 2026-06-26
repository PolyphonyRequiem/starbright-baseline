---
name: local-corpus-fact-checking
description: When the user has mirrored a domain corpus locally (wiki dumps, decompiled source, scraped docs, cloned reference repos), grep the mirror FIRST before claiming any fact about that domain. Also covers carving large mirrors into a router-umbrella skill + N domain skills constellation so future sessions route to the right slice instead of loading 26MB into context.
when_to_use:
  - User has a local directory of mirrored wiki / docs / scraped pages / cloned reference repos in their workspace.
  - You are about to make a factual claim about a game, library, framework, API, or other domain the user has mirrored.
  - User asks you to "build a knowledge base" / "index the docs" / "make this searchable" over a large local corpus.
  - You catch yourself reaching for memory or web_search when a local mirror exists.
triggers:
  - User says "you have it locally" / "check the corpus" / "stop hallucinating" / "rely more on local data"
  - You make a confident negative claim about domain content ("X doesn't have Y") without grepping
  - User points at a `~/.../wiki/` or `~/.../corpus/` or `~/.../docs/` directory they built
  - Corpus is too large to load fully (>1MB or >50 files) but small enough to grep cheaply
---

# Local Corpus Fact-Checking & Constellation Authoring

Two related disciplines:

1. **Fact-checking discipline** — when a local mirror exists, it is the source of truth. Training-data memory is fallback, web search is fallback. Grep first.
2. **Constellation authoring** — for large mirrors (hundreds of pages), build a router-umbrella skill + N domain-sliced skills so future sessions load only the slice they need.

## Discipline: grep before claiming

### The failure this prevents

Confidently asserting a factual negative ("X doesn't have Y", "X is obsolete", "you can't do Z in X") about a domain whose authoritative reference is sitting on disk. Real case: claiming a game "has no bears" when the wiki mirror was on disk with full stats, an internal ID, and four drops listed.

### Rule

Before any factual claim about a domain with a local mirror:

```bash
# Always check first
ls ~/<corpus_root>/ | grep -iE '<term>'
grep -liE '\b<term>\b' ~/<corpus_root>/*.md | head -20
```

If the mirror is structured (decompiled source, classified docs), prefer the structured query path the user already built (e.g. `scripts/q.py wiki <term>`) over raw grep.

### Pitfalls

- **Pattern-matching to "interesting" instead of grepping for "boring obvious".** If you have a hunch the user is wrong, that hunch is exactly when you must check first.
- **Wrong regex anchoring on category headers.** Wiki scrapers often emit categories with internal underscores (`Points_of_interest`, `Crafting_structures`). A regex like `_Categories: ([^_]+?)_` will stop at the first internal underscore. Match through to end-of-line with `(.+?)_\s*$` instead. See `references/wiki-scrape-quirks.md`.
- **Case-sensitive grep on platforms where the user's corpus has both `Foo.md` and `foo.md`.** Some scrapers duplicate pages. Use `-i` for discovery, then dedupe by content.
- **Forgetting the mirror was scraped at a point in time.** A 2026-06 Valheim scrape doesn't have post-2026-06 patch content. State the corpus date when relevant.

## Discipline: route, don't load

For corpora >1MB or >50 pages, don't `cat` the whole thing into context. Build (or use) a constellation:

- **Umbrella skill** (e.g. `valheim-wiki`) — short SKILL.md that names the corpus, states the "grep first" rule, and lists the domain-sliced skills with one-line descriptions. This is the always-on entry point.
- **Domain skills** (e.g. `valheim-creatures`, `valheim-materials`) — one per natural category cleavage. Each has a tight SKILL.md (when to load, how to use) and a `references/index.md` table mapping every page in that domain to `title | internal_id | blurb`. Future sessions load the umbrella, get routed to a domain, scan the index table, then `cat` the specific page.

This keeps any single skill load cheap while preserving full corpus depth on demand.

## Technique: building a constellation from a mirrored wiki

When the user asks you to turn a mirrored corpus into a constellation:

### 1. Survey the corpus

```bash
ls ~/<corpus>/ | wc -l
du -sh ~/<corpus>/
# Category / metadata histogram — adapt the regex to the scraper's format
head -3 -q ~/<corpus>/*.md | grep -oP '_Categories: \K[^_]+' | tr ',' '\n' \
  | sed 's/^ *//;s/ *$//' | sort | uniq -c | sort -rn | head -50
```

Look at the histogram to design domain cleavages. Big buckets (>50 pages) deserve their own skill; small buckets group under "misc" or merge into neighbors.

### 2. Author or reuse the builder script

A reusable template lives at `templates/build_wiki_constellation.py.tmpl`. Adapt the constants:

- `WIKI` — path to the mirrored markdown corpus.
- `SKILLS_ROOT` — where to write the constellation (e.g. `~/.hermes/skills/<domain>/`).
- `DOMAINS` — list of `(skill_name, [category_keywords], description)`. Order matters; first match per page wins.
- Regex for the corpus's category-header format.

Run it. The script is **idempotent** — rerun any time to refresh after the corpus updates.

### 3. Health-check the routing

After building, inspect the misc bucket:

```bash
# What fraction of pages fell into misc?
python3 ~/.hermes/scripts/build_<corpus>_constellation.py 2>&1 | tail -3
# Target: misc < 15% of total
```

If misc is large (>20%):

- **Sample a few pages from the misc bucket** and check their actual categories. Often you'll find a whole category that wasn't routed (real case: "Trophies", "Points_of_interest", "Crafting_structures" all unrouted in first pass).
- **Suspect your regex.** Most over-misc bugs are header-regex bugs, not routing-table bugs. Inspect what `parse_page` actually extracted for a misc page.
- **Re-add to DOMAINS routing keywords** and rerun. The builder is idempotent.

### 4. Schedule a refresh job (optional)

If the corpus refreshes periodically (rescrape after a patch), wire the builder as a recurring `no_agent` cron job. The script's one-line stdout summary becomes the notification.

```python
# Example cron registration (call from a session, not from this skill)
cronjob(action='create',
        schedule='0 4 * * 0',  # weekly Sunday 4am
        no_agent=True,
        script='build_<corpus>_constellation.py',
        name='<corpus>-constellation-refresh')
```

Scripts for cronjobs must live at `~/.hermes/scripts/<name>.py` (relative path, just the filename in the `script` field).

## Pitfalls (constellation building)

- **Naming domain skills after one-off subjects.** Domain skills must be class-level (`<corpus>-creatures`), not session-level (`<corpus>-bog-witch-bestiary`). The constellation is durable infrastructure.
- **Hardcoding domain keywords from a single-page sample.** Survey the full category histogram before designing cleavages.
- **Forgetting to write the umbrella skill.** Without the router, future sessions don't know the constellation exists. The umbrella is the discoverability surface.
- **Putting full page content in `references/index.md`.** The index is a *lookup table*, not a content mirror. Point at `~/<corpus>/<page>.md` and let agents `cat` what they need.
- **Skipping the "Hard rule" in the umbrella.** The umbrella SKILL.md must explicitly say "grep the corpus before claiming any fact" — that's half of why the constellation exists.

## Anti-patterns from real sessions

- Claiming "Valheim has no bears" with `Bear.md` on disk. Cost: user trust dent, explicit correction, full skill-building task spawned to prevent recurrence.
- Generating a constellation where 57% of pages fell into "misc" because the category-header regex matched only the first segment of multi-word categories. Always sample misc and confirm <15%.
- Loading a 26MB wiki dump directly into context "to summarize it" instead of routing. Token-expensive, low-signal, and you can't reuse the work next session.

## Verification

After applying this skill you should be able to:

1. Point at the exact local-mirror path you grepped before making each factual claim about the domain.
2. Show a constellation umbrella + N domain skills, each with a `references/index.md` lookup table.
3. Report `misc < 15%` of total pages.
4. Show the builder script is idempotent (rerunning produces the same constellation).

## Related skills

- `domain-expert-collaboration` — when the user is the expert and the local corpus is *their* prior art.
- `hermes-agent-skill-authoring` — frontmatter conventions, validator, structure for the umbrella and domain SKILL.md files.
- `conversation-frame-verification` — check that "the user said X" is actually a current user turn before treating it as authoritative.
