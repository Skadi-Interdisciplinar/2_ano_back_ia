# Revisão de segurança da Trimmy

## Resumo executivo

Revisão do código atual, comparado à estrutura do Assessor. Contexto confirmado
pelo usuário: API somente local e bancos de teste. Foram preservados mock de
autenticação, contratos e regras aprovadas. Não foi encontrada escrita operacional
pelas tools. A revisão e os testes não certificam produção nem eliminam falhas
semânticas dos modelos. A avaliação real revelou também limites dos provedores.

## Alta se publicada: BP-01 — Identidade mockada

- Referência: FASTAPI-AUTH-001 e FASTAPI-AUTHZ-001.
- Local: `app/auth.py:15`, `obter_usuario_autenticado`; `app/config.py`,
  `TRIMMY_USUARIO_TESTE_ID`.
- Evidência: token descartado, identidade selecionada pelo servidor.
- Impacto: quem alcançar a API compartilha a identidade e memória do mock.
- Decisão vigente: manter local; JWT foi retirado a pedido. Integração de
  autenticação do aplicativo é pendente, sem inventar validador ou permissões.
- Controle existente: acesso por perfil/CD é conferido nas consultas, e o cliente
  não escolhe identidade nos argumentos de tools. Isso não autentica o chamador.

## Média: BP-02 — Disponibilidade e quotas

- Local: `app/llms.py`, `criar_agente`/`obter_modelos`; `app/juiz.py:112`,
  `avaliar`; `app/main.py`, handlers.
- Evidência: serviços externos são necessários; testes reais encontraram
  HTTP 413, HTTP 429 e falha de conexão. Redis local estava desligado.
- Correções: julgamento de PDF por página, menos dados repetidos, referências
  restritas no schema, timeout de 30 segundos/chamada, zero retries automáticos,
  até 25 passos por agente. O Redis existente foi iniciado, sem gerar leituras.
- Risco residual: quota e disponibilidade externas; relatórios extensos exigem
  mais chamadas. Não usar fallback de aprovação nem remover o juiz para passar.
- Antes de publicar: aprovar limites de volume/concor­rência e retenção. Não
  foram inventadas quotas de usuários nem janelas operacionais.

## Média: BP-03 — Instruções e interpretações em conteúdo não confiável

- Local: `app/guardrail.py`, `guardrail_entrada`/`guardrail_saida`;
  `app/diagnostico.py:132`, `validar_analise`;
  `app/regras_diagnostico.py:118`, `recuperar_regras`.
- Controles: consulta por identidade interna, schemas, fonte literal dos relatos,
  requisitos das regras, tratamento de negação/incerteza e comparação numérica.
  Recuperação compara conteúdo, versão e assinatura com a base aprovada.
- Correções: leituras inválidas não são apresentadas como temperaturas válidas;
  fontes do turno chegam ao juiz; memória é identificada como histórica.
- Risco residual: regex e julgamento por LLM são parciais. Não permitir que texto
  de justificativas, memória ou regras recuperadas altere autorização/aprovação.

## Média em uso prolongado: BP-04 — Acúmulo de mensagens

- Local: `app/memory.py:65`, `salvar_turno_conversa`.
- Evidência: `$push/$each` conserva mensagens no documento de sessão. O contexto
  consulta somente as últimas 20, mas não reduz o documento armazenado.
- Impacto: sessão longa pode alcançar o limite de documento do MongoDB.
- Pendente: política de retenção/rotação ou mudança de armazenamento aprovada.
  Não apagar conversas nem iniciar sessões silenciosamente nesta revisão.

## Controles conferidos

- SQL parametrizado; trechos dinâmicos são cláusulas fixas, em
  `app/tools/monitoramento.py:59` e `:186`. A comparação de estado/nível usa
  maiúsculas sem alterar os valores originais ou o escopo.
- Justificativas por alerta/câmara autorizados, em `app/tools/diagnostico.py`.
- Qdrant de memória filtrado por usuário e reconferido no payload, em
  `app/vectorstore.py`, `buscar_resumos`; índice técnico separado.
- PDF usa snapshot somente leitura, fecha conexão antes de renderizar, escapa
  texto, julga antes de registrar, calcula hash e faz auditoria com rollback.
  Campos físicos `gerado`/`baixou` respeitam as constraints consultadas.
- Observabilidade exclusiva de SUPER_ADMIN, sem mensagens/credenciais. ContextVar
  conserva turnos entre threads; falha do juiz não conta como sucesso.
- `.env` ignorado pelo Git; pacote conferido sem arquivo de ambiente. Design,
  FAQ e regras incluídos na distribuição.
- Nenhum endpoint recebe caminho de arquivo, comando de shell ou URL arbitrária
  para buscar conteúdo. Não há uploads ou desserialização pickle no runtime.

## Validação e pendências

Os testes unitários usam mocks simples e verificações diretas. Integrações reais
e perguntas são registradas separadamente em `ACOMPANHAMENTO_IMPLEMENTACAO_SKADI.md`.
O checklist atual está em `../TRIMMY.md`; os totais históricos de outras entregas
não representam a suíte atual.

Sem alteração nos repositórios mobile/backend, permissões dos serviços, planos
pagos, tabelas ou triggers. Nenhum usuário foi promovido a SUPER_ADMIN.
