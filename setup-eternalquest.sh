#!/bin/bash
# setup-eternalquest.sh
# Sets up EternalQuest_bot (Paramahansa Yogananda) on this Pi.
# Run AFTER setup-openclaw.sh has already been run.
#
# Usage:
#   export TELEGRAM_ETERNALQUEST_BOT_TOKEN="your_bot_token"
#   export TELEGRAM_USER_ID="your_numeric_user_id"
#   bash setup-eternalquest.sh

set -e

SKILL_NAME="eternalquest"
SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openclaw-skills/${SKILL_NAME}"
SKILL_DST="$HOME/.openclaw/workspace/skills/${SKILL_NAME}"
WORKSPACE="$HOME/.openclaw/workspace"
SOUL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/SOUL-eternalquest.md"

echo "🌟 Setting up EternalQuest_bot (Paramahansa Yogananda)..."

# ── Check prerequisites ───────────────────────────────────────────
if [ -z "$TELEGRAM_ETERNALQUEST_BOT_TOKEN" ]; then
  echo "❌ TELEGRAM_ETERNALQUEST_BOT_TOKEN not set"
  echo "   export TELEGRAM_ETERNALQUEST_BOT_TOKEN=your_token"
  exit 1
fi

if [ -z "$TELEGRAM_USER_ID" ]; then
  echo "⚠️  TELEGRAM_USER_ID not set — bot will accept messages from anyone"
fi

if [ ! -d "$HOME/.openclaw" ]; then
  echo "❌ OpenClaw not installed. Run setup-openclaw.sh first."
  exit 1
fi

# ── Copy skill files ──────────────────────────────────────────────
echo "📂 Installing skill: ${SKILL_NAME}..."
mkdir -p "${SKILL_DST}/scripts"
cp -r "${SKILL_SRC}/." "${SKILL_DST}/"
echo "   ✅ Skill installed to ${SKILL_DST}"

# ── Copy SOUL ─────────────────────────────────────────────────────
echo "📝 Installing SOUL-eternalquest.md..."
cp "${SOUL_SRC}" "${WORKSPACE}/SOUL-eternalquest.md"
echo "   ✅ SOUL installed"

# ── Init data file ────────────────────────────────────────────────
DATAFILE="${WORKSPACE}/eternalquest-todos.json"
if [ ! -f "$DATAFILE" ]; then
  echo '{"nodes": {}}' > "$DATAFILE"
  echo "   ✅ Created ${DATAFILE}"
else
  echo "   ℹ️  Data file already exists: ${DATAFILE}"
fi

# ── Write .env entry ──────────────────────────────────────────────
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
if grep -q "TELEGRAM_ETERNALQUEST_BOT_TOKEN" "$ENV_FILE" 2>/dev/null; then
  echo "   ℹ️  .env already has TELEGRAM_ETERNALQUEST_BOT_TOKEN"
else
  echo "" >> "$ENV_FILE"
  echo "# EternalQuest Bot" >> "$ENV_FILE"
  echo "TELEGRAM_ETERNALQUEST_BOT_TOKEN=${TELEGRAM_ETERNALQUEST_BOT_TOKEN}" >> "$ENV_FILE"
  echo "   ✅ Added token to .env"
fi

echo ""
echo "✅ EternalQuest_bot setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start the bot via OpenClaw with SOUL-eternalquest.md"
echo "  2. Test: /list  /add Health > Fitness > HABIT run 5k weekly"
echo "  3. Data file: ${DATAFILE}"