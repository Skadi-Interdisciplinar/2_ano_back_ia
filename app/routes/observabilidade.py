"""Painel agregado de observabilidade para usuários autenticados."""

from typing import Annotated

from app.auth import obter_usuario_autenticado
from app.observabilidade import painel_mobile
from app.schemas import ObservabilidadeResponse
from app.tools.access import validar_acesso
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

router = APIRouter(tags=["observabilidade"])
autenticacao_bearer = HTTPBearer(auto_error=False)


def _token_bearer(authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(autenticacao_bearer)] = None) -> str:
    """Extrai somente o token Bearer; evita token em URL ou corpo de GET."""
    if authorization is None or authorization.scheme.lower() != "bearer" or not authorization.credentials.strip():
        raise HTTPException(status_code=401, detail="No Swagger, clique em Authorize e informe o token (exemplo: teste). Nas demais chamadas, envie Authorization: Bearer seguido do token.")
    return authorization.credentials.strip()


@router.get(
    "/observabilidade", response_model=ObservabilidadeResponse,
    responses={
        401: {"description": "Token Bearer ausente ou inválido."},
        403: {"description": "Acesso não permitido."},
        503: {"description": "Banco de dados temporariamente indisponível."},
    },
)
def consultar_observabilidade(
    token: Annotated[str, Depends(_token_bearer)],
) -> dict:
    """Entrega métricas agregadas após conferir a identidade do usuário."""
    usuario = obter_usuario_autenticado(token)
    validar_acesso(usuario.usuario_id)
    return painel_mobile()
