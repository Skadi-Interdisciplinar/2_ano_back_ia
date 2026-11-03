"""Índice exclusivo de resumos da Trimmy; clientes criados sob demanda."""

from functools import lru_cache

from app.config import GEMINI_API_KEY, QDRANT_API_KEY, QDRANT_URL
from app.erros import ServicoIndisponivel

COLLECTION_MEMORIA = "trimmy_memoria_resumos"
EMBEDDING_DIM = 768


@lru_cache(maxsize=1)
def cliente_qdrant():
    from qdrant_client import QdrantClient

    if not QDRANT_URL:
        raise ServicoIndisponivel("QDRANT_URL não configurada.")
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


@lru_cache(maxsize=1)
def modelo_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    if not GEMINI_API_KEY:
        raise ServicoIndisponivel("GEMINI_API_KEY não configurada.")
    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2-preview", google_api_key=GEMINI_API_KEY,
    )


def gerar_embedding(texto: str) -> list[float]:
    return modelo_embeddings().embed_query(texto, output_dimensionality=EMBEDDING_DIM)


@lru_cache(maxsize=1)
def garantir_collection():
    from qdrant_client import models

    cliente = cliente_qdrant()
    if not cliente.collection_exists(COLLECTION_MEMORIA):
        cliente.create_collection(
            COLLECTION_MEMORIA,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
        )
    cliente.create_payload_index(
        collection_name=COLLECTION_MEMORIA,
        field_name="usuarioId",
        field_schema=models.PayloadSchemaType.INTEGER,
    )
    return cliente


def indexar_resumo(sessao_id: str, usuario_id: int, resumo: str) -> None:
    from qdrant_client import models

    cliente = garantir_collection()
    cliente.upsert(
        collection_name=COLLECTION_MEMORIA,
        points=[models.PointStruct(
            id=sessao_id, vector=gerar_embedding(resumo),
            payload={"usuarioId": usuario_id, "sessaoId": sessao_id, "resumo": resumo},
        )],
        wait=True,
    )


def buscar_resumos(usuario_id: int, busca: str) -> list[dict]:
    from qdrant_client import models

    resultado = garantir_collection().query_points(
        collection_name=COLLECTION_MEMORIA,
        query=gerar_embedding(busca),
        query_filter=models.Filter(must=[models.FieldCondition(
            key="usuarioId", match=models.MatchValue(value=usuario_id),
        )]),
        limit=3, with_payload=True,
    )
    # Defesa adicional: nunca entregar payload de outro usuário.
    return [
        {"resumo": ponto.payload["resumo"]}
        for ponto in resultado.points
        if ponto.payload and ponto.payload.get("usuarioId") == usuario_id
        and isinstance(ponto.payload.get("resumo"), str)
    ]
