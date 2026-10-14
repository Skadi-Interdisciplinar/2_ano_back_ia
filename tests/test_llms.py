from unittest.mock import Mock, patch

import pytest
from app import llms


@pytest.fixture(autouse=True)
def limpar_cache_modelos():
    llms.obter_modelos.cache_clear()
    yield
    llms.obter_modelos.cache_clear()


def test_modelos_sao_reutilizados_no_mesmo_processo(monkeypatch):
    monkeypatch.setattr(llms, "GEMINI_API_KEY", "gemini-teste")
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")

    with (
        patch("langchain_google_genai.ChatGoogleGenerativeAI") as gemini,
        patch("langchain_groq.ChatGroq") as groq,
    ):
        primeiro = llms.obter_modelos()
        segundo = llms.obter_modelos()

    assert primeiro is segundo
    gemini.assert_called_once_with(
        model="gemini-2.5-flash", temperature=0, google_api_key="gemini-teste",
    )
    groq.assert_called_once_with(
        model="openai/gpt-oss-20b", temperature=0, groq_api_key="groq-teste",
    )
    gemini.return_value.with_fallbacks.assert_called_once_with([groq.return_value])


def test_modelos_exigem_as_duas_chaves(monkeypatch):
    monkeypatch.setattr(llms, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")

    with pytest.raises(RuntimeError, match="Gemini e Groq"):
        llms.obter_modelos()


@pytest.fixture
def modelos_reais_sem_rede(monkeypatch):
    monkeypatch.setattr(llms, "GEMINI_API_KEY", "gemini-teste")
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")
    return llms.obter_modelos()


def test_quota_gemini_usa_groq_com_tools_e_schema(modelos_reais_sem_rede):
    from app.diagnostico import PropostaDiagnostico
    from langchain.agents.structured_output import ToolStrategy
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.tools import tool
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
    from langchain_groq import ChatGroq

    consulta = Mock()

    @tool
    def consultar_teste() -> dict:
        """Consulta simulada, sem bancos ou rede."""
        return consulta()

    principal, _ = modelos_reais_sem_rede
    resposta = ChatResult(generations=[ChatGeneration(message=AIMessage(
        content="", tool_calls=[{
            "id": "resposta-1", "name": "PropostaDiagnostico",
            "args": {"evidencia_ref": None, "relatos": [], "hipoteses": [], "perguntas_regras": []},
        }],
    ))])
    with (
        patch.object(ChatGoogleGenerativeAI, "_generate", side_effect=ChatGoogleGenerativeAIError("429 RESOURCE_EXHAUSTED")) as gemini,
        patch.object(ChatGroq, "_generate", return_value=resposta) as groq,
    ):
        agente = llms.criar_agente(
            model=principal, tools=[consultar_teste],
            response_format=ToolStrategy(PropostaDiagnostico, handle_errors=False),
        )
        saida = agente.invoke({"messages": [("user", "Faça o diagnóstico.")]})

    gemini.assert_called_once()
    groq.assert_called_once()
    assert isinstance(saida["structured_response"], PropostaDiagnostico)
    ferramentas = groq.call_args.kwargs["tools"]
    assert {t["function"]["name"] for t in ferramentas} == {"consultar_teste", "PropostaDiagnostico"}
    assert groq.call_args.kwargs["tool_choice"] == "required"
    consulta.assert_not_called()


def test_gemini_disponivel_nao_chama_reserva(modelos_reais_sem_rede):
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq

    principal, _ = modelos_reais_sem_rede
    with (
        patch.object(ChatGoogleGenerativeAI, "_generate", return_value=ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="Resposta do principal"))],
        )),
        patch.object(ChatGroq, "_generate") as groq,
    ):
        saida = llms.criar_agente(model=principal, tools=[]).invoke({"messages": [("user", "oi")]})

    assert saida["messages"][-1].content == "Resposta do principal"
    groq.assert_not_called()


