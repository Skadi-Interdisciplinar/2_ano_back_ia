from unittest.mock import MagicMock, Mock

import pytest
from app.tools import monitoramento
from app.tools.access import EscopoAcesso
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto


def test_consulta_a_ultima_leitura_da_camara_permitida(monkeypatch):
    camara = {
        "camara_id": 3, "modelo": "FM-400", "localizacao": "Câmara 03",
        "termometro": 9, "limite_minimo": "2.00", "limite_maximo": "6.00",
    }
    consultar_camaras = Mock(return_value=[camara])
    leituras = Mock(return_value={"9": {"temperatura": "4.00", "data_hora": "2026-10-14T09:04:00-03:00"}})
    monkeypatch.setattr(monitoramento, "consultar_camaras_permitidas", consultar_camaras)
    monkeypatch.setattr(monitoramento, "_ultimas_leituras_permitidas", leituras)

    resultado = monitoramento.consultar_temperaturas_permitidas(12, camara_id=3)

    assert resultado["camaras"][0]["temperatura"] == "4.00"
    assert resultado["camaras"][0]["leitura_disponivel"] is True
    consultar_camaras.assert_called_once_with(12, 3, None, None)


def test_informa_leitura_invalida_sem_inventar_temperatura(monkeypatch):
    camara = {
        "camara_id": 3, "modelo": "FM-400", "localizacao": "Câmara 03",
        "termometro": 9, "limite_minimo": "2.00", "limite_maximo": "6.00",
    }
    monkeypatch.setattr(monitoramento, "consultar_camaras_permitidas", Mock(return_value=[camara]))
    monkeypatch.setattr(monitoramento, "_ultimas_leituras_permitidas", Mock(return_value={
        "9": {"temperatura": "NaN", "data_hora": "2026-10-14T09:04:00-03:00"}
    }))

    resultado = monitoramento.consultar_temperaturas_permitidas(12, camara_id=3)

    assert resultado["camaras"][0]["temperatura"] is None
    assert resultado["camaras"][0]["leitura_invalida"] is True


def test_tool_de_alertas_usa_usuario_do_contexto(monkeypatch):
    consultar = Mock(return_value=[{"status": "ATIVO"}])
    monkeypatch.setattr(monitoramento, "consultar_alertas_atuais", consultar)
    token = definir_usuario_contexto(12)
    try:
        resultado = monitoramento.consultar_alertas_atuais_do_usuario.invoke({})
    finally:
        restaurar_usuario_contexto(token)

    assert resultado == [{"status": "ATIVO"}]
    consultar.assert_called_once_with(12)


@pytest.mark.parametrize("nivel", ["SUPER_ADMIN", "ADMIN", "GESTOR", "OPERADOR"])
def test_selecao_de_camaras_aplica_cd_antes_do_filtro(nivel):
    cursor = Mock()
    cursor.fetchall.return_value = []
    escopo = EscopoAcesso(12, nivel, None if nivel == "SUPER_ADMIN" else 2)

    monitoramento._selecionar_camaras(escopo, monitoramento.FiltrosCamaraArgs(camara_id=3), cursor=cursor)

    sql, parametros = cursor.execute.call_args.args
    assert parametros == ((3,) if nivel == "SUPER_ADMIN" else (2, 3))
    assert ("cod_cd = %s" in sql) is (nivel != "SUPER_ADMIN")


@pytest.mark.parametrize("nivel", ["SUPER_ADMIN", "ADMIN", "GESTOR", "OPERADOR"])
def test_consulta_alertas_preserva_reconhecimento_proprio_e_escopo(monkeypatch, nivel):
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    monkeypatch.setattr(monitoramento, "get_conn", Mock(return_value=conexao))
    monkeypatch.setattr(monitoramento, "validar_acesso", Mock(return_value=EscopoAcesso(12, nivel, 2)))

    monitoramento.consultar_alertas_permitidos(12, camara_id=3)

    sql, parametros = cursor.execute.call_args.args
    assert parametros[:3] == ["ATIVO", "RECONHECIDO", 12]
    assert "atendimento.cod_usuario = %s" in sql
    assert parametros[-1] == 3
    assert "UPPER(a.status) = %s" in sql
    assert ("UPPER(a.nivel_atual) = %s" in sql) is (nivel == "OPERADOR")


def test_camara_ambigua_nao_consulta_redis(monkeypatch):
    camaras = [{"modelo": "FM-400", "localizacao": local, "limite_minimo": "2", "limite_maximo": "6"}
               for local in ("Carnes", "Bebidas")]
    monkeypatch.setattr(monitoramento, "consultar_camaras_permitidas", Mock(return_value=camaras))
    redis = Mock()
    monkeypatch.setattr(monitoramento, "_ultimas_leituras_permitidas", redis)

    resultado = monitoramento.consultar_temperaturas_permitidas(12, modelo="FM-400")

    assert resultado["status"] == "ambigua"
    redis.assert_not_called()


def test_temperaturas_de_todas_as_camaras_preservam_ausencia_de_leitura(monkeypatch):
    camaras = [{"modelo": "FM-400", "localizacao": str(n), "termometro": n,
                "limite_minimo": "2", "limite_maximo": "6"} for n in (3, 4)]
    monkeypatch.setattr(monitoramento, "consultar_camaras_permitidas", Mock(return_value=camaras))
    monkeypatch.setattr(monitoramento, "_ultimas_leituras_permitidas", Mock(return_value={
        "3": {"temperatura": "4.00", "data_hora": "2026-10-29T10:00:00-03:00"},
    }))

    resultado = monitoramento.consultar_temperaturas_permitidas(12, todas=True)

    assert resultado["camaras"][0]["temperatura"] == "4.00"
    assert resultado["camaras"][1]["temperatura"] is None
    assert resultado["camaras"][1]["leitura_disponivel"] is False


def test_leitura_e_busca_nos_lotes_anteriores_do_stream(monkeypatch):
    cliente = Mock()
    cliente.xrevrange.side_effect = [
        [(f"{2000 - i}-0", {"cod_termometro": "99"}) for i in range(1000)],
        [("1000-0", {"cod_termometro": "3", "temperatura": "4", "data_hora": "2026-10-29T10:00:00"})],
    ]
    monkeypatch.setattr(monitoramento, "_cliente_redis", Mock(return_value=cliente))

    leituras = monitoramento._ultimas_leituras_permitidas({"3"})

    assert leituras["3"]["temperatura"] == "4"
    assert cliente.xrevrange.call_count == 2
