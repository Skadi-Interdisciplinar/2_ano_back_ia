# Acompanhamento da Implementacao Skadi

## Etapa: Fundacao segura do backend da IA

### Solicitacao
Desenvolver o backend da IA do Skadi usando o Assessor apenas como referencia arquitetural, sem inventar regras de negocio.

### Plano do Arquiteto do Skadi
- Criar a estrutura `app/` com FastAPI, configuracao, schemas, rota de chat, grafo, prompts, memoria e tools.
- Usar Gemini e Groq como provedores de IA, seguindo a estrutura tecnica do Assessor.
- Obter a identidade somente da camada de autenticacao ja validada pelo aplicativo. O corpo do chat nao recebe `usuarioId`.
- Usar temporariamente os niveis existentes no PostgreSQL: `admin`, `gestor` e `operador`.
- Manter bloqueadas as consultas operacionais que dependem de uma associacao usuario-camara para operadores, de criterios de predicao, de regras tecnicas de diagnostico ou de FAQ aprovada.

### Validacao de Arquitetura
ARQUITETURA APROVADA para a fundacao. A estrutura corresponde ao padrao do Assessor e nao adiciona banco, fila, framework ou integracao fora das fontes fornecidas. As tools que exigem informacao ausente permanecem bloqueadas.

### Implementacao do Redator
- Criados `app/main.py`, `app/config.py`, `app/schemas.py`, `app/auth.py`, `app/graph.py`, `app/prompts.py`, `app/llms.py` e `app/memory.py`.
- Criada a rota `POST /chat`, que nao aceita `usuarioId` no corpo e exige identidade autenticada injetada pelo backend principal.
- Criada a tool `validar_acesso`, com consulta parametrizada a `tb_usuario` para obter `id`, `nivel_acesso` e `cod_cd`.
- Criadas configuracoes para PostgreSQL, MongoDB, Redis, Gemini e Groq; nenhum segredo foi alterado ou registrado.
- Criados `requirements.txt`, `.env.example` e o teste de contrato de autenticacao e schema.

### Validacao do Codigo
- `compileall` executado com sucesso para `app/` e `tests/`.
- Importacao da aplicacao FastAPI validada no ambiente de referencia do Assessor.
- `GET /health` respondeu `200` e `degraded` quando as configuracoes ainda nao estao presentes.
- `POST /chat` sem identidade autenticada respondeu `503`, sem tentar consultar bancos ou modelo.
- Durante os testes, foi encontrada e corrigida a perda do registro do Roteador no estado do LangGraph. A lista de agentes agora acumula corretamente `roteador` e o especialista acionado.

### Validacao das Regras de Negocio
- A identidade nao e aceita do frontend; a API exige a identidade ja autenticada pelo aplicativo.
- A consulta de usuario usa os niveis existentes no banco: `admin`, `gestor` e `operador`.
- Nenhuma regra de alerta, limite, predicao, sobrevivencia, diagnostico tecnico, FAQ ou permissao por camara foi criada.

### Auditoria
- Confirmado que o payload de chat rejeita campos extras, impedindo `usuarioId` livre no corpo.
- Confirmado que consultas ao PostgreSQL usam parametro vinculado para o identificador do usuario.
- Escopo de camaras de operadores permanece bloqueado, pois nao ha relacionamento usuario-camara fornecido.

