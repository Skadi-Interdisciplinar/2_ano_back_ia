from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from app.tools import monitoramento
from app.tools.access import EscopoAcesso
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from tests.conftest import ConexaoFalsa, CursorFalso


@pytest.fixture(autouse=True)
def limpar_cache_redis():
    monitoramento._cliente_redis.cache_clear()
    yield
    monitoramento._cliente_redis.cache_clear()


def _banco_camara(monkeypatch, retorno):
    cursor = CursorFalso(retorno)
    monkeypatch.setattr(monitoramento, "get_conn", lambda: ConexaoFalsa(cursor))
    return cursor


def _banco_camaras(monkeypatch, retornos):
    cursor = CursorFalso(retornos=retornos)
    monkeypatch.setattr(monitoramento, "get_conn", lambda: ConexaoFalsa(cursor))
    return cursor


def test_cliente_redis_e_reutilizado(monkeypatch):
    chamadas = []
    cliente = object()
    monkeypatch.setattr(monitoramento, "REDIS_URL", "redis://teste")
    redis_falso = type(
        "RedisFalso",
        (),
        {"from_url": staticmethod(lambda *args, **kwargs: chamadas.append((args, kwargs)) or cliente)},
    )
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=redis_falso))

    primeiro = monitoramento._cliente_redis()
    segundo = monitoramento._cliente_redis()

    assert primeiro is cliente
    assert segundo is cliente
    assert len(chamadas) == 1


def test_alertas_de_admin_sao_filtrados_pelo_cd(monkeypatch):
    cursor = _banco_camaras(
        monkeypatch,
        [("Modelo A", "Setor 1", "urgente", "ativo", "temperatura_fora_padrao", "2026-10-07")],
    )
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(2, "ADMIN", 2),
    )

    alertas = monitoramento.consultar_alertas_atuais(2)

    assert alertas == [
        {
            "camara": "Modelo A — Setor 1",
            "gravidade": "urgente",
            "status": "ativo",
            "tipo": "temperatura_fora_padrao",
            "data_hora": "2026-10-07",
        }
    ]
    assert cursor.comandos[0][1] == ["ativo", "reconhecido", 2, 2]
    assert "camara.cod_cd = %s" in cursor.comandos[0][0]
    assert "atendimento.cod_usuario = %s" in cursor.comandos[0][0]


def test_alertas_de_operador_exigem_nivel_operador(monkeypatch):
    cursor = _banco_camaras(monkeypatch, [])
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(2, "OPERADOR", 2),
    )

    assert monitoramento.consultar_alertas_atuais(2) == []
    assert cursor.comandos[0][1] == ["ativo", "reconhecido", 2, 2, "operador"]
    assert "a.nivel_atual = %s" in cursor.comandos[0][0]


def test_alertas_de_super_admin_nao_filtram_cd(monkeypatch):
    cursor = _banco_camaras(monkeypatch, [])
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(1, "SUPER_ADMIN", None),
    )

    assert monitoramento.consultar_alertas_atuais(1) == []
    assert cursor.comandos[0][1] == ["ativo", "reconhecido", 1]
    assert "camara.cod_cd = %s" not in cursor.comandos[0][0]


def test_tool_de_alertas_mantem_usuario_no_backend(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        monitoramento,
        "consultar_alertas_atuais",
        lambda usuario_id: chamadas.append(usuario_id) or [{"status": "ativo"}],
    )

    token = definir_usuario_contexto(2)
    try:
        resposta = monitoramento.consultar_alertas_atuais_do_usuario.invoke({})
    finally:
        restaurar_usuario_contexto(token)

    assert resposta == [{"status": "ativo"}]
    assert chamadas == [2]
