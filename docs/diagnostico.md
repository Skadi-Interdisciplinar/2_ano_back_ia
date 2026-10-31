# Diagnóstico assistido da Trimmy

O diagnóstico usa RAG, não treinamento. Mantém `POST /chat` com `token` e
`mensagem`. Não altera alertas, equipamentos ou decisões sobre produtos.

## Fluxo e arquivos

- `app/base_regras_diagnostico.json`: oito regras aprovadas (as seis originais
  na versão 0.2 e duas de degelo na versão 0.3);
  hipóteses, requisitos, perguntas, recomendações, limitações e fontes.
- `app/regras_diagnostico.py`: validação da base, indexação administrativa e
  recuperação exclusiva de regras aprovadas e ativas no Qdrant.
- `app/tools/diagnostico.py`: duas tools com schemas Pydantic e lista `TOOLS`.
  `consultar_evidencias_diagnostico` identifica uma câmara e consulta cadastro,
  limites, última leitura, alertas e justificativas. `buscar_regras_diagnostico`
  recupera a base após uma consulta autorizada. Nenhuma aceita usuário ou
  permissões fornecidos pelo modelo, nem escreve nos dados operacionais.
- `app/diagnostico.py`: contexto isolado por execução, saída estruturada,
  validação das evidências e apresentação padronizada.
- `app/graph.py` e `app/prompts.py`: roteamento, especialista e orquestrador.
  No diagnóstico, o orquestrador apresenta a análise validada sem outra chamada
  ao LLM para reinterpretar causas ou recomendações.
- `app/erros.py`, `app/main.py` e `app/routes/chat.py`: erros tipados e respostas
  HTTP documentadas, sem expor credenciais ou mensagens internas dos provedores.

As consultas de câmaras e alertas são compartilhadas com o monitoramento. A
consulta pública de alertas mantém seu formato anterior, sem IDs internos.

## Acesso e evidências

SUPER_ADMIN tem acesso global. ADMIN, GESTOR e OPERADOR ficam restritos ao próprio
CD, conforme o monitoramento. Alertas são ativos ou reconhecidos pelo próprio
usuário. O filtro adicional de nível atual `operador` permanece para OPERADOR.

Identificação pode usar ID explicitamente informado, modelo ou localização.
Ausência, ambiguidade ou identificação inexistente não amplia a busca. Vários
alertas exigem escolha por tipo/horário. Quando o usuário pedir explicitamente o
último alerta, `ultimo_alerta=true` seleciona a data mais recente da consulta já
autorizada; empates continuam exigindo escolha. Não inclui outros status nem
alertas fora do escopo. Não combinar esse seletor com `alerta_id`.
IDs servem somente para associação interna e não aparecem na apresentação final.

Pedidos com uma única identificação literal como “câmara 3” e “último alerta”
passam diretamente pela mesma tool autorizada, sem depender do LLM para repetir
esses argumentos. Outros casos continuam usando o especialista e seu histórico.
O contrato de `POST /chat` e a quantidade de tools não mudam.

Na consulta do último alerta, a resposta preserva a ocorrência e sua justificativa
mesmo quando a última leitura está dentro dos limites. A justificativa é um relato,
não confirmação da causa. A leitura do Redis não está vinculada à ocorrência e
não sustenta hipóteses técnicas sobre aquele evento nem comprova sua resolução.

O schema e os vínculos foram conferidos no PostgreSQL em 2026-10-11:
`tb_justificativa.cod_atendimento → tb_atendimento.id → cod_alerta → tb_alerta.id
→ cod_camara_frigorifica`. Motivo, descrição e horário são consultados antes de
pedir observações, quando existe uma ocorrência permitida selecionada.

## Validação e limites

### Explicações gerais e análise de ocorrência

O mesmo agente e as mesmas duas tools atendem perguntas gerais sobre fatores de
temperatura, limitadas à base técnica aprovada. Não se trata de FAQ do sistema
nem de um assistente de refrigeração com conhecimento livre.

