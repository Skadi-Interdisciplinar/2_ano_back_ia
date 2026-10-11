from __future__ import annotations

from types import SimpleNamespace

import pytest
from app import graph
from app.tools.contexto import obter_usuario_contexto


class ModeloFalso:
    def __init__(self, conteudo):
        self.conteudo = conteudo
        self.mensagens = None

    def invoke(self, mensagens):
        self.mensagens = mensagens
        return SimpleNamespace(content=self.conteudo)


@pytest.fixture(autouse=True)
def memoria_isolada(monkeypatch):
    monkeypatch.setattr(graph, "carregar_contexto_conversa", lambda _usuario: [])


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


def test_executar_fluxo_disponibiliza_e_limpa_usuario_para_tools(monkeypatch):
    class FluxoFalso:
        def invoke(self, _estado):
            assert obter_usuario_contexto() == 2
            return {"resposta": "Resposta", "agentes_chamados": []}

    monkeypatch.setattr(graph, "FLUXO_SKADI", FluxoFalso())
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", lambda *_: None)

    graph.executar_fluxo_skadi("oi", 2)

    with pytest.raises(RuntimeError, match="usuário autenticado"):
        obter_usuario_contexto()


def test_continuacao_recebe_historico_do_usuario_em_todo_o_grafo(monkeypatch):
    from app.tools import monitoramento
    from langchain_core.messages import AIMessage, HumanMessage

    historico = [
        {"remetente": "usuario", "conteudo": "Qual o limite mínimo da câmara 3?"},
        {"remetente": "assistente", "conteudo": "Posso consultar a câmara 3."},
    ]
    usuarios_consultados = []
    salvas = []
    rapido = ModeloFalso("ROUTE=monitoramento")
    modelo = ModeloFalso("O limite mínimo cadastrado é 2 °C.")
    monkeypatch.setattr(graph, "obter_modelos", lambda: (modelo, rapido))
    monkeypatch.setattr(
        graph, "carregar_contexto_conversa",
        lambda usuario: usuarios_consultados.append(usuario) or historico,
    )
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", lambda *args: salvas.append(args))
    monkeypatch.setattr(
        monitoramento, "consultar_temperaturas_permitidas",
        lambda usuario, camara, *_: {"status": "ok", "camaras": [{"limite_minimo": "2"}]} if (usuario, camara) == (2, 3) else {},
    )
    mensagens_especialista = []

    def criar_agente_falso(**kwargs):
        if kwargs["model"] is rapido:
            class RoteadorFalso:
                def invoke(self, entrada):
                    rapido.mensagens = [None, *entrada["messages"]]
                    return {"messages": [AIMessage(content=rapido.conteudo)]}
            return RoteadorFalso()
        assert monitoramento.consultar_temperaturas in kwargs["tools"]
        assert "limites" in kwargs["system_prompt"]

        class AgenteFalso:
            def invoke(self, entrada):
                mensagens_especialista.extend(entrada["messages"])
                dados = monitoramento.consultar_temperaturas.invoke({"camara_id": 3})
                assert dados["camaras"][0]["limite_minimo"] == "2"
                return {"messages": [AIMessage(content="Limite mínimo cadastrado: 2 °C.")]}

        return AgenteFalso()

    monkeypatch.setattr("langchain.agents.create_agent", criar_agente_falso)

    resposta, agentes = graph.executar_fluxo_skadi("consulte", 2)

    assert usuarios_consultados == [2]
    assert agentes == ["roteador", "monitoramento", "orquestrador"]
    assert resposta == modelo.conteudo
    assert isinstance(rapido.mensagens[1], HumanMessage)
    assert isinstance(rapido.mensagens[2], AIMessage)
    assert [item.content for item in mensagens_especialista] == [
        historico[0]["conteudo"], historico[1]["conteudo"], "consulte",
    ]
    assert "câmara 3" in modelo.mensagens[-1].content
    assert salvas[0] == (2, "usuario", "consulte", "texto")


def test_falha_ao_carregar_memoria_limpa_contexto_e_nao_chama_modelo(monkeypatch):
    monkeypatch.setattr(
        graph, "carregar_contexto_conversa",
        lambda _usuario: (_ for _ in ()).throw(RuntimeError("Mongo indisponível")),
    )

    with pytest.raises(RuntimeError, match="Mongo indisponível"):
        graph.executar_fluxo_skadi("consulte", 2)

    with pytest.raises(RuntimeError, match="usuário autenticado"):
        obter_usuario_contexto()
