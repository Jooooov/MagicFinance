#!/bin/bash
# MagicFinance VPS — Installation Script
# ========================================
# Run this ONCE on the Nanobot VPS to deploy the scraper and cron jobs.
#
# Usage (from your Mac):
#   scp -r vps/ root@76.13.66.197:/opt/magicfinance/
#   ssh root@76.13.66.197 "bash /opt/magicfinance/install_vps.sh"

set -euo pipefail
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

VPS_DIR="/opt/magicfinance"
log "=== MagicFinance VPS Installation ==="

# ─── 1. Create directories ──────────────────────────────────────────────────
mkdir -p "${VPS_DIR}/logs" "${VPS_DIR}/data/raw" "${VPS_DIR}/data/archive"
log "Created directory structure"

# ─── 2. Python venv + dependencies ─────────────────────────────────────────
cd "${VPS_DIR}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    log "Created Python venv"
fi

# Install only the packages needed on VPS (no Qwen/Ollama — that's local)
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet praw python-dotenv qdrant-client requests
log "Installed Python dependencies"

# ─── 3. Copy .env from Nanobot if it exists ─────────────────────────────────
NANOBOT_ENV="/opt/nanobot/config/.env"
if [ -f "${NANOBOT_ENV}" ]; then
    # Append MagicFinance vars to existing Nanobot .env rather than replacing
    log "Found Nanobot .env at ${NANOBOT_ENV}"
    log "Add your REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, NEWSAPI_KEY to ${NANOBOT_ENV}"
else
    log "No Nanobot .env found — create ${VPS_DIR}/.env with required credentials"
fi

# ─── 4. Set up cron jobs ────────────────────────────────────────────────────
log "Installing cron jobs..."

# Backup existing crontab
crontab -l > /tmp/crontab_backup.txt 2>/dev/null || true

# Add MagicFinance cron entries (if not already present)
CRON_SCRAPER="0 6 * * * ${VPS_DIR}/venv/bin/python ${VPS_DIR}/reddit_scraper.py >> ${VPS_DIR}/logs/scraper.log 2>&1"
CRON_CLEANUP="0 3 * * 0 /bin/bash ${VPS_DIR}/cleanup.sh >> ${VPS_DIR}/logs/cleanup.log 2>&1"

(crontab -l 2>/dev/null || true; echo "${CRON_SCRAPER}") | grep -v "^$" | sort -u | crontab -
(crontab -l 2>/dev/null || true; echo "${CRON_CLEANUP}") | grep -v "^$" | sort -u | crontab -

log "Cron jobs installed:"
log "  Scraper: daily at 06:00"
log "  Cleanup: weekly Sundays at 03:00"
crontab -l | grep magicfinance

# ─── 5. Permissions ─────────────────────────────────────────────────────────
chmod +x "${VPS_DIR}/cleanup.sh"
chmod +x "${VPS_DIR}/reddit_scraper.py"
log "Set executable permissions"

# ─── 6. Test run (dry-run) ──────────────────────────────────────────────────
log "Running dry-run test..."
"${VPS_DIR}/venv/bin/python" "${VPS_DIR}/reddit_scraper.py" --dry-run && log "Dry-run: ✅ OK" || log "Dry-run: ❌ check .env credentials"

log "=== Installation complete ==="
log "Next steps:"
log "  1. Add REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET to ${NANOBOT_ENV}"
log "  2. Test live run: ${VPS_DIR}/venv/bin/python ${VPS_DIR}/reddit_scraper.py"
log "  3. Check logs: tail -f ${VPS_DIR}/logs/scraper.log"