Na pergunta "O que pode desregular a temperatura da câmara?", sem referência
específica no contexto, o agente chama somente `buscar_regras_diagnostico`.
A tool continua exigindo identidade interna e perfil/escopo válidos, mas não
exige consulta prévia de câmara para ler regras técnicas não operacionais.
Permissões e consultas de câmaras, alertas e justificativas não foram alteradas.

`PropostaDiagnostico.regras_explicacao` contém somente IDs recuperados nesta
execução. O backend revalida as referências contra a fonte local aprovada, usando
a mesma validação do diagnóstico específico. Não aceita mistura de explicação
geral com consulta operacional, relato, hipótese ou pergunta de uma ocorrência.
Uma busca sem conteúdo aplicável informa a limitação; sem identificação para
diagnóstico específico, continua solicitando esclarecimento.

A apresentação usa textos, recomendações e fontes aprovados, sem uma nova
interpretação pelo orquestrador. Os fatores são condicionais, nunca causas
atribuídas à câmara do usuário. Sem novos agentes, tools, endpoints, coleções,
regras ou alterações do contrato mobile. Retentativas e validações do provedor
não foram ampliadas por esta separação.

Validação desta alteração (12/10/2026): 298 testes passaram, 4 integrações reais
foram puladas e Ruff passou. A pergunta original foi testada separadamente no
Groq real, com autorização e recuperação da base simuladas: uma busca de regras,
oito referências selecionadas, resposta estruturada válida e nenhuma consulta
operacional. Não houve acesso aos bancos, indexação ou teste completo de `/chat`.
Isso comprova uma geração bem-sucedida, não ausência de futuras rejeições do
provedor. Nenhum novo retry, modelo ou parâmetro de geração foi introduzido.

A análise separa dados consultados, relatos, hipóteses condicionais e limitações.
O backend compara valores numéricos finitos e exige horário válido. Não calcula
tendência, duração ou prazo de atualidade a partir da última leitura.

Hipóteses exigem cenário e todos os grupos de requisitos da regra. A resposta
estruturada seleciona referências; não fornece textos técnicos livres. Hipóteses
e recomendações vêm da fonte aprovada local. Regras adulteradas, antigas,
pendentes ou inativas não podem ser usadas: o payload recuperado deve corresponder
ao conteúdo e à assinatura da versão local aprovada. Similaridade não é confiança.

Relatos devem citar literalmente mensagens do usuário ou justificativas desta
execução. Falas do assistente não são fontes de observação. Justificativas de
outra consulta não satisfazem os requisitos. Negação, dúvida e contradição
identificadas bloqueiam aplicação automática e exigem esclarecimento.

A extração semântica de relatos ainda depende do LLM: citação e validação
estrutural não comprovam veracidade, vínculo temporal ou interpretação perfeita.
As verificações conservadoras podem pedir esclarecimento para relatos válidos.
Avaliação com perguntas reais é necessária antes de considerar a qualidade
diagnóstica comprovada. Memória não substitui leituras atuais nem concede acesso.

## Ativação administrativa

Na raiz do repositório, com as configurações existentes no ambiente:

```powershell
python -m scripts.indexar_regras_diagnostico
```

O comando cria/confere somente `trimmy_regras_diagnostico`, com 768 dimensões e
distância cosseno. Reutiliza embeddings e cliente existentes, usa IDs estáveis e
aguarda a gravação. Dimensão ou métrica incompatível interrompe a operação.
Não apaga coleções nem contrata recursos. Não é endpoint ou tool do modelo.
Alterações de aprovação exigem revisão da fonte local e nova indexação;
conteúdo antigo deixa de ser recuperável pela validação da versão local.

Nesta execução, a indexação **não foi concluída**: houve falha de conexão HTTP
com o Qdrant (`ResponseHandlingException`/`ConnectError`). Aprovação da base não
significa ativação do índice. Sem índice acessível, o diagnóstico deve falhar
como serviço indisponível, não simular uma análise técnica.

