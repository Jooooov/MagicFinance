"""
MagicFinance — LLM Client
===========================
Wrappers for local Qwen models via Ollama.

Model routing:
  - Qwen 9B (MODEL_9B): Module A scoring, Module E dynamic weights
  - Qwen 4B (MODEL_4B): Module D binary forecasting (faster, lighter)

All calls return structured JSON. Includes retry logic and timeout handling.
"""

import json
import logging
import re
import time
from typing import Any, Optional

import requests

from magicfinance.config import MODEL_9B, MODEL_4B, OLLAMA_BASE_URL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)

# ─── Core Ollama call ──────────────────────────────────────────────────────────

def _call_ollama(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.1,
    retries: int = 2,
) -> str:
    """
    Call Ollama generate endpoint and return the raw text response.

    Args:
        model: Ollama model tag (e.g. "qwen2.5:9b")
        prompt: user prompt
        system: optional system message
        temperature: lower = more deterministic JSON output
        retries: number of retry attempts on failure

    Returns:
        Raw string response from the model.

    Raises:
        RuntimeError: if all retries fail.
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["response"]
        except Exception as exc:
            logger.warning("Ollama call failed (attempt %d/%d): %s", attempt + 1, retries + 1, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)  # exponential backoff

    raise RuntimeError(f"Ollama failed after {retries + 1} attempts for model {model}")


def _extract_json(text: str) -> dict:
    """
    Extract and parse JSON from a model response.
    Handles cases where the model wraps JSON in markdown code blocks.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

    # Find first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Last resort: try parsing the whole thing
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON from model response:\n%s", text[:500])
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc


# ─── Module A: Reddit Signal Scoring (Qwen 9B) ────────────────────────────────

_SYSTEM_SCORER = """You are a rigorous investment analyst. You evaluate Reddit posts about stocks on five dimensions.
Always respond with valid JSON only — no markdown, no commentary."""

_PROMPT_SCORER = """Evaluate this Reddit post about stock investing.

POST TEXT:
{post_text}

DETECTED TICKERS: {tickers}

Score the post on these five criteria (each 0.0 to 1.0):
- thesis_clarity: Is the investment thesis clear, structured, and logically sound?
- risk_acknowledgment: Does the author explicitly identify risks and adverse scenarios?
- data_quality: Are claims backed by real data, numbers, or cited sources (vs pure opinion)?
- specificity: Are catalysts, time horizons, and price targets concrete (vs vague)?
- original_thinking: Is the analysis original, or does it just echo popular narratives?

Then:
- confidence_level: Overall confidence in this as an investable signal (0.0–1.0)
- is_investable: true if confidence_level >= 0.65 AND at least 3 scores above 0.5, else false
- primary_ticker: The single most-mentioned ticker in this post (string, or null if none)

Return ONLY this JSON:
{{
  "thesis_clarity": 0.0,
  "risk_acknowledgment": 0.0,
  "data_quality": 0.0,
  "specificity": 0.0,
  "original_thinking": 0.0,
  "confidence_level": 0.0,
  "is_investable": false,
  "primary_ticker": null,
  "explanation": {{
    "thesis_clarity": "one sentence",
    "risk_acknowledgment": "one sentence",
    "data_quality": "one sentence",
    "specificity": "one sentence",
    "original_thinking": "one sentence"
  }}
}}"""


def score_reddit_post(post_text: str, tickers: list[str]) -> dict:
    """
    Score a Reddit post using Qwen 9B and return structured signal fields.

    Returns dict with: thesis_clarity, risk_acknowledgment, data_quality,
    specificity, original_thinking, confidence_level, is_investable,
    primary_ticker, explanation
    """
    prompt = _PROMPT_SCORER.format(
        post_text=post_text[:3000],  # cap context length
        tickers=", ".join(tickers) if tickers else "none detected",
    )
    raw = _call_ollama(model=MODEL_9B, prompt=prompt, system=_SYSTEM_SCORER)
    result = _extract_json(raw)

    # Normalise: rename thesis_clarity → thesis_score for pipeline consistency
    result["thesis_score"] = result.pop("thesis_clarity", 0.0)
    return result


# ─── Module D: Binary Event Forecasting (Qwen 4B) ─────────────────────────────

_SYSTEM_FORECASTER = """You are a calibrated probabilistic forecaster. You estimate probabilities for binary financial events.
Always respond with valid JSON only — no markdown, no commentary."""

