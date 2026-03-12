"""
MagicFinance — yfinance Client
================================
Historical OHLCV data and covariance matrix construction for Module E.
Reuses the yfinance pattern already established in Nanobot's stock_watchdog.py.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from magicfinance.config import LOOKBACK_DAYS

logger = logging.getLogger(__name__)


def fetch_prices(
    tickers: list[str],
    lookback_days: int = LOOKBACK_DAYS,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Download daily adjusted closing prices for a list of tickers.

    Args:
        tickers: list of ticker symbols (e.g. ["AAPL", "TSLA"])
        lookback_days: number of calendar days to look back (default ~1 year)
        end_date: end date in "YYYY-MM-DD" format (default: today)

    Returns:
        DataFrame with dates as index, tickers as columns.
        Columns with >20% missing data are dropped with a warning.
    """
    end = pd.Timestamp(end_date) if end_date else pd.Timestamp.today()
    start = end - pd.Timedelta(days=lookback_days)

    logger.info("Fetching prices for %d tickers from %s to %s", len(tickers), start.date(), end.date())

    try:
        raw = yf.download(
            tickers=tickers,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        logger.error("yfinance download failed: %s", exc)
        return pd.DataFrame()

    # Extract 'Close' column
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})

    # Drop tickers with excessive missing data
    missing_pct = prices.isna().mean()
    bad_tickers = missing_pct[missing_pct > 0.20].index.tolist()
    if bad_tickers:
        logger.warning("Dropping %d tickers with >20%% missing data: %s", len(bad_tickers), bad_tickers)
        prices = prices.drop(columns=bad_tickers)

    prices = prices.dropna(how="all")
    logger.info("Price data ready: %d rows × %d tickers", len(prices), prices.shape[1])
    return prices


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily log returns from price DataFrame.
    Log returns are used for Markowitz as they are more statistically well-behaved.
    """
    return np.log(prices / prices.shift(1)).dropna()


def compute_covariance_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute annualised covariance matrix from daily prices.
    Annualisation factor: 252 trading days.
    """
    returns = compute_returns(prices)
    cov = returns.cov() * 252  # annualise
    return cov


def compute_expected_returns(signals: list[dict]) -> pd.Series:
    """
    Build expected return series from MagicFinance composite signals.
    Used as input to the Markowitz optimizer.

    Args:
        signals: list of dicts with 'ticker' and 'expected_return' keys

    Returns:
        pd.Series indexed by ticker symbol.
    """
    data = {s["ticker"]: s["expected_return"] for s in signals if "expected_return" in s}
    return pd.Series(data)


def get_ticker_info(ticker: str) -> dict:
    """
    Fetch basic fundamental info for a ticker (name, sector, market cap).
    Used for display purposes in notebooks.
    """
    try:
        info = yf.Ticker(ticker).info
        return {
            "ticker": ticker,
            "name": info.get("longName", ticker),
            "sector": info.get("sector", "Unknown"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "USD"),
        }
    except Exception as exc:
        logger.warning("Could not fetch info for %s: %s", ticker, exc)
        return {"ticker": ticker, "name": ticker, "sector": "Unknown"}


def backtest_portfolio(
    weights: pd.Series,
    prices: pd.DataFrame,
    initial_value: float = 10_000.0,
) -> pd.DataFrame:
    """
    Simulate portfolio P&L using current weights applied to historical prices.

    Args:
        weights: pd.Series of allocation weights indexed by ticker (must sum to ~1.0)
        prices: historical price DataFrame (from fetch_prices)
        initial_value: starting portfolio value in USD

    Returns:
        DataFrame with columns: portfolio_value, daily_return, cumulative_return
        Indexed by date.
    """
    # Align weights to available price columns
    available = [t for t in weights.index if t in prices.columns]
    if not available:
        logger.error("No overlap between portfolio tickers and available price data")
        return pd.DataFrame()

    w = weights[available] / weights[available].sum()  # renormalise
    price_subset = prices[available].dropna()

    # Daily returns
    daily_returns = price_subset.pct_change().dropna()

    # Portfolio daily return = weighted sum of individual returns
    portfolio_daily = (daily_returns * w).sum(axis=1)

    # Cumulative return starting from initial_value
    cumulative = (1 + portfolio_daily).cumprod()
    portfolio_value = cumulative * initial_value

    result = pd.DataFrame({
        "portfolio_value": portfolio_value,
        "daily_return": portfolio_daily,
        "cumulative_return": cumulative - 1,
    })

    return result


def benchmark_sp500(
    start_date: str,
    end_date: Optional[str] = None,
    initial_value: float = 10_000.0,
) -> pd.DataFrame:
    """
    Fetch S&P 500 (^GSPC) as a benchmark for portfolio comparison.

    Returns DataFrame with portfolio_value and cumulative_return indexed by date.
    """
    end = end_date or datetime.today().strftime("%Y-%m-%d")
    prices = fetch_prices(["^GSPC"], end_date=end)
    if prices.empty:
        return pd.DataFrame()

    prices = prices[prices.index >= start_date]
    daily = prices.pct_change().dropna()
    cumulative = (1 + daily["^GSPC"]).cumprod()

    return pd.DataFrame({
        "portfolio_value": cumulative * initial_value,
        "cumulative_return": cumulative - 1,
    })
