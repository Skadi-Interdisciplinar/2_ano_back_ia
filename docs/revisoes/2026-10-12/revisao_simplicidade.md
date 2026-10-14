# Revisão de simplicidade e estrutura — Trimmy

Data: 2026-10-12. Revisão do checkout local, sem alterações de implementação.
Contexto confirmado pelo usuário: API somente local; bancos somente com dados de teste.
Assessor usado como referência estrutural, sem copiar regras de negócio.

## Conclusão

A arquitetura geral segue o Assessor: FastAPI, schemas, grafo, prompts, clientes,
memória e tools por domínio. Há seis tools reais e nenhuma duplicação funcional
que justifique unificá-las agora. Contudo, o projeto não está inteiramente enxuto:
há código sem uso, configuração de pacote divergente e problemas de correção
que os testes atuais não detectam.

## Prioridades encontradas

| ID | Prioridade | Evidência | Ação recomendada, ainda não executada |
| --- | --- | --- | --- |
| SIM-01 | Primeiro, correção | `app/diagnostico.py:153–172`: citação literal e flags do modelo viram requisito satisfeito | Fortalecer vínculo entre observação e requisito; acrescentar teste com trecho sem observação. Não simplificar removendo validação. |
| SIM-02 | Primeiro, correção pequena | `app/schemas.py:45`: regex de itálico remove asteriscos de multiplicação espaçada | Restringir limpeza à formatação identificável; preservar conteúdo e testar cálculos com espaços. |
| SIM-03 | Limpeza segura | `app/main.py:30–41` escreve identidade em request.state; `app/auth.py:13–20` ignora esse estado | Manter o mock em uma única origem. O middleware atual não alimenta a autenticação das rotas. |
| SIM-04 | Limpeza segura | `app/config.py:26,32`, `app/memory.py:135`, `app/routes/chat.py:11` | Remover funções/configuração/logger sem uso, ou integrar se realmente requeridos. Não alegar tracing: registrar_execucao_agente só é chamado em teste. |
| SIM-05 | Instalação/CI | `pyproject.toml:16–25,37–45,52–55`, requirements.txt, pytest.ini | Unificar dependências e configuração pytest; empacotar app e sua base JSON. O wheel declarado inclui apenas o stub src/agente_ia. |
| SIM-06 | Recursos | `app/tools/access.py:20` usa conexão como contexto sem fechamento explícito | Padronizar closing como no monitoramento. O contexto psycopg2 trata a transação, não fecha a conexão; não foi comprovado vazamento permanente em produção. |
| SIM-07 | Operações redundantes | `app/memory.py:26–31`, `app/vectorstore.py:36–50` | Garantir índices/coleção uma vez após sucesso, não a cada operação. O Assessor já usa flags de inicialização para isso. |
| SIM-08 | Crescimento de sessão | `app/memory.py:41–60,79,116` | Trazer somente o contexto necessário; decidir armazenamento sem array ilimitado. Não usar slice de gravação que descarte histórico sem aprovação. |
| SIM-09 | Concorrência/consistência | `app/graph.py:198–230`, `app/memory.py:72–81,93–100` | Preservar o ID interno da sessão do turno e gravar pergunta/resposta juntas. Hoje encerramento entre leitura e salvamento pode levar o turno a outra sessão; é hipótese de sequência, não reprodução em banco real. |
| SIM-10 | Diagnóstico sem RAG fora da faixa | `app/diagnostico.py:139–140`, `app/tools/diagnostico.py:126` | Distinguir consulta não executada de consulta sem resultado. Não adicionar busca obrigatória dentro da faixa, contrariando a decisão aprovada. |
| SIM-11 | Documentação | TRIMMY.md e docs/ACOMPANHAMENTO_IMPLEMENTACAO_SKADI.md | Separar arquitetura atual de histórico/proposta. TRIMMY descreve assistente removido, orquestrador roteando e criação automática de ocorrências, diferentes do código. |
| SIM-12 | Disponibilidade | get_conn, cliente Redis, obter_modelos e agente.invoke | Timeouts e orçamento de execuções não foram explicitamente definidos pelo projeto. Decidir valores antes de produção; não inventar limites nesta revisão. |

### Provas offline executadas

1. Evidência simulada: temperatura 8, limites 2 a 6, horário válido. Fonte:
   “Quero saber a causa do problema.” O modelo simulado marcou
   `vedacao_danificada`, vínculo e atualidade verdadeiros. O backend retornou
   uma hipótese DIAG-TEC-001, embora o trecho não descreva vedação.
   A fonte aprovada protege o texto técnico, mas não comprova a interpretação do relato.
