# Operação do bot de ofertas no servidor

Servidor: `usuario@SEU_SERVIDOR`.
Projeto: `/home/usuario/bot-ofertas-telegram-linux`.
Serviço: `bot-ofertas.service` (systemd de usuário).

O serviço permanece funcionando depois de fechar o SSH, inicia com o servidor
e reinicia se o processo falhar. Sem token configurado, sua condição de início
mantém o bot parado. O fuso do serviço é `America/Sao_Paulo`.

## Acessar e configurar

```bash
ssh usuario@SEU_SERVIDOR
cd ~/bot-ofertas-telegram-linux
nano .env
chmod 600 .env
```

Campos necessários:

- `TELEGRAM_BOT_TOKEN`: token obtido no BotFather.
- `TELEGRAM_CHAT_ID`: ID confirmado do canal/grupo de destino.
- `TELEGRAM_OWNER_ID`: seu ID de usuário, autorizado a converter e postar.
- `ML_ETIQUETA`: etiqueta do Linkbuilder da sua conta de afiliado.

Reinicie o serviço após alterar `.env` ou `config.yaml`:

```bash
systemctl --user restart bot-ofertas.service
```

Para obter seu ID, envie `/id` no privado do bot. Para obter o ID de um canal,
encaminhe uma publicação dele ao privado do bot. Em grupos, também pode usar
`/id@nome_do_bot`. No canal, o bot precisa ser administrador com permissão
para publicar. Não confunda o link de convite com o ID numérico.

## Renovar cookies do Mercado Livre

A data de expiração de um cookie não garante a duração do login: a sessão
pode ser revogada ou exigir nova verificação. Renove quando o Linkbuilder
redirecionar para login ou a geração de links deixar de funcionar por autenticação.

### 1. Exportar no computador

Entre na conta de afiliado no navegador e abra o Linkbuilder. Exporte os
cookies dos domínios do Mercado Livre em JSON, incluindo HttpOnly. O nome
usado nesta instalação é `coockiesML.json`.

Cookies permitem acesso à conta. Não cole seus valores no chat, não os
compartilhe e não os inclua no Git. O arquivo com esse nome está ignorado no
repositório, assim como o diretório `data/`.

### 2. Parar o serviço e transferir

No servidor:

```bash
systemctl --user stop bot-ofertas.service
mkdir -p ~/bot-ofertas-telegram-linux/data
chmod 700 ~/bot-ofertas-telegram-linux/data
```

No computador, na pasta onde está o novo arquivo:

```bash
chmod 600 coockiesML.json
scp coockiesML.json usuario@SEU_SERVIDOR:~/bot-ofertas-telegram-linux/data/coockiesML.json
```

### 3. Importar e validar no servidor

```bash
cd ~/bot-ofertas-telegram-linux
chmod 600 data/coockiesML.json
.venv/bin/python -m ofertas ml-importar-cookies data/coockiesML.json
.venv/bin/python -m ofertas converter 'URL_REAL_DE_UM_PRODUTO_DO_MERCADO_LIVRE'
```

Substitua a URL de exemplo por um produto real. `converter` consulta o produto
e gera um link de afiliado, mas não publica no Telegram. Confirme que o link
foi gerado antes de reativar as postagens.

O importador converte os atributos para o Playwright, descarta cookies
expirados e salva a sessão no perfil persistente `data/ml_profile`. A mensagem
sobre abrir o Linkbuilder sem redirecionamento não substitui o teste de geração
do link. Se falhar, mantenha o serviço parado e revise a sessão exportada.

**Importar cookies não altera `config.yaml` nem desliga a programação.** A
mensagem atual do importador sobre coleta desligada não deve ser interpretada
como uma mudança de configuração. Parar o serviço antes da importação evita
publicações e disputa pelo perfil do navegador durante a manutenção.

### 4. Retomar

```bash
systemctl --user start bot-ofertas.service
systemctl --user status bot-ofertas.service --no-pager
journalctl --user -u bot-ofertas.service -n 30 --no-pager
```

Se a programação já estava habilitada, iniciar o serviço pode publicar ofertas
no primeiro ciclo, aproximadamente 30 segundos depois, dentro do horário ativo.

## Ativar postagens automáticas somente do Mercado Livre

Antes de ativar, confirme:

