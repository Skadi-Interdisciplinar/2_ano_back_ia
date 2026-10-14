import json
from unittest.mock import Mock, patch

import pytest
from app import graph, predicao
from app.erros import SaidaModeloInvalida, ServicoIndisponivel
from app.predicao import ResultadoPredicao
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from psycopg2 import OperationalError
from pydantic import ValidationError


def test_orquestrador_preserva_estimativa_sem_llm(contexto, monkeypatch):
    from app.tools.predicao import prever_temperatura

    consulta = prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    resultado = contexto.resultados[consulta["referencia"]]
    modelo = Mock()
    monkeypatch.setattr(graph, "obter_modelos", modelo)

    resposta = graph._orquestrar({
        "respostas_agentes": [{"agente": "predicao", "resposta": resultado.model_dump_json()}],
    })["resposta"]

    modelo.assert_not_called()
    assert "4.00 °C" in resposta
    assert "a partir da leitura" in resposta
    assert "não do momento da pergunta" in resposta
    assert "experimental" in resposta
    assert "segurança dos produtos" in resposta
    assert "camara_id" not in resposta


def test_fluxo_chama_unica_tool_e_persiste_conversa(contexto, monkeypatch):
    from app.tools.predicao import TOOLS, prever_temperatura

    monkeypatch.setattr(graph, "carregar_contexto_conversa", Mock(return_value=[
        {"remetente": "usuario", "conteudo": "Predição para a câmara 3"},
        {"remetente": "assistente", "conteudo": "Daqui a quantos minutos?"},
    ]))
    salvar = Mock()
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", salvar)
    modelos = Mock(return_value=(Mock(), Mock()))
    monkeypatch.setattr(graph, "obter_modelos", modelos)
    monkeypatch.setattr("app.llms.obter_modelos", modelos)
    roteador = Mock()
    roteador.invoke.return_value = {"structured_response": {"rota": "predicao"}}

    def consultar(entrada):
        assert isinstance(entrada["messages"][0], HumanMessage)
        assert isinstance(entrada["messages"][1], AIMessage)
        consulta = prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
        return {"messages": [ToolMessage(content=json.dumps(consulta), name="prever_temperatura", tool_call_id="t")]}

    agente = Mock()
    agente.invoke.side_effect = consultar
    with patch("langchain.agents.create_agent", side_effect=[roteador, agente]) as criar:
        resposta, agentes = graph.executar_fluxo_skadi("1 minuto, consulte", 2)

    assert "4.00 °C" in resposta
    assert agentes == ["roteador", "predicao", "orquestrador"]
    assert criar.call_args.kwargs["tools"] == TOOLS
    assert salvar.call_count == 2
    assert predicao.contexto_predicao.get() is contexto


@pytest.mark.parametrize("saida", [None, {}, {"structured_response": {"temperatura_prevista": 999}},
                                   {"structured_response": {"referencia": "inventada"}}])
def test_saida_invalida_nao_vira_previsao(contexto, saida):
    agente = Mock()
    agente.invoke.return_value = saida
    with patch("langchain.agents.create_agent", return_value=agente), pytest.raises(SaidaModeloInvalida):
        predicao.executar_predicao([HumanMessage(content="Predição")], Mock())
    assert predicao.contexto_predicao.get() is contexto


def test_modelo_nao_pode_omitir_resultado_consultado(contexto):
    def executar(entrada):
        predicao.contexto_predicao.get().resultados["r"] = ResultadoPredicao(status="indisponivel", mensagem="Sem modelo")
        return {"structured_response": {}}

    agente = Mock()
    agente.invoke.side_effect = executar
    with patch("langchain.agents.create_agent", return_value=agente), pytest.raises(SaidaModeloInvalida):
        predicao.executar_predicao([HumanMessage(content="Predição")], Mock())


@pytest.mark.parametrize("mensagem", [
    "Esse horizonte não foi avaliado. Horizontes avaliados: 30.",
    "Não encontrei a câmara no seu escopo permitido.",
    "Qual câmara deseja analisar?",
])
def test_esclarecimento_da_tool_chega_ao_usuario_sem_reinterpretacao(contexto, mensagem):
    resultado = ResultadoPredicao(status="esclarecimento", mensagem=mensagem)

    def consultar(entrada):
        predicao.contexto_predicao.get().resultados["consulta"] = resultado
        return {"messages": [ToolMessage(content=json.dumps({"referencia": "consulta", **resultado.model_dump(mode="json")}),
                                         name="prever_temperatura", tool_call_id="t")]}

    agente = Mock()
    agente.invoke.side_effect = consultar
    with patch("langchain.agents.create_agent", return_value=agente):
        resposta = predicao.executar_predicao([HumanMessage(content="Predição")], Mock())

    assert predicao.apresentar_predicao(resposta) == mensagem


@pytest.mark.parametrize("conteudo", ["{}", "não é JSON", '{"referencia":"inventada"}'])
def test_retorno_invalido_da_tool_e_rejeitado(contexto, conteudo):
    agente = Mock()
    agente.invoke.return_value = {"messages": [ToolMessage(content=conteudo, name="prever_temperatura", tool_call_id="t")]}
    with patch("langchain.agents.create_agent", return_value=agente), pytest.raises(SaidaModeloInvalida):
        predicao.executar_predicao([HumanMessage(content="Predição")], Mock())


