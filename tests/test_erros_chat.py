from unittest.mock import Mock

from app.erros import ServicoIndisponivel
from app.main import app
from app.routes import chat
from fastapi.testclient import TestClient


def test_chat_oculta_detalhe_quando_o_servico_esta_indisponivel(monkeypatch):
    monkeypatch.setattr(
        chat, "executar_fluxo_skadi", Mock(side_effect=ServicoIndisponivel("detalhe interno"))
    )

    resposta = TestClient(app).post("/chat", json={"token": "teste", "mensagem": "oi"})

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "Serviço temporariamente indisponível."}
