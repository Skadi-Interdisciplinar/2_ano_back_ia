# Arquitetura de Inteligência Artificial

A arquitetura de Inteligência Artificial do sistema é composta por um conjunto de agentes especializados, responsáveis por diferentes etapas do processo de monitoramento e gerenciamento dos frigoríficos. A divisão das responsabilidades permite que cada agente execute uma função específica, enquanto o **Agente Orquestrador** coordena o fluxo de informações entre eles.

A comunicação entre os agentes ocorre de acordo com a necessidade identificada a partir da solicitação do usuário. Dessa forma, os agentes podem atuar de maneira integrada para realizar atividades de monitoramento, diagnóstico, geração de relatórios e interação com o usuário.

## 1. Agente Orquestrador

O Agente Orquestrador é responsável pelo gerenciamento do fluxo de execução dos demais agentes. Sua principal função é receber uma solicitação ou ocorrência, determinar quais agentes devem participar do processamento e estabelecer a ordem em que serão acionados.

**Responsabilidades:**

* Interpretar a solicitação recebida;
* Identificar os agentes necessários para o processamento;
* Coordenar a comunicação entre os agentes;
* Organizar a sequência de execução das tarefas;
* Consolidar as informações retornadas pelos agentes.

**Entrada:** solicitação do usuário ou informações provenientes de outros agentes.

**Saída:** direcionamento das tarefas e consolidação das informações necessárias para a resposta.

**Tools** 

## 2. Agente de Monitoramento

O Agente de Monitoramento é responsável pelo acompanhamento das condições de temperatura dos frigoríficos. Para isso, realiza consultas à API responsável pelo fornecimento das leituras de temperatura e compara os valores obtidos com os limites configurados para cada equipamento.

Quando identifica uma temperatura fora dos parâmetros estabelecidos, o agente registra a ocorrência e encaminha as informações para o processamento dos demais agentes.

**Responsabilidades:**

* Consultar os dados de temperatura;
* Monitorar os frigoríficos em tempo real;
* Comparar as leituras com os limites configurados;
* Identificar temperaturas fora do padrão;
* Encaminhar ocorrências para o Agente Orquestrador.

**Entrada:** dados de temperatura provenientes da API e parâmetros configurados para os frigoríficos.

**Saída:** leituras processadas e identificação de possíveis ocorrências relacionadas à temperatura.


## 3. Agente de Diagnóstico

O Agente de Diagnóstico é responsável pela análise das ocorrências identificadas durante o monitoramento.
A partir dessas informações, realiza uma análise das possíveis causas associadas ao problema identificado.

Entre as possíveis causas analisadas estão falhas no compressor, abertura da porta, problemas no sensor de temperatura e excesso de carga no frigorífico.

**Responsabilidades:**

* Analisar ocorrências identificadas pelo monitoramento;
* Relacionar os dados disponíveis a possíveis causas;
* Sugerir hipóteses para a origem do problema;
* Encaminhar o diagnóstico para o Agente Orquestrador.

**Entrada:** dados de monitoramento e informações do frigorífico.

**Saída:** possíveis causas associadas à ocorrência identificada.

## 4. Agente de Relatórios

O Agente de Relatórios é responsável pela organização e consolidação das informações armazenadas pelo sistema. Seu objetivo é gerar relatórios e estatísticas que permitam acompanhar o comportamento dos frigoríficos e o histórico de ocorrências.

Os relatórios podem utilizar informações relacionadas às temperaturas registradas, alertas gerados, desempenho dos equipamentos e ocorrências anteriores.

**Responsabilidades:**

* Consultar informações históricas do sistema;
* Consolidar dados de temperatura e alertas;
* Gerar estatísticas sobre os frigoríficos;
* Organizar o histórico de ocorrências;
* Produzir informações para acompanhamento e análise.

**Entrada:** dados históricos, temperaturas, alertas e registros de ocorrências.

**Saída:** relatórios, estatísticas e informações consolidadas.

## 5. Agente Assistente

O Agente Assistente é responsável pela interação entre o sistema e o usuário. Sua função é interpretar solicitações realizadas em linguagem natural e, quando necessário, acionar o Agente Orquestrador para obter informações dos demais componentes da arquitetura.

Após o processamento, o agente apresenta os resultados de forma clara e objetiva, adaptando as informações técnicas para uma linguagem adequada ao usuário.

**Responsabilidades:**

* Receber solicitações em linguagem natural;
* Interpretar a intenção do usuário;
* Solicitar informações aos demais agentes quando necessário;
* Organizar os resultados obtidos;
* Apresentar as informações de forma clara e contextualizada.

**Entrada:** solicitação realizada pelo usuário.

**Saída:** resposta contextualizada com base nas informações obtidas pelo sistema.

## 6. Fluxo de Comunicação entre os Agentes

O fluxo de comunicação tem como elemento central o **Agente Orquestrador**, responsável por direcionar as solicitações e ocorrências para os agentes especializados.

Em uma consulta sobre temperatura fora do padrão, o roteador encaminha pedidos de leitura e alertas ao **Agente de Monitoramento**, ou pedidos de análise de causas ao **Agente de Diagnóstico**. O **Agente Orquestrador** apresenta o resultado ao usuário.

Quando o usuário solicita informações sobre o sistema, o **Agente Assistente** interpreta a solicitação e utiliza o orquestrador para consultar os agentes necessários. Caso sejam solicitadas informações históricas ou estatísticas, o **Agente de Relatórios** pode ser acionado para consolidar os dados.

Dessa forma, a arquitetura permite a especialização das tarefas, mantendo a coordenação centralizada do fluxo de informações e possibilitando que os resultados de diferentes agentes sejam combinados para atender às necessidades do sistema e do usuário.
