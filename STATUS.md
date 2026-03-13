# MagicFinance — Status da Implementação

> Ficheiro de controlo. Atualizado continuamente durante o desenvolvimento.
> Última atualização: 2026-03-12

---

## ✅ Decisão de Arquitectura Resolvida: MLX (migrado)

O código actual usa **Qwen via Ollama** (`llm_client.py`), mas o setup real desta máquina é:

| Configuração actual no código | Setup real da máquina |
|---|---|
| `ollama pull qwen2.5:9b` | **DeepSeek-R1-0528-Qwen3-8B-8bit via MLX** |
| `http://localhost:11434` (Ollama REST) | `mlx_lm.generate()` (Python directo, zero latência de rede) |
| Qwen2.5 9B + 4B | DeepSeek-R1 8B (reasoning + thinking mode) |

**Recomendação**: Migrar `llm_client.py` para usar MLX directamente (como o Wisdom Council). Vantagens:
- Sem servidor Ollama a arrancar
- ~25-30 tokens/sec (mais rápido)
- Thinking mode nativo (melhor qualidade de scoring)
- Consistente com todos os outros projectos

**Acção necessária**: Confirmar com o utilizador se quer migrar para MLX ou manter Ollama.

---

## Estado Geral

| Componente | Estado | Notas |
|---|---|---|
| `magicfinance/` biblioteca | ✅ Completo | 7 módulos implementados |
| `notebooks/notebook_a.ipynb` | ✅ Implementado | Precisa de teste real |
| `notebooks/notebook_d.ipynb` | ✅ Implementado | Precisa de teste real |
| `notebooks/notebook_e.ipynb` | ✅ Implementado | Precisa de teste real |
| `vps/reddit_scraper.py` | ✅ Implementado | Precisa de deploy no VPS |
| `vps/cleanup.sh` | ✅ Implementado | Precisa de deploy no VPS |
| `vps/install_vps.sh` | ✅ Implementado | Ainda não correu no VPS |
| Credenciais `.env` | ❌ Por fazer | Ver secção abaixo |
| Deploy VPS | ❌ Por fazer | Ver secção abaixo |
| Teste end-to-end | ❌ Por fazer | Requer credenciais + VPS |

---

## ✅ O Que Está Feito

### Biblioteca `magicfinance/`

| Ficheiro | Funcionalidade | Status |
|---|---|---|
| `config.py` | Todos os parâmetros: thresholds, modelos, Qdrant, Slack | ✅ |
| `reddit_client.py` | PRAW wrapper, extração de tickers, fetch por subreddit | ✅ |
| `llm_client.py` | Ollama wrappers: scoring (9B), forecasting (4B), dynamic weights (9B) | ✅ |
| `qdrant_client.py` | CRUD para 3 collections: signals, forecasts, raw posts | ✅ |
| `slack_client.py` | Alertas para Módulos A, D, E com Block Kit formatting | ✅ |
| `yfinance_client.py` | Preços históricos, covariance matrix, backtest P&L, benchmark S&P500 | ✅ |
| `portfolio.py` | Markowitz optimizer, fixed/dynamic expected returns, position table | ✅ |

### Notebooks

| Notebook | O que faz | Status |
|---|---|---|
| `notebook_a.ipynb` | Fetch Reddit → Score Qwen 9B → Qdrant → Slack → visualizações | ✅ |
| `notebook_d.ipynb` | NewsAPI + signals → Forecast Qwen 4B → Qdrant → Slack → accuracy backtest | ✅ |
| `notebook_e.ipynb` | A/B comparison (fixed vs dynamic weights) → Markowitz → backtest P&L vs S&P → Slack | ✅ |

### VPS

| Ficheiro | O que faz | Status |
|---|---|---|
| `vps/reddit_scraper.py` | Cron diário: fetch Reddit → store Qdrant (marcado scored=False) | ✅ |
| `vps/cleanup.sh` | Cron semanal: compress → rsync Mac via Tailscale → delete VPS | ✅ |
| `vps/install_vps.sh` | Setup único: venv, deps, cron, permissões, dry-run test | ✅ |

---

## ❌ O Que Falta Fazer

### P0 — Bloqueadores (sem isto nada corre)

- [x] **Criar `.env`** com as credenciais (Reddit preenchido; NewsAPI + Slack em falta):
  - `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` → https://www.reddit.com/prefs/apps (criar app "script")
  - `NEWSAPI_KEY` → https://newsapi.org/register (free tier)
  - `SLACK_WEBHOOK_URL` → reutilizar o webhook do Nanobot (já existe)

- [x] **Modelos MLX verificados** — `Qwen3.5-9B-4bit` + `Qwen3.5-4B-4bit` em `~/Desktop/Apps/MLX/` ✅

