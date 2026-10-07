"""Fixtures e dublês compartilhados para testes sem infraestrutura externa."""

from __future__ import annotations

from types import SimpleNamespace


class CursorFalso:
    def __init__(self, retorno=None):
        self.retorno = retorno
        self.comandos: list[tuple[str, tuple | None]] = []

    def execute(self, comando, parametros=None):
        self.comandos.append((comando, parametros))

    def fetchone(self):
        return self.retorno

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ConexaoFalsa:
    def __init__(self, cursor):
        self.cursor_falso = cursor

    def cursor(self):
        return self.cursor_falso

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def modulo_psycopg2(conexao):
    return SimpleNamespace(connect=lambda _url: conexao)
