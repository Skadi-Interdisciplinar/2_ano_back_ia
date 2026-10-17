from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DecisaoRota(BaseModel):
    """Saída interna do roteador; não representa uma autorização de acesso."""

    model_config = ConfigDict(extra="forbid")
    rota: Literal["monitoramento", "diagnostico", "faq", "orquestrador"]


class RelatorioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    token: str = Field(min_length=1, max_length=10_000, repr=False)
    cd_id: int | None = Field(default=None, gt=0, strict=True)
    camara_id: int | None = Field(default=None, gt=0, strict=True)
    data_inicial: date
    data_final: date

    @field_validator("data_inicial", "data_final", mode="before")
    @classmethod
    def data_iso(cls, valor):
        if type(valor) is date or (isinstance(valor, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor)):
            return valor
        raise ValueError("Informe uma data no formato YYYY-MM-DD.")

    @model_validator(mode="after")
    def periodo_valido(self):
        if self.data_inicial > self.data_final or self.data_final == date.max:
            raise ValueError("Período inválido ou sem limite final representável.")
        return self


class ChatRequest(BaseModel):
    """Mensagem recebida pelo endpoint de chat.

    O token sera validado pela autenticacao do aplicativo quando ela estiver
    integrada. Durante o bypass temporario, ele e recebido e nao interpretado.
    """

    token: str = Field(min_length=1, max_length=10_000)
    mensagem: str = Field(min_length=1, max_length=10_000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("token", "mensagem")
    @classmethod
    def texto_obrigatorio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O campo nao pode ser vazio.")
        return valor


class ChatResponse(BaseModel):
    resposta: str
    agentes_chamados: list[str] = Field(default_factory=list)

    @field_validator("resposta")
    @classmethod
    def texto_sem_formatacao(cls, valor: str) -> str:
        """Apresenta texto simples sem alterar números, fontes ou ressalvas."""
        valor = re.sub(r"(?<!\w)\*\*(\S(?:[^*\n]*[^\s*])?)\*\*(?!\w)", r"\1", valor)
        # Marcadores junto ao texto; asteriscos separados por espaços podem ser multiplicação.
        valor = re.sub(r"(?<!\w)\*([^\W\d_](?:[^*\n]*[^\s*])?)\*(?!\w)", r"\1", valor)
        return " ".join(valor.split())


class EncerrarChatRequest(BaseModel):
    token: str = Field(min_length=1, max_length=10_000)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EncerrarChatResponse(BaseModel):
    resumo: str | None = None
