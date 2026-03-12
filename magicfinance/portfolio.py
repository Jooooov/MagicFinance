"""
MagicFinance — Portfolio Engine (Module E)
==========================================
Markowitz mean-variance optimisation + A/B comparison:
  - Path A: fixed signal weights (config.FIXED_WEIGHTS)
  - Path B: Qwen 9B dynamic weights per ticker

Key functions:
  compute_expected_return_fixed()   — Path A signal combiner
  compute_expected_return_dynamic() — Path B via LLM
  optimize_portfolio()              — Markowitz optimizer
  build_portfolio_positions()       — final position table
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from magicfinance.config import (
    FIXED_WEIGHTS,
    MAX_POSITION_PCT,
    MIN_POSITION_PCT,
    PORTFOLIO_VALUE_USD,
    RISK_FREE_RATE,
)

logger = logging.getLogger(__name__)


# ─── Signal Combination ────────────────────────────────────────────────────────

def compute_expected_return_fixed(
    thesis_score: float,
    forecast_probability: float,
    confidence_level: float,
    weights: dict = FIXED_WEIGHTS,
) -> float:
    """
    Combine three sub-signals into a composite expected return using fixed weights.

    Formula: W_thesis * thesis + W_forecast * forecast + W_confidence * confidence

    Args:
        thesis_score: Module A thesis quality (0–1)
        forecast_probability: Module D binary event probability (0–1)
        confidence_level: Module A composite confidence (0–1)
        weights: weight dict with keys "thesis", "forecast", "confidence"

    Returns:
        Composite expected return in range [0, 1].
        Caller should interpret this as an expected return in context
        (e.g. map to annual % return by multiplying by expected market return).
    """
    return (
        weights["thesis"] * thesis_score
        + weights["forecast"] * forecast_probability
        + weights["confidence"] * confidence_level
    )


def compute_expected_return_dynamic(
    ticker: str,
    thesis_score: float,
    forecast_probability: float,
    confidence_level: float,
) -> tuple[float, dict]:
    """
    Combine signals using Qwen 9B to reason about per-ticker weights.

    Returns:
        (expected_return: float, weights_used: dict)
        weights_used includes LLM reasoning for notebook display.
    """
    # Import here to avoid circular dependencies
    from magicfinance.llm_client import compute_dynamic_weights

    weight_result = compute_dynamic_weights(
        ticker=ticker,
        thesis_score=thesis_score,
        forecast_prob=forecast_probability,
        confidence_level=confidence_level,
    )

    w_thesis = weight_result.get("weight_thesis", FIXED_WEIGHTS["thesis"])
    w_forecast = weight_result.get("weight_forecast", FIXED_WEIGHTS["forecast"])
    w_conf = weight_result.get("weight_confidence", FIXED_WEIGHTS["confidence"])

    expected_return = (
        w_thesis * thesis_score
        + w_forecast * forecast_probability
        + w_conf * confidence_level
    )

    return expected_return, weight_result


def scale_expected_returns(raw_signals: pd.Series, target_mean: float = 0.10) -> pd.Series:
    """
    Scale composite 0–1 signals to plausible annual expected returns.
    Maps signal range [0, 1] to approximately [-5%, +25%] annual return range.

    Args:
        raw_signals: Series of 0–1 composite signals indexed by ticker
        target_mean: target mean annual expected return (default 10%)

    Returns:
        Series of annualised expected returns as decimals.
    """
    # Linear scale: signal 0.5 → target_mean, 0 → -0.05, 1 → +0.25
    return raw_signals * 0.30 - 0.05


# ─── Markowitz Optimisation ────────────────────────────────────────────────────

def optimize_portfolio(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    risk_free_rate: float = RISK_FREE_RATE,
    max_position: float = MAX_POSITION_PCT,
    min_position: float = MIN_POSITION_PCT,
    objective: str = "max_sharpe",
) -> pd.Series:
    """
    Markowitz mean-variance portfolio optimisation.

    Args:
        expected_returns: annualised expected returns per ticker (pd.Series)
        cov_matrix: annualised covariance matrix (pd.DataFrame)
        risk_free_rate: annual risk-free rate for Sharpe calculation
        max_position: maximum allocation per ticker (e.g. 0.25 = 25%)
        min_position: minimum allocation to include a ticker
        objective: "max_sharpe" (Sharpe ratio) or "min_variance"

    Returns:
        pd.Series of portfolio weights indexed by ticker (weights sum to 1.0).
    """
    # Align indices
    tickers = expected_returns.index.intersection(cov_matrix.index)
    if len(tickers) < 2:
        logger.warning("Not enough aligned tickers for optimisation (%d). Using equal weight.", len(tickers))
        return pd.Series(1 / len(expected_returns), index=expected_returns.index)

    mu = expected_returns[tickers].values
    sigma = cov_matrix.loc[tickers, tickers].values
    n = len(tickers)

    def portfolio_return(w):
        return np.dot(w, mu)

    def portfolio_variance(w):
        return np.dot(w, np.dot(sigma, w))

    def portfolio_sharpe(w):
        ret = portfolio_return(w)
        vol = np.sqrt(portfolio_variance(w))
        return -(ret - risk_free_rate) / (vol + 1e-9)  # negative for minimisation

    def portfolio_variance_only(w):
        return portfolio_variance(w)

    obj_fn = portfolio_sharpe if objective == "max_sharpe" else portfolio_variance_only

    # Constraints: weights sum to 1
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    # Bounds: min_position ≤ w_i ≤ max_position
    bounds = [(min_position, max_position)] * n

    # Initial guess: equal weights
    w0 = np.array([1 / n] * n)

    result = minimize(
        obj_fn,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    if not result.success:
        logger.warning("Optimisation did not converge: %s. Using equal weights.", result.message)
        return pd.Series(1 / n, index=tickers)

    weights = pd.Series(result.x, index=tickers)

    # Zero out positions below minimum threshold
    weights[weights < min_position] = 0
    if weights.sum() > 0:
        weights = weights / weights.sum()  # renormalise

    logger.info(
        "Optimised portfolio: %d positions, Sharpe=%.3f",
        (weights > 0).sum(),
        -result.fun if objective == "max_sharpe" else float("nan"),
    )
    return weights


def portfolio_metrics(weights: pd.Series, expected_returns: pd.Series, cov_matrix: pd.DataFrame) -> dict:
    """
    Compute key portfolio performance metrics.

    Returns dict with: expected_return, volatility, sharpe_ratio
    """
    tickers = weights[weights > 0].index.intersection(expected_returns.index).intersection(cov_matrix.index)
    w = weights[tickers]
    mu = expected_returns[tickers]
    sigma = cov_matrix.loc[tickers, tickers]

    port_return = float(np.dot(w, mu))
    port_variance = float(np.dot(w, np.dot(sigma, w)))
    port_vol = np.sqrt(port_variance)
    sharpe = (port_return - RISK_FREE_RATE) / (port_vol + 1e-9)

    return {
        "expected_return": port_return,
        "volatility": port_vol,
        "sharpe_ratio": sharpe,
    }


# ─── Position Table ────────────────────────────────────────────────────────────

def build_portfolio_positions(
    weights: pd.Series,
    signals: list[dict],
    total_value: float = PORTFOLIO_VALUE_USD,
) -> list[dict]:
    """
    Build the final position table combining weights with signal metadata.

    Args:
        weights: optimised portfolio weights (pd.Series indexed by ticker)
        signals: list of signal dicts (from Module A/D/E computation)
        total_value: total portfolio USD value

    Returns:
        List of position dicts sorted by allocation_pct descending:
            ticker, allocation_pct, usd_value, expected_return,
            confidence_level, thesis_score, forecast_probability
    """
    signal_map = {s["ticker"]: s for s in signals}
    positions = []

    for ticker, weight in weights[weights > 0].sort_values(ascending=False).items():
        sig = signal_map.get(ticker, {})
        positions.append({
            "ticker": ticker,
            "allocation_pct": float(weight),
            "usd_value": float(weight * total_value),
            "expected_return": float(sig.get("expected_return", 0)),
            "confidence_level": float(sig.get("confidence_level", 0)),
            "thesis_score": float(sig.get("thesis_score", 0)),
            "forecast_probability": float(sig.get("forecast_probability", 0.5)),
        })

    return positions
