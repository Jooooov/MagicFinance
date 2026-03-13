#!/bin/bash
# MagicFinance — Launcher
# Duplo clique para abrir o Jupyter com o pipeline completo.

cd "$(dirname "$0")"

# ─── Check venv ───────────────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "📦 A criar ambiente virtual pela primeira vez..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --quiet -r requirements.txt
    echo "✅ Dependências instaladas"
else
    source venv/bin/activate
fi

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

echo ""
echo "🚀 A abrir MagicFinance no Jupyter..."
echo ""

# OpenMP fix for Apple Silicon (prevents duplicate libomp errors)
export KMP_DUPLICATE_LIB_OK=TRUE

# Open Jupyter with the notebooks directory
jupyter notebook notebooks/

