from datetime import UTC
from unittest.mock import Mock

import pytest
from app import juiz
from app.erros import SaidaModeloInvalida, ServicoIndisponivel
from pydantic import ValidationError


def _veredito(nota: int) -> juiz.Veredito:
    return juiz.Veredito(criterios=[
        juiz.AvaliacaoCriterio(
            criterio=criterio,
            aplicavel=True,
            nota=nota,
            justificativa="Conforme a fonte.",
            referencias=["evidencias"],
        )
        for criterio in juiz.CRITERIOS
    ])


def test_aprova_quando_todos_os_criterios_criticos_tem_nota_quatro():
    veredito = _veredito(4)

    assert veredito.aprovado is True


def test_reprova_quando_fidelidade_tem_nota_baixa():
    veredito = _veredito(5)
    veredito.criterios[0].nota = 2

    assert veredito.aprovado is False


def test_devolve_recusa_quando_o_juiz_reprova_a_candidata(monkeypatch):
    monkeypatch.setattr(juiz, "avaliar", Mock(return_value=_veredito(1)))

    resposta = juiz.julgar_chat({"pergunta_original": "Pergunta", "resposta": "Candidata"})

    assert resposta == juiz.RECUSA


def test_devolve_candidata_quando_o_juiz_aprova(monkeypatch):
    monkeypatch.setattr(juiz, "avaliar", Mock(return_value=_veredito(5)))

    resposta = juiz.julgar_chat({"pergunta_original": "Pergunta", "resposta": "Candidata"})

    assert resposta == "Candidata"


def test_juiz_recebe_apenas_evidencias_do_turno_atual(monkeypatch):
    avaliar = Mock(return_value=_veredito(5))
    monkeypatch.setattr(juiz, "avaliar", avaliar)

    juiz.julgar_chat({
        "pergunta_original": "Consulte novamente.",
        "resposta": "Leitura consultada.",
        "evidencias_juiz": [{"tipo": "resultado_consulta", "resultado": "4.00"}],
        "historico": [{"conteudo": "Não deve ser enviado"}],
        "memoria_recuperada": ["Também não deve ser enviada"],
    })

    fontes = avaliar.call_args.args[0]
    assert fontes["evidencias"] == [{"tipo": "resultado_consulta", "resultado": "4.00"}]
    assert "historico_nao_verificado" not in fontes
    assert "memoria_nao_verificada" not in fontes


def test_julga_pdf_com_extracao_e_renderizacao_local(monkeypatch):
    from datetime import datetime
    from io import BytesIO

    from reportlab.pdfgen import canvas

    arquivo = BytesIO()
    documento = canvas.Canvas(arquivo)
    documento.drawString(72, 720, "Relatório de teste")
    documento.showPage()
    documento.drawString(72, 720, "Alerta em 14/10/2026 06:04:00: CRITICA")
    documento.save()

    def avaliar(fontes, *, visual=False, imagem=None):
        criterios = ("visual",) if visual else juiz.CRITERIOS
        assert imagem is not None if visual else imagem is None
        return juiz.Veredito(criterios=[
            juiz.AvaliacaoCriterio(
                criterio=criterio,
                aplicavel=True,
                nota=5,
                justificativa="Conforme o conteúdo fornecido.",
                referencias=["design"],
            )
            for criterio in criterios
        ])

    mock_avaliar = Mock(side_effect=avaliar)
    monkeypatch.setattr(juiz, "avaliar", mock_avaliar)

    alerta = (1, 3, "temperatura", datetime(2026, 10, 14, 6, 4, tzinfo=UTC), "CRITICA", "ATIVO")
    dados = {"cd_nome": "Teste", "leituras": [(1, "4.00")], "alertas": [alerta], "total_alertas": 1}

    assert juiz.julgar_pdf(dados, arquivo.getvalue()) is True
    assert mock_avaliar.call_count == 4
    fontes_primeira_pagina = mock_avaliar.call_args_list[0].args[0]
    fontes_segunda_pagina = mock_avaliar.call_args_list[2].args[0]
    assert "leituras" not in fontes_primeira_pagina["dados_snapshot"]
    assert fontes_primeira_pagina["dados_snapshot"]["total_alertas"] == 1
    assert fontes_primeira_pagina["dados_snapshot"]["alertas_presentes_na_pagina"] == []
    assert fontes_segunda_pagina["dados_snapshot"]["alertas_presentes_na_pagina"] == [alerta]
    assert dados["alertas"] == [alerta]


def test_reprova_pdf_quando_alerta_do_snapshot_nao_aparece(monkeypatch):
    from datetime import datetime
    from io import BytesIO

    from reportlab.pdfgen import canvas

    arquivo = BytesIO()
    documento = canvas.Canvas(arquivo)
    documento.drawString(72, 720, "Relatório sem o alerta obrigatório")
    documento.save()
    avaliar = Mock()
    monkeypatch.setattr(juiz, "avaliar", avaliar)
    alerta = (1, 3, "temperatura", datetime(2026, 10, 14, 6, 4, tzinfo=UTC), "CRITICA", "ATIVO")

    assert juiz.julgar_pdf({"alertas": [alerta]}, arquivo.getvalue()) is False
    avaliar.assert_not_called()


