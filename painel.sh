#!/usr/bin/env bash
# Painel de controle do Bot de Ofertas (Linux e macOS).
# Rode com:  bash painel.sh   (ou dê permissão: chmod +x painel.sh  e execute ./painel.sh)
set -e
cd "$(dirname "$0")"

echo
echo "  ============================================"
echo "    BOT DE OFERTAS - PAINEL DE CONTROLE"
echo "  ============================================"
echo

# 1) Garante o uv instalado
if ! command -v uv >/dev/null 2>&1; then
  echo "  O 'uv' nao esta instalado. Instalando agora..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  echo
  echo "  ------------------------------------------------------------"
  echo "  uv instalado! FECHE este terminal e rode o painel de novo."
  echo "  (ou rode:  source \$HOME/.local/bin/env  e tente de novo)"
  echo "  ------------------------------------------------------------"
  exit 0
fi

# 2) Prepara o ambiente (rapido depois da primeira vez)
echo "  Preparando o ambiente (pode demorar na primeira vez)..."
uv sync

# 3) Abre o painel no navegador
echo
echo "  Abrindo o painel no navegador..."
echo "  (deixe este terminal aberto enquanto usar o painel)"
echo
uv run python -m ofertas painel
