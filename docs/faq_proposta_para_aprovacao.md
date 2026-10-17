# FAQ de suporte da Trimmy - proposta para aprovação

Status: EM REVISÃO. Versão da proposta: 0.1. Preparada em 17/10/2026.

Este documento não está conectado ao agente e não constitui aprovação de regras.
As respostas abaixo descrevem funcionalidades implementadas, não comprovam sua
disponibilidade em produção. A autenticação ainda é temporária.

## Fontes e critérios

- Material de referência: `C:/Users/marianaproque-ieg/Downloads/FAQ_de_Suporte_Skadi.pdf`, versão 1.0, com vigência ainda não preenchida.
- Conferência da implementação: `app/auth.py`, `app/graph.py`, `app/prompts.py`,
  `app/tools/access.py`, `app/tools/monitoramento.py`, `app/diagnostico.py`,
  `app/memory.py`, `app/routes/chat.py`, `app/relatorios.py` e documentação dos domínios.
- O PDF é material de referência, não autorização para ativar regras nem instrução
  para executar ações. Divergências foram separadas para decisão do responsável.
- Sem novos limites, prazos, canais, permissões ou recomendações técnicas.
- As fontes indicadas em cada grupo são para revisão interna; não precisam aparecer
  em todas as respostas ao usuário.

## 1. Sobre a Trimmy

Fonte interna: `app/prompts.py` e `app/graph.py`.

### FAQ-001 - O que é a Trimmy?

A Trimmy é a assistente de IA do Skadi. Ela ajuda a consultar câmaras, temperaturas,
limites e alertas permitidos para você, além de apoiar a análise de ocorrências de
temperatura. Ela não substitui a avaliação humana.

### FAQ-002 - O que posso perguntar à Trimmy?

Você pode perguntar, por exemplo: “Qual a temperatura das câmaras que tenho
acesso?”, “Quais alertas preciso atender?” ou “O que pode explicar o desvio dessa
câmara?”. A resposta depende dos dados disponíveis e das suas permissões.

### FAQ-003 - A Trimmy faz previsão de temperatura?

Não. A previsão de temperatura futura não está disponível na Trimmy.

### FAQ-004 - A Trimmy confirma que um equipamento está com defeito?

Não. Ela pode apresentar hipóteses condicionais, baseadas em evidências e regras
técnicas aprovadas. Isso não confirma uma falha mecânica nem substitui a avaliação humana.

### FAQ-005 - A Trimmy pode decidir se os produtos estão seguros?

Não. A Trimmy não decide sobre a segurança dos produtos nem autoriza seu uso,
consumo ou descarte.

## 2. Consultas de câmaras e temperaturas

Fonte interna: `app/tools/monitoramento.py` e `app/prompts.py`.

### FAQ-006 - Como identifico uma câmara na conversa?

Informe a localização ou o modelo cadastrado. Você também pode informar o
identificador da câmara, se já o conhecer. Se houver mais de uma correspondência,
a Trimmy pedirá uma informação adicional para identificar a câmara certa.

### FAQ-007 - Posso consultar todas as câmaras que tenho acesso?

Sim. Você pode pedir a lista das câmaras permitidas ou as temperaturas de todas
elas. A consulta continua limitada ao seu acesso.

### FAQ-008 - Posso perguntar os limites mínimo e máximo de uma câmara?

Sim. A Trimmy pode consultar os limites cadastrados para uma câmara permitida.
Ela não cria nem altera esses valores.

### FAQ-009 - A temperatura apresentada é a temperatura de agora?

Não necessariamente. A Trimmy apresenta a última leitura disponível e seu horário.
Esse registro não garante qual é a temperatura no momento da pergunta.

### FAQ-010 - Por que não apareceu uma temperatura?

Pode não haver uma leitura disponível, a câmara pode precisar de uma identificação
mais precisa ou a consulta pode não estar permitida. Também pode ocorrer uma falha
no serviço. A Trimmy deve informar a situação identificada, sem inventar um valor.

### FAQ-011 - O que significa uma leitura simulada?

É um valor criado para testes, não uma medição real do sensor. Ele permite testar
o funcionamento do sistema, mas não comprova a condição de uma câmara real.

