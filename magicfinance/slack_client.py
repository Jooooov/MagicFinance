"""
MagicFinance — Slack Client
==============================
Direct Slack webhook alerts fired from local Jupyter notebooks.
No VPS dependency during demo — calls Slack API directly.

Environment variable required:
  SLACK_WEBHOOK_URL  (Incoming Webhook URL from Slack app settings)
"""

import logging
import os
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _get_webhook_url() -> str:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        logger.warning("SLACK_WEBHOOK_URL not set — Slack alerts will be skipped")
    return url


def _send(blocks: list[dict], text: str) -> bool:
    """
    Post a message to Slack via webhook.

    Args:
        blocks: Slack Block Kit blocks (rich formatting)
        text: fallback plain text (shown in notifications)

    Returns:
        True on success, False on failure (non-raising).
    """
    url = _get_webhook_url()
    if not url:
        return False

    try:
        resp = requests.post(
            url,
            json={"text": text, "blocks": blocks},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.debug("Slack alert sent: %s", text[:80])
            return True
        else:
            logger.warning("Slack webhook returned %d: %s", resp.status_code, resp.text)
            return False
    except Exception as exc:
        logger.error("Failed to send Slack alert: %s", exc)
        return False


# ─── Module A alert ────────────────────────────────────────────────────────────

def alert_high_confidence_signal(signal: dict) -> bool:
    """
    Fire a Slack alert when Module A finds a high-confidence Reddit signal.

    Args:
        signal: dict with ticker, confidence_level, thesis_score, source_subreddit, etc.
    """
    ticker = signal.get("ticker", "?")
    confidence = signal.get("confidence_level", 0)
    thesis = signal.get("thesis_score", 0)
    subreddit = signal.get("source_subreddit", "?")
    is_investable = signal.get("is_investable", False)

    investable_emoji = "✅" if is_investable else "⚠️"
    text = f"[MagicFinance] Module A: High-confidence signal for ${ticker} ({confidence:.0%})"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 MagicFinance — Module A Signal {investable_emoji}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Ticker:*\n${ticker}"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence:.0%}"},
                {"type": "mrkdwn", "text": f"*Thesis Score:*\n{thesis:.0%}"},
                {"type": "mrkdwn", "text": f"*Subreddit:*\nr/{subreddit}"},
                {"type": "mrkdwn", "text": f"*Investable:*\n{investable_emoji} {'Yes' if is_investable else 'No'}"},
            ],
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"}],
        },
    ]
    return _send(blocks, text)


# ─── Module D alert ────────────────────────────────────────────────────────────

def alert_strong_forecast(forecast: dict) -> bool:
    """
    Fire a Slack alert when Module D produces a high-probability forecast.

    Args:
        forecast: dict with event, ticker, forecast_probability, model_reasoning, is_macro_event
    """
    event = forecast.get("event", "?")[:100]
    prob = forecast.get("forecast_probability", 0)
    ticker = forecast.get("ticker")
    is_macro = forecast.get("is_macro_event", False)
    reasoning = forecast.get("model_reasoning", "")[:200]

    tag = "🌍 MACRO" if is_macro else f"📈 ${ticker}"
    direction = "likely YES" if prob >= 0.7 else "likely NO"
    text = f"[MagicFinance] Module D: {tag} forecast — {event[:60]} ({prob:.0%} {direction})"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🔮 MagicFinance — Module D Forecast"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Event:*\n_{event}_"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Ticker:*\n{tag}"},
                {"type": "mrkdwn", "text": f"*Probability:*\n{prob:.0%}"},
                {"type": "mrkdwn", "text": f"*Direction:*\n{direction}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Reasoning:*\n{reasoning}"},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"}],
        },
    ]
    return _send(blocks, text)


# ─── Module E alert ────────────────────────────────────────────────────────────

def alert_portfolio_ready(portfolio: list[dict], method: str, total_value: float) -> bool:
    """
    Fire a Slack alert when Module E generates a final portfolio.

    Args:
        portfolio: list of position dicts with ticker, allocation_pct, usd_value, expected_return
        method: "fixed_weights" or "dynamic_weights"
        total_value: total portfolio USD value
    """
    n = len(portfolio)
    top3 = sorted(portfolio, key=lambda x: x.get("allocation_pct", 0), reverse=True)[:3]
    top3_lines = "\n".join(
        f"• *${p['ticker']}*: {p['allocation_pct']:.1%} (${p['usd_value']:,.0f}, ER: {p.get('expected_return', 0):.1%})"
        for p in top3
    )

    method_label = "Fixed Weights" if method == "fixed_weights" else "Dynamic Weights (Qwen)"
    text = f"[MagicFinance] Module E: Portfolio generated ({n} positions, {method_label}, ${total_value:,.0f})"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"💼 MagicFinance — Portfolio Ready ({method_label})"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Positions:*\n{n}"},
                {"type": "mrkdwn", "text": f"*Total Value:*\n${total_value:,.0f}"},
                {"type": "mrkdwn", "text": f"*Method:*\n{method_label}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Top 3 Positions:*\n{top3_lines}"},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | MagicFinance v1.0"}],
        },
    ]
    return _send(blocks, text)
