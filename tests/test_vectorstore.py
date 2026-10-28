from unittest.mock import Mock

from app import vectorstore


def test_busca_resumos_filtra_resultado_de_outro_usuario(monkeypatch):
    cliente = Mock()
    cliente.query_points.return_value.points = [
        Mock(payload={"usuarioId": 12, "resumo": "Câmara 03 consultada."}),
        Mock(payload={"usuarioId": 99, "resumo": "Não pode aparecer."}),
    ]
    monkeypatch.setattr(vectorstore, "garantir_collection", Mock(return_value=cliente))
    monkeypatch.setattr(vectorstore, "gerar_embedding", Mock(return_value=[0.0] * 768))

    resumos = vectorstore.buscar_resumos(12, "câmara")

    assert resumos == [{"resumo": "Câmara 03 consultada."}]
    assert cliente.query_points.call_args.kwargs["limit"] == 3
