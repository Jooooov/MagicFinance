"""
MagicFinance — Module F: Blood in the Streets Scanner
======================================================
"When there's blood in the streets, buy. Even if the blood is yours."
                                                    — Baron Rothschild

This module:
1. Detects whether the market is in fear/panic mode (VIX, S&P drawdown)
2. Scans scored tickers for macro-driven selloffs with intact fundamentals
3. Ranks opportunities by blood_opportunity_score
4. Generates LLM buy thesis + price target for each opportunity
5. Stores predictions in Qdrant with resolution_date for accuracy tracking
6. Auto-resolves expired predictions and computes hit/miss outcomes
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─── Sector → geopolitical sensitivity map ─────────────────────────────────────
# Used as LLM context anchor to ground geo reasoning

SECTOR_GEO_SENSITIVITY = {
    "Defense":               "STRONG TAILWIND from military conflict, NATO spending, sanctions",
    "Energy":                "TAILWIND from Middle East tension, OPEC cuts, supply disruption",
    "Gold/Precious Metals":  "STRONG TAILWIND from uncertainty, dollar weakness, safe-haven flows",
    "Utilities":             "TAILWIND in risk-off — defensive, regulated revenues",
    "Agriculture":           "TAILWIND from food security concerns, Ukraine war, trade disruptions",
    "Semiconductors":        "HEADWIND from China/Taiwan tension, US export controls",
    "Consumer Discretionary":"HEADWIND in risk-off — first to be cut",
    "Technology":            "MIXED — growth names hurt by rate fears; defensive tech (cloud, security) resilient",
    "Financials":            "HEADWIND from credit risk in crisis; TAILWIND if rates stay high",
    "Healthcare":            "DEFENSIVE — sector-neutral to most geopolitical events",
    "Real Estate":           "HEADWIND from rate hikes; TAILWIND if flight to hard assets",
    "Industrials":           "MIXED — defense/infra beneficiary; trade-exposed names hurt",
    "Materials":             "TAILWIND from commodity supply shock; HEADWIND from demand collapse",
    "Communication Services":"DEFENSIVE in mild selloffs; HEADWIND in severe crisis (ad spend falls)",
}


# ─── Opportunity scoring ───────────────────────────────────────────────────────

def blood_opportunity_score(
    thesis_score: float,
    confidence_level: float,
    drawdown_30d: float,       # negative float, e.g. -0.12 for -12%
    geo_externality: float,    # 0.0 = company problem, 1.0 = pure macro fear
) -> float:
    """
    Composite score: higher = better buy opportunity in a blood market.

    Components:
      thesis_score     × 0.35  — fundamentals intact?
      drawdown_factor  × 0.30  — deeper drop = more upside potential
      confidence_level × 0.20  — signal quality from Module A
      geo_externality  × 0.15  — is the drop external (macro) rather than company-specific?
    """
    drawdown_factor = min(abs(drawdown_30d) / 0.20, 1.0)   # -20%+ → 1.0
    score = (
        thesis_score     * 0.35
        + drawdown_factor  * 0.30
        + confidence_level * 0.20
        + geo_externality  * 0.15
    )
    return round(min(score, 1.0), 3)


# ─── LLM opportunity explainer ─────────────────────────────────────────────────

_SYSTEM_BLOOD = (
    "You are a contrarian investment analyst specialising in crisis opportunities. "
    "You follow the Rothschild principle: buy when there is blood in the streets. "
    "Your job is to identify whether a selloff is caused by macro fear (temporary) "
    "or real fundamental deterioration (avoid). "
    "Always respond with valid JSON only — no markdown, no commentary."
)

_PROMPT_BLOOD = """Analyse this stock as a contrarian buy opportunity during a market panic.

TICKER: {ticker}
SECTOR: {sector}
SECTOR GEO SENSITIVITY: {sector_geo}
CURRENT DRAWDOWN (30d): {drawdown:+.1%}
THESIS SCORE (from Reddit analysis): {thesis:.2f}
CONFIDENCE LEVEL: {confidence:.2f}

