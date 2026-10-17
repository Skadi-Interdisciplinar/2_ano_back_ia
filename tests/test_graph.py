from unittest.mock import Mock, call, patch

import pytest
from app import graph
from app.tools import monitoramento
from app.tools.contexto import obter_usuario_contexto
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture(autouse=True)
def memoria_isolada(monkeypatch):
    monkeypatch.setattr(graph, "carregar_contexto_conversa", Mock(return_value=[]))
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", Mock())


@pytest.fixture
def modelo(monkeypatch):
    modelo = Mock()
    modelo.invoke.return_value = AIMessage(content="Resposta final")
    monkeypatch.setattr(graph, "obter_modelos", Mock(return_value=(modelo, modelo)))
    return modelo


@pytest.fixture
def fluxo(monkeypatch):
    fluxo = Mock()
    fluxo.invoke.return_value = {
        "resposta": "Resposta final", "agentes_chamados": ["roteador", "orquestrador"],
    }
    monkeypatch.setattr(graph, "FLUXO_SKADI", fluxo)
    return fluxo


def test_rota_texto_aceita_apenas_rotas_aprovadas():
    assert graph._rota_texto("ROUTE=monitoramento") == "monitoramento"
    assert graph._rota_texto("route=fora_do_escopo") == "orquestrador"
    assert graph._rota_texto("resposta livre") == "orquestrador"


def test_especialistas_tem_ordem_estavel_no_grafo():
    assert graph.ROTAS_ESPECIALISTAS == (
        "monitoramento", "predicao", "diagnostico", "relatorios", "faq",
    )


def test_roteador_registra_rota_e_agente(modelo):
    modelo.invoke.return_value = AIMessage(content="ROUTE=faq")

    resultado = graph._rotear({"pergunta_original": "Como funciona?"})

    assert resultado == {"rota": "faq", "agentes_chamados": ["roteador"]}


def test_especialista_sem_tool_repassa_pergunta_original(modelo):
    modelo.invoke.return_value = AIMessage(content="A FAQ ainda nao esta preenchida.")

    resultado = graph._executar_especialista({
        "rota": "faq", "pergunta_original": "Onde encontro ajuda?",
    })

    assert resultado["agentes_chamados"] == ["faq"]
    assert resultado["respostas_agentes"] == [
        {"agente": "faq", "resposta": "A FAQ ainda nao esta preenchida."},
    ]
    assert modelo.invoke.call_args.args[0][-1].content == "Onde encontro ajuda?"


def test_monitoramento_sem_usuario_autenticado_e_bloqueado():
    with pytest.raises(RuntimeError, match="usuário autenticado"):
        graph._executar_especialista({
            "rota": "monitoramento", "pergunta_original": "Temperatura da câmara 3?",
        })


def test_orquestrador_recebe_pergunta_e_resposta_do_especialista(modelo):
    estado = {
        "pergunta_original": "Temperatura da camara 3?",
        "respostas_agentes": [{"agente": "monitoramento", "resposta": "4 C"}],
    }

    resultado = graph._orquestrar(estado)

    assert resultado == {"resposta": "Resposta final", "agentes_chamados": ["orquestrador"]}
    mensagem = modelo.invoke.call_args.args[0][-1].content
    assert "Temperatura da camara 3?" in mensagem
    assert "4 C" in mensagem


def test_executar_fluxo_salva_pergunta_e_resposta(fluxo):
    resposta, agentes = graph.executar_fluxo_skadi("oi", 2)

    assert resposta == "Resposta final"
    assert agentes == ["roteador", "orquestrador"]
    assert fluxo.invoke.call_args.args[0]["usuario_id"] == 2
    assert graph.salvar_mensagem_conversa.call_args_list == [
        call(2, "usuario", "oi", "texto"),
        call(2, "assistente", "Resposta final", "texto", "orquestrador"),
    ]


def test_executar_fluxo_sem_usuario_nao_persiste_memoria(fluxo):
    graph.executar_fluxo_skadi("oi")

    graph.salvar_mensagem_conversa.assert_not_called()


def test_executar_fluxo_reutiliza_grafo_ja_compilado(fluxo):
    with patch.object(graph, "construir_fluxo") as construir:
        graph.executar_fluxo_skadi("primeira", 2)
        graph.executar_fluxo_skadi("segunda", 2)

    construir.assert_not_called()
    assert fluxo.invoke.call_count == 2


def test_executar_fluxo_disponibiliza_e_limpa_usuario_para_tools(fluxo):
    def executar(estado):
        assert obter_usuario_contexto() == 2
        return {"resposta": "Resposta", "agentes_chamados": []}

    fluxo.invoke.side_effect = executar
    graph.executar_fluxo_skadi("oi", 2)

    with pytest.raises(RuntimeError, match="usuário autenticado"):
        obter_usuario_contexto()


def test_continuacao_recebe_historico_do_usuario_em_todo_o_grafo(monkeypatch, modelo):
    historico = [
        {"remetente": "usuario", "conteudo": "Qual o limite mínimo da câmara 3?"},
        {"remetente": "assistente", "conteudo": "Posso consultar a câmara 3."},
    ]
    graph.carregar_contexto_conversa.return_value = historico
    roteador = Mock()
    roteador.invoke.return_value = {"messages": [AIMessage(content="ROUTE=monitoramento")]}
    especialista = Mock()
    consultar = Mock(return_value={"status": "ok", "camaras": [{"limite_minimo": "2"}]})
    monkeypatch.setattr(monitoramento, "consultar_temperaturas_permitidas", consultar)

    def executar(entrada):
        dados = monitoramento.consultar_temperaturas.invoke({"camara_id": 3})
        assert dados["camaras"][0]["limite_minimo"] == "2"
        return {"messages": [AIMessage(content="Limite mínimo cadastrado: 2 °C.")]}

    especialista.invoke.side_effect = executar
    with patch("langchain.agents.create_agent", side_effect=[roteador, especialista]) as criar:
        resposta, agentes = graph.executar_fluxo_skadi("consulte", 2)

    graph.carregar_contexto_conversa.assert_called_once_with(2)
    assert resposta == "Resposta final"
    assert agentes == ["roteador", "monitoramento", "orquestrador"]
    consultar.assert_called_once_with(2, 3, None, None, False)
    assert monitoramento.consultar_temperaturas in criar.call_args.kwargs["tools"]
    assert "limites" in criar.call_args.kwargs["system_prompt"]
    for agente in [roteador, especialista]:
        mensagens = agente.invoke.call_args.args[0]["messages"]
        assert isinstance(mensagens[0], HumanMessage)
        assert isinstance(mensagens[1], AIMessage)
        assert [m.content for m in mensagens] == [
            historico[0]["conteudo"], historico[1]["conteudo"], "consulte",
        ]
    assert "câmara 3" in modelo.invoke.call_args.args[0][-1].content
    assert graph.salvar_mensagem_conversa.call_args_list[0] == call(
        2, "usuario", "consulte", "texto",
    )


def test_falha_ao_carregar_memoria_limpa_contexto_e_nao_chama_modelo(fluxo, modelo):
    graph.carregar_contexto_conversa.side_effect = RuntimeError("Mongo indisponível")

    with pytest.raises(RuntimeError, match="Mongo indisponível"):
        graph.executar_fluxo_skadi("consulte", 2)

    fluxo.invoke.assert_not_called()
    modelo.invoke.assert_not_called()
    with pytest.raises(RuntimeError, match="usuário autenticado"):
        obter_usuario_contexto()
