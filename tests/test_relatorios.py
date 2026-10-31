from unittest.mock import Mock

import pytest
from app.relatorios import FiltroRelatorioInvalido, _cd_permitido, registrar_relatorio
from app.tools.access import EscopoAcesso


def test_gestor_usa_apenas_o_proprio_cd():
    escopo = EscopoAcesso(usuario_id=12, nivel_acesso="GESTOR", cd_id=2)

    cd = _cd_permitido(escopo, None)

    assert cd == 2


def test_super_admin_precisa_informar_cd():
    escopo = EscopoAcesso(usuario_id=1, nivel_acesso="SUPER_ADMIN", cd_id=None)

    with pytest.raises(FiltroRelatorioInvalido):
        _cd_permitido(escopo, None)


def test_registra_hash_e_download_do_relatorio(monkeypatch):
    cursor = Mock()
    cursor.fetchone.side_effect = [(12, "GESTOR", 2), (99,)]

    class CursorContexto:
        def __enter__(self):
            return cursor

        def __exit__(self, *_):
            return False

    conexao = Mock()
    conexao.cursor.return_value = CursorContexto()
    monkeypatch.setattr("app.relatorios.get_conn", Mock(return_value=conexao))

    registrar_relatorio(12, {"cd_id": 2, "data_inicial": "2026-10-01", "data_final": "2026-10-10"}, b"%PDF")

    assert cursor.execute.call_count == 3
    conexao.commit.assert_called_once()
