from __future__ import annotations

from contextlib import closing
from functools import lru_cache

from app.config import REDIS_URL
from app.tools.access import validar_acesso
from app.tools.contexto import obter_usuario_contexto
from app.tools.db import get_conn
from langchain.tools import tool
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


@lru_cache(maxsize=1)
def _cliente_redis():
    """Reutiliza o cliente Redis durante a vida do processo da API."""

    import redis

    if not REDIS_URL:
        raise RuntimeError("REDIS_URL não configurada.")
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


class FiltrosCamaraArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    camara_id: int | None = Field(default=None, strict=True, description="ID informado explicitamente pelo usuário.")
    modelo: str | None = Field(default=None, min_length=1, description="Modelo cadastrado da câmara.")
    localizacao: str | None = Field(default=None, min_length=1, description="Localização cadastrada da câmara.")


class ConsultarTemperaturasArgs(FiltrosCamaraArgs):
    todas: StrictBool = Field(default=False, description="True somente quando o usuário pedir todas as câmaras permitidas.")

    @model_validator(mode="after")
    def validar_selecao(self):
        tem_filtro = any(v is not None for v in (self.camara_id, self.modelo, self.localizacao))
        if self.todas and tem_filtro:
            raise ValueError("Não combine todas=True com filtros de câmara.")
        if not self.todas and not tem_filtro:
            raise ValueError("Informe uma identificação ou solicite explicitamente todas=True.")
        return self


def consultar_camaras_permitidas(
    usuario_id: int, camara_id: int | None = None,
    modelo: str | None = None, localizacao: str | None = None,
) -> list[dict]:
    """Única consulta cadastral interna; aplica autorização antes dos filtros."""
    criterios = FiltrosCamaraArgs(camara_id=camara_id, modelo=modelo, localizacao=localizacao)
    escopo = validar_acesso(usuario_id)
    filtros = []
    parametros: list[object] = []
    if escopo.nivel_acesso == "SUPER_ADMIN":
        pass
    elif escopo.nivel_acesso in {"ADMIN", "GESTOR", "OPERADOR"} and escopo.cd_id is not None:
        filtros.append("cod_cd = %s")
        parametros.append(escopo.cd_id)
    else:
        raise PermissionError("Usuário sem escopo de consulta de câmaras.")
    if criterios.camara_id is not None:
        filtros.append("id = %s")
        parametros.append(criterios.camara_id)
    if criterios.modelo is not None:
        filtros.append("LOWER(modelo) = LOWER(%s)")
        parametros.append(criterios.modelo)
    if criterios.localizacao is not None:
        filtros.append("LOWER(localizacao) = LOWER(%s)")
        parametros.append(criterios.localizacao)
    # SQL contém somente cláusulas fixas; nenhum valor do usuário vira SQL.
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    consulta = f"""
        SELECT id, modelo, localizacao, cod_termometro, temperatura_min, temperatura_max
        FROM tb_camara_frigorifica
        {where}
        ORDER BY localizacao, modelo, id
    """
    with closing(get_conn()) as conexao, conexao.cursor() as cursor:
        cursor.execute(consulta, tuple(parametros))
        linhas = cursor.fetchall()
    return [
        {"camara_id": c[0], "modelo": c[1], "localizacao": c[2], "termometro": c[3],
         "limite_minimo": str(c[4]), "limite_maximo": str(c[5])}
        for c in linhas
    ]


def _cadastro_publico(camara: dict) -> dict:
    """IDs são dados internos, não contexto necessário ao modelo."""
    return {campo: camara[campo] for campo in (
        "modelo", "localizacao", "limite_minimo", "limite_maximo",
    )}


def _ultimas_leituras_permitidas(termometros: set[str]) -> dict[str, dict]:
    """Percorre o stream em lotes sem confundir ausência no lote com ausência de leitura."""
    import redis

    leituras: dict[str, dict] = {}
    limite_superior = "+"
    try:
        while termometros - leituras.keys():
            eventos = _cliente_redis().xrevrange(
                "skadi:leituras:temperatura", max=limite_superior, min="-", count=1_000,
            )
            if not eventos:
                break
            for evento_id, campos in eventos:
                sensor = campos.get("cod_termometro")
                if sensor in termometros and sensor not in leituras:
                    leituras[sensor] = {
                        "temperatura": campos.get("temperatura"),
                        "data_hora": campos.get("data_hora"),
                    }
            ultimo_id = eventos[-1][0]
            if ultimo_id == limite_superior or len(eventos) < 1_000:
                break
            # O limite é inclusivo: um evento se repete entre páginas, sem sobrescrever o mais novo.
            limite_superior = ultimo_id
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as erro:
        raise RuntimeError("Redis indisponível.") from erro
    return leituras