@pytest.mark.parametrize("alteracao", [{"referencia": "inventada"}, {"temperatura_prevista": 999}])
def test_referencia_ou_temperatura_alterada_nao_substitui_backend(contexto, alteracao):
    def consultar(entrada):
        original = ResultadoPredicao(status="ok", temperatura_prevista=4)
        predicao.contexto_predicao.get().resultados["consulta"] = original
        dados = {"referencia": "consulta", **original.model_dump(mode="json"), **alteracao}
        return {"messages": [ToolMessage(content=json.dumps(dados), name="prever_temperatura", tool_call_id="t")]}

    agente = Mock()
    agente.invoke.side_effect = consultar
    with patch("langchain.agents.create_agent", return_value=agente), pytest.raises(SaidaModeloInvalida):
        predicao.executar_predicao([HumanMessage(content="Predição")], Mock())


def test_predicao_encerra_na_tool_sem_segunda_geracao():
    from app.tools.predicao import TOOLS

    assert len(TOOLS) == 1
    assert TOOLS[0].return_direct is True


def test_especialista_exige_consulta_e_nao_responde_so_pela_memoria():
    request = Mock()
    handler = Mock()

    predicao._exigir_consulta_predicao.wrap_model_call(request, handler)

    request.override.assert_called_once_with(tool_choice="prever_temperatura")
    handler.assert_called_once_with(request.override.return_value)


@pytest.mark.parametrize("mensagem", [AIMessage(content="Será 999 graus."),
                                     ToolMessage(content="{}", name="outra_tool", tool_call_id="t")])
def test_texto_livre_e_tool_diferente_nao_viram_previsao(contexto, mensagem):
    agente = Mock()
    agente.invoke.return_value = {"messages": [mensagem]}
    with patch("langchain.agents.create_agent", return_value=agente), pytest.raises(SaidaModeloInvalida):
        predicao.executar_predicao([HumanMessage(content="Predição")], Mock())
    assert predicao.contexto_predicao.get() is contexto


def test_multiplos_resultados_nao_sao_selecionados_automaticamente(contexto):
    def consultar(entrada):
        resultado = ResultadoPredicao(status="esclarecimento", mensagem="Qual câmara?")
        resultados = predicao.contexto_predicao.get().resultados
        resultados["primeira"] = resultado
        resultados["segunda"] = resultado
        dados = {"referencia": "segunda", **resultado.model_dump(mode="json")}
        return {"messages": [ToolMessage(content=json.dumps(dados), name="prever_temperatura", tool_call_id="t")]}

    agente = Mock()
    agente.invoke.side_effect = consultar
    with patch("langchain.agents.create_agent", return_value=agente), pytest.raises(SaidaModeloInvalida):
        predicao.executar_predicao([HumanMessage(content="Predição")], Mock())
    assert predicao.contexto_predicao.get() is contexto


@pytest.mark.parametrize("erro", [RuntimeError("falha"), OperationalError("credenciais privadas")])
def test_infraestrutura_nao_vira_ausencia_de_dados(contexto, erro):
    agente = Mock()
    agente.invoke.side_effect = erro
    with patch("langchain.agents.create_agent", return_value=agente), pytest.raises((ServicoIndisponivel, OperationalError)):
        predicao.executar_predicao([HumanMessage(content="Predição")], Mock())
    assert predicao.contexto_predicao.get() is contexto


def test_operador_bloqueado_antes_de_obter_modelos(contexto):
    from app.tools.access import EscopoAcesso

    predicao.validar_acesso.return_value = EscopoAcesso(2, "OPERADOR", 7)
    with patch("app.llms.obter_modelos") as modelos, pytest.raises(PermissionError):
        graph._executar_especialista({"rota": "predicao", "usuario_id": 2, "pergunta_original": "Predição"})
    modelos.assert_not_called()


def test_sem_usuario_nao_invoca_modelo():
    with pytest.raises(PermissionError):
        graph._executar_especialista({"rota": "predicao", "pergunta_original": "Predição"})


def test_contexto_nao_aceita_fonte_usuario_do_modelo():
    from app.tools.predicao import PreverTemperaturaArgs

    with pytest.raises(ValidationError):
        PreverTemperaturaArgs(camara_id=3, horizonte_minutos=30, usuario_id=99)


def test_consulta_historica_parametriza_sensor_periodo_e_fecha_conexao(monkeypatch):
    from datetime import UTC, datetime

    from tests.conftest import banco_sql

    cursor, conexao = banco_sql()
    monkeypatch.setattr(predicao, "get_conn", Mock(return_value=conexao))
    predicao.consultar_serie({"termometro": 9}, datetime(2026, 10, 12, tzinfo=UTC), ultimas=True)
    sql, parametros = cursor.execute.call_args.args
    assert "cod_termometro = %s" in sql
    assert "LIMIT 2" in sql
    assert parametros[0] == 9
    assert parametros[1].tzinfo is None
    conexao.close.assert_called_once()


def test_tool_sem_contexto_protegido_nao_acessa_modelo(monkeypatch):
    from app.tools import predicao as tools
    from app.tools.access import EscopoAcesso

    token = definir_usuario_contexto(2)
    monkeypatch.setattr(predicao, "validar_acesso", Mock(return_value=EscopoAcesso(2, "ADMIN", 7)))
    try:
        with pytest.raises(PermissionError):
            tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    finally:
        restaurar_usuario_contexto(token)
