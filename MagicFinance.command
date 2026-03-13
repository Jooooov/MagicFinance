#!/bin/bash
# MagicFinance — Launcher
# Duplo clique para abrir o Jupyter com o pipeline completo.

cd "$(dirname "$0")"

# ─── Dependencies ─────────────────────────────────────────────────────────────
echo "📦 A verificar dependências..."
pip3 install --quiet -r requirements.txt
echo "✅ Dependências OK"

# ─── Check .env ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "⚠️  Ficheiro .env não encontrado!"
    echo "   Copia .env.example para .env e preenche as credenciais."
    echo ""
    echo "   cp .env.example .env"
    read -p "   Pressiona Enter para continuar mesmo assim..."
fi

# ─── Check Tailscale ──────────────────────────────────────────────────────────
if ! tailscale status --json 2>/dev/null | grep -q "100.97.190.121"; then
    echo "⚠️  VPS Nanobot não encontrado via Tailscale."
    echo "   Qdrant estará inacessível. Corre: tailscale up"
else
    echo "✅ Tailscale: VPS conectado"
fi

# ─── Check MLX models ─────────────────────────────────────────────────────────
MLX_DIR="$HOME/Desktop/Apps/MLX"
if [ -d "$MLX_DIR/Qwen3.5-9B-4bit" ] && [ -d "$MLX_DIR/Qwen3.5-4B-4bit" ]; then
    echo "✅ MLX: modelos Qwen3.5 encontrados"
else
    echo "⚠️  Modelos MLX não encontrados em $MLX_DIR"
    echo "   Corre: cd $MLX_DIR && python3 download_models.py"
fi

# ─── Sync with VPS ────────────────────────────────────────────────────────────
echo "🔄 A sincronizar com o VPS..."
python3 - << 'PYEOF'
import logging, sys
logging.basicConfig(level=logging.WARNING)
try:
    from magicfinance.sync import sync_on_startup
    r = sync_on_startup()
    if r["qdrant_ok"]:
        parts = []
        if r["events_pulled"] > 0:
            parts.append(f"{r['events_pulled']} eventos novos")
        if r["portfolio_updated"]:
            parts.append("portfolio actualizado")
        if not parts:
            parts.append("tudo em dia")
        print(f"✅ Sinc VPS: {', '.join(parts)}")
    else:
        print(f"⚠️  Qdrant offline — sem sinc ({r.get('error','')[:60]})")
except Exception as e:
    print(f"⚠️  Erro de sinc (não bloqueante): {e}")
PYEOF

echo ""
echo "🚀 A abrir MagicFinance no Streamlit..."
echo ""

# OpenMP fix for Apple Silicon (prevents duplicate libomp errors)
export KMP_DUPLICATE_LIB_OK=TRUE

streamlit run app.py