- [ ] **Confirmar Tailscale ativo** (necessário para Qdrant no VPS):
  ```bash
  tailscale status  # deve mostrar 100.97.190.121 como peer ativo
  ```

### P1 — Deploy VPS

- [ ] **Copiar ficheiros para o VPS**:
  ```bash
  scp -r vps/ root@76.13.66.197:/opt/magicfinance/
  scp .env root@76.13.66.197:/opt/magicfinance/
  ```

- [ ] **Correr install_vps.sh no VPS** (instala venv, deps, cron):
  ```bash
  ssh root@76.13.66.197 "bash /opt/magicfinance/install_vps.sh"
  ```

- [ ] **Confirmar cron ativo** no VPS:
  ```bash
  ssh root@76.13.66.197 "crontab -l | grep magicfinance"
  ```

- [ ] **Primeiro scrape manual** para validar o pipeline:
  ```bash
  ssh root@76.13.66.197 "/opt/magicfinance/venv/bin/python /opt/magicfinance/reddit_scraper.py"
  ```

### P2 — Teste End-to-End (local)

- [ ] Instalar dependências Python:
  ```bash
  pip install -r requirements.txt
  ```

- [ ] Correr `notebook_a.ipynb` do início ao fim sem erros
- [ ] Confirmar que sinais aparecem no Qdrant:
  ```python
  from magicfinance import qdrant_client as qc
  print(len(qc.get_all_signals()))  # deve ser > 0
  ```
- [ ] Correr `notebook_d.ipynb` — verificar forecasts no Qdrant
- [ ] Correr `notebook_e.ipynb` — verificar portfolio output + Slack alert recebido

### P3 — Melhorias Futuras (pós-entrevista)

- [ ] **Módulo B (AI-Buffett Engine)** — requer Buffett letters (PDFs 1977–2024)
  - Download: https://www.berkshirehathaway.com/letters/letters.html
  - Pipeline: PDF → chunks → Qwen 9B extract principles → Buffett score 0–100

- [ ] **Módulo C (Deception Detector)** — requer earnings call transcripts
  - Fonte gratuita: SEC EDGAR 8-K filings (parsing complexo)
  - Alternativa: Motley Fool Transcripts API (paga)

- [ ] **Accuracy backtest real (Módulo D)** — requer dados acumulados ao longo do tempo
  - Implementar mecanismo de resolução: quando um evento se resolve, atualizar Qdrant com `resolved=True` + `actual_outcome`
  - Actualmente: backtest só funciona após semanas de dados reais

- [ ] **Semantic search no Qdrant** — actualmente usa hash-vectors (não semânticos)
  - Substituir `_text_to_vector()` por embeddings reais (ex: `nomic-embed-text` via Ollama)
  - Permitiria busca por "encontra posts sobre value investing similares a X"

- [ ] **GitHub Pages / Streamlit dashboard** — para mostrar resultados ao vivo na entrevista
  - Alternativa mais simples: exportar notebooks como HTML

- [ ] **Testes automatizados** — `tests/` com pytest
  - Unit tests para `portfolio.py` (Markowitz com dados sintéticos)
  - Integration tests para `qdrant_client.py` (mock Qdrant)

---

## Notas de Arquitectura

### Fluxo de dados entre módulos
```
Reddit Posts (VPS cron)
    → Qdrant raw_reddit (scored=False)
    → notebook_a.ipynb: Qwen 9B scoring
    → Qdrant reddit_signals (scored=True, is_investable=True/False)
    → notebook_d.ipynb: event generation + Qwen 4B forecasting
    → Qdrant forecast_history
    → notebook_e.ipynb: Markowitz optimization
    → Portfolio output + Slack alert
```

### Variáveis de configuração críticas (`config.py`)
| Variável | Valor | Significado |
|---|---|---|
| `NANOBOT_WATCHLIST` no notebook_e | `['AAPL','MSFT',...]` | **Atualizar** com tickers reais do stock_watchdog.py |
| `CONFIDENCE_THRESHOLD` | 0.75 | Ajustar após ver distribuição real dos scores |
| `FORECAST_THRESHOLD` | 0.70 | Ajustar após ver distribuição real das probabilidades |
| `SCORE_LIMIT` no notebook_a | 20 | Aumentar para produção (mais posts = mais sinais) |

### Potenciais problemas conhecidos
- **Qwen 9B lento**: cada post demora ~30-60s. Com 20 posts = 10-20min. Reduzir `SCORE_LIMIT` para demos rápidas.
- **Reddit rate limits**: PRAW respeita automaticamente, mas 100 posts × 3 subreddits = ~300 requests. Ok para uso diário.
- **Qdrant vector dim**: actualmente usa hash-vectors (384 dim). Se mudar para embeddings reais, recriar collections.
- **yfinance ^GSPC**: alguns ambientes bloqueiam download do S&P500. Se falhar, o benchmark fica vazio (não quebra o notebook).
