from __future__ import annotations

import logging

from app.erros import SaidaModeloInvalida, ServicoIndisponivel, SessaoEmAlteracao
from app.llms import codigo_erro_groq
from app.routes.chat import router as chat_router
from app.routes.observabilidade import router as observabilidade_router
from app.routes.relatorios import router as relatorios_router
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.genai.errors import APIError as GeminiAPIError
from groq import APIError as GroqAPIError
from groq import BadRequestError
from httpx import HTTPError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langgraph.errors import GraphRecursionError
from psycopg2 import OperationalError
from pymongo.errors import PyMongoError
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Trimmy",
    description="IA para apoio ao monitoramento de camaras frigorificas.",
    version="0.1.0",
)


app.include_router(chat_router)
app.include_router(relatorios_router)
app.include_router(observabilidade_router)


@app.exception_handler(RequestValidationError)
async def requisicao_invalida(request: Request, erro: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "A requisição contém campos ausentes ou inválidos. Confira os campos obrigatórios e seus formatos no exemplo do Swagger."})


async def acesso_negado(request: Request, erro: PermissionError):
    return JSONResponse(status_code=403, content={"detail": "Seu usuário não tem acesso a esta operação ou aos dados solicitados. Confira seu cadastro, perfil e centro de distribuição."})


async def servico_indisponivel(request: Request, erro: Exception):
    if isinstance(erro, BadRequestError):
        logger.error("Rejeição Groq: HTTP=400 codigo=%s", codigo_erro_groq(erro))
        return JSONResponse(status_code=502, content={"detail": "O provedor de IA não conseguiu processar a chamada do agente. Tente novamente; se persistir, consulte o log do servidor.", "error": erro.message})
    logger.error("Serviço indisponível: %s", type(erro).__name__)
    mensagem = "Não foi possível concluir a solicitação porque um serviço necessário está indisponível. Aguarde e tente novamente; se persistir, confira as conexões e as cotas dos provedores no servidor."
    if isinstance(erro, OperationalError):
        mensagem = "Não foi possível conectar ao PostgreSQL para consultar os dados. Confira a conexão com o banco e tente novamente."
    elif isinstance(erro, PyMongoError):
        mensagem = "Não foi possível acessar o MongoDB para carregar ou salvar a conversa. Confira a conexão e a liberação do IP no Atlas."
    elif isinstance(erro, RedisError):
        mensagem = "Não foi possível acessar o Redis para consultar as leituras. Confira se o serviço está em execução e tente novamente."
    elif isinstance(erro, (UnexpectedResponse, ResponseHandlingException)):
        mensagem = "Não foi possível acessar o Qdrant para recuperar a base ou a memória. Confira a conexão e as coleções configuradas."
    return JSONResponse(status_code=503, content={"detail": mensagem, "error": erro.message})


async def saida_modelo_invalida(request: Request, erro: SaidaModeloInvalida):
    logger.error("Saída do modelo inválida: %s", type(erro).__name__)
    return JSONResponse(status_code=502, content={"detail": "A IA devolveu uma resposta que não atende ao formato ou às verificações exigidas. Tente reformular a pergunta; se persistir, consulte o log do servidor."})


app.add_exception_handler(PermissionError, acesso_negado)


@app.exception_handler(SessaoEmAlteracao)
async def sessao_em_alteracao(request: Request, erro: SessaoEmAlteracao):
    return JSONResponse(status_code=409, content={"detail": "A sessão mudou durante a consulta. Envie a pergunta novamente."})


app.add_exception_handler(SaidaModeloInvalida, saida_modelo_invalida)
for tipo in (
    ServicoIndisponivel, OperationalError, PyMongoError, RedisError,
    UnexpectedResponse, ResponseHandlingException, HTTPError, GeminiAPIError, GroqAPIError,
    ChatGoogleGenerativeAIError,
    GraphRecursionError,
):
    app.add_exception_handler(tipo, servico_indisponivel)
