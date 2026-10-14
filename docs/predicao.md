# Predição de temperatura — Trimmy

## Entregue e ainda pendente

O agente possui uma tool `prever_temperatura`, saída estruturada por referência
e apresentação final feita pelo backend. O LLM não calcula nem fornece valores
de temperatura. Não há endpoint novo: `POST /chat` continua recebendo token e
mensagem. Resultados são persistidos apenas na conversa existente.

A tool usa `return_direct=True`: depois de identificar os argumentos e executar
a consulta, o agente encerra sem pedir ao LLM outra geração de JSON. O backend
exige uma mensagem da tool autorizada, valida `ResultadoPredicao`, a referência
da execução e a igualdade com o resultado interno. Não aceita texto livre,
referência inventada, temperatura alterada ou múltiplos resultados simultâneos.
Esclarecimentos seguem esse mesmo caminho; não há schema separado de perguntas.
O especialista exige `tool_choice=prever_temperatura` pelo middleware local:
mesmo perguntas de continuação precisam consultar a tool, sem substituir a
consulta por valores do histórico. O LLM continua identificando somente os
argumentos; a tool e o contexto interno continuam validando identidade e acesso.

Não há modelo real ativado nesta entrega. O treinamento precisa de histórico
contínuo após a alteração do worker, avaliação e aprovação humana. Os bancos
atuais são de teste; testes simulados não comprovam precisão operacional.

`SUPER_ADMIN` consulta globalmente. `ADMIN` e `GESTOR` ficam restritos ao CD
atual, reutilizando seleção de câmaras do monitoramento. `OPERADOR` recebe 403
antes de iniciar o especialista/modelo. Identidade e permissões não são argumentos
da tool. A autenticação mobile real continua pendente para produção.

## Coleta e preparação

O worker no repositório de banco passou a armazenar todas as leituras válidas
na tabela existente `tb_leitura_temperatura`, sem alterar triggers ou limites.
Ele registra em log o início da execução contínua; use o instante real da
primeira ativação como `--inicio-coleta`. O script não descobre automaticamente
que leituras antigas estavam faltando. A declaração administrativa desse marco
precisa ser verdadeira. Não houve implantação do worker nem migração executada.

Só treinar períodos posteriores ao marco. Informar a cadência real do produtor;
não inferir uma frequência com as três leituras antigas. Valores não finitos,
horários inválidos, duplicatas conflitantes e lacunas impedem treinamento ou
predição; não há interpolação ou preenchimento. Repetições idênticas no mesmo
horário são deduplicadas. Timestamps PostgreSQL sem fuso seguem a convenção
efetiva do worker: America/Sao_Paulo; artefatos usam horários com fuso.

Atualize dependências nos ambientes da IA e do worker. `tzdata` foi adicionado
para Windows, que não fornece a base IANA de fusos por padrão. O cálculo usa
OLS fechado com a biblioteca padrão: não foi adicionada biblioteca de ML pesada.

## Modelo AR(1) e avaliação

Para cada câmara/termômetro: ajustar `T(t+1) = intercepto + coeficiente * T(t)`
pelos mínimos quadrados ordinários com intercepto. Série constante produz a
previsão constante ajustada. Não há modelo compartilhado entre câmaras.

Separação temporal: primeiros 80% para ajuste, últimos 20% para avaliação.
Não se reajusta nos dados de avaliação. Para cada horizonte, comparar com repetir
a leitura da origem e calcular MAE/RMSE e número de casos. Origens de avaliação
nunca precedem o fim do ajuste; dados posteriores à origem não viram entradas.
Cada horizonte deve ser múltiplo da cadência e ter alvo observado no bloco de
avaliação. Sem pares suficientes para ajuste ou casos para todos os horizontes,
o comando explica a insuficiência e não grava um artefato.

