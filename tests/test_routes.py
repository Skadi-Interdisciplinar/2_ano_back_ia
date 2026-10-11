from unittest.mock import Mock

from app.auth import AuthenticatedUser
from app.main import app
from app.routes import chat
from fastapi.testclient import TestClient


def test_chat_repassa_mensagem_e_usuario_ao_fluxo(monkeypatch):
    autenticar = Mock(return_value=AuthenticatedUser(2))
    fluxo = Mock(return_value=("Resposta", ["roteador"]))
    monkeypatch.setattr(chat, "obter_usuario_autenticado", autenticar)
    monkeypatch.setattr(chat, "executar_fluxo_skadi", fluxo)

    resposta = TestClient(app).post("/chat", json={"token": "teste", "mensagem": "oi"})

    assert resposta.status_code == 200
    assert resposta.json() == {"resposta": "Resposta", "agentes_chamados": ["roteador"]}
    autenticar.assert_called_once_with("teste")
    fluxo.assert_called_once_with("oi", 2)


def test_chat_rejeita_corpo_antigo_com_sessao_id():
    resposta = TestClient(app).post(
        "/chat", json={"token": "teste", "mensagem": "oi", "sessao_id": "nao-usar"},
    )

    assert resposta.status_code == 422


def test_encerrar_chat_usa_usuario_do_token(monkeypatch):
    autenticar = Mock(return_value=AuthenticatedUser(2))
    encerrar = Mock(return_value="Resumo")
    monkeypatch.setattr(chat, "obter_usuario_autenticado", autenticar)
    monkeypatch.setattr(chat, "encerrar_sessao", encerrar)

    resposta = TestClient(app).post("/chat/encerrar", json={"token": "teste"})

    assert resposta.status_code == 200
    assert resposta.json() == {"resumo": "Resumo"}
    autenticar.assert_called_once_with("teste")
    encerrar.assert_called_once_with(2)


def test_encerrar_chat_nao_aceita_usuario_do_corpo():
    resposta = TestClient(app).post("/chat/encerrar", json={"token": "teste", "usuario_id": 9})

    assert resposta.status_code == 422
