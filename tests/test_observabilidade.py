from unittest.mock import Mock

from app import observabilidade
from app.auth import AuthenticatedUser
from app.main import app
from app.routes import observabilidade as rota_observabilidade
from app.tools.access import EscopoAcesso
from fastapi.testclient import TestClient


def test_calcula_custo_para_modelo_com_preco_conhecido():
    custo = observabilidade.estimar_custo("openai/gpt-oss-20b", 1_000_000, 1_000_000)

    assert custo == 0.375


def test_painel_informa_quando_nao_ha_resolucoes_confirmadas():
    painel = observabilidade.painel_mobile()

    assert painel["custo_por_resolucao"]["valor_usd"] is None
    assert painel["roi"]["valor_percentual"] is None


def test_super_admin_consulta_observabilidade(monkeypatch):
    monkeypatch.setattr(
        rota_observabilidade,
        "obter_usuario_autenticado",
        Mock(return_value=AuthenticatedUser(1)),
    )
    monkeypatch.setattr(
        rota_observabilidade,
        "validar_acesso",
        Mock(return_value=EscopoAcesso(1, "SUPER_ADMIN", None)),
    )
    monkeypatch.setattr(rota_observabilidade, "painel_mobile", Mock(return_value={"resumo": {}}))

    resposta = TestClient(app).get("/observabilidade", headers={"Authorization": "Bearer teste"})

    assert resposta.status_code == 200
    assert resposta.json() == {"resumo": {}}


def test_gestor_nao_consulta_observabilidade(monkeypatch):
    monkeypatch.setattr(
        rota_observabilidade,
        "obter_usuario_autenticado",
        Mock(return_value=AuthenticatedUser(12)),
    )
    monkeypatch.setattr(
        rota_observabilidade,
        "validar_acesso",
        Mock(return_value=EscopoAcesso(12, "GESTOR", 2)),
    )

    resposta = TestClient(app).get("/observabilidade", headers={"Authorization": "Bearer teste"})

    assert resposta.status_code == 403
