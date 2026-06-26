#!/usr/bin/env bash
# Test whether a vision backend accepts an image payload.
#
# Usage:
#   bash test_vision_backend.sh <token-env-var> <base-url> <model> <image-path>
#
# Example (GitHub Models, free under existing GitHub access):
#   bash test_vision_backend.sh \
#     COPILOT_GITHUB_TOKEN \
#     https://models.github.ai/inference \
#     openai/gpt-4o-mini \
#     ~/.hermes/image_cache/some_image.png
#
# Exit codes:
#   0 = backend accepted the image and returned a description.
#   1 = backend rejected the image or auth/payload failed.

set -e

TOKEN_VAR="${1:-COPILOT_GITHUB_TOKEN}"
BASE_URL="${2:-https://models.github.ai/inference}"
MODEL="${3:-openai/gpt-4o-mini}"
IMAGE="${4:-}"

# Resolve token from env, falling back to ~/.hermes/.env.
TOKEN_VALUE="${!TOKEN_VAR:-}"
if [ -z "$TOKEN_VALUE" ] && [ -f "$HOME/.hermes/.env" ]; then
  TOKEN_VALUE=$(grep -E "^${TOKEN_VAR}=" "$HOME/.hermes/.env" 2>/dev/null \
    | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
fi

if [ -z "$TOKEN_VALUE" ]; then
  echo "ERROR: $TOKEN_VAR not found in env or ~/.hermes/.env" >&2
  exit 1
fi

if [ -z "$IMAGE" ] || [ ! -f "$IMAGE" ]; then
  echo "ERROR: image path required and must exist (arg 4)" >&2
  exit 1
fi

# Detect MIME type (prefer `file`, fall back to extension).
if command -v file >/dev/null 2>&1; then
  MIME=$(file --mime-type -b "$IMAGE")
else
  case "${IMAGE##*.}" in
    png) MIME=image/png ;;
    jpg|jpeg) MIME=image/jpeg ;;
    gif) MIME=image/gif ;;
    webp) MIME=image/webp ;;
    *)   MIME=application/octet-stream ;;
  esac
fi

# Base64 encode (handle both GNU and BSD base64).
B64=$(base64 -w 0 "$IMAGE" 2>/dev/null || base64 "$IMAGE" | tr -d '\n')

# Build payload with Python to avoid shell quoting hell.
PAYLOAD=$(MODEL="$MODEL" MIME="$MIME" B64="$B64" python3 -c '
import json, os
print(json.dumps({
    "model": os.environ["MODEL"],
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe this image in one sentence."},
            {"type": "image_url", "image_url": {"url": f"data:{os.environ[chr(39)+chr(77)+chr(73)+chr(77)+chr(69)+chr(39)]};base64,{os.environ[chr(39)+chr(66)+chr(54)+chr(52)+chr(39)]}"}}
        ]
    }]
}))
')

echo "=== Testing $BASE_URL with $MODEL ==="
RESPONSE=$(curl -s -X POST "$BASE_URL/chat/completions" \
  -H "Authorization: Bearer $TOKEN_VALUE" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD")

echo "$RESPONSE" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    if "error" in d:
        print("FAIL:", json.dumps(d["error"], indent=2))
        sys.exit(1)
    content = d.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        print("FAIL: empty response, full body:", json.dumps(d, indent=2))
        sys.exit(1)
    print("OK:", content)
except json.JSONDecodeError:
    sys.stdin.seek(0) if hasattr(sys.stdin, "seek") else None
    print("PARSE ERROR. Raw:")
    sys.exit(1)
'
