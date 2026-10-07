"""Contrato temporário de identidade disponibilizada ao fluxo da IA."""

from __future__ import annotations

from dataclasses import dataclass

from jwt import decode

from app.config import JWT_SECRET_KEY
from app.tools.access import get_user_id


@dataclass(frozen=True)
class AuthenticatedUser:
    usuario_id: int


def obter_usuario_autenticado(token: str) -> AuthenticatedUser:
    """Retorna a identidade temporária até a validação real do token existir."""
    user_id = validate_token(token)
    return AuthenticatedUser(usuario_id=user_id)


def validate_token(token: str) -> int:
    """Valida o token e retorna o usuario_id."""
    try:
        payload = decode(token, JWT_SECRET_KEY,algorithms=["HS256"])
        username = payload["sub"]
        return get_user_id(username)
    except Exception as e:
        raise ValueError(f"Erro ao validar token: {e}")
