# Memória da Trimmy

POST `/chat` continua recebendo somente `token` e `mensagem`. O servidor mantém
uma sessão ativa por usuário em `Skadi.sessoes_trimmy`; as últimas 20 mensagens
dessa sessão alimentam o contexto imediato. A coleção antiga `conversas` não é
apagada nem migrada automaticamente.

O MongoDB retorna somente as últimas 20 mensagens para o chat, sem apagar as
anteriores. A sessão é vinculada no início do turno: pergunta e resposta são
gravadas juntas com um único `$push/$each`. Se a sessão for encerrada durante a
consulta, o turno não é transferido para uma sessão nova e a API retorna 409.

POST `/chat/encerrar` recebe `{"token": "teste"}`. Gera um resumo com o modelo
rápido e o indexa no Qdrant antes de encerrar a sessão. Retorna `{"resumo": "..."}`
ou `{"resumo": null}` se não houver sessão/mensagens. A próxima mensagem cria
outra sessão. O aplicativo precisa chamar explicitamente essa rota; fechar o
aplicativo não encerra a sessão automaticamente.

Configure `QDRANT_URL` e `QDRANT_API_KEY` no `.env`. Opcionalmente, configure
`ASSESSOR_ENV_FILE` com o caminho do `.env` do Assessor para aproveitar somente
essas duas variáveis. Variáveis próprias da Trimmy prevalecem. Nenhuma configuração
de banco do Assessor é reutilizada por esse mecanismo.

O espaço vetorial usa o mesmo modelo do Assessor, `gemini-embedding-2-preview`,
com 768 dimensões, mas somente a coleção `trimmy_memoria_resumos`. A identidade
vem do contexto interno, nunca de argumentos escolhidos pelo modelo.
`buscar_historico` retorna até três resumos filtrados por usuário. Não substitui
tools operacionais nem dados atuais ou regras aprovadas. O orquestrador não recebe tools.

Falhas de resumo/indexação são propagadas; a sessão é reaberta e as mensagens
permanecem. O resumo salvo pode ser reutilizado em nova tentativa. O ID do ponto
Qdrant é o UUID da sessão, evitando duplicação em reindexações. Não há transação
distribuída entre MongoDB e Qdrant. A coleção de sessões tem índice único parcial
por usuário para impedir duas sessões ativas. Não há política de retenção ou
limite de tamanho aprovado; sessões muito longas ainda exigem essa definição.

A autenticação permanece mockada com usuário 12. Assim, todos os clientes de teste
compartilham a mesma identidade e memória até integrar a autenticação real.
