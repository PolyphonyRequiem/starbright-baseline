#!/usr/bin/env bash
# hermes_self_update.sh — runs UNDER its own systemd unit (hermes-update.service),
# decoupled from the gateway so stopping the gateway mid-update can't kill the updater.
#
# Flow: backup -> stop gateway -> git fetch+checkout target tag -> reinstall deps
#       (uv pip install -e .) -> config migrate -> doctor -> restart gateway.
#
# Target tag: env HERMES_UPDATE_TARGET (set via `systemctl --user set-environment`),
# else first arg, else 'main'.
#
# Why a script + oneshot unit instead of `hermes update` directly:
#   `hermes update` stops the gateway itself; when invoked from a tool call that is
#   *delivered through* that gateway, the caller dies mid-update. Running here, under
#   systemd, the updater outlives the gateway bounce. (Root cause seen 2026-06-06.)
set -uo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
REPO="$HERMES_HOME/hermes-agent"
HERMES_BIN="$HOME/.local/bin/hermes"
TARGET="${HERMES_UPDATE_TARGET:-${1:-main}}"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$HERMES_HOME/logs/self-update-$STAMP.log"
BACKUP="$HERMES_HOME/backups/pre-update-$STAMP"

mkdir -p "$HERMES_HOME/logs" "$BACKUP"
exec > >(tee -a "$LOG") 2>&1

echo "=== Hermes self-update $STAMP ==="
echo "Target ref: $TARGET"

# 1) Backup the irreplaceable bits.
echo "--- [1/6] Backup -> $BACKUP"
cp -a "$HERMES_HOME/config.yaml"    "$BACKUP/" 2>/dev/null || true
cp -a "$HERMES_HOME/.env"           "$BACKUP/" 2>/dev/null || true
cp -a "$HERMES_HOME/memories"       "$BACKUP/" 2>/dev/null || true
cp -a "$HERMES_HOME/cron/jobs.json" "$BACKUP/" 2>/dev/null || true
PREV_REF="$(git -C "$REPO" describe --tags --exact-match 2>/dev/null || git -C "$REPO" rev-parse --short HEAD)"
echo "$PREV_REF" > "$BACKUP/PREVIOUS_REF.txt"
echo "Rollback:  git -C $REPO checkout $PREV_REF && systemctl --user restart hermes-gateway"

# 2) Stop the gateway(s). Not delivered through it here, so a clean stop is safe.
echo "--- [2/6] Stop gateway"
systemctl --user stop hermes-gateway.service 2>/dev/null || true
LOCALINTIMATE_WAS_ACTIVE=0
systemctl --user is-active --quiet hermes-gateway-local-intimate.service && LOCALINTIMATE_WAS_ACTIVE=1
[ "$LOCALINTIMATE_WAS_ACTIVE" = 1 ] && systemctl --user stop hermes-gateway-local-intimate.service 2>/dev/null || true

# 3) Fetch + checkout the target tag (or pull if it's a branch).
echo "--- [3/6] git fetch + checkout $TARGET"
git -C "$REPO" fetch --tags --prune || { echo "FATAL: git fetch failed"; exit 75; }
if git -C "$REPO" rev-parse --verify --quiet "refs/tags/$TARGET" >/dev/null; then
    git -C "$REPO" checkout --force "$TARGET" || { echo "FATAL: checkout tag $TARGET failed"; exit 75; }
else
    git -C "$REPO" checkout --force "$TARGET" 2>/dev/null && git -C "$REPO" pull --ff-only origin "$TARGET" \
        || { echo "FATAL: checkout/pull $TARGET failed"; exit 75; }
fi
NEW_REF="$(git -C "$REPO" describe --tags --exact-match 2>/dev/null || git -C "$REPO" rev-parse --short HEAD)"
echo "Now at: $NEW_REF (was $PREV_REF)"

# 4) Reinstall deps via the project's editable install (uv-backed venv).
echo "--- [4/6] Reinstall deps"
if command -v uv >/dev/null 2>&1; then
    VIRTUAL_ENV="$REPO/venv" uv pip install -e "$REPO" || echo "WARN: uv install returned nonzero"
else
    "$REPO/venv/bin/python" -m pip install -e "$REPO" || echo "WARN: pip install returned nonzero"
fi

# 5) Config migration (non-interactive) + doctor.
echo "--- [5/6] config migrate + doctor"
"$HERMES_BIN" config migrate --yes 2>/dev/null || "$HERMES_BIN" config migrate 2>/dev/null || true
"$HERMES_BIN" doctor 2>&1 | tail -30 || true
"$HERMES_BIN" version 2>&1 | head -3 || true

# 6) Restart gateway(s).
echo "--- [6/6] Restart gateway"
systemctl --user start hermes-gateway.service || { echo "FATAL: gateway failed to start"; exit 1; }
[ "$LOCALINTIMATE_WAS_ACTIVE" = 1 ] && systemctl --user start hermes-gateway-local-intimate.service || true

echo "=== Self-update complete: $PREV_REF -> $NEW_REF ==="
echo "Log: $LOG"
echo "Backup: $BACKUP"