As métricas não são probabilidade ou confiança. Não há precisão mínima inventada
nem ativação automática por superar a referência. A amostra, sua origem, o período
e as limitações devem ser avaliados pelo usuário antes da aprovação. O AR(1)
é uma estimativa experimental: não representa portas, carga térmica, degelo,
sazonalidade ou dinâmica física de um equipamento específico.

Referências: [modelo autorregressivo](https://otexts.com/fpp3/AR.html) e
[avaliação temporal](https://otexts.com/fpp3/tscv.html).

## Comandos administrativos locais

Execute na raiz da IA. Substitua os marcadores por parâmetros reais aprovados:

```text
python -m scripts.modelo_predicao treinar --usuario-id <ID_ADMINISTRATIVO> --camara-id <CAMARA> --inicio-coleta "<ISO_PRIMEIRA_ATIVACAO>" --inicio "<ISO_INICIO>" --fim "<ISO_FIM>" --cadencia-segundos <CADENCIA_REAL> --horizontes-minutos <HORIZONTES_A_AVALIAR>
```

O comando valida perfil e câmara no PostgreSQL e lê o histórico autorizado.
É operação administrativa local; `--usuario-id` não é autenticação da API e
não é passado ao LLM. Não exponha este comando como endpoint ou serviço remoto.
Ele imprime metadados e métricas; salva somente JSON local `EM_REVISAO` em
`modelos_predicao/camara_<ID>.pendente.json`, fora do Git.

Somente depois de aprovação humana da versão e das métricas:

```text
python -m scripts.modelo_predicao aprovar --usuario-id <ID_ADMINISTRATIVO> --camara-id <CAMARA> --modelo-id <UUID_DA_VERSAO_REVISADA> --confirmar-aprovacao
```

Esse comando verifica versão, perfil e vínculo do sensor novamente e publica
`camara_<ID>.json` com aprovação datada. Aprovação não é uma tool do LLM. Uma
nova versão pendente não substitui a ativa. Publicação é atômica, em arquivos
locais de acesso administrativo confiável; não usa pickle/joblib. A API relê o
artefato sem cache de aprovação. Para revogar, o administrador muda o status do
artefato ativo para `EM_REVISAO`, mantendo o JSON válido, e ele deixa de ser usado.

Não sobrescreva ou aprove versões sem conferir as métricas. Arquivos locais
precisam de backup/controle de acesso antes de produção; sua integridade depende
do ambiente administrativo, não de uma assinatura criptográfica implementada.

## Conversa e falhas

O usuário identifica uma câmara por ID explicitamente informado, modelo ou
localização e diz o horizonte em minutos. Falta ou ambiguidade gera esclarecimento,
sem ampliar a busca. Não há previsão de todas as câmaras nesta versão.

A tool usa apenas artefato aprovado da câmara/sensor atual e horizonte avaliado,
confere as duas últimas leituras posteriores ao início da coleta e calcula no
backend. Leitura anterior ao ajuste não pode ser usada com conhecimento futuro.
O horizonte é contado a partir da leitura, não de agora; ambos os horários
aparecem na resposta. Não foi criado limite de idade da leitura.

Comparação usa exclusivamente os limites cadastrados, inclusive os extremos.
Não informa gravidade prevista, probabilidade, sobrevivência, segurança de produto
ou diagnóstico mecânico. Memória serve para compreender "consulte" e respostas
em minutos, não como fonte do histórico térmico ou do modelo.

Modelo ausente/pendente, sensor diferente, horizonte não avaliado e série
insuficiente geram explicação no chat. Falhas PostgreSQL ou artefato inválido
são 503; acesso negado, 403; saída estruturada inválida ou referência inventada
pelo modelo, 502. A explicação final não pode ser reescrita tecnicamente por LLM.

## Verificação

As suites cobrem matemática, separação temporal, persistência JSON em diretórios
temporários, aprovação explícita, permissões, parâmetros SQL, contexto isolado,
referências, esclarecimentos e regressão da API. Testes com mocks não comprovam
conectividade real, funcionamento do produtor ou precisão em câmaras reais.
Não foram executados treinamento/aprovação reais, escritas nos bancos ou chamadas
de modelo para esta entrega. A coleta contínua e as triggers precisam de validação
integrada após implantação autorizada.

Verificação local em 13/10/2026: 375 testes da IA aprovados, quatro integrações
reais não executadas e 11 testes do worker aprovados. Os dois avisos da suíte
da IA são de depreciações de dependências. Ruff e `git diff --check` não apontaram
erros; avisos de conversão LF/CRLF do Git não alteram os comportamentos testados.

## Arquivos desta implementação

- `app/modelos_predicao.py`: matemática, avaliação e artefatos JSON.
- `app/predicao.py`: contexto, consulta interna, validação da resposta e apresentação.
- `app/tools/predicao.py`: única tool de predição e schema dos argumentos.
- `scripts/modelo_predicao.py`: treinamento e aprovação administrativos separados.
- `app/graph.py` e `app/prompts.py`: integração do especialista com o fluxo existente.
- `.gitignore` e `pyproject.toml`: artefatos locais ignorados e fuso no Windows.
- `tests/test_*predicao.py` e `tests/conftest.py`: testes numéricos, permissões,
  comandos administrativos e integração simulada.
- No repositório de banco, `databases/redis/worker.py`, `requirements.txt`,
  `README.md` e `tests/test_worker.py`: preservação de leituras e sua verificação.

## Simulação autorizada para teste

Em 14/10/2026 foi autorizado um lote sintético de dois dias para a câmara 3,
termômetro 3, com cadência de cinco minutos e limites cadastrados de 2 a 6 °C.
São 577 pontos, incluindo os extremos de 48 horas. Os cenários se repetem a cada
dia: oscilação normal entre 3 e 5 °C, subida de 4 a 8 °C e retorno, queda de 4 a
0 °C e retorno e picos pontuais. As transições são determinísticas; não há ruído,
medições reais ou causas mecânicas atribuídas.

`scripts/simular_predicao.py` é um comando administrativo local separado das
tools. Exige usuário, UUID do lote, fim do período com fuso, caminho do worker
existente e confirmação explícita de bancos de teste. Recusa cadastro divergente,
modelo ativo, outra versão pendente ou leituras de outro lote no período. IDs
`sim-trimmy-<lote>-<sequência>` identificam os registros no PostgreSQL; os eventos
Redis incluem origem, lote e cenário. O manifesto completo fica em
`simulacoes_predicao/<lote>.json`, ignorado no Git, permitindo repetir o mesmo
lote sem duplicar leituras ou trocar seu período.

A persistência reutiliza `PostgresRepository.persist_reading` do worker e mantém
as triggers. A gravação PostgreSQL é transacional; os eventos são publicados no
Redis em seguida. Não existe transação distribuída entre os bancos: caso Redis
falhe depois do commit, retomar o mesmo lote, sem apagar dados. Não inicia worker
permanente, consumer groups, push ou scheduler; triggers continuam podendo gerar
alertas e notificações no PostgreSQL. Reprocessamento posterior pelo worker usa
os mesmos IDs, sem reinserção de leituras.

O treinamento relê o lote do PostgreSQL e avalia o horizonte de 30 minutos, usado
na pergunta de teste. O JSON fica `EM_REVISAO` e contém `lote_simulacao`; não há
aprovação automática. Se aprovado posteriormente, a tool e a apresentação final
indicam expressamente que os dados e o modelo são simulados. O marco de início
desse lote representa medição sintética, não implantação de coleta real.

Esses cenários verificam código, não precisão operacional ou representatividade
de câmaras reais. O recorte cronológico de avaliação cobre apenas os cenários
presentes no fim do lote, não uma comprovação individual de todos os cenários.
Leituras faltantes/conflitantes continuam em testes unitários separados.
