from __future__ import annotations

from app import memory


class ColecaoFalsa:
    def __init__(self, documento=None):
        self.documento = documento
        self.atualizacoes = []
        self.inseridos = []

    def find_one(self, _filtro):
        return self.documento

    def update_one(self, filtro, atualizacao, upsert=False):
        self.atualizacoes.append((filtro, atualizacao, upsert))

    def insert_one(self, documento):
        self.inseridos.append(documento)


class BancoFalso:
    def __init__(self, conversas=None):
        self.conversas = conversas or ColecaoFalsa()
        self.execucoes_agentes = ColecaoFalsa()


def test_salvar_mensagem_cria_documento_de_conversa(monkeypatch):
    banco = BancoFalso()
    monkeypatch.setattr(memory, "_database", lambda: banco)

    memory.salvar_mensagem_conversa(2, "usuario", "oi", "texto")

    filtro, atualizacao, upsert = banco.conversas.atualizacoes[0]
    assert filtro == {"usuarioId": 2}
    assert upsert is True
    assert atualizacao["$push"]["mensagens"]["conteudo"] == "oi"
    assert "agente" not in atualizacao["$push"]["mensagens"]


def test_salvar_mensagem_registra_agente_quando_informado(monkeypatch):
    banco = BancoFalso()
    monkeypatch.setattr(memory, "_database", lambda: banco)

    memory.salvar_mensagem_conversa(2, "assistente", "resposta", "texto", "orquestrador")

    mensagem = banco.conversas.atualizacoes[0][1]["$push"]["mensagens"]
    assert mensagem["agente"] == "orquestrador"


def test_carregar_contexto_retorna_apenas_ultimas_mensagens(monkeypatch):
    mensagens = [{"conteudo": str(numero)} for numero in range(5)]
    banco = BancoFalso(ColecaoFalsa({"usuarioId": 2, "mensagens": mensagens}))
    monkeypatch.setattr(memory, "_database", lambda: banco)

    contexto = memory.carregar_contexto_conversa(2, limite=2)

    assert contexto == mensagens[-2:]


def test_carregar_contexto_vazio_quando_nao_existe_conversa(monkeypatch):
    banco = BancoFalso(ColecaoFalsa(None))
    monkeypatch.setattr(memory, "_database", lambda: banco)

    assert memory.carregar_contexto_conversa(2) == []


def test_registrar_execucao_persiste_status(monkeypatch):
    banco = BancoFalso()
    monkeypatch.setattr(memory, "_database", lambda: banco)

    memory.registrar_execucao_agente("roteador", {"usuario_id": 2}, "concluido")

    documento = banco.execucoes_agentes.inseridos[0]
    assert documento["agente"] == "roteador"
    assert documento["status"] == "concluido"