### Testes
- Executados 8 testes automatizados com sucesso: identidade injetada, ausencia de identidade, rejeicao de `usuarioId` no payload, rota de chat com servicos dublados, bloqueio sem autenticacao, roteamento do grafo, rota invalida e ausencia de configuracao PostgreSQL.
- Os testes usam dublês locais para o usuario autenticado, PostgreSQL, MongoDB e modelos. Eles nao usam credenciais nem alteram bancos.
- TESTE DISPONIVEL: console de perguntas para validar roteamento e respostas sem dados, dependente apenas de `GEMINI_API_KEY` e `GROQ_API_KEY` configuradas.
- TESTE REAL EXECUTADO: a pergunta "Qual e a funcao da IA do Skadi?" foi roteada para `faq`. Como a FAQ oficial ainda nao contem essa resposta aprovada, o agente informou a indisponibilidade em vez de inventar conteudo.
- Correcao aplicada ao console de perguntas: ele agora localiza a pasta raiz do projeto antes de importar `app`, mesmo quando executado diretamente.
- O console aceita `--env-file` para carregar chaves de um arquivo `.env` apenas durante o teste, sem copiar segredos para o projeto Skadi.
- TESTE BLOQUEADO: chamada real ao PostgreSQL, MongoDB, Redis, Gemini e Groq. Faltam configuracoes reais no `.env` e a integracao autenticada do aplicativo.
- TESTE BLOQUEADO: autorizacao de operador por camara. Falta a relacao de responsabilidade usuario-camara no banco.

### Decisao final
Aguardando resposta para a integracao autenticada e para o escopo de camaras por operador. A fundacao foi implementada e permanece fechada para acessos sem essas definicoes.

### Perguntas pendentes ao usuario
- Como o backend principal disponibilizara a identidade autenticada para a API da IA.
- Qual relacao do banco define as camaras permitidas para cada operador.
- Criterios aprovados para predicao, diagnostico tecnico e respostas pendentes da FAQ.

## Etapa: Massa de dados sinteticos para teste integrado

### Solicitacao
Inserir dados de teste nos bancos para testar a IA com perguntas.

### Plano do Arquiteto do Skadi
- Confirmar em leitura o schema PostgreSQL implantado e procurar entidades de teste existentes.
- Usar o segundo schema MongoDB indicado pelo usuario, que exige o campo `risco`.
- Delimitar uma massa sintetica isolada antes de qualquer insercao em producao, sem disparar alertas ou notificacoes para usuarios reais.
- Inserir somente apos confirmar o schema e a conectividade de PostgreSQL, MongoDB e Redis.
- Executar uma implantacao adaptada exclusivamente em `defaultdb`, recusando o procedimento se tabelas principais do Skadi ja existirem. A implantacao exclui `dataload.sql`, `etl-transformacoes.sql` e `roles.sql`.

### Validacao de Arquitetura
ARQUITETURA APROVADA para a implantacao adaptada. A conexao de leitura confirmou que `defaultdb` esta vazio. O deploy original foi rejeitado porque referencia o banco `skadi` e cria usuarios tecnicos de exemplo; o adaptador preserva somente os scripts aprovados necessarios ao schema operacional.

### Implementacao do Redator
- A implantacao inicial do schema foi executada com um procedimento controlado que exigia `defaultdb`, recusava schema nao vazio e aplicava somente schema, funcoes, procedures, triggers, auditoria, catalogo, view DAU e indices. O utilitario temporario foi removido apos a conclusao da implantacao.
- O schema foi implantado com sucesso em `defaultdb`.
- A massa aprovada `dataload.sql` foi aplicada ao PostgreSQL.
- O segundo schema MongoDB foi reaplicado por `banco de dados/codigos/criar_mongodb.py`, preservando as collections e os documentos existentes.
- O Redis local `skadi-redis` foi iniciado e recebeu tres leituras da camara 3 no Stream `skadi:leituras:temperatura`.

### Validacao do Codigo
- A conexao ao PostgreSQL foi restabelecida apos ajustar o banco de destino para `defaultdb`; o schema estava vazio e foi implantado antes da carga.
- Pos-implantacao: 22 tabelas Skadi, 54 registros no catalogo de dados e 7 triggers relevantes confirmados.
- Pos-carga: 100 usuarios, 12 camaras, 12 lotes, 437 leituras, 4 alertas, 4 atendimentos e 56 notificacoes confirmados.
- Teste integrado de monitoramento identificou que `DATABASE_URL` do Assessor sobrepunha a conexao do Skadi durante o console. Corrigida a prioridade para `POSTGRES_URL_SEGUNDO` do Skadi.

### Validacao das Regras de Negocio
- A carga utilizou somente valores, limites, gravidades, atendimentos e fluxos ja presentes no `dataload.sql` fornecido. Nenhuma regra adicional foi criada.

