"""
MagicFinance — Financial Modeling Prep Client (Module C)
=========================================================
Free tier: 250 requests/day — sufficient for 5-10 tickers per run.
Provides earnings call transcripts for deception analysis.

Setup:
  1. Register free at https://financialmodelingprep.com
  2. Add FMP_API_KEY=your_key to .env

Falls back gracefully to SEC EDGAR if key not set.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_API_KEY = os.getenv("FMP_API_KEY", "")


def get_latest_transcript(ticker: str) -> dict:
    """
    Fetch the most recent earnings call transcript for a ticker.

    Returns dict with: ticker, year, quarter, date, content, source, error
    content is capped at 8000 chars.
    Returns error key (non-None) on failure; content will be empty string.
    """
    if not FMP_API_KEY:
        return {
            "ticker": ticker,
            "content": "",
            "error": "FMP_API_KEY not set — add it to .env for earnings transcripts",
        }

    try:
        # Step 1: get list of available transcripts (returns [{year, quarter}])
        resp = requests.get(
            f"{FMP_BASE}/earning_call_transcript/{ticker}",
            params={"apikey": FMP_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        index = resp.json()

        if not index or not isinstance(index, list):
            return {"ticker": ticker, "content": "", "error": "No transcripts available on FMP"}

        latest = index[0]
        year, quarter = latest.get("year"), latest.get("quarter")

        # Step 2: fetch the actual transcript content
        resp2 = requests.get(
            f"{FMP_BASE}/earning_call_transcript/{ticker}",
            params={"year": year, "quarter": quarter, "apikey": FMP_API_KEY},
            timeout=15,
        )
        resp2.raise_for_status()
        transcript_list = resp2.json()

        if not transcript_list or not isinstance(transcript_list, list):
            return {"ticker": ticker, "content": "", "error": "Empty transcript response"}

        entry = transcript_list[0]
        content = entry.get("content", "")

        return {
            "ticker": ticker,
            "year": year,
            "quarter": quarter,
            "date": entry.get("date", ""),
            "content": content[:8000],
            "source": f"FMP Earnings Call Q{quarter} {year}",
            "error": None,
        }

    except Exception as exc:
        logger.warning("FMP transcript fetch failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "content": "", "error": str(exc)}
