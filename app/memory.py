"""Persistencia do contexto de conversa e das execucoes no MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone

from typing import Any

from app.config import MONGODB_URI

_client: Any = None


def _database():
    global _client
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI nao configurada.")
    if _client is None:
        from pymongo import MongoClient

        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)
    return _client["Skadi"]


def carregar_contexto_conversa(usuario_id: int, limite: int = 20) -> list[dict[str, Any]]:
    documento = _database().conversas.find_one({"usuarioId": usuario_id})
    if not documento:
        return []
    mensagens = documento.get("mensagens", [])
    return mensagens[-limite:]


def salvar_mensagem_conversa(usuario_id: int, remetente: str, conteudo: str, tipo: str, agente: str | None = None) -> None:
    agora = datetime.now(timezone.utc)
    mensagem: dict[str, Any] = {
        "dataHora": agora,
        "remetente": remetente,
        "conteudo": conteudo,
        "tipo": tipo,
    }
    if agente:
        mensagem["agente"] = agente
    _database().conversas.update_one(
        {"usuarioId": usuario_id},
        {
            "$setOnInsert": {"usuarioId": usuario_id, "inicio": agora},
            "$set": {"ultimaAtualizacao": agora},
            "$push": {"mensagens": mensagem},
        },
        upsert=True,
    )


def registrar_execucao_agente(agente: str, entrada: dict[str, Any], status: str, termino: datetime | None = None) -> None:
    documento: dict[str, Any] = {
        "agente": agente,
        "inicio": datetime.now(timezone.utc),
        "entrada": entrada,
        "status": status,
    }
    if termino is not None:
        documento["termino"] = termino
    _database().execucoes_agentes.insert_one(documento)
