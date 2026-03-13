# MagicFinance — Status da Implementação

> Ficheiro de controlo. Atualizado continuamente durante o desenvolvimento.
> Última atualização: 2026-03-13

---

## ✅ Decisão de Arquitectura Resolvida: MLX (migrado e funcional)

`llm_client.py` usa MLX nativo (`mlx_lm`) — sem Ollama, sem servidor.

| Aspecto | Solução |
|---|---|
| Modelos Qwen3.5 são VL (vision-language) | `load_model(strict=False)` ignora vision tower weights |
| API de temperatura mudou no mlx_lm 0.30+ | `make_sampler(temp=T)` passado como `sampler=` |
| Thinking mode ligado por defeito | `enable_thinking=False` no `apply_chat_template` |
| Conflito libomp no launcher | `KMP_DUPLICATE_LIB_OK=TRUE` no `.command` |
| Qwen3.5 emite `<think>...</think>` antes do JSON | `_extract_decisions` strip + findall do último `[...]` |

**Smoke tests: 8/9 ✅** — só Qdrant falha quando Tailscale está desligado.

---

## Estado Geral

| Componente | Estado | Notas |
|---|---|---|
| `magicfinance/` biblioteca | ✅ Completo | 9 módulos implementados |
| `app.py` — Streamlit Dashboard | ✅ Implementado | 4 tabs: Signals, Forecasts, Portfolio, Arena |
| `notebooks/notebook_a.ipynb` | ✅ Implementado | Substituído pelo dashboard |
| `notebooks/notebook_d.ipynb` | ✅ Implementado | Substituído pelo dashboard |
| `notebooks/notebook_e.ipynb` | ✅ Implementado | Substituído pelo dashboard |
| `vps/reddit_scraper.py` | ✅ Implementado | Precisa de deploy no VPS |
| `vps/cleanup.sh` | ✅ Implementado | Precisa de deploy no VPS |
| `vps/install_vps.sh` | ✅ Implementado | Ainda não correu no VPS |
| Credenciais `.env` | ⚠️ Parcial | Reddit ok; NewsAPI + Slack opcionais |
| Deploy VPS | ❌ Por fazer | Ver secção abaixo |

---

## ✅ Streamlit Dashboard (`app.py`)

Lançado com `MagicFinance.command` (duplo clique). Abre em `http://localhost:8501`.

### 4 Tabs

| Tab | O que mostra |
|---|---|
| **Reddit Signals** | Ticker cards com DDD (Due Diligence), verdict, thesis summary, panorama global |
| **Forecasts** | Histórico de previsões binárias, calibração, Brier score |
| **Portfolio** | Optimização Markowitz, pie chart de pesos, backtest vs S&P500 |
| **Investor Arena** | 10 investidores AI tomam decisões BUY/SELL/HOLD em cada tick |

### Funcionalidades Chave

- **Demo mode** — fallback automático quando Qdrant está offline (sem crash)
- **Sidebar** — botões "Run Module A" e "Run Module D", filtros de confiança
- **Ticker Cards** — cada ticker tem: verdict (STRONG BUY / WATCH / WEAK), thesis, DDD vs yfinance
- **Panorama Global** — síntese actionable gerada por LLM do landscape de sinais
- **Investor Arena** — 10 personas MobLand, portfolios persistidos em `data/investor_portfolios.json`
- **Caching** — `@st.cache_data(ttl=300)` nos loaders, `ttl=30` no probe Qdrant
- **Tema escuro** — `#0d1117` background, `#00d4aa` accent teal, Plotly dark

---

## ✅ Investor Arena — 10 Personas MobLand

Ficheiro: `magicfinance/investors.py`

| ID | Nome | Estilo | Risco |
|---|---|---|---|
| harry | Harry Da Souza | Value Investing | low |
| maeve | Maeve Harrigan | Global Macro | high |
| eddie | Eddie Harrigan | Disruptive Innovation | very_high |
| conrad | Conrad Harrigan | All Weather / Risk Parity | medium |
| kevin | Kevin Harrigan | Growth at Reasonable Price | medium |
| jan | Jan Da Souza | Quantitative | medium |
| richie | Richie Stevenson | Deep Value / Contrarian | high |
| vron | Vron Stevenson | Momentum / Trend Following | very_high |
| bella | Bella Harrigan | Pure Value | very_low |
| tommy | Tommy Stevenson | Anti-Fragile / Tail Risk | bimodal |

Motor: `magicfinance/simulation.py` — `run_tick()` → BUY/SELL/HOLD por Qwen MLX → portfolios persistidos.

