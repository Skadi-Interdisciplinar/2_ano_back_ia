from __future__ import annotations

from app.auth import obter_usuario_autenticado
from app.graph import executar_fluxo_skadi
from app.memory import encerrar_sessao
from app.schemas import ChatRequest, ChatResponse, EncerrarChatRequest, EncerrarChatResponse
from fastapi import APIRouter

router = APIRouter(tags=["trimmy"])


@router.post("/chat/encerrar", response_model=EncerrarChatResponse)
def encerrar(requisicao: EncerrarChatRequest) -> EncerrarChatResponse:
    usuario = obter_usuario_autenticado(requisicao.token)
    return EncerrarChatResponse(resumo=encerrar_sessao(usuario.usuario_id))


@router.post(
    "/chat", response_model=ChatResponse,
    responses={
        403: {"description": "Acesso não permitido."},
        502: {"description": "Resposta do modelo inválida."},
        503: {"description": "Infraestrutura ou provedor indisponível."},
    },
)
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
