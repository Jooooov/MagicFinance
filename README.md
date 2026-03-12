# MagicFinance

> LLM-powered investment research platform — end-to-end from Reddit signals to Markowitz portfolio optimisation.
> Built as a portfolio project for a prompt engineer interview at an investment company.

---

## What It Does

MagicFinance is a research-only investment pipeline that combines three ideas:

1. **Module A — MagicReddit**: Evaluate the *reasoning quality* of Reddit stock recommendations using Qwen 9B — not popularity or upvotes. A well-reasoned unpopular post scores higher than a viral shallow one.
2. **Module D — Forecast Engine**: Use Qwen 4B as a calibrated prediction market for binary financial events (per-stock and macro).
3. **Module E — Portfolio Engine**: Combine both signals using Markowitz mean-variance optimisation with an A/B comparison: fixed signal weights vs Qwen 9B dynamic weights.

> ⚠️ For research and simulation only. Not financial advice.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL MAC                                                       │
│                                                                  │
│  notebook_a.ipynb    →  Qwen 9B scores Reddit posts            │
│  notebook_d.ipynb    →  Qwen 4B forecasts binary events        │
│  notebook_e.ipynb    →  Markowitz portfolio optimisation        │
│         ↕ Tailscale VPN (100.77.221.4 ↔ 100.97.190.121)       │
├─────────────────────────────────────────────────────────────────┤
│  NANOBOT VPS (100.97.190.121)                                   │
│                                                                  │
│  vps/reddit_scraper.py  →  daily cron, fetches Reddit posts    │
│  vps/cleanup.sh         →  weekly rsync + delete old raw data  │
│  Qdrant :6333           →  persistent signal + forecast store  │
└─────────────────────────────────────────────────────────────────┘
```

**Qdrant collections:**
| Collection | Contents |
|---|---|
| `magicfinance_reddit_signals` | Module A scored signals (persistent) |
| `magicfinance_forecast_history` | Module D forecasts + accuracy tracking |
| `magicfinance_raw_reddit` | Raw posts (rolling 30-day window on VPS) |

---

## Quickstart (Local Notebooks)

### 1. Install dependencies

```bash
cd /path/to/MagicFinance
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in:
#   REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET  → reddit.com/prefs/apps
#   NEWSAPI_KEY                              → newsapi.org/register
#   SLACK_WEBHOOK_URL                        → reuse Nanobot webhook
```

### 3. Ensure Tailscale is connected

```bash
tailscale status
# Should show: 100.97.190.121 (nanobot VPS) as a peer
```

### 4. Ensure Ollama models are loaded

```bash
ollama list
# Should include qwen2.5:9b and qwen2.5:4b
# If missing: ollama pull qwen2.5:9b && ollama pull qwen2.5:4b
```

### 5. Run the pipeline (in order)

```bash
jupyter notebook notebooks/notebook_a.ipynb   # Module A: score Reddit signals
jupyter notebook notebooks/notebook_d.ipynb   # Module D: binary event forecasts
jupyter notebook notebooks/notebook_e.ipynb   # Module E: portfolio optimisation
```

---

## VPS Setup (Run Once)

```bash
# 1. Copy files to VPS
scp -r vps/ root@76.13.66.197:/opt/magicfinance/
scp .env root@76.13.66.197:/opt/magicfinance/

# 2. Run installation script (sets up venv + cron)
ssh root@76.13.66.197 "bash /opt/magicfinance/install_vps.sh"

# 3. Verify cron
ssh root@76.13.66.197 "crontab -l | grep magicfinance"
# Expected:
#   0 6 * * * .../reddit_scraper.py    (daily at 06:00)
#   0 3 * * 0 .../cleanup.sh           (weekly Sundays at 03:00)
```

---

## Project Structure

```
MagicFinance/
├── magicfinance/              # Shared Python library
│   ├── config.py              # All configurable constants
│   ├── reddit_client.py       # PRAW wrapper for Reddit API
│   ├── qdrant_client.py       # Qdrant read/write helpers
│   ├── llm_client.py          # Ollama wrappers (Qwen 9B + 4B)
│   ├── slack_client.py        # Direct Slack webhook alerts
│   ├── yfinance_client.py     # Historical prices + covariance
│   └── portfolio.py           # Markowitz optimizer + signal combiners
│
├── notebooks/
│   ├── notebook_a.ipynb       # Module A: MagicReddit
│   ├── notebook_d.ipynb       # Module D: Forecast Engine
│   └── notebook_e.ipynb       # Module E: Portfolio Engine
│
├── vps/
│   ├── reddit_scraper.py      # Daily cron scraper
│   ├── cleanup.sh             # Weekly data archive + rsync
│   └── install_vps.sh         # One-time VPS setup script
│
├── data/                      # Generated outputs (gitignored)
│   ├── module_a_signals.png
│   ├── module_d_forecasts.png
│   └── module_e_portfolios.png
│
├── .env.example               # Credentials template
├── requirements.txt
└── README.md
```

---

## Key Design Decisions

### Why Qwen 9B for scoring, 4B for forecasting?
Scoring Reddit posts requires nuanced multi-dimensional evaluation — a task where larger models perform significantly better. Binary probability forecasting is a simpler structured-output task, so Qwen 4B is sufficient and ~3× faster.

### Why Markowitz with LLM-generated expected returns?
Classic portfolio theory requires two inputs: expected returns and a covariance matrix. The covariance matrix comes from real historical prices (yfinance). The expected returns come from LLM signal quality assessment — this is the novel contribution: *using model reasoning quality as a proxy for expected return*.

### A/B Comparison: why fixed vs dynamic weights?
Fixed weights (0.4/0.4/0.2) are interpretable and reproducible. Dynamic weights let Qwen 9B reason about which signals are more reliable for a specific ticker. Showing both methods and comparing their portfolios is a strong demonstration of prompt engineering judgement.

### Why not use Claude API instead of Qwen local?
Cost + privacy. Running 100+ scoring calls per session on API would cost ~$5–20/run. Local Qwen models are free after download and keep financial data off external servers.

---

## Configuration Reference

All constants are in `magicfinance/config.py`:

| Constant | Default | Description |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.75 | Module A Slack alert trigger |
| `FORECAST_THRESHOLD` | 0.70 | Module D Slack alert trigger |
| `FIXED_WEIGHTS` | 0.4/0.4/0.2 | Thesis/forecast/confidence weights |
| `PORTFOLIO_VALUE_USD` | 10,000 | Simulated portfolio size |
| `MAX_POSITION_PCT` | 0.25 | Max single position (25%) |
| `LOOKBACK_DAYS` | 252 | Historical price window (~1 year) |
| `VPS_RAW_RETENTION_DAYS` | 30 | Days of raw data to keep on VPS |
| `SUBREDDITS` | ValueInvesting, SecurityAnalysis, stocks | Target subreddits |

---

## Limitations & Disclaimers

- **Not real trading**: This is a simulation and research tool only.
- **Survivorship bias**: Reddit data skews toward companies still being discussed.
- **Model contamination**: Qwen was trained before 2024; events after that cutoff are harder to forecast.
- **Covariance instability**: 1-year covariance matrices can be unstable during regime changes.
- **Rate limits**: Reddit API allows ~60 requests/minute on free tier; VPS cron respects this.
- **Signal freshness**: Scores reflect the moment of analysis; stale signals should be re-scored.
