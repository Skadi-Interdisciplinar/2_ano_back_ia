from __future__ import annotations

import json
import operator
from typing import Annotated, TypedDict

from app.erros import SaidaModeloInvalida
from app.llms import criar_agente, obter_modelos
from app.memory import carregar_contexto_conversa, salvar_mensagem_conversa
from app.prompts import (
    FAQ_PROMPT,
    MONITORAMENTO_PROMPT,
    ORQUESTRADOR_PROMPT,
    RELATORIOS_PROMPT,
    ROTEADOR_PROMPT,
)
from app.schemas import DecisaoRota
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from pydantic import ValidationError

ROTAS_ESPECIALISTAS = (
    "monitoramento",
    "predicao",
    "diagnostico",
    "relatorios",
    "faq",
)
ROTAS = frozenset((*ROTAS_ESPECIALISTAS, "orquestrador"))
PROMPTS_POR_ROTA = {
    "relatorios": RELATORIOS_PROMPT,
    "faq": FAQ_PROMPT,
}


class EstadoSkadi(TypedDict):
    pergunta_original: str
    historico: list[dict[str, str]]
    usuario_id: int | None
    rota: str
    resposta: str
    respostas_agentes: Annotated[list[dict[str, str]], operator.add]
    agentes_chamados: Annotated[list[str], operator.add]


def _mensagens_da_conversa(estado: EstadoSkadi) -> list:
    """Converte apenas falas anteriores; histórico nunca vira instrução de sistema."""

    from langchain_core.messages import AIMessage, HumanMessage

    mensagens = []
    for entrada in estado.get("historico", []):
        if entrada["remetente"] == "usuario":
            mensagens.append(HumanMessage(content=entrada["conteudo"]))
        elif entrada["remetente"] == "assistente":
            mensagens.append(AIMessage(content=entrada["conteudo"]))
    mensagens.append(HumanMessage(content=estado["pergunta_original"]))
    return mensagens


def _rotear(estado: EstadoSkadi) -> dict:
    from langchain.agents.structured_output import StructuredOutputError, ToolStrategy

    _, modelo_rapido = obter_modelos()
    tools = []
    if estado.get("usuario_id") is not None:
        from app.tools.memoria import TOOLS_MEMORIA

        tools = TOOLS_MEMORIA
    agente = criar_agente(
        model=modelo_rapido, system_prompt=ROTEADOR_PROMPT, tools=tools,
        response_format=ToolStrategy(DecisaoRota, handle_errors=False),
    )
    try:
        saida = agente.invoke({"messages": _mensagens_da_conversa(estado)})
    except StructuredOutputError as erro:
        raise SaidaModeloInvalida("Saída estruturada do roteador inválida.") from erro
    try:
        decisao = DecisaoRota.model_validate(saida.get("structured_response"))
    except (ValidationError, AttributeError, TypeError) as erro:
        # Falha de formato não significa que a pergunta esteja fora do Skadi.
        raise SaidaModeloInvalida("Saída estruturada do roteador inválida.") from erro
    return {"rota": decisao.rota, "agentes_chamados": ["roteador"]}


def _executar_especialista(estado: EstadoSkadi) -> dict:
    from langchain_core.messages import SystemMessage

    rota = estado["rota"]
    if rota == "predicao":
        if estado.get("usuario_id") is None:
            raise PermissionError("Predição exige um usuário autenticado.")
        from app.predicao import executar_predicao

        resultado = executar_predicao(_mensagens_da_conversa(estado))
        return {
            "respostas_agentes": [{"agente": rota, "resposta": resultado.model_dump_json()}],
            "agentes_chamados": [rota],
        }
    if rota == "diagnostico":
        if estado.get("usuario_id") is None:
            raise PermissionError("Diagnóstico exige um usuário autenticado.")
        from app.diagnostico import executar_diagnostico

        modelo, _ = obter_modelos()
        analise = executar_diagnostico(_mensagens_da_conversa(estado), modelo)
        return {
            "respostas_agentes": [{"agente": rota, "resposta": analise.model_dump_json()}],
            "agentes_chamados": [rota],
        }
    if rota == "monitoramento":
        if estado.get("usuario_id") is None:
            raise RuntimeError("Monitoramento exige um usuário autenticado.")

        from app.tools.memoria import TOOLS_MEMORIA
        from app.tools.monitoramento import TOOLS

        modelo, _ = obter_modelos()

        agente = criar_agente(
            model=modelo,
            system_prompt=MONITORAMENTO_PROMPT,
            tools=TOOLS + TOOLS_MEMORIA,
        )
        saida = agente.invoke({"messages": _mensagens_da_conversa(estado)})
        resposta = str(saida["messages"][-1].content)
        return {
            "respostas_agentes": [{"agente": rota, "resposta": resposta}],
            "agentes_chamados": [rota],
        }
    modelo, _ = obter_modelos()
    if estado.get("usuario_id") is not None:
        from app.tools.memoria import TOOLS_MEMORIA

        agente = criar_agente(model=modelo, system_prompt=PROMPTS_POR_ROTA[rota], tools=TOOLS_MEMORIA)
        saida = agente.invoke({"messages": _mensagens_da_conversa(estado)})
        resposta = saida["messages"][-1]
    else:
        resposta = modelo.invoke([
            SystemMessage(content=PROMPTS_POR_ROTA[rota]),
            *_mensagens_da_conversa(estado),
        ])
    return {
        "respostas_agentes": [{"agente": rota, "resposta": str(resposta.content)}],
        "agentes_chamados": [rota],
    }


def _orquestrar(estado: EstadoSkadi) -> dict:
    """Entrega a resposta final sem consultar tools ou complementar especialistas."""

    from langchain_core.messages import HumanMessage, SystemMessage

    predicoes = [r for r in estado["respostas_agentes"] if r["agente"] == "predicao"]
    if predicoes:
        from app.predicao import ResultadoPredicao, apresentar_predicao

        resultado = ResultadoPredicao.model_validate_json(predicoes[-1]["resposta"])
        return {"resposta": apresentar_predicao(resultado), "agentes_chamados": ["orquestrador"]}
    diagnosticos = [
        r for r in estado["respostas_agentes"] if r["agente"] == "diagnostico"
    ]
    if diagnosticos:
        from app.diagnostico import AnaliseDiagnostico, apresentar_diagnostico

        analise = AnaliseDiagnostico.model_validate_json(diagnosticos[-1]["resposta"])
        return {
            "resposta": apresentar_diagnostico(analise),
            "agentes_chamados": ["orquestrador"],
        }
    modelo, _ = obter_modelos()
    contexto = {
        "pergunta_original": estado["pergunta_original"],
        "historico": estado.get("historico", []),
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
    token_contexto = (
        definir_usuario_contexto(usuario_id) if usuario_id is not None else None
    )
    try:
        contexto_anterior = carregar_contexto_conversa(usuario_id) if usuario_id is not None else []
        historico = [
            {"remetente": item["remetente"], "conteudo": item["conteudo"]}
            for item in contexto_anterior
            if item.get("remetente") in {"usuario", "assistente"}
            and isinstance(item.get("conteudo"), str)
        ]
        estado = FLUXO_SKADI.invoke({
            "pergunta_original": mensagem,
            "historico": historico,
            "usuario_id": usuario_id,
            "rota": "orquestrador",
            "resposta": "",
            "respostas_agentes": [],
            "agentes_chamados": [],
        })
    finally:
        if token_contexto is not None:
            restaurar_usuario_contexto(token_contexto)

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
