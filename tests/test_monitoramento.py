from app.tools import monitoramento


def test_tool_mantem_usuario_fora_do_modelo(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        monitoramento,
        "consultar_leituras_temperatura",
        lambda usuario_id, camara_id: chamadas.append((usuario_id, camara_id)) or {"temperatura": "4"},
    )

    ferramenta = monitoramento.criar_tool_consultar_leitura_recente(2)
    resposta = ferramenta.invoke({"camara_id": 3})

    assert resposta == {"temperatura": "4"}
    assert chamadas == [(2, 3)]
