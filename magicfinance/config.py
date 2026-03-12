"""
MagicFinance — Central Configuration
=====================================
All tunable constants for the pipeline. Edit this file to adjust thresholds,
model routing, and infrastructure endpoints without touching notebook code.
"""

# ─── Infrastructure ────────────────────────────────────────────────────────────

# Nanobot VPS Qdrant (reachable via Tailscale VPN)
QDRANT_HOST = "100.97.190.121"
QDRANT_PORT = 6333
QDRANT_TIMEOUT = 10  # seconds

# Qdrant collection names (separate from existing Nanobot collections)
COLLECTION_REDDIT_SIGNALS = "magicfinance_reddit_signals"
COLLECTION_FORECAST_HISTORY = "magicfinance_forecast_history"
COLLECTION_RAW_REDDIT = "magicfinance_raw_reddit"

# Vector dimension for embeddings (text-embedding-3-small compatible, or use simple hash)
VECTOR_DIM = 384

# ─── LLM Models (Ollama/MLX — running locally) ─────────────────────────────────

# Qwen 9B: complex structured scoring (Module A) and dynamic weight reasoning (Module E)
MODEL_9B = "qwen2.5:9b"

# Qwen 4B: binary probability forecasting (Module D) — faster, lighter
MODEL_4B = "qwen2.5:4b"

# Ollama endpoint
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 120  # seconds — 9B can be slow

# ─── Reddit Scraping ────────────────────────────────────────────────────────────

# Top 3 subreddits by historical stock-pick quality
# r/ValueInvesting: highest signal-to-noise (original 547-pick study)
# r/SecurityAnalysis: institutional-quality deep dives
# r/stocks: broad coverage, decent when LLM-filtered
# NOTE: r/wallstreetbets explicitly excluded — noise dominates signal
SUBREDDITS = ["ValueInvesting", "SecurityAnalysis", "stocks"]

# Posts per subreddit per scrape run
REDDIT_POST_LIMIT = 100

# Minimum upvotes to include a post (filter out very low-engagement noise)
MIN_UPVOTES = 10

# ─── Signal Thresholds ─────────────────────────────────────────────────────────

# Module A: fire Slack alert when confidence_level exceeds this
CONFIDENCE_THRESHOLD = 0.75

# Module D: fire Slack alert when forecast_probability exceeds this
FORECAST_THRESHOLD = 0.70

# Module A: minimum composite score for a ticker to be marked is_investable=True
INVESTABLE_MIN_SCORE = 0.65

# ─── Expected Return Formula — Fixed Weights (Module E, Path A) ────────────────
# expected_return = W_THESIS * thesis_score + W_FORECAST * forecast_prob + W_CONF * confidence_level
FIXED_WEIGHTS = {
    "thesis": 0.40,
    "forecast": 0.40,
    "confidence": 0.20,
}

# ─── Portfolio Construction (Module E) ─────────────────────────────────────────

# Total simulated portfolio value (USD)
PORTFOLIO_VALUE_USD = 10_000

# Max allocation per single position (prevents over-concentration)
MAX_POSITION_PCT = 0.25

# Min allocation to include a position (ignore negligible weights)
MIN_POSITION_PCT = 0.02

# Historical price window for covariance matrix and backtest (trading days)
LOOKBACK_DAYS = 252  # ~1 year

# Markowitz risk-free rate (annualized)
RISK_FREE_RATE = 0.05  # 5% — approximate current rate

# ─── VPS Data Management ───────────────────────────────────────────────────────

# Keep N days of raw Reddit/news data on VPS before rsync+delete
VPS_RAW_RETENTION_DAYS = 30

# Rsync destination on local Mac (over Tailscale)
# Update this to your Mac's Tailscale IP or hostname
LOCAL_MAC_TAILSCALE_IP = "100.77.221.4"
LOCAL_ARCHIVE_PATH = "/Users/joaovicente/Desktop/Apps/MagicFinance/data/archive"

# ─── News API (macro events for Module D) ─────────────────────────────────────

# NewsAPI.org free tier — https://newsapi.org (free: 100 req/day, 1 month history)
# Set NEWSAPI_KEY in .env
NEWSAPI_BASE_URL = "https://newsapi.org/v2"
NEWSAPI_QUERIES = [
    "Federal Reserve interest rates",
    "CPI inflation report",
    "S&P 500 earnings",
    "recession GDP",
]
NEWSAPI_ARTICLE_LIMIT = 10  # per query

# ─── Slack ─────────────────────────────────────────────────────────────────────

# Set SLACK_WEBHOOK_URL in .env
# Alerts fire directly from local notebooks (no VPS dependency during demo)
SLACK_CHANNEL = "#all-nanobot"  # reuse existing Nanobot channel
