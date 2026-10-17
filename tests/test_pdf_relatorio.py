# ruff: noqa: DTZ001
# Datas intencionalmente sem fuso: representam TIMESTAMP do PostgreSQL.
from io import BytesIO

from app.pdf_relatorio import _grafico, renderizar_pdf
from app.relatorios import consultar_dados_relatorio
from pypdf import PdfReader
from tests.test_relatorios import filtros, preparar_banco


def test_pdf_contem_estatisticas_alertas_e_ressalvas(monkeypatch):
    preparar_banco(monkeypatch)
    dados = consultar_dados_relatorio(2, filtros())
    pdf = renderizar_pdf(dados)
    leitor = PdfReader(BytesIO(pdf))
    texto = " ".join(p.extract_text() for p in leitor.pages)
    assert pdf.startswith(b"%PDF-")
    for trecho in ("SKADI", "CD Teste", "-2,00", "2,67", "10,00", "Série 1", "Série 2", "não comprovam histórico contínuo"):
        assert trecho in texto
    # A extração pode inserir quebra de linha em palavras longas nas células.
    for status in ("RESOLVIDO", "RECONHECIDO", "ATIVO"):
        assert status in "".join(texto.split())
    assert f"Página 1 de {len(leitor.pages)}" in texto
    primeira = leitor.pages[0].extract_text()
    assert "Resumo executivo do período" in primeira
    assert "Gráfico para análise de comportamento" in primeira
    assert primeira.count("-2,00 °C") == 2
    assert primeira.count("2,67 °C") == 2
    assert primeira.count("10,00 °C") == 2
    assert "Ocorrências do período" not in primeira


def test_pdf_sem_dados_nao_inventa_estatisticas(monkeypatch):
    preparar_banco(monkeypatch, leituras=[], alertas=[])
    dados = consultar_dados_relatorio(2, filtros())
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(renderizar_pdf(dados))).pages)
    assert "Sem leituras no período" in texto
    assert "Sem alertas no período" in texto
    assert "0,00 °C" not in texto
    assert "—" in texto


def test_pdf_preserva_todos_os_alertas_em_varias_paginas(monkeypatch):
    preparar_banco(monkeypatch)
    dados = consultar_dados_relatorio(2, filtros())
    base = dados["alertas"][0]
    dados["alertas"] = [(i, base[1], f"evento-{i:03d}", *base[3:]) for i in range(75)]
    dados["total_alertas"] = 75
    dados["ocorrencias_criticas"] = 75
    leitor = PdfReader(BytesIO(renderizar_pdf(dados)))
    texto = " ".join(p.extract_text() for p in leitor.pages)
    assert len(leitor.pages) > 1
    assert all(f"evento-{i:03d}" in texto for i in range(75))
    assert all(f"Página {i} de {len(leitor.pages)}" in p.extract_text() for i, p in enumerate(leitor.pages, 1))


def test_grafico_constante_e_leitura_unica_e_pdf_simulado(monkeypatch):
    from datetime import datetime

    preparar_banco(monkeypatch, leituras=[(9, 0, datetime(2026, 10, 1), "sim-trimmy-teste-1")])
    dados = consultar_dados_relatorio(2, filtros())
    assert _grafico(dados, 500).contents
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(renderizar_pdf(dados))).pages)
    assert "dados simulados de teste" in texto
    assert "0,00 °C" in texto


def test_legenda_nao_inventa_series_para_camaras_sem_leituras(monkeypatch):
    from datetime import datetime

    preparar_banco(monkeypatch, leituras=[(9, 4, datetime(2026, 10, 1), "e1")])
    dados = consultar_dados_relatorio(2, filtros())
    leitor = PdfReader(BytesIO(renderizar_pdf(dados)))
    primeira = leitor.pages[0].extract_text()
    detalhes = " ".join(p.extract_text() for p in leitor.pages[1:])
    assert "Série 1" in primeira
    assert "Série 2" not in primeira
    assert "Câmaras sem leituras no período: 1 de 2" in primeira
    assert "B - Setor 2: Sem leituras no período" in detalhes


def test_renderizacao_nao_altera_dados_calculados(monkeypatch):
    from copy import deepcopy

    preparar_banco(monkeypatch)
    dados = consultar_dados_relatorio(2, filtros())
    original = deepcopy(dados)
    renderizar_pdf(dados)
    assert dados == original


def test_texto_do_cadastro_nao_vira_markup(monkeypatch):
    preparar_banco(monkeypatch, camaras=[(3, "<b>Equipamento</b>", "A & B", 9, 2, 6)], alertas=[])
    dados = consultar_dados_relatorio(2, filtros(camara_id=3))
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(renderizar_pdf(dados))).pages)
    assert "<b>Equipamento</b>" in texto
    assert "A & B" in texto
