"""Acesso centralizado ao PostgreSQL usado pelas tools da Trimmy."""

from __future__ import annotations

from app.config import DATABASE_URL
from app.erros import ServicoIndisponivel


def get_conn():
    """Abre uma conexão PostgreSQL e traduz indisponibilidade de infraestrutura."""

    if not DATABASE_URL:
        raise ServicoIndisponivel("DATABASE_URL não configurada.")

    import psycopg2

    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.OperationalError as erro:
        raise ServicoIndisponivel("Banco de dados indisponível.") from erro