CURRENT MACRO HEADLINES:
{headlines}

CURRENT FEAR INDICATORS:
{fear_indicators}

Determine:
1. Is this drawdown driven by EXTERNAL macro/geopolitical fear, or by COMPANY-SPECIFIC problems?
2. If external: what is the recovery thesis and realistic target return?
3. What is the prediction window (days)?

Return ONLY valid JSON:
{{"geo_externality":0.0,"red_market_verdict":"BUY_DIP","entry_rationale":"2 sentence buy thesis","predicted_return_pct":0.0,"prediction_window_days":30,"risk_caveat":"1 sentence main risk"}}

Rules:
- geo_externality: 0.0=company has real problems, 1.0=pure macro selloff
- red_market_verdict: "BUY_DIP" if geo_externality > 0.6 AND thesis > 0.5, else "WAIT"
- predicted_return_pct: realistic recovery % (not wishful — be calibrated)
- prediction_window_days: 14, 30, or 60"""


def explain_opportunity(
    ticker: str,
    sector: str,
    drawdown: float,
    thesis: float,
    confidence: float,
    headlines: str,
    fear_indicators: dict,
) -> dict:
    """
    Ask Qwen 4B whether this is a macro-driven selloff worth buying.
    Returns dict with geo_externality, red_market_verdict, entry_rationale,
    predicted_return_pct, prediction_window_days, risk_caveat.
    """
    from magicfinance.llm_client import _generate, MODEL_4B_PATH, _extract_json

    sector_geo = SECTOR_GEO_SENSITIVITY.get(sector, "No specific geo sensitivity mapped for this sector")

    fear_str = (
        f"VIX={fear_indicators.get('vix', 'N/A'):.1f}"
        if fear_indicators.get("vix") else ""
    )
    if fear_indicators.get("spy_30d_pct") is not None:
        fear_str += f"  SPY {fear_indicators['spy_30d_pct']:+.1%} (30d)"
    if fear_indicators.get("gold_30d_pct") is not None:
        fear_str += f"  Gold {fear_indicators['gold_30d_pct']:+.1%} (30d)"

    prompt = _PROMPT_BLOOD.format(
        ticker=ticker,
        sector=sector,
        sector_geo=sector_geo,
        drawdown=drawdown,
        thesis=thesis,
        confidence=confidence,
        headlines=headlines[:1500],
        fear_indicators=fear_str or "unavailable",
    )

    try:
        raw = _generate(MODEL_4B_PATH, prompt, system=_SYSTEM_BLOOD, max_tokens=300, temperature=0.3)
        return _extract_json(raw)
    except Exception as exc:
        logger.warning("LLM blood analysis failed for %s: %s", ticker, exc)
        # Rule-based fallback
        geo_ext = 0.6 if thesis > 0.5 else 0.3
        return {
            "geo_externality": geo_ext,
            "red_market_verdict": "BUY_DIP" if geo_ext > 0.6 else "WAIT",
            "entry_rationale": f"Rule-based: {ticker} down {drawdown:+.1%} with thesis score {thesis:.2f}.",
            "predicted_return_pct": abs(drawdown) * 0.6,
            "prediction_window_days": 30,
            "risk_caveat": "Insufficient LLM analysis — use with caution.",
        }


# ─── Opportunity scanner ───────────────────────────────────────────────────────

def scan_opportunities(
    signals: list[dict],
    prices_30d: dict[str, float],   # ticker → 30d-ago price
    prices_now: dict[str, float],   # ticker → current price
    headlines: str,
    fear_indicators: dict,
    min_drawdown: float = 0.04,     # minimum 4% drop to qualify
    min_thesis: float = 0.45,
) -> list[dict]:
    """
    Filter and rank tickers as buy opportunities.

    Returns list of opportunity dicts, sorted by blood_opportunity_score desc.
    Each dict includes all signal fields + geo analysis + score.
    """
    # Deduplicate signals by ticker (keep highest confidence per ticker)
    by_ticker: dict[str, dict] = {}
    for s in signals:
        t = s.get("ticker", "")
        if not t:
            continue
        if t not in by_ticker or s.get("confidence_level", 0) > by_ticker[t].get("confidence_level", 0):
            by_ticker[t] = s

    opportunities = []
    for ticker, sig in by_ticker.items():
        thesis = sig.get("thesis_score", 0.0)
        conf = sig.get("confidence_level", 0.0)

        # Need price data
        p_now = prices_now.get(ticker)
        p_old = prices_30d.get(ticker)
        if not p_now or not p_old or p_old == 0:
            continue

        drawdown = (p_now - p_old) / p_old
        if drawdown > -min_drawdown:
            continue  # not down enough
        if thesis < min_thesis:
            continue  # thesis too weak

        # Get sector from yfinance (best-effort)
        sector = _get_sector(ticker)

        # LLM analysis
        analysis = explain_opportunity(
            ticker=ticker,
            sector=sector,
            drawdown=drawdown,
            thesis=thesis,
            confidence=conf,
            headlines=headlines,
            fear_indicators=fear_indicators,
        )

        score = blood_opportunity_score(
            thesis_score=thesis,
            confidence_level=conf,
            drawdown_30d=drawdown,
            geo_externality=analysis.get("geo_externality", 0.5),
        )

        opportunities.append({
            **sig,
            "drawdown_30d": round(drawdown, 4),
            "current_price": round(p_now, 2),
            "price_30d_ago": round(p_old, 2),
            "sector": sector,
            "blood_opportunity_score": score,
            "geo_externality": analysis.get("geo_externality", 0.5),
            "red_market_verdict": analysis.get("red_market_verdict", "WAIT"),
            "entry_rationale": analysis.get("entry_rationale", ""),
            "predicted_return_pct": analysis.get("predicted_return_pct", 0.0),
            "prediction_window_days": analysis.get("prediction_window_days", 30),
            "risk_caveat": analysis.get("risk_caveat", ""),
            "scanned_at": datetime.utcnow().isoformat(),
        })

    opportunities.sort(key=lambda x: x["blood_opportunity_score"], reverse=True)
    return opportunities


def _get_sector(ticker: str) -> str:
    """Return yfinance sector string, or 'Unknown'."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        # fast_info doesn't have sector — fall back to full info with timeout guard
        full = yf.Ticker(ticker).info
        return full.get("sector", "Unknown")
    except Exception:
        return "Unknown"