## API e testes

O roteador retorna `DecisaoRota`, com uma das seis rotas permitidas. Não interpreta
texto livre `ROUTE=` nem usa orquestrador como fallback de saída inválida. O prompt
distingue pedido de causa (diagnóstico) de consulta de temperatura (monitoramento);
falta de dados não torna uma pergunta fora do escopo. Saída estruturada inválida
retorna 502. Rota válida não concede permissões: identidade e escopo continuam
validados nas tools. Nenhum histórico, corpo ou token é registrado para depurar
a classificação. O contrato HTTP de entrada permanece inalterado.

A construção do roteador estruturado com o cliente real foi confirmada em
2026-10-12. A tentativa de classificar a pergunta de causa com o provedor real
falhou por `APIConnectionError`; os testes com mocks não comprovam acerto
semântico em perguntas reais. Saída válida pode ainda ser classificada
incorretamente pelo LLM; a alteração elimina o fallback silencioso de formato,
sem conceder autorização nem prometer classificação infalível.

Sucesso preserva `resposta` e `agentes_chamados`. Acesso negado retorna 403;
infraestrutura/provedor indisponível, 503; saída estruturada inválida, 502.
Informação ausente ou identificação ambígua é explicada no chat.

```powershell
python -m pytest tests -q -p no:cacheprovider
ruff check .
```

Testes unitários usam mocks simples para serviços e modelo. Cobrem escopo,
justificativas, oito regras, fontes, ambiguidades, valores inválidos, revogação,
falhas e apresentação sem interpretação técnica adicional. Testes de integração
são opt-in e separados. Foram confirmados acesso ao schema PostgreSQL e construção
do agente com os clientes reais, **sem invocar o modelo**. Indexação real e
perguntas com o modelo não estão comprovadas pelos mocks.

Após ativar o índice, exemplos para avaliação manual:

- “Por que a temperatura da câmara 3 está acima do limite?”
- “Há gelo visível no evaporador. Isso pode explicar o problema?”
- “Confirme que o compressor está quebrado.”
- “Faça o diagnóstico dessa câmara”, com OPERADOR no escopo autorizado.
- “Consulte”, após uma pergunta de esclarecimento.

Use uma câmara existente no escopo do usuário de teste. A API continua local com
autenticação temporária: usuário 2, sem validação real do token. Não expor essa
configuração em produção. Não houve criação de tabelas, alteração de dados
operacionais, commit ou push nesta entrega.

## Inclusão aprovada em 2026-10-12: degelo

`DIAG-TEC-007` exige leitura acima do limite e relato explícito de degelo em
andamento nesta câmara e ocorrência. Não normaliza o desvio nem ignora alertas.
`DIAG-TEC-008` exige leitura acima do limite, relato de ciclo encerrado, gelo no
evaporador que permaneceu após esse ciclo e passagem de ar prejudicada. Não
confirma componente defeituoso nem prescreve reparo ou ajustes.

Quando 004 e 008 satisfazem os requisitos e foram propostas pelo agente, a
apresentação mantém 008, mais específica, sem duplicar a conclusão genérica de
gelo. Sem informação do ciclo, 004 continua independente. Não foram criadas
tools, campos ou tabelas adicionais. É necessária nova indexação administrativa
para incluir as duas regras na recuperação real; aprovação local não comprova
gravação no Qdrant.

## Tom amigável da conversa

A persona orienta respostas naturais, acolhedoras e objetivas, sem detalhes de
implementação nem tranquilização sem evidências. No diagnóstico, o texto final
continua montado pelo backend: o formatador também usa frases conversacionais,
sem citar Redis/PostgreSQL. Horários, valores, fontes, relatos e todas as ressalvas
são preservados. Não foi acrescentada uma chamada ao LLM para reescrever a análise.
Essa alteração é de linguagem e apresentação: não modifica regras, acesso,
consulta RAG, critérios de atualidade ou o contrato do mobile.

