from unittest.mock import Mock

import pytest
from app import memory
from app.erros import SessaoEmAlteracao


def test_salva_pergunta_e_resposta_na_mesma_sessao(monkeypatch):
    colecao = Mock()
    colecao.update_one.return_value.matched_count = 1
    monkeypatch.setattr(memory, "_sessoes", Mock(return_value=colecao))

    memory.salvar_turno_conversa(12, "sessao-1", "Qual a temperatura?", "4.00 °C")

    filtro, alteracao = colecao.update_one.call_args.args
    assert filtro["_id"] == "sessao-1"
    assert [item["remetente"] for item in alteracao["$push"]["mensagens"]["$each"]] == ["usuario", "assistente"]


def test_rejeita_gravacao_quando_a_sessao_foi_fechada(monkeypatch):
    colecao = Mock()
    colecao.update_one.return_value.matched_count = 0
    monkeypatch.setattr(memory, "_sessoes", Mock(return_value=colecao))

    with pytest.raises(SessaoEmAlteracao):
        memory.salvar_turno_conversa(12, "sessao-1", "Pergunta", "Resposta")


def test_leitura_e_gravacao_de_sessoes_separam_dois_usuarios(monkeypatch):
    colecao = Mock()
    colecao.find_one_and_update.side_effect = [
        {"_id": "sessao-a", "status": "aberta", "mensagens": []},
        {"_id": "sessao-b", "status": "aberta", "mensagens": []},
    ]
    colecao.update_one.return_value.matched_count = 1
    monkeypatch.setattr(memory, "_sessoes", Mock(return_value=colecao))

    for usuario in (20, 21):
        sessao = memory.iniciar_sessao(usuario)
        memory.salvar_turno_conversa(usuario, sessao["_id"], "oi", "Olá")

    assert [c.args[0]["usuarioId"] for c in colecao.find_one_and_update.call_args_list] == [20, 21]
    assert [(c.args[0]["usuarioId"], c.args[0]["_id"]) for c in colecao.update_one.call_args_list] == [
        (20, "sessao-a"), (21, "sessao-b"),
    ]
