from unittest.mock import Mock

from app import auth
from app.auth import AuthenticatedUser
from app.main import app
from app.routes import chat
from fastapi.testclient import TestClient


def test_chat_repassa_mensagem_e_usuario_ao_fluxo(monkeypatch):
    autenticar = Mock(return_value=AuthenticatedUser(12))
    fluxo = Mock(return_value=("Resposta", ["roteador", "orquestrador"]))
    monkeypatch.setattr(auth, "obter_usuario_autenticado", autenticar)
    monkeypatch.setattr(chat, "executar_fluxo_skadi", fluxo)

    resposta = TestClient(app).post("/chat", headers={"Authorization": "Bearer teste"}, json={"mensagem": "oi"})

    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == "Resposta"
    fluxo.assert_called_once_with("oi", 12)


def test_chat_rejeita_sessao_enviada_pelo_mobile(monkeypatch):
    monkeypatch.setattr(auth, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(12)))
    resposta = TestClient(app).post("/chat", headers={"Authorization": "Bearer teste"}, json={
        "mensagem": "oi", "sessao_id": "nao-aceita"
    })

    assert resposta.status_code == 422


def test_encerrar_chat_usa_usuario_do_token(monkeypatch):
    encerrar = Mock(return_value="Resumo")
    monkeypatch.setattr(auth, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(12)))
    monkeypatch.setattr(chat, "encerrar_sessao", encerrar)

    resposta = TestClient(app).post("/chat/encerrar", headers={"Authorization": "Bearer teste"})

    assert resposta.json() == {"resumo": "Resumo"}
    encerrar.assert_called_once_with(12)


def test_chat_encaminha_cada_usuario_do_bearer_sem_identidade_no_corpo(monkeypatch):
    monkeypatch.setattr(auth, "obter_usuario_autenticado", Mock(side_effect=[AuthenticatedUser(20), AuthenticatedUser(21)]))
    fluxo = Mock(return_value=("Resposta", ["orquestrador"]))
    monkeypatch.setattr(chat, "executar_fluxo_skadi", fluxo)
    cliente = TestClient(app)

    for token in ("jwt-usuario-a", "jwt-usuario-b"):
        resposta = cliente.post("/chat", headers={"Authorization": f"Bearer {token}"}, json={"mensagem": "oi"})
        assert resposta.status_code == 200

    assert [chamada.args for chamada in fluxo.call_args_list] == [("oi", 20), ("oi", 21)]


def test_chat_rejeita_token_no_corpo(monkeypatch):
    monkeypatch.setattr(auth, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(20)))
    fluxo = Mock()
    monkeypatch.setattr(chat, "executar_fluxo_skadi", fluxo)

    resposta = TestClient(app).post("/chat", headers={"Authorization": "Bearer jwt"},
                                  json={"token": "antigo", "mensagem": "oi"})

    assert resposta.status_code == 422
    fluxo.assert_not_called()


def test_swagger_declara_bearer_nos_quatro_endpoints():
    schema = app.openapi()
    for caminho, metodo in (("/chat", "post"), ("/chat/encerrar", "post"),
                            ("/relatorios/pdf", "post"), ("/observabilidade", "get")):
        assert schema["paths"][caminho][metodo]["security"] == [{"HTTPBearer": []}]
    assert "requestBody" not in schema["paths"]["/chat/encerrar"]["post"]
