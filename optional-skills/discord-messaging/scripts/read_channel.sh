#!/usr/bin/env bash
# Fetch recent Discord channel (or thread) messages to a temp file.
# Requires: DISCORD_BOT_TOKEN env var, curl.
# Usage: read_channel.sh <channel_id> [limit] [before_message_id]
# Limit defaults to 50 (max 100 per API call).

set -euo pipefail

channel_id="${1:?channel_id required}"
limit="${2:-50}"
before="${3:-}"

if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  echo "DISCORD_BOT_TOKEN not set" >&2
  exit 1
fi

# Pick a temp dir that BOTH git-bash and a Windows Python subprocess can read.
if [[ -n "${TEMP:-}" ]]; then
  out_dir="$TEMP"
elif [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
  out_dir="/c/Users/${USER:-$USERNAME}/AppData/Local/Temp"
else
  out_dir="/tmp"
fi
mkdir -p "$out_dir"
out_path="$out_dir/discord_${channel_id}_messages.json"

url="https://discord.com/api/v10/channels/$channel_id/messages?limit=$limit"
if [[ -n "$before" ]]; then
  url="$url&before=$before"
fi

http_code=$(curl -sS -w '%{http_code}' -o "$out_path" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  "$url")

echo "HTTP $http_code"
echo "Wrote: $out_path"
echo "Bytes: $(wc -c < "$out_path")"
