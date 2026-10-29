from app.auth import obter_usuario_autenticado


def test_autenticacao_temporaria_usa_gestor_de_teste(monkeypatch):
    monkeypatch.setattr("app.auth.config.USUARIO_TESTE_ID", 12)
    usuario = obter_usuario_autenticado("qualquer-token")

    assert usuario.usuario_id == 12


def test_token_nao_escolhe_identidade_do_mock(monkeypatch):
    monkeypatch.setattr("app.auth.config.USUARIO_TESTE_ID", 25)

    usuario = obter_usuario_autenticado("1")

    assert usuario.usuario_id == 25
