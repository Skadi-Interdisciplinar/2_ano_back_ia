from unittest.mock import Mock

import pytest
from app import memory


@pytest.fixture
def banco(monkeypatch):
    memory._sessoes.cache_clear()
    banco = Mock()
    banco.sessoes_trimmy.update_one.return_value.matched_count = 1
    monkeypatch.setattr(memory, "_database", Mock(return_value=banco))
    monkeypatch.setattr(memory, "iniciar_sessao", Mock(return_value={
        "_id": "sessao-teste", "usuarioId": 2, "status": "aberta", "mensagens": [],
    }))
    yield banco
    memory._sessoes.cache_clear()


def test_salvar_mensagem_cria_documento_de_conversa(banco):
    memory.salvar_mensagem_conversa(2, "usuario", "oi", "texto")

    filtro, atualizacao = banco.sessoes_trimmy.update_one.call_args.args
    assert filtro == {"_id": "sessao-teste", "usuarioId": 2, "status": "aberta"}
    assert atualizacao["$push"]["mensagens"]["conteudo"] == "oi"
    assert "agente" not in atualizacao["$push"]["mensagens"]
    assert atualizacao["$unset"] == {"resumo": ""}
    banco.sessoes_trimmy.update_one.assert_called_once()


def test_salvar_mensagem_registra_agente_quando_informado(banco):
    memory.salvar_mensagem_conversa(2, "assistente", "resposta", "texto", "orquestrador")

    atualizacao = banco.sessoes_trimmy.update_one.call_args.args[1]
    assert atualizacao["$push"]["mensagens"]["agente"] == "orquestrador"


def test_carregar_contexto_retorna_apenas_ultimas_mensagens(monkeypatch):
    mensagens = [{"conteudo": str(numero)} for numero in range(5)]
    sessao = Mock(return_value={"usuarioId": 2, "mensagens": mensagens})
    monkeypatch.setattr(memory, "iniciar_sessao", sessao)

    assert memory.carregar_contexto_conversa(2, limite=2) == mensagens[-2:]
    sessao.assert_called_once_with(2)


def test_carregar_contexto_vazio_quando_nao_existe_conversa(monkeypatch):
    monkeypatch.setattr(memory, "iniciar_sessao", Mock(return_value=None))

    assert memory.carregar_contexto_conversa(2) == []