2. `ChatResponse(resposta="2 * 3 * 4").resposta` retornou `"2 3 4"`.
   A prova demonstra alteração de conteúdo, não apenas formatação.
3. Validação de acesso com conexão/cursor simulados: `conexao.close` não foi
   chamado. A ausência de fechamento explícito também está visível no código.

Nenhuma prova acessou bancos ou chamou um LLM.

## Tools: manter a divisão atual

| Domínio | Tool | Por que não é redundante |
| --- | --- | --- |
| Monitoramento | consultar_temperaturas | Já cobre uma ou todas as câmaras na mesma implementação. |
| Monitoramento | listar_camaras_responsaveis | Retorna cadastro/limites sem depender do Redis; disponibilidade diferente. |
| Monitoramento | consultar_alertas_atuais_do_usuario | Consulta alertas com filtros próprios de status, reconhecimento e nível. |
| Diagnóstico | consultar_evidencias_diagnostico | Uma câmara/ocorrência, snapshots e justificativas, reutilizando consultas de monitoramento. |
| Diagnóstico | buscar_regras_diagnostico | Fonte técnica aprovada no Qdrant, diferente de dados operacionais. |
| Memória | buscar_historico | Resumos do usuário; não consulta regras nem temperaturas. |

validar_acesso, contexto e helpers SQL não são tools registradas do LLM.
O orquestrador não tem tools. O roteador usa somente memória e seu schema de saída.
Predição, relatórios e FAQ têm prompts/rotas, mas não tools específicas implementadas;
não devem ser apresentados como funcionalidades completas.

## Correspondência com o Assessor

| Parte | Resultado |
| --- | --- |
| app/main.py, routes/chat.py, schemas.py | Mesmo padrão de contrato HTTP e rota pequena. O corpo token/mensagem é decisão do Skadi. |
| tools por domínio, @tool, args_schema, TOOLS, get_conn | Alinhados; nenhuma regra financeira reutilizada. |
| Memória Mongo e resumos Qdrant | Alinhados conceitualmente; uma sessão ativa por usuário é adaptação aprovada. |
| Identidade interna | Trimmy usa ContextVar; Assessor usa RunnableConfig. Não copiar user_id escolhido pelo cliente para enfraquecer acesso. |
| Clientes e embeddings | Reutilização e dimensão compartilhadas; coleções exclusivas mantidas. |
| Grafo | Ambos têm roteamento/especialistas/orquestração. Trimmy tem validação estruturada, apropriada à demanda. |
| Diagnóstico | Não existe equivalente de refrigeração no Assessor; a validação adicional não é redundância por não existir nele. |
| Inicialização | Assessor mantém agentes criados e índices inicializados. Trimmy recompila agentes internos por chamada, embora o grafo externo esteja compilado uma vez. Cache de agentes é melhoria opcional, não prioridade para testes locais. |
| Logs | Assessor integra observabilidade ao fluxo; Trimmy possui função de registro desconectada. Não declarar cobertura equivalente. |

## O que pode ser simplificado sem perder proteção

- Mock de identidade em um único lugar.
- Funções de configuração sem consumidores e logger de rota sem chamadas.
- Entradas monitoramento/diagnostico em PROMPTS_POR_ROTA, pois esses ramos
  retornam antes de usar o mapa genérico (`app/graph.py:31–37,94–125`).
- Retorno vazio em carregar_contexto_conversa após iniciar_sessao: no runtime,
  iniciar_sessao já lança erro quando não há documento; um teste força None artificialmente.
- Repetição de criação/conferência de índices.
- Configurações duplicadas e stub de pacote, depois de ajustar o build.

Não apagar automaticamente registrar_execucao_agente: escolher entre removê-la como
código morto ou integrar observabilidade mínima. Não excluir documentos históricos
sem identificá-los como históricos.

## O que não simplificar por redução de linhas

- ContextVar de identidade e contexto separado das evidências de diagnóstico.
- Separação entre PropostaDiagnostico não confiável e AnaliseDiagnostico validada.
- SQL parametrizado e checagem de escopo dentro das tools.
- Revalidação do alerta antes de ler justificativas: pode ser defesa contra alteração
  de estado entre operações, não duplicação automaticamente removível.