def test_falha_dos_dois_preserva_erro_da_reserva(modelos_reais_sem_rede):
    from groq import APIConnectionError
    from httpx import Request
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
    from langchain_groq import ChatGroq

    principal, _ = modelos_reais_sem_rede
    erro_reserva = APIConnectionError(request=Request("POST", "https://api.groq.com"))
    with (
        patch.object(ChatGoogleGenerativeAI, "_generate", side_effect=ChatGoogleGenerativeAIError("429 RESOURCE_EXHAUSTED")),
        patch.object(ChatGroq, "_generate", side_effect=erro_reserva) as groq,
        pytest.raises(APIConnectionError) as falha,
    ):
        llms.criar_agente(model=principal, tools=[]).invoke({"messages": [("user", "oi")]})

    groq.assert_called_once()
    assert falha.value is erro_reserva


def test_fallback_nao_repete_tool_com_acesso_negado(modelos_reais_sem_rede):
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.tools import tool
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq

    acesso = Mock(side_effect=PermissionError("Sem acesso"))

    @tool
    def consultar_protegido() -> dict:
        """Exige autorização interna antes de consultar dados."""
        return acesso()

    principal, _ = modelos_reais_sem_rede
    resposta = ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
        "id": "consulta-1", "name": "consultar_protegido", "args": {},
    }]))])
    with (
        patch.object(ChatGoogleGenerativeAI, "_generate", return_value=resposta),
        patch.object(ChatGroq, "_generate") as groq,
        pytest.raises(PermissionError),
    ):
        llms.criar_agente(model=principal, tools=[consultar_protegido]).invoke({"messages": [("user", "consulte")]})

    acesso.assert_called_once()
    groq.assert_not_called()


def erro_groq(codigo="tool_use_failed"):
    from groq import BadRequestError
    from httpx import Request, Response

    corpo = {"error": {"code": codigo, "message": "mensagem privada", "failed_generation": "dados privados"}}
    return BadRequestError(
        "detalhes privados", response=Response(400, request=Request("POST", "https://api.groq.com")), body=corpo,
    )


def test_tool_use_failed_refaz_somente_geracao_com_schema(modelos_reais_sem_rede, caplog):
    from app.diagnostico import PropostaDiagnostico
    from langchain.agents.structured_output import ToolStrategy
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_groq import ChatGroq

    _, groq = modelos_reais_sem_rede
    resposta = ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[{
        "id": "resposta-1", "name": "PropostaDiagnostico", "args": {"evidencia_ref": None},
    }]))])
    with patch.object(ChatGroq, "_generate", side_effect=[erro_groq(), resposta]) as gerar:
        agente = llms.criar_agente(
            model=groq, tools=[], system_prompt="Use a saída estruturada.",
            response_format=ToolStrategy(PropostaDiagnostico, handle_errors=False),
        )
        resultado = agente.invoke({"messages": [("user", "Faça o diagnóstico")]})

    assert gerar.call_count == 2
    assert isinstance(resultado["structured_response"], PropostaDiagnostico)
    segunda = gerar.call_args.args[0]
    assert "Correção da chamada de ferramenta" in segunda[0].content
    assert "Faça o diagnóstico" in segunda[1].content
    assert "tool_use_failed" in caplog.text
    assert "privad" not in caplog.text


def test_tool_use_failed_persistente_interrompe_apos_uma_correcao(modelos_reais_sem_rede):
    from groq import BadRequestError
    from langchain_groq import ChatGroq

    _, groq = modelos_reais_sem_rede
    with (
        patch.object(ChatGroq, "_generate", side_effect=erro_groq()) as gerar,
        pytest.raises(BadRequestError),
    ):
        llms.criar_agente(model=groq, tools=[]).invoke({"messages": [("user", "oi")]})

    assert gerar.call_count == 2


def test_outro_erro_400_nao_e_repetido(modelos_reais_sem_rede):
    from groq import BadRequestError
    from langchain_groq import ChatGroq

    _, groq = modelos_reais_sem_rede
    with (
        patch.object(ChatGroq, "_generate", side_effect=erro_groq("context_length_exceeded")) as gerar,
        pytest.raises(BadRequestError),
    ):
        llms.criar_agente(model=groq, tools=[]).invoke({"messages": [("user", "oi")]})

    gerar.assert_called_once()


@pytest.mark.parametrize("codigo", ["segredo\ninjetado", {"token": "segredo"}, None])
def test_codigo_nao_conhecido_nao_e_registrado(codigo):
    assert llms.codigo_erro_groq(erro_groq(codigo)) == "nao_identificado"