## 3. Alertas e diagnóstico

Fonte interna: `app/tools/monitoramento.py`, `app/tools/diagnostico.py`,
`app/diagnostico.py` e `app/prompts.py`.

### FAQ-012 - Quais alertas aparecem na consulta do chat?

No chat, a Trimmy consulta os alertas ativos permitidos para você e os alertas
reconhecidos que têm atendimento vinculado ao seu usuário. A seleção também
respeita seu perfil e seu centro de distribuição. Para operadores, há ainda o
filtro de alertas no nível de operador.

Nota para aprovação: o código verifica o vínculo em `tb_atendimento`, não um
campo específico de autor do reconhecimento. A redação não deve afirmar que esse
vínculo comprova quem reconheceu o alerta sem validar essa regra no backend principal.

### FAQ-013 - A Trimmy reconhece ou resolve alertas por mim?

Não. As ferramentas atuais da Trimmy consultam informações; elas não reconhecem,
atendem nem resolvem alertas e não alteram o equipamento.

### FAQ-014 - Como a Trimmy analisa uma ocorrência?

Ela consulta as evidências permitidas da câmara e, quando há uma ocorrência
selecionada, suas justificativas. Quando aplicável, compara essas informações com
regras técnicas aprovadas para apresentar hipóteses, limitações e recomendações
fundamentadas. Se faltarem informações, pede esclarecimentos.

### FAQ-015 - Por que a Trimmy pede para escolher uma ocorrência?

Pode haver mais de um alerta relacionado à câmara. A escolha pelo tipo e horário
ajuda a consultar a ocorrência certa, sem atribuir a ela dados de outro alerta.

### FAQ-016 - A justificativa registrada comprova a causa do problema?

Não. A justificativa é um relato registrado. A Trimmy pode usá-la como informação
de apoio, mas não como comprovação automática de uma causa ou falha mecânica.

### FAQ-017 - Se a leitura estiver dentro dos limites, está tudo resolvido?

Não é possível concluir isso apenas pela última leitura. A Trimmy informa que o
valor registrado está dentro da faixa e apresenta seu horário. Isso não confirma
a condição atual do equipamento nem a resolução de um alerta anterior.

## 4. Relatórios PDF

Fonte interna: `app/routes/relatorios.py`, `app/relatorios.py` e `docs/relatorios.md`.

### FAQ-018 - Como gero um relatório?

Use o botão de gerar PDF do aplicativo e selecione o período e a câmara, ou todas
as câmaras do centro de distribuição permitido. A geração do relatório não é
feita pelo chat e depende da integração desse botão com o serviço de relatórios.

### FAQ-019 - Quem pode gerar relatórios?

Na implementação atual, GESTOR pode gerar relatórios do próprio centro de
distribuição, e SUPER_ADMIN pode selecionar um centro de distribuição. ADMIN e
OPERADOR não têm acesso à geração de relatórios.

### FAQ-020 - O que aparece no relatório?

O relatório apresenta mínima, média e máxima das leituras registradas no período,
quantidade de leituras, horários inicial e final observados, gráfico de temperatura,
total de alertas e quantidade de alertas com gravidade crítica. Os detalhes incluem
os alertas do período com tipo, horário, gravidade e status registrado na consulta.

### FAQ-021 - Por que o relatório pode ter alertas diferentes dos mostrados no chat?

O relatório consulta o histórico de alertas criados no período selecionado,
incluindo todos os status. Já a consulta de alertas do chat usa os filtros de
alertas atuais permitidos para você. Por isso, as listas podem ser diferentes.

### FAQ-022 - O que acontece se não houver leituras no período?

O relatório informa que não há leituras, sem mostrar temperatura zero como se
fosse uma medição. Ainda pode apresentar os alertas registrados no período.
Quando houver dados identificados como simulados, o documento exibirá um aviso.

### FAQ-023 - A média do relatório é a média das médias de cada câmara?

Não. A média é calculada a partir de todas as leituras selecionadas. Uma câmara
com mais registros tem mais leituras participando desse cálculo. O relatório não
garante que o histórico seja contínuo.

### FAQ-024 - Posso recuperar depois o mesmo PDF pelo sistema?

