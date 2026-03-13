#!/bin/bash
# MagicFinance VPS — Simulation Setup
# =====================================
# Installs Ollama, pulls qwen3.5:0.8b, configures hourly cron job.
#
# Run once on the Hostinger VPS:
#   scp -r . root@YOUR_VPS_IP:/opt/magicfinance/
#   ssh root@YOUR_VPS_IP "bash /opt/magicfinance/vps/install_sim.sh"

set -e

PROJECT_DIR="${PROJECT_DIR:-/opt/magicfinance}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3.5:0.8b}"
LOG_FILE="/var/log/mf_sim.log"
CRON_MINUTE="5"  # Run at :05 of every hour

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  MagicFinance VPS Simulation Setup       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Install Ollama ─────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "▸ Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
    echo "✅ Ollama installed"
else
    echo "✅ Ollama already installed: $(ollama --version 2>/dev/null || echo 'version unknown')"
fi

# ── 2. Ensure Ollama service is running ───────────────────────────────────────
if command -v systemctl &>/dev/null; then
    systemctl enable ollama 2>/dev/null || true
    systemctl start ollama  2>/dev/null || true
    sleep 3
    echo "✅ Ollama service running"
else
    # Start manually in background if systemd not available
    ollama serve &>/dev/null &
    sleep 5
    echo "✅ Ollama started in background"
fi

# ── 3. Pull the model ─────────────────────────────────────────────────────────
echo "▸ Pulling $OLLAMA_MODEL (~500MB — please wait)..."
ollama pull "$OLLAMA_MODEL"
echo "✅ Model ready: $OLLAMA_MODEL"

# ── 4. Quick inference test ───────────────────────────────────────────────────
echo "▸ Testing inference..."
TEST_OUTPUT=$(echo '{"test":true}' | ollama run "$OLLAMA_MODEL" 'Reply with valid JSON: {"ok":true}' 2>/dev/null || echo "timeout")
echo "   Response: $TEST_OUTPUT"
echo "✅ Inference test done"

# ── 5. Install Python dependencies ───────────────────────────────────────────
echo "▸ Installing Python dependencies..."
pip3 install -r "$PROJECT_DIR/requirements.txt" --quiet
echo "✅ Python dependencies installed"

# ── 6. Create log file ────────────────────────────────────────────────────────
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"
echo "✅ Log file: $LOG_FILE"

# ── 7. Verify sim_tick runs ───────────────────────────────────────────────────
echo "▸ Running first tick (this may take a few minutes)..."
cd "$PROJECT_DIR"
LLM_BACKEND=ollama OLLAMA_MODEL="$OLLAMA_MODEL" QDRANT_HOST=localhost \
    python3 vps/sim_tick.py 2>&1 | tail -20
echo ""

# ── 8. Set up hourly cron job ─────────────────────────────────────────────────
CRON_CMD="${CRON_MINUTE} * * * * cd ${PROJECT_DIR} && LLM_BACKEND=ollama OLLAMA_MODEL=${OLLAMA_MODEL} QDRANT_HOST=localhost python3 vps/sim_tick.py >> ${LOG_FILE} 2>&1"

# Remove old entry if exists, add new one
(crontab -l 2>/dev/null | grep -v "sim_tick.py"; echo "$CRON_CMD") | crontab -
echo "✅ Cron job set: every hour at :${CRON_MINUTE}"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Setup complete!                         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Monitor:   tail -f $LOG_FILE"
echo "  Run now:   cd $PROJECT_DIR && LLM_BACKEND=ollama python3 vps/sim_tick.py"
echo "  Cron:      crontab -l | grep sim_tick"
echo ""
