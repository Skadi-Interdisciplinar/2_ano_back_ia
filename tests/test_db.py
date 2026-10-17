from unittest.mock import Mock, patch

import psycopg2
import pytest
from app.tools import db


def test_get_conn_exige_url_de_banco(monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", None)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db.get_conn()


def test_get_conn_traduz_indisponibilidade(monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", "postgres://teste")

    with (
        patch("psycopg2.connect", side_effect=psycopg2.OperationalError("fora")),
        pytest.raises(RuntimeError, match="Banco de dados indisponível"),
    ):
        db.get_conn()


def test_get_conn_retorna_conexao(monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", "postgres://teste")
    conexao = Mock()

    with patch("psycopg2.connect", return_value=conexao) as conectar:
        assert db.get_conn() is conexao

    conectar.assert_called_once_with("postgres://teste")
