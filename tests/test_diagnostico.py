import pytest
from app.diagnostico import (
    AnaliseDiagnostico,
    ContextoDiagnostico,
    PropostaDiagnostico,
    RelatoDiagnostico,
    SaidaDiagnosticoInvalida,
    apresentar_diagnostico,
    validar_analise,
)
from app.regras_diagnostico import carregar_regras


def test_apresenta_limite_quando_a_leitura_esta_dentro_da_faixa():
    analise = AnaliseDiagnostico(evidencias={
        "camara": {"modelo": "FM-400", "localizacao": "Câmara 03", "limite_minimo": "2.00", "limite_maximo": "6.00"},
        "leitura": {"temperatura": "4.00", "data_hora": "2026-10-14T09:04:00-03:00"},
        "comparacao": "dentro_faixa",
    })

    resposta = apresentar_diagnostico(analise)

    assert resposta.startswith("Claro!")
    assert "FM-400" in resposta
    assert "dentro da faixa" in resposta


def test_apresenta_limitacao_quando_nao_ha_regra_aplicavel():
    analise = AnaliseDiagnostico(limitacoes=["Não há regra aprovada recuperada para esta análise."])

    resposta = apresentar_diagnostico(analise)

    assert "Não há regra aprovada" in resposta


def test_nao_expoe_fontes_tecnicas_na_resposta_ao_usuario():
    regra = next(iter(carregar_regras().values()))
    analise = AnaliseDiagnostico(regras_explicacao=[regra])

    resposta = apresentar_diagnostico(analise)

    assert regra.titulo in resposta
    assert "Fonte:" not in resposta
    assert regra.fontes[0].url not in resposta


@pytest.mark.parametrize("regra_id", [f"DIAG-TEC-{numero:03}" for numero in range(1, 9)])
def test_aplica_cada_regra_somente_com_os_relatos_exigidos(regra_id):
    regra = carregar_regras()[regra_id]
    frases = {
        "porta_nao_fecha": "A porta não fecha.",
        "produtos_mais_quentes": "Os produtos entraram mais quentes.",
        "produtos_obstruem_ar": "Os produtos bloqueiam o ar.",
        "gelo_evaporador": "Há gelo no evaporador.",
        "gelo_obstrui_ar": "O gelo bloqueia o ar.",
        "condensador_obstruido_observacao_segura": "O técnico observou o condensador obstruído.",
        "sensor_posicao_exposta": "O sensor está exposto à porta.",
        "degelo_em_andamento": "O degelo está em andamento.",
        "degelo_encerrado": "O ciclo de degelo foi encerrado.",
        "gelo_permaneceu_apos_degelo": "O gelo permaneceu após o degelo.",
    }
    requisitos = [grupo[0] for grupo in regra.grupos_requisitos]
    contexto = ContextoDiagnostico(usuario_id=12, regras={regra.id: regra})
    contexto.evidencias["consulta-1"] = {
        "status": "ok", "camara": {"limite_minimo": "2", "limite_maximo": "6"},
        "leitura": {"temperatura": "8", "data_hora": "2026-10-29T10:00:00-03:00"},
    }
    contexto.fontes["mensagem:0"] = {"texto": " ".join(frases[r] for r in requisitos)}
    proposta = PropostaDiagnostico(evidencia_ref="consulta-1", hipoteses=[regra.id], relatos=[
        RelatoDiagnostico(origem_ref="mensagem:0", requisito=r, trecho=frases[r],
                         situacao="afirmado", vinculo_confirmado=True, atualidade_confirmada=True)
        for r in requisitos
    ])

    analise = validar_analise(proposta, contexto)
    proposta.relatos = []
    sem_relatos = validar_analise(proposta, contexto)

    assert [h.regra_id for h in analise.hipoteses] == [regra.id]
    assert analise.hipoteses[0].recomendacao == regra.recomendacao
    assert sem_relatos.hipoteses == []
    assert sem_relatos.perguntas == [regra.pergunta]


@pytest.mark.parametrize("temperatura", ["NaN", "Infinity", "erro", None])
def test_leitura_invalida_nao_e_apresentada_como_temperatura(temperatura):
    contexto = ContextoDiagnostico(usuario_id=12)
    contexto.evidencias["consulta-1"] = {
        "status": "ok", "camara": {"modelo": "FM-400", "localizacao": "Câmara 03",
                                    "limite_minimo": "2", "limite_maximo": "6"},
        "leitura": {"temperatura": temperatura, "data_hora": "2026-10-29T10:00:00-03:00"},
    }

    analise = validar_analise(PropostaDiagnostico(evidencia_ref="consulta-1"), contexto)
    resposta = apresentar_diagnostico(analise)

    assert analise.hipoteses == []
    assert analise.evidencias["comparacao"] is None
    assert "última leitura disponível é de" not in resposta


def test_rejeita_evidencia_inventada_pelo_modelo():
    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(evidencia_ref="inventada"), ContextoDiagnostico(12))
