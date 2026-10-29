# Bot de ofertas para Telegram

Bot para Linux que busca ofertas no Mercado Livre, Amazon e Shopee e publica no Telegram com seus links de afiliado. Também converte links enviados pelo proprietário no privado do bot, com prévia para aprovar ou descartar.

O post no canal contém título, preço quando disponível e link no texto. A foto é enviada quando disponível; se o Telegram recusar a imagem, o bot envia texto. Os botões de compra, publicação e descarte aparecem apenas na prévia privada.

## Requisitos

- Python 3.12 ou superior e `uv` para preparar o ambiente.
- Um bot criado no @BotFather e um canal ou grupo onde ele possa publicar. Em canais, adicione o bot como administrador.
- Suas próprias contas e identificadores de afiliado nas plataformas utilizadas.
- Para o Mercado Livre: navegador compatível com Playwright e sessão de afiliado autenticada. O código tenta Google Chrome e, se não conseguir iniciá-lo, usa o Chromium instalado pelo projeto.
- Para login interativo no Mercado Livre: ambiente com interface gráfica e Google Chrome ou Chromium instalado no sistema. O comando `ml-login` não procura o Chromium baixado pelo Playwright. Em servidor sem interface, use a importação de cookies.

## Instalação e configuração

Na pasta do projeto, com `uv` disponível:

```bash
uv sync
uv run python -m ofertas instalar-navegador
cp .env.example .env
chmod 600 .env
nano .env
```

O comando `instalar-navegador` baixa o Chromium do Playwright em `data/pw-browsers`. Dependendo do sistema, bibliotecas adicionais do navegador podem ser necessárias.

Preencha o `.env` conforme as fontes que pretende usar:

| Variável | Uso |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token criado no @BotFather; necessário para iniciar o bot. |
| `TELEGRAM_OWNER_ID` | Seu ID numérico; autoriza a conversão de links e o comando `/ciclo` pelo Telegram. |
| `TELEGRAM_CHAT_ID` | Canal ou grupo de destino; necessário para publicar e habilitar os ciclos automáticos. |
| `ML_ETIQUETA` | Etiqueta da sua conta de afiliado no Linkbuilder do Mercado Livre. Requer também sessão autenticada. |
| `AMAZON_TAG` | Tag de associado; necessária para a coleta automática da Amazon. |
| `AMAZON_CREDENTIAL_ID`, `AMAZON_CREDENTIAL_SECRET` | Credenciais da Creators API. Sem elas, a busca da Amazon usa scraping. |
| `SHOPEE_APP_ID`, `SHOPEE_APP_SECRET` | Credenciais da Open API; necessárias para buscar ofertas e converter links da Shopee. |

Para descobrir os IDs, configure primeiro o token e inicie o bot com `uv run python -m ofertas run`. Envie `/id` no privado para obter seu ID e encaminhe uma mensagem do canal para descobrir o ID de origem. Depois, atualize o `.env` e reinicie o bot.

O `.env` e seus backups são ignorados pelo Git, assim como `data/`. Não compartilhe tokens, cookies ou perfis de navegador, mesmo em repositórios privados.

## Autenticação no Mercado Livre

Em um computador com interface gráfica:

```bash
uv run python -m ofertas ml-login
```

Entre na sua conta de afiliado e feche o navegador conforme as instruções do comando. A sessão fica em `data/ml_profile`.

Em servidor sem interface gráfica, exporte os cookies de uma sessão autenticada do Mercado Livre em JSON e transfira o arquivo de forma privada para `data/`. Com o bot parado, importe:

```bash
uv run python -m ofertas ml-importar-cookies data/cookies-ml.json
```

O importador aceita uma lista de cookies ou um objeto com a chave `cookies`, valida os domínios e tenta abrir o Linkbuilder autenticado. Se a sessão expirar ou exigir verificação adicional, renove o login ou os cookies. Veja [SERVIDOR.md](docs/SERVIDOR.md) para a operação no servidor.

## Iniciar pelo terminal

```bash
uv run python -m ofertas check
uv run python -m ofertas run
```

`check` lista pendências de configuração; não garante que credenciais e sessões funcionem. Ele também pode apontar credenciais de plataformas que você não pretende usar. Desative fontes não utilizadas no `config.yaml`.

`run` atende as mensagens privadas e agenda a coleta quando há uma fonte ativa, intervalo positivo e canal configurado. A primeira execução automática é agendada para 30 segundos após iniciar.

Comandos disponíveis no Telegram:

| Comando | Função |
| --- | --- |
| `/start` | Mostra as instruções de uso. |
| `/id` | Mostra os IDs do chat e do usuário. |
| `/status` | Mostra o total publicado e a configuração da coleta. |
| `/ciclo` | Executa um ciclo de busca e publicação; restrito ao proprietário. |

Para converter, envie um link reconhecido de uma das três plataformas no privado do bot. A publicação no canal depende da sua confirmação na prévia.