### Auditoria
- O adaptador de schema foi executado somente depois de autorizacao explicita, apenas em `defaultdb` vazio, e excluiu criacao de usuarios tecnicos e carga generica.
- Redis recebeu somente tres mensagens de teste com IDs `skadi-test-redis-001` a `skadi-test-redis-003` e valores ja presentes na massa aprovada para a camara 3.

### Testes
- PostgreSQL: carga e alertas validados em leitura. Foram confirmados alertas `baixa/resolvido`, `atenção/ativo`, `urgente/ativo` e `crítica/reconhecido`.
- MongoDB: quatro collections e um documento de teste em cada collection confirmados apos reaplicacao do segundo schema.
- Redis: tres mensagens de leitura da camara 3 confirmadas no Stream oficial.

### Decisao final
Concluida para a massa sintetica. A IA ainda nao consulta esses dados pelo chat porque as tools operacionais e a integracao autenticada permanecem pendentes.

### Perguntas pendentes ao usuario
Nenhuma para a massa de dados. Para consultas reais pelo chat, permanecem pendentes a integracao autenticada e o escopo usuario-camara para operadores.

## Etapa: Consulta autorizada de monitoramento

### Solicitacao
Avancar para o primeiro fluxo operacional de perguntas: leitura de temperatura da camara 3.

### Plano do Arquiteto do Skadi
- Validar o usuario autenticado no PostgreSQL e limitar a busca ao seu centro de distribuicao (`cod_cd`).
- Localizar o termometro e os limites ja cadastrados para a camara autorizada.
- Ler somente o Stream oficial `skadi:leituras:temperatura` do Redis e devolver a leitura mais recente daquele termometro.
- Manter operador sem acesso ate existir no banco o vinculo aprovado usuario-camara. Nao incluir predicao, diagnostico ou recomendacao.

### Validacao de Arquitetura
ARQUITETURA APROVADA. O fluxo usa apenas campos e fontes existentes: `tb_usuario`, `tb_camara_frigorifica` e o Stream Redis definido no projeto. O identificador de usuario vem do estado autenticado do backend; o parametro do console e exclusivo para teste local.

### Implementacao do Redator
- Criada `app/tools/monitoramento.py`, com validacao usuario -> CD -> camara e consulta parametrizada ao PostgreSQL.
- Integrada ao agente de monitoramento a tool `consultar_leitura_recente`, vinculada ao usuario autenticado no estado do fluxo.
- Ajustada a prioridade da configuracao PostgreSQL para a variavel especifica `POSTGRES_URL_SEGUNDO`, impedindo que o `.env` do Assessor substitua a base do Skadi durante testes.
- O console agora aceita `--pergunta` para um teste unico nao interativo.

### Validacao do Codigo
- A consulta integrada direta para usuario de teste `2` e camara `3` retornou o termometro `3`, temperatura `4.50`, data `2026-08-31T08:00:00-03:00` e os limites cadastrados `2.00` e `6.00`.
- Executados 9 testes automatizados com sucesso. O teste adicional confirma que um operador e recusado antes de qualquer acesso a camara, enquanto nao houver associacao aprovada.
- A chamada completa ao provedor de IA nao foi concluida dentro da janela do executor automatizado; o console de pergunta unica foi disponibilizado para a validacao local completa.

### Validacao das Regras de Negocio
- A resposta de monitoramento nao cria leitura, limite, alerta ou recomendacao. Ela apenas expoe a leitura existente e os limites cadastrados, dentro do CD permitido.
- Predicoes continuam indisponiveis por falta de criterios aprovados. Diagnosticos continuam apresentados somente como hipotese quando a base tecnica for fornecida.

### Decisao final
Implementacao pronta para validacao local da pergunta de monitoramento. A proxima expansao segura depende do teste completo do provedor ou de uma nova capacidade aprovada.

## Etapa: Autenticacao simulada para desenvolvimento

### Solicitacao
Permitir testar a API pelo Uvicorn antes da integracao com o login real.

