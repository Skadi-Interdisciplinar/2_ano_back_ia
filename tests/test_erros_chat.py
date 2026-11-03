from unittest.mock import Mock

from app import auth
from app.auth import AuthenticatedUser
from app.erros import ServicoIndisponivel
from app.main import app
from app.routes import chat
from fastapi.testclient import TestClient


def test_chat_oculta_detalhe_quando_o_servico_esta_indisponivel(monkeypatch):
    monkeypatch.setattr(auth, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(12)))
    monkeypatch.setattr(
        chat, "executar_fluxo_skadi", Mock(side_effect=ServicoIndisponivel("detalhe interno"))
    )

    resposta = TestClient(app).post("/chat", headers={"Authorization": "Bearer jwt-teste"}, json={"mensagem": "oi"})

    assert resposta.status_code == 503
    assert "serviço necessário está indisponível" in resposta.json()["detail"]
    assert "detalhe interno" not in resposta.text
