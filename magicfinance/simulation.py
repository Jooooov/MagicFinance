"""
MagicFinance — Investor Simulation Engine
==========================================
Runs autonomous BUY/SELL/HOLD decisions for 10 AI investor personas.

Portfolio state → data/investor_portfolios.json  (local, fast)
Decision events → Qdrant magicfinance_sim_events  (queryable history)
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 1000.0  # euros per investor
PORTFOLIO_FILE = Path(__file__).parent.parent / "data" / "investor_portfolios.json"


# ─── Portfolio persistence ────────────────────────────────────────────────────

def _fresh_portfolio() -> dict:
    return {
        "cash": INITIAL_CAPITAL,
        "holdings": {},   # {ticker: {shares: float, avg_price: float}}
        "history": [],    # [{timestamp, value}] — last 500 ticks
    }


def load_portfolios() -> dict:
    """Load all investor portfolios from disk. Auto-initialises missing investors."""
    from magicfinance.investors import INVESTORS

    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE) as f:
            data = json.load(f)
        # Add any new investors not yet in the file
        for inv in INVESTORS:
            if inv["id"] not in data:
                data[inv["id"]] = _fresh_portfolio()
        return data

    return {inv["id"]: _fresh_portfolio() for inv in INVESTORS}


def save_portfolios(portfolios: dict) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolios, f, indent=2, default=str)


def reset_portfolios() -> None:
    """Reset all portfolios to €1,000 cash (wipe history)."""
    from magicfinance.investors import INVESTORS
    portfolios = {inv["id"]: _fresh_portfolio() for inv in INVESTORS}
    save_portfolios(portfolios)


# ─── Portfolio maths ──────────────────────────────────────────────────────────

def get_portfolio_value(portfolio: dict, prices: dict) -> float:
    holdings_value = sum(
        data["shares"] * prices.get(ticker, 0)
        for ticker, data in portfolio.get("holdings", {}).items()
    )
    return portfolio.get("cash", 0.0) + holdings_value


def portfolio_pnl_pct(portfolio: dict, prices: dict) -> float:
    """Return P&L as percentage vs INITIAL_CAPITAL."""
    value = get_portfolio_value(portfolio, prices)
    return (value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100


# ─── LLM decision parsing ─────────────────────────────────────────────────────

def _extract_decisions(text: str) -> list[dict]:
    """
    Extract a JSON array of decisions from the LLM response.
    Handles Qwen3.5 <think>...</think> blocks and markdown fences.
    Picks the LAST [...] match to skip any arrays inside thinking blocks.
    """
    # Strip Qwen thinking blocks
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned).strip().rstrip("`").strip()

    # Use findall to get ALL [...] blocks, then try from last to first
    matches = re.findall(r"\[.*?\]|\[.*\]", cleaned, re.DOTALL)
    for candidate in reversed(matches):
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            continue

    if cleaned.strip() in ("[]", "", "null"):
        return []

    logger.warning("Could not extract decisions from: %s", text[:300])
    return []


# ─── Trade execution ──────────────────────────────────────────────────────────

def _execute_trade(
    portfolio: dict,
    action: str,
    ticker: str,
    amount_eur: float,
    price: float,
) -> float:
    """Execute a trade in-place. Returns shares transacted (+buy / -sell)."""
    if price <= 0:
        return 0.0

    if action == "BUY" and amount_eur > 0:
        actual = min(amount_eur, portfolio["cash"])
        if actual < 0.50:
            return 0.0
        shares = actual / price
        portfolio["cash"] -= actual
        h = portfolio["holdings"].setdefault(ticker, {"shares": 0.0, "avg_price": 0.0})
        total = h["shares"] + shares
        h["avg_price"] = (
            (h["shares"] * h["avg_price"] + shares * price) / total if total > 0 else price
        )
        h["shares"] = total
        return shares

    elif action == "SELL" and ticker in portfolio["holdings"]:
        h = portfolio["holdings"][ticker]
        sell_shares = (
            min(amount_eur / price, h["shares"]) if amount_eur > 0 else h["shares"]
        )
        sell_shares = max(0.0, min(sell_shares, h["shares"]))
        proceeds = sell_shares * price
        portfolio["cash"] += proceeds
        h["shares"] -= sell_shares
        if h["shares"] < 0.0001:
            del portfolio["holdings"][ticker]
        return -sell_shares

    return 0.0


# ─── Main tick ────────────────────────────────────────────────────────────────

def run_tick(
    signals: list[dict],
    prices: dict,
    model_path: str,
) -> tuple[list[dict], list[dict]]:
    """
    Run one simulation tick for all 10 investors.

    Each investor reads current signals + prices, reasons in their own voice,
    and outputs BUY/SELL/HOLD decisions. Portfolio state is updated and persisted.

    Args:
        signals: scored Reddit signals (from Qdrant or demo)
        prices:  {ticker: price_usd} for all relevant tickers
        model_path: path to Qwen MLX model (4B or 9B)

    Returns:
        (events, tick_log) where:
          events   = list of decision event dicts (BUY/SELL/HOLD)
          tick_log = list of {investor_id, raw_response, decisions, error} for debug
    """
    from magicfinance.investors import INVESTORS, build_investor_prompt
    from magicfinance.llm_client import _generate

    portfolios = load_portfolios()
    all_events = []
    tick_log = []
    now = datetime.utcnow().isoformat()

    top_signals = sorted(
        signals, key=lambda s: s.get("confidence_level", 0), reverse=True
    )[:5]

    for investor in INVESTORS:
        inv_id = investor["id"]
        portfolio = portfolios[inv_id]
        total_value = get_portfolio_value(portfolio, prices)

        decisions: list[dict] = []
        raw_response = ""
        error = ""
        try:
            prompt = build_investor_prompt(investor, portfolio, top_signals, prices, total_value)
            raw_response = _generate(model_path, prompt, max_tokens=500, temperature=0.4)
            decisions = _extract_decisions(raw_response)
        except Exception as e:
            error = str(e)
            logger.warning("Investor %s decision error: %s", inv_id, e)

        tick_log.append({
            "investor_id": inv_id,
            "investor_name": investor["name"],
            "raw_response": raw_response[:400],
            "decisions": decisions,
            "error": error,
        })

        if not decisions:
            # Investor chose to do nothing — still update history
            portfolio["history"].append({"timestamp": now, "value": total_value})
            portfolios[inv_id] = portfolio
            continue

        for decision in decisions:
            action = str(decision.get("action", "HOLD")).upper()
            ticker = str(decision.get("ticker", "")).strip().upper()
            amount_eur = float(decision.get("amount_eur") or 0)
            reasoning = str(decision.get("reasoning", ""))
            price = prices.get(ticker, 0)

            shares = 0.0
            if action in ("BUY", "SELL") and ticker:
                shares = _execute_trade(portfolio, action, ticker, amount_eur, price)

            new_value = get_portfolio_value(portfolio, prices)
            event = {
                "investor_id": inv_id,
                "investor_name": investor["name"],
                "investor_emoji": investor["emoji"],
                "investor_style": investor["style"],
                "action": action,
                "ticker": ticker,
                "amount_eur": amount_eur,
                "price_usd": price,
                "shares": shares,
                "reasoning": reasoning,
                "portfolio_value": new_value,
                "cash_remaining": portfolio["cash"],
                "pnl_pct": (new_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100,
                "timestamp": now,
            }
            all_events.append(event)

        # Snapshot history (keep last 500 points)
        portfolio["history"].append(
            {"timestamp": now, "value": get_portfolio_value(portfolio, prices)}
        )
        if len(portfolio["history"]) > 500:
            portfolio["history"] = portfolio["history"][-500:]

        portfolios[inv_id] = portfolio

    save_portfolios(portfolios)
    return all_events, tick_log
