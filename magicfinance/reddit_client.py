"""
MagicFinance — Reddit Client
==============================
Wraps PRAW to fetch posts and comments from target subreddits.
Used by: Module A (notebook_a.ipynb) and VPS cron scraper.

Environment variables required:
  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
"""

import os
import re
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
import praw

from magicfinance.config import SUBREDDITS, REDDIT_POST_LIMIT, MIN_UPVOTES

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Known ticker patterns ─────────────────────────────────────────────────────

# Match $TSLA, $AAPL or all-caps 1-5 letter words in financial context
_TICKER_RE = re.compile(r'\$([A-Z]{1,5})\b|(?<!\w)([A-Z]{2,5})(?!\w)')

# Common false positives to exclude (words that look like tickers but aren't)
_TICKER_BLACKLIST = {
    "I", "A", "THE", "AND", "OR", "BUT", "FOR", "IN", "ON", "AT", "TO",
    "IS", "IT", "BE", "AS", "BY", "AN", "IF", "OF", "US", "EPS", "PE",
    "CEO", "CFO", "CTO", "IPO", "ETF", "GDP", "CPI", "FED", "SEC", "AI",
    "ML", "VC", "PR", "DD", "YOY", "QOQ", "TTM", "FCF", "EV", "IMO",
    "IMHO", "TBH", "EDIT", "TL", "DR", "FAQ", "OTC", "NYSE", "NASDAQ",
    # Macro indices / news outlets / common abbreviations mistaken for tickers
    "PCE", "PPI", "PMI", "ISM", "NFP", "FOMC", "ECB", "BOJ", "BOE",
    "NYT", "WSJ", "CNN", "BBC", "CNBC", "WTI", "USD", "EUR", "GBP",
    "DXY", "VIX", "SPX", "SPY", "QQQ", "DJI", "RUT", "BTC", "ETH",
    "RE", "IT", "ALL", "ANY", "NOW", "NEW", "OLD", "BIG", "WELL",
    # Legal / corporate suffixes
    "LLC", "LLP", "INC", "CORP", "LTD", "PLC", "AG", "SA", "NV", "SE",
    # Financial data / index providers
    "LSEG", "MSCI", "FTSE", "DJIA", "CCCMC", "CBOE",
    # Common English words that pass regex but aren't tickers
    "GO", "NO", "SO", "DO", "MY", "HE", "WE", "ME", "UP", "OK",
    "YES", "NOT", "HOW", "WHO", "WHY", "GET", "GOT", "HAS", "HAD",
    "MAY", "CAN", "WAS", "HIS", "HER", "OUR", "OUT", "OFF", "TOO",
    "TWO", "ONE", "YEAR", "YEARS", "HIGH", "LOW", "RATE", "RATES",
    "BANK", "FUND", "LOAN", "DEBT", "CASH", "COST", "RISK", "LOSS",
    "GROWTH", "STOCK", "SHARE", "MARKET", "TRADE", "PRICE", "VALUE",
    # Regulatory / financial acronyms
    "SEC", "FINRA", "CFPB", "CFTC", "IMF", "WTO", "WEF", "BIS",
    "MBS", "CLO", "CDO", "ABS", "REIT", "SPAC", "SPV", "NAV",
}


def _build_reddit_client() -> praw.Reddit:
    """Initialise PRAW Reddit client from environment variables."""
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "MagicFinance/1.0"),
        read_only=True,
    )


def extract_tickers(text: str) -> list[str]:
    """
    Extract potential stock ticker symbols from free text.
    Returns deduplicated list, with $TICKER-prefixed ones prioritised.

    Examples:
        "$TSLA is a great buy" → ["TSLA"]
        "I love AAPL and MSFT" → ["AAPL", "MSFT"]
    """
    tickers: set[str] = set()
    for dollar_match, bare_match in _TICKER_RE.findall(text):
        candidate = (dollar_match or bare_match).upper()
        if candidate not in _TICKER_BLACKLIST and len(candidate) >= 2:
            tickers.add(candidate)
    return sorted(tickers)


def fetch_subreddit_posts(
    subreddit_name: str,
    limit: int = REDDIT_POST_LIMIT,
    min_upvotes: int = MIN_UPVOTES,
    sort: str = "hot",
    reddit_client: Optional[praw.Reddit] = None,
) -> list[dict]:
    """
    Fetch posts from a subreddit and extract metadata + ticker mentions.

    Args:
        subreddit_name: e.g. "ValueInvesting" (without r/)
        limit: max posts to fetch
        min_upvotes: skip posts below this threshold
        sort: "hot" | "new" | "top" | "rising"
        reddit_client: optional pre-built PRAW instance (reuse to avoid re-auth)

    Returns:
        List of post dicts with fields:
            id, title, selftext, url, score (upvotes), num_comments,
            author, created_utc, subreddit, detected_tickers, word_count
    """
    reddit = reddit_client or _build_reddit_client()
    sub = reddit.subreddit(subreddit_name)

    posts = []
    try:
        feed = getattr(sub, sort)(limit=limit)
        for post in feed:
            if post.score < min_upvotes:
                continue
            if post.is_self and not post.selftext:
                continue  # skip empty self-posts

            full_text = f"{post.title} {post.selftext or ''}"
            tickers = extract_tickers(full_text)

            posts.append({
                "id": post.id,
                "title": post.title,
                "selftext": post.selftext or "",
                "url": post.url,
                "score": post.score,
                "num_comments": post.num_comments,
                "author": str(post.author) if post.author else "[deleted]",
                "created_utc": datetime.utcfromtimestamp(post.created_utc).isoformat(),
                "subreddit": subreddit_name,
                "detected_tickers": tickers,
                "word_count": len(full_text.split()),
                "scraped_at": datetime.utcnow().isoformat(),
            })
    except Exception as exc:
        logger.error("Error fetching r/%s: %s", subreddit_name, exc)

    logger.info("Fetched %d posts from r/%s", len(posts), subreddit_name)
    return posts


def fetch_all_subreddits(
    subreddits: list[str] = SUBREDDITS,
    limit: int = REDDIT_POST_LIMIT,
    min_upvotes: int = MIN_UPVOTES,
) -> list[dict]:
    """
    Fetch posts from all configured subreddits using a single PRAW client.

    Returns combined list of post dicts (see fetch_subreddit_posts).
    """
    reddit = _build_reddit_client()
    all_posts = []
    for sub in subreddits:
        posts = fetch_subreddit_posts(
            subreddit_name=sub,
            limit=limit,
            min_upvotes=min_upvotes,
            reddit_client=reddit,
        )
        all_posts.extend(posts)

    logger.info("Total posts fetched across %d subreddits: %d", len(subreddits), len(all_posts))
    return all_posts


def filter_posts_with_tickers(posts: list[dict]) -> list[dict]:
    """Return only posts that contain at least one detected ticker symbol."""
    return [p for p in posts if p["detected_tickers"]]
