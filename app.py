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

# ─── Page config (must be first Streamlit call) ───────────────────────────────

st.set_page_config(
    page_title="MagicFinance",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
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

    /* ── Signal verdict pill (animated for STRONG BUY) ── */
    @keyframes verdict-pulse {
        0%,100% { box-shadow:0 0 0px #00d4aa00; }
        50%      { box-shadow:0 0 10px #00d4aa60; }
    }
    .verdict-strong {
        animation: verdict-pulse 2s ease-in-out infinite;
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


# ─── Gamification helpers ─────────────────────────────────────────────────────

# (threshold_pnl_pct, emoji, title, hex_color)
_LEVELS = [
    (10.0, "🏆", "LEGEND",  "#ffd700"),
    ( 5.0, "💎", "ELITE",   "#00d4aa"),
    ( 2.0, "🔥", "VETERAN", "#ff8c00"),
    ( 0.0, "⚔️", "SOLDIER", "#6e9eff"),
    (-99,  "🌱", "RECRUIT", "#8b949e"),
]


def _investor_level(pnl_pct: float) -> tuple[str, str, str]:
    """Return (emoji, title, hex_color) based on P&L %."""
    for threshold, emoji, title, color in _LEVELS:
        if pnl_pct >= threshold:
            return emoji, title, color
    return "🌱", "RECRUIT", "#8b949e"


def _xp_progress(pnl_pct: float) -> tuple[float, str]:
    """Return (progress 0-1, next_level_label) for XP bar rendering."""
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


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def _render_sidebar() -> dict:
    """Render sidebar and return user-selected parameters."""
    st.sidebar.title("MagicFinance")
    st.sidebar.caption("Reddit Investment Research Pipeline")
    st.sidebar.divider()

    # System status
    st.sidebar.subheader("System Status")
    qdrant_ok = _probe_qdrant()
    mlx = _load_mlx_health()

    def _status(ok: bool, label: str) -> None:
        icon = "🟢" if ok else "🔴"
        st.sidebar.markdown(f"{icon} {label}")

    _status(qdrant_ok, "Qdrant (Nanobot VPS)")
    _status(mlx.get("mlx_lm_installed", False), "mlx-lm")
    _status(mlx.get("model_9b_exists", False), "Qwen 9B")
    _status(mlx.get("model_4b_exists", False), "Qwen 4B")

    if not qdrant_ok:
        if st.sidebar.button("🔄 Reconnect", use_container_width=True):
            _probe_qdrant.clear()
            _load_signals.clear()
            _load_forecasts.clear()
            _load_investable.clear()
            st.rerun()

    st.sidebar.divider()

    # Filters
    st.sidebar.subheader("Filters")
    min_confidence = st.sidebar.slider(
        "Min confidence", min_value=0.0, max_value=1.0, value=0.0, step=0.05
    )
    investable_only = st.sidebar.checkbox("Investable only", value=False)

    st.sidebar.divider()

    # Run pipeline
    st.sidebar.subheader("Module A — Reddit Scorer")
    posts_per_sub = st.sidebar.slider(
        "Posts per subreddit", min_value=1, max_value=20, value=3
    )

    run_clicked = False
    run_d_clicked = False
    if not qdrant_ok:
        st.sidebar.warning("Qdrant offline — pipeline disabled")
    else:
        run_clicked = st.sidebar.button("▶ Run Module A", use_container_width=True)
        st.sidebar.caption("Scrape Reddit → score with Qwen → store signals")
        st.sidebar.divider()
        st.sidebar.subheader("Module D — Forecast Generator")
        run_d_clicked = st.sidebar.button("▶ Run Module D", use_container_width=True)
        st.sidebar.caption("Generate binary forecasts from investable signals")

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
        st.sidebar.info("No posts with recognisable tickers found.")
        return

    stored = 0
    errors = []
    progress = st.sidebar.progress(0, text="Scoring posts…")
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
        st.sidebar.success(f"Stored {stored}/{len(filtered)} signal(s) in Qdrant.")
        _load_signals.clear()
        _load_investable.clear()
    else:
        st.sidebar.error(f"Stored 0/{len(filtered)} — all failed.")
    if errors:
        with st.sidebar.expander(f"⚠️ {len(errors)} error(s)"):
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
        st.sidebar.info("No signals in Qdrant. Run Module A first.")
        return

    st.sidebar.info(f"Using {len(signals)} signal(s) for forecasting.")

    total_forecasts = 0
    progress = st.sidebar.progress(0, text="Generating forecasts…")

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
            st.sidebar.warning(f"{ticker}: {e}")

        progress.progress((i + 1) / min(len(signals), 10), text=f"Forecasting {ticker}…")

    progress.empty()
    st.sidebar.success(f"Generated {total_forecasts} forecast(s) from {min(len(signals), 10)} signals.")
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

    brier_hint = (
        f" Brier score below 0.25 = good calibration."
        if len(resolved) >= 2 else
        " Need ≥ 2 resolved forecasts to compute Brier score."
    )
    _info_box(
        f"Binary yes/no predictions about market events. Probability 0 = never, 1 = certain. "
        f"<b>Avg probability: {avg_prob:.0%}.</b> "
        f"Resolved forecasts have a known outcome — the <b>Brier Score</b> measures calibration (0 = perfect, 0.25 = random).{brier_hint}"
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

        # RPG level
        lvl_emoji, lvl_title, lvl_color = _investor_level(pnl)
        xp_progress, xp_next = _xp_progress(pnl)
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

        with cols[i % 2]:
            st.markdown(
                f"""
                <div class="inv-card {card_rank_class}">
                  <!-- Header row -->
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                    <span style="font-size:22px;">{investor['emoji']}</span>
                    <div style="text-align:right;">
                      {rank_icon}
                      <div>
                        <span class="level-badge" style="background:{lvl_color}22;color:{lvl_color};border:1px solid {lvl_color}44;">
                          {lvl_emoji} {lvl_title}
                        </span>
                      </div>
                    </div>
                  </div>
                  <!-- Name & class -->
                  <div style="color:#e6edf3;font-weight:700;font-size:15px;">{investor['name']}</div>
                  <div style="color:#8b949e;font-size:11px;font-family:monospace;letter-spacing:1px;margin-bottom:6px;">
                    {investor['style'].upper()}
                  </div>
                  <!-- XP bar -->
                  <div style="display:flex;align-items:center;gap:8px;margin-bottom:2px;">
                    <div class="xp-track" style="flex:1;">
                      <div class="xp-fill" style="width:{xp_pct}%;"></div>
                    </div>
                    <span style="font-size:10px;color:#484f58;font-family:monospace;white-space:nowrap;">{xp_next}</span>
                  </div>
                  <!-- Portfolio value -->
                  <div style="display:flex;align-items:baseline;gap:12px;margin:8px 0 4px;">
                    <span style="color:#e6edf3;font-size:20px;font-weight:700;font-family:monospace;">€{value:.0f}</span>
                    <span style="color:{pnl_colour};font-size:14px;font-weight:600;">{pnl:+.1f}%</span>
                  </div>
                  <div style="color:#484f58;font-size:11px;font-family:monospace;margin-bottom:6px;">
                    CASH €{cash:.0f} · {n_holdings} POS · {holdings_tickers[:30]}
                  </div>
                  <!-- Last trade -->
                  <div style="font-size:12px;border-top:1px solid #21262d;padding-top:6px;margin-top:4px;">
                    {last_html}
                  </div>
                  <!-- Achievements -->
                  <div style="margin-top:6px;">{badges_html}</div>
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    params = _render_sidebar()

    if params["run_clicked"]:
        try:
            _run_pipeline(params["posts_per_sub"])
        except Exception as e:
            st.sidebar.error(f"Pipeline error: {e}")
            traceback.print_exc()

    if params.get("run_d_clicked"):
        try:
            _run_module_d()
        except Exception as e:
            st.sidebar.error(f"Module D error: {e}")
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
          <span class="cp-title">MAGICFINANCE</span>
        </div>
        <div class="cp-subtitle">NEURAL INVESTMENT INTERFACE · REDDIT SIGNAL PIPELINE</div>
        <div class="market-hud" style="margin-top:14px;">
          <div class="hud-item">
            <span class="hud-label">SYSTEM</span>
            <span class="hud-value" style="color:{qdrant_color};">{qdrant_status}</span>
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

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚡ Neural Feed",
        "🔮 Oracle Matrix",
        "💼 Net Worth",
        "⚔️ The Arena",
    ])

    with tab1:
        _render_signals_tab(params)

    with tab2:
        _render_forecasts_tab()

    with tab3:
        _render_portfolio_tab()

    with tab4:
        _render_arena_tab(params["qdrant_ok"])


if __name__ == "__main__":
    main()
