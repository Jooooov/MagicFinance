"""
MagicFinance — Qdrant Client
==============================
Helpers for reading and writing MagicFinance signals to the shared Qdrant
instance on the Nanobot VPS (reachable via Tailscale VPN).

Collections used:
  - magicfinance_reddit_signals   : Module A scored signals (persistent across sessions)
  - magicfinance_forecast_history : Module D binary forecasts (for accuracy tracking)
  - magicfinance_raw_reddit       : Raw Reddit posts (rolling window, VPS cron managed)

All vectors use a simple hash-based placeholder; semantic search is on payload fields.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

from magicfinance.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_TIMEOUT,
    COLLECTION_REDDIT_SIGNALS,
    COLLECTION_FORECAST_HISTORY,
    COLLECTION_RAW_REDDIT,
    VECTOR_DIM,
)

logger = logging.getLogger(__name__)


# ─── Client singleton ──────────────────────────────────────────────────────────

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    """Return a cached QdrantClient connected to the Nanobot VPS."""
    global _client
    if _client is None:
        _client = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            timeout=QDRANT_TIMEOUT,
        )
        logger.info("Connected to Qdrant at %s:%s", QDRANT_HOST, QDRANT_PORT)
    return _client


# ─── Collection management ─────────────────────────────────────────────────────

def ensure_collections() -> None:
    """
    Create MagicFinance Qdrant collections if they don't already exist.
    Safe to call multiple times (idempotent).
    """
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}

    for name in [COLLECTION_REDDIT_SIGNALS, COLLECTION_FORECAST_HISTORY, COLLECTION_RAW_REDDIT]:
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection: %s", name)
        else:
            logger.debug("Collection already exists: %s", name)


# ─── Vector helpers ────────────────────────────────────────────────────────────

def _text_to_vector(text: str) -> list[float]:
    """
    Produce a deterministic pseudo-vector from text using SHA-256 hashing.
    Not semantically meaningful — used as a stable ID for exact-match retrieval.
    For semantic search, replace with a real embedding model call.
    """
    digest = hashlib.sha256(text.encode()).digest()
    # Repeat/truncate digest bytes to fill VECTOR_DIM floats (normalised 0–1)
    repeated = (digest * ((VECTOR_DIM // len(digest)) + 1))[:VECTOR_DIM]
    return [b / 255.0 for b in repeated]


def _make_point_id(text: str) -> int:
    """Convert a string key to a stable positive integer Qdrant point ID."""
    return int(hashlib.md5(text.encode()).hexdigest(), 16) % (10**15)


# ─── Reddit signals (Module A) ─────────────────────────────────────────────────

def upsert_reddit_signal(signal: dict) -> None:
    """
    Store a scored Reddit signal in Qdrant.

    Required signal fields:
        ticker, thesis_score, risk_acknowledgment, data_quality,
        specificity, original_thinking, confidence_level, is_investable,
        source_subreddit, signal_timestamp, post_id (optional)
    """
    client = get_client()
    key = f"{signal['ticker']}:{signal.get('post_id', signal['signal_timestamp'])}"
    point = PointStruct(
        id=_make_point_id(key),
        vector=_text_to_vector(key),
        payload={**signal, "stored_at": datetime.utcnow().isoformat()},
    )
    client.upsert(collection_name=COLLECTION_REDDIT_SIGNALS, points=[point])
    logger.debug("Upserted signal for %s (confidence=%.2f)", signal["ticker"], signal["confidence_level"])


def get_signals_by_ticker(ticker: str) -> list[dict]:
    """Retrieve all scored signals for a specific ticker."""
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_REDDIT_SIGNALS,
        scroll_filter=Filter(
            must=[FieldCondition(key="ticker", match=MatchValue(value=ticker))]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    return [hit.payload for hit in results[0]]


def get_investable_signals(min_confidence: float = 0.0) -> list[dict]:
    """
    Retrieve all signals marked is_investable=True, optionally filtered by
    minimum confidence_level.
    """
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_REDDIT_SIGNALS,
        scroll_filter=Filter(
            must=[FieldCondition(key="is_investable", match=MatchValue(value=True))]
        ),
        limit=500,
        with_payload=True,
        with_vectors=False,
    )
    signals = [hit.payload for hit in results[0]]
    if min_confidence > 0:
        signals = [s for s in signals if s.get("confidence_level", 0) >= min_confidence]
    return signals


def get_all_signals(limit: int = 500) -> list[dict]:
    """Retrieve all stored Reddit signals (for notebook analysis)."""
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_REDDIT_SIGNALS,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [hit.payload for hit in results[0]]


# ─── Forecast history (Module D) ───────────────────────────────────────────────

def upsert_forecast(forecast: dict) -> None:
    """
    Store a binary event forecast in Qdrant.

    Required forecast fields:
        event, ticker (or None for macro), forecast_probability,
        model_reasoning, is_macro_event, signal_timestamp
    Optional:
        resolved (bool), actual_outcome (bool) — filled in later for accuracy tracking
    """
    client = get_client()
    key = f"{forecast.get('ticker', 'macro')}:{forecast['event']}:{forecast['signal_timestamp']}"
    point = PointStruct(
        id=_make_point_id(key),
        vector=_text_to_vector(key),
        payload={**forecast, "stored_at": datetime.utcnow().isoformat()},
    )
    client.upsert(collection_name=COLLECTION_FORECAST_HISTORY, points=[point])
    logger.debug("Upserted forecast: %s (p=%.2f)", forecast["event"][:60], forecast["forecast_probability"])


def get_forecast_history(ticker: Optional[str] = None, macro_only: bool = False) -> list[dict]:
    """
    Retrieve forecast history for accuracy backtest.
    Optionally filter by ticker or macro-only events.
    """
    client = get_client()
    filters = []
    if ticker:
        filters.append(FieldCondition(key="ticker", match=MatchValue(value=ticker)))
    if macro_only:
        filters.append(FieldCondition(key="is_macro_event", match=MatchValue(value=True)))

    results = client.scroll(
        collection_name=COLLECTION_FORECAST_HISTORY,
        scroll_filter=Filter(must=filters) if filters else None,
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    return [hit.payload for hit in results[0]]


def get_resolved_forecasts() -> list[dict]:
    """Return only forecasts with a known actual outcome (for accuracy calculation)."""
    forecasts = get_forecast_history()
    return [f for f in forecasts if f.get("resolved", False)]


# ─── Raw Reddit posts (VPS cron managed) ───────────────────────────────────────

def upsert_raw_post(post: dict) -> None:
    """Store a raw Reddit post (used by VPS cron scraper before LLM scoring)."""
    client = get_client()
    key = f"reddit:{post['subreddit']}:{post['id']}"
    point = PointStruct(
        id=_make_point_id(key),
        vector=_text_to_vector(key),
        payload=post,
    )
    client.upsert(collection_name=COLLECTION_RAW_REDDIT, points=[point])


def get_unscored_posts(limit: int = 200) -> list[dict]:
    """
    Retrieve raw posts that haven't been scored yet (scored=False or missing).
    Used by Module A to pick up fresh data from the VPS cron scraper.
    """
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_RAW_REDDIT,
        scroll_filter=Filter(
            must=[FieldCondition(key="scored", match=MatchValue(value=False))]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [hit.payload for hit in results[0]]


def mark_post_scored(post_id: str, subreddit: str) -> None:
    """Mark a raw post as scored so it won't be re-processed."""
    client = get_client()
    key = f"reddit:{subreddit}:{post_id}"
    client.set_payload(
        collection_name=COLLECTION_RAW_REDDIT,
        payload={"scored": True, "scored_at": datetime.utcnow().isoformat()},
        points=[_make_point_id(key)],
    )
