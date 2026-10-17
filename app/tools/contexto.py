"""Contexto autenticado interno disponível às tools durante um fluxo."""

from __future__ import annotations

from contextvars import ContextVar, Token

_usuario_id_atual: ContextVar[int | None] = ContextVar(
    "usuario_id_atual",
    default=None,
)


def definir_usuario_contexto(usuario_id: int) -> Token[int | None]:
    """Vincula um usuário autenticado à execução atual do fluxo."""

    return _usuario_id_atual.set(usuario_id)


def restaurar_usuario_contexto(token: Token[int | None]) -> None:
    """Remove o usuário do contexto após o fim do fluxo."""

    _usuario_id_atual.reset(token)


def obter_usuario_contexto() -> int:
    """Retorna a identidade interna sem expô-la como argumento de tool."""

    usuario_id = _usuario_id_atual.get()
    if usuario_id is None:
        raise RuntimeError("Tool operacional exige um usuário autenticado.")
    return usuario_id
