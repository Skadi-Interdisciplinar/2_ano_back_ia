from unittest.mock import Mock

import pytest
from app.auth import AuthenticatedUser
from app.erros import ServicoIndisponivel
from app.main import app
from app.relatorios import (
    DadosRelatorioInvalidos,
    FiltroRelatorioInvalido,
    SelecaoRelatorioNaoEncontrada,
)
from app.routes import relatorios
from fastapi.testclient import TestClient
from psycopg2 import OperationalError

CORPO = {"token": "segredo-teste", "data_inicial": "2026-10-01", "data_final": "2026-10-02"}


def test_download_repassa_identidade_e_retorna_pdf(monkeypatch):
    autenticar = Mock(return_value=AuthenticatedUser(27))
    gerar = Mock(return_value=b"%PDF-teste")
    monkeypatch.setattr(relatorios, "obter_usuario_autenticado", autenticar)
    monkeypatch.setattr(relatorios, "gerar_relatorio_pdf", gerar)

    resposta = TestClient(app).post("/relatorios/pdf", json=CORPO)

    assert resposta.status_code == 200
    assert resposta.content == b"%PDF-teste"
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.headers["cache-control"] == "no-store"
    assert resposta.headers["content-disposition"] == 'attachment; filename="skadi-relatorio-2026-10-01-2026-10-02.pdf"'
    autenticar.assert_called_once_with("segredo-teste")
    assert gerar.call_args.args[0] == 27
    assert gerar.call_args.args[1].camara_id is None


@pytest.mark.parametrize("erro,status", [
    (PermissionError("segredo-teste"), 403),
    (SelecaoRelatorioNaoEncontrada("segredo-teste"), 404),
    (DadosRelatorioInvalidos("segredo-teste"), 409),
    (FiltroRelatorioInvalido("Informe o CD para gerar o relatório."), 422),
    (ServicoIndisponivel("segredo-teste"), 503),
    (OperationalError("segredo-teste"), 503),
    (RuntimeError("segredo-teste"), 500),
])
def test_erros_nao_entregam_pdf_nem_expoem_detalhes(monkeypatch, caplog, erro, status):
    monkeypatch.setattr(relatorios, "gerar_relatorio_pdf", Mock(side_effect=erro))
    resposta = TestClient(app).post("/relatorios/pdf", json=CORPO)
    assert resposta.status_code == status
    assert "segredo-teste" not in resposta.text
    assert "segredo-teste" not in caplog.text
    assert resposta.headers["content-type"] == "application/json"


@pytest.mark.parametrize("alteracao", [{"usuario_id": 4}, {"temperatura": 5}, {"data_inicial": "ontem"}, {"token": " "}])
def test_validacao_nao_expoe_corpo_ou_chama_servico(monkeypatch, alteracao):
    gerar = Mock()
    monkeypatch.setattr(relatorios, "gerar_relatorio_pdf", gerar)
    resposta = TestClient(app).post("/relatorios/pdf", json={**CORPO, **alteracao})
    assert resposta.status_code == 422
    assert "segredo-teste" not in resposta.text
    gerar.assert_not_called()


def test_openapi_documenta_download_e_erros():
    operacao = app.openapi()["paths"]["/relatorios/pdf"]["post"]
    assert "application/pdf" in operacao["responses"]["200"]["content"]
    assert all(str(status) in operacao["responses"] for status in (403, 404, 409, 422, 500, 503))
