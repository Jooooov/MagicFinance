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
    COLLECTION_SIM_EVENTS,
    COLLECTION_PORTFOLIOS,
    COLLECTION_BLOOD_PREDICTIONS,
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

    for name in [COLLECTION_REDDIT_SIGNALS, COLLECTION_FORECAST_HISTORY, COLLECTION_RAW_REDDIT, COLLECTION_SIM_EVENTS, COLLECTION_PORTFOLIOS, COLLECTION_BLOOD_PREDICTIONS]:
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


# ─── Invalid ticker cleanup ────────────────────────────────────────────────────

def delete_signals_by_ticker(ticker: str) -> int:
    """Delete all Qdrant points for a given ticker from the signals collection. Returns count deleted."""
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_REDDIT_SIGNALS,
        scroll_filter=Filter(must=[FieldCondition(key="ticker", match=MatchValue(value=ticker))]),
        limit=500,
        with_payload=False,
        with_vectors=False,
    )
    ids = [hit.id for hit in results[0]]
    if ids:
        client.delete(collection_name=COLLECTION_REDDIT_SIGNALS, points_selector=ids)
    return len(ids)


def purge_invalid_ticker_signals() -> dict:
    """
    Delete all signals whose ticker is in the known non-ticker blacklist
    (common English words, abbreviations, media outlets, corporate suffixes, etc.).
    Returns {ticker: count_deleted}.
    """
    from magicfinance.reddit_client import _TICKER_BLACKLIST
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_REDDIT_SIGNALS,
        limit=2000,
        with_payload=True,
        with_vectors=False,
    )
    # Find all points whose ticker is blacklisted or too short
    to_delete: dict[str, list] = {}
    for hit in results[0]:
        t = hit.payload.get("ticker", "")
        if t and (t in _TICKER_BLACKLIST or len(t) < 2):
            to_delete.setdefault(t, []).append(hit.id)

    deleted = {}
    for ticker, ids in to_delete.items():
        client.delete(collection_name=COLLECTION_REDDIT_SIGNALS, points_selector=ids)
        deleted[ticker] = len(ids)
    return deleted


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


# ─── Deception scores (Module C) ──────────────────────────────────────────────

def upsert_deception_score(result: dict) -> None:
    """
    Store a Module C deception analysis result in Qdrant.
    Key: ticker + analyzed_at (one record per analysis run).
    """
    client = get_client()
    key = f"deception:{result['ticker']}:{result.get('analyzed_at', datetime.utcnow().isoformat())}"
    point = PointStruct(
        id=_make_point_id(key),
        vector=_text_to_vector(key),
        payload={**result, "stored_at": datetime.utcnow().isoformat()},
    )
    client.upsert(collection_name=COLLECTION_REDDIT_SIGNALS, points=[point])
    logger.debug("Upserted deception score for %s (risk=%.2f)", result["ticker"], result.get("deception_risk_score", 0))


def get_deception_scores(ticker: str | None = None) -> list[dict]:
    """
    Retrieve Module C deception scores. Filter by ticker if provided.
    Returns most recent score first.
    """
    client = get_client()
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    filters = [FieldCondition(key="deception_risk_score", match=MatchValue(value=None))]
    # We want records that HAVE a deception_risk_score — use scroll + filter in Python
    results = client.scroll(
        collection_name=COLLECTION_REDDIT_SIGNALS,
        limit=500,
        with_payload=True,
        with_vectors=False,
    )
    scores = [
        hit.payload for hit in results[0]
        if hit.payload.get("deception_risk_score") is not None
        and (ticker is None or hit.payload.get("ticker") == ticker)
    ]
    scores.sort(key=lambda x: x.get("analyzed_at", ""), reverse=True)
    return scores


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


def recalibrate_all_signals() -> dict:
    """
    Re-apply the calibrated confidence formula to all stored Reddit signals.
    Updates confidence_level and is_investable in-place via set_payload.
    Returns {"updated": N, "skipped": M}.
    """
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_REDDIT_SIGNALS,
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    updated = 0
    skipped = 0
    for hit in results[0]:
        p = hit.payload
        # Skip deception records (they have deception_risk_score but no thesis_score)
        if p.get("deception_risk_score") is not None and "thesis_score" not in p:
            skipped += 1
            continue
        thesis   = p.get("thesis_score", p.get("thesis_clarity", 0.0))
        spec     = p.get("specificity", 0.0)
        risk_ack = p.get("risk_acknowledgment", 0.0)
        data_q   = p.get("data_quality", 0.0)
        orig     = p.get("original_thinking", 0.0)
        sentiment = abs(p.get("sentiment_score", 0.0))
        conf = round(min(
            thesis * 0.40 + spec * 0.25 + risk_ack * 0.20
            + data_q * 0.10 + orig * 0.05 + sentiment * 0.10,
            1.0
        ), 3)
        is_inv = (
            conf >= 0.60
            and sum(1 for v in [thesis, spec, risk_ack, data_q, orig] if v >= 0.45) >= 3
        )
        client.set_payload(
            collection_name=COLLECTION_REDDIT_SIGNALS,
            payload={"confidence_level": conf, "is_investable": is_inv, "recalibrated_at": datetime.utcnow().isoformat()},
            points=[hit.id],
        )
        updated += 1
    return {"updated": updated, "skipped": skipped}


def mark_post_scored(post_id: str, subreddit: str) -> None:
    """Mark a raw post as scored so it won't be re-processed."""
    client = get_client()
    key = f"reddit:{subreddit}:{post_id}"
    client.set_payload(
        collection_name=COLLECTION_RAW_REDDIT,
        payload={"scored": True, "scored_at": datetime.utcnow().isoformat()},
        points=[_make_point_id(key)],
    )


# ─── Investor simulation events ────────────────────────────────────────────────

