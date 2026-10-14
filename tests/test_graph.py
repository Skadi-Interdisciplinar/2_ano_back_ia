from unittest.mock import Mock, call, patch

import pytest
from app import graph
from app.erros import SaidaModeloInvalida
from app.schemas import DecisaoRota
from app.tools import monitoramento
from app.tools.contexto import obter_usuario_contexto
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError


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


@pytest.mark.parametrize("rota", sorted(graph.ROTAS))
def test_schema_aceita_rotas_permitidas(rota):
    assert DecisaoRota(rota=rota).rota == rota


@pytest.mark.parametrize("dados", [
    {"rota": "fora_do_escopo"}, {"rota": "diagnóstico"}, {"rota": ""},
    {"rota": "diagnostico", "usuario_id": 9},
    {"rota": "diagnostico", "nivel_acesso": "SUPER_ADMIN"},
])
def test_schema_rejeita_rotas_invalidas_e_campos_de_permissao(dados):
    with pytest.raises(ValidationError):
        DecisaoRota.model_validate(dados)


def test_especialistas_tem_ordem_estavel_no_grafo():
    assert graph.ROTAS_ESPECIALISTAS == (
        "monitoramento", "predicao", "diagnostico", "relatorios", "faq",
    )


def test_roteador_registra_rota_e_agente(modelo):
    agente = Mock()
    agente.invoke.return_value = {"structured_response": {"rota": "faq"}}

    with patch("langchain.agents.create_agent", return_value=agente) as criar:
        resultado = graph._rotear({"pergunta_original": "Como funciona?"})

    assert resultado == {"rota": "faq", "agentes_chamados": ["roteador"]}
    estrategia = criar.call_args.kwargs["response_format"]
    assert estrategia.schema is DecisaoRota
    assert estrategia.handle_errors is False
    assert criar.call_args.kwargs["tools"] == []


@pytest.mark.parametrize("saida", [
    {}, {"messages": [AIMessage(content="ROUTE=diagnostico")]},
    {"structured_response": {"rota": "fora_do_escopo"}},
    {"structured_response": "resposta livre"},
    {"structured_response": {"rota": "diagnostico", "usuario_id": 9}},
])
def test_saida_invalida_nao_vira_fora_do_escopo(modelo, saida):
    agente = Mock()
    agente.invoke.return_value = saida

    with (
        patch("langchain.agents.create_agent", return_value=agente),
        pytest.raises(SaidaModeloInvalida),
    ):
        graph._rotear({"pergunta_original": "gostaria de saber a causa dos problemas na camara 3?"})


def test_falha_de_saida_estruturada_do_sdk_nao_vira_fora_do_escopo(modelo):
    from langchain.agents.structured_output import StructuredOutputError

    agente = Mock()
    agente.invoke.side_effect = StructuredOutputError("Saída interna inválida")

    with (
        patch("langchain.agents.create_agent", return_value=agente),
        pytest.raises(SaidaModeloInvalida),
    ):
        graph._rotear({"pergunta_original": "Qual a causa do problema na câmara 3?"})


def test_pergunta_de_causa_chega_ao_diagnostico(monkeypatch, modelo):
    from app.diagnostico import AnaliseDiagnostico
    from app.tools.memoria import TOOLS_MEMORIA

    pergunta = "gostaria de saber a causa dos problemas na camara 3?"
    roteador = Mock()
    roteador.invoke.return_value = {"structured_response": DecisaoRota(rota="diagnostico")}
    diagnosticar = Mock(return_value=AnaliseDiagnostico(perguntas=["Há observações sobre essa ocorrência?"]))
    monkeypatch.setattr("app.diagnostico.executar_diagnostico", diagnosticar)

    with patch("langchain.agents.create_agent", return_value=roteador) as criar:
        resposta, agentes = graph.executar_fluxo_skadi(pergunta, 2)

    assert agentes == ["roteador", "diagnostico", "orquestrador"]
    assert "atua somente" not in resposta
    assert diagnosticar.call_args.args[0][-1].content == pergunta
    assert criar.call_args.kwargs["tools"] == TOOLS_MEMORIA
    assert pergunta in criar.call_args.kwargs["system_prompt"]
    modelo.invoke.assert_not_called()


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
    roteador.invoke.return_value = {"structured_response": {"rota": "monitoramento"}}
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
