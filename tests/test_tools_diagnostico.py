from unittest.mock import Mock

from app.diagnostico import ContextoDiagnostico, contexto_diagnostico
from app.tools import diagnostico
from app.tools.access import EscopoAcesso
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto


def test_pede_identificacao_quando_a_camara_nao_foi_informada(monkeypatch):
    monkeypatch.setattr(diagnostico, "validar_acesso", Mock(return_value=EscopoAcesso(12, "GESTOR", 2)))
    token_usuario = definir_usuario_contexto(12)
    token_diagnostico = contexto_diagnostico.set(ContextoDiagnostico(usuario_id=12))
    try:
        resultado = diagnostico.consultar_evidencias_diagnostico.invoke({})
    finally:
        contexto_diagnostico.reset(token_diagnostico)
        restaurar_usuario_contexto(token_usuario)

    assert resultado["status"] == "identificacao_necessaria"
    assert "Qual câmara" in resultado["mensagem"]


def test_busca_regras_usa_usuario_do_contexto(monkeypatch):
    regra = Mock()
    regra.id = "DIAG-001"
    regra.model_dump.return_value = {"id": "DIAG-001"}
    monkeypatch.setattr(diagnostico, "validar_acesso", Mock(return_value=EscopoAcesso(12, "GESTOR", 2)))
    recuperar = Mock(return_value=[regra])
    monkeypatch.setattr(diagnostico, "recuperar_regras", recuperar)
    token_usuario = definir_usuario_contexto(12)
    token_diagnostico = contexto_diagnostico.set(ContextoDiagnostico(usuario_id=12))
    try:
        resultado = diagnostico.buscar_regras_diagnostico.invoke({"busca": "gelo no evaporador"})
    finally:
        contexto_diagnostico.reset(token_diagnostico)
        restaurar_usuario_contexto(token_usuario)

    assert resultado == [{"id": "DIAG-001"}]
    recuperar.assert_called_once_with("gelo no evaporador")
