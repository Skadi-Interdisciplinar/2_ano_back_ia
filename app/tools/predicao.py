"""Uma única tool de predição; autorização e cálculo permanecem no backend."""

from copy import deepcopy
from datetime import timedelta
from math import isfinite
from uuid import uuid4

from app.modelos_predicao import carregar_modelo, estimar, preparar_serie
from app.predicao import (
    ResultadoPredicao,
    consultar_serie,
    contexto_predicao,
    validar_acesso_predicao,
)
from app.tools.monitoramento import (
    FiltrosCamaraArgs,
    _cadastro_publico,
    consultar_camaras_permitidas,
)
from langchain.tools import tool
from pydantic import Field


class PreverTemperaturaArgs(FiltrosCamaraArgs):
    horizonte_minutos: int | None = Field(default=None, gt=0, strict=True, description="Prazo em minutos informado pelo usuário; nunca inventar um padrão.")


@tool("prever_temperatura", args_schema=PreverTemperaturaArgs, return_direct=True)
def prever_temperatura(camara_id: int | None = None, modelo: str | None = None,
                      localizacao: str | None = None, horizonte_minutos: int | None = None) -> dict:
    """Estima temperatura para uma câmara permitida usando somente modelo aprovado."""
    usuario = validar_acesso_predicao()
    contexto = contexto_predicao.get()
    if contexto is None or contexto.usuario_id != usuario:
        raise PermissionError("Predição exige contexto interno da execução.")
    resultado = ResultadoPredicao(status="esclarecimento", mensagem="Qual câmara deseja analisar? Informe modelo ou localização.")
    if any(v is not None for v in (camara_id, modelo, localizacao)):
        camaras = consultar_camaras_permitidas(usuario, camara_id, modelo, localizacao)
        if not camaras:
            resultado.mensagem = "Não encontrei a câmara no seu escopo permitido."
        elif len(camaras) > 1:
            opcoes = "; ".join(f"{c['modelo']} — {c['localizacao']}" for c in camaras)
            resultado.mensagem = f"Há mais de uma câmara correspondente: {opcoes}. Qual deseja analisar?"
        elif horizonte_minutos is None:
            resultado.mensagem = "Daqui a quantos minutos deseja estimar a temperatura?"
        else:
            camara = camaras[0]
            artefato = carregar_modelo(camara["camara_id"])
            resultado = ResultadoPredicao(status="indisponivel", mensagem="Ainda não há modelo aprovado para essa câmara. É necessário coletar histórico contínuo, avaliar o modelo e aprová-lo.")
            if artefato is not None and artefato.status == "APROVADO":
                if artefato.termometro_id != camara["termometro"]:
                    resultado.mensagem = "O modelo não corresponde ao termômetro cadastrado. É necessária nova avaliação."
                elif (horizonte_minutos * 60 % artefato.cadencia_segundos or
                      horizonte_minutos not in {m.horizonte_minutos for m in artefato.metricas}):
                    horizontes = ", ".join(str(m.horizonte_minutos) for m in artefato.metricas)
                    resultado = ResultadoPredicao(status="esclarecimento", mensagem=f"Esse horizonte não foi avaliado ou não corresponde à cadência. Horizontes avaliados, em minutos: {horizontes}. Qual deseja usar?")
                else:
                    try:
                        linhas = consultar_serie(camara, artefato.inicio_coleta, ultimas=True)
                        serie = preparar_serie(linhas, artefato.cadencia_segundos, artefato.inicio_coleta)
                        if len(serie) < 2:
                            raise ValueError("Leituras insuficientes para conferir a cadência.")
                        horario, temperatura = serie[-1]
                        if horario < artefato.fim_treino:
                            raise ValueError("Leitura anterior ao ajuste do modelo.")
                        previsto = estimar(artefato.intercepto, artefato.coeficiente, temperatura,
                                           horizonte_minutos * 60 // artefato.cadencia_segundos)
                        minimo, maximo = float(camara["limite_minimo"]), float(camara["limite_maximo"])
                        if not all(isfinite(v) for v in (minimo, maximo)) or minimo > maximo:
                            raise ValueError("Limites inválidos.")
                    except (ValueError, TypeError, OverflowError):
                        resultado = ResultadoPredicao(status="dados_invalidos", mensagem="As leituras ou os limites estão ausentes, inválidos ou com lacunas. Não consigo produzir uma estimativa fundamentada.")
                    else:
                        resultado = ResultadoPredicao(
                            status="ok", camara=_cadastro_publico(camara), temperatura_base=temperatura,
                            temperatura_prevista=previsto, horario_base=horario,
                            horario_previsto=horario + timedelta(minutes=horizonte_minutos),
                            horizonte_minutos=horizonte_minutos, versao_modelo=str(artefato.modelo_id),
                            dados_simulados=artefato.lote_simulacao is not None,
                            comparacao="abaixo_minimo" if previsto < minimo else "acima_maximo" if previsto > maximo else "dentro_faixa",
                        )
    referencia = str(uuid4())
    contexto.resultados[referencia] = resultado.model_copy(deep=True)
    return {"referencia": referencia, **deepcopy(resultado.model_dump(mode="json"))}


TOOLS = [prever_temperatura]
