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

# ─── Check Ollama ─────────────────────────────────────────────────────────────
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama não está a correr."
    echo "   Inicia com: ollama serve"
else
    echo "✅ Ollama: a correr"
fi

echo ""
echo "🚀 A abrir MagicFinance no Jupyter..."
echo ""

# Open Jupyter with the notebooks directory
jupyter notebook notebooks/

