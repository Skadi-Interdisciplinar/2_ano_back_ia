from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from unittest.mock import MagicMock, Mock

import pytest
from app import relatorios
from app.erros import SaidaModeloInvalida, ServicoIndisponivel
from app.relatorios import (
    FiltroRelatorioInvalido,
    _cd_permitido,
    _gravidade_critica,
    registrar_relatorio,
)
from app.schemas import RelatorioRequest
from app.tools.access import EscopoAcesso


def test_gestor_usa_apenas_o_proprio_cd():
    escopo = EscopoAcesso(usuario_id=12, nivel_acesso="GESTOR", cd_id=2)

    cd = _cd_permitido(escopo, None)

    assert cd == 2


def test_super_admin_precisa_informar_cd():
    escopo = EscopoAcesso(usuario_id=1, nivel_acesso="SUPER_ADMIN", cd_id=None)

    with pytest.raises(FiltroRelatorioInvalido):
        _cd_permitido(escopo, None)


def test_reconhece_grandeza_critica_sem_alterar_valor_do_alerta():
    assert _gravidade_critica("CRITICA") is True
    assert _gravidade_critica("crítica") is True
    assert _gravidade_critica("urgente") is False


def test_registra_hash_e_download_do_relatorio(monkeypatch):
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(12, "GESTOR", 2), (99,)]
    monkeypatch.setattr("app.relatorios.get_conn", Mock(return_value=conexao))

    registrar_relatorio(12, {"cd_id": 2, "data_inicial": "2026-10-01", "data_final": "2026-10-10"}, b"%PDF")

    assert cursor.execute.call_count == 3
    assert cursor.execute.call_args_list[1].args[1][3] == sha256(b"%PDF").hexdigest()
    assert cursor.execute.call_args_list[1].args[1][4] == "gerado"
    assert cursor.execute.call_args_list[2].args[1] == (99, 12, "baixou")
    conexao.commit.assert_called_once()


@pytest.mark.parametrize("nivel", ["ADMIN", "OPERADOR", "GESTOR"])
def test_perfis_podem_gerar_relatorio_do_proprio_cd(nivel):
    assert _cd_permitido(EscopoAcesso(12, nivel, 2), None) == 2


@pytest.mark.parametrize("nivel", ["ADMIN", "OPERADOR", "GESTOR"])
def test_perfis_nao_podem_gerar_relatorio_de_outro_cd(nivel):
    with pytest.raises(PermissionError):
        _cd_permitido(EscopoAcesso(12, nivel, 2), 3)


def test_gestor_nao_pode_selecionar_outro_cd():
    with pytest.raises(PermissionError):
        _cd_permitido(EscopoAcesso(12, "GESTOR", 2), 3)


def test_snapshot_preserva_gravidade_e_calcula_media_de_todas_as_leituras(monkeypatch):
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value
    horario = datetime.fromisoformat("2026-10-29T12:00:00")
    cursor.fetchone.side_effect = [("CD de teste",), (horario,)]
    alertas = [(1, 3, "TEMPERATURA", horario, "URGENTE", "ATIVO"),
               (2, 3, "TEMPERATURA", horario, "CRITICA", "RESOLVIDO")]
    cursor.fetchall.side_effect = [
        [(1, Decimal(-2), horario, "1"), (1, Decimal(0), horario, "2"),
         (2, Decimal(4), horario, "3")], alertas,
    ]
    monkeypatch.setattr(relatorios, "get_conn", Mock(return_value=conexao))
    monkeypatch.setattr(relatorios, "validar_acesso", Mock(return_value=EscopoAcesso(12, "GESTOR", 2)))
    monkeypatch.setattr(relatorios, "_selecionar_camaras", Mock(return_value=[
        {"camara_id": 3, "termometro": 1}, {"camara_id": 4, "termometro": 2},
    ]))
    filtros = RelatorioRequest(token="teste", data_inicial=date(2026, 10, 28), data_final=date(2026, 10, 29))

    dados = relatorios.consultar_dados_relatorio(12, filtros)

    assert dados["media"] == Decimal(2) / 3
    assert dados["minima"] == -2
    assert dados["maxima"] == 4
    assert dados["alertas"] == alertas
    assert dados["ocorrencias_criticas"] == 1
    assert dados["total_alertas"] == 2
    parametros = cursor.execute.call_args_list[1].args[1]
    assert parametros[1] == datetime.fromisoformat("2026-10-28T00:00:00")
    assert parametros[2] == datetime.fromisoformat("2026-10-30T00:00:00")
    conexao.set_session.assert_called_once_with(isolation_level="REPEATABLE READ", readonly=True)
    conexao.close.assert_called_once()


def test_falha_no_registro_faz_rollback(monkeypatch):
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("falha simulada")
    monkeypatch.setattr(relatorios, "get_conn", Mock(return_value=conexao))
    monkeypatch.setattr(relatorios, "validar_acesso", Mock(return_value=EscopoAcesso(12, "GESTOR", 2)))

    with pytest.raises(RuntimeError):
        registrar_relatorio(12, {"cd_id": 2, "data_inicial": "2026-10-28", "data_final": "2026-10-29"}, b"pdf")

    conexao.rollback.assert_called_once()
    conexao.commit.assert_not_called()


def test_so_registra_os_bytes_da_segunda_geracao_aprovada(monkeypatch):
    dados = {"cd_id": 2}
    monkeypatch.setattr(relatorios, "consultar_dados_relatorio", Mock(return_value=dados))
    renderizar = Mock(side_effect=[b"primeiro", b"segundo"])
    monkeypatch.setattr("app.pdf_relatorio.renderizar_pdf", renderizar)
    monkeypatch.setattr(relatorios, "julgar_pdf", Mock(side_effect=[False, True]))
    registrar = Mock()
    monkeypatch.setattr(relatorios, "registrar_relatorio", registrar)

    pdf = relatorios.gerar_relatorio_pdf(12, Mock())

    assert pdf == b"segundo"
    renderizar.assert_called_with(dados, conservador=True)
    registrar.assert_called_once_with(12, dados, b"segundo")


@pytest.mark.parametrize("erro", [ServicoIndisponivel(), SaidaModeloInvalida()])
def test_falha_do_juiz_nao_registra_nem_repete_a_renderizacao(monkeypatch, erro):
    monkeypatch.setattr(relatorios, "consultar_dados_relatorio", Mock(return_value={}))
    renderizar = Mock(return_value=b"pdf")
    monkeypatch.setattr("app.pdf_relatorio.renderizar_pdf", renderizar)
    monkeypatch.setattr(relatorios, "julgar_pdf", Mock(side_effect=erro))
    registrar = Mock()
    monkeypatch.setattr(relatorios, "registrar_relatorio", registrar)

    with pytest.raises(type(erro)):
        relatorios.gerar_relatorio_pdf(12, Mock())

    renderizar.assert_called_once()
    registrar.assert_not_called()
