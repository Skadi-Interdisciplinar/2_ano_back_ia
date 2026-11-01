"""Validação do JWT emitido pelo backend principal do Skadi."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from typing import Annotated

import jwt
from app import config
from app.erros import ServicoIndisponivel
from app.tools.db import get_conn
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

autenticacao_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    usuario_id: int


def usuario_bearer(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(autenticacao_bearer)],
) -> AuthenticatedUser:
    if credenciais is None or credenciais.scheme.lower() != "bearer" or not credenciais.credentials.strip():
        raise HTTPException(401, "Informe o JWT do login em Authorization: Bearer <JWT>. No Swagger, use Authorize.",
                            headers={"WWW-Authenticate": "Bearer"})
    return obter_usuario_autenticado(credenciais.credentials.strip())


def obter_usuario_autenticado(token: str) -> AuthenticatedUser:
    """Confere assinatura e datas antes de resolver o username no PostgreSQL."""
    chave = config.SECURITY_KEY
    if not chave or len(chave.encode("utf-8")) < 32:
        raise ServicoIndisponivel("SECURITY_KEY deve corresponder à chave HMAC do backend, com pelo menos 32 bytes.")
    tamanho = len(chave.encode("utf-8"))
    algoritmo = "HS512" if tamanho >= 64 else "HS384" if tamanho >= 48 else "HS256"
    try:
        claims = jwt.decode(token, chave, algorithms=["HS256", "HS384", "HS512"], options={"require": ["sub", "iat", "exp"]})
        if (not isinstance(claims["sub"], str) or not claims["sub"].strip()
                or type(claims["iat"]) is not int or type(claims["exp"]) is not int
                or claims["exp"] <= claims["iat"]):
            raise jwt.InvalidTokenError("Claims incompatíveis com o token de acesso.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sua sessão expirou. Faça login novamente no aplicativo.",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        raise HTTPException(401, "Token de acesso inválido. Faça login novamente no aplicativo.",
                            headers={"WWW-Authenticate": "Bearer"}) from None

    with closing(get_conn()) as conexao, conexao.cursor() as cursor:
        cursor.execute("SELECT id FROM tb_usuario WHERE username = %s", (claims["sub"],))
        linha = cursor.fetchone()
    if linha is None:
        raise HTTPException(401, "O usuário desta sessão não está mais cadastrado. Faça login novamente.",
                            headers={"WWW-Authenticate": "Bearer"})
    return AuthenticatedUser(usuario_id=linha[0])
