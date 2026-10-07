from __future__ import annotations

from types import SimpleNamespace

import pytest
from app import graph


class ModeloFalso:
    def __init__(self, conteudo):
        self.conteudo = conteudo
        self.mensagens = None

    def invoke(self, mensagens):
        self.mensagens = mensagens
        return SimpleNamespace(content=self.conteudo)


def test_rota_texto_aceita_apenas_rotas_aprovadas():
    assert graph._rota_texto("ROUTE=monitoramento") == "monitoramento"
    assert graph._rota_texto("route=fora_do_escopo") == "orquestrador"
    assert graph._rota_texto("resposta livre") == "orquestrador"


def test_especialistas_tem_ordem_estavel_no_grafo():
    assert graph.ROTAS_ESPECIALISTAS == (
        "monitoramento",
        "predicao",
        "diagnostico",
        "relatorios",
        "faq",
    )


def test_roteador_registra_rota_e_agente(monkeypatch):
    rapido = ModeloFalso("ROUTE=faq")
    monkeypatch.setattr(graph, "obter_modelos", lambda: (ModeloFalso(""), rapido))

    resultado = graph._rotear({"pergunta_original": "Como funciona?"})

    assert resultado == {"rota": "faq", "agentes_chamados": ["roteador"]}


def test_especialista_sem_tool_repassa_pergunta_original(monkeypatch):
    modelo = ModeloFalso("A FAQ ainda nao esta preenchida.")
    monkeypatch.setattr(graph, "obter_modelos", lambda: (modelo, ModeloFalso("")))

    resultado = graph._executar_especialista({"rota": "faq", "pergunta_original": "Onde encontro ajuda?"})

    assert resultado["agentes_chamados"] == ["faq"]
    assert resultado["respostas_agentes"] == [{"agente": "faq", "resposta": "A FAQ ainda nao esta preenchida."}]


def test_monitoramento_sem_usuario_autenticado_e_bloqueado():
    with pytest.raises(RuntimeError, match="usuário autenticado"):
        graph._executar_especialista(
            {"rota": "monitoramento", "pergunta_original": "Temperatura da câmara 3?"}
        )


def test_orquestrador_recebe_pergunta_e_resposta_do_especialista(monkeypatch):
    modelo = ModeloFalso("Resposta final")
    monkeypatch.setattr(graph, "obter_modelos", lambda: (modelo, ModeloFalso("")))
    estado = {
        "pergunta_original": "Temperatura da camara 3?",
        "respostas_agentes": [{"agente": "monitoramento", "resposta": "4 C"}],
    }

    resultado = graph._orquestrar(estado)

    assert resultado == {"resposta": "Resposta final", "agentes_chamados": ["orquestrador"]}
    assert "Temperatura da camara 3?" in modelo.mensagens[-1].content
    assert "4 C" in modelo.mensagens[-1].content


def test_executar_fluxo_salva_pergunta_e_resposta(monkeypatch):
    class FluxoFalso:
        def invoke(self, estado):
            assert estado["usuario_id"] == 2
            return {"resposta": "Resposta final", "agentes_chamados": ["roteador", "orquestrador"]}

    chamadas = []
    monkeypatch.setattr(graph, "FLUXO_SKADI", FluxoFalso())
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", lambda *args: chamadas.append(args))

    resposta, agentes = graph.executar_fluxo_skadi("oi", 2)

    assert resposta == "Resposta final"
    assert agentes == ["roteador", "orquestrador"]
    assert chamadas == [
        (2, "usuario", "oi", "texto"),
        (2, "assistente", "Resposta final", "texto", "orquestrador"),
    ]


def test_executar_fluxo_sem_usuario_nao_persiste_memoria(monkeypatch):
    class FluxoFalso:
        def invoke(self, _estado):
            return {"resposta": "Resposta final", "agentes_chamados": []}

    chamadas = []
    monkeypatch.setattr(graph, "FLUXO_SKADI", FluxoFalso())
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", lambda *args: chamadas.append(args))

    graph.executar_fluxo_skadi("oi")

    assert chamadas == []


def test_executar_fluxo_reutiliza_grafo_ja_compilado(monkeypatch):
    class FluxoFalso:
        def __init__(self):
            self.execucoes = 0

        def invoke(self, _estado):
            self.execucoes += 1
            return {"resposta": "Resposta", "agentes_chamados": []}

    fluxo = FluxoFalso()
    monkeypatch.setattr(graph, "FLUXO_SKADI", fluxo)
    monkeypatch.setattr(
        graph,
        "construir_fluxo",
        lambda: (_ for _ in ()).throw(AssertionError("O grafo nao deve ser recompilado.")),
    )
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", lambda *_: None)

    graph.executar_fluxo_skadi("primeira", 2)
    graph.executar_fluxo_skadi("segunda", 2)

    assert fluxo.execucoes == 2
