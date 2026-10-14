from __future__ import annotations

from unittest.mock import Mock

import pytest
from app.tools import access
from tests.conftest import banco_sql


def _configurar_banco_falso(monkeypatch, retorno):
    cursor, conexao = banco_sql(retorno=retorno)
    monkeypatch.setattr(access, "get_conn", Mock(return_value=conexao))
    return cursor


def test_validar_acesso_normaliza_nivel_do_banco(monkeypatch):
    cursor = _configurar_banco_falso(monkeypatch, (2, " admin ", 7))

    escopo = access.validar_acesso(2)

    assert escopo.usuario_id == 2
    assert escopo.nivel_acesso == "ADMIN"
    assert escopo.cd_id == 7
    assert cursor.execute.call_args.args[1] == (2,)


def test_validar_acesso_rejeita_usuario_inexistente(monkeypatch):
    _configurar_banco_falso(monkeypatch, None)

    with pytest.raises(PermissionError, match="nao encontrado"):
        access.validar_acesso(99)


def test_validar_acesso_rejeita_nivel_desconhecido(monkeypatch):
    _configurar_banco_falso(monkeypatch, (2, "VISITANTE", 7))

    with pytest.raises(PermissionError, match="nao reconhecido"):
        access.validar_acesso(2)


@pytest.mark.parametrize("falha", [False, True])
def test_validacao_fecha_conexao_mesmo_com_erro(monkeypatch, falha):
    cursor, conexao = banco_sql(retorno=(2, "ADMIN", 7))
    monkeypatch.setattr(access, "get_conn", Mock(return_value=conexao))
    if falha:
        cursor.execute.side_effect = RuntimeError("Consulta indisponível")
        with pytest.raises(RuntimeError):
            access.validar_acesso(2)
    else:
        access.validar_acesso(2)

    conexao.close.assert_called_once()


