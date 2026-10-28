import pytest
from app.schemas import ChatRequest, ChatResponse, RelatorioRequest
from pydantic import ValidationError


def test_remove_espacos_da_mensagem_do_chat():
    requisicao = ChatRequest(token="  token  ", mensagem="  olá  ")

    assert requisicao.token == "token"
    assert requisicao.mensagem == "olá"


def test_rejeita_mensagem_vazia_no_chat():
    with pytest.raises(ValidationError):
        ChatRequest(token="teste", mensagem="   ")


def test_remove_formatacao_simples_da_resposta():
    resposta = ChatResponse(resposta="**Leitura:** 4.00 °C\n\n")

    assert resposta.resposta == "Leitura: 4.00 °C"


def test_rejeita_periodo_de_relatorio_invertido():
    with pytest.raises(ValidationError):
        RelatorioRequest(
            token="teste", cd_id=2, data_inicial="2026-10-20", data_final="2026-10-10"
        )
