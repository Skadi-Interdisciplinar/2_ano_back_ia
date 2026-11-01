"""Métricas persistidas, agregadas e sem conteúdo de conversas para o mobile."""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from app import config
from app.erros import ServicoIndisponivel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

PRECOS_POR_MILHAO = {
    "gemini-2.5-flash": (0.30, 2.50),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
}
LIMITE_TURNOS = 200

_lock = threading.Lock()
_turno_local: ContextVar[str | None] = ContextVar("turno_observabilidade", default=None)
_abertos: dict[str, float] = {}
_chamadas: list[dict[str, Any]] = []
_etapas: list[dict[str, Any]] = []


def _turno_atual() -> str | None:
    return _turno_local.get()


def _nome_modelo(valor: Any) -> str:
    nome = str(valor or "desconhecido")
    return nome.removeprefix("models/")


def _tokens(mensagem: Any) -> tuple[int, int]:
    uso = getattr(mensagem, "usage_metadata", None) or {}
    if not isinstance(uso, dict):
        uso = {}
    entrada = int(uso.get("input_tokens") or uso.get("prompt_tokens") or 0)
    saida = int(uso.get("output_tokens") or uso.get("completion_tokens") or 0)
    if entrada or saida:
        return entrada, saida
    metadados = getattr(mensagem, "response_metadata", None) or {}
    bruto = metadados.get("token_usage") or metadados.get("usage") or {}
    return (
        int(bruto.get("prompt_tokens") or bruto.get("input_tokens") or 0),
        int(bruto.get("completion_tokens") or bruto.get("output_tokens") or 0),
    )


def estimar_custo(modelo: str, entrada: int, saida: int) -> float | None:
    """Preço ausente não significa gratuidade."""
    precos = PRECOS_POR_MILHAO.get(_nome_modelo(modelo))
    if precos is None:
        return None
    return (entrada * precos[0] + saida * precos[1]) / 1_000_000


class ColetorChamadas(BaseCallbackHandler):
    """Registra metadados de LLM sem armazenar prompts, respostas, token ou usuário."""

    raise_error = False

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        turno_id = _turno_atual()
        if turno_id is None:
            return
        parametros = kwargs.get("invocation_params") or {}
        modelo = parametros.get("model") or parametros.get("model_name")
        if not modelo and isinstance(serialized, dict):
            modelo = (serialized.get("kwargs") or {}).get("model")
        with _lock:
            self._runs[str(run_id)] = {
                "turno_id": turno_id,
                "inicio": time.perf_counter(),
                "modelo": _nome_modelo(modelo),
            }

    def on_llm_end(self, response: LLMResult, *, run_id, **kwargs) -> None:
        with _lock:
            abertura = self._runs.pop(str(run_id), None)
        if abertura is None:
            return
        try:
            mensagem = response.generations[0][0].message
        except (AttributeError, IndexError):
            mensagem = None
        entrada, saida = _tokens(mensagem)
        metadados = getattr(mensagem, "response_metadata", None) or {}
        modelo = _nome_modelo(metadados.get("model_name") or metadados.get("model") or abertura["modelo"])
        registro = {
            "turno_id": abertura["turno_id"],
            "modelo": modelo,
            "tokens_entrada": entrada,
            "tokens_saida": saida,
            "custo_usd": estimar_custo(modelo, entrada, saida),
            "latencia_ms": round((time.perf_counter() - abertura["inicio"]) * 1_000),
        }
        with _lock:
            _chamadas.append(registro)

    def on_llm_error(self, error: BaseException, *, run_id, **kwargs) -> None:
        with _lock:
            self._runs.pop(str(run_id), None)


coletor = ColetorChamadas()


@lru_cache(maxsize=1)
def _colecao_turnos():
    """Coleção exclusiva de telemetria, sem mensagens, tokens ou credenciais."""

    from app.memory import obter_banco_mongo

    colecao = obter_banco_mongo().observabilidade_trimmy
    colecao.create_index("data_hora")
    return colecao


