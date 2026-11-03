# FAQ integrada à Trimmy

A fonte aprovada é `docs/faq_skadi.md`, versão 1.0. Sua cópia de execução fica
em `app/base_faq.md`, incluída no pacote da aplicação. Um teste exige que os dois
arquivos permaneçam iguais. Os itens removidos pelo responsável não foram restaurados.

O agente recebe essa base pequena diretamente no contexto: não foi criada outra
coleção vetorial, tool ou serviço para a FAQ. Isso mantém a separação de domínios
do Assessor, mas evita reproduzir seu pipeline de ingestão de PDF para 31 respostas.

O modelo retorna `SelecaoFAQ`: referências a itens existentes e uma indicação
de informação ausente. `app/faq.py` valida as referências e entrega somente os
textos aprovados. O orquestrador não os reescreve. Texto técnico ou resposta livre
não pode ser inserido nesse schema. Memória não aprova conteúdo de suporte.

Durante os testes, a resposta livre inventou atendimento de segunda a sexta e
ausência de atendimento no domingo. A versão estruturada respondeu apenas o horário
documentado, das 9h às 17h, e informou a ausência dos demais detalhes.

Isso reduz invenções, mas não garante que o modelo sempre escolha o item mais
pertinente. Referências erradas/inexistentes geram erro validado, não conhecimento
livre. Mudanças na FAQ exigem aprovação, atualização das duas cópias, testes e
reinício da aplicação para carregar a nova versão.
