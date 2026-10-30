# Observabilidade da Trimmy

`GET /observabilidade` disponibiliza os dados necessários à futura tela mobile
de observabilidade. O endpoint exige `Authorization: Bearer <token>` e é
disponível a todos os perfis com usuário cadastrado, sem restrição de cargo.

## Testar localmente

Enquanto a autenticação é mockada, `TRIMMY_USUARIO_TESTE_ID` seleciona no servidor
o usuário de teste. O padrão é `12` (GESTOR), que pode consultar este endpoint.
É necessário um usuário existente no PostgreSQL. A configuração afeta todos os
endpoints que usam o mock. Nenhum token enviado pelo cliente escolhe o perfil.

No Swagger (`/docs`), clique em `Authorize`, informe somente `teste` e confirme.
Depois abra `GET /observabilidade`, clique em `Try it out` e `Execute`.
O Swagger envia `Authorization: Bearer teste` automaticamente. Não envie corpo JSON.
A autenticação usa o esquema HTTP Bearer do OpenAPI: declarar `Authorization`
como parâmetro comum faz o Swagger ignorar esse cabeçalho reservado.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/observabilidade' -Headers @{Authorization='Bearer teste'}
```

Sem Bearer, a resposta é `401`; usuário inexistente ou com cadastro inválido recebe
`403`. Com usuário válido e os bancos disponíveis, o retorno é `200` com as métricas.

## Dados retornados

- `resumo`: total de turnos, índice de erros, latência média e p95, tokens e
  custo estimado.
- `latencia_interagentes`: latência média e quantidade de chamadas por nó do
  fluxo.
- `projecoes_semanais`: estimativas para 100 e 1.000 usuários, usando uma
  interação semanal por usuário como premissa explícita.
- `custo_por_resolucao`: custo estimado dos turnos dividido pela quantidade de
  turnos concluídos e aprovados pelo juiz (`resumo.resolucoes_tecnicas`). Uma
  resolução técnica de interação não comprova resolução de um alerta/defeito.
- `roi`: `(benefício estimado - custo estimado) / custo estimado * 100`.
  Benefício = resoluções técnicas × minutos manuais evitados / 60 × custo/hora USD.
  A definição foi delegada pelo usuário; as premissas devem ser configuradas em
  `ROI_TEMPO_MANUAL_MINUTOS` e `ROI_CUSTO_HORA_USD`, sem valores padrão. Sem
  premissas válidas ou custo positivo, retorna `null` com motivo. Não representa
  economia comprovada, faturamento nem cobrança real da conta gratuita.
- `turnos_recentes`: até 50 turnos recentes, sem conteúdo de mensagens.

## Persistência e privacidade

Ao terminar um turno, a API registra em `Skadi.observabilidade_trimmy` somente
data/hora, rota, status, latências, tokens, custo estimado e nomes de modelos.
Perguntas, respostas, token de autenticação, dados de câmaras, alertas e
credenciais não são armazenados nessa coleção.

O painel calcula os dados a partir dos últimos 200 turnos persistidos. Se o
MongoDB estiver indisponível, o chat não deixa de responder por isso, mas o
endpoint de observabilidade retorna indisponibilidade até a leitura voltar.

## Integração futura do mobile

A tela mobile pode consumir esse endpoint com usuário cadastrado e deve apresentar
os valores ausentes como “não disponível”, acompanhados do motivo retornado.
Ela não deve tentar calcular ROI, custo por resolução ou custo estimado no
cliente.

O contexto da telemetria usa ContextVar para acompanhar as threads do grafo.
Falha do juiz conta como erro, sua reprovação como bloqueio; não entram como
resolução técnica. A cópia redundante de turnos em memória foi removida.
