# ruff: noqa: DTZ001
# Datas intencionalmente sem fuso: representam TIMESTAMP do PostgreSQL.
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from unittest.mock import Mock

import pytest
from app import relatorios
from app.schemas import RelatorioRequest
from pydantic import ValidationError
from tests.conftest import banco_sql


def filtros(**alteracoes):
    return RelatorioRequest.model_validate({
        "token": "teste", "data_inicial": "2026-10-01", "data_final": "2026-10-02", **alteracoes,
    })


def preparar_banco(monkeypatch, nivel="GESTOR", cd=7, camaras=None, leituras=None, alertas=None):
    cursor, conexao = banco_sql()
    cursor.fetchone.side_effect = [(2, nivel, cd), ("CD Teste",), (datetime(2026, 10, 3, 8),)]
    cursor.fetchall.side_effect = [
        camaras if camaras is not None else [
            (3, "A", "Setor 1", 9, Decimal(2), Decimal(6)),
            (4, "B", "Setor 2", 10, Decimal(2), Decimal(6)),
        ],
        leituras if leituras is not None else [
            (9, Decimal(-2), datetime(2026, 10, 1), "e1"),
            (9, Decimal(0), datetime(2026, 10, 1, 12), "e2"),
            (10, Decimal(10), datetime(2026, 10, 2, 23, 59, 59), "e3"),
        ],
        alertas if alertas is not None else [
            (3, 3, "TEMPERATURA_FORA_PADRAO", datetime(2026, 10, 2, 12), "CRITICA", "RESOLVIDO"),
            (2, 4, "TEMPERATURA_FORA_PADRAO", datetime(2026, 10, 2), "URGENTE", "RECONHECIDO"),
            (1, 3, "TEMPERATURA_FORA_PADRAO", datetime(2026, 10, 1), "BAIXA", "ATIVO"),
        ],
    ]
    monkeypatch.setattr(relatorios, "get_conn", Mock(return_value=conexao))
    return cursor, conexao


@pytest.mark.parametrize("alteracao", [
    {"data_final": "2026-09-30"}, {"data_final": "9999-12-31"},
    {"data_inicial": "01/10/2026"}, {"data_inicial": 0},
    {"cd_id": True}, {"camara_id": 0}, {"token": " "},
    {"usuario_id": 2}, {"nivel_acesso": "GESTOR"}, {"temperatura": 4},
])
def test_contrato_rejeita_filtros_invalidos(alteracao):
    with pytest.raises(ValidationError):
        filtros(**alteracao)


@pytest.mark.parametrize("nivel", ["ADMIN", "OPERADOR", "VISITANTE"])
def test_bloqueia_perfil_antes_das_consultas_operacionais(monkeypatch, nivel):
    cursor, conexao = preparar_banco(monkeypatch, nivel=nivel)
    with pytest.raises(PermissionError):
        relatorios.consultar_dados_relatorio(2, filtros())
    assert cursor.execute.call_count == 1
    conexao.close.assert_called_once()


@pytest.mark.parametrize("cd,solicitado", [(None, None), (7, 8)])
def test_gestor_sem_cd_ou_cd_divergente_nao_consulta_dados(monkeypatch, cd, solicitado):
    cursor, _ = preparar_banco(monkeypatch, cd=cd)
    with pytest.raises(PermissionError):
        relatorios.consultar_dados_relatorio(2, filtros(cd_id=solicitado))
    assert cursor.execute.call_count == 1


def test_super_admin_exige_cd(monkeypatch):
    preparar_banco(monkeypatch, nivel="SUPER_ADMIN", cd=None)
    with pytest.raises(relatorios.FiltroRelatorioInvalido):
        relatorios.consultar_dados_relatorio(2, filtros())


