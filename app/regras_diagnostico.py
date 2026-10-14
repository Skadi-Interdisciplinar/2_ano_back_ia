"""Fonte aprovada e RAG técnico; indexação nunca é uma tool do agente."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from app.erros import ServicoIndisponivel
from app.vectorstore import EMBEDDING_DIM, cliente_qdrant, gerar_embedding
from pydantic import BaseModel, ConfigDict, Field

COLLECTION_DIAGNOSTICO = "trimmy_regras_diagnostico"
BASE_REGRAS = Path(__file__).with_name("base_regras_diagnostico.json")
Requisito = Literal[
    "porta_nao_fecha", "vedacao_danificada", "produtos_mais_quentes",
    "produtos_obstruem_ar", "gelo_evaporador", "gelo_obstrui_ar",
    "condensador_obstruido_observacao_segura", "sensor_posicao_exposta",
    "degelo_em_andamento", "degelo_encerrado", "gelo_permaneceu_apos_degelo",
]


class FonteRegra(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    titulo: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://[^\s]+$")
    secao: str = Field(min_length=1)
    data_consulta: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class AprovacaoRegra(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    origem: str = Field(min_length=1)
    data: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class RegraDiagnostico(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^DIAG-TEC-\d{3}$")
    versao: str = Field(min_length=1)
    status: Literal["APROVADA", "EM_REVISAO", "INATIVA"]
    ativa: bool = Field(strict=True)
    titulo: str = Field(min_length=1)
    cenario: Literal["acima_maximo", "fora_faixa"]
    grupos_requisitos: list[list[Requisito]] = Field(min_length=1)
    hipotese: str = Field(min_length=1)
    recomendacao: str = Field(min_length=1)
    pergunta: str = Field(min_length=1)
    limitacoes: str = Field(min_length=1)
    fontes: list[FonteRegra] = Field(min_length=1)
    aprovacao: AprovacaoRegra | None = None


def carregar_regras() -> dict[str, RegraDiagnostico]:
    """Lê a fonte local a cada operação para não manter aprovação revogada em cache."""
    try:
        dados = json.loads(BASE_REGRAS.read_text(encoding="utf-8"))
        regras = [RegraDiagnostico.model_validate(dado) for dado in dados]
        if len({r.id for r in regras}) != len(regras):
            raise ValueError("Identificadores duplicados.")
        if any(not grupo for r in regras for grupo in r.grupos_requisitos):
            raise ValueError("Requisito vazio.")
        if any(r.status == "APROVADA" and r.aprovacao is None for r in regras):
            raise ValueError("Aprovação não documentada.")
        return {r.id: r for r in regras if r.status == "APROVADA" and r.ativa}
    except (OSError, ValueError, TypeError) as erro:
        raise ServicoIndisponivel("Base técnica inválida ou indisponível.") from erro


def assinatura_regra(regra: RegraDiagnostico) -> str:
    texto = json.dumps(regra.model_dump(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode()).hexdigest()


def indexar_regras() -> int:
    """Operação administrativa idempotente. Não altera dados operacionais."""
    from qdrant_client import models

    regras = carregar_regras()
    if not regras:
        raise RuntimeError("Não há regras aprovadas para indexar.")
    cliente = cliente_qdrant()
    if cliente.collection_exists(COLLECTION_DIAGNOSTICO):
        vetor = cliente.get_collection(COLLECTION_DIAGNOSTICO).config.params.vectors
        if not isinstance(vetor, models.VectorParams) or vetor.size != EMBEDDING_DIM:
            raise RuntimeError("Dimensão da coleção técnica incompatível.")
        if vetor.distance != models.Distance.COSINE:
            raise RuntimeError("Métrica da coleção técnica incompatível.")
    else:
        cliente.create_collection(
            COLLECTION_DIAGNOSTICO,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
        )
    for campo, tipo in (
        ("status", models.PayloadSchemaType.KEYWORD),
        ("ativa", models.PayloadSchemaType.BOOL),
        ("assinatura", models.PayloadSchemaType.KEYWORD),
    ):
        cliente.create_payload_index(
            collection_name=COLLECTION_DIAGNOSTICO, field_name=campo, field_schema=tipo,
        )
    pontos = []
    for regra in regras.values():
        texto = json.dumps(regra.model_dump(), ensure_ascii=False)
        pontos.append(models.PointStruct(
            id=str(uuid5(NAMESPACE_URL, f"{COLLECTION_DIAGNOSTICO}/{regra.id}")),
            vector=gerar_embedding(texto),
            payload={"regra": regra.model_dump(), "status": regra.status, "ativa": regra.ativa,
                     "assinatura": assinatura_regra(regra)},
        ))
    cliente.upsert(collection_name=COLLECTION_DIAGNOSTICO, points=pontos, wait=True)
    return len(pontos)


def recuperar_regras(busca: str) -> list[RegraDiagnostico]:
    """Qdrant seleciona; somente o conteúdo igual à fonte aprovada pode ser utilizado."""
    from qdrant_client import models

    regras = carregar_regras()
    if not regras:
        return []
    cliente = cliente_qdrant()
    if not cliente.collection_exists(COLLECTION_DIAGNOSTICO):
        raise ServicoIndisponivel("Base técnica ainda não indexada.")
    resultado = cliente.query_points(
        collection_name=COLLECTION_DIAGNOSTICO, query=gerar_embedding(busca),
        query_filter=models.Filter(must=[
            models.FieldCondition(key="status", match=models.MatchValue(value="APROVADA")),
            models.FieldCondition(key="ativa", match=models.MatchValue(value=True)),
            models.FieldCondition(key="assinatura", match=models.MatchAny(
                any=[assinatura_regra(r) for r in regras.values()],
            )),
        ]),
        limit=len(regras), with_payload=True,
    )
    encontradas = {}
    for ponto in resultado.points:
        payload = ponto.payload or {}
        candidato = payload.get("regra")
        if not isinstance(candidato, dict) or not isinstance(candidato.get("id"), str):
            continue
        regra = regras.get(candidato.get("id"))
        if (regra is not None and candidato == regra.model_dump()
                and payload.get("status") == "APROVADA" and payload.get("ativa") is True
                and payload.get("assinatura") == assinatura_regra(regra)):
            encontradas[regra.id] = regra
    return list(encontradas.values())

