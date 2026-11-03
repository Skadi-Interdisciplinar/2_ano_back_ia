from unittest.mock import Mock

import pytest
from app.tools.access import validar_acesso


def test_normaliza_o_nivel_de_acesso_do_usuario():
    cursor = Mock()
    cursor.fetchone.return_value = (2, " gestor ", 7)

    escopo = validar_acesso(2, cursor=cursor)

    assert escopo.usuario_id == 2
    assert escopo.nivel_acesso == "GESTOR"
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


def test_admin_usa_relacionamento_de_cds_sem_fallback_para_cd_direto():
    cursor = Mock()
    cursor.fetchone.return_value = (2, "ADMIN", 99)
    cursor.fetchall.return_value = [(3,), (7,)]

    escopo = validar_acesso(2, cursor=cursor)

    assert escopo.cds_permitidos == (3, 7)
    assert escopo.permite_cd(3)
    assert not escopo.permite_cd(99)
    cursor.execute.assert_called_with("SELECT cod_cd FROM tb_admin_cd WHERE cod_admin = %s ORDER BY cod_cd", (2,))


def test_admin_sem_vinculos_nao_obtem_escopo_pelo_cd_direto():
    cursor = Mock()
    cursor.fetchone.return_value = (2, "ADMIN", 99)
    cursor.fetchall.return_value = []

    escopo = validar_acesso(2, cursor=cursor)

    assert escopo.cds_permitidos == ()
    assert not escopo.permite_cd(99)