# ─── Prediction lifecycle ──────────────────────────────────────────────────────

def build_prediction(opportunity: dict) -> dict:
    """
    Create a storable prediction record from a scanned opportunity.
    """
    prediction_date = datetime.utcnow().isoformat()
    window = int(opportunity.get("prediction_window_days", 30))
    resolution_date = (datetime.utcnow() + timedelta(days=window)).date().isoformat()

    return {
        "ticker": opportunity["ticker"],
        "entry_price": opportunity.get("current_price", 0.0),
        "predicted_return_pct": opportunity.get("predicted_return_pct", 0.0),
        "predicted_target_price": round(
            opportunity.get("current_price", 0.0)
            * (1 + opportunity.get("predicted_return_pct", 0.0) / 100),
            2,
        ),
        "prediction_window_days": window,
        "prediction_date": prediction_date,
        "resolution_date": resolution_date,
        "blood_opportunity_score": opportunity.get("blood_opportunity_score", 0.0),
        "entry_rationale": opportunity.get("entry_rationale", ""),
        "risk_caveat": opportunity.get("risk_caveat", ""),
        "geo_externality": opportunity.get("geo_externality", 0.5),
        "sector": opportunity.get("sector", "Unknown"),
        "drawdown_30d": opportunity.get("drawdown_30d", 0.0),
        "resolved": False,
        "actual_price": None,
        "actual_return_pct": None,
        "outcome": None,   # HIT | PARTIAL | MISS
    }