- Fonte local aprovada, comparação do payload recuperado e índice técnico separado.
- Indexador administrativo fora do LLM.
- Fallback do framework e correção limitada de tool_use_failed.

Importar helpers privados de monitoramento pelo diagnóstico é acoplamento leve:
pode-se renomear sua interface interna compartilhada. Não precisa criar uma camada
de repositories/services ou hierarquia de classes para resolver isso.
A serialização JSON do diagnóstico seguida de leitura pelo orquestrador é evitável,
mas preserva o formato uniforme atual; baixa prioridade, não motivo para refazer o grafo.

## Inventário e limites da revisão

- Inventariados 38 arquivos Python: 19 em app, 17 em tests (incluindo preparação
  e integração), um script administrativo e um stub src.
- Código de runtime, scripts e configuração inspecionados; testes inventariados por
  AST, casos de acesso, memória, roteamento, regras, falhas e apresentação examinados,
  e suíte inteira executada.
- JSON da base validado pelo carregador e testes das oito regras; não houve nova
  aprovação técnica nem nova pesquisa de causas nesta revisão.
- CI, manifests, .gitignore, template de PR e documentação considerados.
- PDFs de output identificados como materiais de apoio, não revalidados tecnicamente;
  .env real, histórico Git completo, segurança dos provedores e infraestrutura fora
  do escopo. Não foi publicado conteúdo de segredos.
- Relatórios antigos de 2026-10-11 foram preservados; esta revisão não trata os
  controles atuais como apenas planejados.

## Matriz por arquivo de runtime

| Arquivo | Resultado |
| --- | --- |
| app/auth.py | Mock intencional; centralizar e manter impedimento de produção. |
| app/config.py | Leitura de env coerente; duas funções sem consumidores. |
| app/main.py | Handlers seguros e centralizados; middleware de mock sem leitor. |
| app/routes/chat.py | Pequena e adequada; logger sem uso. |
| app/schemas.py | Contrato estrito; corrigir limpeza de itálico que altera cálculo. |
| app/graph.py | Estrutura adequada; sobras no mapa, agentes internos recriados e sessão do turno não preservada. |
| app/prompts.py | Persona e domínios presentes; prompt não garante ausência de invenção. |
| app/llms.py | Cache e fallback pertinentes ao erro reproduzido; middleware não é uma tool. |
| app/erros.py | Duas classes pequenas; manter distinção de falhas. |
| app/memory.py | Índice único parcial bom; operações repetidas, array crescente e registro sem uso. |
| app/vectorstore.py | Filtro por usuário bom; criação/conferência recorrente no caminho de leitura. |
| app/regras_diagnostico.py | Fonte local e aprovação coerentes; manter controles. RAG com limit=len(regras) considera todas as oito, não um corte de pertinência. |
| app/diagnostico.py | Responsabilidade maior justificada; falha de correspondência semântica confirmada. |
| app/tools/access.py | SQL e nível de acesso coerentes; padronizar fechamento explícito. |
| app/tools/contexto.py | Necessário para identidade por execução. |
| app/tools/db.py | Adaptador único e pequeno; não adicionar pool por padrão para uso local. |
| app/tools/monitoramento.py | Três tools distintas e consultas compartilhadas; varredura de stream pode ser cara se um sensor não tiver evento. |
| app/tools/diagnostico.py | Duas tools pertinentes; snapshots e vínculos por IDs mantidos. |
| app/tools/memoria.py | Uma tool pertinente; schema poderia rejeitar extras como os demais. |
| scripts/indexar_regras_diagnostico.py | Operação administrativa sanitizada; não transformar em tool. |
| src/agente_ia/__init__.py | Stub sem implementação; alvo atual do build não representa a API. |

## Testes e ordem proposta

Ruff aprovado; 258 testes passaram, quatro integrações opt-in puladas e dois
avisos de dependências. Isso não comprova ausência de todos os cenários nem
qualidade semântica do LLM. Python do ambiente de validação é 3.14; CI usa 3.11,
não executado separadamente nesta revisão.

Ordem sugerida: corrigir SIM-01 e SIM-02; padronizar conexão; limpar mock/código
morto; alinhar pacote/configuração; reduzir operações de memória/índices; definir
consistência de sessão e armazenamento. Mudanças de schema, políticas de retenção,
timeouts e autenticação real dependem de decisões explícitas. Nenhuma alteração
de código, banco, dependência, commit ou push foi feita por esta revisão.

