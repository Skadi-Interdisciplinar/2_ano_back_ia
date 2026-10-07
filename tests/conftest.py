"""LLM falso para exercitar o agente sem chamar provedores externos."""

from types import SimpleNamespace


class ModeloFalso:
    def __init__(self, conteudo="ok"):
        self.conteudo = conteudo
        self.mensagens = None

    def invoke(self, mensagens):
        self.mensagens = mensagens
        return SimpleNamespace(content=self.conteudo)
