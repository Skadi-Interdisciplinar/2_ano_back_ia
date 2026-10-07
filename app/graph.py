from __future__ import annotations

import json
import operator
from typing import Annotated, TypedDict

from app.llms import obter_modelos
from app.memory import salvar_mensagem_conversa
from app.prompts import (
    DIAGNOSTICO_PROMPT,
    FAQ_PROMPT,
    MONITORAMENTO_PROMPT,
    ORQUESTRADOR_PROMPT,
    PREDICAO_PROMPT,
    RELATORIOS_PROMPT,
    ROTEADOR_PROMPT,
)

ROTAS_ESPECIALISTAS = (
    "monitoramento",
    "predicao",
    "diagnostico",
    "relatorios",
    "faq",
)
ROTAS = frozenset((*ROTAS_ESPECIALISTAS, "orquestrador"))
PROMPTS_POR_ROTA = {
    "monitoramento": MONITORAMENTO_PROMPT,
    "predicao": PREDICAO_PROMPT,
    "diagnostico": DIAGNOSTICO_PROMPT,
    "relatorios": RELATORIOS_PROMPT,
    "faq": FAQ_PROMPT,
}


class EstadoSkadi(TypedDict):
    pergunta_original: str
    usuario_id: int | None
    rota: str
    resposta: str
    respostas_agentes: Annotated[list[dict[str, str]], operator.add]
    agentes_chamados: Annotated[list[str], operator.add]


def _rota_texto(valor: str) -> str:
    for linha in valor.splitlines():
        if linha.strip().upper().startswith("ROUTE="):
            rota = linha.split("=", 1)[1].strip().lower()
            if rota in ROTAS:
                return rota
    return "orquestrador"


def _rotear(estado: EstadoSkadi) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage

    _, modelo_rapido = obter_modelos()
    resposta = modelo_rapido.invoke([
        SystemMessage(content=ROTEADOR_PROMPT),
        HumanMessage(content=estado["pergunta_original"]),
    ])
    return {"rota": _rota_texto(str(resposta.content)), "agentes_chamados": ["roteador"]}


def _executar_especialista(estado: EstadoSkadi) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage

    rota = estado["rota"]
    if rota == "monitoramento":
        if estado.get("usuario_id") is None:
            raise RuntimeError("Monitoramento exige um usuário autenticado.")

        from app.tools.monitoramento import criar_tool_consultar_leitura_recente
        from langchain.agents import create_agent

        modelo, _ = obter_modelos()
        consultar_leitura_recente = criar_tool_consultar_leitura_recente(
            estado["usuario_id"]
        )

        agente = create_agent(
            model=modelo,
            system_prompt=(
                MONITORAMENTO_PROMPT
                + " Quando o usuário pedir uma câmara identificada, chame "
                "consultar_leitura_recente antes de responder."
            ),
            tools=[consultar_leitura_recente],
        )
        saida = agente.invoke({"messages": [HumanMessage(content=estado["pergunta_original"])]})
        resposta = str(saida["messages"][-1].content)
        return {
            "respostas_agentes": [{"agente": rota, "resposta": resposta}],
            "agentes_chamados": [rota],
        }
    modelo, _ = obter_modelos()
    resposta = modelo.invoke([
        SystemMessage(content=PROMPTS_POR_ROTA[rota]),
        HumanMessage(content=estado["pergunta_original"]),
    ])
    return {
        "respostas_agentes": [{"agente": rota, "resposta": str(resposta.content)}],
        "agentes_chamados": [rota],
    }


def _orquestrar(estado: EstadoSkadi) -> dict:
    """Entrega a resposta final sem consultar tools ou complementar especialistas."""

    from langchain_core.messages import HumanMessage, SystemMessage

    modelo, _ = obter_modelos()
    contexto = {
        "pergunta_original": estado["pergunta_original"],
        "respostas_agentes": estado["respostas_agentes"],
    }
    resposta = modelo.invoke([
        SystemMessage(content=ORQUESTRADOR_PROMPT),
        HumanMessage(content=json.dumps(contexto, ensure_ascii=False)),
    ])
    return {"resposta": str(resposta.content), "agentes_chamados": ["orquestrador"]}


def _escolher_rota(estado: EstadoSkadi) -> str:
    return estado["rota"]


def construir_fluxo():
    from langgraph.graph import END, StateGraph

    fluxo = StateGraph(EstadoSkadi)
    fluxo.add_node("roteador", _rotear)
    for rota in ROTAS_ESPECIALISTAS:
        fluxo.add_node(rota, _executar_especialista)
    fluxo.add_node("orquestrador", _orquestrar)
    fluxo.set_entry_point("roteador")
    fluxo.add_conditional_edges("roteador", _escolher_rota, {rota: rota for rota in ROTAS})
    for rota in ROTAS_ESPECIALISTAS:
        fluxo.add_edge(rota, "orquestrador")
    fluxo.add_edge("orquestrador", END)
    return fluxo.compile()


FLUXO_SKADI = construir_fluxo()


def executar_fluxo_skadi(mensagem: str, usuario_id: int | None = None) -> tuple[str, list[str]]:
    estado = FLUXO_SKADI.invoke({
        "pergunta_original": mensagem,
        "usuario_id": usuario_id,
        "rota": "orquestrador",
        "resposta": "",
        "respostas_agentes": [],
        "agentes_chamados": [],
    })

    # A rota permanece apenas como contrato HTTP. O contexto e persistido pelo
    # fluxo depois que a resposta final foi produzida, como no Assessor.
    if usuario_id is not None:
        salvar_mensagem_conversa(usuario_id, "usuario", mensagem, "texto")
        salvar_mensagem_conversa(
            usuario_id,
            "assistente",
            estado["resposta"],
            "texto",
            "orquestrador",
        )
    return estado["resposta"], estado["agentes_chamados"]
