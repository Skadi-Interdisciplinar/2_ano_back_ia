from unittest.mock import patch

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
