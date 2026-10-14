import json
from unittest.mock import Mock

import pytest
from app import regras_diagnostico as base
from qdrant_client import models


def test_base_tem_oito_regras_aprovadas_com_fontes_e_versao():
    regras = base.carregar_regras()

    assert len(regras) == 8
    assert all(r.fontes and r.aprovacao for r in regras.values())
    assert all(r.versao == "0.2" for r in list(regras.values())[:6])
    assert regras["DIAG-TEC-007"].versao == regras["DIAG-TEC-008"].versao == "0.3"
    assert regras["DIAG-TEC-007"].aprovacao.data == "2026-10-12"
    assert regras["DIAG-TEC-008"].aprovacao.data == "2026-10-12"


@pytest.mark.parametrize("mudanca", [
    {"status": "EM_REVISAO"}, {"ativa": False}, {"status": "INATIVA"},
])
def test_base_nao_entrega_regra_pendente_ou_inativa(monkeypatch, mudanca):
    regra = base.carregar_regras()["DIAG-TEC-001"].model_dump()
    regra.update(mudanca)
    arquivo = Mock()
    arquivo.read_text.return_value = json.dumps([regra])
    monkeypatch.setattr(base, "BASE_REGRAS", arquivo)

    assert base.carregar_regras() == {}


@pytest.mark.parametrize("mudanca", [
    {"fontes": []}, {"aprovacao": None}, {"grupos_requisitos": [[]]},
    {"hipotese": ""}, {"versao": ""},
])
def test_base_incompleta_e_recusada(monkeypatch, mudanca):
    regra = base.carregar_regras()["DIAG-TEC-001"].model_dump()
    regra.update(mudanca)
    arquivo = Mock()
    arquivo.read_text.return_value = json.dumps([regra])
    monkeypatch.setattr(base, "BASE_REGRAS", arquivo)

    with pytest.raises(RuntimeError, match="Base técnica"):
        base.carregar_regras()


def test_base_recusa_ids_duplicados(monkeypatch):
    regra = base.carregar_regras()["DIAG-TEC-001"].model_dump()
    arquivo = Mock()
    arquivo.read_text.return_value = json.dumps([regra, regra])
    monkeypatch.setattr(base, "BASE_REGRAS", arquivo)

    with pytest.raises(RuntimeError):
        base.carregar_regras()


@pytest.fixture
def cliente(monkeypatch):
    cliente = Mock()
    cliente.collection_exists.return_value = True
    cliente.get_collection.return_value.config.params.vectors = models.VectorParams(
        size=768, distance=models.Distance.COSINE,
    )
    monkeypatch.setattr(base, "cliente_qdrant", Mock(return_value=cliente))
    monkeypatch.setattr(base, "gerar_embedding", Mock(return_value=[0.0] * 768))
    return cliente


def test_indexacao_idempotente_com_confirmacao(cliente):
    assert base.indexar_regras() == 8
    primeiros_ids = [p.id for p in cliente.upsert.call_args.kwargs["points"]]
    assert base.indexar_regras() == 8

    envio = cliente.upsert.call_args.kwargs
    assert envio["wait"] is True
    assert envio["collection_name"] == "trimmy_regras_diagnostico"
    assert primeiros_ids == [p.id for p in envio["points"]]
    assert len(set(primeiros_ids)) == 8


def test_indexador_cria_colecao_exclusiva(cliente):
    cliente.collection_exists.return_value = False

    base.indexar_regras()

    cliente.create_collection.assert_called_once()
    assert cliente.create_collection.call_args.args == ("trimmy_regras_diagnostico",)
    assert cliente.create_collection.call_args.kwargs["vectors_config"].size == 768


def test_dimensao_incompativel_nao_e_sobrescrita(cliente):
    cliente.get_collection.return_value.config.params.vectors = models.VectorParams(
        size=10, distance=models.Distance.COSINE,
    )

    with pytest.raises(RuntimeError, match="Dimensão"):
        base.indexar_regras()

    cliente.upsert.assert_not_called()
    cliente.create_collection.assert_not_called()


def test_recuperacao_considera_oito_e_confere_fonte_aprovada(cliente):
    regras = base.carregar_regras()
    cliente.query_points.return_value.points = [Mock(payload={
        "regra": r.model_dump(), "assinatura": base.assinatura_regra(r),
        "status": "APROVADA", "ativa": True,
    }) for r in regras.values()]

    encontradas = base.recuperar_regras("gelo")

    assert len(encontradas) == 8
    consulta = cliente.query_points.call_args.kwargs
    assert consulta["limit"] == 8
    assert consulta["collection_name"] == "trimmy_regras_diagnostico"
    assert [c.key for c in consulta["query_filter"].must] == ["status", "ativa", "assinatura"]


@pytest.mark.parametrize("mudanca", [
    {"recomendacao": "Troque o compressor"}, {"versao": "0.1"},
    {"status": "EM_REVISAO"}, {"ativa": False}, {"id": ["injetado"]},
])
def test_payload_adulterado_ou_antigo_nao_e_usado(cliente, mudanca):
    regra = base.carregar_regras()["DIAG-TEC-001"]
    candidato = regra.model_dump()
    candidato.update(mudanca)
    cliente.query_points.return_value.points = [Mock(payload={
        "regra": candidato, "assinatura": base.assinatura_regra(regra),
        "status": "APROVADA", "ativa": True,
    })]

    assert base.recuperar_regras("porta") == []


def test_ausencia_de_colecao_e_configuracao_pendente_nao_resultado_vazio(cliente):
    cliente.collection_exists.return_value = False

    with pytest.raises(RuntimeError, match="não indexada"):
        base.recuperar_regras("porta")


def test_falha_qdrant_propaga(cliente):
    cliente.query_points.side_effect = RuntimeError("Qdrant indisponível")

    with pytest.raises(RuntimeError, match="Qdrant"):
        base.recuperar_regras("porta")

