#!/usr/bin/env bash
# check-drift.sh — has this installed profile drifted from what its distribution shipped?
#
# Wraps lineage.py so a human (or the profile-reconcile skill) can answer
# "which distribution-owned files did I edit locally?" WITHOUT needing a .git
# checkout — the installer strips .git, so git-diff is not available on an
# installed profile. Drift is computed against distribution.manifest (the
# path:sha256 baseline shipped with the distribution).
#
# Usage:
#   check-drift.sh <profile_dir>            # report drift (JSON) — exit 1 if drifted
#   check-drift.sh --regen <profile_dir>    # (re)write the baseline manifest, then exit 0
#
# Exit: 0 = clean (or --regen done), 1 = drift found, 2 = usage/error.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINEAGE="$HERE/lineage.py"

# On git-bash / MSYS the script dir is a POSIX path (/c/Users/...), but a
# native-Windows Python reads '/c/...' as 'C:\c\...' and can't find the script.
# Convert to a native path when cygpath is present (harmless no-op elsewhere).
if command -v cygpath >/dev/null 2>&1; then
  LINEAGE="$(cygpath -w "$LINEAGE")"
fi

# Prefer a real python3; fall back to 'python' (Windows/git-bash where python3
# is a broken Store shim). Both must have PyYAML — lineage.py checks and errors.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import yaml' >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done
if [[ -z "$PY" ]]; then
  echo "check-drift: no python with PyYAML found on PATH" >&2
  exit 2
fi

REGEN=0
if [[ "${1:-}" == "--regen" ]]; then
  REGEN=1; shift
fi

DIR="${1:-}"
if [[ -z "$DIR" || ! -d "$DIR" ]]; then
  echo "usage: check-drift.sh [--regen] <profile_dir>" >&2
  exit 2
fi

if [[ "$REGEN" -eq 1 ]]; then
  "$PY" "$LINEAGE" manifest-gen "$DIR"
  exit 0
fi

if [[ ! -f "$DIR/distribution.manifest" ]]; then
  echo "check-drift: no distribution.manifest in $DIR — run: check-drift.sh --regen $DIR" >&2
  exit 2
fi

# lineage.py drift already exits 0 clean / 1 drifted and prints the JSON report.
exec "$PY" "$LINEAGE" drift "$DIR"
