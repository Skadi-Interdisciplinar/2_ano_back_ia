from __future__ import annotations

import pytest
from app.schemas import ChatRequest, ChatResponse
from pydantic import ValidationError


def test_chat_request_remove_espacos():
    requisicao = ChatRequest(token="  token  ", mensagem="  olá  ")

    assert requisicao.token == "token"
    assert requisicao.mensagem == "olá"


@pytest.mark.parametrize("campo", ["token", "mensagem"])
def test_chat_request_rejeita_texto_vazio(campo):
    dados = {"token": "t", "mensagem": "oi"}
    dados[campo] = "   "

    with pytest.raises(ValidationError):
        ChatRequest(**dados)


def test_chat_request_rejeita_campos_extras():
    with pytest.raises(ValidationError):
        ChatRequest(token="t", mensagem="oi", usuario_id=2)


def test_chat_response_tem_lista_de_agentes_vazia_por_padrao():
    resposta = ChatResponse(resposta="Olá")

    assert resposta.agentes_chamados == []
