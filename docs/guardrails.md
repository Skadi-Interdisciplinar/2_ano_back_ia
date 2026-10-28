# Guardrails da Trimmy

Implementados em 21/10/2026, com a organização do Assessor como referência:
`app/guardrail.py` concentra as verificações; `app/graph.py` tem os nós
`guardrail_entrada` e `guardrail_saida`. Não são agentes nem tools.

## Entrada

O primeiro nó verifica a mensagem antes de carregar a sessão ou chamar modelos.
Os limites de formato/tamanho continuam no `ChatRequest`, sem um segundo schema
concorrente. A verificação adicional reconhece alguns padrões explícitos de
substituição de instruções, pedidos de prompts/credenciais e inclusão de segredos.

Quando identifica um desses padrões, retorna uma recusa fixa no contrato habitual
do chat, com lista de agentes vazia. A recusa passa pelo guardrail de saída.
Não chama o roteador, ferramentas, MongoDB nem provedor; não grava esse turno.
É uma resposta de chat, não uma concessão/negação de acesso a um objeto consultado.

Na entrada permitida, o texto efetivamente enviado aos agentes é mascarado.
O histórico carregado e as memórias recuperadas também são tratados. A mensagem
nova persistida contém o texto mascarado, não o dado pessoal original.
Não há mapa reversível nem restauração automática de dados pessoais.

## Saída

Todas as rotas do chat passam pela saída: monitoramento, diagnóstico, FAQ e
orquestrador/conversa geral. A verificação acontece antes de salvar o turno.

- Reutiliza o formato em texto simples de `ChatResponse`.
- Rejeita resposta vazia, padrões de credenciais, valores completos de segredos
  configurados e cópias reconhecíveis de instruções internas.
- Mascara padrões de dados pessoais, sem pedir a outro modelo que reescreva fatos.
- Saída rejeitada gera `SaidaModeloInvalida`, mapeada para 502 com mensagem pública
  genérica. A resposta rejeitada não é salva e não há tentativa ilimitada de correção.

Não recalcula temperaturas, não interpreta status e não inventa conclusões:
continuam valendo a apresentação determinística do monitoramento, a validação das
evidências/regras do diagnóstico e a seleção estruturada dos itens da FAQ.

O resumo de `/chat/encerrar` também recebe tratamento antes de indexar/devolver.
Mensagens antigas são mascaradas antes de enviadas ao resumidor; falha de saída
não indexa o resumo e reabre a sessão pelo tratamento já existente.

## Dados pessoais e fontes

O mascaramento reconhece e-mails privados, CPF/CNPJ formatados, CPF/CNPJ numéricos
explicitamente identificados e telefones em formatos reconhecidos ou rotulados.
Sequências numéricas sem contexto não são adivinhadas como CPF ou telefone:
isso evita confundir IDs, eventos e valores operacionais com documentos pessoais.
Não há reconhecimento geral de nomes, endereços ou toda forma possível de PII.

Os e-mails explicitamente publicados na FAQ aprovada, como o contato de suporte,
são preservados. Datas, temperaturas, limites, status e fontes técnicas continuam
os mesmos; não há revisão financeira nem filtros de investimento/política.

Também são tratados os campos textuais públicos do cadastro/alertas, os resumos
da tool de memória e o motivo/descrição de justificativas. No diagnóstico, a fonte
da justificativa é registrada com o mesmo texto mascarado retornado pela tool:
a validação de citação literal continua consistente, sem restaurar dados pessoais.
Associações de câmara/alerta/atendimento continuam feitas por IDs internos.
Se um cadastro usar dado pessoal como identificação textual, o mascaramento pode
exigir outra identificação; ele não autoriza ampliar a busca para contornar isso.

## O que não muda e limites da proteção

- Nenhuma chamada adicional ao LLM, dependência paga, agente ou tool nova.
- `POST /chat` continua recebendo somente token e mensagem. Permissões, filtros de
  alertas, regras aprovadas e consultas SQL não foram ampliados.
- O PDF não passa pelo grafo conversacional e não foi alterado nesta etapa.
- A autenticação continua mockada para testes locais; guardrail não autentica.
- São verificações determinísticas e parciais. Há risco de falsos positivos e de
  evasão por outra formulação, codificação ou conteúdo indireto. Não garantem
  detectar toda injeção, vazamento, dado pessoal ou informação falsa.
- Mensagens, justificativas e memória continuam sendo dados, nunca permissões ou
  instruções de sistema. A autorização continua nas consultas do backend.
- Registros antigos dos bancos não são migrados, apagados ou anonimizados em lote.
  O tratamento ocorre nas fronteiras de leitura/envio e nos novos turnos gravados.
- Configurações externas de tracing, logs de requisição e telemetria também precisam
  de revisão antes de produção: estes guardrails não limpam dados já registrados
  por um proxy, cliente ou coletor fora dessas fronteiras.
- Não foram criados limites de temperatura, retenção, prazo de sessão ou orçamento
  de chamadas para justificar esta implementação.

## Arquivos alterados nesta etapa

| Arquivo | Responsabilidade |
| --- | --- |
| `app/guardrail.py` | Entrada, saída e mascaramento compartilhado. |
| `app/graph.py` | Dois nós, recusa antecipada, sessão carregada depois da entrada e persistência após saída. |
| `app/memory.py` | Proteção das mensagens enviadas ao resumidor e do resumo antes de indexar. |
| `app/tools/diagnostico.py` | Justificativa mascarada e fonte literal coerente. |
| `app/tools/memoria.py` | Resumos recuperados sem dados pessoais reconhecidos. |
| `app/tools/monitoramento.py` | Campos textuais públicos tratados antes de chegar ao modelo. |
| `app/routes/chat.py` | Documentação dos erros do encerramento. |
| `tests/test_guardrail.py` e testes existentes | Recusas, formatos legítimos, privacidade, dados operacionais e regressão. |

Testes usam segredos fictícios, modelos e bancos simulados. Não foi necessário
enviar dados aos provedores ou alterar bancos para testar estes guardrails.

Validação da etapa: 484 testes passaram, quatro integrações opt-in foram puladas
e houve dois avisos de dependências. Ruff passou. Isso comprova as verificações
exercitadas, não proteção completa contra toda formulação ou falha do modelo.
