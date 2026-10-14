"""Execução e apresentação da predição: somente resultados calculados pelo backend."""

from __future__ import annotations

import json
from contextlib import closing
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.erros import SaidaModeloInvalida, ServicoIndisponivel
from app.modelos_predicao import FUSO_LEITURAS, momento
from app.tools.access import validar_acesso
from app.tools.contexto import obter_usuario_contexto
from app.tools.db import get_conn
from langchain.agents.middleware import wrap_model_call
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ResultadoPredicao(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    status: Literal["ok", "esclarecimento", "indisponivel", "dados_invalidos"]
    mensagem: str = ""
    camara: dict = Field(default_factory=dict)
    temperatura_base: float | None = None
    temperatura_prevista: float | None = None
    horario_base: datetime | None = None
    horario_previsto: datetime | None = None
    horizonte_minutos: int | None = None
    comparacao: Literal["abaixo_minimo", "dentro_faixa", "acima_maximo"] | None = None
    versao_modelo: str | None = None
    dados_simulados: bool = False


@dataclass
class ContextoPredicao:
    usuario_id: int
    resultados: dict[str, ResultadoPredicao] = field(default_factory=dict)


contexto_predicao: ContextVar[ContextoPredicao | None] = ContextVar("contexto_predicao", default=None)


@wrap_model_call
def _exigir_consulta_predicao(request, handler):
    """Histórico identifica parâmetros, mas nunca substitui a única tool autorizada."""
    return handler(request.override(tool_choice="prever_temperatura"))


def validar_acesso_predicao() -> int:
    usuario = obter_usuario_contexto()
    escopo = validar_acesso(usuario)
    if escopo.nivel_acesso not in {"SUPER_ADMIN", "ADMIN", "GESTOR"}:
        raise PermissionError("Perfil sem acesso à predição.")
    if escopo.nivel_acesso != "SUPER_ADMIN" and escopo.cd_id is None:
        raise PermissionError("Usuário sem CD para predição.")
    return usuario


def consultar_serie(camara: dict, inicio: datetime, fim: datetime | None = None,
                    *, ultimas: bool = False) -> list[tuple]:
    """Consulta interna: recebe cadastro já autorizado; reutilizada no treinamento."""
    parametros = [camara["termometro"], momento(inicio).astimezone(FUSO_LEITURAS).replace(tzinfo=None)]
    filtro_fim = ""
    if fim is not None:
        filtro_fim = " AND data_hora <= %s"
        parametros.append(momento(fim).astimezone(FUSO_LEITURAS).replace(tzinfo=None))
    ordenacao = "ORDER BY data_hora DESC, id DESC LIMIT 2" if ultimas else "ORDER BY data_hora, id"
    with closing(get_conn()) as conexao, conexao.cursor() as cursor:
        cursor.execute(
            "SELECT temperatura, data_hora FROM tb_leitura_temperatura "
            f"WHERE cod_termometro = %s AND data_hora >= %s{filtro_fim} {ordenacao}",
            tuple(parametros),
        )
        return cursor.fetchall()


def executar_predicao(mensagens: list, modelo=None) -> ResultadoPredicao:
    from app.llms import criar_agente, obter_modelos
    from app.prompts import PREDICAO_PROMPT
    from app.tools.predicao import TOOLS
    from langchain_core.messages import ToolMessage

    usuario = validar_acesso_predicao()
    if modelo is None:
        modelo = obter_modelos()[0]
    contexto = ContextoPredicao(usuario)
    token = contexto_predicao.set(contexto)
    try:
        agente = criar_agente(
            model=modelo, system_prompt=PREDICAO_PROMPT, tools=TOOLS,
            middleware=[_exigir_consulta_predicao],
        )
        try:
            saida = agente.invoke({"messages": mensagens})
            ultima = saida["messages"][-1]
            if not isinstance(ultima, ToolMessage) or ultima.name != "prever_temperatura":
                raise SaidaModeloInvalida("Predição exige retorno da tool autorizada.")
            dados = json.loads(ultima.content)
            referencia = dados.pop("referencia")
            resultado = ResultadoPredicao.model_validate(dados)
        except (ValidationError, AttributeError, TypeError, ValueError, KeyError, IndexError) as erro:
            raise SaidaModeloInvalida("Saída estruturada da predição inválida.") from erro
        except RuntimeError as erro:
            raise ServicoIndisponivel("Predição temporariamente indisponível.") from erro
        if (len(contexto.resultados) != 1 or not isinstance(referencia, str)
                or referencia not in contexto.resultados):
            raise SaidaModeloInvalida("Referência de predição inválida.")
        original = contexto.resultados[referencia]
        if resultado != original:
            raise SaidaModeloInvalida("Resultado da predição foi alterado.")
        return original.model_copy(deep=True)
    finally:
        contexto_predicao.reset(token)


def apresentar_predicao(resultado: ResultadoPredicao) -> str:
    if resultado.status != "ok":
        return resultado.mensagem
    camara = resultado.camara
    posicao = {"abaixo_minimo": "abaixo do mínimo", "acima_maximo": "acima do máximo",
               "dentro_faixa": "dentro da faixa"}[resultado.comparacao]
    aviso = "Dados e modelo simulados para teste; não representam medições reais nem precisão operacional. " if resultado.dados_simulados else ""
    return aviso + (
        f"Para {camara['modelo']}, em {camara['localizacao']}, a estimativa experimental "
        f"é de {resultado.temperatura_prevista:.2f} °C em "
        f"{resultado.horario_previsto.astimezone(FUSO_LEITURAS).isoformat()}. "
        f"O horizonte de {resultado.horizonte_minutos} minutos é contado a partir da leitura "
        f"de {resultado.temperatura_base:.2f} °C, registrada em "
        f"{resultado.horario_base.astimezone(FUSO_LEITURAS).isoformat()}, não do momento da pergunta. "
        f"Comparada à faixa cadastrada de {camara['limite_minimo']} a {camara['limite_maximo']} °C, "
        f"essa estimativa fica {posicao}. É uma projeção AR(1), não confirmação da temperatura "
        "atual ou futura, de falha mecânica ou de segurança dos produtos. Não considera causas "
        "como carregamento, abertura de porta ou degelo e não substitui avaliação humana."
    )
