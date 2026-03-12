#!/usr/bin/env python3
"""
MagicFinance VPS — Reddit Scraper (Cron Job)
=============================================
Runs daily on the Nanobot VPS to fetch fresh Reddit posts and store
raw data in Qdrant. Local Jupyter notebooks then pull from Qdrant
to run Qwen scoring (Module A) without needing Reddit API access locally.

Cron entry (add to VPS root crontab via: ssh root@76.13.66.197 crontab -e):
    0 6 * * * /opt/magicfinance/venv/bin/python /opt/magicfinance/reddit_scraper.py >> /opt/magicfinance/logs/scraper.log 2>&1

Usage:
    python reddit_scraper.py [--dry-run]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ─── Path setup (works both locally and on VPS) ────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("magicfinance.scraper")

from magicfinance.reddit_client import fetch_all_subreddits, filter_posts_with_tickers
from magicfinance import qdrant_client as qc
from magicfinance.config import SUBREDDITS, REDDIT_POST_LIMIT, MIN_UPVOTES


def run_scraper(dry_run: bool = False) -> dict:
    """
    Main scraper run:
    1. Fetch posts from all configured subreddits
    2. Filter posts with ticker mentions
    3. Store raw posts in Qdrant (marked scored=False for Module A pickup)
    4. Return summary stats

    Args:
        dry_run: if True, fetch and log but don't write to Qdrant

    Returns:
        Dict with run statistics.
    """
    run_start = datetime.utcnow()
    logger.info("=== MagicFinance Reddit Scraper starting ===")
    logger.info("Subreddits: %s | Limit: %d | Min upvotes: %d", SUBREDDITS, REDDIT_POST_LIMIT, MIN_UPVOTES)
    if dry_run:
        logger.info("DRY RUN — no data will be written to Qdrant")

    # ─── Step 1: Fetch posts ─────────────────────────────────────────────────
    try:
        all_posts = fetch_all_subreddits(
            subreddits=SUBREDDITS,
            limit=REDDIT_POST_LIMIT,
            min_upvotes=MIN_UPVOTES,
        )
    except Exception as exc:
        logger.error("Fatal: Reddit fetch failed: %s", exc)
        return {"status": "error", "error": str(exc)}

    posts_with_tickers = filter_posts_with_tickers(all_posts)
    logger.info(
        "Posts fetched: %d total, %d with ticker mentions",
        len(all_posts), len(posts_with_tickers),
    )

    # ─── Step 2: Initialise Qdrant collections ───────────────────────────────
    if not dry_run:
        try:
            qc.ensure_collections()
        except Exception as exc:
            logger.error("Qdrant connection failed: %s", exc)
            logger.error("Check: is Tailscale connected? Is Qdrant running on VPS?")
            return {"status": "error", "error": str(exc)}

    # ─── Step 3: Store raw posts ─────────────────────────────────────────────
    stored = 0
    skipped = 0
    errors = 0

    for post in posts_with_tickers:
        # Mark post as unscored so Module A picks it up
        post["scored"] = False
        post["scored_at"] = None

        if dry_run:
            logger.debug("DRY RUN: would store post %s (%s)", post["id"], post["subreddit"])
            stored += 1
            continue

        try:
            qc.upsert_raw_post(post)
            stored += 1
        except Exception as exc:
            logger.warning("Failed to store post %s: %s", post["id"], exc)
            errors += 1

    # ─── Step 4: Log summary ─────────────────────────────────────────────────
    duration = (datetime.utcnow() - run_start).total_seconds()
    summary = {
        "status": "success" if errors == 0 else "partial",
        "dry_run": dry_run,
        "run_at": run_start.isoformat(),
        "duration_seconds": round(duration, 1),
        "posts_fetched": len(all_posts),
        "posts_with_tickers": len(posts_with_tickers),
        "stored": stored,
        "skipped": skipped,
        "errors": errors,
        "subreddits": SUBREDDITS,
    }

    logger.info("=== Scraper complete in %.1fs: %d stored, %d errors ===", duration, stored, errors)
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MagicFinance Reddit Scraper")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't write to Qdrant")
    args = parser.parse_args()

    result = run_scraper(dry_run=args.dry_run)
    sys.exit(0 if result["status"] in ("success", "partial") else 1)
