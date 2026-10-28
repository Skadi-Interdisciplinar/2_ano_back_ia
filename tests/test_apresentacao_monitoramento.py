import json

from app.apresentacao_monitoramento import apresentar_consultas
from langchain_core.messages import ToolMessage


def test_apresenta_temperatura_e_limites_consultados():
    dados = {"status": "ok", "camaras": [{
        "modelo": "FM-400", "localizacao": "Câmara 03", "temperatura": "4.00",
        "data_hora": "2026-10-14T09:04:00-03:00", "leitura_disponivel": True,
        "limite_minimo": "2.00", "limite_maximo": "6.00",
    }]}
    mensagem = ToolMessage(content=json.dumps(dados), name="consultar_temperaturas", tool_call_id="1")

    resposta = apresentar_consultas([mensagem])

    assert "4.00 °C" in resposta
    assert "2.00 a 6.00 °C" in resposta


def test_informa_quando_nao_ha_alertas_permitidos():
    mensagem = ToolMessage(content="[]", name="consultar_alertas_atuais_do_usuario", tool_call_id="1")

    resposta = apresentar_consultas([mensagem])

    assert "Não encontrei alertas" in resposta