@pytest.mark.parametrize("nivel", ["GESTOR", "SUPER_ADMIN"])
def test_resumo_consolidado_usa_leituras_e_historico_completo(monkeypatch, nivel):
    cursor, conexao = preparar_banco(monkeypatch, nivel=nivel)
    dados = relatorios.consultar_dados_relatorio(2, filtros(cd_id=7))

    assert dados["minima"] == -2
    assert dados["maxima"] == 10
    assert dados["media"] == Decimal(8) / 3  # Não é a média das médias das câmaras.
    assert dados["quantidade_leituras"] == 3
    assert dados["total_alertas"] == 3
    assert dados["ocorrencias_criticas"] == 1  # Inclui o alerta resolvido.
    assert dados["dados_simulados"] is False
    conexao.set_session.assert_called_once_with(isolation_level="REPEATABLE READ", readonly=True)
    conexao.close.assert_called_once()
    consultas = [c.args for c in cursor.execute.call_args_list]
    assert "cod_cd = %s" in consultas[2][0]
    assert consultas[2][1] == (7,)
    assert consultas[3][1] == ([9, 10], datetime(2026, 10, 1), datetime(2026, 10, 3))
    assert "data_hora < %s" in consultas[3][0]
    assert "status =" not in consultas[4][0]
    assert "JOIN" not in consultas[4][0]


@pytest.mark.parametrize("gravidade,quantidade", [
    ("CRITICA", 1), ("URGENTE", 0), ("ATENCAO", 0), ("BAIXA", 0),
])
def test_contagem_critica_usa_gravidades_do_backend(monkeypatch, gravidade, quantidade):
    preparar_banco(monkeypatch, alertas=[
        (1, 3, "TEMPERATURA_FORA_PADRAO", datetime(2026, 10, 1), gravidade, "ATIVO"),
    ])

    dados = relatorios.consultar_dados_relatorio(2, filtros())

    assert dados["total_alertas"] == 1
    assert dados["ocorrencias_criticas"] == quantidade


def test_camara_especifica_limita_ambas_as_consultas(monkeypatch):
    cursor, _ = preparar_banco(monkeypatch, camaras=[(3, "A", "Setor 1", 9, 2, 6)], alertas=[])
    relatorios.consultar_dados_relatorio(2, filtros(camara_id=3))
    consultas = [c.args for c in cursor.execute.call_args_list]
    assert consultas[2][1] == (7, 3)
    assert consultas[3][1][0] == [9]
    assert consultas[4][1][0] == [3]


def test_camara_inexistente_nao_amplia_consulta(monkeypatch):
    cursor, _ = preparar_banco(monkeypatch, camaras=[])
    with pytest.raises(relatorios.SelecaoRelatorioNaoEncontrada):
        relatorios.consultar_dados_relatorio(2, filtros(camara_id=999))
    assert cursor.execute.call_count == 3


def test_cd_inexistente_nao_consulta_camaras(monkeypatch):
    cursor, _ = preparar_banco(monkeypatch)
    cursor.fetchone.side_effect = [(2, "GESTOR", 7), None]
    with pytest.raises(relatorios.SelecaoRelatorioNaoEncontrada):
        relatorios.consultar_dados_relatorio(2, filtros())
    assert cursor.execute.call_count == 2


def test_sem_leituras_nao_vira_temperatura_zero(monkeypatch):
    preparar_banco(monkeypatch, leituras=[], alertas=[])
    dados = relatorios.consultar_dados_relatorio(2, filtros())
    assert dados["quantidade_leituras"] == 0
    assert dados["minima"] is dados["media"] is dados["maxima"] is None
    assert dados["total_alertas"] == 0


@pytest.mark.parametrize("valor,horario", [("NaN", datetime(2026, 10, 1)),
                                        ("Infinity", datetime(2026, 10, 1)),
                                        (None, datetime(2026, 10, 1)), (4, None)])
def test_leitura_invalida_nao_e_descartada_silenciosamente(monkeypatch, valor, horario):
    preparar_banco(monkeypatch, leituras=[(9, valor, horario, "e1")])
    with pytest.raises(relatorios.DadosRelatorioInvalidos):
        relatorios.consultar_dados_relatorio(2, filtros())


def test_origem_simulada_identificada_pelo_evento(monkeypatch):
    preparar_banco(monkeypatch, leituras=[(9, 4, datetime(2026, 10, 1), "sim-trimmy-lote-1")])
    assert relatorios.consultar_dados_relatorio(2, filtros())["dados_simulados"] is True


