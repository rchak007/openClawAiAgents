#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Real Estate Agent Setup — Chuck & Nisha
#  Run on Pi AFTER OpenClaw is already installed
#  bash setup-realestate.sh
# ═══════════════════════════════════════════════════════════

set -e
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; BOLD="\033[1m"; RESET="\033[0m"

echo -e "${BOLD}🏠 Real Estate Agent Setup${RESET}"
echo "──────────────────────────"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1. Create workspace ──────────────────────────────────────
echo -e "\n${YELLOW}[1/5]${RESET} Creating workspace..."
mkdir -p ~/.openclaw/workspace-realestate/skills
echo -e "${GREEN}✓ Workspace created at ~/.openclaw/workspace-realestate${RESET}"

# ── 2. Copy skill ────────────────────────────────────────────
echo -e "\n${YELLOW}[2/5]${RESET} Installing realestate-manager skill..."
cp -r "$SCRIPT_DIR/openclaw-skills/realestate-manager" \
      ~/.openclaw/workspace-realestate/skills/
chmod +x ~/.openclaw/workspace-realestate/skills/realestate-manager/scripts/realestate.py
echo -e "${GREEN}✓ Skill installed${RESET}"

# ── 3. Copy SOUL.md ──────────────────────────────────────────
echo -e "\n${YELLOW}[3/5]${RESET} Installing SOUL.md..."
cp "$SCRIPT_DIR/SOUL-realestate.md" ~/.openclaw/workspace-realestate/SOUL.md
echo -e "${GREEN}✓ SOUL.md installed${RESET}"

# ── 4. Initialize property data ──────────────────────────────
echo -e "\n${YELLOW}[4/5]${RESET} Initializing property data..."
python3 ~/.openclaw/workspace-realestate/skills/realestate-manager/scripts/realestate.py init
echo -e "${GREEN}✓ Properties initialized${RESET}"

# ── 5. Configure emails ──────────────────────────────────────
echo -e "\n${YELLOW}[5/5]${RESET} Email configuration"
echo ""
read -p "  Your email address (Chuck): " CHUCK_EMAIL
read -p "  Partner email (Nisha): " NISHA_EMAIL
read -p "  Gmail address to SEND FROM: " GMAIL_ADDR

python3 ~/.openclaw/workspace-realestate/skills/realestate-manager/scripts/realestate.py config-set chuck_email "$CHUCK_EMAIL"
python3 ~/.openclaw/workspace-realestate/skills/realestate-manager/scripts/realestate.py config-set nisha_email "$NISHA_EMAIL"
python3 ~/.openclaw/workspace-realestate/skills/realestate-manager/scripts/realestate.py config-set gmail_address "$GMAIL_ADDR"

echo ""
echo -e "${GREEN}✓ Emails configured${RESET}"
echo ""
echo "  ⚠️  Gmail App Password setup:"
echo "  1. Go to myaccount.google.com → Security → 2-Step Verification"
echo "  2. Scroll down → App passwords → Create"
echo "  3. Add this to your Pi environment:"
echo ""
echo "     echo 'export GMAIL_APP_PASSWORD=yourpassword' >> ~/.bashrc"
echo "     source ~/.bashrc"
echo ""

# ── 6. Add second agent to openclaw.json ─────────────────────
echo -e "${YELLOW}[6/5]${RESET} Add this agent to OpenClaw config:"
echo ""
echo "  Run: nano ~/.openclaw/openclaw.json"
echo ""
echo "  Add under 'agents':"
cat << 'EOF'
  "list": [
    {
      "id": "main",
      "workspace": "~/.openclaw/workspace"
    },
    {
      "id": "realestate",
      "workspace": "~/.openclaw/workspace-realestate",
      "model": { "primary": "anthropic/claude-sonnet-4-6" }
    }
  ]
EOF
echo ""
echo "  Add under 'channels.telegram' bindings:"
cat << 'EOF'
  "bindings": [
    {
      "agentId": "realestate",
      "match": {
        "channel": "telegram",
        "accountId": "realestate"
      }
    }
  ]
EOF
echo ""
echo "  Add second bot token under 'channels.telegram.accounts':"
cat << 'EOF'
  "accounts": {
    "realestate": {
      "botToken": "YOUR_REALESTATE_BOT_TOKEN_HERE"
    }
  }
EOF

echo ""
echo -e "${BOLD}${GREEN}🏠 Real Estate Agent ready!${RESET}"
echo "──────────────────────────"
echo ""
echo "  Test: python3 ~/.openclaw/workspace-realestate/skills/realestate-manager/scripts/realestate.py deadlines"
echo ""