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


def test_chat_response_remove_enfase_e_quebras_de_linha():
    resposta = ChatResponse(resposta="O degelo pode **reduzir a eficiência**.\n\nConfirme *o relato*.")

    assert resposta.resposta == "O degelo pode reduzir a eficiência. Confirme o relato."
    assert "\\n" not in resposta.model_dump_json()
    assert "*" not in resposta.resposta


def test_formato_preserva_dados_fontes_e_caminhos():
    texto = "Leitura: **4.50 °C**, 2026-08-31T08:00:00-03:00.\nFonte: https://example.com.\nNão confirma falha. C:\\notas; cálculo 2*3*4."

    resposta = ChatResponse(resposta=texto, agentes_chamados=["diagnostico"])

    assert "4.50 °C" in resposta.resposta
    assert "2026-08-31T08:00:00-03:00" in resposta.resposta
    assert "https://example.com" in resposta.resposta
    assert "Não confirma falha" in resposta.resposta
    assert "C:\\notas" in resposta.resposta
    assert "2*3*4" in resposta.resposta
    assert resposta.agentes_chamados == ["diagnostico"]


@pytest.mark.parametrize("texto", [
    "2 * 3 * 4", "2*3*4", "x * y * z", "2 ** 3", "2 ** 3 ** 4", "2**3**4",
])
def test_formato_preserva_operadores_matematicos(texto):
    assert ChatResponse(resposta=texto).resposta == texto