def upsert_sim_event(event: dict) -> None:
    """Store an investor simulation decision event in Qdrant."""
    client = get_client()
    key = f"sim:{event['investor_id']}:{event['ticker']}:{event['timestamp']}"
    point = PointStruct(
        id=_make_point_id(key),
        vector=_text_to_vector(key),
        payload=event,
    )
    client.upsert(collection_name=COLLECTION_SIM_EVENTS, points=[point])


def get_sim_events(investor_id: Optional[str] = None, limit: int = 500) -> list[dict]:
    """Retrieve simulation decision events, optionally filtered by investor."""
    client = get_client()
    scroll_filter = None
    if investor_id:
        scroll_filter = Filter(
            must=[FieldCondition(key="investor_id", match=MatchValue(value=investor_id))]
        )
    results = client.scroll(
        collection_name=COLLECTION_SIM_EVENTS,
        scroll_filter=scroll_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [hit.payload for hit in results[0]]


# ─── Shared portfolio state (VPS <-> Mac sync) ────────────────────────────────

_PORTFOLIO_POINT_ID = 1  # Single document — always ID 1


def push_portfolio(portfolios: dict) -> None:
    """Upload portfolio state to Qdrant so VPS tick can read it, and Mac can restore it."""
    client = get_client()
    key = "portfolio_state"
    point = PointStruct(
        id=_PORTFOLIO_POINT_ID,
        vector=_text_to_vector(key),
        payload={"portfolios": portfolios, "updated_at": datetime.utcnow().isoformat()},
    )
    client.upsert(collection_name=COLLECTION_PORTFOLIOS, points=[point])
    logger.info("Portfolio pushed to Qdrant (%d investors)", len(portfolios))


def pull_portfolio() -> Optional[dict]:
    """Download portfolio state from Qdrant. Returns None if not found."""
    client = get_client()
    try:
        existing = {c.name for c in client.get_collections().collections}
        if COLLECTION_PORTFOLIOS not in existing:
            return None
        results = client.retrieve(
            collection_name=COLLECTION_PORTFOLIOS,
            ids=[_PORTFOLIO_POINT_ID],
            with_payload=True,
        )
        if results:
            return results[0].payload.get("portfolios")
    except Exception as exc:
        logger.warning("pull_portfolio failed: %s", exc)
    return None


def pull_and_clear_sim_events(batch_size: int = 2000) -> list[dict]:
    """
    Pull all pending sim_events from Qdrant and delete them.
    Used by Mac sync to drain the VPS event queue into local archive.
    Returns list of event dicts (sorted by timestamp).
    """
    client = get_client()
    try:
        existing = {c.name for c in client.get_collections().collections}
        if COLLECTION_SIM_EVENTS not in existing:
            return []
        results, _ = client.scroll(
            collection_name=COLLECTION_SIM_EVENTS,
            limit=batch_size,
            with_payload=True,
            with_vectors=False,
        )
        events = [hit.payload for hit in results]
        if events:
            ids = [hit.id for hit in results]
            client.delete(
                collection_name=COLLECTION_SIM_EVENTS,
                points_selector=ids,
            )
            logger.info("Pulled and cleared %d sim events from Qdrant", len(events))
        return sorted(events, key=lambda e: e.get("timestamp", ""))
    except Exception as exc:
        logger.warning("pull_and_clear_sim_events failed: %s", exc)
        return []


# ─── Blood predictions (Module F) ─────────────────────────────────────────────

def upsert_blood_prediction(pred: dict) -> int:
    """
    Store a Module F blood opportunity prediction.
    Key: ticker + prediction_date (one prediction per ticker per scan run).
    Returns the Qdrant point ID.
    """
    client = get_client()
    key = f"blood:{pred['ticker']}:{pred.get('prediction_date', datetime.utcnow().isoformat())}"
    point_id = _make_point_id(key)
    point = PointStruct(
        id=point_id,
        vector=_text_to_vector(key),
        payload={**pred, "stored_at": datetime.utcnow().isoformat(), "_point_id": point_id},
    )
    client.upsert(collection_name=COLLECTION_BLOOD_PREDICTIONS, points=[point])
    logger.debug("Upserted blood prediction for %s (score=%.2f)", pred["ticker"], pred.get("blood_opportunity_score", 0))
    return point_id


def get_pending_predictions() -> list[dict]:
    """Return all unresolved blood predictions."""
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_BLOOD_PREDICTIONS,
        scroll_filter=Filter(must=[FieldCondition(key="resolved", match=MatchValue(value=False))]),
        limit=500,
        with_payload=True,
        with_vectors=False,
    )
    return [hit.payload for hit in results[0]]


def get_all_blood_predictions(limit: int = 500) -> list[dict]:
    """Return all blood predictions (resolved and pending), newest first."""
    client = get_client()
    results = client.scroll(
        collection_name=COLLECTION_BLOOD_PREDICTIONS,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    preds = [hit.payload for hit in results[0]]
    preds.sort(key=lambda x: x.get("prediction_date", ""), reverse=True)
    return preds


def update_prediction_outcome(point_id: int, updated_pred: dict) -> None:
    """Overwrite a prediction record with resolved outcome fields."""
    if point_id is None:
        return
    client = get_client()
    client.set_payload(
        collection_name=COLLECTION_BLOOD_PREDICTIONS,
        payload={
            "resolved":          True,
            "actual_price":      updated_pred.get("actual_price"),
            "actual_return_pct": updated_pred.get("actual_return_pct"),
            "outcome":           updated_pred.get("outcome"),
            "resolved_at":       updated_pred.get("resolved_at"),
        },
        points=[point_id],
    )
    logger.debug("Resolved prediction %s → %s", point_id, updated_pred.get("outcome"))
