"""Testes opt-in de conectividade com a infraestrutura configurada.

Eles nao inserem, atualizam ou removem dados. A execucao requer
SKADI_RUN_INTEGRATION_TESTS=true para evitar chamadas acidentais a bancos ou
provedores de IA durante a suite unitária.
"""

from __future__ import annotations

import os

import pytest

from app.config import DATABASE_URL, GEMINI_API_KEY, GROQ_API_KEY, MONGODB_URI, REDIS_URL


pytestmark = pytest.mark.integration


def _requer_execucao_real() -> None:
    if os.getenv("SKADI_RUN_INTEGRATION_TESTS", "").strip().lower() != "true":
        pytest.skip("Defina SKADI_RUN_INTEGRATION_TESTS=true para executar integrações reais.")


def test_postgresql_esta_acessivel():
    """Executa apenas SELECT 1 no banco operacional."""

    _requer_execucao_real()
    if not DATABASE_URL:
        pytest.fail("DATABASE_URL nao configurada.")
    import psycopg2

    with psycopg2.connect(DATABASE_URL, connect_timeout=10) as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)


def test_redis_esta_acessivel():
    """Executa somente PING no Redis."""

    _requer_execucao_real()
    if not REDIS_URL:
        pytest.fail("REDIS_URL nao configurada.")
    import redis

    cliente = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=10)
    assert cliente.ping() is True


def test_mongodb_esta_acessivel():
    """Executa somente o comando administrativo ping no MongoDB."""

    _requer_execucao_real()
    if not MONGODB_URI:
        pytest.fail("MONGODB_URI nao configurada.")
    from pymongo import MongoClient

    with MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10_000) as cliente:
        resultado = cliente.admin.command("ping")
    assert resultado["ok"] == 1.0


def test_modelo_esta_acessivel():
    """Faz uma chamada curta ao modelo configurado, sem acessar dados do Skadi."""

    _requer_execucao_real()
    if not GEMINI_API_KEY or not GROQ_API_KEY:
        pytest.fail("GEMINI_API_KEY e GROQ_API_KEY precisam estar configuradas.")
    from app.llms import obter_modelos

    modelo, _ = obter_modelos()
    resposta = modelo.invoke("Responda somente com a palavra PONG.")

    assert str(resposta.content).strip()
