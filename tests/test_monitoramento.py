from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from app.tools import monitoramento
from app.tools.access import EscopoAcesso
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from tests.conftest import banco_sql


@pytest.fixture(autouse=True)
def limpar_cache_redis():
    monitoramento._cliente_redis.cache_clear()
    yield
    monitoramento._cliente_redis.cache_clear()


def _banco_camaras(monkeypatch, retornos):
    cursor, conexao = banco_sql(retornos=retornos)
    monkeypatch.setattr(monitoramento, "get_conn", Mock(return_value=conexao))
    return cursor


def test_cliente_redis_e_reutilizado(monkeypatch):
    monkeypatch.setattr(monitoramento, "REDIS_URL", "redis://teste")
    with patch("redis.Redis.from_url") as criar:
        primeiro = monitoramento._cliente_redis()
        segundo = monitoramento._cliente_redis()

    assert primeiro is segundo
    criar.assert_called_once_with("redis://teste", decode_responses=True)


def test_monitoramento_consulta_leitura_sem_classificar_origem(monkeypatch):
    camara = {"modelo": "A", "localizacao": "B", "termometro": 3,
              "limite_minimo": "2", "limite_maximo": "6"}
    monkeypatch.setattr(monitoramento, "consultar_camaras_permitidas", Mock(return_value=[camara]))
    cliente = Mock()
    cliente.xrevrange.return_value = [(
        "1-0", {"cod_termometro": "3", "temperatura": "4",
                "data_hora": "2026-10-14T09:04:00-03:00", "origem": "SIMULADO"},
    )]
    monkeypatch.setattr(monitoramento, "_cliente_redis", Mock(return_value=cliente))

    resposta = monitoramento.consultar_temperaturas_permitidas(2, camara_id=3)

    leitura = resposta["camaras"][0]
    assert leitura["temperatura"] == "4"
    assert leitura["data_hora"] == "2026-10-14T09:04:00-03:00"
    assert leitura["leitura_disponivel"] is True
    assert "origem_leitura" not in leitura
    assert "SIMULADO" not in str(resposta)


def test_alertas_de_admin_sao_filtrados_pelo_cd(monkeypatch):
    cursor = _banco_camaras(
        monkeypatch,
        [("Modelo A", "Setor 1", "URGENTE", "ATIVO", "TEMPERATURA_FORA_PADRAO", "2026-10-07", 1, 3)],
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
            "gravidade": "URGENTE",
            "status": "ATIVO",
            "tipo": "TEMPERATURA_FORA_PADRAO",
            "data_hora": "2026-10-07",
        }
    ]
    assert cursor.execute.call_args.args[1] == ["ATIVO", "RECONHECIDO", 2, 2]
    assert "camara.cod_cd = %s" in cursor.execute.call_args.args[0]
    assert "atendimento.cod_usuario = %s" in cursor.execute.call_args.args[0]


def test_alertas_de_operador_exigem_nivel_operador(monkeypatch):
    cursor = _banco_camaras(monkeypatch, [])
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(2, "OPERADOR", 2),
    )

    assert monitoramento.consultar_alertas_atuais(2) == []
    assert cursor.execute.call_args.args[1] == ["ATIVO", "RECONHECIDO", 2, 2, "OPERADOR"]
    assert "a.nivel_atual = %s" in cursor.execute.call_args.args[0]


def test_alertas_de_super_admin_nao_filtram_cd(monkeypatch):
    cursor = _banco_camaras(monkeypatch, [])
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(1, "SUPER_ADMIN", None),
    )

    assert monitoramento.consultar_alertas_atuais(1) == []
    assert cursor.execute.call_args.args[1] == ["ATIVO", "RECONHECIDO", 1]
    assert "camara.cod_cd = %s" not in cursor.execute.call_args.args[0]


def test_tool_de_alertas_mantem_usuario_no_backend(monkeypatch):
    consultar = Mock(return_value=[{"status": "ATIVO"}])
    monkeypatch.setattr(monitoramento, "consultar_alertas_atuais", consultar)

    token = definir_usuario_contexto(2)
    try:
        resposta = monitoramento.consultar_alertas_atuais_do_usuario.invoke({})
    finally:
        restaurar_usuario_contexto(token)

    assert resposta == [{"status": "ATIVO"}]
    consultar.assert_called_once_with(2)
