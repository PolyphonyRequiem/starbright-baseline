#!/usr/bin/env bash
# Open (or fetch) a Discord DM channel with a user. Idempotent.
# Requires: DISCORD_BOT_TOKEN env var, curl.
# Usage: open_dm.sh <user_id>
# Prints the DM channel id on stdout (errors / raw response go to stderr).

set -euo pipefail

user_id="${1:?user_id required}"

if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  echo "DISCORD_BOT_TOKEN not set" >&2
  exit 1
fi

response=$(curl -sS -X POST https://discord.com/api/v10/users/@me/channels \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"recipient_id\": \"$user_id\"}")

# Extract the first "id":"..." pair (the channel id) without requiring jq.
channel_id=$(printf '%s' "$response" | grep -oE '"id":"[0-9]+"' | head -n1 | cut -d'"' -f4)

if [[ -z "$channel_id" ]]; then
  echo "Failed to parse channel id from response:" >&2
  echo "$response" >&2
  exit 1
fi

echo "$channel_id"
