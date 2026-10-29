"""Contrato temporário de identidade disponibilizada ao fluxo da IA."""

from __future__ import annotations

from dataclasses import dataclass

from app import config


@dataclass(frozen=True)
class AuthenticatedUser:
    usuario_id: int


def obter_usuario_autenticado(token: str) -> AuthenticatedUser:
    """Retorna a identidade temporária até a validação real do token existir."""

    # TODO(autenticacao-mobile): validar o token e extrair o usuario_id.
    # O token é recebido para preservar o contrato do aplicativo mobile, mas
    # enquanto a autenticação não estiver integrada usa a identidade configurada
    # no servidor. O padrão é 12 (GESTOR). As permissões vêm do banco.
    del token
    return AuthenticatedUser(usuario_id=config.USUARIO_TESTE_ID)
