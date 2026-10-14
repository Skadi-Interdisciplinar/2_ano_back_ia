from datetime import timedelta
from decimal import Decimal
from itertools import pairwise
from uuid import UUID

from app.modelos_predicao import momento, treinar_modelo
from app.predicao import apresentar_predicao
from scripts.simular_predicao import gerar_leituras

LOTE = UUID("d774ef2e-0964-4496-8b54-689c94722133")
FIM = "2026-10-14T08:00:00-03:00"


def test_lote_tem_dois_dias_cadencia_e_identificacao():
    eventos = gerar_leituras(FIM, LOTE)
    horarios = [momento(e["data_hora"]) for e in eventos]
    assert len(eventos) == 577
    assert horarios[-1] - horarios[0] == timedelta(days=2)
    assert all(b - a == timedelta(minutes=5) for a, b in pairwise(horarios))
    assert len({e["id_evento_redis"] for e in eventos}) == 577
    assert all(e["origem"] == "SIMULADO" and e["cod_termometro"] == "3" for e in eventos)
    assert gerar_leituras(FIM, LOTE) == eventos


def test_cenarios_aprovados_e_sem_lacunas():
    eventos = gerar_leituras(FIM, LOTE)
    assert {e["cenario"] for e in eventos} == {
        "normal_oscilante", "subida_recuperacao", "queda_recuperacao", "picos_pontuais",
    }
    valores = [Decimal(e["temperatura"]) for e in eventos]
    assert min(valores) == 0 and max(valores) == 8
    normais = [Decimal(e["temperatura"]) for e in eventos if e["cenario"] == "normal_oscilante"]
    assert min(normais) == 3 and max(normais) == 5
    linhas = [(e["temperatura"], e["data_hora"]) for e in eventos]
    modelo = treinar_modelo(linhas, camara_id=3, termometro_id=3,
                           cadencia_segundos=300, inicio_coleta=momento(eventos[0]["data_hora"]),
                           horizontes_minutos=[30])
    assert modelo.status == "EM_REVISAO"
    assert modelo.leituras_treino == 461
    assert modelo.leituras_avaliacao == 116
    assert modelo.metricas[0].casos == 111


def test_tool_e_apresentacao_sinalizam_modelo_simulado(contexto, monkeypatch):
    from app.tools import predicao as tools

    modelo = tools.carregar_modelo.return_value
    tools.carregar_modelo.return_value = modelo.model_copy(update={"lote_simulacao": LOTE})
    saida = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    assert saida["dados_simulados"] is True
    texto = apresentar_predicao(contexto.resultados[saida["referencia"]])
    assert "simulados" in texto
    assert "não representam medições reais" in texto


def test_monitoramento_preserva_marcacao_do_evento(monkeypatch):
    from unittest.mock import Mock

    from app.tools import monitoramento

    cliente = Mock()
    cliente.xrevrange.return_value = [("1-0", {"cod_termometro": "3", "temperatura": "4",
                                            "data_hora": FIM, "origem": "SIMULADO"})]
    monkeypatch.setattr(monitoramento, "_cliente_redis", Mock(return_value=cliente))
    camara = {"modelo": "A", "localizacao": "B", "termometro": 3,
              "limite_minimo": "2", "limite_maximo": "6"}
    monkeypatch.setattr(monitoramento, "consultar_camaras_permitidas", Mock(return_value=[camara]))
    resposta = monitoramento.consultar_temperaturas_permitidas(2, camara_id=3)
    assert resposta["camaras"][0]["origem_leitura"] == "SIMULADO"
