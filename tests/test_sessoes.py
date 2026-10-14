from unittest.mock import Mock, patch

import pytest
from app import memory, vectorstore
from app.tools import memoria
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto


@pytest.fixture
def sessao():
    return {
        "_id": "71345280-eae2-4ce7-bb08-a1bfe66182a8", "usuarioId": 2,
        "ativa": True, "status": "aberta",
        "mensagens": [{"remetente": "usuario", "conteudo": "Câmara 3?"}],
    }


@pytest.fixture
def colecao(monkeypatch, sessao):
    memory._sessoes.cache_clear()
    banco = Mock()
    colecao = banco.sessoes_trimmy
    colecao.find_one_and_update.return_value = sessao
    monkeypatch.setattr(memory, "_database", Mock(return_value=banco))
    yield colecao
    memory._sessoes.cache_clear()


def test_sessao_reutilizada_e_indice_unico_parcial(colecao, sessao):
    assert memory.iniciar_sessao(2) == sessao
    assert memory.iniciar_sessao(2) == sessao

    assert colecao.find_one_and_update.call_count == 2
    filtro = colecao.find_one_and_update.call_args.args[0]
    assert filtro == {"usuarioId": 2, "ativa": True}
    colecao.create_index.assert_called_with(
        "usuarioId", unique=True, partialFilterExpression={"ativa": True},
    )
    colecao.create_index.assert_called_once()


def test_encerrar_resume_indexa_e_mantem_mensagens(colecao, sessao):
    modelo = Mock()
    modelo.invoke.return_value.content = "Perguntou sobre a câmara 3."
    with (
        patch("app.llms.obter_modelos", return_value=(None, modelo)),
        patch("app.vectorstore.indexar_resumo") as indexar,
    ):
        assert memory.encerrar_sessao(2) == "Perguntou sobre a câmara 3."

    indexar.assert_called_once_with(sessao["_id"], 2, "Perguntou sobre a câmara 3.")
    assert "Câmara 3?" in modelo.invoke.call_args.args[0][-1].content
    fechamento = colecao.update_one.call_args.args[1]["$set"]
    assert fechamento["status"] == "encerrada"
    assert fechamento["ativa"] is False
    for chamada in colecao.update_one.call_args_list:
        assert "mensagens" not in chamada.args[1]["$set"]

    colecao.find_one_and_update.return_value = None
    colecao.find_one.return_value = None
    assert memory.encerrar_sessao(2) is None


def test_falha_indexacao_reabre_e_preserva_resumo_para_tentar_novamente(monkeypatch, colecao, sessao):
    sessao["resumo"] = "Resumo salvo."
    modelos = Mock()
    monkeypatch.setattr("app.llms.obter_modelos", modelos)
    with (
        patch("app.vectorstore.indexar_resumo", side_effect=RuntimeError("Qdrant indisponível")),
        pytest.raises(RuntimeError, match="Qdrant"),
    ):
        memory.encerrar_sessao(2)

    colecao.update_one.assert_called_once_with(
        {"_id": sessao["_id"]}, {"$set": {"status": "aberta"}},
    )
    with patch("app.vectorstore.indexar_resumo") as indexar:
        assert memory.encerrar_sessao(2) == "Resumo salvo."

    modelos.assert_not_called()
    indexar.assert_called_once_with(sessao["_id"], 2, "Resumo salvo.")


def test_falha_modelo_reabre_sessao(colecao, sessao):
    modelo = Mock()
    modelo.invoke.side_effect = RuntimeError("LLM indisponível")
    with (
        patch("app.llms.obter_modelos", return_value=(None, modelo)),
        pytest.raises(RuntimeError, match="LLM"),
    ):
        memory.encerrar_sessao(2)

    colecao.update_one.assert_called_once_with(
        {"_id": sessao["_id"]}, {"$set": {"status": "aberta"}},
    )


def test_sessao_em_encerramento_bloqueia_nova_mensagem_e_segundo_encerramento(colecao, sessao):
    sessao["status"] = "encerrando"
    with pytest.raises(RuntimeError, match="encerrada"):
        memory.iniciar_sessao(2)

    colecao.find_one_and_update.return_value = None
    colecao.find_one.return_value = sessao
    with pytest.raises(RuntimeError, match="encerrada"):
        memory.encerrar_sessao(2)


