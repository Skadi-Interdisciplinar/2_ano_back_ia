# Pull request

## Descrição do pull request

- Descreva brevemente o que foi feito e como isso afeta o comportamento, a precisão ou o desempenho do Agente de IA.

## Que tipo de alteração foi feita

- [ ] Nova Feature (Core Backend)
- [ ] Correção de bug
- [ ] Refatoração de código
- [ ] Documentação
- [ ] Criação ou Refinamento de Prompt
- [ ] Nova Ferramenta/Ação (Tool/Function Calling) do Agente
- [ ] Alteração/Atualização de Modelo (LLM) ou Parâmetros (Temperatura, Top-P, etc.)
- [ ] Ajuste em RAG (Embeddings, Vector DB, Recuperação de Contexto)
- [ ] Outro: ______________

## Alterações realizadas

- Descreva detalhadamente o que foi alterado no código (Ex: Nova lógica de roteamento do agente, adição de memória, alteração de system prompt, etc.)

## Validação e Testes

- [ ] sim
- [ ] Não

### Evidências (opcional)

- Cole aqui evidências de que o código e o comportamento do agente foram testados (ex: logs da observabilidade do LLM, saída do prompt esperado, prints de tela).

## Como testar (se necessário)

- Descreva os passos para testar esta alteração.
- **Dica:** Se for uma alteração no agente, forneça os *prompts de entrada* exatos que o revisor deve usar para reproduzir ou testar o comportamento esperado.

## Checklist de Agentes e IA

- [ ] Nenhum bug aparente e o código segue os padrões do projeto.
- [ ] A documentação foi atualizada (se aplicável).
- [ ] **Observabilidade:** Logs e Tracing (ex: LangSmith, Langfuse, Datadog) cobrem adequadamente as novas interações e invocações do LLM.
- [ ] **Tratamento de Falhas:** Cenários de falha do LLM (timeouts, parsing de JSON inválido, recusa de resposta, alucinações) foram tratados adequadamente.
- [ ] **Custos e Tokens:** O impacto do uso de tokens e a latência foram considerados (a alteração não introduz um consumo ou lentidão desproporcional).
- [ ] **Regressão:** O comportamento e a segurança do agente não regrediram para casos de uso existentes.

## Comentário (opcional)

- Deixe aqui qualquer comentário ou informação adicional (ex: links para referências de papers, discussões sobre limites de tokens, ou decisões arquiteturais).