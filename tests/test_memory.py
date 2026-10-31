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