def test_registro_atomico_contem_hash_periodo_e_usuario(monkeypatch):
    cursor, conexao = banco_sql()
    cursor.fetchone.side_effect = [(2, "GESTOR", 7), (88,)]
    monkeypatch.setattr(relatorios, "get_conn", Mock(return_value=conexao))
    dados = {"cd_id": 7, "data_inicial": date(2026, 10, 1), "data_final": date(2026, 10, 2)}

    relatorios.registrar_relatorio(2, dados, b"%PDF-teste")

    consultas = [c.args for c in cursor.execute.call_args_list]
    assert consultas[1][1] == (2, dados["data_inicial"], dados["data_final"], sha256(b"%PDF-teste").hexdigest(), "GERADO")
    assert consultas[2][1] == (88, 2, "BAIXOU")
    conexao.commit.assert_called_once()
    conexao.rollback.assert_not_called()
    conexao.close.assert_called_once()


@pytest.mark.parametrize("etapa", [1, 2, 3])
def test_falha_de_registro_reverte_tudo(monkeypatch, etapa):
    cursor, conexao = banco_sql()
    cursor.fetchone.side_effect = [(2, "GESTOR", 7), (88,)]
    cursor.execute.side_effect = [None] * (etapa - 1) + [RuntimeError("falha")]
    monkeypatch.setattr(relatorios, "get_conn", Mock(return_value=conexao))
    with pytest.raises(RuntimeError):
        relatorios.registrar_relatorio(2, {"cd_id": 7, "data_inicial": date(2026, 10, 1), "data_final": date(2026, 10, 2)}, b"pdf")
    conexao.rollback.assert_called_once()
    conexao.commit.assert_not_called()


def test_permissao_revogada_antes_do_registro_impede_entrega(monkeypatch):
    cursor, conexao = banco_sql(retorno=(2, "ADMIN", 7))
    monkeypatch.setattr(relatorios, "get_conn", Mock(return_value=conexao))
    with pytest.raises(PermissionError):
        relatorios.registrar_relatorio(2, {"cd_id": 7}, b"pdf")
    assert cursor.execute.call_count == 1
    conexao.rollback.assert_called_once()


def test_falha_no_commit_nao_e_tratada_como_sucesso(monkeypatch):
    cursor, conexao = banco_sql()
    cursor.fetchone.side_effect = [(2, "GESTOR", 7), (88,)]
    conexao.commit.side_effect = RuntimeError("commit indisponível")
    monkeypatch.setattr(relatorios, "get_conn", Mock(return_value=conexao))
    with pytest.raises(RuntimeError):
        relatorios.registrar_relatorio(2, {"cd_id": 7, "data_inicial": date(2026, 10, 1),
                                         "data_final": date(2026, 10, 2)}, b"pdf")
    conexao.rollback.assert_called_once()
    conexao.close.assert_called_once()


def test_falha_de_consulta_fecha_snapshot_e_nao_renderiza(monkeypatch):
    cursor, conexao = preparar_banco(monkeypatch)
    cursor.execute.side_effect = RuntimeError("consulta indisponível")
    renderizar = Mock()
    monkeypatch.setattr("app.pdf_relatorio.renderizar_pdf", renderizar)
    with pytest.raises(RuntimeError):
        relatorios.gerar_relatorio_pdf(2, filtros())
    conexao.close.assert_called_once()
    renderizar.assert_not_called()


def test_pdf_so_renderiza_depois_de_fechar_leitura(monkeypatch):
    from app import pdf_relatorio

    _, conexao = preparar_banco(monkeypatch)
    registrar = Mock()
    monkeypatch.setattr(relatorios, "registrar_relatorio", registrar)

    def renderizar(dados):
        conexao.close.assert_called_once()
        return b"%PDF-teste"

    monkeypatch.setattr(pdf_relatorio, "renderizar_pdf", renderizar)
    assert relatorios.gerar_relatorio_pdf(2, filtros()) == b"%PDF-teste"
    assert registrar.call_args.args[0] == 2
    assert registrar.call_args.args[2] == b"%PDF-teste"


def test_falha_de_renderizacao_nao_registra(monkeypatch):
    preparar_banco(monkeypatch)
    registrar = Mock()
    monkeypatch.setattr(relatorios, "registrar_relatorio", registrar)
    monkeypatch.setattr("app.pdf_relatorio.renderizar_pdf", Mock(side_effect=RuntimeError("falha")))
    with pytest.raises(RuntimeError):
        relatorios.gerar_relatorio_pdf(2, filtros())
    registrar.assert_not_called()
