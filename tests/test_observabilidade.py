from unittest.mock import Mock

import pytest
from app import observabilidade
from app.auth import AuthenticatedUser
from app.routes import observabilidade as rota_observabilidade
from app.schemas import ObservabilidadeResponse
from app.tools.access import EscopoAcesso
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _painel_vazio() -> dict:
    return {
        "escopo": "Teste",
        "resumo": {
            "turnos": 0, "erros": 0, "indice_erros": None,
            "latencia_media_ms": None, "latencia_p95_ms": None,
            "tokens_entrada": 0, "tokens_saida": 0,
            "custo_estimado_usd": 0.0, "custo_medio_por_turno_usd": None,
        },
        "latencia_interagentes": [], "projecoes_semanais": [],
        "custo_por_resolucao": {"valor_usd": None, "motivo": "Sem resolução."},
        "roi": {"valor_percentual": None, "motivo": "Sem retorno."},
        "turnos_recentes": [],
    }


def test_calcula_custo_para_modelo_com_preco_conhecido():
    custo = observabilidade.estimar_custo("openai/gpt-oss-20b", 1_000_000, 1_000_000)

    assert custo == 0.375


def test_painel_informa_quando_nao_ha_resolucoes_confirmadas(monkeypatch):
    monkeypatch.setattr(observabilidade, "_carregar_turnos", Mock(return_value=[]))

    painel = observabilidade.painel_mobile()

    assert painel["custo_por_resolucao"]["valor_usd"] is None
    assert painel["roi"]["valor_percentual"] is None


def test_persiste_turno_sem_conteudo_de_conversa(monkeypatch):
    colecao = Mock()
    monkeypatch.setattr(observabilidade, "_colecao_turnos", Mock(return_value=colecao))

    turno_id = observabilidade.abrir_turno()
    observabilidade.fechar_turno(turno_id=turno_id, rota="faq", status="ok")

    turno = colecao.insert_one.call_args.args[0]
    assert turno["rota"] == "faq"
    assert turno["status"] == "ok"
    assert "pergunta" not in turno
    assert "resposta" not in turno


def test_registra_etapa_executada_em_outra_thread_do_grafo(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context

    persistir = Mock()
    monkeypatch.setattr(observabilidade, "_persistir_turno", persistir)
    turno_id = observabilidade.abrir_turno()

    def executar():
        with observabilidade.medir_etapa("monitoramento"):
            return observabilidade._turno_atual()

    with ThreadPoolExecutor(max_workers=1) as executor:
        turno_na_thread = executor.submit(copy_context().run, executar).result()
    observabilidade.fechar_turno(turno_id=turno_id, rota="monitoramento", status="ok")

    assert turno_na_thread == turno_id
    assert persistir.call_args.args[0]["etapas"][0]["agente"] == "monitoramento"


def test_painel_calcula_metricas_dos_turnos_persistidos(monkeypatch):
    monkeypatch.setattr(observabilidade, "_carregar_turnos", Mock(return_value=[{
        "id": "turno-1", "data_hora": "2026-10-28T10:00:00+00:00", "rota": "monitoramento",
        "status": "ok", "latencia_total_ms": 500, "tokens_entrada": 10,
        "tokens_saida": 5, "custo_usd": 0.001,
        "chamadas": [{
            "modelo": "openai/gpt-oss-20b", "latencia_ms": 300,
            "tokens_entrada": 10, "tokens_saida": 5, "custo_usd": 0.001,
        }],
        "etapas": [{"agente": "monitoramento", "latencia_ms": 250}],
    }]))

    painel = observabilidade.painel_mobile()

    assert painel["resumo"]["turnos"] == 1
    assert painel["resumo"]["latencia_media_ms"] == 500.0
    assert painel["latencia_interagentes"] == [
        {"agente": "monitoramento", "latencia_media_ms": 250.0, "chamadas": 1}
    ]


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
    monkeypatch.setattr(rota_observabilidade, "painel_mobile", Mock(return_value=_painel_vazio()))

    app = FastAPI()
    app.include_router(rota_observabilidade.router)
    with TestClient(app) as cliente:
        resposta = cliente.get("/observabilidade", headers={"Authorization": "Bearer teste"})

    assert resposta.status_code == 200
    assert resposta.json()["resumo"]["turnos"] == 0


def test_endpoint_exige_bearer_antes_de_consultar_bancos(monkeypatch):
    validar = Mock()
    monkeypatch.setattr(rota_observabilidade, "validar_acesso", validar)
    app = FastAPI()
    app.include_router(rota_observabilidade.router)

    with TestClient(app) as cliente:
        resposta = cliente.get("/observabilidade")

    assert resposta.status_code == 401
    validar.assert_not_called()


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

    with pytest.raises(PermissionError):
        rota_observabilidade.consultar_observabilidade(authorization="Bearer teste")


def test_rota_de_observabilidade_declara_contrato_mobile():
    rota = next(route for route in rota_observabilidade.router.routes if route.path == "/observabilidade")

    assert rota.response_model is ObservabilidadeResponse


def test_custo_por_resolucao_inclui_custo_dos_erros_e_roi_usa_premissas(monkeypatch):
    turnos = [{"status": status, "latencia_total_ms": 100, "custo_usd": custo,
               "data_hora": "2026-10-30T10:00:00+00:00", "rota": "faq",
               "tokens_entrada": 0, "tokens_saida": 0} for status, custo in (("ok", 1.0), ("erro", 3.0))]
    monkeypatch.setattr(observabilidade, "_carregar_turnos", Mock(return_value=turnos))
    monkeypatch.setattr(observabilidade.config, "ROI_TEMPO_MANUAL_MINUTOS", "6")
    monkeypatch.setattr(observabilidade.config, "ROI_CUSTO_HORA_USD", "20")

    painel = observabilidade.painel_mobile()

    assert painel["resumo"]["resolucoes_tecnicas"] == 1
    assert painel["custo_por_resolucao"]["valor_usd"] == 4.0
    assert painel["roi"]["valor_percentual"] == -50.0


@pytest.mark.parametrize("valor", [None, "NaN", "Infinity", "-1", "inválido"])
def test_roi_sem_premissas_validas_nao_inventa_beneficio(monkeypatch, valor):
    monkeypatch.setattr(observabilidade, "_carregar_turnos", Mock(return_value=[]))
    monkeypatch.setattr(observabilidade.config, "ROI_TEMPO_MANUAL_MINUTOS", valor)
    monkeypatch.setattr(observabilidade.config, "ROI_CUSTO_HORA_USD", "20")

    assert observabilidade.painel_mobile()["roi"]["valor_percentual"] is None
