#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  OpenClaw Pi 5 Setup — Todo Bot Edition
#  Run this on a FRESH Raspberry Pi OS Lite (64-bit)
#  ssh pi@<your-pi-ip> then: bash setup-openclaw.sh
# ═══════════════════════════════════════════════════════════════

set -e
BOLD="\033[1m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; RESET="\033[0m"

echo -e "${BOLD}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   OpenClaw Pi 5 Setup — Todo Edition  ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${RESET}"

# ── Step 1: System Update ────────────────────────────────────────
echo -e "\n${YELLOW}[1/6]${RESET} ${BOLD}System update...${RESET}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl build-essential

# ── Step 2: Set Timezone ─────────────────────────────────────────
echo -e "\n${YELLOW}[2/6]${RESET} ${BOLD}Set timezone${RESET}"
echo "Current timezone: $(timedatectl show --property=Timezone --value)"
read -p "Enter your timezone (e.g. Asia/Kolkata, America/New_York): " TZ_INPUT
sudo timedatectl set-timezone "$TZ_INPUT"
echo -e "${GREEN}✓ Timezone set to $TZ_INPUT${RESET}"

# ── Step 3: Node.js 22 ───────────────────────────────────────────
echo -e "\n${YELLOW}[3/6]${RESET} ${BOLD}Installing Node.js 22 (required by OpenClaw)...${RESET}"
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
echo -e "${GREEN}✓ Node $(node --version) / npm $(npm --version)${RESET}"

# ── Step 4: Swap (important for Pi 5 16GB — skip or keep small) ──
echo -e "\n${YELLOW}[4/6]${RESET} ${BOLD}Swap setup${RESET}"
# Pi 5 16GB has plenty of RAM, but swap on SSD is fine as safety net
if ! swapon --show | grep -q swapfile; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
fi
echo -e "${GREEN}✓ Swap configured${RESET}"

# ── Step 5: Node compile cache (Pi performance tweak) ────────────
echo -e "\n${YELLOW}[5/6]${RESET} ${BOLD}Node compile cache (speeds up OpenClaw CLI on Pi)...${RESET}"
grep -q 'NODE_COMPILE_CACHE' ~/.bashrc || cat >> ~/.bashrc << 'EOF'
export NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
mkdir -p /var/tmp/openclaw-compile-cache
export OPENCLAW_NO_RESPAWN=1
EOF
source ~/.bashrc
echo -e "${GREEN}✓ Cache configured${RESET}"

# ── Step 6: Install OpenClaw ─────────────────────────────────────
echo -e "\n${YELLOW}[6/6]${RESET} ${BOLD}Installing OpenClaw...${RESET}"
echo ""
echo "  This will run the official OpenClaw installer."
echo "  It launches an interactive setup wizard — you'll need:"
echo ""
echo "  📌 Your Anthropic API key  (from console.anthropic.com)"
echo "  📌 Your Telegram Bot Token (from @BotFather)"
echo "  📌 Your Telegram User ID   (from @userinfobot)"
echo ""
read -p "Ready? Press Enter to start the OpenClaw installer..."

curl -fsSL https://openclaw.ai/install.sh | bash

echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  OpenClaw installed! Now:${RESET}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════${RESET}"
echo ""
echo "  NEXT STEPS:"
echo ""
echo "  1. Copy the SOUL.md to your workspace:"
echo "     cp ~/openclaw-todo/SOUL.md ~/.openclaw/workspace/SOUL.md"
echo ""
echo "  2. Install the Todo skill:"
echo "     cp -r ~/openclaw-todo/skill/todo-manager ~/.openclaw/workspace/skills/"
echo ""
echo "  3. Start OpenClaw:"
echo "     openclaw gateway start"
echo ""
echo "  4. Open Telegram and message your bot!"
echo ""
