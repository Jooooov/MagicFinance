"""
MagicFinance — Module C: Deception Detector
=============================================
Analyses executive language in SEC 10-Q filings and earnings call transcripts
to detect risk indicators: hedge words, evasive patterns, tone shifts.

Score:
  deception_risk_score: 0.0 (fully transparent) → 1.0 (highly evasive/alarming)

Pipeline:
  1. Try FMP earnings call transcript (requires FMP_API_KEY in .env)
  2. Fallback: SEC EDGAR 10-Q MD&A section (always free, no key needed)
  3. Rule-based hedge-word count → LLM scoring via Qwen3.5 4B
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Hedge word lexicon (from finance linguistics research) ───────────────────

HEDGE_CATEGORIES = {
    "uncertainty": [
        "uncertain", "uncertainty", "unpredictable", "volatile", "volatility",
        "challenging", "challenges", "difficult", "headwinds", "pressures",
        "complex environment", "evolving landscape", "remain cautious",
    ],
    "vagueness": [
        "going forward", "in due course", "at the appropriate time",
        "we will see", "remains to be seen", "too early to say",
        "we are monitoring", "we are evaluating", "we continue to assess",
        "various factors", "a number of factors", "we are exploring",
    ],
    "deflection": [
        "as previously disclosed", "as we have indicated",
        "consistent with guidance", "in line with expectations",
        "macro environment", "industry-wide", "broader market conditions",
        "as previously communicated", "as disclosed",
    ],
    "positive_spin": [
        "excited about", "confident in our", "well-positioned",
        "strong pipeline", "transformational", "record results",
        "best-in-class", "exceptional performance", "accelerating growth",
        "tremendous momentum",
    ],
}


def count_hedge_words(text: str) -> dict:
    """Count occurrences of hedge phrases by category."""
    text_lower = text.lower()
    counts = {cat: sum(text_lower.count(w) for w in words)
              for cat, words in HEDGE_CATEGORIES.items()}
    counts["total"] = sum(counts.values())
    return counts


def _rule_based_score(hedge_counts: dict, word_count: int) -> float:
    """Simple hedge-density score as fallback when LLM fails."""
    # Weight: uncertainty + vagueness + deflection matter; positive_spin is noise
    weighted = (
        hedge_counts.get("uncertainty", 0) * 1.5
        + hedge_counts.get("vagueness", 0) * 2.0
        + hedge_counts.get("deflection", 0) * 1.0
        + hedge_counts.get("positive_spin", 0) * 0.5
    )
    density = weighted / max(word_count / 100, 1)  # per 100 words
    return round(min(density / 8.0, 1.0), 2)


def analyze_deception(ticker: str, text: str, source: str) -> dict:
    """
    Analyse executive language for deception/evasion risk.

    Args:
        ticker:  stock ticker symbol
        text:    MD&A or earnings transcript text
        source:  human-readable source label

    Returns dict with:
        ticker, deception_risk_score, transparency_score, tone_label,
        hedge_counts, flag_words, key_concerns, positive_signals,
        reasoning, source, analyzed_at
    """
    from magicfinance.llm_client import _generate, MODEL_4B_PATH, _extract_json

    if not text or len(text) < 150:
        return {
            "ticker": ticker,
            "deception_risk_score": None,
            "error": "Insufficient text for analysis (< 150 chars)",
        }

    hedge_counts = count_hedge_words(text)
    word_count = len(text.split())

    # Collect top flag words actually present in the text
    text_lower = text.lower()
    flag_words = [
        w for cat, words in HEDGE_CATEGORIES.items()
        if cat != "positive_spin"
        for w in words
        if w in text_lower
    ][:10]

    system = (
        "You are a forensic financial analyst specialising in executive language. "
        "You detect evasive, hedged, or misleading communication in SEC filings and earnings calls. "
        "Always respond with valid JSON only — no markdown, no commentary."
    )

    prompt = f"""Analyse this executive communication excerpt for deception / evasion risk.

COMPANY: {ticker}
SOURCE: {source}
HEDGE WORD COUNTS: {hedge_counts}

TEXT (excerpt, first 3000 chars):
{text[:3000]}

Score on these dimensions:
- deception_risk_score (0.0=fully transparent, 1.0=highly evasive or alarming)
- transparency_score (0.0=opaque, 1.0=fully transparent — should roughly equal 1 - deception_risk_score)
- tone_label: exactly one of "TRANSPARENT", "CAUTIOUS", "EVASIVE", "ALARMING"
- key_concerns: JSON array of 2-3 specific red flags found (empty array if none)
- positive_signals: JSON array of 1-2 genuine transparency indicators (empty array if none)
- reasoning: 2-3 sentence plain-English assessment

Red flags to look for:
• Omitting specific numbers when concrete data would be expected
• Blaming macro/external factors without quantifying impact
• Excessive forward-looking language with no substance
• Absence of risk acknowledgment despite known challenges
• Stark contrast between stated optimism and disclosed facts

Return ONLY valid JSON:
{{"deception_risk_score":0.0,"transparency_score":0.0,"tone_label":"CAUTIOUS","key_concerns":[],"positive_signals":[],"reasoning":"assessment here"}}"""

    try:
        raw = _generate(MODEL_4B_PATH, prompt, system=system, max_tokens=350, temperature=0.2)
        result = _extract_json(raw)
    except Exception as exc:
        logger.warning("LLM deception analysis failed for %s: %s", ticker, exc)
        risk = _rule_based_score(hedge_counts, word_count)
        result = {
            "deception_risk_score": risk,
            "transparency_score": round(1.0 - risk, 2),
            "tone_label": "EVASIVE" if risk > 0.5 else ("CAUTIOUS" if risk > 0.25 else "TRANSPARENT"),
            "key_concerns": flag_words[:3],
            "positive_signals": [],
            "reasoning": f"Rule-based fallback: {hedge_counts['total']} hedge phrases in {word_count} words.",
        }

    result["ticker"] = ticker
    result["hedge_counts"] = hedge_counts
    result["flag_words"] = flag_words
    result["source"] = source
    result["analyzed_at"] = datetime.utcnow().isoformat()
    result["word_count"] = word_count
    return result


def run_deception_check(ticker: str) -> dict:
    """
    Full pipeline for a ticker: fetch text → analyze → return result.

    Priority:
      1. FMP earnings call transcript (if FMP_API_KEY set)
      2. SEC EDGAR 10-Q MD&A (always available, free)
    """
    from magicfinance.fmp_client import get_latest_transcript
    from magicfinance.sec_client import get_mda_for_ticker

    # Try FMP transcript first
    transcript = get_latest_transcript(ticker)
    if transcript.get("content") and len(transcript["content"]) > 200:
        logger.info("Using FMP transcript for %s (%s)", ticker, transcript.get("source", ""))
        return analyze_deception(ticker, transcript["content"], transcript.get("source", "FMP Earnings Call"))

    # Fallback: SEC EDGAR MD&A
    logger.info("Falling back to SEC EDGAR MD&A for %s", ticker)
    mda = get_mda_for_ticker(ticker)
    if mda.get("mda_text") and len(mda["mda_text"]) > 200:
        return analyze_deception(ticker, mda["mda_text"], mda.get("source", "SEC EDGAR 10-Q"))

    return {
        "ticker": ticker,
        "deception_risk_score": None,
        "error": mda.get("error") or transcript.get("error") or "No executive language data found",
    }
