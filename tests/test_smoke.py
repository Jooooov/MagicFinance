"""
MagicFinance — Smoke Tests
===========================
Quick validation that all components work before running the full pipeline.
Run with: python tests/test_smoke.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback
from dotenv import load_dotenv
load_dotenv()

PASS = []
FAIL = []

def ok(name): PASS.append(name); print(f"  ✅ {name}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")


# ─── 1. Imports ───────────────────────────────────────────────────────────────
print("\n=== 1. Imports ===")
try:
    from magicfinance import config
    from magicfinance.llm_client import check_mlx_health, check_ollama_health
    from magicfinance.reddit_client import extract_tickers, filter_posts_with_tickers
    from magicfinance.portfolio import compute_expected_return_fixed, optimize_portfolio, portfolio_metrics
    from magicfinance.yfinance_client import fetch_prices, compute_covariance_matrix, backtest_portfolio
    from magicfinance.slack_client import _get_webhook_url
    import magicfinance.qdrant_client as qc
    ok("all imports")
except Exception as e:
    fail("imports", e)


# ─── 2. MLX Health ────────────────────────────────────────────────────────────
print("\n=== 2. MLX Health ===")
try:
    h = check_mlx_health()
    assert h["mlx_lm_installed"], "mlx_lm not installed"
    assert h["model_9b_exists"], f"9B model missing at {h['model_9b_path']}"
    assert h["model_4b_exists"], f"4B model missing at {h['model_4b_path']}"
    ok(f"MLX models found: {h['model_9b_path']}")
except Exception as e:
    fail("MLX health", e)


# ─── 3. Ticker Extraction ─────────────────────────────────────────────────────
print("\n=== 3. Ticker Extraction ===")
try:
    assert extract_tickers("$TSLA is great") == ["TSLA"]
    assert "AAPL" in extract_tickers("I love AAPL and MSFT")
    assert extract_tickers("No tickers here, just opinions") == []
    ok("ticker extraction (3/3 cases)")
except Exception as e:
    fail("ticker extraction", e)


# ─── 4. Reddit API ────────────────────────────────────────────────────────────
print("\n=== 4. Reddit API ===")
try:
    import praw
    reddit_id = os.environ.get("REDDIT_CLIENT_ID", "")
    assert reddit_id, "REDDIT_CLIENT_ID not set in .env"

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "test"),
        read_only=True,
    )
    # Lightweight test: just verify auth works
    posts = list(reddit.subreddit("ValueInvesting").hot(limit=3))
    assert len(posts) > 0, "no posts returned"
    ok(f"Reddit API: fetched {len(posts)} posts from r/ValueInvesting")
except Exception as e:
    fail("Reddit API", e)


# ─── 5. Qdrant Connection ─────────────────────────────────────────────────────
print("\n=== 5. Qdrant (VPS via Tailscale) ===")
try:
    client = qc.get_client()
    collections = client.get_collections().collections
    qc.ensure_collections()
    ok(f"Qdrant connected at {config.QDRANT_HOST}:{config.QDRANT_PORT} ({len(collections)} collections)")
except Exception as e:
    fail(f"Qdrant ({config.QDRANT_HOST}:{config.QDRANT_PORT})", e)


# ─── 6. yfinance ─────────────────────────────────────────────────────────────
print("\n=== 6. yfinance (Market Data) ===")
try:
    prices = fetch_prices(["AAPL", "MSFT"], lookback_days=30)
    assert not prices.empty, "no price data returned"
    assert "AAPL" in prices.columns, "AAPL missing from prices"
    cov = compute_covariance_matrix(prices)
    assert cov.shape == (2, 2), f"unexpected cov shape: {cov.shape}"
    ok(f"yfinance: {prices.shape[0]} days, {prices.shape[1]} tickers, cov {cov.shape}")
except Exception as e:
    fail("yfinance", e)


# ─── 7. Portfolio Math (no LLM needed) ───────────────────────────────────────
print("\n=== 7. Portfolio Math (Markowitz) ===")
try:
    import pandas as pd
    import numpy as np

    # Build synthetic test data
    tickers = ["AAPL", "MSFT", "GOOGL"]
    er = pd.Series([0.12, 0.10, 0.09], index=tickers)
    # Synthetic covariance matrix (diagonal = variance)
    cov_data = np.array([
        [0.04, 0.01, 0.008],
        [0.01, 0.035, 0.007],
        [0.008, 0.007, 0.03],
    ])
    cov = pd.DataFrame(cov_data, index=tickers, columns=tickers)

    weights = optimize_portfolio(er, cov)
    assert abs(weights.sum() - 1.0) < 0.01, f"weights don't sum to 1: {weights.sum()}"
    assert all(weights >= 0), "negative weights found"
    metrics = portfolio_metrics(weights, er, cov)
    assert metrics["sharpe_ratio"] > 0, "sharpe should be positive"

    # Test fixed expected return formula
    er_fixed = compute_expected_return_fixed(0.8, 0.7, 0.75)
    assert 0 < er_fixed < 1, f"ER out of range: {er_fixed}"

    ok(f"Markowitz: weights={dict(weights.round(2))}, Sharpe={metrics['sharpe_ratio']:.3f}")
    ok(f"Fixed ER formula: thesis=0.8, forecast=0.7, conf=0.75 → {er_fixed:.3f}")
except Exception as e:
    fail("portfolio math", traceback.format_exc())


# ─── 8. LLM Smoke Test (real inference — ~10s) ───────────────────────────────
print("\n=== 8. LLM Inference (Qwen3.5 4B — quick test) ===")
try:
    from magicfinance.llm_client import _generate, MODEL_4B_PATH
    result = _generate(
        MODEL_4B_PATH,
        prompt='Return ONLY this JSON with no other text: {"status": "ok", "value": 42}',
        max_tokens=50,
        temperature=0.0,
    )
    assert result and len(result) > 0, "empty response"
    ok(f"LLM 4B responded: {result[:80].strip()}")
except Exception as e:
    fail("LLM inference (4B)", e)


# ─── 9. Slack Config ─────────────────────────────────────────────────────────
print("\n=== 9. Slack Config ===")
try:
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if webhook:
        ok("SLACK_WEBHOOK_URL is set")
    else:
        print("  ⚠️  SLACK_WEBHOOK_URL not set — alerts will be skipped (not a blocker)")
except Exception as e:
    fail("Slack config", e)


# ─── Summary ─────────────────────────────────────────────────────────────────
print()
print("=" * 50)
print(f"PASSED: {len(PASS)}  FAILED: {len(FAIL)}")
if FAIL:
    print(f"Failed tests: {', '.join(FAIL)}")
    sys.exit(1)
else:
    print("All smoke tests passed ✅")
    sys.exit(0)