def _persistir_turno(turno: dict[str, Any]) -> None:
    """Falha de telemetria não pode impedir a resposta do usuário."""

    from pymongo.errors import PyMongoError

    try:
        _colecao_turnos().insert_one(turno)
    except (PyMongoError, ServicoIndisponivel):
        logger.warning("Observabilidade: persistência do turno indisponível")


def _carregar_turnos() -> list[dict[str, Any]]:
    """Lê os últimos turnos persistidos para manter métricas após reinicialização."""

    from pymongo.errors import PyMongoError

    try:
        return list(_colecao_turnos().find({}).sort("data_hora", -1).limit(LIMITE_TURNOS))
    except (PyMongoError, ServicoIndisponivel) as erro:
        raise ServicoIndisponivel("Observabilidade temporariamente indisponível.") from erro


def abrir_turno() -> str:
    turno_id = uuid.uuid4().hex
    _turno_local.set(turno_id)
    with _lock:
        _abertos[turno_id] = time.perf_counter()
    return turno_id


@contextmanager
def medir_etapa(nome: str) -> Iterator[None]:
    """Mede um nó do grafo somente quando há turno ativo."""
    turno_id = _turno_atual()
    inicio = time.perf_counter()
    try:
        yield
    finally:
        if turno_id is not None:
            with _lock:
                _etapas.append({
                    "turno_id": turno_id,
                    "agente": nome,
                    "latencia_ms": round((time.perf_counter() - inicio) * 1_000),
                })


def fechar_turno(*, turno_id: str, rota: str, status: str) -> None:
    _turno_local.set(None)
    with _lock:
        inicio = _abertos.pop(turno_id, None)
        if inicio is None:
            return
        chamadas = [item for item in _chamadas if item["turno_id"] == turno_id]
        etapas = [item for item in _etapas if item["turno_id"] == turno_id]
        turno = {
            "id": turno_id,
            "data_hora": datetime.now(UTC),
            "rota": rota or "orquestrador",
            "status": status,
            "latencia_total_ms": round((time.perf_counter() - inicio) * 1_000),
            "tokens_entrada": sum(item["tokens_entrada"] for item in chamadas),
            "tokens_saida": sum(item["tokens_saida"] for item in chamadas),
            "custo_usd": (sum(item["custo_usd"] for item in chamadas)
                          if all(item["custo_usd"] is not None for item in chamadas) else None),
            "chamadas": chamadas,
            "etapas": etapas,
        }
        _chamadas[:] = [item for item in _chamadas if item["turno_id"] != turno_id]
        _etapas[:] = [item for item in _etapas if item["turno_id"] != turno_id]
    _persistir_turno(turno)


def _media(valores: list[float]) -> float | None:
    return round(sum(valores) / len(valores), 2) if valores else None


