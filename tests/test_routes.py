from __future__ import annotations

from app.auth import AuthenticatedUser
from app.main import app
from app.routes import chat
from fastapi.testclient import TestClient


def test_chat_repassa_mensagem_e_usuario_ao_fluxo(monkeypatch):
    chamadas = []
    monkeypatch.setattr(chat, "obter_usuario_autenticado", lambda token: AuthenticatedUser(2))
    monkeypatch.setattr(
        chat,
        "executar_fluxo_skadi",
        lambda mensagem, usuario_id: chamadas.append((mensagem, usuario_id)) or ("Resposta", ["roteador"]),
    )

    resposta = TestClient(app).post("/chat", json={"token": "teste", "mensagem": "oi"})

    assert resposta.status_code == 200
    assert resposta.json() == {"resposta": "Resposta", "agentes_chamados": ["roteador"]}
    assert chamadas == [("oi", 2)]


def test_chat_rejeita_corpo_antigo_com_sessao_id():
    resposta = TestClient(app).post(
        "/chat",
        json={"token": "teste", "mensagem": "oi", "sessao_id": "nao-usar"},
    )

    assert resposta.status_code == 422


def test_encerrar_chat_usa_usuario_do_token(monkeypatch):
    chamadas = []
    monkeypatch.setattr(chat, "obter_usuario_autenticado", lambda token: AuthenticatedUser(2))
    monkeypatch.setattr(chat, "encerrar_sessao", lambda usuario: chamadas.append(usuario) or "Resumo")
    resposta = TestClient(app).post("/chat/encerrar", json={"token": "teste"})
    assert resposta.status_code == 200
    assert resposta.json() == {"resumo": "Resumo"}
    assert chamadas == [2]


def test_encerrar_chat_nao_aceita_usuario_do_corpo():
    resposta = TestClient(app).post("/chat/encerrar", json={"token": "teste", "usuario_id": 9})
    assert resposta.status_code == 422
