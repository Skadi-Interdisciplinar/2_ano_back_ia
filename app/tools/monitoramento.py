from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from app.config import DATABASE_URL, REDIS_URL
from app.tools.access import EscopoAcesso, validar_acesso


@lru_cache(maxsize=1)
def _cliente_redis():
    """Reutiliza o cliente Redis durante a vida do processo da API."""

    import redis

    if not REDIS_URL:
        raise RuntimeError("REDIS_URL não configurada.")
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _camara_permitida(usuario_id: int, camara_id: int) -> tuple[EscopoAcesso, int, Decimal, Decimal]:
    escopo = validar_acesso(usuario_id)
    if escopo.nivel_acesso == "SUPER_ADMIN":
        consulta = """
            SELECT cod_termometro, temperatura_min, temperatura_max
            FROM tb_camara_frigorifica
            WHERE id = %s
        """
        parametros = (camara_id,)
    elif escopo.nivel_acesso in {"ADMIN", "GESTOR", "OPERADOR"} and escopo.cd_id is not None:
        consulta = """
            SELECT cod_termometro, temperatura_min, temperatura_max
            FROM tb_camara_frigorifica
            WHERE id = %s AND cod_cd = %s
        """
        parametros = (camara_id, escopo.cd_id)
    else:
        raise PermissionError("Usuário sem escopo de consulta de câmaras.")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")

    import psycopg2

    try:
        with psycopg2.connect(DATABASE_URL) as conexao, conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            linha = cursor.fetchone()
    except psycopg2.OperationalError as erro:
        raise RuntimeError("Banco de dados indisponível.") from erro
    if linha is None:
        raise PermissionError("Câmara não encontrada no escopo permitido.")
    return escopo, linha[0], linha[1], linha[2]


def consultar_leituras_temperatura(usuario_id: int, camara_id: int) -> dict:
    """Retorna a leitura recente do Redis para uma câmara autorizada."""

    _escopo, termometro_id, minimo, maximo = _camara_permitida(usuario_id, camara_id)
    import redis

    try:
        mensagens = _cliente_redis().xrevrange(
            "skadi:leituras:temperatura", max="+", min="-", count=1_000
        )
    except redis.exceptions.ConnectionError as erro:
        raise RuntimeError("Redis indisponível.") from erro
    for evento_id, campos in mensagens:
        if campos.get("cod_termometro") == str(termometro_id):
            return {
                "camara_id": camara_id,
                "termometro_id": termometro_id,
                "temperatura": campos.get("temperatura"),
                "data_hora": campos.get("data_hora"),
                "limite_minimo": str(minimo),
                "limite_maximo": str(maximo),
                "evento_redis": evento_id,
            }
    raise LookupError("Não há leitura recente disponível para esta câmara no Redis.")


def criar_tool_consultar_leitura_recente(usuario_id: int):
    """Cria a tool de monitoramento vinculada ao usuário já autenticado.

    O agente recebe somente ``camara_id``. O identificador do usuário é
    mantido no backend e nunca é fornecido pelo modelo ou pela requisição.
    """

    from langchain_core.tools import tool

    @tool
    def consultar_leitura_recente(camara_id: int) -> dict:
        """Consulta a leitura recente autorizada de uma câmara frigorífica."""

        return consultar_leituras_temperatura(usuario_id, camara_id)

    return consultar_leitura_recente
