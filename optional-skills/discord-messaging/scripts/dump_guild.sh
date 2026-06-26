#!/usr/bin/env bash
# Dump every text/announcement channel in a Discord guild to local JSON files.
# Usage: dump_guild.sh <guild_id> <output_dir> [limit_per_channel]
set -e

GUILD_ID="$1"
OUT_DIR="$2"
LIMIT="${3:-100}"

if [ -z "$GUILD_ID" ] || [ -z "$OUT_DIR" ]; then
  echo "usage: $0 <guild_id> <output_dir> [limit_per_channel]"
  exit 1
fi

if [ -z "$DISCORD_BOT_TOKEN" ]; then
  echo "DISCORD_BOT_TOKEN not set" >&2
  exit 1
fi

mkdir -p "$OUT_DIR/channels"
AUTH="Authorization: Bot $DISCORD_BOT_TOKEN"
BASE="https://discord.com/api/v10"

# 1. Dump guild channels list
curl -s "$BASE/guilds/$GUILD_ID/channels" -H "$AUTH" > "$OUT_DIR/channels.json"

# 2. Filter to text (0) + announcement (5) channels, strip \r from names
python - <<'PY' > "$OUT_DIR/channel_list.txt"
import json, os
out_dir = os.environ['OUT_DIR']
data = json.load(open(f"{out_dir}/channels.json"))
for ch in data:
    if ch.get('type') in (0, 5):
        name = ch['name'].replace('\r','').replace('/','_').replace('\\','_')
        print(f"{ch['id']}|{name}")
PY

export OUT_DIR

# 3. Pull messages per channel, throttled
total=$(wc -l < "$OUT_DIR/channel_list.txt" | tr -d ' ')
i=0
while IFS='|' read -r CID CNAME; do
  i=$((i+1))
  CNAME_CLEAN=$(echo "$CNAME" | tr -d '\r')
  echo "[$i/$total] $CNAME_CLEAN ($CID)"
  curl -s "$BASE/channels/$CID/messages?limit=$LIMIT" -H "$AUTH" \
    > "$OUT_DIR/channels/${CNAME_CLEAN}.json"
  sleep 0.5
done < "$OUT_DIR/channel_list.txt"

echo "Done. Output in $OUT_DIR/"
