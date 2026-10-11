from __future__ import annotations

import pytest
from app.tools import access
from tests.conftest import ConexaoFalsa, CursorFalso


def _configurar_banco_falso(monkeypatch, retorno):
    cursor = CursorFalso(retorno)
    monkeypatch.setattr(access, "get_conn", lambda: ConexaoFalsa(cursor))
    return cursor


def test_validar_acesso_normaliza_nivel_do_banco(monkeypatch):
    cursor = _configurar_banco_falso(monkeypatch, (2, " admin ", 7))

    escopo = access.validar_acesso(2)

    assert escopo.usuario_id == 2
    assert escopo.nivel_acesso == "ADMIN"
    assert escopo.cd_id == 7
    assert cursor.comandos[0][1] == (2,)


def test_validar_acesso_rejeita_usuario_inexistente(monkeypatch):
    _configurar_banco_falso(monkeypatch, None)

    with pytest.raises(PermissionError, match="nao encontrado"):
        access.validar_acesso(99)


def test_validar_acesso_rejeita_nivel_desconhecido(monkeypatch):
    _configurar_banco_falso(monkeypatch, (2, "VISITANTE", 7))

    with pytest.raises(PermissionError, match="nao reconhecido"):
        access.validar_acesso(2)


