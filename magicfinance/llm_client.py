"""
MagicFinance — LLM Client (MLX)
=================================
Local inference via MLX — no server required, no network latency.

Model routing:
  - Qwen3.5 9B (MODEL_9B_PATH): Module A scoring, Module E dynamic weights
  - Qwen3.5 4B (MODEL_4B_PATH): Module D binary forecasting (faster)

Models are loaded lazily and cached as singletons — loaded once, reused across calls.
MLX runs natively on Apple Silicon (M-series) via the mlx_lm library.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Model paths ───────────────────────────────────────────────────────────────

_MLX_BASE = Path.home() / "Desktop/Apps/MLX"
MODEL_9B_PATH = str(_MLX_BASE / "Qwen3.5-9B-4bit")
MODEL_4B_PATH = str(_MLX_BASE / "Qwen3.5-4B-4bit")

# Max tokens per call (keep conservative to avoid RAM pressure)
MAX_TOKENS_SCORING = 600    # Module A: structured 7-field JSON
MAX_TOKENS_FORECAST = 300   # Module D: binary forecast JSON
MAX_TOKENS_WEIGHTS = 200    # Module E: weight allocation JSON
MAX_TOKENS_EVENTS = 250     # Module D: event generation array

# ─── Model singleton cache ─────────────────────────────────────────────────────

_models: dict = {}  # path → (model, tokenizer)


def _load_model(model_path: str):
    """
    Load an MLX model and tokenizer, caching in memory.
    Qwen3.5 models are VL architectures but used in text-only mode.
    Uses strict=False to skip vision tower weights that aren't in the text model.
    First call takes ~2-5s; subsequent calls return instantly from cache.
    """
    if model_path not in _models:
        try:
            from mlx_lm.utils import load_model, load_tokenizer
            logger.info("Loading MLX model from %s...", Path(model_path).name)
            model, _config = load_model(Path(model_path), lazy=False, strict=False)
            tokenizer = load_tokenizer(Path(model_path))
            _models[model_path] = (model, tokenizer)
            logger.info("MLX model loaded: %s", Path(model_path).name)
        except Exception as exc:
            raise RuntimeError(f"Failed to load MLX model from {model_path}: {exc}") from exc
    return _models[model_path]


# ─── Core generation call ──────────────────────────────────────────────────────

def _generate(
    model_path: str,
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 400,
    temperature: float = 0.1,
) -> str:
    """
    Run MLX generation with the given model (VLM text-only mode).

    Args:
        model_path: path to the MLX model directory
        prompt: user message
        system: optional system message
        max_tokens: max tokens to generate (keep low to avoid RAM pressure)
        temperature: lower = more deterministic JSON output

    Returns:
        Raw string response from the model.
    """
    from mlx_lm import generate

    model, tokenizer = _load_model(model_path)

    # Build chat messages and apply chat template
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # enable_thinking=False disables Qwen3.5 chain-of-thought for faster JSON output
    try:
        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        # Fallback for tokenizers that don't support enable_thinking
        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    from mlx_lm.sample_utils import make_sampler
    sampler = make_sampler(temp=temperature)
    response = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=max_tokens,
        sampler=sampler,
        verbose=False,
    )
    return response


def _extract_json(text: str) -> dict:
    """
    Extract and parse JSON from a model response.
    Handles markdown code fences and leading/trailing noise.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

    # Find first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON from model response:\n%s", text[:500])
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc


# ─── Module A: Reddit Signal Scoring (Qwen3.5 9B) ─────────────────────────────

_SYSTEM_SCORER = """You are a rigorous investment analyst. You evaluate Reddit posts about stocks on five dimensions.
Always respond with valid JSON only — no markdown, no commentary, no extra text."""

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
- primary_ticker: The single most-mentioned ticker (string, or null if none)

Return ONLY valid JSON, no other text:
{{"thesis_clarity":0.0,"risk_acknowledgment":0.0,"data_quality":0.0,"specificity":0.0,"original_thinking":0.0,"confidence_level":0.0,"is_investable":false,"primary_ticker":null,"explanation":{{"thesis_clarity":"one sentence","risk_acknowledgment":"one sentence","data_quality":"one sentence","specificity":"one sentence","original_thinking":"one sentence"}}}}"""


def score_reddit_post(post_text: str, tickers: list[str]) -> dict:
    """
    Score a Reddit post using Qwen3.5 9B and return structured signal fields.

    Returns dict with: thesis_score (renamed from thesis_clarity), risk_acknowledgment,
    data_quality, specificity, original_thinking, confidence_level, is_investable,
    primary_ticker, explanation
    """
    prompt = _PROMPT_SCORER.format(
        post_text=post_text[:3000],
        tickers=", ".join(tickers) if tickers else "none detected",
    )
    raw = _generate(MODEL_9B_PATH, prompt, system=_SYSTEM_SCORER, max_tokens=MAX_TOKENS_SCORING)
    result = _extract_json(raw)

    # Rename thesis_clarity → thesis_score for pipeline consistency
    result["thesis_score"] = result.pop("thesis_clarity", 0.0)
    return result


# ─── Module D: Binary Event Forecasting (Qwen3.5 4B) ─────────────────────────

_SYSTEM_FORECASTER = """You are a calibrated probabilistic forecaster. You estimate probabilities for binary financial events.
Always respond with valid JSON only — no markdown, no commentary."""

_PROMPT_FORECAST = """Estimate the probability of this financial event occurring.

EVENT: {event}
CONTEXT: {context}

