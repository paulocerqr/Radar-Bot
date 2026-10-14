# Bot de ofertas: trabalho realizado em 08/10/2026

Estado conferido em **08/10/2026, aproximadamente 14h48, horário de Brasília**.
Este relatório é um registro desse momento; a configuração e os logs podem
mudar depois. O guia operacional está em [SERVIDOR.md](SERVIDOR.md).

## Objetivo e escopo

Preparar o bot no servidor para manter o canal de ofertas funcionando e,
futuramente, usar as ofertas publicadas como entrada de um perfil no Radar.
Esse perfil poderá buscar vídeos de produtos e produzir conteúdo para YouTube
e TikTok, direcionando interessados ao Telegram.

Hoje trabalhamos na operação do bot. A integração com n8n, Radar e produção
de vídeos foi analisada, mas ainda não foi implementada.

## Instalação no servidor

- Servidor: `usuario@SEU_SERVIDOR`.
- Projeto: `/home/usuario/bot-ofertas-telegram-linux`.
- Serviço: `bot-ofertas.service`, no systemd do usuário.
- Python: 3.14.4, com dependências instaladas na `.venv` usando o lockfile.
- Serviço habilitado para iniciar com o servidor, reiniciar em caso de falha
  e continuar funcionando depois de fechar a sessão SSH. Linger está habilitado.
- Fuso do processo: `America/Sao_Paulo`.
- Credenciais no `.env`, com permissão 600, sem registrar valores neste relatório.

Na preparação inicial, todas as fontes e o agendamento foram desativados para
validar a conexão e a sessão sem publicar ofertas.

## Telegram configurado

- Bot: `@cerqr_radar_bot`.
- Destino: canal **Radar de Ofertas**.
- ID confirmado pela Bot API: `-1003558182778`.
- Bot administrador com permissão para publicar.
- Proprietário configurado a partir do criador do canal retornado pelo Telegram.

O número inicialmente informado, `-3558182778`, não foi usado diretamente.
O ID correto foi confirmado consultando o Telegram. O link de convite não
substitui esse identificador.

O bot recebe comandos por polling. Não configurar um Telegram Trigger do
n8n com o mesmo token enquanto esse processo estiver recebendo updates.

## Fontes disponíveis

| Fonte | Situação |
|---|---|
| Mercado Livre | Etiqueta configurada, sessão autenticada e geração de links validadas; fonte automática atualmente ativa. |
| Amazon | StoreID configurado; acesso à API ainda não disponível conforme informado pelo proprietário. Fonte automática desativada. |
| Shopee | Aprovação de acesso à API pendente conforme informado pelo proprietário. Fonte automática desativada. |

No Mercado Livre, coletar dados e gerar links de afiliado são operações
diferentes. O código coleta páginas de produtos e usa o Linkbuilder com a
sessão autenticada para gerar links. Esse gerador usa um endpoint interno,
não uma integração pública documentada de API de afiliados.

## Cookies e navegador

1. O proprietário exportou `coockiesML.json` da sessão deste computador.
2. O arquivo foi protegido com permissão 600 e adicionado ao `.gitignore`.
3. Criamos o comando `ml-importar-cookies` para adaptar o JSON ao Playwright,
   validar os domínios, preservar atributos de autenticação e descartar
   cookies expirados.
4. O arquivo foi transferido por SSH para `data/coockiesML.json` no servidor.
5. Dos 53 cookies exportados, 52 foram importados; um expirado foi descartado.
6. O Linkbuilder abriu sem redirecionar para login, e a geração de um link
   de afiliado foi testada com sucesso, sem publicação no Telegram nesse teste.

O cookie `ssid` da exportação informa expiração em **12/11/2027, às 11h33,
horário de Brasília**. Isso não garante que a autenticação durará até essa
data: a sessão pode ser revogada ou exigir nova verificação.

Instalamos o Chromium do Playwright em `data/pw-browsers`. O servidor não
tinha todas as bibliotecas necessárias; pacotes do Ubuntu foram baixados e
extraídos em `data/browser-libs`, sem instalação como root nem alteração de
pacotes do sistema. O navegador usa essas bibliotecas quando disponíveis.

A sessão persistente fica em `data/ml_profile`. Cookies e perfil autenticado
não devem ser publicados, compartilhados ou incluídos no Git.

## Correção da coleta

