from __future__ import annotations

from typing import Annotated

from app.auth import AuthenticatedUser, usuario_bearer
from app.graph import executar_fluxo_skadi
from app.memory import encerrar_sessao
from app.schemas import ChatRequest, ChatResponse, EncerrarChatResponse
from fastapi import APIRouter, Depends

router = APIRouter(tags=["trimmy"])


@router.post(
    "/chat/encerrar", response_model=EncerrarChatResponse,
    responses={
        401: {"description": "Token inválido, expirado ou usuário não encontrado."},
        409: {"description": "Sessão já em encerramento."},
        502: {"description": "Resumo não passou pela validação de saída."},
        503: {"description": "Infraestrutura ou provedor indisponível."},
    },
)
def encerrar(usuario: Annotated[AuthenticatedUser, Depends(usuario_bearer)]) -> EncerrarChatResponse:
    return EncerrarChatResponse(resumo=encerrar_sessao(usuario.usuario_id))


@router.post(
    "/chat", response_model=ChatResponse,
    responses={
        401: {"description": "Token inválido, expirado ou usuário não encontrado."},
        403: {"description": "Acesso não permitido."},
        409: {"description": "Sessão alterada durante a consulta."},
        502: {"description": "Resposta do modelo inválida."},
        503: {"description": "Infraestrutura ou provedor indisponível."},
    },
)
def conversar(requisicao: ChatRequest, usuario: Annotated[AuthenticatedUser, Depends(usuario_bearer)]) -> ChatResponse:

    resposta, agentes = executar_fluxo_skadi(
        requisicao.mensagem,
        usuario.usuario_id,
    )

    return ChatResponse(
        resposta=resposta,
        agentes_chamados=agentes,
    )