def resolve_prediction(pred: dict, current_price: float) -> dict:
    """
    Compute outcome for an expired prediction given current price.

    HIT     = actual_return >= 50% of predicted_return (model was directionally right)
    PARTIAL = actual_return > 0 but < 50% of predicted
    MISS    = actual_return <= 0
    """
    entry = pred.get("entry_price", 0)
    if not entry or entry == 0:
        return {**pred, "resolved": True, "outcome": "MISS", "actual_price": current_price}

    actual_return = (current_price - entry) / entry * 100
    predicted = pred.get("predicted_return_pct", 0)

    if predicted > 0:
        if actual_return >= predicted * 0.5:
            outcome = "HIT"
        elif actual_return > 0:
            outcome = "PARTIAL"
        else:
            outcome = "MISS"
    else:
        outcome = "MISS"

    return {
        **pred,
        "resolved": True,
        "actual_price": round(current_price, 2),
        "actual_return_pct": round(actual_return, 2),
        "outcome": outcome,
        "resolved_at": datetime.utcnow().isoformat(),
    }


def auto_resolve_predictions() -> list[dict]:
    """
    Check all pending predictions in Qdrant. Resolve those past their resolution_date.
    Returns list of newly resolved predictions.
    """
    from magicfinance.qdrant_client import get_pending_predictions, update_prediction_outcome

    try:
        import yfinance as yf
    except ImportError:
        return []

    pending = get_pending_predictions()
    today = datetime.utcnow().date().isoformat()
    resolved = []

    for pred in pending:
        if pred.get("resolution_date", "9999") > today:
            continue  # not due yet

        ticker = pred.get("ticker", "")
        if not ticker:
            continue

        try:
            price_data = yf.download(ticker, period="2d", progress=False, auto_adjust=True)["Close"]
            if price_data.empty:
                continue
            current_price = float(price_data.iloc[-1])
        except Exception:
            continue

        updated = resolve_prediction(pred, current_price)
        update_prediction_outcome(pred.get("_point_id"), updated)
        resolved.append(updated)
        logger.info("Resolved blood prediction: %s → %s (actual %+.1f%%)",
                    ticker, updated["outcome"], updated.get("actual_return_pct", 0))

    return resolved


# ─── Accuracy statistics ───────────────────────────────────────────────────────

def get_blood_accuracy_stats(predictions: list[dict]) -> dict:
    """
    Compute accuracy stats from a list of prediction dicts.

    Returns: total, resolved, hit_rate, avg_predicted, avg_actual,
             calibration_bias, hit_count, miss_count, partial_count
    """
    resolved = [p for p in predictions if p.get("resolved") and p.get("outcome")]
    hits    = [p for p in resolved if p["outcome"] == "HIT"]
    partial = [p for p in resolved if p["outcome"] == "PARTIAL"]
    misses  = [p for p in resolved if p["outcome"] == "MISS"]

    hit_rate = len(hits) / len(resolved) if resolved else 0.0

    predicted_returns = [p["predicted_return_pct"] for p in resolved if p.get("predicted_return_pct")]
    actual_returns    = [p["actual_return_pct"]    for p in resolved if p.get("actual_return_pct") is not None]

    avg_predicted = sum(predicted_returns) / len(predicted_returns) if predicted_returns else 0.0
    avg_actual    = sum(actual_returns)    / len(actual_returns)    if actual_returns    else 0.0
    calibration_bias = avg_predicted - avg_actual  # positive = model overestimates

    return {
        "total":            len(predictions),
        "resolved":         len(resolved),
        "pending":          len(predictions) - len(resolved),
        "hit_count":        len(hits),
        "partial_count":    len(partial),
        "miss_count":       len(misses),
        "hit_rate":         round(hit_rate, 3),
        "avg_predicted_pct": round(avg_predicted, 2),
        "avg_actual_pct":   round(avg_actual, 2),
        "calibration_bias": round(calibration_bias, 2),
    }
