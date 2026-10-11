from unittest.mock import Mock, call

import pytest
from app.tools import monitoramento
from app.tools.access import EscopoAcesso
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from pydantic import ValidationError
from tests.conftest import banco_sql


def banco(monkeypatch, nivel="ADMIN", cd=2, camaras=None):
    cursor, conexao = banco_sql(retornos=camaras)
    monkeypatch.setattr(monitoramento, "get_conn", Mock(return_value=conexao))
    monkeypatch.setattr(monitoramento, "validar_acesso", lambda usuario: EscopoAcesso(usuario, nivel, cd))
    return cursor, conexao


def redis(monkeypatch, paginas):
    cliente = Mock()
    cliente.xrevrange.side_effect = paginas
    monkeypatch.setattr(monitoramento, "_cliente_redis", Mock(return_value=cliente))
    return cliente.xrevrange


@pytest.mark.parametrize("nivel", ["ADMIN", "GESTOR", "OPERADOR"])
def test_todas_temperaturas_consultam_so_camaras_do_cd(monkeypatch, nivel):
    cursor, conexao = banco(monkeypatch, nivel, camaras=[(3, "Modelo A", "Setor 1", 3, 2, 6)])
    redis(monkeypatch, [[
        ("4-0", {"cod_termometro": "99", "temperatura": "SIGILOSO"}),
        ("3-0", {"cod_termometro": "3", "temperatura": "4", "data_hora": "agora"}),
        ("2-0", {"cod_termometro": "3", "temperatura": "5", "data_hora": "antes"}),
    ]])
    resultado = monitoramento.consultar_temperaturas_permitidas(2, todas=True)
    assert resultado == {"status": "ok", "camaras": [{
        "modelo": "Modelo A", "localizacao": "Setor 1", "limite_minimo": "2",
        "limite_maximo": "6", "temperatura": "4", "data_hora": "agora", "leitura_disponivel": True,
    }]}
    assert cursor.execute.call_args.args[1] == (2,)
    assert "cod_cd = %s" in cursor.execute.call_args.args[0]
    conexao.close.assert_called_once()
    assert "SIGILOSO" not in str(resultado)
    assert not {"camara_id", "termometro", "evento_redis", "cd"} & resultado["camaras"][0].keys()


def test_super_admin_temperaturas_sem_filtro_cd(monkeypatch):
    cursor, _ = banco(monkeypatch, "SUPER_ADMIN", None)
    assert monitoramento.consultar_temperaturas_permitidas(1, todas=True)["camaras"] == []
    assert cursor.execute.call_args.args[1] == ()
    assert "cod_cd = %s" not in cursor.execute.call_args.args[0]


def test_sem_camaras_nao_consulta_redis(monkeypatch):
    banco(monkeypatch)
    monkeypatch.setattr(monitoramento, "_cliente_redis", lambda: pytest.fail("Não acessar Redis"))
    assert monitoramento.consultar_temperaturas_permitidas(2, todas=True)["camaras"] == []


def test_sem_leitura_inclui_camara_sem_inventar_temperatura(monkeypatch):
    banco(monkeypatch, camaras=[(3, "Modelo A", "Setor 1", 3, 2, 6)])
    redis(monkeypatch, [[]])
    resultado = monitoramento.consultar_temperaturas_permitidas(2, todas=True)["camaras"][0]
    assert resultado["temperatura"] is None
    assert resultado["data_hora"] is None
    assert resultado["leitura_disponivel"] is False


def test_varredura_busca_sensor_fora_do_primeiro_lote(monkeypatch):
    primeira = [(f"{2000 - i}-0", {"cod_termometro": "99"}) for i in range(1000)]
    chamadas = redis(monkeypatch, [primeira, [
        primeira[-1], ("1000-0", {"cod_termometro": "3", "temperatura": "4"}),
    ]])
    resultado = monitoramento._ultimas_leituras_permitidas({"3"})
    assert resultado["3"]["temperatura"] == "4"
    assert chamadas.call_args_list[1].kwargs["max"] == primeira[-1][0]


def test_sem_eventos_na_proxima_pagina_termina(monkeypatch):
    primeira = [(f"{2000 - i}-0", {"cod_termometro": "99"}) for i in range(1000)]
    redis(monkeypatch, [primeira, []])
    assert monitoramento._ultimas_leituras_permitidas({"3"}) == {}


@pytest.mark.parametrize("erro", ["ConnectionError", "TimeoutError"])
def test_falha_redis_nao_vira_resultado_vazio(monkeypatch, erro):
    import redis as redis_lib

    cliente = Mock()
    cliente.xrevrange.side_effect = getattr(redis_lib.exceptions, erro)("falha")
    monkeypatch.setattr(monitoramento, "_cliente_redis", Mock(return_value=cliente))
    with pytest.raises(RuntimeError, match="Redis indisponível"):
        monitoramento._ultimas_leituras_permitidas({"3"})