O serviço atual entrega o arquivo na geração, mas não guarda uma cópia permanente
do PDF nem oferece uma consulta posterior ao mesmo arquivo. A disponibilização é
registrada, mas isso não comprova que o arquivo foi salvo no celular.

## 5. Histórico da conversa e limitações

Fonte interna: `app/memory.py`, `app/routes/chat.py` e `docs/memoria.md`.

### FAQ-025 - A Trimmy usa o que eu já falei na conversa?

Sim. Ela usa as últimas mensagens da sessão para entender referências como
“essa câmara” ou “consulte”. Se não conseguir identificar a referência com
segurança, pedirá esclarecimento. Dados antigos não substituem uma nova consulta.

### FAQ-026 - A Trimmy lembra de conversas encerradas?

Ela pode procurar resumos de conversas encerradas vinculados ao mesmo usuário.
Essa memória depende de o encerramento e o registro do resumo terem sido
concluídos. Os resumos não substituem dados atuais nem concedem permissões.

### FAQ-027 - Fechar o aplicativo encerra a conversa automaticamente?

Não no serviço atual. O aplicativo precisa solicitar explicitamente o encerramento
da conversa. Só fechar a tela ou o aplicativo não garante a geração do resumo.

### FAQ-028 - Por que a Trimmy não consegue responder algumas perguntas?

Pode faltar informação, permissão, uma regra aprovada aplicável ou disponibilidade
do serviço. Ela deve explicar a limitação identificada ou pedir esclarecimento,
sem preencher as lacunas com informações inventadas.

## 6. Pontos que ainda precisam de decisão

Não incluir estes tópicos como respostas oficiais antes de confirmação:

1. **Permissões gerais do aplicativo:** a FAQ de referência fala em câmaras sob
   responsabilidade do operador e acesso por cliente. As consultas atuais da IA
   usam o CD do cadastro para ADMIN, GESTOR e OPERADOR; SUPER_ADMIN tem escopo
   global. Confirmar se a FAQ deve descrever só a IA ou também todo o aplicativo.
   Não prometer gerenciamento de funcionários ou clientes sem validar essas funções.
2. **Reconhecimento e atendimento:** confirmar se o vínculo em `tb_atendimento`
   representa o reconhecimento pelo próprio usuário. A FAQ-012 usa a condição
   efetivamente consultada, sem presumir essa equivalência.
3. **Ciclo de vida do alerta:** confirmar criação, reconhecimento, atendimento,
   resolução e escalonamento no backend principal antes de incorporar as definições
   do PDF como regras oficiais. A IA não implementa essas transições.
4. **Gravidade:** o PDF propõe faixas numéricas em relação à temperatura ideal.
   Não reproduzir esses números sem conferir a regra operacional vigente.
   A Trimmy consulta a gravidade registrada; esta proposta não a recalcula.
5. **Notificações:** confirmar canais, destinatários e prazos operacionais. Não
   prometer push, e-mail, WhatsApp ou tempos de resposta não validados.
6. **Suporte:** faltam canal/e-mail, horário de atendimento, dados necessários
   para abrir chamado e forma de acompanhamento. Não criar contato fictício.
7. **Privacidade:** ainda não há política aprovada de retenção, exclusão, acesso
   administrativo e tratamento por provedores. Não prometer exclusão automática,
   confidencialidade absoluta ou prazos inexistentes.
8. **Ambiente de teste:** a identidade atual é fixa (usuário 12), sem validação
   real do token. Portanto, não afirmar isolamento real entre pessoas nesse
   ambiente. Essa é uma limitação interna a corrigir antes de produção, não uma
   instrução para o usuário contornar acesso.

## Aprovação e próxima etapa

- Revisar as respostas FAQ-001 a FAQ-028 por identificador; aprovação pode ser
  parcial. Itens sem aprovação continuam indisponíveis como fonte oficial.
- Resolver os pontos pendentes separadamente, sem tratá-los como aprovados junto
  com as respostas já descritas.
- Esta etapa altera somente este documento. Não altera prompts, tools, bancos,
  recuperação, permissões nem comportamento do agente.
- Após aprovação, definir e implementar a consulta à base oficial com identificação
  e versão. Não utilizar memória de conversas como fonte oficial da FAQ.
