import json

from app.apresentacao_monitoramento import apresentar_consultas, resumir_alertas
from langchain_core.messages import ToolMessage


def test_apresenta_temperatura_e_limites_consultados():
    dados = {"status": "ok", "camaras": [{
        "modelo": "FM-400", "localizacao": "Câmara 03", "temperatura": "4.00",
        "data_hora": "2026-10-14T09:04:00-03:00", "leitura_disponivel": True,
        "limite_minimo": "2.00", "limite_maximo": "6.00",
    }]}
    mensagem = ToolMessage(content=json.dumps(dados), name="consultar_temperaturas", tool_call_id="1")

    resposta = apresentar_consultas([mensagem])

    assert resposta.startswith("Claro!")
    assert "4.00 °C" in resposta
    assert "2.00 a 6.00 °C" in resposta


def test_informa_quando_nao_ha_alertas_permitidos():
    mensagem = ToolMessage(content="[]", name="consultar_alertas_atuais_do_usuario", tool_call_id="1")

    resposta = apresentar_consultas([mensagem])

    assert "não encontrei alertas" in resposta.casefold()


def test_resumo_agrupa_sem_perder_alertas_ou_trocar_gravidade():
    alertas = [
        {"camara": "Carnes", "tipo": "temperatura", "gravidade": "urgente", "status": "ativo", "data_hora": "2026-10-29 10:00:00"},
        {"camara": "Carnes", "tipo": "temperatura", "gravidade": "urgente", "status": "ativo", "data_hora": "2026-10-29 11:00:00"},
        {"camara": "Carnes", "tipo": "temperatura", "gravidade": "crítica", "status": "reconhecido", "data_hora": "2026-10-29 12:00:00"},
    ]

    grupos = resumir_alertas(alertas)

    assert sum(grupo["quantidade"] for grupo in grupos) == 3
    assert grupos[0]["gravidade"] == "urgente"
    assert grupos[0]["primeiro_horario"] == "2026-10-29 10:00:00"
    assert grupos[0]["ultimo_horario"] == "2026-10-29 11:00:00"
    assert grupos[1]["gravidade"] == "crítica"
