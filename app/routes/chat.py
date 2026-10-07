from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthenticatedUser, obter_usuario_autenticado
from app.graph import executar_fluxo_skadi
from app.memory import registrar_execucao_agente, salvar_mensagem_conversa
from app.schemas import ChatRequest, ChatResponse
from app.tools.access import validar_acesso

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trimmy"])


@router.post("/chat", response_model=ChatResponse)
def conversar(requisicao: ChatRequest) -> ChatResponse:
    usuario = obter_usuario_autenticado(requisicao.token)

    resposta, agentes = executar_fluxo_skadi(
        requisicao.mensagem,
        usuario.usuario_id,
    )

    return ChatResponse(
        resposta=resposta,
        agentes_chamados=agentes,
    )