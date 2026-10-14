import sys
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from scripts import modelo_predicao as comando
from tests.test_modelos_predicao import leituras, treinar


@pytest.fixture
def administrativo(monkeypatch):
    monkeypatch.setattr(comando, "validar_acesso_predicao", Mock(return_value=2))
    monkeypatch.setattr(comando, "consultar_camaras_permitidas", Mock(return_value=[{
        "camara_id": 3, "termometro": 9,
    }]))
    monkeypatch.setattr(comando, "salvar_modelo", Mock())
    return comando


def test_treinar_nao_aprova_modelo(administrativo, monkeypatch):
    monkeypatch.setattr(comando, "consultar_serie", Mock(return_value=leituras(list(range(20)))))
    monkeypatch.setattr(sys, "argv", ["modelo_predicao", "treinar", "--usuario-id", "2", "--camara-id", "3",
        "--inicio-coleta", "2026-10-12T00:00:00Z", "--inicio", "2026-10-12T00:00:00Z",
        "--fim", "2026-10-12T01:00:00Z", "--cadencia-segundos", "60", "--horizontes-minutos", "1"])

    comando.main()

    salvo = comando.salvar_modelo.call_args.args[0]
    assert salvo.status == "EM_REVISAO"
    assert salvo.aprovado_em is None


@pytest.mark.parametrize("confirmar", [False, True])
def test_aprovar_exige_confirmacao_e_versao(administrativo, monkeypatch, confirmar):
    modelo = treinar([4] * 20)
    monkeypatch.setattr(comando, "carregar_modelo", Mock(return_value=modelo))
    argumentos = ["modelo_predicao", "aprovar", "--usuario-id", "2", "--camara-id", "3", "--modelo-id", str(modelo.modelo_id)]
    if confirmar:
        argumentos.append("--confirmar-aprovacao")
    monkeypatch.setattr(sys, "argv", argumentos)
    if confirmar:
        comando.main()
        aprovado = comando.salvar_modelo.call_args.args[0]
        assert aprovado.status == "APROVADO"
        assert aprovado.aprovado_em <= datetime.now(UTC)
    else:
        with pytest.raises(SystemExit):
            comando.main()
        comando.salvar_modelo.assert_not_called()


def test_insuficiencia_nao_grava_artefato(administrativo, monkeypatch):
    monkeypatch.setattr(comando, "consultar_serie", Mock(return_value=[]))
    monkeypatch.setattr(sys, "argv", ["modelo_predicao", "treinar", "--usuario-id", "2", "--camara-id", "3",
        "--inicio-coleta", "2026-10-12T00:00:00Z", "--inicio", "2026-10-12T00:00:00Z",
        "--fim", "2026-10-12T01:00:00Z", "--cadencia-segundos", "60", "--horizontes-minutos", "1"])
    with pytest.raises(SystemExit, match="insuficientes"):
        comando.main()
    comando.salvar_modelo.assert_not_called()
