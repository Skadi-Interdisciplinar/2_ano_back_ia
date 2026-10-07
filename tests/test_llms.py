import pytest
from app import llms


def test_modelos_exigem_chaves_de_api(monkeypatch):
    llms.obter_modelos.cache_clear()
    monkeypatch.setattr(llms, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")

    with pytest.raises(RuntimeError, match="Gemini e Groq"):
        llms.obter_modelos()
