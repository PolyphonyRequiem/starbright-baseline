#!/usr/bin/env bash
# ==============================================================================
# Companion Setup — ship this INSIDE a shared profile so the recipient can wire
# their own model + image backend across five providers. Copy & adjust the
# default model ids / profile name. Collects nothing, transmits nothing — keys
# are written only to THIS profile's local .env / config.yaml.
#
#   ./setup-companion.sh
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HERMES_HOME="$SCRIPT_DIR"            # this profile dir = its HERMES_HOME
ENVF="$HERMES_HOME/.env"

cfg() { hermes config set "$1" "$2" >/dev/null 2>&1 || true; }
setenv() {  # idempotent KEY=value into this profile's .env
  local k="$1" v="$2"; touch "$ENVF"; chmod 600 "$ENVF"
  grep -v "^${k}=" "$ENVF" > "${ENVF}.tmp" 2>/dev/null || true; mv "${ENVF}.tmp" "$ENVF"
  printf '%s=%s\n' "$k" "$v" >> "$ENVF"
}

cat <<'EOF'
Pick the brain this agent runs on. All five give a fully working agent.
  1) Anthropic Claude   (API key)      2) OpenAI GPT (API key; also image gen)
  3) Google Gemini      (free key; ALSO powers vision + image gen)
  4) GitHub Copilot     (OAuth)        5) Self-hosted Ollama (no key, fully local)
EOF
read -rp "Choose 1-5: " C
case "$C" in
  1) read -rp "ANTHROPIC_API_KEY: " K; setenv ANTHROPIC_API_KEY "$K"
     cfg model.provider anthropic; cfg model.default claude-sonnet-4 ;;
  2) read -rp "OPENAI_API_KEY: " K; setenv OPENAI_API_KEY "$K"
     cfg model.provider openai; cfg model.default gpt-5
     echo "  (same key enables reference-conditioned image gen)";;
  3) echo "Free key: https://aistudio.google.com/apikey"
     read -rp "GEMINI_API_KEY: " K; setenv GEMINI_API_KEY "$K"
     cfg model.provider google; cfg model.default gemini-2.5-pro
     echo "  (one key = chat + vision + image gen)";;
  4) echo "Copilot uses device-code OAuth. After this, run: hermes model -> GitHub Copilot"
     cfg model.provider copilot; cfg model.default claude-sonnet-4 ;;
  5) command -v ollama >/dev/null || { echo "Install: curl -fsSL https://ollama.com/install.sh | sh"; }
     read -rp "Model tag [gemma4:31b]: " M; M="${M:-gemma4:31b}"
     ollama pull "$M" || true
     # Hermes REJECTS <64K context at startup — bake a 64K variant.
     BAKED="${M%%:*}-64k"
     printf 'FROM %s\nPARAMETER num_ctx 64000\n' "$M" > /tmp/Modelfile.sb
     ollama create "$BAKED" -f /tmp/Modelfile.sb || BAKED="$M"
     cfg model.provider custom; cfg model.base_url http://localhost:11434/v1
     cfg model.default "$BAKED"; cfg model.context_length 64000
     setenv OPENAI_API_KEY no-key
     echo "  Local lane = text (+ vision if a vision model is pulled), but NOT image"
     echo "  gen. Pair with Pollinations.ai or a Gemini key to let it draw.";;
  *) echo "Pick 1-5."; exit 1;;
esac

cat <<'EOF'

Image gen + vision (optional, independent of the chat model above):
  - Easiest free : a Google GEMINI_API_KEY does BOTH vision + image gen.
  - No-key gen   : Pollinations.ai (URL-based, zero signup).
  - Best likeness: an OPENAI_API_KEY (reference-conditioned edits).
  - Local vision : Ollama + a llava/llama-vision model.
Choose/enable backends anytime with:  hermes tools

Test:  hermes chat -q "Say hi in one line." -Q
EOF
