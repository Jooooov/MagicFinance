#!/usr/bin/env python3
"""
MagicFinance VPS — Simulation Tick Runner
==========================================
Runs one full simulation tick for all 10 AI investors using Ollama.
Designed to be called from cron (hourly or as often as desired).

Environment variables:
  LLM_BACKEND=ollama          (required — forces Ollama backend)
  OLLAMA_MODEL=qwen3.5:0.8b   (model to use, default: qwen3.5:0.8b)
  OLLAMA_BASE_URL=http://localhost:11434  (Ollama server URL)
  QDRANT_HOST=localhost        (Qdrant host — on VPS it's localhost)
  QDRANT_PORT=6333

Cron example (every hour at :05):
  5 * * * * cd /opt/magicfinance && LLM_BACKEND=ollama python3 vps/sim_tick.py >> /var/log/mf_sim.log 2>&1
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Force Ollama backend — this script always runs on VPS
os.environ["LLM_BACKEND"] = "ollama"
os.environ.setdefault("OLLAMA_MODEL", "qwen3.5:0.8b")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

# On VPS Qdrant runs locally
os.environ.setdefault("QDRANT_HOST", "localhost")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sim_tick")


def main() -> int:
    logger.info("=== MagicFinance Simulation Tick START ===")
    logger.info("Model: %s @ %s", os.environ["OLLAMA_MODEL"], os.environ["OLLAMA_BASE_URL"])

    # ── 1. Verify Ollama is running ───────────────────────────────────────────
    from magicfinance.llm_client import check_ollama_server
    ollama_status = check_ollama_server()
    if not ollama_status["ok"]:
        logger.error("Ollama not reachable: %s", ollama_status.get("error"))
        return 1
    if not ollama_status["target_available"]:
        logger.error(
            "Model '%s' not found in Ollama. Available: %s",
            ollama_status["target_model"],
            ollama_status["models"],
        )
        logger.error("Run: ollama pull %s", ollama_status["target_model"])
        return 1
    logger.info("Ollama OK — model '%s' available", ollama_status["target_model"])

    # ── 2. Connect to Qdrant and ensure collections ───────────────────────────
    try:
        from magicfinance.qdrant_client import ensure_collections
        ensure_collections()
    except Exception as exc:
        logger.error("Qdrant connection failed: %s", exc)
        return 1

    # ── 3. Load portfolio (from Qdrant — written by Mac or previous tick) ─────
    from magicfinance.qdrant_client import pull_portfolio, push_portfolio
    from magicfinance.simulation import load_portfolios, save_portfolios
    from magicfinance.investors import INVESTORS

    remote = pull_portfolio()
    if remote:
        save_portfolios(remote)
        logger.info("Portfolio loaded from Qdrant (%d investors)", len(remote))
    else:
        logger.info("No remote portfolio found — starting fresh")

    portfolios = load_portfolios()

    # ── 4. Load signals ───────────────────────────────────────────────────────
    from magicfinance.qdrant_client import get_investable_signals, get_all_signals

    signals = get_investable_signals()
    if not signals:
        signals = get_all_signals(limit=20)
    if not signals:
        logger.warning("No signals in Qdrant — investors will mostly HOLD")
    logger.info("Signals available: %d", len(signals))

    # ── 5. Fetch current prices ───────────────────────────────────────────────
    tickers = list({s.get("ticker") for s in signals if s.get("ticker")})
    for p in portfolios.values():
        tickers.extend(p.get("holdings", {}).keys())
    tickers = list(set(t for t in tickers if t))

    prices: dict = {}
    if tickers:
        try:
            from magicfinance.yfinance_client import fetch_prices
            price_df = fetch_prices(tickers, lookback_days=5)
            if not price_df.empty:
                prices = price_df.iloc[-1].to_dict()
            logger.info("Prices fetched: %d tickers", len(prices))
        except Exception as exc:
            logger.warning("Price fetch failed: %s", exc)

    for t in tickers:
        prices.setdefault(t, 0.0)

    # ── 6. Run simulation tick ────────────────────────────────────────────────
    from magicfinance.simulation import run_tick

    # model_path is ignored when LLM_BACKEND=ollama, but required by signature
    model_path = os.environ["OLLAMA_MODEL"]
    logger.info("Running tick for %d investors...", len(INVESTORS))

    try:
        events, tick_log = run_tick(signals, prices, model_path)
    except Exception as exc:
        logger.error("run_tick failed: %s", exc)
        return 1

    buy_sell = [e for e in events if e.get("action") in ("BUY", "SELL")]
    logger.info("Tick results: %d total decisions, %d BUY/SELL", len(events), len(buy_sell))

    for log_entry in tick_log:
        status = f"{len(log_entry['decisions'])} decision(s)"
        if log_entry.get("error"):
            status += f"  [ERR: {log_entry['error'][:80]}]"
        logger.info("  %-20s %s", log_entry["investor_name"], status)

    # ── 7. Save updated portfolio to Qdrant ──────────────────────────────────
    try:
        updated = load_portfolios()
        push_portfolio(updated)
        logger.info("Portfolio saved to Qdrant")
    except Exception as exc:
        logger.warning("Portfolio push failed: %s", exc)

    # ── 8. Save events to Qdrant sim_events (Mac will pull on next sync) ──────
    if events:
        from magicfinance.qdrant_client import upsert_sim_event
        saved = 0
        for ev in events:
            try:
                upsert_sim_event(ev)
                saved += 1
            except Exception as exc:
                logger.warning("Failed to upsert event: %s", exc)
        logger.info("Saved %d/%d events to Qdrant sim_events", saved, len(events))

    logger.info("=== Tick done at %s ===", datetime.utcnow().isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