def test_sessao_vazia_fecha_sem_llm_ou_indexacao(colecao, sessao):
    sessao["mensagens"] = []
    with (
        patch("app.llms.obter_modelos") as modelos,
        patch("app.vectorstore.indexar_resumo") as indexar,
    ):
        assert memory.encerrar_sessao(2) is None

    modelos.assert_not_called()
    indexar.assert_not_called()
    assert colecao.update_one.call_args.args[1]["$set"]["ativa"] is False


def test_busca_filtra_usuario_limita_tres_e_descarta_payload_alheio(monkeypatch):
    cliente = Mock()
    cliente.query_points.return_value.points = [
        Mock(payload={"usuarioId": 2, "resumo": "Permitido"}),
        Mock(payload={"usuarioId": 9, "resumo": "Proibido"}),
    ]
    monkeypatch.setattr(vectorstore, "garantir_collection", Mock(return_value=cliente))
    monkeypatch.setattr(vectorstore, "gerar_embedding", Mock(return_value=[0.0] * 768))

    assert vectorstore.buscar_resumos(2, "câmara") == [{"resumo": "Permitido"}]

    consulta = cliente.query_points.call_args.kwargs
    assert consulta["limit"] == 3
    assert consulta["query_filter"].must[0].match.value == 2
    assert consulta["collection_name"] == "trimmy_memoria_resumos"


def test_tool_usa_identidade_interna_e_informa_resultado_vazio(monkeypatch):
    buscar = Mock(return_value=[])
    monkeypatch.setattr(memoria, "buscar_resumos", buscar)
    token = definir_usuario_contexto(2)
    try:
        assert memoria.buscar_historico.invoke({"busca": "câmara"}) == {
            "resumos": [], "encontrado": False,
        }
    finally:
        restaurar_usuario_contexto(token)

    buscar.assert_called_once_with(2, "câmara")
    with pytest.raises(RuntimeError, match="autenticado"):
        memoria.buscar_historico.invoke({"busca": "câmara"})


def test_indexacao_usa_id_estavel_colecao_exclusiva_e_confirmacao(monkeypatch, sessao):
    cliente = Mock()
    monkeypatch.setattr(vectorstore, "garantir_collection", Mock(return_value=cliente))
    monkeypatch.setattr(vectorstore, "gerar_embedding", Mock(return_value=[0.0] * 768))

    vectorstore.indexar_resumo(sessao["_id"], 2, "Resumo")

    cliente.upsert.assert_called_once()
    envio = cliente.upsert.call_args.kwargs
    assert envio["collection_name"] == "trimmy_memoria_resumos"
    assert envio["wait"] is True
    assert envio["points"][0].id == sessao["_id"]
    assert envio["points"][0].payload["usuarioId"] == 2


def test_embedding_mantem_dimensionalidade_do_assessor(monkeypatch):
    modelo = Mock()
    modelo.embed_query.return_value = [0.0] * 768
    monkeypatch.setattr(vectorstore, "modelo_embeddings", Mock(return_value=modelo))

    assert len(vectorstore.gerar_embedding("Resumo")) == 768
    modelo.embed_query.assert_called_once_with("Resumo", output_dimensionality=768)


def test_indice_vetorial_e_preparado_uma_vez(monkeypatch):
    vectorstore.garantir_collection.cache_clear()
    cliente = Mock()
    cliente.collection_exists.return_value = True
    monkeypatch.setattr(vectorstore, "cliente_qdrant", Mock(return_value=cliente))
    try:
        assert vectorstore.garantir_collection() is cliente
        assert vectorstore.garantir_collection() is cliente
        cliente.collection_exists.assert_called_once()
        cliente.create_payload_index.assert_called_once()
        cliente.create_collection.assert_not_called()
    finally:
        vectorstore.garantir_collection.cache_clear()


def test_falha_preparacao_vetorial_permite_nova_tentativa(monkeypatch):
    vectorstore.garantir_collection.cache_clear()
    cliente = Mock()
    cliente.collection_exists.side_effect = [RuntimeError("Indisponível"), True]
    monkeypatch.setattr(vectorstore, "cliente_qdrant", Mock(return_value=cliente))
    try:
        with pytest.raises(RuntimeError):
            vectorstore.garantir_collection()
        assert vectorstore.garantir_collection() is cliente
        assert cliente.collection_exists.call_count == 2
    finally:
        vectorstore.garantir_collection.cache_clear()
