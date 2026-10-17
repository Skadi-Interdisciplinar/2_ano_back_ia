# Consultas de monitoramento

O agente dispõe de três tools: consultar_temperaturas, listar_camaras_responsaveis
e consultar_alertas_atuais_do_usuario. São declaradas com @tool e exportadas em
TOOLS, no padrão do Assessor. A memória de conversas é uma tool separada.

## Temperaturas

consultar_temperaturas recebe camara_id, modelo e/ou localizacao para identificar
uma câmara. Para todas as câmaras permitidas, exige todas=True sem filtros.
Filtros vazios, tipos inválidos ou combinação de todas=True com identificação são
rejeitados. Nenhum erro de identificação amplia o escopo automaticamente.
A comparação textual é exata, sem distinguir maiúsculas; não há campo nome.

A resposta é um objeto com status e camaras (sempre uma lista). status=ok retorna
leituras; nao_encontrada indica que nenhuma câmara corresponde no escopo permitido;
ambigua traz candidatos para esclarecimento, sem consultar o Redis. Ausência de
leitura retorna temperatura/data_hora nulos e leitura_disponivel=false.
Falhas de infraestrutura são propagadas, não convertidas em ausência de dados.

Uma única consulta cadastral interna aplica o usuário/CD e os filtros no PostgreSQL.
O Redis é lido em lotes de 1.000 eventos até encontrar as últimas leituras dos
sensores autorizados ou esgotar o stream, tanto para uma quanto para várias câmaras.
O lote é técnico, não limite de validade; o horário não garante temperatura atual.

## Cadastro e alertas

listar_camaras_responsaveis usa a mesma consulta interna, mas não acessa o Redis.
Retorna modelo/localização e limites. IDs de câmara/sensor/evento não são entregues
ao modelo pelas tools de cadastro ou temperaturas.

Alertas permanecem separados, com os filtros já aprovados para status, CD,
nível do operador e reconhecimento pelo próprio usuário. Não houve ampliação
de permissões nem mudança de esquema dos bancos.

Os filtros usam os valores do backend em maiúsculas e sem acento: `ATIVO`,
`RECONHECIDO` e `OPERADOR`. Gravidade, tipo e status retornados pelo banco são
preservados; dados antigos não são convertidos silenciosamente pela consulta.

O usuário vem do contexto interno, nunca de argumentos do LLM. SQL usa parâmetros.
A autenticação continua mockada com usuário 2; não publicar esse bypass em produção.

## Exemplos de argumentos internos

- Câmara por ID: {"camara_id": 3}
- Câmara por localização: {"localizacao": "localização cadastrada"}
- Todas as câmaras: {"todas": true}

O mobile continua enviando apenas token e mensagem para POST /chat.
Não precisa selecionar a tool ou enviar seus argumentos.

As três tools anteriores de leitura foram removidas do registro e do código.
Chamadas internas diretas aos nomes antigos precisam usar consultar_temperaturas.
