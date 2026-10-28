"""Guardrails determinísticos: defesa adicional, não autenticação nem prova de veracidade."""

from __future__ import annotations

import re
import unicodedata

from app import config
from app.erros import SaidaModeloInvalida
from app.faq import BASE_FAQ
from app.schemas import ChatResponse

_EMAIL = re.compile(r"\b[A-Z0-9_.+-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+\b", re.IGNORECASE)
# Contatos explicitamente publicados na FAQ aprovada não são dados privados.
_EMAILS_PUBLICOS = frozenset(email.casefold() for email in _EMAIL.findall(BASE_FAQ))
_DADOS_PESSOAIS = (
    (re.compile(r"(?<!\w)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\w)"), "[CNPJ OMITIDO]"),
    (re.compile(r"(?<!\w)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\w)"), "[CPF OMITIDO]"),
    (re.compile(r"\bCPF\s*[:=]?\s*\d{11}\b", re.IGNORECASE), "[CPF OMITIDO]"),
    (re.compile(r"\bCNPJ\s*[:=]?\s*\d{14}\b", re.IGNORECASE), "[CNPJ OMITIDO]"),
    (re.compile(r"(?<!\w)(?:\+55\s*)?(?:\(\d{2}\)\s*|\d{2}[ -])\d{4,5}-?\d{4}(?!\w)"), "[TELEFONE OMITIDO]"),
    (re.compile(r"\b(?:telefone|celular)\s*[:=]?\s*(?:\+55)?\d{10,11}\b", re.IGNORECASE), "[TELEFONE OMITIDO]"),
)
_SEGREDOS = re.compile(
    r"\b(?:postgres(?:ql)?|mongodb(?:\+srv)?|rediss?|https?)://[^\s/:@]+:[^\s@]+@[^\s<>\"']+"
    r"|\b(?:[A-Z_]*(?:API_KEY|DATABASE_URL|MONGODB_URI|REDIS_URL)|senha|password|token)\b[\"']?\s*[:=]\s*[\"']?[^\s\"']+"
    r"|\bAuthorization\s*:\s*Bearer\s+\S+"
    r"|\b(?:gsk_|sk-)[A-Za-z0-9_-]{16,}\b"
    r"|\bAIza[A-Za-z0-9_-]{20,}\b"
    r"|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
    re.IGNORECASE,
)
_INJECAO = re.compile(
    r"(?<!nao )(?<!not )(?<!don't )(?:\b(?:ignore|desconsidere|esqueca|substitua)\s+(?:(?:as?|todas?|suas?|essas?|anteriores|de|do|sistema)\s+)*"
    r"(?:instrucoes|regras|restricoes|permissoes)\b"
    r"|\b(?:ignore|forget|override)\s+(?:(?:all|the|your|previous|system)\s+)*(?:instructions|rules)\b"
    r"|\b(?:finja|atue)\s+(?:ser|como)\s+(?:um\s+)?(?:super[_ ]?admin|administrador|sistema)\b)"
    r"|<\s*/?\s*(?:system|developer)\s*>|\[/?INST\]",
    re.IGNORECASE,
)
_PEDIDO_INTERNO = re.compile(
    r"(?<!nao )(?<!not )(?<!don't )\b(?:mostre|revele|exiba|imprima|envie|forneca|retorne|show|reveal|print)\b[^.!?\n]{0,80}"
    r"\b(?:system prompt|prompt (?:do |de )?sistema|instrucoes (?:internas|do sistema)|"
    r"variaveis de ambiente|arquivo \.env|chaves? (?:de )?api|credenciais(?: internas)?)\b",
    re.IGNORECASE,
)
_DADO_NAO_VERIFICADO = re.compile(
    r"\b(?:invente|improvise|complete)\b[^.!?\n]{0,100}\b(?:valor|leitura|temperatura|dado|informacao|informa[cç][aã]o|justificativa|resposta)\b"
    r"|\b(?:sem consultar|sem verificar|sem checar)\b[^.!?\n]{0,100}\b(?:sensor(?:es)?|leitura(?:s)?|dados?|alerta(?:s)?|banco)\b[^.!?\n]{0,100}\b(?:diga|afirme|informe|declare|apresente|confirme|garanta)\b"
    r"|\b(?:mesmo que nao tenha essa informacao|mesmo que nao tenha a informacao|se nao encontrar)\b[^.!?\n]{0,100}\b(?:complete|invente|improvise|estime)\b",
    re.IGNORECASE,
)


def _segredos_configurados() -> tuple[str, ...]:
    return tuple(valor for valor in (
        config.GEMINI_API_KEY, config.GROQ_API_KEY, config.QDRANT_API_KEY,
        config.DATABASE_URL, config.MONGODB_URI, config.REDIS_URL,
    ) if isinstance(valor, str) and valor)


def anonimizar_texto(texto: str) -> str:
    """Mascara padrões reconhecidos; não guarda mapa reversível nem adivinha nomes/IDs."""
    for segredo in _segredos_configurados():
        texto = texto.replace(segredo, "[SEGREDO OMITIDO]")
    texto = _SEGREDOS.sub("[SEGREDO OMITIDO]", texto)
    for padrao, substituto in _DADOS_PESSOAIS:
        texto = padrao.sub(substituto, texto)
    return _EMAIL.sub(
        lambda m: m.group() if m.group().casefold() in _EMAILS_PUBLICOS else "[EMAIL OMITIDO]",
        texto,
    )


def guardrail_entrada(mensagem: str) -> dict:
    """Checa o texto antes de mascará-lo; limites HTTP continuam no ChatRequest."""
    if not isinstance(mensagem, str) or not mensagem.strip():
        return {"bloqueado": True, "texto": "", "mensagem": "Informe uma mensagem para consultar a Trimmy."}
    normalizado = "".join(
        c for c in unicodedata.normalize("NFKD", mensagem.casefold())
        if not unicodedata.combining(c) and unicodedata.category(c) != "Cf"
    )
    bloqueado = bool(
        _INJECAO.search(normalizado) or _PEDIDO_INTERNO.search(normalizado)
        or _DADO_NAO_VERIFICADO.search(normalizado)
        or _SEGREDOS.search(mensagem)
        or any(segredo in mensagem for segredo in _segredos_configurados())
    )
    return {
        "bloqueado": bloqueado,
        "texto": anonimizar_texto(mensagem),
        "mensagem": (
            "Não posso processar pedidos que tentem substituir as instruções, contornar "
            "permissões, expor informações internas ou apresentar dados não verificados como reais. "
            "Faça sua pergunta sobre o Skadi sem incluir segredos."
            if bloqueado else ""
        ),
    }


def guardrail_saida(resposta: str, instrucoes_internas: tuple[str, ...] = ()) -> str:
    """Não reescreve fatos/regras: rejeita segredos e só mascara dados pessoais reconhecidos."""
    if not isinstance(resposta, str) or not resposta.strip():
        raise SaidaModeloInvalida("Resposta final vazia ou inválida.")
    # Verifica o mesmo texto simples que o HTTP entregará e a memória salvará.
    resposta = ChatResponse(resposta=resposta).resposta
    if (_SEGREDOS.search(resposta)
            or any(segredo in resposta for segredo in _segredos_configurados())
            or any(texto.strip() and texto.strip() in resposta for texto in instrucoes_internas)
            or re.search(r"###\s*(?:PERSONA|PAPEL\s*:)|<\s*(?:system|developer)\s*>", resposta, re.IGNORECASE)):
        raise SaidaModeloInvalida("Resposta final contém conteúdo interno não publicável.")
    return anonimizar_texto(resposta)
