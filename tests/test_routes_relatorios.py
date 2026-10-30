from unittest.mock import Mock

import pytest
from app.auth import AuthenticatedUser
from app.erros import SaidaModeloInvalida, ServicoIndisponivel
from app.main import app
from app.routes import relatorios
from fastapi.testclient import TestClient


def test_devolve_pdf_com_nome_controlado_pelo_servidor(monkeypatch):
    monkeypatch.setattr(relatorios, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(12)))
    gerar = Mock(return_value=b"%PDF-teste")
    monkeypatch.setattr(relatorios, "gerar_relatorio_pdf", gerar)

    resposta = TestClient(app).post("/relatorios/pdf", json={
        "token": "teste", "cd_id": 2, "camara_id": None,
        "data_inicial": "2026-10-01", "data_final": "2026-10-10",
    })

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert "skadi-relatorio-2026-10-01-2026-10-10.pdf" in resposta.headers["content-disposition"]
    gerar.assert_called_once()


@pytest.mark.parametrize("erro,codigo,trecho", [
    (ServicoIndisponivel("segredo interno"), 503, "serviço que confere"),
    (SaidaModeloInvalida("segredo interno"), 502, "não passou pela conferência"),
    (PermissionError("segredo interno"), 403, "CD vinculado"),
])
def test_erro_do_relatorio_explica_o_problema_sem_expor_detalhes(monkeypatch, erro, codigo, trecho):
    monkeypatch.setattr(relatorios, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(12)))
    monkeypatch.setattr(relatorios, "gerar_relatorio_pdf", Mock(side_effect=erro))

    resposta = TestClient(app).post("/relatorios/pdf", json={
        "token": "teste", "data_inicial": "2026-10-01", "data_final": "2026-10-10",
    })

    assert resposta.status_code == codigo
    assert trecho in resposta.json()["detail"]
    assert "segredo interno" not in resposta.text
