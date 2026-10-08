#!/usr/bin/env bash
# Liga o bot direto no terminal (Linux e macOS). Reinicia sozinho se cair.
# Prefira o painel grafico:  bash painel.sh
set -e
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "Instale o uv primeiro:  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

uv sync
while true; do
  uv run python -m ofertas run || true
  echo
  echo "O bot parou. Reiniciando em 15s (Ctrl+C para sair)..."
  sleep 15
done
