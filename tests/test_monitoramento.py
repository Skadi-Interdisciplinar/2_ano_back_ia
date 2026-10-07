from __future__ import annotations

import sys
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.tools import monitoramento
from app.tools.access import EscopoAcesso
from tests.conftest import ConexaoFalsa, CursorFalso, modulo_psycopg2


@pytest.fixture(autouse=True)
def limpar_cache_redis():
    monitoramento._cliente_redis.cache_clear()
    yield
    monitoramento._cliente_redis.cache_clear()


def _banco_camara(monkeypatch, retorno):
    cursor = CursorFalso(retorno)
    monkeypatch.setattr(monitoramento, "DATABASE_URL", "postgres://teste")
    monkeypatch.setitem(sys.modules, "psycopg2", modulo_psycopg2(ConexaoFalsa(cursor)))
    return cursor


def test_camara_regular_e_filtrada_pelo_cd(monkeypatch):
    cursor = _banco_camara(monkeypatch, (3, Decimal(2), Decimal(6)))
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(2, "ADMIN", 2),
    )

    escopo, termometro, minimo, maximo = monitoramento._camara_permitida(2, 3)

    assert escopo.nivel_acesso == "ADMIN"
    assert (termometro, minimo, maximo) == (3, Decimal(2), Decimal(6))
    assert cursor.comandos[0][1] == (3, 2)
    assert "cod_cd = %s" in cursor.comandos[0][0]


def test_super_admin_consulta_camara_sem_restringir_cd(monkeypatch):
    cursor = _banco_camara(monkeypatch, (5, Decimal(-22), Decimal(-16)))
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(1, "SUPER_ADMIN", None),
    )

    monitoramento._camara_permitida(1, 11)

    assert cursor.comandos[0][1] == (11,)
    assert "cod_cd = %s" not in cursor.comandos[0][0]


def test_camara_fora_do_escopo_e_bloqueada(monkeypatch):
    _banco_camara(monkeypatch, None)
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(2, "OPERADOR", 2),
    )

    with pytest.raises(PermissionError, match="escopo permitido"):
        monitoramento._camara_permitida(2, 99)


def test_indisponibilidade_do_postgresql_tem_erro_estavel(monkeypatch):
    class ErroOperacional(Exception):
        pass

    monkeypatch.setattr(monitoramento, "DATABASE_URL", "postgres://teste")
    monkeypatch.setattr(
        monitoramento,
        "validar_acesso",
        lambda _usuario: EscopoAcesso(2, "ADMIN", 2),
    )
    banco_indisponivel = SimpleNamespace(
        OperationalError=ErroOperacional,
        connect=lambda _url: (_ for _ in ()).throw(ErroOperacional("fora")),
    )
    monkeypatch.setitem(sys.modules, "psycopg2", banco_indisponivel)

    with pytest.raises(RuntimeError, match="Banco de dados indisponível"):
        monitoramento._camara_permitida(2, 3)


def test_consulta_leitura_retorna_evento_do_termometro_autorizado(monkeypatch):
    monkeypatch.setattr(
        monitoramento,
        "_camara_permitida",
        lambda *_: (EscopoAcesso(2, "ADMIN", 2), 3, Decimal(2), Decimal(6)),
    )
    stream = [
        ("1-0", {"cod_termometro": "9", "temperatura": "10"}),
        ("2-0", {"cod_termometro": "3", "temperatura": "4.5", "data_hora": "2026-10-06T10:00:00Z"}),
    ]
    cliente = SimpleNamespace(xrevrange=lambda *args, **kwargs: stream)
    monkeypatch.setattr(monitoramento, "REDIS_URL", "redis://teste")
    redis_falso = type("RedisFalso", (), {"from_url": staticmethod(lambda *_, **__: cliente)})
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=redis_falso))

    leitura = monitoramento.consultar_leituras_temperatura(2, 3)

    assert leitura["camara_id"] == 3
    assert leitura["temperatura"] == "4.5"
    assert leitura["limite_minimo"] == "2"
    assert leitura["limite_maximo"] == "6"


def test_consulta_leitura_sem_evento_do_termometro_falha(monkeypatch):
    monkeypatch.setattr(
        monitoramento,
        "_camara_permitida",
        lambda *_: (EscopoAcesso(2, "ADMIN", 2), 3, Decimal(2), Decimal(6)),
    )
    cliente = SimpleNamespace(xrevrange=lambda *args, **kwargs: [])
    monkeypatch.setattr(monitoramento, "REDIS_URL", "redis://teste")
    redis_falso = type("RedisFalso", (), {"from_url": staticmethod(lambda *_, **__: cliente)})
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=redis_falso))

    with pytest.raises(LookupError, match="leitura recente"):
        monitoramento.consultar_leituras_temperatura(2, 3)


def test_indisponibilidade_do_redis_tem_erro_estavel(monkeypatch):
    class ErroConexaoRedis(Exception):
        pass

    monkeypatch.setattr(
        monitoramento,
        "_camara_permitida",
        lambda *_: (EscopoAcesso(2, "ADMIN", 2), 3, Decimal(2), Decimal(6)),
    )
    monkeypatch.setattr(monitoramento, "REDIS_URL", "redis://teste")
    cliente = SimpleNamespace(
        xrevrange=lambda *args, **kwargs: (_ for _ in ()).throw(ErroConexaoRedis("fora"))
    )
    redis_falso = type("RedisFalso", (), {"from_url": staticmethod(lambda *_, **__: cliente)})
    monkeypatch.setitem(
        sys.modules,
        "redis",
        SimpleNamespace(
            Redis=redis_falso,
            exceptions=SimpleNamespace(ConnectionError=ErroConexaoRedis),
        ),
    )

    with pytest.raises(RuntimeError, match="Redis indisponível"):
        monitoramento.consultar_leituras_temperatura(2, 3)


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


def test_tool_de_monitoramento_mantem_usuario_no_backend(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        monitoramento,
        "consultar_leituras_temperatura",
        lambda usuario_id, camara_id: chamadas.append((usuario_id, camara_id)) or {"temperatura": "4"},
    )

    ferramenta = monitoramento.criar_tool_consultar_leitura_recente(2)
    resposta = ferramenta.invoke({"camara_id": 3})

    assert resposta == {"temperatura": "4"}
    assert chamadas == [(2, 3)]