@pytest.mark.parametrize("nivel,cd", [("OPERADOR", None), ("DESCONHECIDO", 2)])
def test_usuario_sem_escopo_nao_consulta_bancos(monkeypatch, nivel, cd):
    banco(monkeypatch, nivel, cd)
    monkeypatch.setattr(monitoramento, "get_conn", lambda: pytest.fail("Sem consulta sem escopo"))
    with pytest.raises(PermissionError):
        monitoramento.consultar_temperaturas_permitidas(2, todas=True)
    with pytest.raises(PermissionError):
        monitoramento.consultar_temperaturas_permitidas(2, modelo="Modelo A")



@pytest.mark.parametrize("filtros", [
    {"camara_id": 3}, {"modelo": "Modelo A"}, {"localizacao": "Setor 1"},
    {"modelo": "Modelo A", "localizacao": "Setor 1"}, {"todas": True},
])
def test_selecoes_compartilham_resultado_sem_ids(monkeypatch, filtros):
    banco(monkeypatch, camaras=[(3, "Modelo A", "Setor 1", 9, 2, 6)])
    redis(monkeypatch, [[("1-0", {"cod_termometro": "9", "temperatura": "4", "data_hora": "agora"})]])
    resultado = monitoramento.consultar_temperaturas_permitidas(2, **filtros)
    assert resultado["status"] == "ok"
    assert resultado["camaras"][0]["temperatura"] == "4"
    assert not {"camara_id", "termometro", "usuario_id"} & resultado["camaras"][0].keys()


def test_filtros_sql_parametrizados_e_intersecao(monkeypatch):
    cursor, conexao = banco(monkeypatch)
    texto = "%' OR TRUE; --"
    resultado = monitoramento.consultar_temperaturas_permitidas(
        2, camara_id=3, modelo=texto, localizacao=" Setor 1 ",
    )
    sql, parametros = cursor.execute.call_args.args
    assert parametros == (2, 3, texto, "Setor 1")
    assert texto not in sql
    assert "cod_cd = %s AND id = %s AND LOWER(modelo) = LOWER(%s) AND LOWER(localizacao) = LOWER(%s)" in sql
    assert resultado["status"] == "nao_encontrada"
    conexao.close.assert_called_once()


@pytest.mark.parametrize("argumentos", [
    {}, {"todas": False}, {"modelo": " "}, {"localizacao": ""},
    {"camara_id": True}, {"camara_id": "3"}, {"todas": "true"},
    {"todas": True, "camara_id": 3}, {"todas": True, "modelo": "A"},
    {"modelo": "A", "usuario_id": 9},
])
def test_schema_rejeita_selecao_invalida(argumentos):
    with pytest.raises(ValidationError):
        monitoramento.ConsultarTemperaturasArgs(**argumentos)


@pytest.mark.parametrize("argumentos", [{}, {"modelo": " "}, {"todas": True, "camara_id": 3}])
def test_selecao_invalida_nao_consulta_bancos(monkeypatch, argumentos):
    monkeypatch.setattr(monitoramento, "get_conn", lambda: pytest.fail("Entrada inválida"))
    with pytest.raises(ValidationError):
        monitoramento.consultar_temperaturas_permitidas(2, **argumentos)


@pytest.mark.parametrize("camaras,status", [
    ([], "nao_encontrada"),
    ([(3, "A", "Setor 1", 9, 2, 6), (4, "A", "Setor 2", 10, 2, 6)], "ambigua"),
])
def test_nao_encontrada_ou_ambigua_nao_amplia_consulta(monkeypatch, camaras, status):
    cursor, _ = banco(monkeypatch, camaras=camaras)
    monkeypatch.setattr(monitoramento, "_cliente_redis", lambda: pytest.fail("Não escolher câmara"))
    resultado = monitoramento.consultar_temperaturas_permitidas(2, modelo="A")
    assert resultado["status"] == status
    cursor.execute.assert_called_once()
    assert "camara_id" not in str(resultado)


def test_listagem_usa_consulta_comum_sem_redis(monkeypatch):
    cursor, _ = banco(monkeypatch, camaras=[(3, "A", "Setor 1", 9, 2, 6)])
    monkeypatch.setattr(monitoramento, "_cliente_redis", lambda: pytest.fail("Somente cadastro"))
    token = definir_usuario_contexto(2)
    try:
        resultado = monitoramento.listar_camaras_responsaveis.invoke({})
    finally:
        restaurar_usuario_contexto(token)
    assert resultado == [{"modelo": "A", "localizacao": "Setor 1", "limite_minimo": "2", "limite_maximo": "6"}]
    assert cursor.execute.call_args.args[1] == (2,)


