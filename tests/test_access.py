from unittest.mock import Mock

import pytest
from app.tools.access import validar_acesso


def test_normaliza_o_nivel_de_acesso_do_usuario():
    cursor = Mock()
    cursor.fetchone.return_value = (2, " admin ", 7)

    escopo = validar_acesso(2, cursor=cursor)

    assert escopo.usuario_id == 2
    assert escopo.nivel_acesso == "ADMIN"
    cursor.execute.assert_called_once_with(
        "SELECT id, nivel_acesso, cod_cd FROM tb_usuario WHERE id = %s", (2,)
    )


def test_rejeita_usuario_que_nao_existe():
    cursor = Mock()
    cursor.fetchone.return_value = None

    with pytest.raises(PermissionError, match="nao encontrado"):
        validar_acesso(99, cursor=cursor)


def test_rejeita_nivel_de_acesso_desconhecido():
    cursor = Mock()
    cursor.fetchone.return_value = (2, "VISITANTE", 7)

    with pytest.raises(PermissionError, match="nao reconhecido"):
        validar_acesso(2, cursor=cursor)
