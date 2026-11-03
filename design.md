# Design do relatório de monitoramento Skadi

## Objetivo e referência

Este documento define a apresentação do PDF gerado por `POST /relatorios/pdf`.
A referência visual é a captura enviada pelo usuário em 16/10/2026:
`codex-clipboard-46763afa-f3b5-4151-9778-1ec79e33935b.png`.

O resultado deve seguir o design da imagem: cabeçalho azul-escuro, faixas
azul-claras arredondadas, cartões brancos, indicadores de temperatura em azul,
dois cartões rosa de ocorrências e um gráfico dentro de um cartão branco.
Não usar o layout atual de relatório predominantemente textual como referência.

Os números, nomes e datas da captura são ilustrativos. Todo conteúdo deve vir
do resultado autorizado já calculado pelo backend, conforme `docs/relatorios.md`.
Este documento não muda permissões, filtros, fórmulas, tabelas ou contrato HTTP.
O layout foi aplicado ao gerador em 17/10/2026. O logotipo permanece textual
enquanto não houver um arquivo oficial fornecido para uso.

## Formato e identidade visual

- PDF A4 vertical, com fundo branco. A captura é referência de composição,
  não uma imagem a ser ampliada e colada na página.
- Elementos vetoriais e texto selecionável; não rasterizar o documento inteiro.
- Área útil com margens laterais regulares, aproximadamente 36 a 40 pt.
- Alinhar títulos, faixas e cartões à mesma grade vertical.
- Usar espaço em branco entre os blocos, sem transformar todo espaço disponível
  em cartões maiores. Não reduzir fontes para forçar conteúdo em uma página.
- Cantos arredondados e sombra discreta nos cartões; evitar bordas pesadas.

### Paleta de implementação

As cores abaixo são aproximações da captura, não tokens extraídos do Figma.

| Uso | Cor proposta |
| --- | --- |
| Cabeçalho e textos institucionais | `#102F4C` |
| Faixas e cartões de temperatura | `#ADD9FA` |
| Cartões de alertas e ocorrências críticas | `#FFB3BE` |
| Destaque da temperatura mínima | `#2795F5` |
| Destaque da temperatura máxima | `#FA4052` |
| Texto principal | `#161616` |
| Texto secundário | `#646464` |
| Separadores | `#DADADA` |
| Cartões e página | `#FFFFFF` |

O rosa é parte da apresentação dos indicadores, não uma nova classificação de
gravidade. A cor da máxima também não significa, sozinha, temperatura irregular.

### Tipografia

Usar uma família sem serifa. Enquanto não houver fonte oficial fornecida,
utilizar Helvetica/Helvetica-Bold, já disponíveis no gerador atual.

- Título do documento: aproximadamente 16 a 18 pt, branco.
- Títulos de seção e nome do CD: 11 a 12 pt.
- Valores de temperatura: 20 a 24 pt.
- Quantidades de alertas: 28 a 32 pt.
- Conteúdo e notas: 9 a 11 pt; não esconder ressalvas em texto ilegível.
- Valores com duas casas decimais e vírgula na apresentação, por exemplo
  `-2,00 °C`. Contagens são inteiras. Não alterar a precisão dos cálculos.

## Composição da primeira página

### 1. Cabeçalho institucional

Faixa azul-escura no topo, com título branco em duas linhas:

> RELATÓRIO DE MONITORAMENTO
> SKADI

Apresentar abaixo o período no formato `DD/MM/AAAA - DD/MM/AAAA`.
Reproduzir o recorte diagonal branco na parte inferior esquerda do cabeçalho,
sem encobrir o título, o período ou a área de marca.

A imagem usa a marca do lobo do Skadi. Inserir somente um arquivo oficial
fornecido e autorizado, com proporção preservada e boa resolução ou vetor.
Não redesenhar o lobo, criar uma marca nova ou recortar a captura para obter
o logo. Enquanto esse arquivo não existir, usar identificação textual SKADI,
sem mostrar um ícone genérico ou um espaço vazio que pareça erro.

### 2. Resumo executivo do período

Faixa azul-clara arredondada com o título `Resumo executivo do período`.
Abaixo, um cartão branco arredondado contendo:

- Nome do centro de distribuição.
- Subtítulo `Relatório de temperatura - Todas as câmaras`, ou identificação
  da câmara selecionada por modelo e localização.
- Separador horizontal fino.
- Três cartões azul-claros de mesma largura, em uma linha: mínima, média, máxima.
- Valor em destaque e legenda imediatamente abaixo: `Mínima`, `Média`, `Máxima`.

Não mostrar IDs internos de usuários, CDs, câmaras ou termômetros.
Nomes e localizações longos devem quebrar linha e aumentar a altura do bloco,
sem invadir os valores ou ser cortados.

Em “Todas”, os três indicadores são consolidados sobre as leituras selecionadas,
como já aprovado. Não substituir por uma média das médias das câmaras.
Sem leituras, manter os lugares dos indicadores com `—` e apresentar claramente
`Sem leituras no período`. Não preencher com `0,00 °C`.