Return ONLY valid JSON:
{{"event":"{event}","prediction":"yes","forecast_probability":0.0,"confidence_level":0.0,"model_reasoning":"2-3 sentences"}}

Rules:
- forecast_probability: 0.0=definitely no, 1.0=definitely yes
- confidence_level: how confident you are in your estimate (0.0–1.0)
- Be calibrated: if uncertain, use values closer to 0.5"""


def forecast_binary_event(event: str, context: str) -> dict:
    """
    Generate a binary probability forecast using Qwen3.5 4B.

    Args:
        event: binary question (e.g. "Will TSLA beat EPS next quarter?")
        context: relevant market/ticker context

    Returns:
        Dict with: event, prediction, forecast_probability, confidence_level, model_reasoning
    """
    prompt = _PROMPT_FORECAST.format(event=event, context=context[:2000])
    raw = _generate(MODEL_4B_PATH, prompt, system=_SYSTEM_FORECASTER, max_tokens=MAX_TOKENS_FORECAST)
    return _extract_json(raw)


# ─── Module D: Event Generation from Reddit Signal ────────────────────────────

_PROMPT_GENERATE_EVENTS = """Given this investment signal, generate 1-2 binary forecast questions resolvable within 3 months.

TICKER: {ticker}
THESIS SUMMARY: {thesis_summary}
CONFIDENCE: {confidence:.2f}

Return ONLY a valid JSON array (no other text):
[{{"event":"Will {ticker} beat analyst EPS estimates next earnings?","event_type":"earnings"}}]"""


def generate_events_from_signal(signal: dict) -> list[dict]:
    """
    Auto-generate relevant binary forecast questions from a scored signal.
    Returns list of dicts with keys: event, event_type
    """
    prompt = _PROMPT_GENERATE_EVENTS.format(
        ticker=signal.get("ticker", ""),
        thesis_summary=signal.get("explanation", {}).get("thesis_score", "")[:300],
        confidence=signal.get("confidence_level", 0.0),
    )
    raw = _generate(MODEL_4B_PATH, prompt, system=_SYSTEM_FORECASTER, max_tokens=MAX_TOKENS_EVENTS)

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return []


# ─── Module E: Dynamic Weight Reasoning (Qwen3.5 9B) ─────────────────────────

_SYSTEM_WEIGHER = """You are a quantitative portfolio analyst. You reason about relative signal reliability.
Always respond with valid JSON only — no markdown, no commentary."""

_PROMPT_DYNAMIC_WEIGHTS = """Determine optimal weights for combining three investment sub-signals into an expected return estimate.

TICKER: {ticker}
THESIS SCORE: {thesis_score:.2f} (quality of investment thesis)
FORECAST PROBABILITY: {forecast_prob:.2f} (LLM binary event forecast)
CONFIDENCE LEVEL: {confidence_level:.2f} (composite signal confidence)

Weights must sum to 1.0. Adjust based on relative signal reliability for this ticker.

Return ONLY valid JSON:
{{"weight_thesis":0.0,"weight_forecast":0.0,"weight_confidence":0.0,"reasoning":"1-2 sentences"}}"""


def compute_dynamic_weights(ticker: str, thesis_score: float, forecast_prob: float, confidence_level: float) -> dict:
    """
    Ask Qwen3.5 9B to reason about optimal signal weights for a specific ticker.

    Returns dict with: weight_thesis, weight_forecast, weight_confidence, reasoning
    Weights are normalised to sum to 1.0.
    """
    from magicfinance.config import FIXED_WEIGHTS

    prompt = _PROMPT_DYNAMIC_WEIGHTS.format(
        ticker=ticker,
        thesis_score=thesis_score,
        forecast_prob=forecast_prob,
        confidence_level=confidence_level,
    )
    raw = _generate(MODEL_9B_PATH, prompt, system=_SYSTEM_WEIGHER, max_tokens=MAX_TOKENS_WEIGHTS)
    result = _extract_json(raw)

    # Normalise to sum to 1.0
    total = result.get("weight_thesis", 0) + result.get("weight_forecast", 0) + result.get("weight_confidence", 0)
    if total > 0:
        result["weight_thesis"] /= total
        result["weight_forecast"] /= total
        result["weight_confidence"] /= total
    else:
        result = {
            "weight_thesis": FIXED_WEIGHTS["thesis"],
            "weight_forecast": FIXED_WEIGHTS["forecast"],
            "weight_confidence": FIXED_WEIGHTS["confidence"],
            "reasoning": "fallback to fixed weights (LLM returned invalid weights)",
        }

    return result


# ─── Health check ─────────────────────────────────────────────────────────────

def check_mlx_health() -> dict:
    """
    Verify MLX models are accessible and mlx_lm is installed.

    Returns dict with: mlx_lm_installed, model_9b_exists, model_4b_exists
    """
    try:
        import mlx_lm  # noqa: F401
        mlx_ok = True
    except ImportError:
        mlx_ok = False

    return {
        "mlx_lm_installed": mlx_ok,
        "model_9b_exists": Path(MODEL_9B_PATH).exists(),
        "model_4b_exists": Path(MODEL_4B_PATH).exists(),
        "model_9b_path": MODEL_9B_PATH,
        "model_4b_path": MODEL_4B_PATH,
    }


# ─── Backwards compatibility alias ────────────────────────────────────────────
# The notebooks reference check_ollama_health() — redirect to MLX check.

def check_ollama_health() -> bool:
    """Deprecated alias — checks MLX health instead of Ollama."""
    health = check_mlx_health()
    return health["mlx_lm_installed"] and health["model_9b_exists"]
