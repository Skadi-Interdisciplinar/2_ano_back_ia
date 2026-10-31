# Revisão do planejamento de diagnóstico da Trimmy

Data: 2026-10-11. Método: security-best-practices e comparação do código da Trimmy com o Assessor. Revisão estática; nenhuma conexão real ou pergunta ao LLM foi executada.

## Resumo executivo

O plano é adequado como evolução do domínio de diagnóstico, com duas tools e reutilização da infraestrutura existente. A implementação ainda não existe. A segurança dependerá de controles executáveis de autorização, referência às evidências e aprovação das regras, não apenas de prompts. A API está somente local, conforme confirmado pelo usuário; a autenticação simulada permanece uma limitação explícita e impede considerar a solução pronta para produção.

## Achados prioritários

### BP-01 — Autenticação simulada: impedimento para publicação

- Severidade: alta se exposta a terceiros; no uso local confirmado, limitação conhecida dos testes.
- Referência: FASTAPI-AUTH-001 / FASTAPI-AUTHZ-001.
- Evidência: `app/auth.py:13`, `obter_usuario_autenticado`, descarta o token e retorna `AuthenticatedUser(usuario_id=2)`; `app/main.py:14` também injeta usuário 2.
- Impacto: quem alcançar a API opera como o usuário 2, inclusive sobre conversa e encerramento de sessão. ContextVar preserva identidade interna, mas não autentica sua origem.
- Recomendação: manter o diagnóstico em testes locais; integrar autenticação real antes de publicação. Não alterar o contrato token/mensagem nesta entrega. A flag de mock em `app/config.py` não é aplicada por essa função atualmente.
- Nota: não é necessário trocar para JWT ou outro mecanismo sem conhecer a integração do aplicativo. Não foi confirmado acesso externo.

### BP-02 — Reutilização incompleta da autorização de alertas

- Severidade: alta se a implementação copiar somente parte dos filtros; lacuna do plano, não falha de uma tool de diagnóstico existente.
- Referência: FASTAPI-AUTHZ-001 / FASTAPI-INJECT-001.
- Evidência: `app/tools/monitoramento.py:161`, `consultar_alertas_atuais`: ativos ou reconhecidos pelo usuário; `:180` aplica CD; `:183` exige também `a.nivel_atual = operador` para OPERADOR.
- Impacto: uma consulta nova que só filtre câmara, CD e status pode expor alertas e justificativas que o monitoramento não permite.
- Ajuste do plano: uma consulta interna de alertas permitidos deve fornecer associação por IDs e filtros opcionais de câmara/alerta. A tool pública atual apenas transforma o resultado no formato existente. Justificativas devem ser vinculadas ao alerta autorizado; possuir ID não concede acesso.
- Testes: operador diante de alerta de outro nível; alerta reconhecido por outro usuário; alerta de outra câmara; tentativa de acessar outro CD.

### BP-03 — Estrutura válida não garante interpretação correta do relato

- Severidade: média no contexto local; pode aumentar com uso operacional.
- Evidência: `app/graph.py:90` recebe texto do especialista; `app/graph.py:134` envia a saída ao orquestrador LLM. O plano propõe estrutura Pydantic e trechos de origem, ainda não implementados.
- Impacto: o modelo pode transformar “não há gelo” em presença de gelo, misturar ocorrências ou citar um trecho verdadeiro para sustentar uma hipótese incompatível.
- Ajuste do plano: um validador do diagnóstico verifica valores finitos, cenário da regra, evidências da execução e referência exata ao relato. As falas anteriores do assistente não são relatos do usuário. Negação, contradição, atualidade ou associação incertas exigem esclarecimento; não basta constatar que o trecho existe.
- Risco residual: interpretação semântica feita por LLM não é certificada pelo schema. Não prometer que checagem de citação elimina esse risco. Não acrescentar um segundo agente verificador como garantia artificial.
- Saída: hipóteses, recomendações e fontes vêm das regras aprovadas; apresentação determinística do diagnóstico no orquestrador evita novas conclusões técnicas.

### BP-04 — RAG deve recuperar regras, não conceder aprovação

- Severidade: média, condicionada a conteúdo incorreto ou acesso de escrita ao índice.
- Evidência: `app/vectorstore.py:7` separa a memória em `trimmy_memoria_resumos`; `:12`, `:21` e `:31` já disponibilizam cliente, modelo de embeddings e geração de vetor. A coleção técnica ainda não está implementada.
- Impacto: misturar memória e regras, confiar no status de um payload sem conferir a fonte aprovada, ou permitir indexação pelo agente pode ativar conteúdo não aprovado.
- Ajuste do plano: fonte estruturada única no repositório; coleção técnica exclusiva; recuperar apenas IDs/versões cujo conteúdo corresponda à base aprovada. Indexador administrativo sem registro em TOOLS. Não fazer consultas HTTP às URLs das fontes durante o chat.
- Nota: separação de coleção não substitui controle das credenciais do Qdrant. Não foi auditada a configuração de permissões do cluster.