### 3. Indicadores de ocorrências

Dois blocos lado a lado, com a mesma largura e alinhamento:

| Faixa azul-clara | Cartão rosa |
| --- | --- |
| Alertas no período | Quantidade e legenda `Alertas` |
| Ocorrências críticas | Quantidade e legenda `Ocorrências críticas` |

Cada quantidade fica centralizada, grande e em negrito. A legenda pode usar
duas linhas. Usar os totais retornados pelo backend; nunca fixar os exemplos
`14` ou `3` da captura.

Zero alertas deve aparecer como `0`, sem criar uma ocorrência de exemplo.
“Críticas” continua significando a gravidade cadastrada, sem regra visual nova.

### 4. Gráfico de comportamento

Faixa azul-clara com o título `Gráfico para análise de comportamento`.
Abaixo, um cartão branco arredondado contendo:

1. Linha de três indicadores, repetindo os mesmos valores do resumo:
   mínima em azul, média em preto e máxima em vermelho, com suas legendas.
2. Gráfico cronológico das temperaturas registradas, com unidade °C e horários.
3. Legenda das séries quando houver mais de uma câmara.

A legenda inclui somente câmaras que possuem leituras no período. As demais
não recebem linha ou cor de série; a primeira página informa quantas estão sem
leituras, e os detalhes identificam cada uma como `Sem leituras no período`.

Essa repetição de valores é intencional, conforme a imagem. Reutilizar os
indicadores calculados; não realizar uma segunda consulta ou outro cálculo.

Para uma câmara, usar linha azul com preenchimento azul-claro discreto, como na
referência. O preenchimento é decorativo, não intervalo de confiança nem área
de segurança. Para várias câmaras, manter uma série por câmara, com cores e
legenda legíveis, sem sobrepor preenchimentos que ocultem as demais séries.
Não transformar câmaras diferentes em uma única curva consolidada.

Mostrar o eixo completo das temperaturas observadas, incluindo valores
negativos. Não cortar mínimos/máximos para reproduzir a escala do exemplo.
Não inserir curvas suaves, previsões ou valores entre registros. Linhas apenas
conectam pontos observados e não comprovam continuidade da coleta.

Uma leitura isolada deve aparecer como ponto, sem curva inventada. Sem leituras,
substituir a área do gráfico por `Sem leituras no período`, sem desenhar exemplo.

## Informações complementares e páginas seguintes

A primeira página prioriza o resumo visual da captura, mas não pode esconder
informações necessárias para interpretar os dados:

- Quantidade de leituras, primeiro e último horário observado e data de geração.
- Aviso de que o relatório representa os registros disponíveis, não garantia
  de coleta contínua ou condição atual.
- Não há classificação ou aviso automático de dados simulados. Os avisos sobre
  registros disponíveis e ausência de garantia de condição atual permanecem.
- Para seleção de várias câmaras, identificação legível das séries; uma relação
  extensa de câmaras pode continuar em página complementar.

Usar um bloco compacto de notas, com texto legível. Informações extensas seguem
nas páginas posteriores, sem retirar avisos essenciais da primeira página.

A lista detalhada de ocorrências continua nas páginas seguintes, com câmara,
tipo, horário, gravidade e status. Não remover essa lista para imitar o exemplo
de uma página. Repetir o cabeçalho da tabela a cada página e manter todos os
registros, sem corte silencioso. Não inventar temperatura associada ao alerta.

Manter a ressalva de que status e gravidade são os registrados na consulta,
não uma reconstrução do seu estado no passado.

Se nem o resumo couber com legibilidade, permitir outra página; não omitir
conteúdo, reduzir fontes excessivamente ou comprimir o gráfico até ficar ilegível.

## Rodapé

- Separador horizontal fino.
- À esquerda: `SKADI - AAAA`, usando o ano de geração, não um ano fixo.
- À direita: `Página N de M`, com o total real de páginas do documento.
- Repetir em todas as páginas, fora da área de texto, gráfico e tabela.

## Implementação e validação

Aplicar este design no módulo `app/pdf_relatorio.py`, preservando a separação
de consultas e cálculos em `app/relatorios.py`. Não criar endpoint, agente,
tool, banco ou consulta adicional apenas para reproduzir o layout.

Na implementação, atualizar os testes de apresentação e renderizar exemplos
com uma câmara, várias câmaras, ausência de leituras e múltiplas páginas.
Conferir visualmente todas as páginas, além de extrair o texto do PDF para
verificar dados e paginação. Validar especialmente:

- Proximidade visual da referência: cabeçalho, faixas, cartões e hierarquia.
- Ausência de sobreposição, texto cortado, glifos inválidos ou tabelas truncadas.
- Igualdade entre indicadores do resumo e os repetidos sobre o gráfico.
- Preservação dos filtros, dos valores calculados e das ressalvas.
- Ausência de classificação automática de simulação e de números ilustrativos fixos.
- Paginação correta, inclusive total de páginas e tabelas de continuação.
- Nenhuma alteração em autorização, auditoria, hash ou contrato de download.
