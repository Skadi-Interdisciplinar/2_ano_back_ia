from __future__ import annotations

import logging

from app.auth import obter_usuario_autenticado
from app.graph import executar_fluxo_skadi
from app.schemas import ChatRequest, ChatResponse
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trimmy"])


@router.post("/chat", response_model=ChatResponse)
async def conversar(requisicao: ChatRequest) -> ChatResponse:
    usuario = obter_usuario_autenticado(requisicao.token)

    resposta, agentes = executar_fluxo_skadi(
        requisicao.mensagem,
        usuario.usuario_id,
    )

    return ChatResponse(
        resposta=resposta,
        agentes_chamados=agentes,
    )