### BP-05 — Disponibilidade e exposição de erros

- Severidade: média; sem evidência de exploração local.
- Evidência: `app/llms.py:9` não configura timeout/retries explícitos; `app/tools/monitoramento.py:95` percorre o stream até concluir a busca; `app/memory.py:78` acumula mensagens na sessão. `app/routes/chat.py:23` atualmente propaga falhas sem os mapeamentos propostos.
- Impacto: chamadas lentas, leituras extensas e mensagens acumuladas podem atrasar ou interromper o atendimento. Isso não deve parecer ausência de dados nem diagnóstico mecânico.
- Ajuste do plano: handlers centrais para erros conhecidos, com mensagens públicas genéricas; preservar a diferença entre indisponibilidade e dados ausentes. Não mapear todo RuntimeError para 503: encerramento de sessão também usa esse tipo.
- Fora desta entrega: valores de timeout, quotas e retenção precisam de decisão própria; não inventar limites operacionais. Não afirmar thread presa indefinidamente, pois defaults das bibliotecas não foram verificados nesta revisão.

## Estrutura mínima recomendada e ausência de redundâncias

| Responsabilidade | Decisão |
| --- | --- |
| Consultar dados operacionais | Uma tool `consultar_evidencias_diagnostico` reúne cadastro, leitura, alertas e justificativas; não criar tools separadas para cada SELECT. |
| Recuperar conhecimento aprovado | Uma tool `buscar_regras_diagnostico`; não unificar com evidências, pois possuem argumentos, origem e finalidade distintos. |
| Autorização e consultas compartilhadas | Reutilizar `validar_acesso`, seleção de câmaras, leitura Redis e consulta interna de alertas; não criar outro RBAC ou clonar SQL. |
| Aprovação e indexação | Um arquivo estruturado das seis regras e um comando administrativo; não criar serviço, endpoint ou agente de aprovação. |
| Validar análise | Um módulo de domínio com modelos Pydantic e um ponto de validação; não construir motor genérico de regras ou cadeia de wrappers. |
| Apresentar análise | Um formatador chamado pelo orquestrador para diagnóstico; demais domínios preservados. |
| Recursos existentes | Reutilizar get_conn, contexto de usuário, clientes, embeddings e persistência de conversas; não adicionar dependência ou banco sem necessidade demonstrada. |

Uma função interna seguida de um wrapper @tool não é redundante quando a função recebe a identidade do backend e o wrapper expõe só os argumentos permitidos ao modelo. Validar acesso no fluxo e em tools diretamente invocáveis também é defesa necessária, não uma razão para retirar a checagem da tool. Já funções que só renomeiam outras, consultas SQL copiadas e validadores idênticos devem ser evitados.

## Compatibilidade com o Assessor

Comparação direta realizada em seu checkout de referência:

- `Assessor/app/graph.py:29`: roteador/especialistas criados com create_agent e listas de tools por domínio; o plano acompanha esse desenho.
- `Assessor/app/tools/agenda.py:37`: schema Pydantic e @tool; `Assessor/app/tools/db.py:8`: get_conn centralizado.
- `Assessor/app/tools/memoria.py:10`: identidade passada internamente por RunnableConfig. A Trimmy já usa ContextVar; não adicionar um segundo mecanismo só para copiar o Assessor.
- `Assessor/app/graph.py:201`: orquestrador chama LLM. A apresentação fixa de diagnóstico da Trimmy é uma diferença intencional aprovada, não equivalência literal.

Não copiar regras financeiras, defaults, permissões ou infraestrutura de guardrails sem necessidade específica da Trimmy.

## Ajustes documentais e critérios de aceite

A base em `docs/base_tecnica_diagnostico_em_revisao.md:7` ainda está marcada EM_REVISAO e `:29` exclui OPERADOR. O usuário aprovou a base e depois autorizou os quatro perfis com acesso igual ao monitoramento. Na implementação, atualizar esses registros sem inventar aprovador no banco. Esta revisão não ativa regras nem altera aquela base.

Antes de concluir a entrega: conferir schema real; testar todos os filtros do monitoramento; avaliar cada regra com e sem evidências; testar negações e mistura de ocorrências; impedir atualização do índice pelo LLM; validar erro de infraestrutura e saída inválida; verificar resposta sem IDs e sem conclusões acrescentadas. Testes unitários simples não substituem avaliação de perguntas com o modelo e integração real separada.

## Conclusão

Plano aprovado tecnicamente com os ajustes BP-02 a BP-04 incorporados à implementação. Adequado ao projeto, com duas tools e sem novas camadas genéricas. Autenticação mock e controles de disponibilidade permanecem limitações conhecidas, não certificação de segurança de produção. Nenhum código de aplicação foi alterado nesta revisão.
