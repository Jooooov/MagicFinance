"""
MagicFinance — Geo Client (Module F)
=====================================
Fetches macro headlines and market fear indicators.
No API keys required — uses RSS feeds and yfinance.
"""

import logging
import requests
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# RSS feeds with financial/geopolitical news (no key needed)
_RSS_FEEDS = [
    ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
    ("BBC",     "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Reuters Geopolitics", "https://feeds.reuters.com/reuters/worldNews"),
]

# yfinance symbols for fear indicators
_FEAR_SYMBOLS = {
    "vix":   "^VIX",
    "spy":   "SPY",
    "dxy":   "DX-Y.NYB",   # US Dollar Index
    "oil":   "CL=F",       # WTI Crude
    "gold":  "GC=F",       # Gold futures
    "bonds": "^TNX",       # 10yr Treasury yield
}


def get_market_fear_indicators() -> dict:
    """
    Fetch real-time fear/macro indicators via yfinance.

    Returns dict with: vix, spy_5d_pct, spy_30d_pct, dxy_30d_pct,
    oil_30d_pct, gold_30d_pct, bonds_yield, fetched_at
    """
    try:
        import yfinance as yf
        import pandas as pd

        tickers = list(_FEAR_SYMBOLS.values())
        data = yf.download(tickers, period="35d", progress=False, auto_adjust=True)["Close"]

        def pct(symbol, days):
            col = symbol
            if col not in data.columns:
                return None
            series = data[col].dropna()
            if len(series) < days + 1:
                return None
            return float((series.iloc[-1] - series.iloc[-days]) / series.iloc[-days])

        vix_val = None
        vix_col = _FEAR_SYMBOLS["vix"]
        if vix_col in data.columns:
            s = data[vix_col].dropna()
            if len(s):
                vix_val = float(s.iloc[-1])

        return {
            "vix":          vix_val,
            "spy_5d_pct":   pct(_FEAR_SYMBOLS["spy"], 5),
            "spy_30d_pct":  pct(_FEAR_SYMBOLS["spy"], 30),
            "dxy_30d_pct":  pct(_FEAR_SYMBOLS["dxy"], 30),
            "oil_30d_pct":  pct(_FEAR_SYMBOLS["oil"], 30),
            "gold_30d_pct": pct(_FEAR_SYMBOLS["gold"], 30),
            "bonds_yield":  float(data[_FEAR_SYMBOLS["bonds"]].dropna().iloc[-1])
                            if _FEAR_SYMBOLS["bonds"] in data.columns else None,
            "fetched_at":   datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.warning("Fear indicator fetch failed: %s", exc)
        return {"vix": None, "spy_30d_pct": None, "fetched_at": datetime.utcnow().isoformat()}


def is_blood_mode(indicators: dict | None = None) -> tuple[bool, str, dict]:
    """
    Determine if market is in 'blood in the streets' mode.

    Conditions (any one triggers):
      - VIX > 25
      - S&P500 down > 3% in 5 days
      - S&P500 down > 7% in 30 days

    Returns: (is_blood: bool, reason: str, indicators: dict)
    """
    ind = indicators or get_market_fear_indicators()
    reasons = []

    vix = ind.get("vix")
    if vix and vix > 30:
        reasons.append(f"VIX={vix:.1f} (FEAR)")
    elif vix and vix > 25:
        reasons.append(f"VIX={vix:.1f} (elevated)")

    spy5 = ind.get("spy_5d_pct")
    if spy5 and spy5 < -0.03:
        reasons.append(f"SPY {spy5:+.1%} (5d)")

    spy30 = ind.get("spy_30d_pct")
    if spy30 and spy30 < -0.07:
        reasons.append(f"SPY {spy30:+.1%} (30d)")

    blood = len(reasons) > 0
    reason_str = "  ·  ".join(reasons) if reasons else (
        f"VIX={vix:.1f}" if vix else "market data unavailable"
    )
    return blood, reason_str, ind


def fetch_macro_headlines(max_items: int = 8) -> str:
    """
    Fetch recent macro/geopolitical headlines from Reuters and BBC RSS feeds.
    Returns a plain-text summary string suitable for LLM context.
    No API key required.
    """
    headlines = []
    for source, url in _RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": "MagicFinance/1.0"})
            resp.raise_for_status()
            # Parse <title> tags — works without xml parser dependencies
            titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>|<title>(.+?)</title>",
                                resp.text, re.DOTALL)
            for t1, t2 in titles[1:6]:  # skip feed title (first item)
                title = (t1 or t2).strip()
                # Filter out nav/footer items
                if len(title) > 20 and not any(x in title.lower() for x in ["rss", "feed", "copyright"]):
                    headlines.append(f"[{source}] {title}")
        except Exception as exc:
            logger.debug("RSS fetch failed for %s: %s", source, exc)

    if not headlines:
        return "No macro headlines available (RSS feeds unreachable)."

    return "\n".join(headlines[:max_items])