@pytest.mark.parametrize("nota", [0, 6, True, "5"])
def test_rejeita_notas_invalidas(nota):
    with pytest.raises(ValidationError):
        juiz.AvaliacaoCriterio(criterio="fidelidade", aplicavel=True, nota=nota,
                              justificativa="Teste", referencias=["evidencias"])


def test_estilo_baixo_nao_compensa_nem_reprova_criterios_criticos():
    veredito = _veredito(5)
    veredito.criterios[-1].nota = 1

    assert veredito.aprovado is True


@pytest.mark.parametrize("falha", ["criterio_ausente", "criterio_repetido", "referencia_inventada"])
def test_veredito_invalido_nunca_aprova_resposta(monkeypatch, falha):
    bruto = _veredito(5).model_dump()
    if falha == "criterio_ausente":
        bruto["criterios"].pop()
    elif falha == "criterio_repetido":
        bruto["criterios"].append(bruto["criterios"][0])
    else:
        bruto["criterios"][0]["referencias"] = ["inventada"]
    modelo = Mock()
    modelo.with_structured_output.return_value.invoke.return_value = bruto
    monkeypatch.setattr(juiz, "_modelo_juiz", Mock(return_value=modelo))

    with pytest.raises(SaidaModeloInvalida):
        juiz.avaliar({"evidencias": "Dados autorizados."})


def test_falha_do_juiz_devolve_mensagem_de_indisponibilidade(monkeypatch):
    monkeypatch.setattr(juiz, "avaliar", Mock(side_effect=ServicoIndisponivel()))

    resposta = juiz.julgar_chat({"pergunta_original": "Pergunta", "resposta": "Candidata"})

    assert resposta == juiz.INDISPONIVEL


def test_aguarda_liberacao_informada_pelo_groq_sem_repetir_chamada(monkeypatch):
    monkeypatch.setattr(juiz, "perf_counter", Mock(return_value=100.0))
    monkeypatch.setattr(juiz, "_proxima_chamada_groq", 0.0)
    dormir = Mock()
    monkeypatch.setattr(juiz, "sleep", dormir)
    modelo = Mock()
    modelo.invoke.return_value = "veredito"
    juiz._registrar_cota_groq(Mock(headers={"x-ratelimit-reset-tokens": "2.8s"}))

    resposta = juiz._chamar_juiz(modelo, [], visual=False)

    assert resposta == "veredito"
    assert dormir.call_args.args[0] == pytest.approx(2.8)
    modelo.invoke.assert_called_once_with([])


def test_cota_com_espera_excessiva_nao_prende_a_requisicao(monkeypatch):
    monkeypatch.setattr(juiz, "perf_counter", Mock(return_value=100.0))
    monkeypatch.setattr(juiz, "_proxima_chamada_groq", 200.0)
    dormir = Mock()
    monkeypatch.setattr(juiz, "sleep", dormir)
    modelo = Mock()

    with pytest.raises(ServicoIndisponivel):
        juiz._chamar_juiz(modelo, [], visual=False)

    dormir.assert_not_called()
    modelo.invoke.assert_not_called()


def test_avaliacao_visual_nao_aguarda_cota_do_outro_provedor(monkeypatch):
    monkeypatch.setattr(juiz, "_proxima_chamada_groq", float("inf"))
    dormir = Mock()
    monkeypatch.setattr(juiz, "sleep", dormir)
    modelo = Mock()

    juiz._chamar_juiz(modelo, [], visual=True)

    dormir.assert_not_called()
    modelo.invoke.assert_called_once_with([])


@pytest.mark.parametrize("reset,segundos", [("1m2.5s", 62.5), ("500ms", 0.5), ("inválido", 0.0)])
def test_interpreta_cota_sem_inventar_tempo_de_espera(monkeypatch, reset, segundos):
    monkeypatch.setattr(juiz, "perf_counter", Mock(return_value=100.0))
    monkeypatch.setattr(juiz, "_proxima_chamada_groq", 100.0)

    juiz._registrar_cota_groq(Mock(headers={"x-ratelimit-reset-tokens": reset}))

    assert juiz._proxima_chamada_groq == 100.0 + segundos


def test_juiz_avalia_a_pagina_como_candidata_sem_exigir_resposta_de_chat(monkeypatch):
    modelo = Mock()
    bruto = _veredito(5).model_dump()
    for criterio in bruto["criterios"]:
        criterio["referencias"] = ["pagina:1"]
    modelo.with_structured_output.return_value.invoke.return_value = bruto
    monkeypatch.setattr(juiz, "_modelo_juiz", Mock(return_value=modelo))
    monkeypatch.setattr(juiz, "_proxima_chamada_groq", 0.0)

    veredito = juiz.avaliar({"pagina:1": "Relatório", "paginacao": {"pagina": 1, "total": 2}})

    mensagem = modelo.with_structured_output.return_value.invoke.call_args.args[0][0].content
    assert "Modo relatório PDF" in mensagem
    assert "não uma resposta conversacional" in mensagem
    assert "cabeçalho compacto textual" in mensagem
    assert veredito.aprovado is True