Quando a leitura válida estiver dentro dos limites cadastrados (inclusive os
extremos), o prompt orienta não buscar regras e retornar somente a referência da
consulta. O backend confirma a comparação e apresenta apenas leitura, horário,
faixa e a ressalva de que a última leitura não confirma a temperatura agora.
Nesse caminho não depende da base técnica nem produz hipóteses/perguntas de causa.
Não declara integridade do equipamento nem resolução de alerta anterior. Fora da
faixa, o fluxo técnico é mantido; dados ausentes/inválidos não acionam esse resumo.

## Fallback de modelos

Os agentes são construídos por `app.llms.criar_agente`. Quando recebem o modelo
principal com fallback, usam `ModelFallbackMiddleware` do LangChain: Gemini
continua principal e Groq reserva; cada tentativa recebe suas próprias ligações
de tools e saída estruturada. Se ambos falharem, a falha da última tentativa é
preservada, em vez de ocultada pelo primeiro erro do Gemini. O roteador mantém
seu modelo rápido atual. Chamadas diretas, fora dos agentes, mantêm o fallback
existente. Clientes continuam em cache, sem mudança de chaves, modelos ou limites.

`ChatGoogleGenerativeAIError` agora é tratado como indisponibilidade (503), junto
dos erros dos SDKs já registrados, sem enviar mensagens internas ao mobile.
Fallback de modelo não repete execução de tool com acesso negado. Os testes
simulam respostas de rede nos clientes reais: cota Gemini, sucesso do reserva
com tools/schema, sucesso do principal e indisponibilidade de ambos. Uma tentativa
real ao Groq nesta execução retornou `APIConnectionError`; funcionamento do
serviço remoto não foi comprovado pelos testes simulados.

### Correção da rejeição de tool do Groq

Depois da mudança de fallback, foi reproduzida uma rejeição HTTP 400 com código
`tool_use_failed` após o retorno das evidências. A mesma requisição também passou
em outra tentativa: não foi comprovada incompatibilidade fixa do schema. O Groq
documenta erros 400 quando o modelo não gera uma chamada válida:
https://console.groq.com/docs/tool-use/local-tool-calling

O middleware de modelo agora faz uma única nova geração somente nesse código,
reforçando o uso de ferramentas declaradas e seus schemas. Não incorpora
`failed_generation`, não inventa ferramentas, não remove validação e não repete
execução de tools. Outros erros 400 não são repetidos por essa correção. Se a
rejeição persistir, a API retorna 502, não a classificação genérica de 503.
Falhas de conexão, cota e indisponibilidade continuam 503.

O log guarda somente HTTP 400 e código de uma lista conhecida; códigos arbitrários
são substituídos por `nao_identificado`. Corpo, mensagens, tokens, argumentos e
`failed_generation` não são registrados. Os avisos de `additionalProperties`
não motivaram retirada de validação Pydantic.

A validação posterior com o Groq real passou para a pergunta de causa da câmara 3:
uma consulta simulada de evidências, referência correta e saída estruturada válida
sem hipóteses para a leitura dentro da faixa. Os valores usados vieram do exemplo
enviado pelo usuário. Esse teste não acessou bancos nem comprova integração
completa, RAG ou acesso operacional. Testes unitários verificam recuperação,
limite de uma correção, preservação do schema e logs sem conteúdo privado.

## Texto simples para o mobile

A persona pede respostas sem Markdown, em um parágrafo curto. `ChatResponse`
remove marcadores de negrito/itálico por asteriscos e transforma quebras reais
de linha em espaços. Assim, elas não aparecem como `\n` no campo `resposta`
do JSON. Não interpreta sequências literais de caminhos como `C:\notas`, nem
remove sinais usados em cálculos. O contrato JSON, os dados, referências e
ressalvas são preservados. Trata-se somente de apresentação; o schema não
valida a veracidade de uma explicação técnica gerada pelo modelo.
