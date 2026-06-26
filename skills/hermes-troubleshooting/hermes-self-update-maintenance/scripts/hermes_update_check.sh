#!/usr/bin/env bash
# hermes_update_check.sh
#
# Designed for `no_agent` cron use: exits SILENTLY (empty stdout) when the
# install is current, prints a delta + safe checkout + rollback line when behind.
#
# Drop at ~/.hermes/scripts/hermes_update_check.sh, chmod +x, then:
#   cronjob action='create' name=hermes-update-check-weekly schedule='0 9 * * 1' \
#          no_agent=True script='hermes_update_check.sh' deliver='origin'
#
# Adjust HERMES_REPO if the install lives elsewhere.

set -u
HERMES_REPO="${HERMES_REPO:-$HOME/.hermes/hermes-agent}"

if [ ! -d "$HERMES_REPO/.git" ]; then
  # Not a git install — nothing to check. Silent.
  exit 0
fi

cd "$HERMES_REPO" || exit 0

# Stamp last-check time for the "is the cron alive?" sanity case
mkdir -p "$HOME/.hermes/state"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$HOME/.hermes/state/hermes_update_last_check"

git fetch --tags --quiet 2>/dev/null || exit 0

current_tag="$(git describe --tags --exact-match 2>/dev/null || true)"
current_sha="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
current="${current_tag:-$current_sha}"

latest="$(git tag -l 'v*' | sort -V | tail -1)"

if [ -z "$latest" ]; then
  exit 0
fi

if [ "$current" = "$latest" ]; then
  # Up to date — silent.
  exit 0
fi

# Behind. Compose the report.
behind="$(git rev-list --count "$current..$latest" 2>/dev/null || echo "?")"
rollback="${current}"

echo "🪶 Hermes update available"
echo ""
echo "  current: $current"
echo "  latest:  $latest ($behind commits ahead)"
echo ""
echo "Commits between:"
git log --oneline "$current..$latest" 2>/dev/null | head -20
echo ""
echo "Safe upgrade (run when you have a quiet window):"
echo "  cd $HERMES_REPO && git checkout $latest && hermes doctor"
echo ""
echo "Rollback if it breaks:"
echo "  cd $HERMES_REPO && git checkout $rollback && hermes doctor"
echo ""
echo "Tip: if a $latest hotfix tag (e.g. ${latest}.1) drops in the next 24h,"
echo "apply the hotfix instead — it's usually fixing what $latest broke."
