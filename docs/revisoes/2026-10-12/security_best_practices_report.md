# Revisão de boas práticas de segurança — Trimmy

Data: 2026-10-12. Contexto confirmado: somente localhost e dados de teste.
Método: security-best-practices, revisão estática, provas offline e testes.
Esta revisão não altera código e não substitui auditoria de infraestrutura.
Os relatórios de 2026-10-11 continuam como histórico; este documento avalia a implementação atual.

## Resumo executivo

SQL parametrizado, escopo por CD, identidade interna, snapshots de evidências,
fonte aprovada local e erros sanitizados são controles reais. As seis tools têm
responsabilidades diferentes. O principal problema confirmado é integridade da
interpretação de relatos: uma citação verdadeira pode ser rotulada pelo modelo
como observação que ela não contém. Há riscos de disponibilidade pela memória
crescente e trabalho sem orçamento explícito. O mock conhecido é aceitável para
o teste local autorizado, mas impede publicação. Não foi encontrado nesta revisão
um caminho demonstrado de execução arbitrária ou acesso entre CDs via SQL.

## Achados de segurança e confiabilidade

### BP-101 — Correspondência semântica do relato insuficientemente validada

- Severidade atual: média, com dados de teste. Prioridade funcional: alta antes de uso real.
- Referência: FASTAPI-VALID-001 / integridade de entrada não confiável.
- Local: `app/diagnostico.py:23–30,151–181`, validar_analise.
- Evidência: `relato.trecho in fonte["texto"]` confirma citação; requisito e flags
  de vínculo/atualidade continuam atributos escolhidos pelo modelo.
- Prova: “Quero saber a causa do problema.” rotulado vedacao_danificada produziu
  DIAG-TEC-001 com leitura acima do máximo, sem qualquer relato sobre vedação.
- Impacto: hipótese aprovada aplicada ao caso sem a evidência exigida; texto técnico
  não é livre, mas sua aplicabilidade pode ser falsa.
- Mitigação existente: regras locais aprovadas, enum de requisitos, comparação
  numérica finita, proveniência de justificativa e bloqueios conservadores de negação.
- Recomendação: rejeitar observação que não esteja expressa no trecho; manter
  vínculo com câmara/ocorrência e pedir esclarecimento quando incerto. Acrescentar
  teste de regressão com trecho sem observação. Não tratar booleanos do LLM como prova.
- Limite: nenhum teste confirma que um atacante fará o LLM escolher esse rótulo;
  a prova confirma que o backend aceita tal proposta quando recebida.

### BP-102 — Armazenamento de conversa e resumo sem crescimento controlado

- Severidade: média de disponibilidade; probabilidade baixa no teste local pequeno.
- Referência: FASTAPI-LIMITS-001.
- Local: `app/memory.py:41–60,79,103–116`.
- Evidência: array mensagens recebe push sem limite; iniciar_sessao retorna o
  documento inteiro; as últimas 20 são escolhidas somente em Python; o resumo
  recebe toda a sessão.
