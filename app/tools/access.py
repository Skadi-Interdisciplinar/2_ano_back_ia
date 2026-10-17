from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass

from app.tools.db import get_conn

NIVEIS_ACESSO_CONHECIDOS = {"SUPER_ADMIN", "ADMIN", "GESTOR", "OPERADOR"}


@dataclass(frozen=True)
class EscopoAcesso:
    usuario_id: int
    nivel_acesso: str
    cd_id: int | None


def validar_acesso(usuario_id: int, *, cursor=None) -> EscopoAcesso:
    """Consulta somente os campos aprovados para definir o escopo do usuario."""

    if cursor is None:
        with closing(get_conn()) as conexao, conexao.cursor() as cursor_local:
            return validar_acesso(usuario_id, cursor=cursor_local)
    cursor.execute(
        "SELECT id, nivel_acesso, cod_cd FROM tb_usuario WHERE id = %s",
        (usuario_id,),
    )
    linha = cursor.fetchone()
    if linha is None:
        raise PermissionError("Usuario autenticado nao encontrado no banco operacional.")
    nivel_acesso = str(linha[1]).strip().upper()
    if nivel_acesso not in NIVEIS_ACESSO_CONHECIDOS:
        raise PermissionError("Nivel de acesso do usuario nao reconhecido.")
    return EscopoAcesso(
        usuario_id=linha[0], nivel_acesso=nivel_acesso, cd_id=linha[2]
    )
