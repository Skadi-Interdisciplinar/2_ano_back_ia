from unittest.mock import Mock, patch

import pytest
from app import llms
from app.erros import ServicoIndisponivel


def test_cria_modelos_e_reutiliza_o_cache(monkeypatch):
    llms.obter_modelos.cache_clear()
    monkeypatch.setattr(llms, "GEMINI_API_KEY", "gemini-teste")
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")

    with patch("langchain_google_genai.ChatGoogleGenerativeAI") as gemini, patch(
        "langchain_groq.ChatGroq"
    ) as groq:
        primeiro = llms.obter_modelos()
        segundo = llms.obter_modelos()

    assert primeiro is segundo
    gemini.assert_called_once()
    groq.assert_called_once()
    llms.obter_modelos.cache_clear()


def test_exige_as_duas_chaves_dos_provedores(monkeypatch):
    llms.obter_modelos.cache_clear()
    monkeypatch.setattr(llms, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llms, "GROQ_API_KEY", "groq-teste")

    with pytest.raises(ServicoIndisponivel, match="Gemini e Groq"):
        llms.obter_modelos()


def test_codigo_de_erro_desconhecido_nao_e_exposto():
    erro = Mock()
    erro.body = {"error": {"code": "dado-privado"}}

    codigo = llms.codigo_erro_groq(erro)

    assert codigo == "nao_identificado"