def test_tool_usa_usuario_interno_e_rejeita_identidade_externa(monkeypatch):
    consultar = Mock(return_value={"status": "ok", "camaras": []})
    monkeypatch.setattr(monitoramento, "consultar_temperaturas_permitidas", consultar)
    token = definir_usuario_contexto(2)
    try:
        monitoramento.consultar_temperaturas.invoke({"camara_id": 3})
        monitoramento.consultar_temperaturas.invoke({"todas": True})
        with pytest.raises(ValidationError):
            monitoramento.consultar_temperaturas.invoke({"todas": True, "usuario_id": 9})
    finally:
        restaurar_usuario_contexto(token)
    assert consultar.call_args_list == [
        call(2, 3, None, None, False), call(2, None, None, None, True),
    ]
    with pytest.raises(RuntimeError, match="autenticado"):
        monitoramento.consultar_temperaturas.invoke({"todas": True})


def test_tools_sem_aliases_redundantes():
    assert [t.name for t in monitoramento.TOOLS] == [
        "consultar_temperaturas", "listar_camaras_responsaveis", "consultar_alertas_atuais_do_usuario",
    ]


def test_falha_sql_fecha_conexao(monkeypatch):
    cursor, conexao = banco(monkeypatch)
    cursor.execute.side_effect = RuntimeError("Banco indisponível")
    with pytest.raises(RuntimeError, match="Banco indisponível"):
        monitoramento.consultar_temperaturas_permitidas(2, camara_id=3)
    conexao.close.assert_called_once()


@pytest.mark.parametrize("nivel", ["ADMIN", "GESTOR", "OPERADOR"])
def test_id_nao_encontrado_nao_remove_restricao_de_cd(monkeypatch, nivel):
    cursor, _ = banco(monkeypatch, nivel)
    monkeypatch.setattr(monitoramento, "_cliente_redis", lambda: pytest.fail("Sem acesso à leitura"))
    resultado = monitoramento.consultar_temperaturas_permitidas(2, camara_id=99)
    assert resultado["status"] == "nao_encontrada"
    assert cursor.execute.call_args.args[1] == (2, 99)
    assert "cod_cd = %s AND id = %s" in cursor.execute.call_args.args[0]
    cursor.execute.assert_called_once()


def test_todas_inclui_camaras_sem_sensor_sem_inventar_leitura(monkeypatch):
    banco(monkeypatch, camaras=[
        (3, "A", "Setor 1", 9, 2, 6), (4, "B", "Setor 2", None, 2, 6),
    ])
    redis(monkeypatch, [[("1-0", {"cod_termometro": "9", "temperatura": "4"})]])
    resultado = monitoramento.consultar_temperaturas_permitidas(2, todas=True)
    assert len(resultado["camaras"]) == 2
    assert resultado["camaras"][0]["leitura_disponivel"] is True
    assert resultado["camaras"][1]["leitura_disponivel"] is False
    assert resultado["camaras"][1]["temperatura"] is None


@pytest.mark.parametrize("args", [{"camara_id": 3}, {"modelo": "A"}, {"todas": True}])
def test_agente_invoca_tool_unificada(monkeypatch, args):
    from app import graph
    from langchain_core.messages import AIMessage

    consultar = Mock(return_value={"status": "ok", "camaras": []})
    agente = Mock()
    monkeypatch.setattr(graph, "obter_modelos", Mock(return_value=(Mock(), Mock())))
    monkeypatch.setattr(monitoramento, "consultar_temperaturas_permitidas", consultar)

    def executar(entrada):
        assert entrada["messages"][-1].content == "Consulte"
        assert monitoramento.consultar_temperaturas.invoke(args)["status"] == "ok"
        return {"messages": [AIMessage(content="Resposta validada")]}

    agente.invoke.side_effect = executar
    criar = Mock(return_value=agente)
    monkeypatch.setattr("langchain.agents.create_agent", criar)
    token = definir_usuario_contexto(2)
    try:
        resultado = graph._executar_especialista({
            "rota": "monitoramento", "usuario_id": 2, "pergunta_original": "Consulte",
        })
    finally:
        restaurar_usuario_contexto(token)
    consultar.assert_called_once_with(
        2, args.get("camara_id"), args.get("modelo"), None, args.get("todas", False),
    )
    assert monitoramento.consultar_temperaturas in criar.call_args.kwargs["tools"]
    assert "consultar_temperaturas" in criar.call_args.kwargs["system_prompt"]
    assert resultado["respostas_agentes"] == [{"agente": "monitoramento", "resposta": "Resposta validada"}]
