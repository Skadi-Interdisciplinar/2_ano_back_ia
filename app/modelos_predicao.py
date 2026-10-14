"""AR(1) por câmara: ajuste OLS, avaliação temporal e artefatos JSON locais."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.erros import ServicoIndisponivel
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

PASTA_MODELOS = Path(__file__).resolve().parent.parent / "modelos_predicao"
FUSO_LEITURAS = ZoneInfo("America/Sao_Paulo")  # Convenção efetiva do worker existente.


def momento(valor: str | datetime) -> datetime:
    data = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    if not isinstance(data, datetime):
        raise TypeError("Horário ausente ou inválido.")
    if data.tzinfo is None:
        data = data.replace(tzinfo=FUSO_LEITURAS)
    return data.astimezone(UTC)


class MetricasHorizonte(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    horizonte_minutos: int = Field(gt=0, strict=True)
    casos: int = Field(gt=0, strict=True)
    mae: float = Field(ge=0)
    rmse: float = Field(ge=0)
    mae_referencia: float = Field(ge=0)
    rmse_referencia: float = Field(ge=0)


class ModeloPredicao(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    formato: Literal["AR1-v1"] = "AR1-v1"
    modelo_id: UUID = Field(default_factory=uuid4)
    status: Literal["EM_REVISAO", "APROVADO"] = "EM_REVISAO"
    camara_id: int = Field(gt=0, strict=True)
    termometro_id: int = Field(gt=0, strict=True)
    cadencia_segundos: int = Field(gt=0, strict=True)
    inicio_coleta: datetime
    inicio_treino: datetime
    fim_treino: datetime
    inicio_avaliacao: datetime
    fim_avaliacao: datetime
    leituras_treino: int = Field(ge=3, strict=True)
    leituras_avaliacao: int = Field(ge=1, strict=True)
    intercepto: float
    coeficiente: float
    metricas: list[MetricasHorizonte] = Field(min_length=1)
    aprovado_em: datetime | None = None
    lote_simulacao: UUID | None = None

    @model_validator(mode="after")
    def conferir_perfil(self):
        datas = (self.inicio_coleta, self.inicio_treino, self.fim_treino,
                 self.inicio_avaliacao, self.fim_avaliacao)
        if any(d.tzinfo is None for d in datas):
            raise ValueError("Artefato exige horários com fuso.")
        if not (self.inicio_coleta <= self.inicio_treino <= self.fim_treino
                < self.inicio_avaliacao <= self.fim_avaliacao):
            raise ValueError("Períodos de coleta, treino e avaliação inconsistentes.")
        horizontes = [m.horizonte_minutos for m in self.metricas]
        if len(set(horizontes)) != len(horizontes) or any(
            h * 60 % self.cadencia_segundos
            or h * 60 // self.cadencia_segundos > self.leituras_avaliacao
            for h in horizontes
        ):
            raise ValueError("Horizontes duplicados ou incompatíveis com a cadência.")
        if (self.fim_treino - self.inicio_treino).total_seconds() != (self.leituras_treino - 1) * self.cadencia_segundos:
            raise ValueError("Período de treinamento incompatível com a cadência.")
        if (self.fim_avaliacao - self.inicio_avaliacao).total_seconds() != (self.leituras_avaliacao - 1) * self.cadencia_segundos:
            raise ValueError("Período de avaliação incompatível com a cadência.")
        if (self.inicio_avaliacao - self.fim_treino).total_seconds() != self.cadencia_segundos:
            raise ValueError("Lacuna entre treino e avaliação.")
        if any(m.casos != self.leituras_avaliacao - m.horizonte_minutos * 60 // self.cadencia_segundos + 1
               for m in self.metricas):
            raise ValueError("Número de casos não corresponde à avaliação temporal.")
        if self.status == "APROVADO" and self.aprovado_em is None:
            raise ValueError("Modelo sem registro de aprovação administrativa.")
        if self.aprovado_em is not None and self.aprovado_em.tzinfo is None:
            raise ValueError("Horário de aprovação sem fuso.")
        return self


def preparar_serie(linhas: list[tuple], cadencia: int, inicio_coleta: datetime) -> list[tuple[datetime, float]]:
    """Ordena e deduplica repetições idênticas; não interpola nem preenche lacunas."""
    if type(cadencia) is not int or cadencia <= 0:
        raise ValueError("Cadência deve ser positiva.")
    pontos: dict[datetime, float] = {}
    for temperatura, data, *_ in linhas:
        if isinstance(temperatura, bool):
            raise TypeError("Booleano não é uma medição de temperatura.")
        valor, horario = float(temperatura), momento(data)
        if not math.isfinite(valor) or horario < momento(inicio_coleta):
            raise ValueError("Leitura inválida ou anterior à coleta contínua.")
        if horario in pontos and pontos[horario] != valor:
            raise ValueError("Leituras conflitantes no mesmo horário.")
        pontos[horario] = valor
    serie = sorted(pontos.items())
    if any(b[0] - a[0] != timedelta(seconds=cadencia) for a, b in pairwise(serie)):
        raise ValueError("Há lacunas ou cadência irregular na série.")
    return serie


def estimar(intercepto: float, coeficiente: float, temperatura: float, passos: int) -> float:
    if passos <= 0 or not all(math.isfinite(v) for v in (intercepto, coeficiente, temperatura)):
        raise ValueError("Parâmetros de projeção inválidos.")
    valor = temperatura
    for _ in range(passos):
        valor = intercepto + coeficiente * valor
        if not math.isfinite(valor):
            raise ValueError("A projeção produziu um valor não finito.")
    return valor


def treinar_modelo(linhas: list[tuple], *, camara_id: int, termometro_id: int,
                   cadencia_segundos: int, inicio_coleta: datetime,
                   horizontes_minutos: list[int]) -> ModeloPredicao:
    serie = preparar_serie(linhas, cadencia_segundos, inicio_coleta)
    corte = len(serie) * 80 // 100
    if corte < 3 or corte >= len(serie) or not horizontes_minutos:
        raise ValueError("Dados insuficientes para ajuste AR(1) e avaliação temporal.")
    if len(set(horizontes_minutos)) != len(horizontes_minutos):
        raise ValueError("Horizontes repetidos.")
    x = [p[1] for p in serie[:corte - 1]]
    y = [p[1] for p in serie[1:corte]]
    media_x, media_y = sum(x) / len(x), sum(y) / len(y)
    variancia = sum((v - media_x) ** 2 for v in x)
    # OLS com intercepto; em uma série constante, a previsão ajustada é a média.
    coeficiente = sum((a - media_x) * (b - media_y) for a, b in zip(x, y)) / variancia if variancia else 0.0
    intercepto = media_y - coeficiente * media_x
    if not all(math.isfinite(v) for v in (coeficiente, intercepto)):
        raise ValueError("Coeficientes não finitos.")
    metricas = []
    for horizonte in horizontes_minutos:
        if type(horizonte) is not int or horizonte <= 0 or horizonte * 60 % cadencia_segundos:
            raise ValueError("Horizonte deve ser positivo e múltiplo da cadência.")
        passos = horizonte * 60 // cadencia_segundos
        # Só alvos do bloco posterior; cada origem usa apenas a leitura já observada.
        alvos = list(range(corte - 1 + passos, len(serie)))
        if not alvos:
            raise ValueError("Não há casos observados para avaliar todos os horizontes.")
        erros, referencia = [], []
        for alvo in alvos:
            origem = serie[alvo - passos][1]
            previsto = estimar(intercepto, coeficiente, origem, passos)
            erros.append(previsto - serie[alvo][1])
            referencia.append(origem - serie[alvo][1])
        metricas.append(MetricasHorizonte(
            horizonte_minutos=horizonte, casos=len(alvos),
            mae=sum(abs(e) for e in erros) / len(erros),
            rmse=math.sqrt(sum(e ** 2 for e in erros) / len(erros)),
            mae_referencia=sum(abs(e) for e in referencia) / len(referencia),
            rmse_referencia=math.sqrt(sum(e ** 2 for e in referencia) / len(referencia)),
        ))
    return ModeloPredicao(
        camara_id=camara_id, termometro_id=termometro_id, cadencia_segundos=cadencia_segundos,
        inicio_coleta=momento(inicio_coleta), inicio_treino=serie[0][0], fim_treino=serie[corte - 1][0],
        inicio_avaliacao=serie[corte][0], fim_avaliacao=serie[-1][0],
        leituras_treino=corte, leituras_avaliacao=len(serie) - corte,
        intercepto=intercepto, coeficiente=coeficiente, metricas=metricas,
    )


def carregar_modelo(camara_id: int, *, pendente: bool = False) -> ModeloPredicao | None:
    sufixo = ".pendente" if pendente else ""
    caminho = PASTA_MODELOS / f"camara_{camara_id}{sufixo}.json"
    try:
        modelo = ModeloPredicao.model_validate_json(caminho.read_text(encoding="utf-8"))
        if modelo.camara_id != camara_id:
            raise ValueError("Artefato de outra câmara.")
        return modelo
    except FileNotFoundError:
        return None
    except (OSError, ValueError, ValidationError) as erro:
        raise ServicoIndisponivel("Artefato de predição inválido ou inacessível.") from erro


def salvar_modelo(modelo: ModeloPredicao) -> None:
    """Uso administrativo: substituição atômica, sem cache de aprovação."""
    PASTA_MODELOS.mkdir(parents=True, exist_ok=True)
    sufixo = ".pendente" if modelo.status == "EM_REVISAO" else ""
    caminho = PASTA_MODELOS / f"camara_{modelo.camara_id}{sufixo}.json"
    temporario = caminho.with_suffix(f".{uuid4()}.tmp")
    try:
        temporario.write_text(modelo.model_dump_json(indent=2), encoding="utf-8")
        temporario.replace(caminho)
    finally:
        temporario.unlink(missing_ok=True)