## Painel local

```bash
bash painel.sh
```

O script instala o `uv` caso esteja ausente e pede para reabrir o terminal. Com `uv` disponível, prepara as dependências e abre o painel em `http://127.0.0.1:8481`.

O painel permite configurar os campos das plataformas, detectar IDs, selecionar nichos, instalar o Chromium, iniciar o login do Mercado Livre, testar fontes e iniciar ou parar o processo do bot. Mantenha o terminal aberto: encerrar o painel também encerra o bot iniciado por ele.

A detecção de IDs usa as atualizações recebidas pelo bot; pare outra instância antes de utilizá-la. Alterações de configuração exigem reiniciar o processo do bot.

## Coleta e filtros

Edite [config.yaml](config.yaml) para ajustar as fontes e a publicação. A configuração versionada usa:

| Parâmetro | Valor atual |
| --- | --- |
| Intervalo entre ciclos | 45 minutos |
| Limite de posts por ciclo | 15 |
| Espaçamento entre posts | 5 segundos |
| Período sem repetir o mesmo produto | 7 dias |
| Horário dos ciclos | Das 08:00 às 23:00, sem incluir 23:00 |
| Desconto mínimo | 10% |

As três fontes estão habilitadas. O Mercado Livre combina categorias de tecnologia com uma entrada geral; a Amazon usa departamentos e buscas de tecnologia; a Shopee, sem termos de busca, consulta ofertas em destaque. Não é uma configuração uniforme de todas as categorias.

A seleção de nichos feita no painel fica em `data/nichos.json` e, quando não está vazia, substitui as categorias, departamentos e buscas do YAML. Os demais parâmetros continuam vindo do `config.yaml`.

Os ciclos filtram por desconto, preço, palavras bloqueadas e histórico de produtos publicados, e distribuem a seleção entre as plataformas disponíveis. Ofertas sem link de afiliado são descartadas antes da publicação.

`horario_ativo` usa o horário local do processo e vale para ciclos automáticos, `/ciclo` e o comando de terminal `ciclo`. A confirmação de uma prévia e o comando `postar` publicam diretamente, sem esses filtros ou restrição de horário.

## Outros comandos

Execute a partir da pasta do projeto:

```bash
# Testar a coleta sem publicar
uv run python -m ofertas testar ml
uv run python -m ofertas testar amazon
uv run python -m ofertas testar shopee

# Converter sem publicar
uv run python -m ofertas converter 'URL_DO_PRODUTO'

# Converter e publicar diretamente, sem prévia
uv run python -m ofertas postar 'URL_DO_PRODUTO'

# Executar um ciclo de coleta e publicação
uv run python -m ofertas ciclo

# Listar os comandos
uv run python -m ofertas --help
```

## Integração com Radar

Opcionalmente, configure `RADAR_API_URL`, `RADAR_TOKEN` e `RADAR_SOURCE_ID` no `.env`. O bot envia as ofertas publicadas pelos ciclos e pelas confirmações no Telegram para `RADAR_API_URL` acrescida de `/ingest`. O comando de terminal `postar` não faz esse envio.

As três variáveis precisam estar preenchidas para habilitar a integração. Falhas no Radar são registradas no log e não impedem a publicação no Telegram.

O painel ainda não oferece os campos do Radar e regrava o `.env` apenas com os campos conhecidos. Salvar configurações pelo painel remove essas variáveis; se usar Radar, mantenha a configuração pelo terminal.

## Operação contínua

`bash run.sh` prepara as dependências e reinicia o bot após 15 segundos quando o processo termina. Mantenha a sessão aberta, por exemplo em `tmux` ou `screen`.

Para iniciar com o servidor, há um modelo de serviço de usuário em [deploy/bot-ofertas.service](deploy/bot-ofertas.service). Ajuste os caminhos para a instalação e siga [SERVIDOR.md](docs/SERVIDOR.md). O modelo define o fuso `America/Sao_Paulo`.

Execute apenas uma instância do bot por token. Preserve `data/` entre reinícios: ela contém a sessão do navegador, a seleção de nichos e o histórico usado para evitar republicações.

## Problemas comuns

- `uv: command not found`: reabra o terminal após instalar ou execute `source "$HOME/.local/bin/env"`.
- Falha ao iniciar o navegador: execute `instalar-navegador` e confira as bibliotecas necessárias no sistema.
- Mercado Livre sem link de afiliado: confira a etiqueta, renove a sessão e teste `converter` com um produto. A presença de arquivos no perfil não garante login válido.
- Fonte sem ofertas: confira as credenciais e os logs com `testar`. Bloqueios, indisponibilidade e mudanças nas páginas ou APIs podem impedir a coleta.
- Nenhuma publicação no ciclo: verifique o horário, os filtros, os produtos já publicados, o canal de destino e as permissões do bot.

Use suas próprias contas de afiliado, respeite os termos das plataformas e informe no canal que os links podem gerar comissão.
