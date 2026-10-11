from types import SimpleNamespace

import pytest
from app import memory, vectorstore
from app.tools import memoria
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto


class Sessoes:
    def __init__(self, documento=None):
        self.documento = documento
        self.indice = None

    def create_index(self, campo, **kwargs):
        self.indice = (campo, kwargs)

    def find_one(self, filtro):
        if self.documento and all(self.documento.get(k) == v for k, v in filtro.items()):
            return self.documento.copy()

    def find_one_and_update(self, filtro, atualizacao, **kwargs):
        documento = self.find_one(filtro)
        if not documento and kwargs.get("upsert"):
            self.documento = dict(atualizacao["$setOnInsert"])
            documento = self.documento.copy()
        if not documento:
            return None
        self.documento.update(atualizacao.get("$set", {}))
        return self.documento.copy()

    def update_one(self, filtro, atualizacao):
        if not self.find_one(filtro):
            return SimpleNamespace(matched_count=0)
        self.documento.update(atualizacao.get("$set", {}))
        return SimpleNamespace(matched_count=1)


def preparar(monkeypatch, documento=None):
    colecao = Sessoes(documento)
    monkeypatch.setattr(memory, "_database", lambda: SimpleNamespace(sessoes_trimmy=colecao))
    return colecao


def documento():
    return {
        "_id": "71345280-eae2-4ce7-bb08-a1bfe66182a8", "usuarioId": 2,
        "ativa": True, "status": "aberta",
        "mensagens": [{"remetente": "usuario", "conteudo": "Câmara 3?"}],
    }


def test_sessao_reutilizada_e_indice_unico_parcial(monkeypatch):
    colecao = preparar(monkeypatch)
    primeira = memory.iniciar_sessao(2)
    assert memory.iniciar_sessao(2)["_id"] == primeira["_id"]
    assert colecao.indice == ("usuarioId", {
        "unique": True, "partialFilterExpression": {"ativa": True},
    })


def test_encerrar_resume_indexa_e_mantem_mensagens(monkeypatch):
    colecao = preparar(monkeypatch, documento())
    chamadas = []

    class Modelo:
        def invoke(self, mensagens):
            assert "Câmara 3?" in mensagens[-1].content
            return SimpleNamespace(content="Perguntou sobre a câmara 3.")

    monkeypatch.setattr("app.llms.obter_modelos", lambda: (None, Modelo()))
    monkeypatch.setattr(vectorstore, "indexar_resumo", lambda *args: chamadas.append(args))
    assert memory.encerrar_sessao(2) == "Perguntou sobre a câmara 3."
    assert chamadas == [(documento()["_id"], 2, "Perguntou sobre a câmara 3.")]
    assert colecao.documento["status"] == "encerrada"
    assert colecao.documento["ativa"] is False
    assert colecao.documento["mensagens"] == documento()["mensagens"]
    assert memory.encerrar_sessao(2) is None


def test_falha_indexacao_reabre_e_preserva_resumo_para_tentar_novamente(monkeypatch):
    doc = {**documento(), "resumo": "Resumo salvo."}
    colecao = preparar(monkeypatch, doc)

    def falhar(*args):
        raise RuntimeError("Qdrant indisponível")

    monkeypatch.setattr(vectorstore, "indexar_resumo", falhar)
    with pytest.raises(RuntimeError, match="Qdrant"):
        memory.encerrar_sessao(2)
    assert colecao.documento["ativa"] is True
    assert colecao.documento["status"] == "aberta"
    monkeypatch.setattr(vectorstore, "indexar_resumo", lambda *_: None)
    assert memory.encerrar_sessao(2) == "Resumo salvo."


def test_falha_modelo_reabre_sessao(monkeypatch):
    colecao = preparar(monkeypatch, documento())

    class Modelo:
        def invoke(self, _mensagens):
            raise RuntimeError("LLM indisponível")

    monkeypatch.setattr("app.llms.obter_modelos", lambda: (None, Modelo()))
    with pytest.raises(RuntimeError, match="LLM"):
        memory.encerrar_sessao(2)
    assert colecao.documento["status"] == "aberta"


def test_sessao_em_encerramento_bloqueia_nova_mensagem_e_segundo_encerramento(monkeypatch):
    preparar(monkeypatch, {**documento(), "status": "encerrando"})
    with pytest.raises(RuntimeError, match="encerrada"):
        memory.iniciar_sessao(2)
    with pytest.raises(RuntimeError, match="encerrada"):
        memory.encerrar_sessao(2)


def test_sessao_vazia_fecha_sem_llm_ou_indexacao(monkeypatch):
    colecao = preparar(monkeypatch, {**documento(), "mensagens": []})
    monkeypatch.setattr(vectorstore, "indexar_resumo", lambda *_: pytest.fail("Não indexar vazio"))
    assert memory.encerrar_sessao(2) is None
    assert colecao.documento["ativa"] is False


def test_busca_filtra_usuario_limita_tres_e_descarta_payload_alheio(monkeypatch):
    class Cliente:
        def query_points(self, **kwargs):
            assert kwargs["limit"] == 3
            assert kwargs["query_filter"].must[0].match.value == 2
            assert kwargs["collection_name"] == "trimmy_memoria_resumos"
            return SimpleNamespace(points=[
                SimpleNamespace(payload={"usuarioId": 2, "resumo": "Permitido"}),
                SimpleNamespace(payload={"usuarioId": 9, "resumo": "Proibido"}),
            ])

    monkeypatch.setattr(vectorstore, "garantir_collection", lambda: Cliente())
    monkeypatch.setattr(vectorstore, "gerar_embedding", lambda _: [0.0] * 768)
    assert vectorstore.buscar_resumos(2, "câmara") == [{"resumo": "Permitido"}]


def test_tool_usa_identidade_interna_e_informa_resultado_vazio(monkeypatch):
    chamadas = []
    monkeypatch.setattr(memoria, "buscar_resumos", lambda *args: chamadas.append(args) or [])
    token = definir_usuario_contexto(2)
    try:
        assert memoria.buscar_historico.invoke({"busca": "câmara"}) == {
            "resumos": [], "encontrado": False,
        }
    finally:
        restaurar_usuario_contexto(token)
    assert chamadas == [(2, "câmara")]
    with pytest.raises(RuntimeError, match="autenticado"):
        memoria.buscar_historico.invoke({"busca": "câmara"})


def test_indexacao_usa_id_estavel_colecao_exclusiva_e_confirmacao(monkeypatch):
    chamadas = []
    cliente = SimpleNamespace(upsert=lambda **kwargs: chamadas.append(kwargs))
    monkeypatch.setattr(vectorstore, "garantir_collection", lambda: cliente)
    monkeypatch.setattr(vectorstore, "gerar_embedding", lambda _: [0.0] * 768)
    vectorstore.indexar_resumo(documento()["_id"], 2, "Resumo")
    chamada = chamadas[0]
    assert chamada["collection_name"] == "trimmy_memoria_resumos"
    assert chamada["wait"] is True
    assert chamada["points"][0].id == documento()["_id"]
    assert chamada["points"][0].payload["usuarioId"] == 2


def test_embedding_mantem_dimensionalidade_do_assessor(monkeypatch):
    chamadas = []
    modelo = SimpleNamespace(
        embed_query=lambda texto, **kwargs: chamadas.append((texto, kwargs)) or [0.0] * 768,
    )
    monkeypatch.setattr(vectorstore, "modelo_embeddings", lambda: modelo)
    assert len(vectorstore.gerar_embedding("Resumo")) == 768
    assert chamadas == [("Resumo", {"output_dimensionality": 768})]