- Token, destino, proprietário e etiqueta corretos no `.env`.
- Permissão do bot para publicar no destino.
- Sessão e geração de links validadas pelo procedimento anterior.
- Regras de divulgação do programa de afiliados atendidas. O guia do Mercado
  Livre indica Telegram público entre os canais permitidos: [checklist oficial](https://www.mercadolivre.com.br/l/checklist).

Pare o serviço e edite a configuração:

```bash
systemctl --user stop bot-ofertas.service
cd ~/bot-ofertas-telegram-linux
nano config.yaml
```

Ajuste os campos nas seções **existentes**, sem duplicar as chaves `geral`,
`filtros` ou `fontes`. Preserve categorias e outras opções que já configurou.
Exemplo dos campos relevantes:

```yaml
geral:
  intervalo_minutos: 45
  max_posts_por_ciclo: 3
  espacamento_segundos: 120
  nao_repetir_dias: 7
  horario_ativo: "08:00-23:00"

filtros:
  desconto_minimo: 25
  preco_minimo: 0
  preco_maximo: 0
  palavras_bloqueadas: []

fontes:
  mercadolivre:
    ativa: true
  amazon:
    ativa: false
  shopee:
    ativa: false
```

- O bot verifica ofertas a cada 45 minutos e publica até três por ciclo.
- Há uma pausa de 120 segundos entre as postagens do ciclo.
- A coleta automática evita repetir o mesmo produto por sete dias.
- O horário é o de Brasília; `23:00` já está fora da janela deste exemplo.
- `horario_ativo: ""` permite postagens durante as 24 horas. Não use horário
  malformado: o código atual trata um formato inválido como horário livre.
- Limites de preço em zero significam ausência de limite.

Teste a coleta sem publicar e depois inicie o serviço:

```bash
.venv/bin/python -m ofertas testar ml
systemctl --user enable bot-ofertas.service
systemctl --user start bot-ofertas.service
journalctl --user -u bot-ofertas.service -f
```

O primeiro ciclo é agendado para aproximadamente **30 segundos após iniciar**.
Ele só publica se estiver no horário ativo e encontrar ofertas aprovadas com
link de afiliado. Fechar o comando de logs com Ctrl+C não encerra o serviço.

## Pausar postagens

Para interromper o bot:

```bash
systemctl --user stop bot-ofertas.service
```

Para manter os comandos privados funcionando, mas desligar o agendamento,
altere `geral.intervalo_minutos` para `0` e reinicie o serviço.

**Intervalo zero desliga somente o agendamento.** `/ciclo`, publicações manuais
e o botão de confirmação de uma prévia ainda podem publicar. Para desligar
as coletas manuais também, mantenha todas as fontes com `ativa: false`;
publicações diretas por link continuam sendo ações separadas.

## Comandos de gerenciamento

Execute no servidor; os comandos `.venv/bin/python` exigem a pasta do projeto.

| Comando | Uso |
|---|---|
| `systemctl --user status bot-ofertas.service --no-pager` | Estado do processo e últimos logs. |
| `systemctl --user start bot-ofertas.service` | Iniciar. Pode disparar o ciclo automático após 30 segundos. |
| `systemctl --user stop bot-ofertas.service` | Parar. |
| `systemctl --user restart bot-ofertas.service` | Recarregar código e configuração. |
| `systemctl --user enable bot-ofertas.service` | Habilitar início com o servidor. Não inicia imediatamente. |
| `systemctl --user disable --now bot-ofertas.service` | Parar e desabilitar início automático. |
| `systemctl --user is-enabled bot-ofertas.service` | Conferir início automático. |
| `systemctl --user show bot-ofertas.service -p NRestarts -p Result` | Conferir reinícios e resultado. |
| `journalctl --user -u bot-ofertas.service -n 50 --no-pager` | Ver os últimos 50 registros. |
| `journalctl --user -u bot-ofertas.service -f` | Acompanhar os logs. |
| `loginctl show-user usuario -p Linger` | Conferir execução sem sessão SSH; nesta instalação está habilitada. |
| `systemctl --user daemon-reload` | Recarregar a definição do serviço após editar seu arquivo. |

### CLI do projeto

```bash
cd ~/bot-ofertas-telegram-linux
.venv/bin/python -m ofertas --help
.venv/bin/python -m ofertas check
.venv/bin/python -m ofertas testar ml
.venv/bin/python -m ofertas converter 'URL_REAL_DO_PRODUTO'
```

`check` é uma checagem geral e pode apontar credenciais ausentes de lojas que
você deixou desativadas. Não é uma validação completa da sessão do Mercado Livre.

Os comandos a seguir **publicam**; use apenas quando desejar enviar ofertas:

```bash
TZ=America/Sao_Paulo .venv/bin/python -m ofertas ciclo
.venv/bin/python -m ofertas postar 'URL_REAL_DO_PRODUTO'
```

`ciclo` respeita fontes, filtros, deduplicação e horário ativo. `postar` é uma
publicação direta e não aplica esses filtros da seleção automática.

Pare o serviço antes de testes CLI que usem o navegador do Mercado Livre e
antes de um ciclo manual, para evitar acesso concorrente ao perfil e ciclos
simultâneos. Ao iniciar o serviço novamente, considere a programação configurada.
Não use `run.sh`, `run` ou o painel para iniciar outra cópia enquanto o serviço
estiver ativo: duas instâncias disputariam os updates do mesmo bot.

### Comandos no Telegram

| Comando/ação | Uso |
|---|---|
| `/start` | Instruções de uso do bot. |
| `/id` | ID do chat privado e do seu usuário. |
| `/status` | Resumo da configuração e do histórico de produtos. |
| `/ciclo` | Solicitar um ciclo de publicação; permitido ao proprietário configurado. |
| Enviar um link no privado | Preparar prévia; confirmar no botão para publicar. |
| Encaminhar publicação de canal ao privado | Obter o ID do canal; se contiver link de produto reconhecido, inicia a conversão. |

## Arquivos e dependências

- `.env`: credenciais; mantenha permissão 600.
- `config.yaml`: filtros, fontes e agendamento.
- `config.yaml.original`: configuração preservada antes da preparação inicial.
- `data/coockiesML.json`: exportação privada dos cookies.
- `data/ml_profile/`: perfil autenticado; não apagar durante uma execução.
- `data/ofertas.db`: histórico usado para evitar repetições automáticas.
- `data/pw-browsers/`: Chromium instalado pelo Playwright.
- `data/browser-libs/`: bibliotecas do Ubuntu extraídas no projeto, sem alterar
  os pacotes do sistema; usadas pelo navegador nesta instalação.
- `~/.config/systemd/user/bot-ofertas.service`: definição do serviço.

As dependências Python são instaladas com `~/.local/bin/uv sync --frozen`, usando
Python 3.14 do servidor. O serviço executa diretamente o Python da `.venv`.
Para reinstalar o navegador, com o serviço parado:

```bash
.venv/bin/python -m ofertas instalar-navegador
```

Não apague o histórico nem o perfil para corrigir um erro genérico: isso pode
permitir repetições ou remover a sessão. Consulte os logs antes de alterar dados.

Na conferência de 08/10/2026, o Mercado Livre e o agendamento estavam ativos,
com publicações confirmadas nos logs. Consulte o registro e os valores dessa
conferência em [RELATORIO_2026-10-08.md](RELATORIO_2026-10-08.md).
Este guia documenta a ativação; escrever ou copiar o arquivo não ativa postagens.


```
geral:
  intervalo_minutos: 45
  max_posts_por_ciclo: 3
  espacamento_segundos: 120
  nao_repetir_dias: 7
  horario_ativo: "08:00-23:00"
```

| Campo | O que significa |
|---|---|
| `intervalo_minutos` | Tempo entre os ciclos de busca. `45` significa executar a cada 45 minutos. `0` desliga o agendamento automático. |
| `max_posts_por_ciclo` | Máximo de ofertas publicadas em cada ciclo. Com `3`, pode publicar até três — ou menos, se faltarem ofertas aprovadas. |
| `espacamento_segundos` | Pausa entre as postagens do mesmo ciclo. `120` significa dois minutos. |
| `nao_repetir_dias` | Evita que a seleção automática reposte o mesmo produto durante esse período. `7` significa sete dias. |
| `horario_ativo` | Horário permitido para os ciclos, no fuso de Brasília. `"08:00-23:00"` permite das 08h até antes das 23h. `""` permite as 24 horas. |

Nesse exemplo, o bot busca ofertas a cada 45 minutos, publica até três com dois minutos de intervalo e evita repetir produtos por sete dias. **O bot permanece online fora do horário, mas não executa os ciclos de ofertas.**
