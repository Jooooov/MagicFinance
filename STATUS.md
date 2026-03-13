# MagicFinance — Status da Implementação

> Ficheiro de controlo. Atualizado continuamente durante o desenvolvimento.
> Última atualização: 2026-03-13

---

## Arquitectura Geral

```
┌─────────────────────────────────────────────────────────────┐
│  Mac (Apple Silicon)                                         │
│  ┌─────────────────┐    ┌──────────────────────────────┐    │
│  │  Streamlit UI   │    │  MLX (Qwen3.5-9B / 4B)       │    │
│  │  app.py         │◄───│  Module A scoring              │    │
│  │  4 tabs + HUD   │    │  Module D forecasting          │    │
│  └────────┬────────┘    └──────────────────────────────┘    │
│           │ on startup: sync_on_startup()                    │
└───────────┼─────────────────────────────────────────────────┘
            │
            │ Tailscale VPN (100.97.190.121)
            │
┌───────────┼─────────────────────────────────────────────────┐
│  Nanobot VPS (Tailscale peer)                                │
│           │                                                  │
│  ┌────────▼────────┐                                         │
│  │  Qdrant         │  4 Collections:                         │
│  │  :6333          │  • magicfinance_reddit_signals           │
│  │                 │  • magicfinance_forecast_history         │
│  │                 │  • magicfinance_raw_reddit               │
│  │                 │  • magicfinance_sim_events  (VPS queue)  │
│  │                 │  • magicfinance_portfolios  (shared state)│
│  └─────────────────┘                                         │
└─────────────────────────────────────────────────────────────┘
            ▲
            │ push events + portfolio each tick
            │
┌───────────┼─────────────────────────────────────────────────┐
│  Hostinger VPS (KVM1 — 4GB RAM, 1 CPU, 50GB)                │
│                                                              │
│  ┌─────────────────┐    ┌──────────────────────────────┐    │
│  │  Ollama         │    │  cron (hourly at :05)         │    │
│  │  qwen3.5:0.8b   │◄───│  vps/sim_tick.py              │    │
│  │  ~500MB GGUF Q4 │    │  10 AI investors decide       │    │
│  └─────────────────┘    └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Sincronização (startup sync)

```
Hostinger VPS:
  cron tick → run_tick() → push_portfolio() + upsert_sim_event()
                                  ↓
                           Qdrant (Nanobot VPS)
                                  ↓
Mac (on .command startup):
  sync_on_startup()
    1. pull_portfolio() → save_portfolios() → data/investor_portfolios.json
    2. pull_and_clear_sim_events() → data/sim_events_history.jsonl
    3. push_portfolio() (authoritative Mac state back to Qdrant)
```

---

## Estado Geral

| Componente | Estado | Notas |
|---|---|---|
| `magicfinance/` biblioteca | ✅ Completo | 9 módulos implementados |
| `app.py` — Streamlit Dashboard | ✅ Implementado | Tema Cyberpunk RPG, 4 tabs |
| `magicfinance/llm_client.py` | ✅ Dual backend | MLX (Mac) + Ollama (VPS) |
| `magicfinance/sync.py` | ✅ Implementado | Startup sync Mac↔VPS |
| `magicfinance/qdrant_client.py` | ✅ Atualizado | +push/pull portfolio, +pull_and_clear_sim_events |
| `vps/sim_tick.py` | ✅ Implementado | Cron script Hostinger (Ollama) |
| `vps/install_sim.sh` | ✅ Implementado | Setup one-command Hostinger |
| `MagicFinance.command` | ✅ Atualizado | Auto-sync + launch Streamlit |
| Deploy Hostinger VPS | ❌ Por fazer | Ver secção abaixo |

---

## ✅ Streamlit Dashboard (`app.py`) — Tema Cyberpunk RPG

Lançado com `MagicFinance.command` (duplo clique). Abre em `http://localhost:8501`.

### 4 Tabs

| Tab | Nome UI | O que mostra |
|---|---|---|
| 1 | ⚡ Neural Feed | Sinais Reddit com score bars, verdict, thesis, Intel Brief |
| 2 | 🔮 Oracle Matrix | Forecasts binários, calibração, Brier score, Oracle Status synthesis |
| 3 | 💼 Net Worth | Portfolio Markowitz, pie chart, backtest vs S&P500 |
| 4 | ⚔️ The Arena | 10 investidores AI com cards cyberpunk, nível RPG, XP bar, popover DNA |

### Funcionalidades Cyberpunk

- **Matrix Rain** — canvas WebGL injectado no parent frame via `components.html()`
- **Ticker Tape** — banner scrolling com dados de sinais em tempo real
- **Market Condition HUD** — BULL MARKET / BEAR MARKET / CONSOLIDATION com status dot
- **Investor Cards** — level badge (RECRUIT→LEGEND), XP bar animada, achievements, `has_traded` flag
- **Netrunner Profile Popover** — Financial DNA por investidor, risk bar, sizing/exit tiles
- **Oracle Status** — síntese: bias (BULLISH/BEARISH/NEUTRAL), Brier calibration grade, top prediction
- **Demo mode** — fallback automático quando Qdrant offline (sem crash)
- **Sidebar** — status Qdrant/MLX, última sincronização VPS, botão "Run Module A"

### Sistema de Níveis (Investor Arena)