def consultar_temperaturas_permitidas(
    usuario_id: int, camara_id: int | None = None,
    modelo: str | None = None, localizacao: str | None = None, todas: bool = False,
) -> dict:
    """Uma implementação para todas as seleções; nunca amplia filtros após falha."""
    criterios = ConsultarTemperaturasArgs(
        camara_id=camara_id, modelo=modelo, localizacao=localizacao, todas=todas,
    )
    camaras = consultar_camaras_permitidas(
        usuario_id, criterios.camara_id, criterios.modelo, criterios.localizacao,
    )
    if not camaras:
        return {
            "status": "ok" if criterios.todas else "nao_encontrada", "camaras": [],
            "mensagem": "Nenhuma câmara encontrada no escopo permitido.",
        }
    if not criterios.todas and len(camaras) > 1:
        return {
            "status": "ambigua",
            "mensagem": "Mais de uma câmara corresponde à identificação. Peça esclarecimento.",
            "camaras": [_cadastro_publico(c) for c in camaras],
        }
    termometros = {str(c["termometro"]) for c in camaras if c["termometro"] is not None}
    leituras = _ultimas_leituras_permitidas(termometros)
    resultado = []
    for camara in camaras:
        leitura = leituras.get(str(camara["termometro"]))
        resultado.append({
            **_cadastro_publico(camara),
            "temperatura": leitura.get("temperatura") if leitura else None,
            "data_hora": leitura.get("data_hora") if leitura else None,
            "leitura_disponivel": bool(leitura and leitura.get("temperatura") is not None),
        })
    return {"status": "ok", "camaras": resultado}


def consultar_alertas_atuais(usuario_id: int) -> list[dict]:
    """Consulta alertas ativos ou reconhecidos pelo próprio usuário."""

    escopo = validar_acesso(usuario_id)
    filtros = [
        """
        (a.status = %s OR (a.status = %s AND EXISTS (
            SELECT 1
            FROM tb_atendimento atendimento
            WHERE atendimento.cod_alerta = a.id
              AND atendimento.cod_usuario = %s
        )))
        """
    ]
    parametros: list[object] = ["ativo", "reconhecido", usuario_id]

    if escopo.nivel_acesso == "SUPER_ADMIN":
        pass
    elif escopo.nivel_acesso in {"ADMIN", "GESTOR"} and escopo.cd_id is not None:
        filtros.append("camara.cod_cd = %s")
        parametros.append(escopo.cd_id)
    elif escopo.nivel_acesso == "OPERADOR" and escopo.cd_id is not None:
        filtros.extend(["camara.cod_cd = %s", "a.nivel_atual = %s"])
        parametros.extend([escopo.cd_id, "operador"])
    else:
        raise PermissionError("Usuário sem escopo de consulta de alertas.")

    consulta = f"""
        SELECT
            camara.modelo,
            camara.localizacao,
            a.nivel_gravidade,
            a.status,
            a.tipo,
            a.data_hora
        FROM tb_alerta a
        JOIN tb_camara_frigorifica camara ON camara.id = a.cod_camara_frigorifica
        WHERE {' AND '.join(filtros)}
        ORDER BY a.data_hora DESC
    """
    with closing(get_conn()) as conexao, conexao.cursor() as cursor:
        cursor.execute(consulta, parametros)
        linhas = cursor.fetchall()

    return [
        {
            "camara": f"{linha[0]} — {linha[1]}",
            "gravidade": linha[2],
            "status": linha[3],
            "tipo": linha[4],
            "data_hora": str(linha[5]),
        }
        for linha in linhas
    ]


@tool("consultar_temperaturas", args_schema=ConsultarTemperaturasArgs)
def consultar_temperaturas(
    camara_id: int | None = None, modelo: str | None = None,
    localizacao: str | None = None, todas: bool = False,
) -> dict:
    """Consulta temperaturas por ID/modelo/localização ou todas=True; identificação ambígua pede esclarecimento."""
    return consultar_temperaturas_permitidas(
        obter_usuario_contexto(), camara_id, modelo, localizacao, todas,
    )


@tool
def listar_camaras_responsaveis() -> list[dict]:
    """Lista cadastro e limites das câmaras permitidas, sem depender do Redis."""
    return [_cadastro_publico(c) for c in consultar_camaras_permitidas(obter_usuario_contexto())]


@tool
def consultar_alertas_atuais_do_usuario() -> list[dict]:
    """Lista alertas atuais permitidos ao usuário autenticado."""
    return consultar_alertas_atuais(obter_usuario_contexto())


TOOLS = [
    consultar_temperaturas,
    listar_camaras_responsaveis,
    consultar_alertas_atuais_do_usuario,
]
