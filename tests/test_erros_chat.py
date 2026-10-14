from unittest.mock import Mock

import pytest
from app.erros import SaidaModeloInvalida, ServicoIndisponivel
from app.main import app
from app.routes import chat
from fastapi.testclient import TestClient
from httpx import ConnectError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from psycopg2 import OperationalError
from pymongo.errors import ServerSelectionTimeoutError
from qdrant_client.http.exceptions import ResponseHandlingException
from redis.exceptions import ConnectionError as RedisConnectionError
from tests.test_llms import erro_groq


@pytest.mark.parametrize("erro,status", [
    (PermissionError("dados sigilosos"), 403),
    (SaidaModeloInvalida("JSON interno inválido"), 502),
    (ServicoIndisponivel("configuração interna"), 503),
    (OperationalError("URI com credenciais"), 503),
    (ServerSelectionTimeoutError("URI com credenciais"), 503),
    (RedisConnectionError("senha interna"), 503),
    (ResponseHandlingException(ConnectError("cluster privado")), 503),
    (ConnectError("provedor fora"), 503),
    (ChatGoogleGenerativeAIError("429 RESOURCE_EXHAUSTED detalhes internos"), 503),
    (erro_groq(), 502),
])
def test_chat_mapeia_erros_sem_expor_detalhes(monkeypatch, erro, status):
    monkeypatch.setattr(chat, "executar_fluxo_skadi", Mock(side_effect=erro))

    resposta = TestClient(app).post("/chat", json={"token": "teste", "mensagem": "Diagnostique"})

    assert resposta.status_code == status
    assert "detail" in resposta.json()
    assert str(erro) not in resposta.text


def test_openapi_mantem_contrato_mobile_e_documenta_falhas():
    operacao = app.openapi()["paths"]["/chat"]["post"]

    assert {"403", "502", "503"} <= operacao["responses"].keys()
    schema = app.openapi()["components"]["schemas"]["ChatRequest"]
    assert set(schema["properties"]) == {"token", "mensagem"}


def test_runtime_de_sessao_nao_e_rotulado_como_falha_de_infraestrutura(monkeypatch):
    monkeypatch.setattr(chat, "executar_fluxo_skadi", Mock(side_effect=RuntimeError("sessão encerrando")))

    resposta = TestClient(app, raise_server_exceptions=False).post(
        "/chat", json={"token": "teste", "mensagem": "oi"},
    )

    assert resposta.status_code == 500


def test_rejeicao_groq_registra_codigo_sem_geracao_ou_dados(monkeypatch, caplog):
    monkeypatch.setattr(chat, "executar_fluxo_skadi", Mock(side_effect=erro_groq()))

    resposta = TestClient(app).post("/chat", json={"token": "token-privado", "mensagem": "pergunta privada"})

    assert resposta.status_code == 502
    assert "HTTP=400 codigo=tool_use_failed" in caplog.text
    assert "privad" not in caplog.text
    assert "privad" not in resposta.text