### Implementacao do Redator
- Adicionado middleware de autenticacao simulada em `app/main.py`.
- Durante o bypass atual, o middleware injeta o usuario de teste `2`. O corpo JSON recebe somente `token` e `mensagem`.
- A autenticacao real permanece como tarefa pendente antes de producao.

### Validacao das Regras de Negocio
- A simulacao nao acrescenta permissao nem ignora as verificacoes de usuario, CD ou camara. Ela apenas substitui temporariamente a origem da identidade autenticada.
- O modo simulado deve ser desativado antes de qualquer implantacao de producao.
- Executados 11 testes automatizados, incluindo o envio do header mock ao aplicativo FastAPI principal.

## Etapa: Contrato temporario para integracao mobile

### Solicitacao
Preparar a IA para consumo pelo aplicativo mobile e manter a validacao de token temporariamente bypassada para testes.

### Implementacao do Redator
- Definido `POST /api/v1/ia/chat` como endpoint oficial do aplicativo mobile. O endpoint legado `/chat` foi mantido para nao quebrar testes anteriores, mas nao aparece na documentacao.
- Adicionado `GET /api/v1/ia/capacidades`, para o aplicativo descobrir recursos efetivamente entregues sem presumir predicao, diagnostico ou FAQ.
- A verificacao de token foi deixada como `TODO(autenticacao-mobile)` comentado. Enquanto ela nao for integrada, o middleware injeta o usuario de teste `2`.
- Ampliada a validacao de niveis conhecidos conforme o banco: `super_admin`, `admin`, `gestor` e `operador`.

### Validacao das Regras de Negocio
- A existencia e o nivel do usuario continuam sendo validados no PostgreSQL antes do chat executar.
- Para a leitura de temperatura, somente `admin` e `gestor` com `cod_cd` podem acessar cameras do mesmo CD. A consulta filtra a camera pelo CD no SQL.
- `operador` permanece sem leitura de camera por ausencia do relacionamento aprovado operador-camara.
- `super_admin` tambem fica sem leitura de camera porque nao possui `cod_cd` e nao existe regra aprovada que lhe conceda escopo global.
- O bypass de identidade e estritamente temporario; ele nao deve ser usado em producao.
- Para o aplicativo mobile, negacao de permissao responde `403`; indisponibilidade de configuracao ou servico responde `503`.
- A rota de chat grava no MongoDB os valores ja aprovados pelos validadores: mensagens com tipo `texto`, execucao `orquestrador` e status `executando`.
- Os niveis de acesso seguem o padrao do banco em maiusculas: `SUPER_ADMIN`, `ADMIN`, `GESTOR` e `OPERADOR`.
- Monitoramento: `SUPER_ADMIN` consulta qualquer camera; `ADMIN`, `GESTOR` e `OPERADOR` consultam cameras do proprio CD. Alertas de operador permanecem pendentes da tool de alertas.

## Etapa: Persona Trimmy

### Implementacao do Redator
- Adicionada `PERSONA_SISTEMA` em `app/prompts.py`, definindo a Trimmy como assistente objetiva e confiavel de apoio ao monitoramento de camaras frigorificas.
- A persona e compartilhada pelos prompts de roteador, orquestrador, monitoramento, predicao, diagnostico, relatorios e FAQ.
- O roteador ja existente continua em `_rotear`, em `app/graph.py`, selecionando uma unica rota a partir de `ROTEADOR_PROMPT`.
- Nao foi incluida instrucao de busca de memoria, pois nao ha tool de recuperacao de historico integrada ao grafo.

## Etapa: Orquestrador real e remocao do assistente

### Implementacao do Redator
- Removido o agente generico `assistente`.
- O roteador nao responde ao usuario: ele encaminha para um especialista ou diretamente para o orquestrador quando a mensagem for saudacao, conversa geral ou estiver fora do Skadi.
- Especialistas agora registram respostas internas junto ao nome do agente.
- O orquestrador recebe `pergunta_original` e `respostas_agentes`, sem tools, e produz a unica resposta final entregue ao aplicativo mobile.
