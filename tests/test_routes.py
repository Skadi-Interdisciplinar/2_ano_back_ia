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
