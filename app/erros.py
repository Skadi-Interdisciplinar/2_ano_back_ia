"""Erros públicos distinguem indisponibilidade de informações ausentes."""


class ServicoIndisponivel(RuntimeError):
    """Falha de infraestrutura, configuração ou provedor."""


class SaidaModeloInvalida(Exception):
    """Resposta do modelo não atende ao contrato validado."""
