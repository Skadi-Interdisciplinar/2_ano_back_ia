from app.auth import obter_usuario_autenticado


def test_autenticacao_temporaria_usa_usuario_dois():
    usuario = obter_usuario_autenticado("qualquer-token")

    assert usuario.usuario_id == 2