| Nível | Threshold P&L | Condição |
|---|---|---|
| RECRUIT | — | Sem trades ainda (`has_traded=False`) |
| SOLDIER | ≥ 0% | Primeiro trade realizado |
| VETERAN | ≥ 5% | P&L positivo significativo |
| ELITE | ≥ 15% | Performance sólida |
| LEGEND | ≥ 30% | Retorno excepcional |

---

## ✅ 10 Personas MobLand — Investor Arena

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

Motor: `magicfinance/simulation.py` — `run_tick()` → BUY/SELL/HOLD → portfolios persistidos.

---

## ✅ LLM Backend Dual (MLX + Ollama)

Controlado pela variável de ambiente `LLM_BACKEND`:

| Backend | Onde corre | Modelo | Env vars |
|---|---|---|---|
| `mlx` (default) | Mac Apple Silicon | Qwen3.5-9B/4B MLX | `MLX_DIR` |
| `ollama` | Hostinger VPS | qwen3.5:0.8b | `OLLAMA_MODEL`, `OLLAMA_BASE_URL` |

Funções adicionadas a `llm_client.py`:
- `_generate_ollama(prompt, system, max_tokens, temperature)` — REST POST `/api/chat`
- `check_ollama_server()` → `{ok, models, target_model, target_available}`
- `_generate()` — router MLX vs Ollama baseado em `LLM_BACKEND`

---

## ✅ Collections Qdrant (5 total)

| Collection | Conteúdo | Quem escreve | Quem lê |
|---|---|---|---|
| `magicfinance_reddit_signals` | Sinais scored Module A | Mac | Mac + VPS |
| `magicfinance_forecast_history` | Forecasts Module D | Mac | Mac |
| `magicfinance_raw_reddit` | Posts brutos VPS cron | VPS scraper | Mac Module A |
| `magicfinance_sim_events` | Decisões AI (fila VPS) | VPS sim_tick | Mac (drain on startup) |
| `magicfinance_portfolios` | Estado portfolio partilhado | Mac + VPS | Mac + VPS |

---

## ✅ Notas de Arquitectura MLX

| Aspecto | Solução |
|---|---|
| Modelos Qwen3.5 são VL (vision-language) | `load_model(strict=False)` ignora vision tower weights |
| API de temperatura mudou no mlx_lm 0.30+ | `make_sampler(temp=T)` passado como `sampler=` |
| Thinking mode ligado por defeito | `enable_thinking=False` no `apply_chat_template` |
| Conflito libomp no launcher | `KMP_DUPLICATE_LIB_OK=TRUE` no `.command` |
| Qwen3.5 emite `<think>...</think>` antes do JSON | `_extract_decisions` strip + findall do último `[...]` |

---

## ❌ O Que Falta Fazer

### P0 — Deploy VPS Hostinger

```bash
# 1. Confirmar IP do Hostinger e ajustar QDRANT_HOST se necessário
#    (por defeito sim_tick.py usa QDRANT_HOST=localhost — mas Qdrant corre no Nanobot!)
#    Adicionar ao .env no VPS ou à linha de cron:
#    QDRANT_HOST=100.97.190.121

# 2. Copiar projecto para o VPS
scp -r . root@HOSTINGER_IP:/opt/magicfinance/

# 3. Correr install
ssh root@HOSTINGER_IP "bash /opt/magicfinance/vps/install_sim.sh"

# 4. Verificar cron
ssh root@HOSTINGER_IP "crontab -l | grep sim_tick"

# 5. Monitorizar
ssh root@HOSTINGER_IP "tail -f /var/log/mf_sim.log"
```

> ⚠️ **Atenção**: `sim_tick.py` usa `QDRANT_HOST=localhost` por defeito.
> Se Qdrant corre no Nanobot VPS (100.97.190.121), é necessário:
> - Instalar Tailscale no Hostinger VPS, ou
> - Expor Qdrant publicamente (não recomendado), ou
> - Instalar Qdrant localmente no Hostinger

### P1 — Configuração `.env` Mac

```
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=MagicFinance/1.0
```

### P2 — Melhorias Futuras

- [ ] **Módulo B (AI-Buffett Engine)** — score baseado nas cartas de Buffett (PDFs 1977-2024)
- [ ] **Módulo C (Deception Detector)** — análise de earnings call transcripts
- [ ] **Accuracy backtest real (Module D)** — requer dados acumulados (semanas)
- [ ] **Semantic search no Qdrant** — substituir hash-vectors por embeddings reais
- [ ] **Resolução de forecasts** — marcar `resolved=True` + `actual_outcome`
- [ ] **Investor Arena histórico** — gráfico de performance ao longo do tempo (multi-sessão)
- [ ] **Arena tab — sim_events feed** — mostrar últimas decisões VPS em tempo real

---

## Potenciais Problemas Conhecidos

- **Qdrant no Hostinger**: `sim_tick.py` defaulta `QDRANT_HOST=localhost` — se Qdrant está no Nanobot precisa de ajuste
- **Qwen 9B lento**: ~30-60s por post. Usar 3-5 posts em demo.
- **Reddit rate limits**: PRAW respeita automaticamente.
- **Qdrant offline**: dashboard entra em demo mode automaticamente (sem crash).
- **yfinance ^GSPC**: alguns ambientes bloqueiam. Benchmark fica vazio mas não quebra.
- **Thinking blocks Qwen3.5**: `_extract_decisions` strip + findall resolve.
