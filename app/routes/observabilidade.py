"""Painel agregado de observabilidade para usuários autenticados."""

from typing import Annotated

from app.auth import AuthenticatedUser, usuario_bearer
from app.observabilidade import painel_mobile
from app.schemas import ObservabilidadeResponse
from app.tools.access import validar_acesso
from fastapi import APIRouter, Depends

router = APIRouter(tags=["observabilidade"])


@router.get(
    "/observabilidade", response_model=ObservabilidadeResponse,
    responses={
        401: {"description": "Token Bearer ausente ou inválido."},
        403: {"description": "Acesso não permitido."},
        503: {"description": "Banco de dados temporariamente indisponível."},
    },
)
def consultar_observabilidade(
    usuario: Annotated[AuthenticatedUser, Depends(usuario_bearer)],
) -> dict:
    """Entrega métricas agregadas após conferir a identidade do usuário."""
    validar_acesso(usuario.usuario_id)
    return painel_mobile()
