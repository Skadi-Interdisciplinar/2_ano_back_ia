"""Tools do domínio diagnóstico; identidade sempre vem do backend."""

from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from uuid import uuid4

from app.diagnostico import SaidaDiagnosticoInvalida, obter_contexto_diagnostico
from app.regras_diagnostico import recuperar_regras
from app.tools.access import validar_acesso
from app.tools.contexto import obter_usuario_contexto
from app.tools.db import get_conn
from app.tools.monitoramento import (
    FiltrosCamaraArgs,
    _cadastro_publico,
    _ultimas_leituras_permitidas,
    consultar_alertas_permitidos,
    consultar_camaras_permitidas,
)
from langchain.tools import tool
from pydantic import BaseModel, ConfigDict, Field


class ConsultarEvidenciasArgs(FiltrosCamaraArgs):
    ultimo_alerta: bool = Field(
        default=False, strict=True,
        description="True somente quando o usuário pedir o último alerta ou o mais recente permitido.",
    )
    alerta_id: int | None = Field(
        default=None, strict=True,
        description="ID interno retornado por consulta desta execução. Nunca inventar.",
    )


class BuscarRegrasArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    busca: str = Field(min_length=1, description="Fator de temperatura ou assunto técnico da ocorrência, sem instruções de aprovação.")


@tool("consultar_evidencias_diagnostico", args_schema=ConsultarEvidenciasArgs)
def consultar_evidencias_diagnostico(
    camara_id: int | None = None, modelo: str | None = None,
    localizacao: str | None = None, alerta_id: int | None = None,
    ultimo_alerta: bool = False,
) -> dict:
    """Reúne dados permitidos de uma única câmara e justificativas da ocorrência selecionada."""
    usuario = obter_usuario_contexto()
    contexto = obter_contexto_diagnostico()
    validar_acesso(usuario)
    if ultimo_alerta and alerta_id is not None:
        raise SaidaDiagnosticoInvalida("Escolha último alerta ou alerta específico, não ambos.")
    referencia = str(uuid4())
    dados: dict = {"referencia": referencia, "status": "identificacao_necessaria", "opcoes": []}
    dados["ultimo_alerta_solicitado"] = ultimo_alerta
    if all(v is None for v in (camara_id, modelo, localizacao)):
        dados["mensagem"] = "Qual câmara deseja analisar? Informe modelo ou localização."
    else:
        camaras = consultar_camaras_permitidas(usuario, camara_id, modelo, localizacao)
        if not camaras:
            dados.update(status="nao_encontrada", mensagem="Câmara não encontrada no escopo permitido.")
        elif len(camaras) != 1:
            dados.update(
                status="camara_ambigua", mensagem="Há mais de uma câmara. Qual modelo/localização deseja analisar?",
                opcoes=[_cadastro_publico(c) for c in camaras],
            )
        else:
            camara = camaras[0]
            alertas = consultar_alertas_permitidos(usuario, camara["camara_id"])
            if ultimo_alerta and alertas:
                # A consulta compartilhada já ordena por data_hora DESC. Empates
                # continuam ambíguos: não escolher uma ocorrência pelo ID.
                horario = alertas[0]["data_hora"]
                alertas = [a for a in alertas if a["data_hora"] == horario]
            dados["camara"] = _cadastro_publico(camara)
            # O ID opcional só pode selecionar uma opção retornada por tool nesta execução.
            if alerta_id is not None:
                anteriores = {
                    a["alerta_id"] for e in contexto.evidencias.values()
                    if e.get("_camara_id") == camara["camara_id"]
                    for a in e.get("_alertas", [])
                }
                if alerta_id not in anteriores:
                    raise PermissionError("Alerta não disponível na consulta autorizada.")
                alertas = [a for a in alertas if a["alerta_id"] == alerta_id]
                if not alertas:
                    raise PermissionError("Alerta não disponível no escopo permitido.")
            dados["_camara_id"] = camara["camara_id"]
            dados["_alertas"] = deepcopy(alertas)
            if len(alertas) > 1:
                dados.update(
                    status="alerta_ambiguo",
                    mensagem="Há mais de uma ocorrência. Qual tipo e horário deseja analisar?",
                    opcoes=[{k: a[k] for k in ("alerta_id", "tipo", "status", "data_hora")} for a in alertas],
                )
            else:
                sensor = camara["termometro"]
                leituras = _ultimas_leituras_permitidas({str(sensor)} if sensor is not None else set())
                dados.update(
                    status="ok", leitura=leituras.get(str(sensor)), alerta=None, justificativas=[],
                )
                if alertas:
                    alerta = alertas[0]
                    if not consultar_alertas_permitidos(
                        usuario, camara["camara_id"], alerta["alerta_id"],
                    ):
                        raise PermissionError("Alerta não disponível no escopo permitido.")
                    dados["alerta"] = {k: alerta[k] for k in ("tipo", "status", "gravidade", "data_hora")}
                    # Schema e FKs conferidos no PostgreSQL em 2026-10-11.
                    with closing(get_conn()) as conexao, conexao.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT j.id, j.motivo, j.descricao, j.data_hora
                            FROM tb_justificativa j
                            JOIN tb_atendimento atendimento ON atendimento.id = j.cod_atendimento
                            JOIN tb_alerta a ON a.id = atendimento.cod_alerta
                            WHERE a.id = %s AND a.cod_camara_frigorifica = %s
                            ORDER BY j.data_hora, j.id
                            """,
                            (alerta["alerta_id"], camara["camara_id"]),
                        )
                        justificativas = cursor.fetchall()
                    for j in justificativas:
                        ref = f"justificativa:{referencia}:{j[0]}"
                        justificativa = {
                            "origem_ref": ref, "motivo": j[1], "descricao": j[2],
                            "data_hora": str(j[3]),
                        }
                        dados["justificativas"].append(justificativa)
                        contexto.fontes[ref] = {
                            "texto": f"{j[1]}\n{j[2]}", "evidencia_ref": referencia,
                        }
    contexto.evidencias[referencia] = deepcopy(dados)
    # _camara_id/_alertas são somente backend; alerta_id é seletor interno, não resposta pública.
    return {k: deepcopy(v) for k, v in dados.items() if not k.startswith("_")}


@tool("buscar_regras_diagnostico", args_schema=BuscarRegrasArgs)
def buscar_regras_diagnostico(busca: str) -> list[dict]:
    """Recupera somente regras técnicas aprovadas e ativas, com requisitos e fontes."""
    usuario = obter_usuario_contexto()
    contexto = obter_contexto_diagnostico()
    escopo = validar_acesso(usuario)
    if escopo.nivel_acesso != "SUPER_ADMIN" and escopo.cd_id is None:
        raise PermissionError("Usuário sem escopo de diagnóstico.")
    regras = recuperar_regras(busca)
    contexto.regras_consultadas = True
    contexto.regras.update({r.id: r for r in regras})
    return [r.model_dump() for r in regras]


TOOLS = [consultar_evidencias_diagnostico, buscar_regras_diagnostico]

