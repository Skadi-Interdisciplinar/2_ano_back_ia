"""Contrato temporário de identidade disponibilizada ao fluxo da IA."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    usuario_id: int


def obter_usuario_autenticado(token: str) -> AuthenticatedUser:
    """Retorna a identidade temporária até a validação real do token existir."""

    # TODO(autenticacao-mobile): validar o token e extrair o usuario_id.
    # O token é recebido para preservar o contrato do aplicativo mobile, mas
    # enquanto a autenticação não estiver integrada usa o usuário sintético 2.
    del token
    return AuthenticatedUser(usuario_id=2)
