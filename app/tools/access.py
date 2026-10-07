from __future__ import annotations

from dataclasses import dataclass

from app.config import DATABASE_URL

NIVEIS_ACESSO_CONHECIDOS = {"SUPER_ADMIN", "ADMIN", "GESTOR", "OPERADOR"}


@dataclass(frozen=True)
class EscopoAcesso:
    usuario_id: int
    nivel_acesso: str
    cd_id: int | None


def validar_acesso(usuario_id: int) -> EscopoAcesso:
    """Consulta somente os campos aprovados para definir o escopo do usuario."""

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL nao configurada.")
    import psycopg2

    with psycopg2.connect(DATABASE_URL) as conexao, conexao.cursor() as cursor:
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
