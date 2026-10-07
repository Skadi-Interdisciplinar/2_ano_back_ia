import pytest
from jwt import encode

from app import auth
from app.tools import access


def test_obter_usuario_autenticado_usa_validate_token(monkeypatch):
    monkeypatch.setattr(auth, "validate_token", lambda _token: 7)

    usuario = auth.obter_usuario_autenticado("qualquer-token")

    assert usuario.usuario_id == 7


def test_validate_token_decodifica_jwt_e_busca_usuario(monkeypatch):
    monkeypatch.setattr(auth, "JWT_SECRET_KEY", "segredo-teste-com-32-bytes-ok!!!")
    monkeypatch.setattr(auth, "get_user_id", lambda username: 7 if username == "enzo" else 0)
    token = encode({"sub": "enzo"}, "segredo-teste-com-32-bytes-ok!!!", algorithm="HS256")

    assert auth.validate_token(token) == 7


def test_validate_token_rejeita_jwt_invalido(monkeypatch):
    monkeypatch.setattr(auth, "JWT_SECRET_KEY", "segredo-teste-com-32-bytes-ok!!!")

    with pytest.raises(ValueError, match="Erro ao validar token"):
        auth.validate_token("token-invalido")


def test_get_user_id_exige_banco(monkeypatch):
    monkeypatch.setattr(access, "DATABASE_URL", None)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        access.get_user_id("enzo")
