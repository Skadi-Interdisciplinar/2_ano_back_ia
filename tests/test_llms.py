from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app import llms


@pytest.fixture(autouse=True)
def limpar_cache_modelos():
    llms.obter_modelos.cache_clear()
    yield
    llms.obter_modelos.cache_clear()


def test_modelos_sao_reutilizados_no_mesmo_processo(monkeypatch):
    criacoes_gemini = []
    criacoes_groq = []

    class GeminiFalso:
        def __init__(self, **kwargs):
            criacoes_gemini.append(kwargs)

        def with_fallbacks(self, fallbacks):
            return ("modelo-com-fallback", fallbacks)

    class GroqFalso:
        def __init__(self, **kwargs):
            criacoes_groq.append(kwargs)

    monkeypatch.setattr(llms, "GEMINI_API_KEY", "gemini-teste")
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")
    monkeypatch.setitem(
        sys.modules,
        "langchain_google_genai",
        SimpleNamespace(ChatGoogleGenerativeAI=GeminiFalso),
    )
    monkeypatch.setitem(sys.modules, "langchain_groq", SimpleNamespace(ChatGroq=GroqFalso))

    primeiro = llms.obter_modelos()
    segundo = llms.obter_modelos()

    assert primeiro is segundo
    assert len(criacoes_gemini) == 1
    assert len(criacoes_groq) == 1
    assert criacoes_gemini[0]["model"] == "gemini-2.5-flash"
    assert criacoes_groq[0]["model"] == "openai/gpt-oss-20b"


def test_modelos_exigem_as_duas_chaves(monkeypatch):
    monkeypatch.setattr(llms, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")

    with pytest.raises(RuntimeError, match="Gemini e Groq"):
        llms.obter_modelos()
