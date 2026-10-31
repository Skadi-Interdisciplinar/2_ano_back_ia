import pytest
from app.erros import SaidaModeloInvalida
from app.faq import RESPOSTAS_FAQ, SelecaoFAQ, apresentar_faq


def test_apresenta_a_resposta_aprovada_da_faq():
    resposta = apresentar_faq(SelecaoFAQ(referencias=["FAQ-031"]))

    assert resposta == RESPOSTAS_FAQ["FAQ-031"]


def test_informa_quando_nao_ha_resposta_aprovada():
    resposta = apresentar_faq(SelecaoFAQ())

    assert "Não tenho informação aprovada" in resposta


def test_rejeita_referencia_que_nao_esta_na_base():
    with pytest.raises(SaidaModeloInvalida):
        apresentar_faq(SelecaoFAQ(referencias=["FAQ-999"]))
