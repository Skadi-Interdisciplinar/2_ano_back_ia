from __future__ import annotations

from app.routes.chat import router as chat_router
from fastapi import FastAPI, Request

app = FastAPI(
    title="Trimmy",
    description="IA para apoio ao monitoramento de camaras frigorificas.",
    version="0.1.0",
)


@app.middleware("http")
async def injetar_usuario_temporario(request: Request, call_next):
    """Define uma identidade temporaria para permitir testes de integracao mobile.

    ATENCAO: o bypass e temporario e deve ser removido quando a autenticacao do
    aplicativo mobile estiver disponivel. Enquanto isso, usa o usuario
    sintetico 2.
    """

    # TODO(autenticacao-mobile):
    # token = extrair_token_do_header(request)
    # usuario_id = validar_token_do_aplicativo(token)
    request.state.skadi_authenticated_user_id = 2
    return await call_next(request)


app.include_router(chat_router)
