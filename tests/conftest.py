"""Preparação simples de conexão e cursor para testes sem banco real."""

from unittest.mock import MagicMock, Mock

import pytest


def banco_sql(retorno=None, retornos=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = retorno
    cursor.fetchall.return_value = retornos or []
    cursor.__enter__.return_value = cursor

    conexao = MagicMock()
    conexao.cursor.return_value = cursor
    conexao.__enter__.return_value = conexao
    return cursor, conexao


@pytest.fixture(name="contexto")
def preparar_contexto_predicao(monkeypatch):
    """Contexto isolado compartilhado somente pelos testes de predição."""
    from datetime import UTC, datetime

    from app import predicao
    from app.tools import predicao as tools
    from app.tools.access import EscopoAcesso
    from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
    from tests.test_modelos_predicao import leituras, treinar

    usuario = definir_usuario_contexto(2)
    contexto = predicao.ContextoPredicao(2)
    token = predicao.contexto_predicao.set(contexto)
    monkeypatch.setattr(predicao, "validar_acesso", Mock(return_value=EscopoAcesso(2, "ADMIN", 7)))
    camara = {"camara_id": 3, "termometro": 9, "modelo": "A", "localizacao": "Setor 1",
              "limite_minimo": "2", "limite_maximo": "6"}
    monkeypatch.setattr(tools, "consultar_camaras_permitidas", Mock(return_value=[camara]))
    modelo = treinar([4] * 20).model_copy(update={"status": "APROVADO", "aprovado_em": datetime.now(UTC)})
    monkeypatch.setattr(tools, "carregar_modelo", Mock(return_value=modelo))
    monkeypatch.setattr(tools, "consultar_serie", Mock(return_value=leituras([4] * 20)[-2:]))
    yield contexto
    predicao.contexto_predicao.reset(token)
    restaurar_usuario_contexto(usuario)
