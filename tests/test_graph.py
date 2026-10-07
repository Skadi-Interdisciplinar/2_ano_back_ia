import pytest
from app import graph
from tests.conftest import ModeloFalso


def test_roteador_escolhe_rota_do_modelo(monkeypatch):
    rapido = ModeloFalso("ROUTE=faq")
    monkeypatch.setattr(graph, "obter_modelos", lambda: (ModeloFalso(""), rapido))

    resultado = graph._rotear({"pergunta_original": "Como funciona?"})

    assert resultado == {"rota": "faq", "agentes_chamados": ["roteador"]}


def test_rota_desconhecida_cai_no_orquestrador():
    assert graph._rota_texto("ROUTE=monitoramento") == "monitoramento"
    assert graph._rota_texto("ROUTE=desconhecida") == "orquestrador"


def test_especialista_responde_com_o_modelo(monkeypatch):
    modelo = ModeloFalso("A FAQ ainda nao esta preenchida.")
    monkeypatch.setattr(graph, "obter_modelos", lambda: (modelo, ModeloFalso("")))

    resultado = graph._executar_especialista(
        {"rota": "faq", "pergunta_original": "Onde encontro ajuda?"}
    )

    assert resultado["agentes_chamados"] == ["faq"]
    assert resultado["respostas_agentes"][0]["resposta"] == "A FAQ ainda nao esta preenchida."


def test_monitoramento_exige_usuario_autenticado():
    with pytest.raises(RuntimeError, match="autenticado"):
        graph._executar_especialista(
            {"rota": "monitoramento", "pergunta_original": "Temperatura da camara 3?"}
        )


def test_orquestrador_usa_contexto_do_especialista(monkeypatch):
    modelo = ModeloFalso("Resposta final")
    monkeypatch.setattr(graph, "obter_modelos", lambda: (modelo, ModeloFalso("")))

    resultado = graph._orquestrar(
        {
            "pergunta_original": "Temperatura da camara 3?",
            "respostas_agentes": [{"agente": "monitoramento", "resposta": "4 C"}],
        }
    )

    assert resultado["resposta"] == "Resposta final"
    assert "4 C" in modelo.mensagens[-1].content


def test_fluxo_persiste_conversa_quando_ha_usuario(monkeypatch):
    class FluxoFalso:
        def invoke(self, _estado):
            return {"resposta": "Resposta final", "agentes_chamados": ["roteador"]}

    salvas = []
    monkeypatch.setattr(graph, "FLUXO_SKADI", FluxoFalso())
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", lambda *args: salvas.append(args))

    resposta, agentes = graph.executar_fluxo_skadi("oi", 2)

    assert resposta == "Resposta final"
    assert agentes == ["roteador"]
    assert salvas[0][:3] == (2, "usuario", "oi")
    assert salvas[1][:3] == (2, "assistente", "Resposta final")


def test_fluxo_sem_usuario_nao_grava_memoria(monkeypatch):
    class FluxoFalso:
        def invoke(self, _estado):
            return {"resposta": "ok", "agentes_chamados": []}

    salvas = []
    monkeypatch.setattr(graph, "FLUXO_SKADI", FluxoFalso())
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", lambda *args: salvas.append(args))

    graph.executar_fluxo_skadi("oi")

    assert salvas == []
