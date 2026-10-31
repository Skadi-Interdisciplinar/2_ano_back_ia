"""Respostas da FAQ vêm da base aprovada, nunca de texto livre do modelo."""

import re
from pathlib import Path

from app.erros import SaidaModeloInvalida
from pydantic import BaseModel, ConfigDict, Field, StrictBool

BASE_FAQ = Path(__file__).with_name("base_faq.md").read_text(encoding="utf-8")
RESPOSTAS_FAQ = {
    identificador: " ".join(resposta.strip().split())
    for identificador, resposta in re.findall(
        r"^### (FAQ-\d{3}) - [^\n]+\n(.*?)(?=^## |^### |\Z)",
        BASE_FAQ, re.MULTILINE | re.DOTALL,
    )
}


class SelecaoFAQ(BaseModel):
    model_config = ConfigDict(extra="forbid")
    referencias: list[str] = Field(default_factory=list, description="Somente IDs FAQ-xxx da base oficial que respondem à pergunta.")
    informacao_ausente: StrictBool = Field(default=False, description="True se qualquer detalhe solicitado não estiver documentado na base.")


def apresentar_faq(selecao: SelecaoFAQ) -> str:
    if any(ref not in RESPOSTAS_FAQ for ref in selecao.referencias):
        raise SaidaModeloInvalida("Referência de FAQ não aprovada.")
    respostas = [RESPOSTAS_FAQ[ref] for ref in dict.fromkeys(selecao.referencias)]
    if not respostas or selecao.informacao_ausente:
        respostas.append("Não tenho informação aprovada sobre os detalhes que não constam nessas orientações.")
    return " ".join(respostas)
