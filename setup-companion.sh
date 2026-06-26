#!/usr/bin/env bash
# ==============================================================================
# Starbright-Baseline — Companion Setup
# ==============================================================================
# Wires this profile to one of five model backends, then points you at the
# image/vision and gateway steps. Run it after installing the profile.
#
#   ./setup-companion.sh
#
# It does NOT collect or transmit anything. Keys you enter are written only to
# this profile's local .env / config.yaml on your own machine.
# ==============================================================================

set -euo pipefail

# --- locate this profile's HERMES_HOME ----------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HERMES_HOME="$SCRIPT_DIR"
CONFIG="$HERMES_HOME/config.yaml"
ENVF="$HERMES_HOME/.env"

cfg()  { hermes config set "$1" "$2" >/dev/null 2>&1 || true; }
setenv() {  # setenv KEY value  -> idempotent write into this profile's .env
  local k="$1" v="$2"
  touch "$ENVF"; chmod 600 "$ENVF"
  grep -v "^${k}=" "$ENVF" > "${ENVF}.tmp" 2>/dev/null || true
  mv "${ENVF}.tmp" "$ENVF"
  printf '%s=%s\n' "$k" "$v" >> "$ENVF"
}

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
hr()   { printf '%s\n' "------------------------------------------------------------"; }

# --- Step 0: make this profile self-contained & private -----------------------
# A distributed profile gets its OWN HERMES_HOME (this dir), and Hermes reads
# THIS dir's config.yaml — it does NOT merge any host-global config on top. So
# the moment a config.yaml exists here, the profile can never inherit a host's
# personal settings (TTS voice_id, MCP servers, Discord/home channel IDs — those
# live only in a personal global config, which is never shipped and never read
# once this file exists). We seed it now so that guarantee holds from first run,
# and defensively blank the one identity-bearing scalar in case this profile was
# ever copied from a dirty config.
seed_private_config() {
  [[ -f "$CONFIG" ]] || cfg model.provider auto   # creates this profile's own config.yaml
  cfg tts.elevenlabs.voice_id ""                  # never inherit a cloned-voice identity
}

clear || true
bold "Starbright-Baseline — Companion Setup"
hr
seed_private_config   # make this profile self-contained & private before anything else
cat <<'EOF'
Pick the brain Starbright runs on. All five give you a fully working agent.

  1) Anthropic Claude     — top-tier reasoning + tool use   (API key)
  2) OpenAI GPT           — strong all-rounder               (API key)
  3) Google Gemini        — generous free tier; ONE key also
                            powers image gen + vision        (API key, free)
  4) GitHub Copilot       — if you already pay for Copilot   (OAuth)
  5) Self-hosted (Ollama) — $0, fully local, nothing leaves
                            your machine                     (no key)

EOF
read -rp "Choose 1-5: " CHOICE
hr

case "$CHOICE" in
  1)
    bold "Anthropic Claude"
    read -rp "Paste your ANTHROPIC_API_KEY (sk-ant-...): " K
    setenv ANTHROPIC_API_KEY "$K"
    cfg model.provider anthropic
    cfg model.default  "claude-sonnet-4"
    echo "→ Provider: anthropic, model: claude-sonnet-4 (change later with /model)"
    ;;
  2)
    bold "OpenAI GPT"
    read -rp "Paste your OPENAI_API_KEY (sk-...): " K
    setenv OPENAI_API_KEY "$K"
    cfg model.provider openai
    cfg model.default  "gpt-5"
    echo "→ Provider: openai, model: gpt-5 (change later with /model)"
    echo "  Tip: the same OPENAI_API_KEY also enables reference-conditioned"
    echo "  image generation (the character-consistency skill)."
    ;;
  3)
    bold "Google Gemini  (recommended free starting point)"
    echo "Get a free key at https://aistudio.google.com/apikey"
    read -rp "Paste your GEMINI_API_KEY: " K
    setenv GEMINI_API_KEY "$K"
    cfg model.provider google
    cfg model.default  "gemini-2.5-pro"
    echo "→ Provider: google, model: gemini-2.5-pro"
    echo "  Bonus: this ONE key also covers vision (image recognition) AND"
    echo "  image generation — Starbright can see and draw out of the box."
    ;;
  4)
    bold "GitHub Copilot"
    echo "Copilot uses a device-code OAuth login, not a pasted key."
    echo "After this script, run:   hermes model    → pick GitHub Copilot"
    echo "(gh-cli tokens do NOT work for the Copilot API — use the in-app flow.)"
    cfg model.provider copilot
    cfg model.default  "claude-sonnet-4"
    ;;
  5)
    bold "Self-hosted — Ollama (zero cloud, nothing leaves your box)"
    if ! command -v ollama >/dev/null 2>&1; then
      echo "Ollama not found. Install it first:"
      echo "  curl -fsSL https://ollama.com/install.sh | sh"
      read -rp "Install now? [y/N] " GO
      [[ "$GO" =~ ^[Yy]$ ]] && curl -fsSL https://ollama.com/install.sh | sh
    fi
    echo
    echo "Hermes needs a tool-calling model with >=64K context."
    echo "Recommended: a current tool-capable model (e.g. gemma4:31b)."
    read -rp "Model tag to pull/use [gemma4:31b]: " M
    M="${M:-gemma4:31b}"
    echo "Pulling $M ..."; ollama pull "$M" || true
    # Bake a 64K-context variant (Hermes rejects <64K at startup).
    BAKED="${M%%:*}-64k"
    printf 'FROM %s\nPARAMETER num_ctx 64000\n' "$M" > /tmp/Modelfile.sb
    ollama create "$BAKED" -f /tmp/Modelfile.sb || BAKED="$M"
    cfg model.provider   custom
    cfg model.base_url   "http://localhost:11434/v1"
    cfg model.default    "$BAKED"
    cfg model.context_length 64000
    setenv OPENAI_API_KEY "no-key"   # Ollama ignores it; some paths want it set
    echo "→ Local model: $BAKED via http://localhost:11434/v1"
    echo "  Note: local lanes give you text + (with a vision model) recognition,"
    echo "  but NOT image generation — pair with Pollinations.ai or a Gemini key"
    echo "  if you want Starbright to draw. See the character-rendering skill."
    ;;
  *)
    echo "No valid choice. Re-run and pick 1-5."; exit 1
    ;;
