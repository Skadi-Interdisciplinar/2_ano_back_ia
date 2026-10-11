from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from app.tools import db


def test_get_conn_exige_url_de_banco(monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", None)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db.get_conn()


def test_get_conn_traduz_indisponibilidade(monkeypatch):
    class ErroOperacional(Exception):
        pass

    monkeypatch.setattr(db, "DATABASE_URL", "postgres://teste")
    monkeypatch.setitem(
        sys.modules,
        "psycopg2",
        SimpleNamespace(
            OperationalError=ErroOperacional,
            connect=lambda _url: (_ for _ in ()).throw(ErroOperacional("fora")),
        ),
    )

    with pytest.raises(RuntimeError, match="Banco de dados indisponível"):
        db.get_conn()