---

## ✅ O Que Está Feito

### Biblioteca `magicfinance/`

| Ficheiro | Funcionalidade | Status |
|---|---|---|
| `config.py` | Parâmetros globais + `COLLECTION_SIM_EVENTS` | ✅ |
| `reddit_client.py` | PRAW wrapper, extração de tickers, blacklist alargada | ✅ |
| `llm_client.py` | MLX scoring (9B), forecasting (4B), health check | ✅ |
| `qdrant_client.py` | CRUD para 4 collections: signals, forecasts, raw posts, sim events | ✅ |
| `slack_client.py` | Alertas para Módulos A, D, E com Block Kit formatting | ✅ |
| `yfinance_client.py` | Preços históricos, covariance matrix, backtest P&L, benchmark S&P500 | ✅ |
| `portfolio.py` | Markowitz optimizer, fixed/dynamic expected returns, position table | ✅ |
| `investors.py` | 10 personas MobLand com prompts compactos | ✅ |
| `simulation.py` | Motor de decisões BUY/SELL/HOLD, trade execution, portfolio persistence | ✅ |

### Collections Qdrant

| Collection | Conteúdo |
|---|---|
| `magicfinance_reddit_signals` | Sinais scored pelo Module A |
| `magicfinance_forecast_history` | Forecasts gerados pelo Module D |
| `magicfinance_raw_reddit` | Posts brutos do VPS cron |
| `magicfinance_sim_events` | Decisões dos 10 investidores AI |

---

## ❌ O Que Falta Fazer

### P0 — Para correr agora

- [ ] **Confirmar Tailscale ativo** (necessário para Qdrant no VPS):
  ```bash
  tailscale status  # deve mostrar 100.97.190.121 como peer ativo
  ```

- [ ] **Criar `.env`** com Reddit credentials:
  ```
  REDDIT_CLIENT_ID=...
  REDDIT_CLIENT_SECRET=...
  REDDIT_USER_AGENT=MagicFinance/1.0
  ```

### P1 — Deploy VPS

- [ ] Copiar ficheiros para o VPS e correr `install_vps.sh`
- [ ] Confirmar cron ativo para scrape diário

### P2 — Melhorias Futuras

- [ ] **Módulo B (AI-Buffett Engine)** — score baseado nas cartas de Buffett (PDFs 1977-2024)
- [ ] **Módulo C (Deception Detector)** — análise de earnings call transcripts
- [ ] **Accuracy backtest real (Module D)** — requer dados acumulados (semanas)
- [ ] **Semantic search no Qdrant** — substituir hash-vectors por embeddings reais
- [ ] **Resolução de forecasts** — mecanismo para marcar `resolved=True` + `actual_outcome`
- [ ] **Investor Arena histórico** — gráfico de performance ao longo do tempo (multi-sessão)

---

## Notas de Arquitectura

### Fluxo de dados entre módulos
```
Reddit Posts (VPS cron ou sidebar "Run Module A")
    → Qdrant raw_reddit (scored=False)  [ou directo para signals]
    → Module A: Qwen 9B scoring
    → Qdrant reddit_signals (scored=True, is_investable=True/False)
    → Module D: event generation + Qwen 4B forecasting
    → Qdrant forecast_history
    → Module E (Portfolio tab): Markowitz optimization
    → Investor Arena: 10 AI personas → BUY/SELL/HOLD → Qdrant sim_events
```

### Launcher
```bash
# Double-click MagicFinance.command  — abre http://localhost:8501
# Ou manualmente:
KMP_DUPLICATE_LIB_OK=TRUE streamlit run app.py
```

### Variáveis críticas (`config.py`)
| Variável | Valor | Significado |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.75 | Threshold para sinais investable |
| `FORECAST_THRESHOLD` | 0.70 | Threshold para forecasts de alta confiança |
| `MIN_UPVOTES` | 5 | Posts Reddit com menos upvotes são ignorados |
| `QDRANT_HOST` | 100.97.190.121 | IP Tailscale do VPS Nanobot |

### Potenciais problemas conhecidos
- **Qwen 9B lento**: ~30-60s por post. Usar 3-5 posts em demo.
- **Reddit rate limits**: PRAW respeita automaticamente.
- **Qdrant offline**: dashboard entra em demo mode automaticamente (sem crash).
- **yfinance ^GSPC**: alguns ambientes bloqueiam. Benchmark fica vazio mas não quebra.
- **Thinking blocks Qwen3.5**: `_extract_decisions` strip + findall resolve.