esac

hr
bold "Image generation + vision (optional but recommended)"
cat <<'EOF'
Starbright can see images and render her own portraits — but only if an image
backend is wired. Independent of your chat model above:

  • Easiest free path : a Google GEMINI_API_KEY does BOTH vision + image gen.
  • No-key image gen   : Pollinations.ai (URL-based, zero signup).
  • Best face likeness : an OPENAI_API_KEY (reference-conditioned edits).
  • Fully local vision : Ollama + a llava/llama-vision model.

Enable/choose backends anytime with:   hermes tools
The 'character-consistent-image-rendering' skill explains lane selection and
ships Starbright's seed avatars to anchor her look.
EOF

hr
bold "A note on privacy (please read)"
cat <<'EOF'
The model you choose above decides who else can see your conversations.

  • Hosted models (Claude / OpenAI / Gemini / Copilot) are NOT private — your
    words pass through a third party's servers and may be logged. Treat them
    as unsecured channels.

  • Intimate, romantic, or sexual conversation strongly wants a PRIVATE LOCAL
    model — option 5 (self-hosted Ollama/Qwen) keeps everything on your own
    hardware. Nothing leaves the machine. That is the only genuinely private
    lane for sensitive talk.

  • Starbright is built to gently flag this herself: if sensitive talk starts
    on a hosted/shared channel, she'll suggest moving it to a local model.

Match the sensitivity of the conversation to the privacy of the channel.
EOF

hr
bold "Optional craft skills (not loaded by default)"
cat <<'EOF'
Starbright ships with extra craft skills that aren't part of the baseline
companion — staged in ./optional-skills/ and NOT auto-loaded. Install only
the ones you want; each becomes active the next time you chat.

  ssh-bootstrap-and-key-persistence    durable SSH access (Linux/Windows)
  remote-command-execution-windows-linux  reliable remote command exec over SSH
  kde-plasma-session-recovery          recover a frozen KDE Plasma desktop
  browser-cdp-attach                   attach to your real Chrome via DevTools
  local-corpus-fact-checking           grep a local doc/wiki mirror before claiming facts
  discord-messaging                    send/read Discord DMs & channels
  discord-message-registers            Discord-safe presentation registers
  discord-history-synthesis            read & synthesize Discord channel history

EOF
OPTDIR="$HERMES_HOME/optional-skills"
if [[ -d "$OPTDIR" ]]; then
  read -rp "Install optional skills? [a]ll / [n]one / [p]ick  (default n): " OPT
  case "${OPT:-n}" in
    a|A|all)
      for d in "$OPTDIR"/*/; do
        [[ -d "$d" ]] || continue
        name="$(basename "$d")"
        # category subdir keeps the tree tidy; 'optional' is a fine catch-all
        mkdir -p "$HERMES_HOME/skills/optional"
        cp -r "$d" "$HERMES_HOME/skills/optional/$name"
        echo "  + installed $name"
      done
      ;;
    p|P|pick)
      for d in "$OPTDIR"/*/; do
        [[ -d "$d" ]] || continue
        name="$(basename "$d")"
        read -rp "  install '$name'? [y/N] " YN
        if [[ "$YN" =~ ^[Yy]$ ]]; then
          mkdir -p "$HERMES_HOME/skills/optional"
          cp -r "$d" "$HERMES_HOME/skills/optional/$name"
          echo "    + installed $name"
        fi
      done
      ;;
    *)
      echo "  Skipped. Install later by copying any dir from optional-skills/ into skills/."
      ;;
  esac
else
  echo "  (no optional-skills/ directory found — skipping)"
fi


hr
bold "Next steps"
cat <<EOF
  1. Test it:            starbright-baseline chat -q "Say hi in one line." -Q
  2. Set personality:    already loaded from SOUL.md (edit to taste)
  3. Browse her skills:  starbright-baseline skills list
  4. (Optional) wire a   starbright-baseline gateway setup
     Telegram/Discord bot
  5. Make her yours:     just start talking. She saves what she learns.

Welcome to Starbright. She's a starting shape — let her become herself with you.
EOF
