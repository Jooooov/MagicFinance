#!/bin/bash
# MagicFinance VPS — Data Cleanup & Archive Job
# ================================================
# Runs weekly on the Nanobot VPS to prevent disk fill-up:
#   1. Compresses raw Reddit/news data older than N days
#   2. Rsync compressed archives to local Mac via Tailscale
#   3. Deletes originals from VPS after successful rsync
#
# Cron entry (weekly, Sundays at 3am):
#   0 3 * * 0 /bin/bash /opt/magicfinance/cleanup.sh >> /opt/magicfinance/logs/cleanup.log 2>&1
#
# Prerequisites on VPS:
#   - Tailscale connected (tailscale status)
#   - SSH key access to Mac (ssh-copy-id user@MAC_TAILSCALE_IP)
#   - rsync installed (apt install rsync)

set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────────
RETENTION_DAYS=30                          # keep N days of raw data on VPS
DATA_DIR="/opt/magicfinance/data/raw"      # raw data directory on VPS
ARCHIVE_DIR="/opt/magicfinance/data/archive"  # compressed archives on VPS
LOG_FILE="/opt/magicfinance/logs/cleanup.log"

# Mac destination (via Tailscale)
MAC_IP="100.77.221.4"
MAC_USER="joaovicente"
MAC_ARCHIVE_PATH="/Users/joaovicente/Desktop/Apps/MagicFinance/data/archive"

# ─── Logging helpers ────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "=== MagicFinance Cleanup starting ==="
log "Retention: ${RETENTION_DAYS} days | Data dir: ${DATA_DIR}"

# Create directories if they don't exist
mkdir -p "${DATA_DIR}" "${ARCHIVE_DIR}"

# ─── Step 1: Compress files older than RETENTION_DAYS ───────────────────────
log "Step 1: Compressing files older than ${RETENTION_DAYS} days..."

OLD_FILES=$(find "${DATA_DIR}" -type f -name "*.json" -mtime "+${RETENTION_DAYS}" 2>/dev/null | wc -l)
log "Found ${OLD_FILES} files to archive"

if [ "${OLD_FILES}" -gt 0 ]; then
    ARCHIVE_NAME="magicfinance_$(date '+%Y%m%d').tar.gz"
    ARCHIVE_PATH="${ARCHIVE_DIR}/${ARCHIVE_NAME}"

    find "${DATA_DIR}" -type f -name "*.json" -mtime "+${RETENTION_DAYS}" \
        | tar -czf "${ARCHIVE_PATH}" -T - 2>/dev/null

    ARCHIVE_SIZE=$(du -sh "${ARCHIVE_PATH}" | cut -f1)
    log "Compressed ${OLD_FILES} files → ${ARCHIVE_NAME} (${ARCHIVE_SIZE})"
else
    log "No old files to compress"
    ARCHIVE_NAME=""
fi

# ─── Step 2: Rsync archives to local Mac ────────────────────────────────────
if [ -n "${ARCHIVE_NAME:-}" ]; then
    log "Step 2: Syncing archives to Mac at ${MAC_IP}..."

    if rsync -avz --timeout=60 \
        "${ARCHIVE_DIR}/" \
        "${MAC_USER}@${MAC_IP}:${MAC_ARCHIVE_PATH}/" \
        2>&1; then
        log "Rsync to Mac: ✅ success"
        RSYNC_OK=true
    else
        log "Rsync to Mac: ❌ failed (check Tailscale and SSH keys)"
        RSYNC_OK=false
    fi
else
    log "Step 2: No new archives to sync"
    RSYNC_OK=true
fi

# ─── Step 3: Delete originals from VPS after successful rsync ───────────────
if [ "${RSYNC_OK}" = true ] && [ "${OLD_FILES}" -gt 0 ]; then
    log "Step 3: Deleting archived originals from VPS..."
    find "${DATA_DIR}" -type f -name "*.json" -mtime "+${RETENTION_DAYS}" -delete
    DELETED=$(find "${DATA_DIR}" -type f -name "*.json" -mtime "+${RETENTION_DAYS}" 2>/dev/null | wc -l)
    log "Deleted originals: original count was ${OLD_FILES}, remaining: ${DELETED}"
else
    log "Step 3: Skipping delete (rsync failed or nothing to delete)"
fi

# ─── Step 4: Disk usage report ───────────────────────────────────────────────
log "Step 4: Disk usage report"
log "VPS data dir:   $(du -sh ${DATA_DIR} 2>/dev/null || echo 'N/A')"
log "VPS archive:    $(du -sh ${ARCHIVE_DIR} 2>/dev/null || echo 'N/A')"
log "VPS total disk: $(df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\" used)\"}')"

log "=== Cleanup complete ==="
