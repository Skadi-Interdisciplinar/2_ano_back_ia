from unittest.mock import Mock

from app import juiz


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
