# FAQ de suporte do Skadi

Versão: 1.0. Atualizada em 19/10/2026.

Respostas sobre o aplicativo Skadi e sua assistente Trimmy.

## Sobre a Trimmy

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

## Consultas de câmaras

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

## Alertas e diagnóstico na Trimmy

### FAQ-012 - Quais alertas aparecem na consulta do chat?

No chat, a Trimmy consulta os alertas ativos permitidos para você e os alertas
reconhecidos por você, identificados pelo atendimento vinculado ao seu usuário.
A seleção também respeita seu perfil e seu centro de distribuição. Para operadores,
há ainda o filtro de alertas no nível de operador.

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
Se você pedir o último alerta, a Trimmy seleciona o mais recente entre os que pode
consultar. Se houver empate no horário, pedirá que você escolha a ocorrência.

## Relatórios

### FAQ-018 - Como gero um relatório?

Na área de relatórios, selecione o período e a câmara, ou todas as câmaras do
centro de distribuição permitido, e use o botão Baixar PDF. A geração não é
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

### FAQ-022 - O que acontece se não houver leituras no período?

O relatório informa que não há leituras, sem mostrar temperatura zero como se
fosse uma medição. Ainda pode apresentar os alertas registrados no período.
O relatório não classifica automaticamente a origem dos registros como simulada
ou real.

### FAQ-023 - A média do relatório é a média das médias de cada câmara?

Não. A média é calculada a partir de todas as leituras selecionadas. Uma câmara
com mais registros tem mais leituras participando desse cálculo. O relatório não
garante que o histórico seja contínuo.

### FAQ-024 - Posso recuperar depois o mesmo PDF pelo sistema?

O serviço atual entrega o arquivo na geração, mas não guarda uma cópia permanente
do PDF nem oferece uma consulta posterior ao mesmo arquivo. A disponibilização é
registrada, mas isso não comprova que o arquivo foi salvo no celular.

## Disponibilidade das respostas

### FAQ-028 - Por que a Trimmy não consegue responder algumas perguntas?

Pode faltar informação, permissão, uma regra aprovada aplicável ou disponibilidade
do serviço. Ela deve explicar a limitação identificada ou pedir esclarecimento,
sem preencher as lacunas com informações inventadas.

## Suporte, perfil e saída da conta

### FAQ-029 - Como abro um chamado de suporte?

No Perfil, toque em Fale conosco para acessar Abrir chamado. Selecione o tipo
do chamado, descreva o problema e toque em Enviar.

### FAQ-030 - O que devo preencher no chamado?

A tela apresenta os campos Tipo do chamado e Descrição. Selecione o tipo
disponível que corresponde ao problema e explique o que aconteceu.

### FAQ-031 - Qual é o e-mail de suporte do Skadi?

O e-mail de suporte é skadi.enterprise@gmail.com.

### FAQ-032 - Qual é o horário de atendimento do suporte?

O horário informado para atendimento é das 9h às 17h.

### FAQ-033 - Como saio da minha conta?

No Perfil, toque em Sair da conta. Na confirmação, toque em Confirmar para sair
ou em Cancelar para permanecer na conta.

## Alertas, notificações e perfis do aplicativo

### FAQ-034 - Quais perfis existem no Skadi?

Os perfis são SUPER_ADMIN, ADMIN, GESTOR e OPERADOR. As funcionalidades e os dados
disponíveis dependem das permissões do usuário.

### FAQ-035 - Qual é a diferença entre ocorrência e alerta?

Uma ocorrência de temperatura é uma leitura fora dos limites configurados para
a câmara. O alerta é o registro gerado pelo sistema para sinalizar essa situação.
Isso não significa que cada nova leitura fora da faixa crie outro alerta enquanto
já houver um aberto para a mesma câmara.

### FAQ-036 - Reconhecer um alerta significa que ele foi resolvido?

Não. Reconhecer registra que um usuário tomou ciência da ocorrência e assumiu
o atendimento. O reconhecimento não resolve o alerta nem comprova que a
temperatura voltou aos limites.

### FAQ-037 - O que é necessário para resolver um alerta?

No fluxo conferido, o atendimento deve estar em andamento e receber uma
justificativa. O sistema verifica se a temperatura está dentro dos limites
cadastrados antes de registrar a resolução. Apenas reconhecer o alerta ou
registrar uma justificativa não comprova sua resolução.

### FAQ-038 - O que é o escalonamento de um alerta?

É a passagem da responsabilidade do alerta para outro nível de acesso conforme
as regras e os prazos do sistema. A hierarquia prevista é OPERADOR, GESTOR e ADMIN.
A Trimmy não altera o nível nem define um prazo por conta própria.

### FAQ-039 - Como recebo notificações de alerta?

O canal definido para as notificações é push no aplicativo. Elas são destinadas
aos funcionários do centro de distribuição que estão no nível de acesso
responsável pelo alerta naquele momento, conforme o escalonamento.

## Gravidade

### FAQ-040 - Como a gravidade de um alerta é calculada?

O PostgreSQL determina a gravidade do alerta conforme a regra implementada no
banco. A Trimmy apresenta a gravidade registrada, sem recalculá-la ou definir
outros limites.
