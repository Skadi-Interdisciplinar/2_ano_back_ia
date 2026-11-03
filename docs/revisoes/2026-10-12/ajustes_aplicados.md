# Ajustes após a revisão

Autorizados pelo usuário nesta conversa em 12/10/2026. API somente local e bancos
com dados de teste. Sem alteração de schema ou escrita nos bancos nesta entrega.

## Comportamentos alterados

- Diagnóstico: além da origem literal e das verificações já existentes, exige
  vocabulário explícito da observação aprovada no trecho. Frases genéricas,
  perguntas ou comandos de classificação não satisfazem requisitos. Quando o
  filtro não reconhece uma paráfrase, retorna a pergunta aprovada para esclarecer.
  É uma guarda conservadora, não prova semântica completa nem confirmação técnica.
  Não altera as oito regras aprovadas, cenários ou recomendações do RAG.
- Apresentação: remove itálico com marcadores junto ao texto, preservando
  multiplicações como `2 * 3 * 4`, `2*3*4` e `x * y * z`.
- Acesso: a conexão PostgreSQL é explicitamente fechada também em erro.
- Autenticação: removido middleware que gravava uma identidade não consumida.
  O mock existente em `auth.py` permanece como única fonte temporária de identidade.
- Removidos configuração mock sem consumidor, verificador de configuração sem
  uso, logger sem uso, entradas inalcançáveis do mapa de prompts e função de
  gravação de execuções que não era chamada pelo fluxo. Não há tracing novo.
- MongoDB e memória Qdrant: preparação do índice/coleção cacheada por processo,
  somente após sucesso. Falhas continuam sendo propagadas e permitem nova tentativa.
- Dependências: `requirements.txt` usa `pyproject.toml` como fonte única. O build
  agora inclui `app` e seu JSON de regras em vez do stub `src/agente_ia`. Pytest
  mantém apenas `pytest.ini`; o CI deixa de instalar o mesmo projeto duas vezes.

## Preservado

Contrato token + mensagem, permissões por CD, filtros de alertas, tools públicas,
autenticação temporária, fontes e ressalvas do diagnóstico e histórico integral.
Nada foi commitado, publicado ou indexado em infraestrutura real.

## Verificação

- Suíte completa: 282 passaram, 4 integrações reais puladas, 2 avisos de dependências.
- Após o último refinamento do filtro de exposição do sensor, os 126 testes dos
  módulos afetados passaram novamente. Essa execução inclui o novo caso em que
  a mera menção ao sensor longe da porta não satisfaz exposição.
- Ruff passou. Metadados TOML conferidos localmente; não foi construído um wheel,
  pois `build` e `hatchling` não estão instalados no ambiente de testes utilizado.
- Testes com mocks não comprovam conexões reais, RAG indexado ou qualidade das
  respostas do modelo. Não foram usados serviços externos nesta etapa.

## Ainda exige decisão ou validação separada

- Memória: o array ainda cresce; leitura com projeção, associação da resposta à
  mesma sessão e mudança para mensagens individuais devem ser tratadas em etapa
  específica. Não foi escolhido um limite de retenção nem descartado histórico.
- Timeout/retries e duração de sessões: continuam sem novos valores arbitrários.
- Autenticação real antes de publicação; avaliação com perguntas e serviços reais.
- Build isolado do wheel precisa ser executado com ferramentas de build disponíveis.
- Os relatórios anteriores registram o estado encontrado na revisão, não o estado
  após estas correções. As limitações não listadas como resolvidas permanecem.
