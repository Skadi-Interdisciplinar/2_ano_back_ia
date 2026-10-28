from unittest.mock import Mock

from app.auth import AuthenticatedUser
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
