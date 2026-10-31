from unittest.mock import Mock

from app.auth import AuthenticatedUser
from app.main import app
from app.routes import chat
from fastapi.testclient import TestClient


def test_chat_repassa_mensagem_e_usuario_ao_fluxo(monkeypatch):
    autenticar = Mock(return_value=AuthenticatedUser(12))
    fluxo = Mock(return_value=("Resposta", ["roteador", "orquestrador"]))
    monkeypatch.setattr(chat, "obter_usuario_autenticado", autenticar)
    monkeypatch.setattr(chat, "executar_fluxo_skadi", fluxo)

    resposta = TestClient(app).post("/chat", json={"token": "teste", "mensagem": "oi"})

    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == "Resposta"
    fluxo.assert_called_once_with("oi", 12)


def test_chat_rejeita_sessao_enviada_pelo_mobile():
    resposta = TestClient(app).post("/chat", json={
        "token": "teste", "mensagem": "oi", "sessao_id": "nao-aceita"
    })

    assert resposta.status_code == 422


def test_encerrar_chat_usa_usuario_do_token(monkeypatch):
    encerrar = Mock(return_value="Resumo")
    monkeypatch.setattr(chat, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(12)))
    monkeypatch.setattr(chat, "encerrar_sessao", encerrar)

    resposta = TestClient(app).post("/chat/encerrar", json={"token": "teste"})

    assert resposta.json() == {"resumo": "Resumo"}
    encerrar.assert_called_once_with(12)
