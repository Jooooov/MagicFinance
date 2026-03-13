"""
MagicFinance — Streamlit Dashboard
====================================
Professional web interface for the MagicFinance Reddit investment research pipeline.
Displays live data from Qdrant + allows running Module A from the browser.

Launch:
    KMP_DUPLICATE_LIB_OK=TRUE streamlit run app.py
"""

import os
import traceback
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# ─── Page config (must be first Streamlit call) ───────────────────────────────

st.set_page_config(
    page_title="MagicFinance",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Dark theme CSS ───────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

    .stApp { background-color: #0d1117; }

    /* ── Glitch animation ── */
    @keyframes glitch {
        0%,88%,100% { transform:translate(0); text-shadow:none; }
        89% { transform:translate(-3px,1px);
              text-shadow:-3px 0 #ff0055, 3px 0 #00d4aa; }
        91% { transform:translate(3px,-1px);
              text-shadow:3px 0 #ff0055, -3px 0 #00d4aa; }
        93% { transform:translate(-1px,0);
              text-shadow:-2px 0 #ff0055; }
        95% { transform:translate(0); text-shadow:none; }
    }
    @keyframes neon-pulse {
        0%,100% { box-shadow:0 0 6px #00d4aa40, 0 0 12px #00d4aa20,
                              inset 0 0 6px #00d4aa10; }
        50%     { box-shadow:0 0 18px #00d4aa80, 0 0 36px #00d4aa40,
                              inset 0 0 10px #00d4aa20; }
    }
    @keyframes scanline {
        0%   { transform:translateY(-100%); }
        100% { transform:translateY(100vh); }
    }
    @keyframes xp-grow {
        from { width:0%; }
    }
    @keyframes blink-cursor {
        0%,100% { border-right-color:#00d4aa; }
        50%     { border-right-color:transparent; }
    }
    @keyframes float-badge {
        0%,100% { transform:translateY(0px); }
        50%     { transform:translateY(-3px); }
    }

    /* ── Scanline overlay ── */
    .stApp::before {
        content:'';
        position:fixed; top:0; left:0; right:0; bottom:0;
        background:repeating-linear-gradient(
            0deg, transparent, transparent 3px,
            rgba(0,212,170,0.015) 3px, rgba(0,212,170,0.015) 4px
        );
        pointer-events:none; z-index:9999;
    }

    /* ── Metric card ── */
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-card .label { color: #8b949e; font-size: 13px; margin-bottom: 4px; }
    .metric-card .value { color: #e6edf3; font-size: 28px; font-weight: 700; }
    .metric-card .sub   { color: #8b949e; font-size: 12px; margin-top: 2px; }

    /* ── Demo banner ── */
    .demo-banner {
        background-color: #3d2c00;
        border: 1px solid #d29922;
        border-radius: 6px;
        padding: 10px 16px;
        color: #d29922;
        font-size: 14px;
        margin-bottom: 16px;
    }

    /* ── Cyberpunk investor card ── */
    .inv-card {
        background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 12px;
        position: relative;
        transition: border-color 0.3s;
    }
    .inv-card.rank-1 {
        border-color: #ffd700;
        animation: neon-pulse 2.5s ease-in-out infinite;
    }
    .inv-card.rank-2 { border-color: #c0c0c0; }
    .inv-card.rank-3 { border-color: #cd7f32; }

    /* ── XP bar ── */
    .xp-track {
        background: #21262d;
        border-radius: 3px;
        height: 5px;
        overflow: hidden;
        margin: 5px 0 3px;
    }
    .xp-fill {
        height: 100%;
        background: linear-gradient(90deg, #00d4aa, #00ffcc);
        border-radius: 3px;
        animation: xp-grow 1s ease-out;
    }

    /* ── Level badge ── */
    .level-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        font-family: 'Share Tech Mono', monospace;
    }

    /* ── Achievement pill ── */
    .ach-pill {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        background: #21262d;
        border: 1px solid #30363d;
        border-radius: 20px;
        padding: 2px 8px;
        font-size: 10px;
        color: #8b949e;
        margin: 2px 2px 0 0;
        animation: float-badge 3s ease-in-out infinite;
    }

    /* ── Market HUD ── */
    .market-hud {
        background: #0d1117;
        border: 1px solid #30363d;
        border-top: 2px solid #00d4aa;
        border-radius: 6px;
        padding: 10px 20px;
        font-family: 'Share Tech Mono', monospace;
        font-size: 12px;
        color: #8b949e;
        margin-bottom: 16px;
        display: flex;
        gap: 20px;
        align-items: center;
        flex-wrap: wrap;
    }
    .hud-item { display: flex; flex-direction: column; }
    .hud-label { font-size: 10px; color: #484f58; letter-spacing: 1px; }
    .hud-value { color: #e6edf3; font-size: 13px; }

    /* ── Intel brief (panorama) ── */
    .intel-brief {
        background: linear-gradient(135deg, #0d1f17 0%, #0d1117 100%);
        border: 1px solid #00d4aa40;
        border-left: 3px solid #00d4aa;
        border-radius: 6px;
        padding: 14px 18px;
        font-family: 'Share Tech Mono', monospace;
        font-size: 13px;
        color: #c9d1d9;
        line-height: 1.7;
        margin: 16px 0;
    }
    .intel-header {
        color: #00d4aa;
        font-size: 10px;
        letter-spacing: 3px;
        margin-bottom: 8px;
        font-weight: 700;
    }

    /* ── Fade in up (staggered card entry) ── */
    @keyframes fadeInUp {
        from { opacity:0; transform:translateY(20px); }
        to   { opacity:1; transform:translateY(0); }
    }
    .inv-card {
        animation: fadeInUp 0.5s ease-out both;
    }
    /* Stagger delays 0–9 */
    .inv-card:nth-child(1)  { animation-delay:.05s; }
    .inv-card:nth-child(2)  { animation-delay:.10s; }
    .inv-card:nth-child(3)  { animation-delay:.15s; }
    .inv-card:nth-child(4)  { animation-delay:.20s; }
    .inv-card:nth-child(5)  { animation-delay:.25s; }
    .inv-card:nth-child(6)  { animation-delay:.30s; }
    .inv-card:nth-child(7)  { animation-delay:.35s; }
    .inv-card:nth-child(8)  { animation-delay:.40s; }
    .inv-card:nth-child(9)  { animation-delay:.45s; }
    .inv-card:nth-child(10) { animation-delay:.50s; }

    /* ── Hover glow on cards ── */
    .inv-card:hover {
        border-color: #00d4aa80 !important;
        box-shadow: 0 0 20px #00d4aa15, 0 4px 20px #00000060;
        transform: translateY(-2px);
        transition: all 0.25s ease;
    }

    /* ── Shimmer on metric values ── */
    @keyframes shimmer {
        0%   { background-position: -200% center; }
        100% { background-position:  200% center; }
    }
    .shimmer-text {
        background: linear-gradient(90deg,
            #e6edf3 0%, #00d4aa 40%, #ffffff 50%, #00d4aa 60%, #e6edf3 100%);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: shimmer 3s linear infinite;
    }

    /* ── Flicker for danger/red items ── */
    @keyframes flicker {
        0%,19%,21%,23%,25%,54%,56%,100% { opacity:1; }
        20%,22%,24%,55% { opacity:0.4; }
    }
    .flicker { animation: flicker 4s linear infinite; }

    /* ── Typewriter cursor ── */
    @keyframes type-cursor {
        0%,100% { border-right-color:#00d4aa; }
        50%     { border-right-color:transparent; }
    }
    .intel-header::after {
        content:'_';
        animation: type-cursor 1s step-end infinite;
        color:#00d4aa;
    }

    /* ── HUD ticker scroll ── */
    @keyframes ticker-scroll {
        0%   { transform:translateX(100%); }
        100% { transform:translateX(-100%); }
    }
    .ticker-wrap {
        overflow:hidden;
        background:#0a0e13;
        border-top:1px solid #21262d;
        border-bottom:1px solid #21262d;
        padding:4px 0;
        font-family:'Share Tech Mono',monospace;
        font-size:11px;
        color:#484f58;
        white-space:nowrap;
    }
    .ticker-inner {
        display:inline-block;
        animation: ticker-scroll 30s linear infinite;
    }

    /* ── Signal verdict pill (animated for STRONG BUY) ── */
    @keyframes verdict-pulse {
        0%,100% { box-shadow:0 0 0px #00d4aa00; }
        50%      { box-shadow:0 0 10px #00d4aa60; }
    }
    .verdict-strong {
        animation: verdict-pulse 2s ease-in-out infinite;
    }

    /* ── Animated gradient border on metric card ── */
    @keyframes border-spin {
        0%   { --angle:0deg; }
        100% { --angle:360deg; }
    }
    .metric-card:hover {
        border-color: #00d4aa60;
        box-shadow: 0 0 12px #00d4aa20;
        transition: all 0.3s ease;
    }

    /* ── Discrete popover footer button ── */
    [data-testid="stPopover"] > div > button {
        background-color: #0d1117 !important;
        border: 1px solid #30363d !important;
        border-top: 1px solid #21262d !important;
        border-radius: 0 0 10px 10px !important;
        color: #484f58 !important;
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 10px !important;
        letter-spacing: 2px !important;
        padding: 5px 0 !important;
        width: 100% !important;
        margin-top: -2px !important;
        transition: color 0.2s, background-color 0.2s !important;
    }
    [data-testid="stPopover"] > div > button:hover {
        color: #00d4aa !important;
        background-color: #161b22 !important;
        border-color: #00d4aa40 !important;
    }

    /* ── Popover panel dark theme ── */
    [data-testid="stPopoverBody"] {
        background-color: #0d1117 !important;
        border: 1px solid #30363d !important;
        border-radius: 10px !important;
    }

    /* ── Pulse dot for live indicator ── */
    @keyframes pulse-dot {
        0%,100% { transform:scale(1);   opacity:1; }
        50%     { transform:scale(1.5); opacity:0.6; }
    }
    .live-dot {
        display:inline-block;
        width:8px; height:8px;
        border-radius:50%;
        background:#00d4aa;
        animation:pulse-dot 2s ease-in-out infinite;
        margin-right:5px;
    }

    /* ── Page title ── */
    .cp-title {
        font-family: 'Share Tech Mono', monospace;
        font-size: 32px;
        font-weight: 700;
        color: #00d4aa;
        letter-spacing: 4px;
        animation: glitch 10s infinite;
        display: inline-block;
        margin-bottom: 0;
    }
    .cp-subtitle {
        font-family: 'Share Tech Mono', monospace;
        font-size: 11px;
        color: #484f58;
        letter-spacing: 3px;
        margin-top: 2px;
    }

    /* ── Hide sidebar completely ── */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* ── Mission Control panel ── */
    .mc-panel {
        background: linear-gradient(180deg, #0d1f17 0%, #0d1117 100%);
        border: 1px solid #00d4aa40;
        border-top: 2px solid #00d4aa;
        border-radius: 8px;
        padding: 14px 20px 10px;
        margin-bottom: 18px;
        font-family: 'Share Tech Mono', monospace;
    }
    .mc-title {
        font-size: 10px;
        letter-spacing: 2px;
        color: #484f58;
        margin-bottom: 10px;
    }
    .mc-status-row {
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
        margin-bottom: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid #21262d;
    }
    .mc-status-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        color: #8b949e;
    }
    .mc-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }
    .mc-dot.on  { background: #00d4aa; box-shadow: 0 0 6px #00d4aa80; }
    .mc-dot.off { background: #f85149; box-shadow: 0 0 6px #f8514980; }
    .mc-dot.warn { background: #d29922; box-shadow: 0 0 6px #d2992280; }
    .mc-sync {
        font-size: 10px;
        color: #484f58;
        margin-left: auto;
        align-self: center;
    }

    /* ── Watchdog ticker card ── */
    .wd-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-left: 3px solid #00d4aa;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }
    .wd-ticker { font-family: 'Share Tech Mono', monospace; font-size: 18px; color: #e6edf3; font-weight: 700; }
    .wd-sub { font-size: 11px; color: #484f58; margin-bottom: 6px; }
    .wd-bar-row { display: flex; gap: 4px; align-items: center; margin: 3px 0; }
    .wd-bar-label { font-size: 10px; color: #8b949e; width: 90px; flex-shrink: 0; font-family: 'Share Tech Mono', monospace; }
    .wd-bar-track { flex: 1; background: #21262d; border-radius: 2px; height: 6px; }
    .wd-bar-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #00d4aa, #00ffcc); }
    .wd-bar-val { font-size: 10px; color: #8b949e; width: 36px; text-align: right; font-family: 'Share Tech Mono', monospace; }
    </style>
    """,
    unsafe_allow_html=True,
)

ACCENT = "#00d4aa"

# ─── Demo data ────────────────────────────────────────────────────────────────

DEMO_SIGNALS = [
    {
        "ticker": "NVDA",
        "source_subreddit": "ValueInvesting",
        "confidence_level": 0.88,
        "thesis_score": 0.91,
        "risk_acknowledgment": 0.82,
        "data_quality": 0.85,
        "specificity": 0.79,
        "original_thinking": 0.76,
        "is_investable": True,
        "signal_timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
    },
    {
        "ticker": "MSFT",
        "source_subreddit": "SecurityAnalysis",
        "confidence_level": 0.81,
        "thesis_score": 0.84,
        "risk_acknowledgment": 0.78,
        "data_quality": 0.90,
        "specificity": 0.83,
        "original_thinking": 0.65,
        "is_investable": True,
        "signal_timestamp": (datetime.utcnow() - timedelta(hours=5)).isoformat(),
    },
    {
        "ticker": "AAPL",
        "source_subreddit": "stocks",
        "confidence_level": 0.72,
        "thesis_score": 0.69,
        "risk_acknowledgment": 0.61,
        "data_quality": 0.74,
        "specificity": 0.58,
        "original_thinking": 0.55,
        "is_investable": False,
        "signal_timestamp": (datetime.utcnow() - timedelta(hours=8)).isoformat(),
    },
    {
        "ticker": "GOOGL",
        "source_subreddit": "ValueInvesting",
        "confidence_level": 0.77,
        "thesis_score": 0.80,
        "risk_acknowledgment": 0.73,
        "data_quality": 0.82,
        "specificity": 0.71,
        "original_thinking": 0.68,
        "is_investable": True,
        "signal_timestamp": (datetime.utcnow() - timedelta(hours=12)).isoformat(),
    },
    {
        "ticker": "META",
        "source_subreddit": "SecurityAnalysis",
        "confidence_level": 0.84,
        "thesis_score": 0.87,
        "risk_acknowledgment": 0.80,
        "data_quality": 0.88,
        "specificity": 0.86,
        "original_thinking": 0.82,
        "is_investable": True,
        "signal_timestamp": (datetime.utcnow() - timedelta(hours=18)).isoformat(),
    },
]

DEMO_FORECASTS = [
    {
        "event": "Fed holds rates at May FOMC meeting",
        "ticker": None,
        "forecast_probability": 0.73,
        "confidence_level": 0.80,
        "is_macro_event": True,
        "resolved": True,
        "actual_outcome": True,
        "model_reasoning": "Strong employment data and sticky core CPI support a hold.",
        "signal_timestamp": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    },
    {
        "event": "NVDA Q2 revenue beats consensus estimate",
        "ticker": "NVDA",
        "forecast_probability": 0.81,
        "confidence_level": 0.85,
        "is_macro_event": False,
        "resolved": True,
        "actual_outcome": True,
        "model_reasoning": "Data center demand acceleration and AI capex cycle intact.",
        "signal_timestamp": (datetime.utcnow() - timedelta(days=5)).isoformat(),
    },
    {
        "event": "10-year Treasury yield rises above 4.8% in Q3",
        "ticker": None,
        "forecast_probability": 0.42,
        "confidence_level": 0.60,
        "is_macro_event": True,
        "resolved": False,
        "actual_outcome": None,
        "model_reasoning": "Mixed signals: resilient economy vs. disinflation trend.",
        "signal_timestamp": (datetime.utcnow() - timedelta(days=1)).isoformat(),
    },
    {
        "event": "MSFT Azure growth re-accelerates to >30% YoY",
        "ticker": "MSFT",
        "forecast_probability": 0.65,
        "confidence_level": 0.72,
        "is_macro_event": False,
        "resolved": False,
        "actual_outcome": None,
        "model_reasoning": "Copilot uptake and enterprise AI migrations driving incremental demand.",
        "signal_timestamp": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
    },
    {
        "event": "S&P 500 enters bear market (−20%) by year-end",
        "ticker": None,
        "forecast_probability": 0.22,
        "confidence_level": 0.55,
        "is_macro_event": True,
        "resolved": False,
        "actual_outcome": None,
        "model_reasoning": "Soft-landing probability still elevated; valuations stretched but not extreme.",
        "signal_timestamp": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
    },
]

DEMO_TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "META"]

# Financial DNA per investor — what metrics drive their decisions
_FINANCIAL_DNA: dict[str, dict] = {
    "harry": {
        "metrics": ["P/E < 15×", "FCF yield > 6%", "ROIC > 15%", "Moat score"],
        "horizon": "5–10 years",
        "position_sizing": "High conviction, few positions",
        "exit_trigger": "Thesis break or >30% overvaluation",
        "benchmark": "S&P 500 (long-term beat)",
    },
    "maeve": {
        "metrics": ["Rate differentials", "Currency flows", "PMI delta", "COT positioning"],
        "horizon": "3–18 months",
        "position_sizing": "Asymmetric — large when conviction is high",
        "exit_trigger": "Macro regime shift detected",
        "benchmark": "Global Macro HF Index",
    },
    "eddie": {
        "metrics": ["Revenue CAGR > 40%", "TAM size", "Gross margin expansion", "Unit economics"],
        "horizon": "5+ years (ignores short-term vol)",
        "position_sizing": "Concentrated bets (40% max single)",
        "exit_trigger": "Disruptive thesis proven wrong",
        "benchmark": "ARK Innovation ETF",
    },
    "conrad": {
        "metrics": ["Correlation < 0.3 between positions", "Sharpe > 1.0", "Max drawdown < 15%", "Risk parity weight"],
        "horizon": "All-weather, multi-year",
        "position_sizing": "Equal risk contribution per asset class",
        "exit_trigger": "Correlation spike across holdings",
        "benchmark": "Risk Parity benchmark",
    },
    "kevin": {
        "metrics": ["PEG ratio < 1", "Revenue growth 15–30%", "P/E relative to sector", "Founder-led"],
        "horizon": "2–5 years",
        "position_sizing": "Moderate, diversified",
        "exit_trigger": "PEG > 2 or thesis weakens emotionally",
        "benchmark": "S&P 500 Growth",
    },
    "jan": {
        "metrics": ["Signal confidence z-score", "Backtest Sharpe", "Statistical edge > 0.55", "Low autocorrelation"],
        "horizon": "Days to weeks (mean-reversion) or months (trend)",
        "position_sizing": "Kelly fraction, many small positions",
        "exit_trigger": "Signal threshold crossed, no narrative",
        "benchmark": "Quantitative Hedge Fund Index",
    },
    "richie": {
        "metrics": ["Short interest > 20%", "Insider buying", "Consensus vs reality gap", "Catalyst clarity"],
        "horizon": "3–12 months (needs clear catalyst)",
        "position_sizing": "Concentrated contrarian (40% max)",
        "exit_trigger": "Catalyst fails or consensus comes around",
        "benchmark": "S&P 500 Value (beat by contrarianism)",
    },
    "vron": {
        "metrics": ["Price vs 200-DMA", "RSI momentum", "52-week high proximity", "Volume surge"],
        "horizon": "Weeks to months (trend-following)",
        "position_sizing": "Size up on momentum, cut fast",
        "exit_trigger": "Trend reversal or stop-loss hit",
        "benchmark": "CTA / Trend Following Index",
    },
    "bella": {
        "metrics": ["30%+ discount to intrinsic", "Graham Number", "Book value P/B < 1", "Dividend yield > 3%"],
        "horizon": "3–7 years",
        "position_sizing": "Conservative, many positions (15% max)",
        "exit_trigger": "Reaches fair value or dividend cut",
        "benchmark": "Berkshire Hathaway",
    },
    "tommy": {
        "metrics": ["Option implied vol mispricing", "Black swan probability", "Tail risk premium", "Barbell ratio"],
        "horizon": "Short (options) + Very long (core safety)",
        "position_sizing": "Barbell: 80% safe + 20% convex bets",
        "exit_trigger": "Asymmetry disappears",
        "benchmark": "Universa Tail Risk Fund",
    },
}


# ─── Gamification helpers ─────────────────────────────────────────────────────

# (threshold_pnl_pct, emoji, title, hex_color)
_LEVELS = [
    (10.0, "🏆", "LEGEND",  "#ffd700"),
    ( 5.0, "💎", "ELITE",   "#00d4aa"),
    ( 2.0, "🔥", "VETERAN", "#ff8c00"),
    ( 0.0, "⚔️", "SOLDIER", "#6e9eff"),
    (-99,  "🌱", "RECRUIT", "#8b949e"),
]


def _investor_level(pnl_pct: float, has_traded: bool = False) -> tuple[str, str, str]:
    """Return (emoji, title, hex_color) based on P&L %.
    Anyone who hasn't made a trade yet stays at RECRUIT regardless of P&L.
    """
    if not has_traded:
        return "🌱", "RECRUIT", "#8b949e"
    for threshold, emoji, title, color in _LEVELS:
        if pnl_pct >= threshold:
            return emoji, title, color
    return "🌱", "RECRUIT", "#8b949e"


def _xp_progress(pnl_pct: float, has_traded: bool = False) -> tuple[float, str]:
    """Return (progress 0-1, next_level_label) for XP bar rendering."""
    if not has_traded:
        return 0.0, "▶ SOLDIER"
    breakpoints = [-99, 0.0, 2.0, 5.0, 10.0, 9999]
    labels = ["RECRUIT", "SOLDIER", "VETERAN", "ELITE", "LEGEND"]
    for i in range(len(breakpoints) - 1):
        lo, hi = breakpoints[i], breakpoints[i + 1]
        if pnl_pct < hi:
            if hi == 9999:
                return 1.0, "MAX LEVEL"
            progress = (pnl_pct - lo) / (hi - lo)
            next_label = labels[min(i + 1, len(labels) - 1)]
            return max(0.0, min(1.0, progress)), f"▶ {next_label}"
    return 1.0, "MAX LEVEL"


def _achievements(portfolio: dict, inv_id: str, all_events: list[dict]) -> list[tuple[str, str]]:
    """Return list of (emoji, label) achievement badges earned."""
    badges = []
    inv_events = [e for e in all_events if e.get("investor_id") == inv_id]
    trades = [e for e in inv_events if e.get("action") in ("BUY", "SELL")]
    holdings = portfolio.get("holdings", {})
    history = portfolio.get("history", [])

    if trades:
        badges.append(("🎯", "FIRST BLOOD"))
    if len(trades) >= 5:
        badges.append(("⚡", "TRIGGER HAPPY"))
    if len(holdings) >= 3:
        badges.append(("🏦", "DIVERSIFIED"))
    if len(history) >= 10:
        badges.append(("📡", "VETERAN RUNNER"))
    buy_tickers = {e.get("ticker") for e in trades if e.get("action") == "BUY"}
    sell_tickers = {e.get("ticker") for e in trades if e.get("action") == "SELL"}
    if buy_tickers & sell_tickers:
        badges.append(("🔄", "TRADE LOOP"))
    if not trades:
        badges.append(("👻", "GHOST"))
    return badges


def _market_condition(signals: list[dict]) -> tuple[str, str, str]:
    """Return (indicator, label, hex_color) based on avg signal confidence."""
    if not signals:
        return "⚫", "NO SIGNAL", "#8b949e"
    avg = sum(s.get("confidence_level", 0) for s in signals) / len(signals)
    if avg >= 0.70:
        return "🟢", "CONDITION GREEN", "#00d4aa"
    elif avg >= 0.50:
        return "🟡", "CONDITION YELLOW", "#d29922"
    else:
        return "🔴", "CONDITION RED", "#f85149"


# ─── Connection probe ──────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def _probe_qdrant() -> bool:
    """Return True if Qdrant is reachable. Re-probes every 30 s."""
    try:
        from magicfinance.qdrant_client import get_client, ensure_collections
        import magicfinance.qdrant_client as _qc
        _qc._client = None
        client = get_client()
        client.get_collections()
        ensure_collections()  # idempotent — creates missing collections on first connect
        return True
    except Exception:
        return False


# ─── Data loaders (cached 5 min) ──────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _load_signals() -> tuple[list[dict], str]:
    """Return (signals, mode) where mode is 'live' | 'empty' | 'offline'."""
    try:
        from magicfinance.qdrant_client import get_all_signals
        signals = get_all_signals(limit=500)
        if signals:
            return signals, "live"
        return DEMO_SIGNALS, "empty"
    except Exception:
        return DEMO_SIGNALS, "offline"


@st.cache_data(ttl=300, show_spinner=False)
def _load_forecasts() -> tuple[list[dict], str]:
    """Return (forecasts, mode) where mode is 'live' | 'empty' | 'offline'."""
    try:
        from magicfinance.qdrant_client import get_forecast_history
        forecasts = get_forecast_history()
        if forecasts:
            return forecasts, "live"
        return DEMO_FORECASTS, "empty"
    except Exception:
        return DEMO_FORECASTS, "offline"


@st.cache_data(ttl=300, show_spinner=False)
def _load_investable(min_confidence: float = 0.0) -> tuple[list[dict], str]:
    """Return (investable_signals, mode) where mode is 'live' | 'empty' | 'offline'."""
    try:
        from magicfinance.qdrant_client import get_investable_signals
        signals = get_investable_signals(min_confidence=min_confidence)
        if signals:
            return signals, "live"
        return [s for s in DEMO_SIGNALS if s["is_investable"]], "empty"
    except Exception:
        return [s for s in DEMO_SIGNALS if s["is_investable"]], "offline"


@st.cache_data(ttl=300, show_spinner=False)
def _load_mlx_health() -> dict:
    try:
        from magicfinance.llm_client import check_mlx_health
        return check_mlx_health()
    except Exception:
        return {"mlx_lm_installed": False, "model_9b_exists": False, "model_4b_exists": False}


# ─── Helper: metric card ──────────────────────────────────────────────────────

def _metric(col, label: str, value: str, sub: str = "") -> None:
    col.markdown(
        f"""
        <div class="metric-card">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
            <div class="sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _info_box(text: str) -> None:
    st.markdown(
        f'<div style="background:#0d2137;border:1px solid #1f6feb;border-radius:6px;'
        f'padding:10px 16px;color:#8b949e;font-size:13px;margin:12px 0 4px 0;">{text}</div>',
        unsafe_allow_html=True,
    )


def _demo_banner(mode: str) -> None:
    if mode == "offline":
        msg = "⚠️ <b>Demo mode</b> — Qdrant unreachable. Connect Tailscale and click <b>Reconnect</b> in the sidebar."
    else:  # empty
        msg = "ℹ️ <b>Coleções vazias</b> — Qdrant ligado mas sem dados ainda. Clica <b>▶ Run Module A</b> na sidebar para popular."
    colour = "#3d2c00" if mode == "offline" else "#0d2137"
    border = "#d29922" if mode == "offline" else "#1f6feb"
    text = "#d29922" if mode == "offline" else "#58a6ff"
    st.markdown(
        f'<div style="background:{colour};border:1px solid {border};border-radius:6px;'
        f'padding:10px 16px;color:{text};font-size:14px;margin-bottom:16px;">{msg}</div>',
        unsafe_allow_html=True,
    )


# ─── Mission Control ──────────────────────────────────────────────────────────

def _render_mission_control() -> dict:
    """Render NASA-style mission control panel and return user-selected parameters."""
    qdrant_ok = _probe_qdrant()
    mlx = _load_mlx_health()

    # ── Status lights HTML ─────────────────────────────────────────────────────
    def _dot(ok, label, extra=""):
        cls = "on" if ok else "off"
        return f'<div class="mc-status-item"><span class="mc-dot {cls}"></span>{label}{extra}</div>'

    mlx_ok   = mlx.get("mlx_lm_installed", False)
    q9b_ok   = mlx.get("model_9b_exists", False)
    q4b_ok   = mlx.get("model_4b_exists", False)

    sync_html = ""
    try:
        from magicfinance.sync import load_last_sync
        last_sync = load_last_sync()
        if last_sync:
            sync_time = last_sync.get("last_sync", "")[:16].replace("T", " ")
            n_ev = last_sync.get("events_pulled", 0)
            sync_ok = last_sync.get("qdrant_ok", False)
            sync_cls = "on" if sync_ok else "warn"
            ev_str = f" · ↓{n_ev} events" if n_ev > 0 else ""
            sync_html = (
                f'<div class="mc-sync">'
                f'<span class="mc-dot {sync_cls}" style="width:6px;height:6px;"></span>'
                f' LAST SYNC {sync_time} UTC{ev_str}'
                f'</div>'
            )
    except Exception:
        pass

    st.markdown(
        f"""<div class="mc-panel">
          <div class="mc-title">// MISSION CONTROL</div>
          <div class="mc-status-row">
            {_dot(qdrant_ok, "QDRANT")}
            {_dot(mlx_ok,   "MLX-LM")}
            {_dot(q9b_ok,   "QWEN-9B")}
            {_dot(q4b_ok,   "QWEN-4B")}
            {sync_html}
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Interactive controls row ───────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns([2, 1.2, 1.5, 1.5, 1.5, 1.5])
    with c1:
        min_confidence = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05, label_visibility="collapsed",
                                   help="Min confidence threshold")
        st.caption(f"⚙ Min confidence: {min_confidence:.2f}")
    with c2:
        investable_only = st.checkbox("Investable only", value=False)
    with c3:
        posts_per_sub = st.slider("Posts/sub", 1, 20, 3, label_visibility="collapsed", help="Posts per subreddit")
        st.caption(f"⚙ Posts/sub: {posts_per_sub}")

    run_clicked = False
    run_d_clicked = False
    if not qdrant_ok:
        with c4:
            if st.button("🔄 Reconnect", use_container_width=True):
                _probe_qdrant.clear()
                _load_signals.clear()
                _load_forecasts.clear()
                _load_investable.clear()
                st.rerun()
    else:
        with c4:
            run_clicked = st.button("▶ MODULE A", use_container_width=True, help="Scrape Reddit → score with Qwen → store signals")
        with c5:
            run_d_clicked = st.button("▶ MODULE D", use_container_width=True, help="Generate binary forecasts from investable signals")

    return {
        "min_confidence": min_confidence,
        "investable_only": investable_only,
        "posts_per_sub": posts_per_sub,
        "run_clicked": run_clicked,
        "run_d_clicked": run_d_clicked,
        "qdrant_ok": qdrant_ok,
    }


def _run_pipeline(posts_per_sub: int) -> None:
    """Execute Module A: scrape → filter → score → store."""
    from magicfinance.config import SUBREDDITS
    from magicfinance.reddit_client import fetch_all_subreddits, filter_posts_with_tickers
    from magicfinance.llm_client import score_reddit_post
    from magicfinance.qdrant_client import upsert_reddit_signal, ensure_collections

    with st.spinner("Ensuring Qdrant collections exist…"):
        ensure_collections()

    with st.spinner("Fetching Reddit posts…"):
        posts = fetch_all_subreddits(
            subreddits=SUBREDDITS,
            limit=posts_per_sub,
        )

    with st.spinner("Filtering posts with tickers…"):
        filtered = filter_posts_with_tickers(posts)

    if not filtered:
        st.info("No posts with recognisable tickers found.")
        return

    stored = 0
    errors = []
    progress = st.progress(0, text="Scoring posts…")
    for i, post in enumerate(filtered):
        text = f"{post.get('title', '')} {post.get('selftext', '')}"
        tickers = post.get("detected_tickers") or post.get("tickers", [])
        if not tickers:
            continue
        try:
            scored = score_reddit_post(text, tickers)
        except Exception as e:
            errors.append(f"LLM score failed: {e}")
            progress.progress((i + 1) / len(filtered), text=f"Scoring {i+1}/{len(filtered)}…")
            continue
        try:
            scored.setdefault("ticker", tickers[0])
            scored["source_subreddit"] = post.get("subreddit", "unknown")
            scored["signal_timestamp"] = datetime.utcnow().isoformat()
            scored["post_id"] = post.get("id", "")
            upsert_reddit_signal(scored)
            stored += 1
        except Exception as e:
            errors.append(f"Qdrant upsert failed: {e}")
        progress.progress((i + 1) / len(filtered), text=f"Scoring {i+1}/{len(filtered)}…")

    progress.empty()
    if stored > 0:
        st.success(f"Stored {stored}/{len(filtered)} signal(s) in Qdrant.")
        _load_signals.clear()
        _load_investable.clear()
    else:
        st.error(f"Stored 0/{len(filtered)} — all failed.")
    if errors:
        with st.expander(f"⚠️ {len(errors)} error(s)"):
            for err in errors[:10]:
                st.code(err)

    # Bust caches so tabs reload
    _load_signals.clear()
    _load_forecasts.clear()
    _load_investable.clear()


# ─── Module D runner ──────────────────────────────────────────────────────────

def _run_module_d() -> None:
    """Generate binary forecasts from investable signals and store in Qdrant."""
    from magicfinance.llm_client import generate_events_from_signal, forecast_binary_event
    from magicfinance.qdrant_client import get_investable_signals, upsert_forecast

    from magicfinance.qdrant_client import ensure_collections
    with st.spinner("Ensuring Qdrant collections exist…"):
        ensure_collections()

    with st.spinner("Loading signals…"):
        signals = get_investable_signals()
        if not signals:
            from magicfinance.qdrant_client import get_all_signals
            signals = get_all_signals(limit=100)

    if not signals:
        st.info("No signals in Qdrant. Run Module A first.")
        return

    st.info(f"Using {len(signals)} signal(s) for forecasting.")

    total_forecasts = 0
    progress = st.progress(0, text="Generating forecasts…")

    for i, signal in enumerate(signals[:10]):  # cap at 10 signals to avoid RAM pressure
        ticker = signal.get("ticker", "")
        try:
            events = generate_events_from_signal(signal)
            for evt in events:
                event_text = evt.get("event", "")
                if not event_text:
                    continue
                context = (
                    f"Ticker: {ticker}. "
                    f"Thesis score: {signal.get('thesis_score', 0):.2f}. "
                    f"Confidence: {signal.get('confidence_level', 0):.2f}. "
                    f"Subreddit: {signal.get('source_subreddit', '')}."
                )
                forecast = forecast_binary_event(event_text, context)
                forecast["ticker"] = ticker
                forecast["is_macro_event"] = False
                forecast["resolved"] = False
                forecast["actual_outcome"] = None
                forecast["signal_timestamp"] = datetime.utcnow().isoformat()
                upsert_forecast(forecast)
                total_forecasts += 1
        except Exception as e:
            st.warning(f"{ticker}: {e}")

        progress.progress((i + 1) / min(len(signals), 10), text=f"Forecasting {ticker}…")

    progress.empty()
    st.success(f"Generated {total_forecasts} forecast(s) from {min(len(signals), 10)} signals.")
    _load_forecasts.clear()


# ─── Tab 1 — Reddit Signals ───────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_ticker_info(ticker: str) -> dict:
    try:
        from magicfinance.yfinance_client import get_ticker_info
        return get_ticker_info(ticker)
    except Exception:
        return {}


def _verdict(conf: float, thesis: float, is_inv: bool) -> tuple[str, str]:
    """Return (label, colour) for the Reddit signal verdict."""
    if is_inv and conf >= 0.75:
        return "🟢 STRONG BUY", "#00d4aa"
    if is_inv or conf >= 0.60:
        return "🟡 WATCH", "#d29922"
    return "🔴 WEAK SIGNAL", "#f85149"


def _ddd_verdict(signal: dict, info: dict) -> tuple[str, str, str]:
    """
    Cross-check Reddit signal with market fundamentals.
    Returns (badge, colour, reasoning).
    """
    conf = signal.get("confidence_level", 0)
    thesis = signal.get("thesis_score", 0)
    pe = info.get("trailingPE") or info.get("forwardPE")
    revenue_growth = info.get("revenueGrowth")  # e.g. 0.15 = 15%
    target = info.get("targetMeanPrice")
    price = info.get("currentPrice") or info.get("regularMarketPrice")

    reasons = []
    support_points = 0
    contradict_points = 0

    if conf >= 0.50 and thesis >= 0.50:
        support_points += 1
        reasons.append(f"Reddit thesis credible (thesis={thesis:.0%}, confidence={conf:.0%})")
    else:
        contradict_points += 1
        risk = signal.get("risk_acknowledgment", 0)
        data = signal.get("data_quality", 0)
        weak_why = []
        if thesis < 0.5:
            weak_why.append("vague thesis")
        if data < 0.5:
            weak_why.append("lacks data/sources")
        if risk < 0.5:
            weak_why.append("ignores risks")
        why_str = (", ".join(weak_why) + " — ") if weak_why else ""
        reasons.append(
            f"Reddit signal is weak (thesis={thesis:.0%}, confidence={conf:.0%}) — "
            f"{why_str}not enough evidence to act on this alone."
        )

    if revenue_growth is not None:
        if revenue_growth > 0.10:
            support_points += 1
            reasons.append(f"Revenue growing {revenue_growth:.0%} YoY — supports bullish thesis")
        elif revenue_growth < 0:
            contradict_points += 1
            reasons.append(f"Revenue declining {revenue_growth:.0%} YoY — contradicts bullish thesis")

    if pe is not None:
        if pe < 15:
            support_points += 1
            reasons.append(f"P/E {pe:.1f}x — cheap relative to market")
        elif pe > 60:
            contradict_points += 1
            reasons.append(f"P/E {pe:.1f}x — expensive, leaves little margin of safety")

    if target and price and price > 0:
        upside = (target - price) / price
        if upside > 0.15:
            support_points += 1
            reasons.append(f"Analyst target ${target:.0f} implies {upside:.0%} upside")
        elif upside < -0.05:
            contradict_points += 1
            reasons.append(f"Analyst target ${target:.0f} implies {upside:.0%} downside")

    if not reasons:
        return "⚪ NO DATA", "#8b949e", "No fundamental data available from yfinance."

    if support_points > contradict_points:
        badge, colour = "✅ SUPPORTS", "#00d4aa"
    elif contradict_points > support_points:
        badge, colour = "❌ CONTRADICTS", "#f85149"
    else:
        badge, colour = "⚠️ MIXED", "#d29922"

    return badge, colour, " · ".join(reasons)


def _render_signals_tab(params: dict) -> None:
    signals_raw, mode = _load_signals()

    # Refresh button
    hcol1, hcol2 = st.columns([5, 1])
    with hcol2:
        if st.button("🔄 Refresh", use_container_width=True):
            _load_signals.clear()
            st.rerun()

    if mode != "live":
        _demo_banner(mode)

    # Apply filters
    signals = signals_raw
    if params["min_confidence"] > 0:
        signals = [s for s in signals if s.get("confidence_level", 0) >= params["min_confidence"]]
    if params["investable_only"]:
        signals = [s for s in signals if s.get("is_investable", False)]

    if not signals:
        st.info(f"No signals match the current filters (min confidence: {params['min_confidence']:.0%}, investable only: {params['investable_only']}). Adjust the sidebar filters.")
        return

    # Deduplicate: best signal per ticker
    ticker_map: dict = {}
    for s in signals:
        t = s.get("ticker", "")
        if t and (t not in ticker_map or s.get("confidence_level", 0) > ticker_map[t].get("confidence_level", 0)):
            ticker_map[t] = s
    unique = sorted(ticker_map.values(), key=lambda s: s.get("confidence_level", 0), reverse=True)

    investable = [s for s in unique if s.get("is_investable", False)]
    avg_conf = sum(s.get("confidence_level", 0) for s in unique) / len(unique)
    top_ticker = unique[0].get("ticker", "—") if unique else "—"

    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Tickers", str(len(unique)))
    _metric(c2, "Investable", str(len(investable)))
    _metric(c3, "Avg Confidence", f"{avg_conf:.0%}")
    _metric(c4, "Top Pick", top_ticker)

    # ── Global synthesis ─────────────────────────────────────────────────────
    strong = [s for s in unique if s.get("confidence_level", 0) >= 0.65 and s.get("is_investable", False)]
    watch  = [s for s in unique if 0.45 <= s.get("confidence_level", 0) < 0.65]
    weak   = [s for s in unique if s.get("confidence_level", 0) < 0.45]

    top_picks = sorted(strong, key=lambda s: s.get("confidence_level", 0), reverse=True)[:3]
    top_names = ", ".join(f"**{s['ticker']}** ({s.get('confidence_level',0):.0%})" for s in top_picks)

    if strong:
        panorama = (
            f"🟢 **{len(strong)} ticker(s) com sinal investável** detectado(s) pelo Reddit + Qwen: {top_names}. "
            f"Estes posts têm tese estruturada e confiança suficiente para considerar posição. "
            f"Verifica o DDD de cada um para perceber se os fundamentais de mercado suportam ou contradizem."
        )
        border_col = "#00d4aa"
    elif watch:
        wnames = ", ".join(f"**{s['ticker']}**" for s in sorted(watch, key=lambda s: s.get("confidence_level",0), reverse=True)[:3])
        panorama = (
            f"🟡 **Nenhum sinal forte esta ronda**, mas {len(watch)} ticker(s) merecem atenção: {wnames}. "
            f"Os posts têm algum mérito mas faltam dados concretos ou reconhecimento de risco. "
            f"Aguarda mais sinais ou corre Module A com mais posts."
        )
        border_col = "#d29922"
    else:
        panorama = (
            f"🔴 **Nada a investir desta ronda.** {len(weak)} ticker(s) com sinal fraco — "
            f"os posts do Reddit não apresentam teses bem fundamentadas. "
            f"Tenta correr Module A com mais posts por subreddit (slider na sidebar)."
        )
        border_col = "#f85149"

    if len(unique) > 0:
        sectors_text = f"{len(unique)} unique tickers tracked this session."
        cond_icon_s, _, _ = _market_condition(unique)
        st.markdown(
            f'<div class="intel-brief">'
            f'<div class="intel-header">// INTEL BRIEF — NEURAL FEED ANALYSIS</div>'
            f'{cond_icon_s} {panorama}<br>'
            f'<span style="color:#484f58;font-size:11px;margin-top:6px;display:block;">'
            f'▸ {sectors_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Ticker cards (2 columns)
    cols = st.columns(2)
    for i, signal in enumerate(unique):
        ticker = signal.get("ticker", "?")
        conf = signal.get("confidence_level", 0)
        thesis = signal.get("thesis_score", 0)
        risk = signal.get("risk_acknowledgment", 0)
        is_inv = signal.get("is_investable", False)
        subreddit = signal.get("source_subreddit", "")
        explanation = signal.get("explanation", {})
        ts = signal.get("signal_timestamp", "")[:16].replace("T", " ")

        verdict_label, verdict_colour = _verdict(conf, thesis, is_inv)
        inv_badge = (
            '<span style="background:#00d4aa22;color:#00d4aa;padding:2px 6px;'
            'border-radius:4px;font-size:11px;margin-left:6px;">✓ investable</span>'
            if is_inv else ""
        )

        # Fetch market info (cached)
        info = _fetch_ticker_info(ticker)
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        change_pct = info.get("regularMarketChangePercent", 0) * 100 if info.get("regularMarketChangePercent") else None
        change_html = ""
        if change_pct is not None:
            cc = "#00d4aa" if change_pct >= 0 else "#f85149"
            change_html = f'<span style="color:{cc};font-size:13px;">{change_pct:+.2f}%</span>'

        ddd_badge, ddd_colour, ddd_reason = _ddd_verdict(signal, info)
        thesis_summary = (explanation or {}).get("thesis_clarity") or (explanation or {}).get("thesis_score", "")
        thesis_html = (
            f'<div style="color:#c9d1d9;font-size:12px;font-style:italic;margin:6px 0 8px;'
            f'border-left:2px solid #30363d;padding-left:8px;">{thesis_summary}</div>'
            if thesis_summary else ""
        )

        with cols[i % 2]:
            st.markdown(
                f"""
                <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                            padding:16px;margin-bottom:4px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="color:#e6edf3;font-size:22px;font-weight:700;">{ticker}{inv_badge}</span>
                    <span style="color:{verdict_colour};font-weight:600;font-size:14px;">{verdict_label}</span>
                  </div>
                  <div style="color:#8b949e;font-size:12px;margin:4px 0 4px;">
                    r/{subreddit} · {ts}{("  ·  $" + str(round(price, 2)) + " " + change_html) if price else ""}
                  </div>
                  {thesis_html}
                  <div style="display:flex;gap:20px;font-size:13px;">
                    <span>Confidence <b style="color:#e6edf3;">{conf:.0%}</b></span>
                    <span>Thesis <b style="color:#e6edf3;">{thesis:.0%}</b></span>
                    <span>Risk ACK <b style="color:#e6edf3;">{risk:.0%}</b></span>
                  </div>
                  <div style="margin-top:10px;padding:8px;background:#0d1117;border-radius:6px;">
                    <span style="color:{ddd_colour};font-weight:600;font-size:12px;">DDD {ddd_badge}</span>
                    <div style="color:#8b949e;font-size:12px;margin-top:4px;">{ddd_reason}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Expandable detail — no nested st.columns (Streamlit restriction)
            with st.expander("Full analysis"):
                if explanation:
                    for key, text in explanation.items():
                        st.markdown(f"**{key.replace('_', ' ').title()}:** {text}")
                else:
                    st.caption("No explanation available.")
                if info:
                    mkt_lines = []
                    mc = info.get("marketCap")
                    if mc:
                        mkt_lines.append(f"**Market Cap:** ${mc/1e9:.1f}B")
                    pe = info.get("trailingPE")
                    if pe:
                        mkt_lines.append(f"**P/E:** {pe:.1f}x")
                    rg = info.get("revenueGrowth")
                    if rg is not None:
                        mkt_lines.append(f"**Revenue Growth:** {rg:.0%}")
                    hi = info.get("fiftyTwoWeekHigh")
                    lo = info.get("fiftyTwoWeekLow")
                    if hi and lo:
                        mkt_lines.append(f"**52w Range:** ${lo:.2f} – ${hi:.2f}")
                    tgt = info.get("targetMeanPrice")
                    if tgt:
                        mkt_lines.append(f"**Analyst Target:** ${tgt:.2f}")
                    if mkt_lines:
                        st.markdown("  ·  ".join(mkt_lines))


# ─── Tab 2 — Forecasts ────────────────────────────────────────────────────────

def _render_forecasts_tab() -> None:
    forecasts_raw, mode = _load_forecasts()
    if mode != "live":
        _demo_banner(mode)

    # Filter controls
    c1, c2, c3 = st.columns(3)
    show_macro = c1.checkbox("Macro events", value=True)
    show_stock = c2.checkbox("Stock events", value=True)
    resolved_only = c3.checkbox("Resolved only", value=False)

    forecasts = forecasts_raw
    if not show_macro:
        forecasts = [f for f in forecasts if not f.get("is_macro_event", False)]
    if not show_stock:
        forecasts = [f for f in forecasts if f.get("is_macro_event", False)]
    if resolved_only:
        forecasts = [f for f in forecasts if f.get("resolved", False)]

    if not forecasts:
        st.info("No forecasts match the current filters.")
        return

    resolved = [f for f in forecasts if f.get("resolved", False)]
    macro_count = sum(1 for f in forecasts if f.get("is_macro_event", False))
    avg_prob = sum(f.get("forecast_probability", 0) for f in forecasts) / len(forecasts)

    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Total Forecasts", str(len(forecasts)))
    _metric(c2, "Resolved", str(len(resolved)))
    _metric(c3, "Avg Probability", f"{avg_prob:.0%}")
    _metric(c4, "Macro Events", str(macro_count))

    # ── Oracle synthesis ──────────────────────────────────────────────────────
    bullish_stock = [f for f in forecasts if not f.get("is_macro_event") and f.get("forecast_probability", 0) >= 0.6]
    high_macro = [f for f in forecasts if f.get("is_macro_event") and f.get("forecast_probability", 0) >= 0.6]
    top_pred = max(forecasts, key=lambda f: f.get("forecast_probability", 0)) if forecasts else None
    resolution_rate = len(resolved) / len(forecasts) if forecasts else 0

    brier_str = "N/A"
    calibration_str, calibration_color = "PENDING DATA", "#8b949e"
    if len(resolved) >= 2:
        probs_r   = [f["forecast_probability"] for f in resolved]
        actuals_r = [1 if f.get("actual_outcome") else 0 for f in resolved]
        brier_val = sum((p - a) ** 2 for p, a in zip(probs_r, actuals_r)) / len(probs_r)
        brier_str = f"{brier_val:.3f}"
        if brier_val < 0.10:
            calibration_str, calibration_color = "EXCELLENT", "#00d4aa"
        elif brier_val < 0.20:
            calibration_str, calibration_color = "GOOD", "#6e9eff"
        elif brier_val < 0.25:
            calibration_str, calibration_color = "ACCEPTABLE", "#d29922"
        else:
            calibration_str, calibration_color = "POOR", "#f85149"

    if avg_prob >= 0.65:
        bias_icon, bias_label, bias_color = "📈", "BULLISH BIAS", "#00d4aa"
        bias_text = f"{len(bullish_stock)} stock event(s) forecast at >60% — oracle leans bullish."
    elif avg_prob <= 0.40:
        bias_icon, bias_label, bias_color = "📉", "BEARISH / CAUTIOUS", "#f85149"
        bias_text = f"High uncertainty across {len(forecasts)} predictions — avg prob below 40%."
    else:
        bias_icon, bias_label, bias_color = "⚖️", "NEUTRAL / MIXED", "#d29922"
        bias_text = f"{len(bullish_stock)} bullish stock signal(s) · {len(high_macro)} elevated macro risk(s)."

    top_pred_html = ""
    if top_pred:
        tp_ticker = top_pred.get("ticker") or "MACRO"
        tp_prob   = top_pred.get("forecast_probability", 0)
        tp_event  = (top_pred.get("event") or "")[:90]
        top_pred_html = (
            f'<br><span style="color:#484f58;font-size:10px;letter-spacing:2px;">'
            f'HIGHEST CONFIDENCE</span>  '
            f'<span style="color:#e6edf3;">{tp_ticker}</span> · '
            f'<span style="color:#00d4aa;font-weight:700;">{tp_prob:.0%}</span> · '
            f'<span style="color:#8b949e;font-size:11px;">{tp_event}</span>'
        )

    st.markdown(
        f'<div class="intel-brief">'
        f'<div class="intel-header">// ORACLE STATUS — PREDICTION MATRIX ANALYSIS</div>'
        f'<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:10px;">'
        f'  <span><span style="color:#484f58;font-size:10px;letter-spacing:1px;">MARKET BIAS</span><br>'
        f'    <span style="color:{bias_color};font-weight:700;">{bias_icon} {bias_label}</span></span>'
        f'  <span><span style="color:#484f58;font-size:10px;letter-spacing:1px;">CALIBRATION</span><br>'
        f'    <span style="color:{calibration_color};font-weight:700;">{calibration_str}</span>'
        f'    <span style="color:#484f58;font-size:10px;"> (Brier {brier_str})</span></span>'
        f'  <span><span style="color:#484f58;font-size:10px;letter-spacing:1px;">RESOLVED</span><br>'
        f'    <span style="color:#e6edf3;font-weight:700;">{resolution_rate:.0%}</span>'
        f'    <span style="color:#484f58;font-size:10px;"> ({len(resolved)}/{len(forecasts)})</span></span>'
        f'  <span><span style="color:#484f58;font-size:10px;letter-spacing:1px;">AVG PROBABILITY</span><br>'
        f'    <span style="color:#e6edf3;font-weight:700;">{avg_prob:.0%}</span></span>'
        f'</div>'
        f'{bias_text}{top_pred_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Dataframe
    score_cols = ["forecast_probability", "confidence_level"]
    display_cols = ["event", "ticker", "is_macro_event", "resolved", "actual_outcome", "signal_timestamp"] + score_cols

    df = pd.DataFrame(forecasts)
    for col in display_cols:
        if col not in df.columns:
            df[col] = None

    df = df[display_cols].copy()
    df["signal_timestamp"] = pd.to_datetime(df["signal_timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    df["ticker"] = df["ticker"].fillna("macro")

    col_config = {
        col: st.column_config.ProgressColumn(
            col.replace("_", " ").title(),
            min_value=0.0,
            max_value=1.0,
            format="%.2f",
        )
        for col in score_cols
    }
    col_config["event"] = st.column_config.TextColumn("Event", width="large")
    col_config["ticker"] = st.column_config.TextColumn("Ticker")
    col_config["is_macro_event"] = st.column_config.CheckboxColumn("Macro")
    col_config["resolved"] = st.column_config.CheckboxColumn("Resolved")
    col_config["actual_outcome"] = st.column_config.CheckboxColumn("Outcome")
    col_config["signal_timestamp"] = st.column_config.TextColumn("Timestamp")

    st.dataframe(df, use_container_width=True, column_config=col_config, hide_index=True)

    # Calibration chart if enough resolved
    if len(resolved) >= 2:
        st.subheader("Forecast Calibration")

        probs = [f["forecast_probability"] for f in resolved]
        actuals = [1 if f.get("actual_outcome", False) else 0 for f in resolved]
        brier = sum((p - a) ** 2 for p, a in zip(probs, actuals)) / len(probs)

        st.caption(f"Brier Score: **{brier:.3f}** (lower = better; perfect = 0.0)")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=probs,
            y=actuals,
            mode="markers",
            marker=dict(color=ACCENT, size=12, opacity=0.8),
            name="Resolved forecast",
        ))
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1],
            mode="lines",
            line=dict(color="#8b949e", dash="dash"),
            name="Perfect calibration",
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#161b22",
            xaxis=dict(title="Forecast probability", range=[0, 1], gridcolor="#30363d"),
            yaxis=dict(title="Actual outcome (0/1)", range=[-0.1, 1.1], gridcolor="#30363d"),
            margin=dict(t=20, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        # Probability histogram as placeholder
        st.subheader("Forecast Probability Distribution")
        fig = px.histogram(
            [f["forecast_probability"] for f in forecasts],
            nbins=20,
            template="plotly_dark",
            color_discrete_sequence=[ACCENT],
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#161b22",
            xaxis=dict(title="Forecast probability", gridcolor="#30363d"),
            yaxis=dict(title="Count", gridcolor="#30363d"),
            margin=dict(t=20, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


# ─── Tab 3 — Portfolio ────────────────────────────────────────────────────────

def _render_portfolio_tab() -> None:
    from magicfinance.config import PORTFOLIO_VALUE_USD, RISK_FREE_RATE, FIXED_WEIGHTS

    investable, mode = _load_investable()
    if mode != "live":
        _demo_banner(mode)

    # Deduplicate by ticker — keep highest confidence per ticker
    ticker_map: dict = {}
    for s in investable:
        t = s.get("ticker")
        if t and (t not in ticker_map or s.get("confidence_level", 0) > ticker_map[t].get("confidence_level", 0)):
            ticker_map[t] = s
    signals = list(ticker_map.values())

    if not signals:
        # Hard fallback to demo tickers
        signals = [s for s in DEMO_SIGNALS if s["is_investable"]]
        ticker_map = {s["ticker"]: s for s in signals}
        mode = "empty"

    tickers = [s["ticker"] for s in signals]

    try:
        from magicfinance.portfolio import (
            compute_expected_return_fixed,
            scale_expected_returns,
            optimize_portfolio,
            portfolio_metrics,
            build_portfolio_positions,
        )
        from magicfinance.yfinance_client import (
            fetch_prices,
            compute_covariance_matrix,
            backtest_portfolio,
            benchmark_sp500,
        )

        # Expected returns
        raw = pd.Series(
            {
                s["ticker"]: compute_expected_return_fixed(
                    thesis_score=s.get("thesis_score", 0.5),
                    forecast_probability=s.get("forecast_probability", 0.5),
                    confidence_level=s.get("confidence_level", 0.5),
                    weights=FIXED_WEIGHTS,
                )
                for s in signals
            }
        )
        expected_returns = scale_expected_returns(raw)

        prices = fetch_prices(tickers)
        cov_matrix = compute_covariance_matrix(prices)

        weights = optimize_portfolio(expected_returns, cov_matrix, risk_free_rate=RISK_FREE_RATE)
        metrics = portfolio_metrics(weights, expected_returns, cov_matrix)

        c1, c2, c3, c4 = st.columns(4)
        _metric(c1, "Expected Return", f"{metrics['expected_return']:.1%}", "annualised")
        _metric(c2, "Volatility", f"{metrics['volatility']:.1%}", "annualised")
        _metric(c3, "Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
        _metric(c4, "Portfolio Value", f"${PORTFOLIO_VALUE_USD:,.0f}")

        sharpe = metrics["sharpe_ratio"]
        sharpe_label = "excellent" if sharpe > 1.5 else "good" if sharpe > 1.0 else "moderate" if sharpe > 0.5 else "low"
        _info_box(
            f"<b>Markowitz optimisation</b> finds the allocation that maximises the Sharpe ratio "
            f"(return per unit of risk) given the investable signals above. "
            f"Current Sharpe of <b>{sharpe:.2f} = {sharpe_label}</b>. "
            f"Expected annual return <b>{metrics['expected_return']:.1%}</b> at <b>{metrics['volatility']:.1%}</b> volatility. "
            f"The backtest below shows how this allocation would have performed over the past year."
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Enrich signals with expected_return + forecast_probability for position table
        for s in signals:
            s["expected_return"] = float(expected_returns.get(s["ticker"], 0))
            if "forecast_probability" not in s:
                s["forecast_probability"] = 0.5

        positions = build_portfolio_positions(weights, signals, total_value=PORTFOLIO_VALUE_USD)

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("Allocation")
            pos_df = pd.DataFrame(positions)
            if not pos_df.empty:
                fig_pie = px.pie(
                    pos_df,
                    names="ticker",
                    values="allocation_pct",
                    template="plotly_dark",
                    color_discrete_sequence=px.colors.sequential.Teal,
                )
                fig_pie.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=20, b=20),
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_right:
            st.subheader("Positions")
            if not pos_df.empty:
                st.dataframe(
                    pos_df,
                    use_container_width=True,
                    column_config={
                        "ticker": st.column_config.TextColumn("Ticker"),
                        "allocation_pct": st.column_config.ProgressColumn(
                            "Allocation", min_value=0.0, max_value=1.0, format="%.1%"
                        ),
                        "usd_value": st.column_config.NumberColumn("USD Value", format="$%.0f"),
                        "expected_return": st.column_config.NumberColumn("Exp. Return", format="%.1%"),
                        "confidence_level": st.column_config.ProgressColumn(
                            "Confidence", min_value=0.0, max_value=1.0, format="%.2f"
                        ),
                        "thesis_score": st.column_config.ProgressColumn(
                            "Thesis", min_value=0.0, max_value=1.0, format="%.2f"
                        ),
                        "forecast_probability": st.column_config.ProgressColumn(
                            "Forecast P", min_value=0.0, max_value=1.0, format="%.2f"
                        ),
                    },
                    hide_index=True,
                )

        # Backtest
        st.subheader("Backtest vs S&P 500")
        try:
            bt = backtest_portfolio(weights, prices, initial_value=PORTFOLIO_VALUE_USD)
            start_date = prices.index[0].strftime("%Y-%m-%d")
            sp = benchmark_sp500(start_date=start_date, initial_value=PORTFOLIO_VALUE_USD)

            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(
                x=bt.index,
                y=bt["portfolio_value"],
                mode="lines",
                name="MagicFinance Portfolio",
                line=dict(color=ACCENT, width=2),
            ))
            if not sp.empty:
                fig_bt.add_trace(go.Scatter(
                    x=sp.index,
                    y=sp["portfolio_value"],
                    mode="lines",
                    name="S&P 500",
                    line=dict(color="#8b949e", width=1.5, dash="dot"),
                ))
            fig_bt.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#161b22",
                xaxis=dict(gridcolor="#30363d"),
                yaxis=dict(gridcolor="#30363d", tickprefix="$"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig_bt, use_container_width=True)
        except Exception as e:
            st.info(f"Backtest unavailable: {e}")

    except Exception:
        # Equal-weight fallback
        st.warning("Portfolio optimisation failed. Showing equal-weight allocation.")
        n = len(tickers)
        if n == 0:
            tickers = DEMO_TICKERS
            n = len(tickers)

        weights_eq = pd.Series(1 / n, index=tickers)
        pos_df = pd.DataFrame([
            {
                "ticker": t,
                "allocation_pct": 1 / n,
                "usd_value": PORTFOLIO_VALUE_USD / n,
            }
            for t in tickers
        ])

        c1, c2, c3, c4 = st.columns(4)
        _metric(c1, "Expected Return", "—")
        _metric(c2, "Volatility", "—")
        _metric(c3, "Sharpe Ratio", "—")
        _metric(c4, "Portfolio Value", f"${PORTFOLIO_VALUE_USD:,.0f}")
        st.markdown("<br>", unsafe_allow_html=True)

        fig_pie = px.pie(
            pos_df,
            names="ticker",
            values="allocation_pct",
            template="plotly_dark",
            color_discrete_sequence=px.colors.sequential.Teal,
        )
        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)


# ─── Tab 4 — Investor Arena ───────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _load_sim_events() -> list[dict]:
    try:
        from magicfinance.qdrant_client import get_sim_events
        return get_sim_events(limit=1000)
    except Exception:
        return []


def _render_arena_tab(qdrant_ok: bool) -> None:
    from magicfinance.investors import INVESTORS
    from magicfinance.simulation import (
        load_portfolios,
        get_portfolio_value,
        portfolio_pnl_pct,
        reset_portfolios,
        INITIAL_CAPITAL,
    )
    from magicfinance.llm_client import MODEL_4B_PATH, MODEL_9B_PATH

    arena_signals, _ = _load_signals()
    arena_cond_icon, arena_cond_label, arena_cond_color = _market_condition(arena_signals)
    _early_portfolios = load_portfolios()
    n_ticks = max(
        (len(_early_portfolios.get(inv["id"], {}).get("history", [])) for inv in INVESTORS),
        default=0,
    )

    st.markdown(
        f'<div class="market-hud">'
        f'<div class="hud-item"><span class="hud-label">MARKET</span>'
        f'<span class="hud-value" style="color:{arena_cond_color};">{arena_cond_icon} {arena_cond_label}</span></div>'
        f'<div class="hud-item"><span class="hud-label">TICKS RUN</span>'
        f'<span class="hud-value">{n_ticks}</span></div>'
        f'<div class="hud-item"><span class="hud-label">NETRUNNERS</span>'
        f'<span class="hud-value">10 ACTIVE</span></div>'
        f'<div class="hud-item"><span class="hud-label">SIGNALS IN FEED</span>'
        f'<span class="hud-value">{len(arena_signals)}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _info_box(
        "<b>10 netrunners</b> jacked into the market, each starting with €1,000 and making autonomous "
        "BUY/SELL/HOLD decisions based on the Reddit neural feed. Each has a unique class, risk profile, "
        "and personality — powered by Qwen 3.5. Click <b>▶ Run Tick</b> to trigger the next round. "
        "Earn XP, unlock achievements, and climb the standings."
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    mlx = _load_mlx_health()
    model_available = mlx.get("model_4b_exists", False) or mlx.get("model_9b_exists", False)

    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([2, 1, 1, 1])

    with ctrl_col1:
        model_choice = st.radio(
            "Model",
            ["Qwen 4B (faster)", "Qwen 9B (smarter)"],
            horizontal=True,
            label_visibility="collapsed",
        )
    model_path = MODEL_4B_PATH if "4B" in model_choice else MODEL_9B_PATH

    run_tick = False
    do_reset = False
    with ctrl_col2:
        if not qdrant_ok or not model_available:
            st.button("▶ Run Tick", disabled=True, use_container_width=True)
            if not qdrant_ok:
                st.caption("Qdrant offline")
            elif not model_available:
                st.caption("MLX model missing")
        else:
            run_tick = st.button("▶ Run Tick", use_container_width=True)

    with ctrl_col3:
        do_reset = st.button("🔄 Reset €1k", use_container_width=True)

    with ctrl_col4:
        signals_raw, _ = _load_signals()
        st.caption(f"{len(signals_raw)} signals available")

    # ── Execute tick ──────────────────────────────────────────────────────────
    if run_tick:
        signals_raw, _ = _load_signals()
        tickers = list({s.get("ticker") for s in signals_raw if s.get("ticker")})
        prices: dict = {}
        try:
            from magicfinance.yfinance_client import fetch_prices
            if tickers:
                price_df = fetch_prices(tickers, lookback_days=5)
                if not price_df.empty:
                    prices = price_df.iloc[-1].to_dict()
        except Exception:
            pass

        # Fill missing prices with 0 so simulation doesn't crash
        for s in signals_raw:
            t = s.get("ticker", "")
            if t and t not in prices:
                prices[t] = 0.0

        with st.spinner("Running simulation tick — all 10 investors deciding…"):
            try:
                from magicfinance.simulation import run_tick as _run_tick
                events, tick_log = _run_tick(signals_raw, prices, model_path)
                if qdrant_ok:
                    from magicfinance.qdrant_client import upsert_sim_event
                    for ev in events:
                        try:
                            upsert_sim_event(ev)
                        except Exception:
                            pass
                _load_sim_events.clear()
                buy_sell = [e for e in events if e.get("action") in ("BUY", "SELL")]
                st.success(f"Tick complete — {len(buy_sell)} BUY/SELL decisions from {len(tick_log)} investors.")

                # Debug expander — always shown so you can diagnose 0-decision ticks
                with st.expander("🔍 Debug: LLM responses this tick"):
                    no_prices = [t for t, p in prices.items() if p == 0]
                    if no_prices:
                        st.warning(f"Prices unavailable ($0) for: {', '.join(no_prices)} — investors may abstain.")
                    for log in tick_log:
                        colour = "green" if log["decisions"] else "orange" if not log["error"] else "red"
                        st.markdown(
                            f"**{log['investor_name']}** — "
                            f":{colour}[{len(log['decisions'])} decision(s)]"
                            + (f" ⚠️ `{log['error']}`" if log["error"] else "")
                        )
                        if log["raw_response"]:
                            st.code(log["raw_response"], language="json")
            except Exception as e:
                st.error(f"Tick failed: {e}")
                traceback.print_exc()

    if do_reset:
        reset_portfolios()
        _load_sim_events.clear()
        st.success("All portfolios reset to €1,000.")
        st.rerun()

    # ── Load state ────────────────────────────────────────────────────────────
    portfolios = load_portfolios()
    sim_events = _load_sim_events()

    # Build last-decision map per investor
    last_decision: dict[str, dict] = {}
    for ev in sorted(sim_events, key=lambda e: e.get("timestamp", "")):
        if ev.get("action") in ("BUY", "SELL"):
            last_decision[ev["investor_id"]] = ev

    # Need prices for current portfolio values
    all_tickers = set()
    for p in portfolios.values():
        all_tickers.update(p.get("holdings", {}).keys())
    live_prices: dict = {}
    if all_tickers:
        try:
            from magicfinance.yfinance_client import fetch_prices
            pdf = fetch_prices(list(all_tickers), lookback_days=5)
            if not pdf.empty:
                live_prices = pdf.iloc[-1].to_dict()
        except Exception:
            pass

    # ── Investor cards grid ───────────────────────────────────────────────────
    st.markdown(
        '<div style="font-family:\'Share Tech Mono\',monospace;font-size:11px;'
        'color:#484f58;letter-spacing:2px;margin-bottom:10px;">// NETRUNNER STANDINGS</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    sorted_investors = sorted(
        INVESTORS,
        key=lambda inv: get_portfolio_value(portfolios.get(inv["id"], {}), live_prices),
        reverse=True,
    )

    for i, investor in enumerate(sorted_investors):
        inv_id = investor["id"]
        portfolio = portfolios.get(inv_id, {"cash": INITIAL_CAPITAL, "holdings": {}, "history": []})
        value = get_portfolio_value(portfolio, live_prices)
        pnl = portfolio_pnl_pct(portfolio, live_prices)
        cash = portfolio.get("cash", INITIAL_CAPITAL)
        n_holdings = len(portfolio.get("holdings", {}))

        # RPG level — only promoted from RECRUIT after first trade
        inv_trades = [e for e in sim_events if e.get("investor_id") == inv_id and e.get("action") in ("BUY", "SELL")]
        has_traded = len(inv_trades) > 0
        lvl_emoji, lvl_title, lvl_color = _investor_level(pnl, has_traded)
        xp_progress, xp_next = _xp_progress(pnl, has_traded)
        xp_pct = int(xp_progress * 100)

        # Achievements
        badges = _achievements(portfolio, inv_id, sim_events)
        badges_html = "".join(
            f'<span class="ach-pill">{e} {lbl}</span>'
            for e, lbl in badges[:3]  # max 3 shown
        )

        # Last trade
        last = last_decision.get(inv_id)
        if last:
            act_color = "#00d4aa" if last["action"] == "BUY" else "#f85149"
            last_html = (
                f'<span style="color:{act_color};font-weight:700;font-family:monospace;">'
                f'{last["action"]} {last.get("ticker","")}</span>'
                f' <span style="color:#8b949e;font-size:11px;">'
                f'{last.get("reasoning","")[:70]}…</span>'
            )
        else:
            last_html = '<span style="color:#484f58;font-size:11px;font-family:monospace;">[ AWAITING ORDERS ]</span>'

        pnl_colour = "#00d4aa" if pnl >= 0 else "#f85149"
        rank = i + 1
        rank_icon = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"<span style='font-family:monospace;color:#484f58;'>#{rank}</span>")
        card_rank_class = {1: "rank-1", 2: "rank-2", 3: "rank-3"}.get(rank, "")

        holdings_tickers = " · ".join(portfolio.get("holdings", {}).keys()) or "—"

        # Build financial DNA tags for this investor
        dna = _FINANCIAL_DNA.get(inv_id, {})
        dna_tags_html = "".join(
            f'<span style="background:#21262d;border:1px solid #30363d;border-radius:4px;'
            f'padding:2px 7px;font-size:10px;color:#8b949e;margin:2px;display:inline-block;">'
            f'{m}</span>'
            for m in dna.get("metrics", [])
        )

        risk_colors = {
            "very_low": "#8b949e", "low": "#6e9eff", "medium": "#d29922",
            "high": "#ff8c00", "very_high": "#f85149", "bimodal": "#c678dd",
        }
        risk_labels = {
            "very_low": "VERY LOW", "low": "LOW", "medium": "MEDIUM",
            "high": "HIGH", "very_high": "VERY HIGH", "bimodal": "BIMODAL",
        }
        risk_bars = {"very_low": 10, "low": 25, "medium": 50, "high": 75, "very_high": 95, "bimodal": 65}
        risk_col  = risk_colors.get(investor["risk_tolerance"], "#8b949e")
        risk_lbl  = risk_labels.get(investor["risk_tolerance"], "?")
        risk_bar  = risk_bars.get(investor["risk_tolerance"], 50)

        with cols[i % 2]:
            # Card — no bottom border-radius so popover footer attaches seamlessly
            st.markdown(
                f"""
                <div class="inv-card {card_rank_class}"
                     style="border-radius:10px 10px 0 0;margin-bottom:0;">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                    <span style="font-size:22px;">{investor['emoji']}</span>
                    <div style="text-align:right;">
                      {rank_icon}
                      <div>
                        <span class="level-badge"
                              style="background:{lvl_color}22;color:{lvl_color};border:1px solid {lvl_color}44;">
                          {lvl_emoji} {lvl_title}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div style="color:#e6edf3;font-weight:700;font-size:15px;">{investor['name']}</div>
                  <div style="color:#8b949e;font-size:11px;font-family:monospace;letter-spacing:1px;margin-bottom:6px;">
                    {investor['style'].upper()}
                  </div>
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">
                    <div class="xp-track" style="flex:1;">
                      <div class="xp-fill" style="width:{xp_pct}%;"></div>
                    </div>
                    <span style="font-size:10px;color:#484f58;font-family:monospace;white-space:nowrap;">{xp_next}</span>
                  </div>
                  <div style="display:flex;align-items:baseline;gap:12px;margin:8px 0 4px;">
                    <span style="color:#e6edf3;font-size:20px;font-weight:700;font-family:monospace;">€{value:.0f}</span>
                    <span style="color:{pnl_colour};font-size:14px;font-weight:600;">{pnl:+.1f}%</span>
                  </div>
                  <div style="color:#484f58;font-size:11px;font-family:monospace;margin-bottom:6px;">
                    CASH €{cash:.0f} · {n_holdings} POS · {holdings_tickers[:28]}
                  </div>
                  <div style="font-size:12px;border-top:1px solid #21262d;padding-top:6px;margin-top:4px;">
                    {last_html}
                  </div>
                  <div style="margin-top:6px;">{badges_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # ── Seamless popover footer ──────────────────────────────────────
            with st.popover("◈  NETRUNNER PROFILE", use_container_width=True):
                st.markdown(
                    f"""
                    <div style="font-family:'Share Tech Mono',monospace;">
                      <div style="display:flex;align-items:center;gap:12px;
                                  border-bottom:1px solid #30363d;padding-bottom:12px;margin-bottom:14px;">
                        <span style="font-size:36px;">{investor['emoji']}</span>
                        <div>
                          <div style="color:#e6edf3;font-size:16px;font-weight:700;">{investor['name']}</div>
                          <div style="color:#00d4aa;font-size:10px;letter-spacing:3px;">{investor['style'].upper()}</div>
                          <div style="margin-top:4px;">
                            <span class="level-badge" style="background:{lvl_color}22;color:{lvl_color};border:1px solid {lvl_color}44;">
                              {lvl_emoji} {lvl_title} · P&L <span style="color:{pnl_colour};">{pnl:+.1f}%</span>
                            </span>
                          </div>
                        </div>
                      </div>
                      <div style="color:#484f58;font-size:9px;letter-spacing:3px;margin-bottom:6px;">// FINANCIAL DNA</div>
                      <div style="margin-bottom:12px;">{dna_tags_html}</div>
                      <div style="color:#484f58;font-size:9px;letter-spacing:3px;margin-bottom:4px;">// RISK PROFILE</div>
                      <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">
                        <div style="flex:1;background:#21262d;border-radius:3px;height:6px;overflow:hidden;">
                          <div style="width:{risk_bar}%;height:100%;background:linear-gradient(90deg,#6e9eff,{risk_col});border-radius:3px;"></div>
                        </div>
                        <span style="color:{risk_col};font-size:10px;font-weight:700;">{risk_lbl}</span>
                      </div>
                      <div style="color:#484f58;font-size:10px;margin-bottom:12px;">
                        Max single bet: <span style="color:#e6edf3;">{investor['max_single_bet_pct']*100:.0f}%</span>
                        &nbsp;·&nbsp;
                        Horizon: <span style="color:#e6edf3;">{dna.get('horizon','—')}</span>
                      </div>
                      <div style="display:flex;gap:10px;margin-bottom:12px;">
                        <div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 10px;">
                          <div style="color:#484f58;font-size:9px;letter-spacing:2px;margin-bottom:4px;">SIZING</div>
                          <div style="color:#c9d1d9;font-size:11px;">{dna.get('position_sizing','—')}</div>
                        </div>
                        <div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 10px;">
                          <div style="color:#484f58;font-size:9px;letter-spacing:2px;margin-bottom:4px;">EXIT TRIGGER</div>
                          <div style="color:#c9d1d9;font-size:11px;">{dna.get('exit_trigger','—')}</div>
                        </div>
                      </div>
                      <div style="color:#484f58;font-size:9px;letter-spacing:3px;margin-bottom:6px;">// PERSONALITY</div>
                      <div style="color:#8b949e;font-size:12px;font-style:italic;line-height:1.5;
                                  border-left:2px solid #30363d;padding-left:10px;margin-bottom:12px;">
                        "{investor['personality']}"
                      </div>
                      <div style="color:#484f58;font-size:9px;letter-spacing:3px;margin-bottom:6px;">// STRATEGY</div>
                      <div style="color:#c9d1d9;font-size:12px;line-height:1.5;margin-bottom:10px;">
                        {investor['strategy']}
                      </div>
                      <div style="color:#21262d;font-size:10px;text-align:right;border-top:1px solid #21262d;padding-top:8px;">
                        Benchmark: {dna.get('benchmark','—')}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ── Performance chart ─────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-family:\'Share Tech Mono\',monospace;font-size:11px;'
        'color:#484f58;letter-spacing:2px;margin:16px 0 8px;">// PORTFOLIO TELEMETRY</div>',
        unsafe_allow_html=True,
    )

    fig_perf = go.Figure()
    colours = px.colors.qualitative.Plotly
    has_history = False

    for j, investor in enumerate(INVESTORS):
        history = portfolios.get(investor["id"], {}).get("history", [])
        if len(history) >= 2:
            has_history = True
            times = [h["timestamp"] for h in history]
            values = [h["value"] for h in history]
            fig_perf.add_trace(go.Scatter(
                x=times,
                y=values,
                mode="lines",
                name=f"{investor['emoji']} {investor['name']}",
                line=dict(color=colours[j % len(colours)], width=1.5),
            ))

    if has_history:
        fig_perf.add_hline(
            y=INITIAL_CAPITAL,
            line_dash="dash",
            line_color="#8b949e",
            annotation_text="Starting €1,000",
            annotation_position="right",
        )
        fig_perf.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#161b22",
            xaxis=dict(gridcolor="#30363d"),
            yaxis=dict(gridcolor="#30363d", tickprefix="€"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=40, b=20),
            height=350,
        )
        st.plotly_chart(fig_perf, use_container_width=True)
    else:
        st.info("Run at least 2 ticks to see the performance chart.")

    # ── Decision log ──────────────────────────────────────────────────────────
    if sim_events:
        st.markdown(
            '<div style="font-family:\'Share Tech Mono\',monospace;font-size:11px;'
            'color:#484f58;letter-spacing:2px;margin:16px 0 8px;">// COMBAT LOG</div>',
            unsafe_allow_html=True,
        )
        action_events = [e for e in sim_events if e.get("action") in ("BUY", "SELL")]
        action_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        if action_events:
            log_df = pd.DataFrame(action_events[:50])[
                ["timestamp", "investor_name", "action", "ticker", "amount_eur", "price_usd", "reasoning", "portfolio_value", "pnl_pct"]
            ]
            log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce").dt.strftime("%m-%d %H:%M")
            st.dataframe(
                log_df,
                use_container_width=True,
                column_config={
                    "timestamp": st.column_config.TextColumn("Time"),
                    "investor_name": st.column_config.TextColumn("Investor"),
                    "action": st.column_config.TextColumn("Action"),
                    "ticker": st.column_config.TextColumn("Ticker"),
                    "amount_eur": st.column_config.NumberColumn("Amount", format="€%.0f"),
                    "price_usd": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "reasoning": st.column_config.TextColumn("Reasoning", width="large"),
                    "portfolio_value": st.column_config.NumberColumn("Portfolio", format="€%.0f"),
                    "pnl_pct": st.column_config.NumberColumn("P&L %", format="%.1f%%"),
                },
                hide_index=True,
            )
        else:
            st.info("No BUY/SELL decisions yet. Run a tick to start.")


# ─── Watchdog Tab ─────────────────────────────────────────────────────────────

def _render_watchdog_tab(params: dict) -> None:
    """Show Reddit signals as ticker cards with price chart + full DDD breakdown."""
    signals, is_demo = _load_signals()

    if is_demo:
        st.markdown(
            '<div class="demo-banner">⚠ DEMO MODE — connect Qdrant to see live watchdog data</div>',
            unsafe_allow_html=True,
        )

    if not signals:
        st.info("No signals found. Run Module A to populate.")
        return

    # Apply filters
    min_conf = params.get("min_confidence", 0.0)
    inv_only = params.get("investable_only", False)
    filtered = [s for s in signals if s.get("confidence_level", 0) >= min_conf]
    if inv_only:
        filtered = [s for s in filtered if s.get("is_investable")]

    if not filtered:
        st.warning("No signals match current filters.")
        return

    # ── Ticker selector ──────────────────────────────────────────────────────
    tickers = list({s.get("ticker", "") for s in filtered if s.get("ticker")})
    tickers.sort()

    col_sel, col_info = st.columns([2, 5])
    with col_sel:
        st.markdown(
            '<div style="font-family:\'Share Tech Mono\',monospace;font-size:11px;color:#484f58;'
            'letter-spacing:1px;margin-bottom:4px;">// SELECT TICKER</div>',
            unsafe_allow_html=True,
        )
        selected = st.selectbox("Ticker", tickers, label_visibility="collapsed")

    # Filter to selected ticker signals
    ticker_signals = [s for s in filtered if s.get("ticker") == selected]
    if not ticker_signals:
        st.info("No signals for selected ticker.")
        return
    sig = ticker_signals[0]  # most recent

    verdict_map = {
        "STRONG BUY": ("#00d4aa", "▲▲"),
        "BUY":        ("#39d353", "▲"),
        "WATCH":      ("#d29922", "◆"),
        "HOLD":       ("#8b949e", "■"),
        "WEAK":       ("#f85149", "▼"),
        "SELL":       ("#f85149", "▼▼"),
    }
    verdict = sig.get("verdict", sig.get("recommendation", "WATCH")).upper()
    v_color, v_icon = verdict_map.get(verdict, ("#8b949e", "■"))

    with col_info:
        conf = sig.get("confidence_level", 0)
        subreddit = sig.get("source_subreddit", "unknown")
        ts = sig.get("signal_timestamp", "")[:16].replace("T", " ")
        is_inv = sig.get("is_investable", False)
        inv_badge = '<span style="color:#00d4aa;font-size:11px;margin-left:8px;">● INVESTABLE</span>' if is_inv else ""
        st.markdown(
            f'<div style="font-family:\'Share Tech Mono\',monospace;">'
            f'<span style="font-size:28px;color:{v_color};font-weight:700;">{selected}</span>'
            f'<span style="font-size:16px;color:{v_color};margin-left:12px;">{v_icon} {verdict}</span>'
            f'{inv_badge}'
            f'<div style="font-size:11px;color:#484f58;margin-top:2px;">r/{subreddit} · {ts} UTC · conf: {conf:.0%}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    left, right = st.columns([3, 2])

    # ── Score breakdown ──────────────────────────────────────────────────────
    with left:
        st.markdown(
            '<div style="font-family:\'Share Tech Mono\',monospace;font-size:11px;'
            'color:#484f58;letter-spacing:1px;margin-bottom:8px;">// DUE DILIGENCE BREAKDOWN</div>',
            unsafe_allow_html=True,
        )
        score_fields = [
            ("confidence_level",   "CONFIDENCE"),
            ("thesis_score",       "THESIS"),
            ("risk_acknowledgment","RISK ACK"),
            ("data_quality",       "DATA QUALITY"),
            ("specificity",        "SPECIFICITY"),
            ("original_thinking",  "ORIGINALITY"),
        ]
        bars_html = ""
        for key, label in score_fields:
            val = sig.get(key, 0)
            pct = int(val * 100)
            color = "#00d4aa" if val >= 0.7 else "#d29922" if val >= 0.4 else "#f85149"
            bars_html += (
                f'<div class="wd-bar-row">'
                f'<span class="wd-bar-label">{label}</span>'
                f'<div class="wd-bar-track"><div class="wd-bar-fill" style="width:{pct}%;background:{color};"></div></div>'
                f'<span class="wd-bar-val">{val:.2f}</span>'
                f'</div>'
            )
        st.markdown(f'<div class="wd-card">{bars_html}</div>', unsafe_allow_html=True)

        # Thesis summary
        thesis = sig.get("thesis_summary", sig.get("summary", ""))
        if thesis:
            st.markdown(
                f'<div class="intel-brief">'
                f'<div class="intel-header">// THESIS</div>'
                f'{thesis}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Risk factors
        risks = sig.get("risk_factors", [])
        if risks:
            risk_items = "".join(f"<li style='margin:3px 0;'>{r}</li>" for r in risks[:5])
            st.markdown(
                f'<div class="intel-brief" style="border-left-color:#f85149;">'
                f'<div class="intel-header" style="color:#f85149;">// RISK FACTORS</div>'
                f'<ul style="margin:6px 0 0 16px;padding:0;">{risk_items}</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Price chart ──────────────────────────────────────────────────────────
    with right:
        st.markdown(
            '<div style="font-family:\'Share Tech Mono\',monospace;font-size:11px;'
            'color:#484f58;letter-spacing:1px;margin-bottom:8px;">// PRICE CHART (30D)</div>',
            unsafe_allow_html=True,
        )
        try:
            from magicfinance.yfinance_client import fetch_prices
            price_df = fetch_prices([selected], lookback_days=30)
            if not price_df.empty and selected in price_df.columns:
                prices = price_df[selected].dropna()
                fig = go.Figure()
                pct_chg = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0] if len(prices) > 1 else 0
                line_color = "#00d4aa" if pct_chg >= 0 else "#f85149"
                fig.add_trace(go.Scatter(
                    x=prices.index, y=prices.values,
                    mode="lines",
                    line=dict(color=line_color, width=2),
                    fill="tozeroy",
                    fillcolor=f"{line_color}15",
                    name=selected,
                ))
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=20, b=0),
                    height=220,
                    showlegend=False,
                    xaxis=dict(showgrid=False, color="#484f58"),
                    yaxis=dict(showgrid=True, gridcolor="#21262d", color="#484f58"),
                    annotations=[dict(
                        x=0.02, y=0.95, xref="paper", yref="paper",
                        text=f"{'▲' if pct_chg>=0 else '▼'} {pct_chg:+.1%} (30d)",
                        showarrow=False,
                        font=dict(color=line_color, size=13, family="Share Tech Mono"),
                    )],
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No price data available for this ticker.")
        except Exception as e:
            st.warning(f"Price fetch failed: {e}")

    # ── All signals for this ticker ──────────────────────────────────────────
    if len(ticker_signals) > 1:
        st.markdown("---")
        st.markdown(
            f'<div style="font-family:\'Share Tech Mono\',monospace;font-size:11px;'
            f'color:#484f58;letter-spacing:1px;margin-bottom:8px;">// ALL SIGNALS FOR {selected} ({len(ticker_signals)})</div>',
            unsafe_allow_html=True,
        )
        rows = []
        for s in ticker_signals:
            rows.append({
                "Timestamp": s.get("signal_timestamp", "")[:16],
                "Subreddit": s.get("source_subreddit", ""),
                "Confidence": s.get("confidence_level", 0),
                "Thesis": s.get("thesis_score", 0),
                "Investable": "✅" if s.get("is_investable") else "—",
                "Verdict": s.get("verdict", s.get("recommendation", "")),
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
                "Thesis":     st.column_config.ProgressColumn("Thesis",     min_value=0, max_value=1),
            },
        )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    params = _render_mission_control()

    if params["run_clicked"]:
        try:
            _run_pipeline(params["posts_per_sub"])
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            traceback.print_exc()

    if params.get("run_d_clicked"):
        try:
            _run_module_d()
        except Exception as e:
            st.error(f"Module D error: {e}")
            traceback.print_exc()

    # ── Cyberpunk header ───────────────────────────────────────────────────────
    signals_for_hud, _ = _load_signals()
    cond_icon, cond_label, cond_color = _market_condition(signals_for_hud)
    investable_count = sum(1 for s in signals_for_hud if s.get("is_investable"))
    avg_conf = (
        sum(s.get("confidence_level", 0) for s in signals_for_hud) / len(signals_for_hud)
        if signals_for_hud else 0.0
    )
    qdrant_status = "● ONLINE" if params["qdrant_ok"] else "● OFFLINE"
    qdrant_color = "#00d4aa" if params["qdrant_ok"] else "#f85149"
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    st.markdown(
        f"""
        <div style="margin-bottom:4px;">
          <span class="cp-title shimmer-text">MAGICFINANCE</span>
        </div>
        <div class="cp-subtitle">NEURAL INVESTMENT INTERFACE · REDDIT SIGNAL PIPELINE</div>
        <div class="market-hud" style="margin-top:14px;">
          <div class="hud-item">
            <span class="hud-label">SYSTEM</span>
            <span class="hud-value" style="color:{qdrant_color};">
              <span class="live-dot" style="background:{qdrant_color};"></span>{qdrant_status.replace('● ','')}</span>
          </div>
          <div class="hud-item">
            <span class="hud-label">MARKET STATUS</span>
            <span class="hud-value" style="color:{cond_color};">{cond_icon} {cond_label}</span>
          </div>
          <div class="hud-item">
            <span class="hud-label">SIGNALS LOADED</span>
            <span class="hud-value">{len(signals_for_hud)} total · {investable_count} investable</span>
          </div>
          <div class="hud-item">
            <span class="hud-label">AVG CONFIDENCE</span>
            <span class="hud-value">{avg_conf:.0%}</span>
          </div>
          <div class="hud-item">
            <span class="hud-label">TIMESTAMP</span>
            <span class="hud-value">{now_str}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Matrix rain (canvas injected into parent frame via same-origin iframe) ──
    components.html(
        """
        <script>
        (function() {
            if (parent.document.getElementById('mf-matrix-canvas')) return;
            var canvas = parent.document.createElement('canvas');
            canvas.id = 'mf-matrix-canvas';
            canvas.style.cssText = [
                'position:fixed','top:0','left:0',
                'width:100vw','height:100vh',
                'z-index:0','pointer-events:none','opacity:0.038',
            ].join(';');
            parent.document.body.appendChild(canvas);
            var ctx = canvas.getContext('2d');
            function resize() {
                canvas.width  = parent.window.innerWidth;
                canvas.height = parent.window.innerHeight;
            }
            resize();
            parent.window.addEventListener('resize', resize);
            var chars = '01アイウエカキ$€₿∑∂∞ABCDEF9873';
            var cols  = Math.floor(canvas.width / 16);
            var drops = Array.from({length: cols}, () => Math.random() * canvas.height / 16 | 0);
            function draw() {
                ctx.fillStyle = 'rgba(13,17,23,0.055)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                for (var i = 0; i < drops.length; i++) {
                    var c = chars[Math.random() * chars.length | 0];
                    ctx.fillStyle = Math.random() > 0.97 ? '#ffffff' : '#00d4aa';
                    ctx.globalAlpha = Math.random() * 0.6 + 0.15;
                    ctx.font = '13px monospace';
                    ctx.fillText(c, i * 16, drops[i] * 16);
                    if (drops[i] * 16 > canvas.height && Math.random() > 0.97) drops[i] = 0;
                    drops[i]++;
                }
                ctx.globalAlpha = 1;
            }
            setInterval(draw, 55);
        })();
        </script>
        """,
        height=0,
        scrolling=False,
    )

    # ── Ticker tape ───────────────────────────────────────────────────────────
    tickers_live = [s.get("ticker", "") for s in signals_for_hud if s.get("ticker")]
    tape_items = "  ·  ".join(
        f"{t}  {s.get('confidence_level',0):.0%}" for t, s in zip(
            tickers_live,
            signals_for_hud,
        )
    ) or "NO SIGNAL DATA — RUN MODULE A TO POPULATE THE NEURAL FEED"
    tape_text = f"▸ MAGICFINANCE NEURAL FEED  ·  {tape_items}  ·  " * 3
    st.markdown(
        f'<div class="ticker-wrap"><span class="ticker-inner">{tape_text}</span></div>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚡ Neural Feed",
        "🔮 Oracle Matrix",
        "💼 Net Worth",
        "⚔️ The Arena",
        "📡 Watchdog",
    ])

    with tab1:
        _render_signals_tab(params)

    with tab2:
        _render_forecasts_tab()

    with tab3:
        _render_portfolio_tab()

    with tab4:
        _render_arena_tab(params["qdrant_ok"])

    with tab5:
        _render_watchdog_tab(params)


if __name__ == "__main__":
    main()
