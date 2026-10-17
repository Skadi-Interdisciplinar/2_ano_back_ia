"""Preparação simples de conexão e cursor para testes sem banco real."""

from unittest.mock import MagicMock


def banco_sql(retorno=None, retornos=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = retorno
    cursor.fetchall.return_value = retornos or []
    cursor.__enter__.return_value = cursor

    conexao = MagicMock()
    conexao.cursor.return_value = cursor
    conexao.__enter__.return_value = conexao
    return cursor, conexao
