"""Memória antiga, sempre filtrada pela identidade interna do usuário."""

from app.tools.contexto import obter_usuario_contexto
from app.vectorstore import buscar_resumos
from langchain.tools import tool
from pydantic import BaseModel, Field


class BuscarHistoricoArgs(BaseModel):
    busca: str = Field(min_length=1, description="Termo curto sobre uma conversa anterior.")


@tool(args_schema=BuscarHistoricoArgs)
def buscar_historico(busca: str) -> dict:
    """Busca até três resumos de conversas encerradas do usuário autenticado."""
    resultados = buscar_resumos(obter_usuario_contexto(), busca)
    return {"resumos": resultados, "encontrado": bool(resultados)}


TOOLS_MEMORIA = [buscar_historico]