def _p95(valores: list[int]) -> int | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[max(0, (95 * len(ordenados) + 99) // 100 - 1)]


def painel_mobile() -> dict[str, Any]:
    """Métricas técnicas e cenário financeiro acadêmico para o mobile."""

    turnos = list(reversed(_carregar_turnos()))
    chamadas = [chamada for turno in turnos for chamada in turno.get("chamadas", [])]
    etapas = [etapa for turno in turnos for etapa in turno.get("etapas", [])]

    latencias = [item["latencia_total_ms"] for item in turnos]
    sem_preco = sorted({item.get("modelo", "desconhecido") for item in chamadas
                       if item.get("custo_usd") is None or _nome_modelo(item.get("modelo")) not in PRECOS_POR_MILHAO})
    custo_completo = not sem_preco and all(item.get("custo_usd") is not None for item in turnos)
    custo_total = sum(item.get("custo_usd") or 0 for item in turnos)
    total_turnos = len(turnos)
    erros = sum(item["status"] == "erro" for item in turnos)
    resolucoes = sum(item["status"] == "ok" for item in turnos)
    custo_medio = (custo_total / total_turnos) if total_turnos and custo_completo else None
    por_agente: dict[str, list[int]] = {}
    for etapa in etapas:
        por_agente.setdefault(etapa["agente"], []).append(etapa["latencia_ms"])
    roi = None
    motivo_roi = "Configure tempo manual evitado em minutos e custo por hora em USD para estimar o benefício."
    beneficio = None
    minutos = custo_hora = None
    try:
        minutos = float(config.ROI_TEMPO_MANUAL_MINUTOS)
        custo_hora = float(config.ROI_CUSTO_HORA_USD)
        if not all(math.isfinite(v) and v >= 0 for v in (minutos, custo_hora)):
            raise ValueError
        beneficio = resolucoes * minutos / 60 * custo_hora
        if not custo_completo:
            motivo_roi = "Estimativa incompleta: há chamadas sem preço conhecido. Não é possível calcular ROI."
        elif not total_turnos:
            motivo_roi = "Sem turnos registrados para calcular ROI."
        elif custo_total > 0:
            roi = round((beneficio - custo_total) / custo_total * 100, 2)
            motivo_roi = ("Estimativa: benefício = resoluções técnicas × minutos manuais evitados / 60 × custo/hora USD; "
                          "ROI = (benefício - custo estimado dos modelos) / custo estimado dos modelos × 100. "
                          "As premissas configuradas não comprovam economia real.")
        else:
            motivo_roi = "Sem custo estimado positivo, não é possível calcular o percentual de ROI."
    except (TypeError, ValueError):
        minutos = custo_hora = None

    def cenario(usuarios: int) -> dict[str, Any]:
        return {
            "usuarios_semanais": usuarios,
            "interacoes_por_usuario": 1,
            "premissa": "Uma interação por usuário na semana; custo médio da amostra × usuários. Não é cobrança real.",
            "custo_estimado_usd": round(custo_medio * usuarios, 6) if custo_medio is not None else None,
            "motivo": ("Estimativa baseada nos turnos da amostra." if custo_medio is not None else
                       "Sem turnos ou com preços desconhecidos; projeção indisponível."),
        }

    return {
        "escopo": "Últimos 200 turnos persistidos; não inclui conteúdo de conversas.",
        "resumo": {
            "turnos": total_turnos,
            "erros": erros,
            "resolucoes_tecnicas": resolucoes,
            "indice_erros": round(erros / total_turnos, 4) if total_turnos else None,
            "latencia_media_ms": _media(latencias),
            "latencia_p95_ms": _p95(latencias),
            "tokens_entrada": sum(item["tokens_entrada"] for item in chamadas),
            "tokens_saida": sum(item["tokens_saida"] for item in chamadas),
            "custo_estimado_usd": round(custo_total, 6) if custo_completo else None,
            "custo_parcial_conhecido_usd": round(sum(c.get("custo_usd") or 0 for c in chamadas), 6),
            "estimativa_custo_completa": custo_completo,
            "modelos_sem_preco": sem_preco,
            "custo_medio_por_turno_usd": round(custo_medio, 6) if custo_medio is not None else None,
        },
        "latencia_interagentes": [
            {"agente": nome, "latencia_media_ms": _media(valores), "chamadas": len(valores)}
            for nome, valores in sorted(por_agente.items())
        ],
        "projecoes_semanais": [cenario(100), cenario(1_000)],
        "custo_por_resolucao": {
            "valor_usd": round(custo_total / resolucoes, 6) if resolucoes and custo_completo else None,
            "motivo": ("Estimativa incompleta: há chamadas sem preço conhecido." if not custo_completo else
                       "Sem resoluções técnicas aprovadas." if not resolucoes else
                       "Custo de todos os turnos / interações concluídas e aprovadas pelo juiz; não é resolução de alertas."),
        },
        "roi": {
            "valor_percentual": roi,
            "motivo": motivo_roi,
            "beneficio_estimado_usd": round(beneficio, 6) if beneficio is not None else None,
        },
        "premissas": {
            "tipo": "Cenário acadêmico ilustrativo, sem comprovação de economia real.",
            "tempo_manual_evitado_minutos": minutos,
            "custo_hora_usd": custo_hora,
            "interacoes_por_usuario_semana": 1,
            "turnos_na_amostra": total_turnos,
        },
        "turnos_recentes": [
            {chave: valor for chave, valor in turno.items() if chave not in {"_id", "id", "chamadas", "etapas"}}
            for turno in turnos[-50:]
        ],
    }