_PROMPT_FORECAST = """Estimate the probability of this financial event occurring.

EVENT: {event}
CONTEXT: {context}

Return ONLY this JSON:
{{
  "event": "{event}",
  "prediction": "yes" or "no",
  "forecast_probability": 0.0,
  "confidence_level": 0.0,
  "model_reasoning": "2-3 sentences explaining your estimate"
}}

Rules:
- forecast_probability: 0.0 = definitely no, 1.0 = definitely yes
- confidence_level: how confident you are in your own estimate (0.0–1.0)
- Be calibrated: if uncertain, use values closer to 0.5
- Base reasoning on fundamentals, not speculation"""


def forecast_binary_event(event: str, context: str) -> dict:
    """
    Generate a binary probability forecast using Qwen 4B.

    Args:
        event: The binary question (e.g. "Will TSLA beat EPS next quarter?")
        context: Relevant market/ticker context to inform the forecast

    Returns:
        Dict with: event, prediction, forecast_probability, confidence_level, model_reasoning
    """
    prompt = _PROMPT_FORECAST.format(event=event, context=context[:2000])
    raw = _call_ollama(model=MODEL_4B, prompt=prompt, system=_SYSTEM_FORECASTER)
    return _extract_json(raw)


# ─── Module D: Event Generation from Reddit Signal ────────────────────────────

_PROMPT_GENERATE_EVENTS = """Given this investment signal, generate 1-2 concrete binary forecast questions.

TICKER: {ticker}
THESIS: {thesis_summary}
CONFIDENCE: {confidence:.2f}

Generate binary questions that could be resolved within 3 months.
Focus on: earnings beats, price targets, catalyst events.

Return ONLY this JSON array:
[
  {{
    "event": "Will {ticker} beat analyst EPS estimates next earnings?",
    "event_type": "earnings"
  }}
]"""


def generate_events_from_signal(signal: dict) -> list[dict]:
    """
    Use the signal data to auto-generate relevant binary forecast questions.
    Returns list of event dicts with keys: event, event_type
    """
    prompt = _PROMPT_GENERATE_EVENTS.format(
        ticker=signal.get("ticker", ""),
        thesis_summary=signal.get("explanation", {}).get("thesis_score", "")[:300],
        confidence=signal.get("confidence_level", 0.0),
    )
    raw = _call_ollama(model=MODEL_4B, prompt=prompt, system=_SYSTEM_FORECASTER)

    # Extract JSON array
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return []


# ─── Module E: Dynamic Weight Reasoning (Qwen 9B) ─────────────────────────────

_SYSTEM_WEIGHER = """You are a quantitative portfolio analyst. You reason about relative signal reliability.
Always respond with valid JSON only — no markdown, no commentary."""

_PROMPT_DYNAMIC_WEIGHTS = """Given this investment signal, determine the optimal weights for combining the three sub-signals into an expected return estimate.

TICKER: {ticker}
THESIS SCORE: {thesis_score:.2f} — quality of investment thesis
FORECAST PROBABILITY: {forecast_prob:.2f} — LLM binary event forecast probability
CONFIDENCE LEVEL: {confidence_level:.2f} — composite signal confidence

The weights must sum to 1.0. Adjust based on:
- If thesis_score is high but forecast_prob is uncertain (near 0.5), weight thesis more
- If confidence is low, reduce its weight
- If all signals are strong and aligned, use balanced weights

Return ONLY this JSON:
{{
  "weight_thesis": 0.0,
  "weight_forecast": 0.0,
  "weight_confidence": 0.0,
  "reasoning": "1-2 sentences explaining the weight allocation"
}}"""


def compute_dynamic_weights(ticker: str, thesis_score: float, forecast_prob: float, confidence_level: float) -> dict:
    """
    Ask Qwen 9B to reason about optimal signal weights for a specific ticker.

    Returns dict with: weight_thesis, weight_forecast, weight_confidence, reasoning
    (weights sum to ~1.0)
    """
    prompt = _PROMPT_DYNAMIC_WEIGHTS.format(
        ticker=ticker,
        thesis_score=thesis_score,
        forecast_prob=forecast_prob,
        confidence_level=confidence_level,
    )
    raw = _call_ollama(model=MODEL_9B, prompt=prompt, system=_SYSTEM_WEIGHER)
    result = _extract_json(raw)

    # Normalise weights to ensure they sum to 1.0
    total = result.get("weight_thesis", 0) + result.get("weight_forecast", 0) + result.get("weight_confidence", 0)
    if total > 0:
        result["weight_thesis"] /= total
        result["weight_forecast"] /= total
        result["weight_confidence"] /= total
    else:
        # Fallback to equal weights
        result = {"weight_thesis": 0.33, "weight_forecast": 0.34, "weight_confidence": 0.33, "reasoning": "fallback equal weights"}

    return result


def check_ollama_health() -> bool:
    """Return True if Ollama server is reachable and responding."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False
