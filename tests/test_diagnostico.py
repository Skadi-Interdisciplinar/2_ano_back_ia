from app.diagnostico import AnaliseDiagnostico, apresentar_diagnostico


def test_apresenta_limite_quando_a_leitura_esta_dentro_da_faixa():
    analise = AnaliseDiagnostico(evidencias={
        "camara": {"modelo": "FM-400", "localizacao": "Câmara 03", "limite_minimo": "2.00", "limite_maximo": "6.00"},
        "leitura": {"temperatura": "4.00", "data_hora": "2026-10-14T09:04:00-03:00"},
        "comparacao": "dentro_faixa",
    })

    resposta = apresentar_diagnostico(analise)

    assert "FM-400" in resposta
    assert "dentro da faixa" in resposta


def test_apresenta_limitacao_quando_nao_ha_regra_aplicavel():
    analise = AnaliseDiagnostico(limitacoes=["Não há regra aprovada recuperada para esta análise."])

    resposta = apresentar_diagnostico(analise)

    assert "Não há regra aprovada" in resposta
