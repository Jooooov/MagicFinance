"""
MagicFinance — VPS Sync
========================
Synchronises portfolio state and agent events between VPS (Qdrant) and Mac (local files).

Called automatically from MagicFinance.command on every startup.

Flow:
  1. Pull portfolio state from Qdrant → save to data/investor_portfolios.json
  2. Pull pending sim_events from Qdrant → archive to data/sim_events_history.jsonl
  3. Clear pulled events from Qdrant (VPS accumulates, Mac archives)
  4. Push updated portfolio back to Qdrant (so VPS tick reads fresh state)

Signals: already shared via Qdrant — no sync needed.
  Both Mac dashboard and VPS sim_tick read from the same Qdrant collections.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LOCAL_EVENTS_LOG = Path(__file__).parent.parent / "data" / "sim_events_history.jsonl"
SYNC_STATE_FILE  = Path(__file__).parent.parent / "data" / "last_sync.json"


def sync_on_startup() -> dict:
    """
    Full startup sync. Safe to run when Qdrant is offline (skips gracefully).

    Returns summary dict:
        qdrant_ok        (bool)   — Qdrant reachable
        portfolio_updated (bool)  — local portfolio refreshed from VPS
        events_pulled    (int)    — number of new events archived
        last_sync        (str)    — ISO timestamp of this sync
        error            (str)    — error message if something failed
    """
    summary = {
        "qdrant_ok": False,
        "portfolio_updated": False,
        "events_pulled": 0,
        "last_sync": datetime.utcnow().isoformat(),
        "error": None,
    }

    try:
        from magicfinance.qdrant_client import (
            get_client,
            pull_portfolio,
            pull_and_clear_sim_events,
            push_portfolio,
            ensure_collections,
        )
        from magicfinance.simulation import load_portfolios, save_portfolios

        client = get_client()
        client.get_collections()           # connection test
        summary["qdrant_ok"] = True
        ensure_collections()

    except Exception as exc:
        summary["error"] = f"Qdrant offline — {exc}"
        logger.warning("Sync skipped: %s", exc)
        _save_sync_state(summary)
        return summary

    # ── 1. Pull portfolio from Qdrant ─────────────────────────────────────────
    try:
        remote = pull_portfolio()
        if remote:
            save_portfolios(remote)
            summary["portfolio_updated"] = True
            logger.info("Portfolio synced from Qdrant (%d investors)", len(remote))
        else:
            # First time — push local portfolio so VPS can use it
            local = load_portfolios()
            push_portfolio(local)
            logger.info("No remote portfolio found — pushed local state to Qdrant")
    except Exception as exc:
        logger.warning("Portfolio sync failed: %s", exc)

    # ── 2. Pull and clear pending sim_events ──────────────────────────────────
    try:
        events = pull_and_clear_sim_events()
        summary["events_pulled"] = len(events)
        if events:
            _archive_events(events)
            logger.info("Archived %d events locally", len(events))
    except Exception as exc:
        logger.warning("Events sync failed: %s", exc)

    # ── 3. Push current portfolio back to Qdrant (authoritative state) ────────
    try:
        from magicfinance.simulation import load_portfolios
        push_portfolio(load_portfolios())
    except Exception as exc:
        logger.warning("Portfolio push failed: %s", exc)

    _save_sync_state(summary)
    return summary


def _archive_events(events: list[dict]) -> None:
    """Append events to the local JSONL archive file."""
    LOCAL_EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_EVENTS_LOG, "a") as f:
        for event in events:
            f.write(json.dumps(event, default=str) + "\n")


def _save_sync_state(summary: dict) -> None:
    """Persist last sync summary for the dashboard to display."""
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump(summary, f, indent=2, default=str)


def load_last_sync() -> Optional[dict]:
    """Load last sync summary from disk (for sidebar display)."""
    if SYNC_STATE_FILE.exists():
        try:
            with open(SYNC_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def load_events_history(limit: int = 500) -> list[dict]:
    """Load locally archived sim events from JSONL (most recent first)."""
    if not LOCAL_EVENTS_LOG.exists():
        return []
    events = []
    try:
        with open(LOCAL_EVENTS_LOG) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return list(reversed(events))[-limit:]
