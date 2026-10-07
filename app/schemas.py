from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from datetime import datetime

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


class errorResponse(BaseModel):
    status_code: int
    message: str
    now: datetime

