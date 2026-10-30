from time import time
from unittest.mock import MagicMock, Mock

import jwt
import pytest
from app import auth
from app.erros import ServicoIndisponivel
from fastapi import HTTPException

CHAVE_TESTE = "chave-ficticia-de-teste-sem-uso-em-producao-" * 2


def _token(**alteracoes):
    agora = int(time())
    claims = {"sub": "usuario_teste", "iat": agora, "exp": agora + 3600, **alteracoes}
    return jwt.encode(claims, CHAVE_TESTE, algorithm="HS512")


@pytest.fixture
def conexao(monkeypatch):
    monkeypatch.setattr(auth.config, "SECURITY_KEY", CHAVE_TESTE)
    conexao = MagicMock()
    conexao.cursor.return_value.__enter__.return_value.fetchone.return_value = (25,)
    monkeypatch.setattr(auth, "get_conn", Mock(return_value=conexao))
    return conexao


def test_token_resolve_username_no_banco_sem_usar_id_ou_cargo_do_cliente(conexao):
    usuario = auth.obter_usuario_autenticado(_token(usuario_id=999, nivel_acesso="SUPER_ADMIN"))

    assert usuario.usuario_id == 25
    cursor = conexao.cursor.return_value.__enter__.return_value
    cursor.execute.assert_called_once_with("SELECT id FROM tb_usuario WHERE username = %s", ("usuario_teste",))
    conexao.close.assert_called_once()


@pytest.mark.parametrize("token", ["teste", "", "a.b.c"])
def test_token_malformado_nao_consulta_banco(conexao, token):
    with pytest.raises(HTTPException) as erro:
        auth.obter_usuario_autenticado(token)

    assert erro.value.status_code == 401
    conexao.cursor.assert_not_called()


def test_token_expirado_pede_novo_login(conexao):
    with pytest.raises(HTTPException) as erro:
        auth.obter_usuario_autenticado(_token(iat=int(time()) - 120, exp=int(time()) - 60))

    assert erro.value.status_code == 401
    assert "expirou" in erro.value.detail
    conexao.cursor.assert_not_called()


@pytest.mark.parametrize("algoritmo,chave", [("HS512", "outra-chave-ficticia-" * 4), ("HS256", CHAVE_TESTE)])
def test_rejeita_assinatura_ou_algoritmo_diferente(conexao, algoritmo, chave):
    claims = jwt.decode(_token(), CHAVE_TESTE, algorithms=["HS512"])
    token = jwt.encode(claims, chave, algorithm=algoritmo)

    with pytest.raises(HTTPException) as erro:
        auth.obter_usuario_autenticado(token)

    assert erro.value.status_code == 401
    conexao.cursor.assert_not_called()


@pytest.mark.parametrize("campo", ["sub", "iat", "exp"])
def test_rejeita_token_sem_claim_obrigatoria(conexao, campo):
    claims = jwt.decode(_token(), CHAVE_TESTE, algorithms=["HS512"])
    del claims[campo]

    with pytest.raises(HTTPException):
        auth.obter_usuario_autenticado(jwt.encode(claims, CHAVE_TESTE, algorithm="HS512"))

    conexao.cursor.assert_not_called()


def test_rejeita_token_de_usuario_excluido(conexao):
    conexao.cursor.return_value.__enter__.return_value.fetchone.return_value = None

    with pytest.raises(HTTPException) as erro:
        auth.obter_usuario_autenticado(_token())

    assert erro.value.status_code == 401


def test_sem_chave_configurada_nao_ativa_mock(monkeypatch):
    monkeypatch.setattr(auth.config, "SECURITY_KEY", None)

    with pytest.raises(ServicoIndisponivel):
        auth.obter_usuario_autenticado("teste")


def test_chave_jwt_configurada_e_mascarada_antes_de_enviar_texto(monkeypatch):
    from app.guardrail import anonimizar_texto

    monkeypatch.setattr(auth.config, "SECURITY_KEY", CHAVE_TESTE)

    assert anonimizar_texto(CHAVE_TESTE) == "[SEGREDO OMITIDO]"


@pytest.mark.parametrize("bytes_chave,algoritmo", [(32, "HS256"), (48, "HS384"), (64, "HS512")])
def test_compativel_com_selecao_hmac_do_jjwt(conexao, monkeypatch, bytes_chave, algoritmo):
    chave = "x" * bytes_chave
    monkeypatch.setattr(auth.config, "SECURITY_KEY", chave)
    agora = int(time())
    token = jwt.encode({"sub": "usuario_teste", "iat": agora, "exp": agora + 3600}, chave, algorithm=algoritmo)

    assert auth.obter_usuario_autenticado(token).usuario_id == 25


@pytest.mark.parametrize("rota", ["/chat", "/chat/encerrar", "/relatorios/pdf", "/observabilidade"])
def test_endpoints_rejeitam_token_falso_com_401_sem_consultar_banco(conexao, rota):
    from app.main import app
    from fastapi.testclient import TestClient

    cliente = TestClient(app)
    if rota == "/observabilidade":
        resposta = cliente.get(rota, headers={"Authorization": "Bearer teste"})
    else:
        corpo = {"token": "teste"}
        if rota == "/chat":
            corpo["mensagem"] = "oi"
        elif rota == "/relatorios/pdf":
            corpo.update(data_inicial="2026-10-01", data_final="2026-10-30")
        resposta = cliente.post(rota, json=corpo)

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"
    conexao.cursor.assert_not_called()
