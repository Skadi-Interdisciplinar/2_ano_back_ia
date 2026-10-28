from unittest.mock import Mock

from app.tools import monitoramento
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
