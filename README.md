# Bot de Ofertas para Telegram 🔥 — Linux

Bot que roda **no seu PC/servidor Linux**, garimpa promoções em **Mercado Livre, Shopee e Amazon** e posta no seu canal do Telegram com **os seus links de afiliado** — foto, preço "de/por", desconto e botão de compra. Tudo local, sem mensalidade.

> ⚠️ Você precisa das **suas próprias** contas de afiliado (Mercado Livre, Amazon Associados, Shopee Afiliados). As comissões vão para quem configurar.

## Como funciona

1. **Automático** — de tempos em tempos busca ofertas, filtra por desconto mínimo, evita repetir produto e posta as melhores no canal com o seu link.
2. **Conversor** — você cola qualquer link de produto no privado do bot; ele monta a prévia do post e você decide **✅ Postar** ou **🗑 Descartar**.

Por padrão pega **ofertas de todas as categorias**. Para focar num nicho, edite o `config.yaml` (tem exemplos comentados).

## Pré-requisitos

- **Google Chrome** instalado (usado para gerar os links do Mercado Livre). Instale o `.deb`/`.rpm` do [google.com/chrome](https://www.google.com/chrome/) — em Debian/Ubuntu:
  ```bash
  wget -qO- https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
  sudo apt update && sudo apt install -y google-chrome-stable
  ```
  (Chromium também serve como alternativa.)
- Uma conta no Telegram, um bot (@BotFather) e um canal.

## Jeito fácil: o painel gráfico (recomendado)

No terminal, dentro da pasta do bot:
```bash
bash painel.sh
```
Ele instala o que falta e abre um **painel no navegador**, onde você faz tudo com formulário e botões — configurar, descobrir os IDs do Telegram, instalar o navegador, fazer o login do Mercado Livre, testar e **ligar/desligar o bot** — sem mais comandos.

> Na primeira vez, se o `uv` não estiver instalado, o script instala e pede para reabrir o terminal (ou rode `source $HOME/.local/bin/env`).

## Passo a passo (manual, pelo terminal)

```bash
# 1. Instalar o uv (uma vez)
curl -LsSf https://astral.sh/uv/install.sh | sh
#    reabra o terminal depois

# 2. Na pasta do bot:
uv sync
uv run python -m ofertas instalar-navegador   # navegador do Linkbuilder

# 3. Configurar (crie o bot no @BotFather e um canal com o bot como admin)
cp .env.example .env
nano .env        # cole o token; os IDs saem no painel ou mandando /id ao bot

# 4. Login no Mercado Livre (abre o Chrome; logue e feche o navegador)
uv run python -m ofertas ml-login

# 5. Conferir e rodar
uv run python -m ofertas check
uv run python -m ofertas run     # ou: bash run.sh (reinicia sozinho se cair)
```

Preencha no `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`, `TELEGRAM_CHAT_ID` (o painel tem um botão **Detectar IDs**), `ML_ETIQUETA` (Linkbuilder do painel de afiliados), `AMAZON_TAG`, e opcionalmente as credenciais da Creators API (Amazon) e da Open API (Shopee).

## Deixar rodando sozinho

- `bash run.sh` reinicia o bot se ele cair. `horario_ativo` no `config.yaml` evita posts de madrugada.
- Servidor 24/7? Rode em um `tmux`/`screen`, ou crie um serviço `systemd` apontando para `uv run python -m ofertas run` (com `WorkingDirectory` na pasta do bot).

## Problemas comuns

- **`uv: command not found`** logo após instalar: reabra o terminal ou rode `source $HOME/.local/bin/env`.
- **"Google Chrome não encontrado"**: instale o Google Chrome (ou Chromium) — veja *Pré-requisitos*.
- **`testar ml` não acha ofertas**: refaça o `ml-login` (a sessão pode ter expirado).

## ⚖️ Uso responsável

- **Divulgação obrigatória**: avise no canal que há links de afiliado (exigência dos programas, principalmente Amazon). Ex.: *"Contém links de afiliado; podemos receber comissão pelas compras, sem custo extra para você."*
- Respeite os termos de cada plataforma; os padrões do `config.yaml` já são comedidos.
