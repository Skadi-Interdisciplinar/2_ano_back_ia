# Observabilidade da Trimmy

`GET /observabilidade` disponibiliza os dados necessários à futura tela mobile
de observabilidade. O endpoint exige `Authorization: Bearer <token>` e é
disponível a todos os perfis com usuário cadastrado, sem restrição de cargo.

## Testar localmente

Faça login no backend principal por `POST /auth/login` e copie o campo `token`.
A Trimmy precisa da mesma `SECURITY_KEY` do backend e de acesso ao mesmo banco
de usuários. A identidade vem do JWT validado e do cadastro; não há usuário fixo.

No Swagger (`/docs`), clique em `Authorize`, informe somente o JWT real e confirme.
Depois abra `GET /observabilidade`, clique em `Try it out` e `Execute`.
O Swagger envia `Authorization: Bearer <JWT>` automaticamente. Não envie corpo JSON.
A autenticação usa o esquema HTTP Bearer do OpenAPI: declarar `Authorization`
como parâmetro comum faz o Swagger ignorar esse cabeçalho reservado.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/observabilidade' -Headers @{Authorization='Bearer JWT_DO_LOGIN'}
```

Sem Bearer, com token inválido/expirado ou usuário inexistente, a resposta é `401`.
Cadastro com perfil não reconhecido recebe `403`. Com usuário válido e os bancos
disponíveis, o retorno é `200` com as métricas.

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
  `ROI_TEMPO_MANUAL_MINUTOS` e `ROI_CUSTO_HORA_USD`, com padrão acadêmico explícito de 5 minutos e US$ 5/hora. Sem
  premissas válidas ou custo positivo, retorna `null` com motivo. Não representa
  economia comprovada, faturamento nem cobrança real da conta gratuita.
- `turnos_recentes`: até 50 turnos recentes, sem conteúdo de mensagens.

## Persistência e privacidade

### Cenário acadêmico de ROI aprovado para os testes

Em 30/10/2026, o usuário autorizou definir as premissas do cenário. O `.env`
local foi configurado com `ROI_TEMPO_MANUAL_MINUTOS=5` e `ROI_CUSTO_HORA_USD=5`.
São hipóteses ilustrativas, não tempos medidos nem remuneração real da equipe.
Os cinco minutos representam a consulta manual de câmaras, leituras, limites e
alertas que a interação pode reunir; o custo de US$ 5 por hora serve somente
como parâmetro de comparação. O benefício simulado é de US$ 0,4167 por resolução
técnica. São os padrões acadêmicos configuráveis, não parâmetros operacionais obrigatórios.
Para uso real, substituir por medição de tempo e custo aprovados pelo projeto.
Com custo estimado zero, o ROI percentual permanece indisponível: não é infinito.

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

## Demonstração reproduzível dos cálculos

Exemplo exclusivamente numérico, coberto por teste unitário: uma interação
aprovada com custo estimado de US$ 0,01. Premissas: 5 minutos, US$ 5/hora e uma
interação por usuário/semana. Benefício = 5/60 × 5 = US$ 0,416667; custo por
resolução = US$ 0,01; ROI = 4066,67%. Projeção de 100 usuários = US$ 1,00;
de 1000 usuários = US$ 10,00. Não são resultados medidos nem fatura dos provedores.

`premissas` expõe minutos, custo/hora, frequência e tamanho da amostra.
`roi.beneficio_estimado_usd` explicita o benefício. Sem turnos, resoluções ou
premissas válidas, o indicador aplicável é null com motivo. Custo zero não gera
ROI infinito. Chamadas com modelos sem preço conhecido invalidam o custo total,
projeções e ROI, sem atribuir gratuidade. `modelos_sem_preco` identifica essas
lacunas; `custo_parcial_conhecido_usd` é apenas a soma conhecida, não custo total.
Os preços existentes são referências de estimativa, não cobrança comprovada.