A coleta HTTP original retornou zero ofertas. Na mesma página renderizada
pelo navegador autenticado, o parser existente conseguiu ler 48 cards.

Adicionamos um caminho alternativo: quando o HTML recebido por HTTP não
contém ofertas e existe um perfil salvo, o coletor abre a página no navegador
e reaproveita o parser existente. O contexto é fechado depois da leitura.

No teste integrado posterior, foram coletadas **46 ofertas** e um link de
afiliado foi gerado. Esses números refletem a página naquele momento e não
são uma quantidade fixa garantida para os próximos ciclos.

## Ativação das postagens

O proprietário ajustou intervalo, limites e filtros. Inicialmente ainda não
havia publicações porque todas as fontes continuavam com `ativa: false`;
os logs indicavam que o ciclo automático estava desligado.

Depois da ativação do Mercado Livre e reinício do serviço, os logs passaram
a indicar **ciclo automático a cada 45 minutos**.

Às **14h32min21s**, há um ciclo concluído registrado com:

```text
46 coletadas, 46 aprovadas, 10 postadas
```

O serviço foi iniciado novamente às **14h47**, com o agendamento ativo.
Na conferência deste relatório, ainda não havia um resumo concluído desse
novo ciclo. Não interpretar o limite atual de 25 como 25 publicações já feitas.

## Configuração atual conferida no servidor

| Campo | Valor |
|---|---|
| `geral.intervalo_minutos` | 45 |
| `geral.max_posts_por_ciclo` | 25 |
| `geral.espacamento_segundos` | 10 |
| `geral.nao_repetir_dias` | 7 |
| `geral.horario_ativo` | `08:00-23:00` |
| `filtros.desconto_minimo` | 10 |
| `filtros.preco_minimo` | 0: sem limite |
| `filtros.preco_maximo` | 0: sem limite |
| `fontes.mercadolivre.ativa` | true |
| `fontes.amazon.ativa` | false |
| `fontes.shopee.ativa` | false |

O serviço estava **ativo e em execução**, com `NRestarts=0` na instância atual.
Isso não significa que nunca foi reiniciado: houve reinícios de configuração
e manutenção durante o dia.

O bot seleciona até 25 ofertas por ciclo, respeitando filtros e histórico.
Pode publicar menos se faltarem ofertas válidas ou se uma etapa falhar.
A janela permite ciclos das 08h até antes das 23h; o bot continua online fora
desse período. Após iniciar, o primeiro ciclo é agendado para cerca de 30 segundos.

## Verificações realizadas

- Validação do serviço systemd e importação dos módulos Python.
- Confirmação do bot, canal, ID e permissão de publicação pela API do Telegram.
- Testes de normalização dos cookies e fallback de coleta: dois testes passaram.
- Testes reais de abertura do navegador, coleta e geração de link de afiliado.
- Conferência de permissões do arquivo de cookies e exclusão pelo Git.
- Atualização do grafo do repositório com extração de código, sem chamadas de IA.
- Documentação de renovação de sessão, agendamento e gerenciamento em `SERVIDOR.md`.

## Limitações e próximos passos

- A geração de links depende da sessão e de um endpoint interno do Mercado
  Livre; mudanças no site ou na autenticação podem interromper a operação.
- O fallback de coleta foi adicionado para resposta HTTP sem cards. Erros HTTP
  continuam podendo interromper a coleta; não foi prometido contornar bloqueios.
- O navegador é aberto por página no fallback. Se muitas categorias tornarem
  o ciclo lento, compartilhar o contexto pode ser uma melhoria futura.
- Confirmar as regras de divulgação do programa antes de ampliar a operação.
  O [checklist oficial do Mercado Livre](https://www.mercadolivre.com.br/l/checklist)
  indica Telegram público entre os destinos permitidos. A visibilidade atual
  do canal não foi reconfirmada nesta leitura de configuração e logs.
- Aguardar os acessos das APIs de Amazon e Shopee antes de planejar sua ativação.
- Futuramente, integrar um evento estruturado de oferta publicada ao n8n,
  com ID da mensagem, produto e preço, para alimentar o Radar sem depender
  de reconstruir dados a partir do texto do Telegram.
- O perfil de vídeos de produtos, a busca no Pinterest e a captação por
  YouTube/TikTok ainda pertencem à próxima etapa.

Os testes de importação e geração de links não publicaram mensagens.
As dez postagens citadas foram registradas pelo ciclo automático do bot
após sua ativação.
