from unittest.mock import Mock, patch

import pytest
from app.erros import ServicoIndisponivel
from app.tools import db


def test_exige_url_para_abrir_conexao(monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", None)

    with pytest.raises(ServicoIndisponivel, match="DATABASE_URL"):
        db.get_conn()


def test_devolve_conexao_do_psycopg2(monkeypatch):
    conexao = Mock()
    monkeypatch.setattr(db, "DATABASE_URL", "postgres://teste")

    with patch("psycopg2.connect", return_value=conexao) as conectar:
        resultado = db.get_conn()

    assert resultado is conexao
    conectar.assert_called_once_with("postgres://teste")
