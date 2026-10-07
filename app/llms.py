from __future__ import annotations

from functools import lru_cache

from app.config import GEMINI_API_KEY, GROQ_API_KEY


@lru_cache(maxsize=1)
def obter_modelos():
    """Cria uma vez e reutiliza os modelos durante a vida do processo."""

    if not GEMINI_API_KEY or not GROQ_API_KEY:
        raise RuntimeError(
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
