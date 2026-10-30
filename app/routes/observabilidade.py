"""Painel agregado de observabilidade para usuários autenticados."""

from typing import Annotated

from app.auth import obter_usuario_autenticado
from app.observabilidade import painel_mobile
from app.schemas import ObservabilidadeResponse
from app.tools.access import validar_acesso
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(tags=["observabilidade"])


def _token_bearer(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extrai somente o token Bearer; evita token em URL ou corpo de GET."""
    esquema, separador, token = (authorization or "").partition(" ")
    if esquema.lower() != "bearer" or not separador or not token.strip():
        raise HTTPException(status_code=401, detail="Preencha o cabeçalho authorization com Bearer seguido do token. Exemplo: Bearer teste.")
    return token.strip()


@router.get(
    "/observabilidade", response_model=ObservabilidadeResponse,
    responses={
        401: {"description": "Token Bearer ausente ou inválido."},
        403: {"description": "Acesso não permitido."},
        503: {"description": "Banco de dados temporariamente indisponível."},
    },
)
def consultar_observabilidade(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Entrega métricas agregadas após conferir a identidade do usuário."""
    usuario = obter_usuario_autenticado(_token_bearer(authorization))
    validar_acesso(usuario.usuario_id)
    return painel_mobile()
