#!/usr/bin/env bash
# Contamination sweep for a Hermes share-profile (or extracted export tree).
# Usage: contamination-sweep.sh <dir> [markers-file]
# Prints per-file hit counts ranked high->low, then a ZERO/NONZERO verdict.
# Exit 0 = clean (zero hits), exit 1 = hits found, exit 2 = usage error.
#
# 🔴 The markers are the private part — DO NOT hardcode real names/IDs into this
# script. A sweep tool that ships with the household's name list IS itself a leak.
# Supply the sensitive markers OUT-OF-BAND, one of three ways (checked in order):
#
#   1. A markers file passed as $2 (one regex term per line; '#' comments ok).
#   2. The HERMES_SWEEP_MARKERS env var (a single '|'-joined alternation).
#   3. A markers file at $HOME/.hermes/.contamination-markers (git-ignored).
#
# Keep that markers file OUTSIDE any profile you export, and never commit it.
# Before trusting a "clean" verdict, fill it with: the user's real name, partner/
# family/pet names, host/box names, project codenames, channel-ID prefixes,
# network IP prefixes, voice_id values, and any private endpoint.

set -euo pipefail
DIR="${1:-}"
if [[ -z "$DIR" || ! -d "$DIR" ]]; then
  echo "usage: contamination-sweep.sh <dir> [markers-file]" >&2
  exit 2
fi

# --- Generic structural markers (safe to ship — no personal data) ------------
# These catch the SHAPE of a leak (a real key, an IP, a long ID) without naming
# anyone. The persona-specific names come from the out-of-band sources below.
GENERIC='[0-9]{1,3}(\.[0-9]{1,3}){3}|sk-[A-Za-z0-9]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|[0-9]{17,20}|/home/[a-z][a-z0-9_-]+|/Users/[A-Za-z][A-Za-z0-9_-]+'

# --- Persona/household markers, supplied out-of-band (never hardcoded) --------
PERSONAL=""
MARKERS_FILE="${2:-${HERMES_SWEEP_MARKERS_FILE:-$HOME/.hermes/.contamination-markers}}"
if [[ -n "${HERMES_SWEEP_MARKERS:-}" ]]; then
  PERSONAL="$HERMES_SWEEP_MARKERS"
elif [[ -f "$MARKERS_FILE" ]]; then
  # one term per line, strip comments/blank lines, join with '|'
  PERSONAL="$(grep -vE '^\s*(#|$)' "$MARKERS_FILE" | paste -sd '|' -)"
fi

if [[ -z "$PERSONAL" ]]; then
  echo "WARNING: no personal markers supplied (arg / HERMES_SWEEP_MARKERS / $MARKERS_FILE)." >&2
  echo "         Sweeping with GENERIC structural patterns only — names will NOT be caught." >&2
  echo "         Provide a markers file before trusting a 'clean' verdict." >&2
  echo >&2
  MARKERS="$GENERIC"
else
  MARKERS="${GENERIC}|${PERSONAL}"
fi

echo "== contamination sweep: $DIR =="
echo "== generic patterns active; personal markers: $([[ -n "$PERSONAL" ]] && echo "loaded ($(echo "$PERSONAL" | tr '|' '\n' | grep -c .) terms)" || echo "NONE (see warning)")"
echo

# Text hits, ranked by per-file count.
total=0
while IFS= read -r f; do
  c=$(grep -aIicE "$MARKERS" "$f" 2>/dev/null || true)
  if [[ "${c:-0}" -gt 0 ]]; then
    printf "%4d  %s\n" "$c" "${f#$DIR/}"
    total=$((total + c))
  fi
done < <(grep -aIilrE "$MARKERS" "$DIR" 2>/dev/null || true)

echo
# Asset / binary ref check — real photos of real people are the sharpest hazard.
echo "== image/binary asset files present (review — default is NONE should travel) =="
find "$DIR" -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \
  -o -iname '*.webp' -o -iname '*.gif' -o -iname '*.mp4' -o -iname '*.mp3' \) \
  -printf '%s  %p\n' 2>/dev/null | sed "s#$DIR/##" || true

echo
# Secret/user-data files that must NOT be in an export tree.
echo "== forbidden files (must be ABSENT in an export tree) =="
for bad in .env auth.json; do
  if find "$DIR" -name "$bad" -print -quit 2>/dev/null | grep -q .; then
    echo "  PRESENT (LEAK): $bad"
    total=$((total + 1))
  fi
done
# memories/ must be empty (or absent).
if find "$DIR" -path '*/memories/*' -type f -print -quit 2>/dev/null | grep -q .; then
  echo "  NON-EMPTY memories/ (LEAK)"
  total=$((total + 1))
fi

echo
if [[ "$total" -eq 0 ]]; then
  echo "VERDICT: ZERO hits — clean. (Still eyeball the asset list above.)"
  exit 0
else
  echo "VERDICT: $total hit(s) — NOT clean. Fix or drop the files above, then re-run."
  exit 1
fi
