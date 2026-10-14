# Revisão do modelo simulado — câmara 3

## Execução autorizada em 14/10/2026

- Lote: `9b5f7e56-0cce-40a9-8e66-7091d22e9a49`.
- Câmara/termômetro: 3/3; limites conferidos no banco: 2–6 °C.
- Período sintético: 12/10/2026 09:04 até 14/10/2026 09:04, America/Sao_Paulo.
- Cadência: cinco minutos; 577 leituras incluindo os extremos.
- Cenários: normal oscilante (3–5 °C), subida e recuperação (4–8–4 °C),
  queda e recuperação (4–0–4 °C), picos pontuais (0 e 8 °C).
- 577 leituras gravadas no PostgreSQL. As triggers vincularam 144 leituras
  a alertas. Nenhuma regra de alerta ou trigger foi alterada.
- Conferência no banco: 433 leituras dentro da faixa, nenhuma com alerta;
  144 fora da faixa, todas com alerta. Redis conferido: 577 eventos do lote.
- Não houve implantação de produtor contínuo, scheduler ou serviço de push.
  Eventos Redis foram publicados com os mesmos IDs da persistência, origem
  `SIMULADO`, UUID do lote e cenário.

## Modelo em revisão

Versão: `4116738e-dfe2-49e8-8e0f-492db177ea77`. Artefato local:
`modelos_predicao/camara_3.pendente.json`. Não existe ativação automática.
O manifesto está em `simulacoes_predicao/9b5f7e56-0cce-40a9-8e66-7091d22e9a49.json`.
Esses dois diretórios não são versionados no Git.

Treinamento cronológico: 461 leituras; avaliação posterior: 116 leituras.
Horizonte avaliado: 30 minutos, com 111 casos válidos.

| Métrica (°C) | AR(1) | Repetir última temperatura |
| --- | ---: | ---: |
| MAE | 0,3123 | 0,3756 |
| RMSE | 0,7773 | 0,8507 |

O modelo teve erros menores que a referência neste recorte sintético. Isso não
significa precisão garantida, um erro máximo ou um percentual de confiança.
O recorte final contém apenas parte dos cenários: as métricas agregadas não
validam cada cenário individualmente. A série foi desenhada para testes, não
medida por sensores. Não transferir esta aprovação experimental a câmaras reais
ou a outras faixas de operação.

Aprovação posterior deve referenciar explicitamente essa versão, apenas para
teste. Até lá, `POST /chat` continua informando ausência de modelo aprovado.
Após eventual aprovação, a previsão incluirá aviso de dados/modelo simulados.
O monitoramento também preserva a marcação `origem_leitura=SIMULADO` dos eventos.

## Código alterado nesta etapa

- `scripts/simular_predicao.py`: geração, manifesto, gravação pela implementação
  existente do worker, publicação Redis e treinamento em revisão.
- `app/modelos_predicao.py`: UUID de origem sintética opcional no artefato.
- `app/tools/predicao.py` e `app/predicao.py`: preservação da origem e aviso final.
- `app/tools/monitoramento.py` e `app/prompts.py`: identificação das leituras de
  teste, sem alterar autorização, limites ou regras.
- `.gitignore`: manifestos sintéticos fora do Git.
- `tests/test_simular_predicao.py`: cadência, cenários, treinamento e avisos.
- `docs/predicao.md`: procedimento e limitações.

Nada foi removido dos bancos. Alertas gerados são efeitos do teste autorizado;
se necessário, sua limpeza deverá ser solicitada e delimitada separadamente.

Verificação final: 379 testes unitários/regressões aprovados, quatro integrações
da suíte não executadas, dois avisos de depreciação de dependências. Ruff passou.
As conferências PostgreSQL/Redis acima foram reais, com dados sintéticos; não
houve teste ponta a ponta com LLM nem aprovação/ativação do modelo.