- Impacto: maior transferência/custo; documentos muito longos deixam de aceitar
  gravação. O limite BSON é 16 MiB, conforme [MongoDB](https://www.mongodb.com/docs/manual/reference/limits/#bson-document-size).
- Recomendação: projeção do contexto necessário e armazenamento que preserve
  histórico sem array ilimitado. Retenção, descarte ou novo schema exigem aprovação.
- Não alegar que o problema já ocorreu ou reduzir histórico silenciosamente.

### BP-103 — Ausência de orçamento explícito para operações caras

- Severidade atual: baixa; média se exposto ou usado simultaneamente.
- Referência: FASTAPI-LIMITS-001.
- Local: `app/tools/db.py:17`, `app/tools/monitoramento.py:24,98–119`,
  `app/llms.py:67–78`, `app/graph.py:79,119,130`.
- Evidência: o projeto não configura explicitamente timeout de conexão/LLM e
  recursion_limit de agentes; busca Redis pode percorrer o stream até esgotá-lo.
  SDKs podem ter defaults: não afirmar que todos esperam indefinidamente.
- Mitigação: corpo de chat limitado a 10.000 caracteres; correção de tool_use_failed
  limitada a uma nova geração; testes reais são opt-in.
- Recomendação: definir parâmetros técnicos após medir/validar demanda. Não criar
  limites de sensores ou de negócio nem instalar um sistema de rate limiting complexo
  para a API local por padrão.

### BP-104 — Mock sem autenticação real e identidade duplicada

- Severidade atual: baixa, configuração de teste explicitamente autorizada.
  Alta se a API for exposta ou usar dados reais.
- Referência: FASTAPI-AUTH-001 / FASTAPI-AUTHZ-001.
- Local: `app/auth.py:13–20`, `app/main.py:30–41`, `app/config.py:26–29`.
- Evidência: token é descartado e user 2 é retornado; middleware também escreve
  user 2 em estado que a rota não lê; flag de mock existe mas não governa esse código.
- Impacto: todos os clientes alcançáveis compartilham identidade e memória do user 2.
- Recomendação atual: centralizar mock e tornar a limitação explícita. Antes de
  exposição, integrar identidade real e bloquear o mock. Não copiar user_id do
  Assessor como dado confiável escolhido pelo cliente.
- Falso positivo evitado: não tratar o bypass autorizado como ataque remoto atual;
  não recomendar TLS/HSTS apenas porque localhost usa HTTP.

### BP-105 — Sessão do turno pode mudar entre leitura e gravação

- Severidade: baixa de integridade/ disponibilidade no uso atual; média com concorrência.
- Local: `app/graph.py:198–230`, `app/memory.py:72–81,93–100`.
- Evidência: o turno lê sessão e depois chama salvar_mensagem duas vezes; cada
  salvamento obtém novamente a sessão ativa.
- Sequência possível: encerramento conclui durante o LLM; o salvamento abre nova
  sessão. Outra sequência pode separar pergunta e resposta entre sessões.
- Mitigação: índice único parcial e bloqueio do status encerrando.
- Recomendação: manter sessão interna do turno, gravar interação atomicamente e
  decidir conflito de encerramento, sem exigir session_id novo no mobile.
- Não houve reprodução concorrente em Mongo real nesta revisão.

### BP-106 — Empacotamento/dependências não representam o runtime

- Severidade: baixa de manutenção; disponibilidade potencialmente média em nova instalação.
- Referência: FASTAPI-SUPPLY-001.
- Local: `pyproject.toml:16–25,37–45`, requirements.txt, .github/workflows/build.yml.
- Evidência: wheel/sdist incluem stub src/agente_ia, não app nem base JSON; a
  lista principal omite SDKs de Gemini/Groq, PostgreSQL/Redis/Mongo usados no runtime.
  CI instala duas fontes de dependências. pytest.ini sobrepõe configuração distinta.
- Recomendação: alinhar uma fonte de dependências, versão mínima das APIs usadas,
  alvo de build e teste de importação do artefato. Não afirmar que existe CVE sem SCA.
- Não foi construído/importado wheel isolado: constatação da configuração declarada.

### BP-107 — Limpeza de Markdown pode alterar conteúdo

- Severidade de segurança: baixa; bug de integridade confirmado.
- Referência: FASTAPI-RESP-001.
- Local: `app/schemas.py:42–46`.
- Prova: 2 * 3 * 4 vira 2 3 4.
- Recomendação: restringir limpeza e testar preservação de operadores espaçados.
  Texto simples não é validação técnica de uma resposta.

### BP-108 — Fechamento explícito inconsistente

- Severidade: baixa de confiabilidade.
- Local: `app/tools/access.py:20`; demais consultas usam closing.
- Prova offline: close explícito não chamado no caminho de autorização.
- [Psycopg](https://www.psycopg.org/docs/usage.html#with-statement) documenta
  que o contexto de conexão não a fecha. Padronizar closing evita depender do descarte.
- Não alegar vazamento permanente medido: destruição do objeto pode encerrar a conexão.

## Controles aprovados que devem permanecer

- SQL com valores em parâmetros, mesmo quando cláusulas fixas são montadas.
- SUPER_ADMIN global e demais por CD; filtros de reconhecimento/OPERADOR em alertas.
- Identidade fora dos argumentos do modelo; ContextVar restaurado em finally.
- Resumos Qdrant filtrados por usuário e defesa adicional no payload.
- Coleção técnica exclusiva, fonte local aprovada e payload/hash conferidos.
- Indexação administrativa fora do LLM; ferramentas operacionais sem escrita.
- Schema estrito de rota e análise; erros públicos sem stack trace ou credenciais.
- Fallback nativo e correção limitada sem repetir execução de tool.
- Não adotar SQL arbitrário, eval, agentes de reparo ou “guardrail” que confie somente no LLM.

## Verificações e limites

Ruff aprovado, 258 testes aprovados, quatro integrações opt-in puladas.
Provas offline expuseram lacunas que essa suíte ainda aceita. Não foram chamados
provedores, executados testes reais ou feitas alterações nos bancos nesta revisão.
Valores de segredos não foram exibidos e o .env não foi aberto para auditoria;
.env é ignorado e não consta nos arquivos
rastreados consultados. Isso não é uma busca completa por segredos no histórico Git.
Não foi auditado o conteúdo dos PDFs de apoio nem a segurança dos serviços externos.
Nenhum código foi alterado; somente relatórios novos, preservando os anteriores.

