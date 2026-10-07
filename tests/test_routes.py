from fastapi.testclient import TestClient
from app.auth import AuthenticatedUser
from app.main import app
from app.routes import chat


def test_chat_repassa_mensagem_ao_agente(monkeypatch):
    monkeypatch.setattr(chat, "obter_usuario_autenticado", lambda _token: AuthenticatedUser(2))
    monkeypatch.setattr(
        chat,
        "executar_fluxo_skadi",
        lambda mensagem, usuario_id: ("Resposta", ["roteador"]),
    )

    resposta = TestClient(app).post("/chat", json={"token": "teste", "mensagem": "oi"})

    assert resposta.status_code == 200
    assert resposta.json() == {"resposta": "Resposta", "agentes_chamados": ["roteador"]}
