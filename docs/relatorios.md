# Relatórios PDF por botão do mobile

`POST /relatorios/pdf` é um serviço determinístico, não um agente do chat.
Não usa LLM, RAG, Redis, MongoDB ou Qdrant. A antiga rota conversacional
`relatorios` foi removida; o chat orienta o uso do botão do aplicativo.

## Requisição

```json
{
  "token": "token-do-aplicativo",
  "cd_id": 1,
  "camara_id": null,
  "data_inicial": "2026-10-01",
  "data_final": "2026-10-15"
}
```

GESTOR pode omitir `cd_id`: o cadastro determina seu CD. Se enviado, precisa
ser o mesmo. SUPER_ADMIN precisa escolher um CD; ADMIN e OPERADOR são bloqueados.
`camara_id: null` seleciona todas as câmaras desse CD. Uma identificação inválida
não amplia o filtro. O corpo não aceita usuário, permissões ou dados calculados.

As datas são obrigatórias no formato YYYY-MM-DD. O último dia é incluído usando
o início do dia seguinte como limite exclusivo. Os TIMESTAMP sem fuso do banco
seguem a convenção do produtor, America/Sao_Paulo. Não há migração de datas.

## Documento e cálculos

O backend consulta cadastro, leituras e alertas no mesmo snapshot PostgreSQL
REPEATABLE READ, somente leitura. Reutiliza a autorização e a consulta cadastral
do monitoramento, com cursor compartilhado; não reutiliza seu filtro de alertas
ativos/reconhecidos, pois o relatório é histórico e inclui todos os status.

- Mínima/máxima globais e média aritmética de todas as leituras do filtro.
- Quantidade de leituras, primeiro e último horário efetivamente observados.
- Cada alerta é contado uma vez; críticos são os de gravidade `crítica`.
- Alertas filtrados pela criação no período, ordenados do mais recente ao antigo.
- Status e gravidade são os existentes na consulta, não seu estado em uma data passada.
- Uma série por câmara no gráfico, com os pontos registrados, sem criar leituras
  intermediárias; as linhas só conectam os registros.
- Sem leituras: estatísticas indisponíveis, não zero. Sem alertas: contagem zero.
- Valores não finitos ou datas de leitura inválidas impedem a geração.
- Eventos `sim-trimmy-...` causam aviso de dados de teste, inclusive em séries mistas.

O documento usa o cadastro e os vínculos atuais dos termômetros; não reconstrói
movimentações de equipamentos. Quantidades refletem os registros disponíveis,
não garantem coleta contínua. Alertas não recebem temperaturas por associação
textual ou proximidade de horário. Não há diagnóstico, previsão ou assinatura.

ReportLab gera o PDF em memória após fechar a transação de consulta. Texto de
cadastro é escapado antes de usar Paragraph. A tabela de ocorrências pagina
automaticamente, sem truncar registros. O cabeçalho é textual, sem logo presumido.

O layout segue `design.md`: cabeçalho azul-escuro, faixas e cartões arredondados,
indicadores rosa, valores com vírgula e rodapé `Página N de M`. A primeira página
prioriza o resumo e o gráfico; as ocorrências e a disponibilidade de cada câmara
ficam nos detalhes. A legenda mostra somente séries com leituras; câmaras sem
dados permanecem na seleção, mas são identificadas como sem leituras no período.
Não houve mudança nos cálculos, autorização ou registro transacional.

## Entrega e auditoria

Depois de renderizar, o serviço reconfere o perfil/CD e registra em uma única
transação `tb_relatorio` com usuário, datas, SHA-256 dos bytes e status `gerado`,
e `tb_log_acesso_relatorio` com ação `baixou`. Os valores correspondem ao schema
implantado conferido no planejamento, não aos valores maiúsculos de outro script.
Falha causa rollback e nenhum PDF é entregue. Essa operação não modifica alertas
ou leituras. `baixou` registra disponibilização pela API, não recebimento no celular.
Uma desconexão ou falha de rede depois do commit pode deixar o registro sem que
o cliente receba o arquivo. Não há transação distribuída com o dispositivo.

Cada chamada gera outro relatório. Não existe cópia persistente do arquivo ou
endpoint para recuperar o mesmo PDF; os metadados atuais não guardam CD/câmara
nem permitem reproduzir todos os filtros. Não foram criadas tabelas ou migrations.

Sucesso: `application/pdf`, `Content-Disposition: attachment` e
`Cache-Control: no-store`. Nome gerado pelo servidor a partir das datas.
Erros: 403 acesso; 404 seleção; 409 dados inconsistentes; 422 filtros;
503 banco; 500 falha inesperada. Erros de validação desse endpoint não repetem
o corpo recebido (que contém token). Logs não incluem tokens, SQL ou mensagens
brutas de SDKs. A rota de chat mantém seu contrato anterior.

## Uso e testes

Instale `pip install -r requirements.txt`; o manifesto inclui ReportLab em
produção e pypdf nos testes. Inicie `uvicorn app.main:app --reload` e abra `/docs`.
No aplicativo, leia a resposta como bytes/blob para o download, não como JSON.

A autenticação usa o mock central de usuário 12, conferido como GESTOR do CD 2
no banco de teste. Qualquer token não muda sua identidade; a escolha vale também
para o chat. Omita `cd_id` ou envie 2. Se o cadastro ou perfil mudar, a validação
do banco prevalece e poderá retornar 403. Nenhuma permissão foi alterada.
Produção exige a autenticação real do aplicativo.

Os testes usam mocks e PDFs em memória, sem chamadas a bancos/provedores.
Incluem permissões, fronteiras de datas no SQL, indicadores, filtros, saída
HTTP, rollback, hash, erros e paginação. Exemplos de revisão visual são
explicitamente simulados e não registram relatórios nos bancos. Integração
real de geração/auditoria só deverá ocorrer em validação autorizada separada.

Validação em 16/10/2026: 355 testes aprovados, quatro integrações reais não
executadas e dois avisos de depreciação de dependências. Ruff e `git diff --check`
passaram. A revisão visual prevista na skill de PDF renderizou e inspecionou
todas as páginas dos exemplos de uma e três câmaras, incluindo paginação,
acentos, valores negativos, legenda e aviso de simulação. As tabelas não foram
cortadas para caber em uma página. Os exemplos locais são ignorados pelo Git
e não correspondem a relatórios gerados a partir dos bancos.

Revisão em 17/10/2026: layout de `design.md` aplicado, com cartões arredondados,
cores de referência, vírgula decimal, resumo na primeira página e total real de
páginas no rodapé. A legenda passou a excluir câmaras sem leituras, que são
identificadas nos detalhes. Testes de apresentação verificam os indicadores
repetidos, dados inalterados, paginação e ausência de séries vazias. A regressão
passou com 357 testes e quatro integrações não executadas; Ruff passou.
A skill de PDF orientou a revisão visual de todas as páginas dos exemplos com
uma/múltiplas câmaras, do caso sem leituras e da prévia do CD 2. Essa prévia foi
gerada localmente com consultas de leitura, sem passar por `registrar_relatorio`:
não criou registros de geração/download, não substituiu o PDF do usuário e não
alterou dados operacionais. O logotipo oficial ainda não foi fornecido; o
cabeçalho usa a identificação textual SKADI prevista no design.
