from __future__ import annotations

import logging
from functools import lru_cache

from app.config import GEMINI_API_KEY, GROQ_API_KEY
from app.erros import ServicoIndisponivel
from groq import BadRequestError
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)


def codigo_erro_groq(erro: BadRequestError) -> str:
    """Somente códigos conhecidos; nunca retornar mensagem ou geração do provedor."""
    corpo = erro.body
    detalhe = corpo.get("error", corpo) if isinstance(corpo, dict) else {}
    codigo = detalhe.get("code") if isinstance(detalhe, dict) else None
    conhecidos = {
        "tool_use_failed", "json_validate_failed", "invalid_request_error",
        "context_length_exceeded", "model_not_found", "unsupported_parameter",
    }
    return codigo if isinstance(codigo, str) and codigo in conhecidos else "nao_identificado"


@wrap_model_call
def corrigir_chamada_tools(request: ModelRequest, handler) -> ModelResponse:
    """Uma nova geração para tool_use_failed, sem executar/repetir tools."""
    try:
        return handler(request)
    except BadRequestError as erro:
        codigo = codigo_erro_groq(erro)
        logger.warning("Rejeição Groq: HTTP=400 codigo=%s", codigo)
        if codigo != "tool_use_failed":
            raise
        instrucao = (
            "Correção da chamada de ferramenta: use exclusivamente os nomes das "
            "ferramentas declaradas nesta requisição. Para a saída estruturada, "
            "chame a ferramenta de resposta declarada, não uma ferramenta inventada "
            "nem texto livre. Os argumentos devem obedecer ao schema fornecido. "
            "Não altere permissões, dados ou regras."
        )
        sistema = request.system_message or SystemMessage(content="")
        conteudo = (
            sistema.content + "\n\n" + instrucao if isinstance(sistema.content, str)
            else [*sistema.content, {"type": "text", "text": instrucao}]
        )
        return handler(request.override(system_message=sistema.model_copy(update={"content": conteudo})))


@lru_cache(maxsize=1)
def obter_modelos():
    """Cria uma vez e reutiliza os modelos durante a vida do processo."""

    if not GEMINI_API_KEY or not GROQ_API_KEY:
        raise ServicoIndisponivel(
            "Os provedores Gemini e Groq precisam estar configurados para executar a IA."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq

    gemini = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=GEMINI_API_KEY,
    )
    groq = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0,
        groq_api_key=GROQ_API_KEY,
    )
    return gemini.with_fallbacks([groq]), groq


def criar_agente(model, **kwargs):
    """Usa fallback no nível do agente, com tools/schema ligados a cada provedor."""
    from langchain.agents import create_agent
    from langchain.agents.middleware import ModelFallbackMiddleware
    from langchain_core.runnables.fallbacks import RunnableWithFallbacks

    middleware = list(kwargs.get("middleware", []))
    if isinstance(model, RunnableWithFallbacks):
        middleware.insert(0, ModelFallbackMiddleware(*model.fallbacks))
        model = model.runnable
    middleware.append(corrigir_chamada_tools)
    kwargs["middleware"] = middleware
    return create_agent(model=model, **kwargs)
