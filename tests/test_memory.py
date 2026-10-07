from app import memory


class BancoFalso:
    def __init__(self):
        self.conversas = self
        self.atualizacoes = []

    def update_one(self, filtro, atualizacao, upsert=False):
        self.atualizacoes.append((filtro, atualizacao, upsert))


def test_salvar_mensagem_grava_conteudo_do_usuario(monkeypatch):
    banco = BancoFalso()
    monkeypatch.setattr(memory, "_database", lambda: banco)

    memory.salvar_mensagem_conversa(2, "usuario", "oi", "texto")

    filtro, atualizacao, upsert = banco.atualizacoes[0]
    assert filtro == {"usuarioId": 2}
    assert upsert is True
    assert atualizacao["$push"]["mensagens"]["conteudo"] == "oi"
