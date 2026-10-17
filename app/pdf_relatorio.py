"""Layout do design.md: apresentação vetorial, sem consultas ou cálculos de negócio."""

from functools import partial
from io import BytesIO
from itertools import pairwise
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

AZUL = colors.HexColor("#102F4C")
CLARO = colors.HexColor("#ADD9FA")
ROSA = colors.HexColor("#FFB3BE")
MINIMA = colors.HexColor("#2795F5")
MAXIMA = colors.HexColor("#FA4052")
CORES_SERIES = ["#1674BE", "#D54D54", "#218762", "#8D51A8", "#AB650F", "#387981"]


class Cartao(Table):
    """Tabela de apresentação com fundo arredondado; usada apenas em blocos compactos."""

    def __init__(self, linhas, larguras, *, cor=colors.white, sombra=False, padding=10):
        self.cor = cor
        self.sombra = sombra
        super().__init__(linhas, colWidths=larguras, style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), padding),
            ("TOPPADDING", (0, 0), (-1, -1), padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ]))

    def draw(self):
        self.canv.saveState()
        if self.sombra:
            self.canv.setFillColor(colors.HexColor("#E6E9ED"))
            self.canv.roundRect(1, -2, self._width, self._height, 11, stroke=0, fill=1)
        self.canv.setFillColor(self.cor)
        self.canv.roundRect(0, 0, self._width, self._height, 11, stroke=0, fill=1)
        self.canv.restoreState()
        super().draw()


class CanvasPaginado(Canvas):
    """Reproduz as páginas compostas para escrever o total correto no rodapé."""

    def __init__(self, *args, ano, **kwargs):
        super().__init__(*args, **kwargs)
        self.ano = ano
        self.paginas = []

    def showPage(self):
        self.paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.paginas)
        for estado in self.paginas:
            self.__dict__.update(estado)
            self.saveState()
            self.setStrokeColor(colors.HexColor("#DADADA"))
            self.line(36, 36, A4[0] - 36, 36)
            self.setFillColor(AZUL)
            self.setFont("Helvetica", 9)
            self.drawString(36, 22, f"SKADI - {self.ano}")
            self.drawRightString(A4[0] - 36, 22, f"Página {self._pageNumber} de {total}")
            self.restoreState()
            super().showPage()
        super().save()


def _temperatura(valor) -> str:
    return "—" if valor is None else f"{valor:.2f} °C".replace(".", ",")


def _camaras_com_leituras(dados: dict) -> list[dict]:
    sensores = {l[0] for l in dados["leituras"]}
    return [c for c in dados["camaras"] if c["termometro"] in sensores]


def _grafico(dados: dict, largura: float) -> Drawing:
    desenho = Drawing(largura, 165)
    x0, x1, y0, y1 = 38, largura - 20, 34, 144
    inicio, fim = dados["primeira_leitura"], dados["ultima_leitura"]
    duracao = (fim - inicio).total_seconds()
    minimo, maximo = float(dados["minima"]), float(dados["maxima"])
    if minimo == maximo:
        minimo, maximo = minimo - 0.5, maximo + 0.5
    for i in range(5):
        y = y0 + (y1 - y0) * i / 4
        desenho.add(Line(x0, y, x1, y, strokeColor=colors.HexColor("#E6EDF3")))
        valor = minimo + (maximo - minimo) * i / 4
        desenho.add(String(x0 - 5, y - 3, f"{valor:.2f}".replace(".", ","),
                           textAnchor="end", fontSize=8))
    desenho.add(String(5, 154, "°C", fontSize=9))
    for i in range(3 if duracao else 1):
        fracao = i / 2 if duracao else 0.5
        horario = inicio + (fim - inicio) * fracao
        x = x0 + (x1 - x0) * fracao
        desenho.add(String(x, 19, horario.strftime("%d/%m/%Y"), textAnchor="middle", fontSize=8))
        desenho.add(String(x, 7, horario.strftime("%H:%M:%S"), textAnchor="middle", fontSize=8))
    camaras = _camaras_com_leituras(dados)
    for indice, camara in enumerate(camaras):
        cor = colors.HexColor(CORES_SERIES[indice % len(CORES_SERIES)])
        pontos = []
        for sensor, temperatura, horario, _evento in dados["leituras"]:
            if sensor == camara["termometro"]:
                x = x0 + (x1 - x0) * ((horario - inicio).total_seconds() / duracao if duracao else 0.5)
                y = y0 + (y1 - y0) * (float(temperatura) - minimo) / (maximo - minimo)
                pontos.append((x, y))
        if len(camaras) == 1 and len(pontos) > 1:
            area = [(pontos[0][0], y0), *pontos, (pontos[-1][0], y0)]
            desenho.add(Polygon([coordenada for p in area for coordenada in p],
                                fillColor=colors.HexColor("#E4F3FF"), strokeColor=None))
        tracejado = [4, 2] if indice // len(CORES_SERIES) % 2 else None
        for a, b in pairwise(pontos):
            desenho.add(Line(*a, *b, strokeColor=cor, strokeWidth=1.3, strokeDashArray=tracejado))
        for x, y in pontos:
            desenho.add(Circle(x, y, 1.2, fillColor=cor, strokeColor=cor))
    return desenho


def renderizar_pdf(dados: dict) -> bytes:
    saida = BytesIO()
    largura = A4[0] - 72
    estilos = {
        "normal": ParagraphStyle("Normal", fontName="Helvetica", fontSize=10, leading=13,
                                 textColor=colors.HexColor("#161616")),
        "titulo": ParagraphStyle("Titulo", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=AZUL),
        "secao": ParagraphStyle("Secao", fontName="Helvetica", fontSize=11, leading=13, textColor=AZUL),
        "nota": ParagraphStyle("Nota", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#646464")),
        "valor": ParagraphStyle("Valor", fontName="Helvetica", fontSize=22, leading=28, alignment=TA_CENTER, textColor=AZUL),
        "rotulo": ParagraphStyle("Rotulo", fontName="Helvetica", fontSize=10, leading=12, alignment=TA_CENTER),
        "quantidade": ParagraphStyle("Quantidade", fontName="Helvetica-Bold", fontSize=30, leading=35, alignment=TA_CENTER),
    }

    def texto(valor, estilo="normal"):
        return Paragraph(escape(str(valor)), estilos[estilo])

    def faixa(titulo, tamanho=largura):
        return Cartao([[texto(titulo, "secao")]], [tamanho], cor=CLARO, padding=6)

    def tabela_sem_padding(linhas, larguras):
        return Table(linhas, colWidths=larguras, style=TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

    def coluna(itens, tamanho):
        return tabela_sem_padding([[item] for item in itens], [tamanho])

    def indicadores(tamanho, *, em_cartoes):
        espaco = 12
        largura_indicador = (tamanho - espaco * 2) / 3
        celulas = []
        for campo, rotulo, cor in zip(("minima", "media", "maxima"), ("Mínima", "Média", "Máxima"), (MINIMA, colors.black, MAXIMA)):
            valor = _temperatura(dados[campo])
            paragrafo = texto(valor, "valor") if em_cartoes else Paragraph(
                f'<font color="{cor.hexval()}">{escape(valor)}</font>', estilos["valor"])
            itens = [paragrafo, texto(rotulo, "rotulo")]
            celula = Cartao([[item] for item in itens], [largura_indicador], cor=CLARO, sombra=True, padding=5) if em_cartoes else coluna(itens, largura_indicador)
            celulas.extend([celula, ""])
        return tabela_sem_padding([celulas[:-1]], [largura_indicador, espaco, largura_indicador, espaco, largura_indicador])

    def cabecalho(canvas, documento):
        canvas.saveState()
        canvas.setFillColor(AZUL)
        canvas.rect(0, A4[1] - 88, A4[0], 88, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        recorte = canvas.beginPath()
        recorte.moveTo(0, A4[1] - 88)
        recorte.lineTo(45, A4[1] - 88)
        recorte.lineTo(64, A4[1] - 70)
        recorte.lineTo(0, A4[1] - 70)
        recorte.close()
        canvas.drawPath(recorte, stroke=0, fill=1)
        canvas.setFont("Helvetica", 17)
        canvas.drawString(36, A4[1] - 30, "RELATÓRIO DE MONITORAMENTO")
        canvas.setFont("Helvetica-Bold", 17)
        canvas.drawString(36, A4[1] - 51, "SKADI")
        canvas.setFont("Helvetica", 9)
        canvas.drawString(36, A4[1] - 66, f"PERÍODO: {dados['data_inicial']:%d/%m/%Y} - {dados['data_final']:%d/%m/%Y}")
        canvas.restoreState()

    def cabecalho_detalhes(canvas, documento):
        canvas.saveState()
        canvas.setFillColor(AZUL)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(36, A4[1] - 28, "SKADI - DETALHES DO RELATÓRIO")
        canvas.setFont("Helvetica", 9)
        canvas.drawString(36, A4[1] - 42, f"{dados['data_inicial']:%d/%m/%Y} - {dados['data_final']:%d/%m/%Y}")
        canvas.restoreState()

    conteudo = [NextPageTemplate("Detalhes")]
    if dados["dados_simulados"]:
        conteudo.extend([texto("ATENÇÃO: contém dados simulados de teste, não medições reais.", "nota"), Spacer(1, 8)])
    conteudo.extend([faixa("Resumo executivo do período"), Spacer(1, 10)])
    selecao = "Relatório de temperatura - Todas as câmaras" if dados["todas"] else (
        f"{dados['camaras'][0]['modelo']} - {dados['camaras'][0]['localizacao']}")
    resumo = coluna([texto(f"Centro de distribuição: {dados['cd_nome']}", "titulo"),
                      texto(selecao, "nota"), Spacer(1, 7),
                      HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DADADA")), Spacer(1, 8),
                      indicadores(largura - 28, em_cartoes=True)], largura - 28)
    conteudo.extend([Cartao([[resumo]], [largura], sombra=True, padding=14), Spacer(1, 14)])
    largura_bloco = (largura - 16) / 2
    blocos = []
    for titulo, campo, rotulo in (("Alertas no período", "total_alertas", "Alertas"),
                                  ("Ocorrências críticas", "ocorrencias_criticas", "Ocorrências críticas")):
        bloco = coluna([faixa(titulo, largura_bloco), Spacer(1, 8),
                        Cartao([[texto(dados[campo], "quantidade")], [texto(rotulo, "rotulo")]],
                               [largura_bloco], cor=ROSA, padding=6)], largura_bloco)
        blocos.append(bloco)
    conteudo.extend([tabela_sem_padding([[blocos[0], "", blocos[1]]], [largura_bloco, 16, largura_bloco]), Spacer(1, 14),
                     faixa("Gráfico para análise de comportamento"), Spacer(1, 10)])
    if dados["quantidade_leituras"]:
        grafico = coluna([indicadores(largura - 24, em_cartoes=False), Spacer(1, 8),
                          _grafico(dados, largura - 24)], largura - 24)
        conteudo.append(Cartao([[grafico]], [largura], sombra=True, padding=12))
    else:
        conteudo.append(Cartao([[texto("Sem leituras no período.")]], [largura], sombra=True, padding=18))
    conteudo.append(Spacer(1, 10))
    ativas = _camaras_com_leituras(dados)
    for i, c in enumerate(ativas):
        cor = CORES_SERIES[i % len(CORES_SERIES)]
        estilo = "tracejada" if i // len(CORES_SERIES) % 2 else "contínua"
        conteudo.append(Paragraph(f'<font color="{cor}">Série {i + 1} ({estilo}): '
                                 f'{escape(str(c["modelo"]))} - {escape(str(c["localizacao"]))}</font>', estilos["nota"]))
    sem_leituras = [c for c in dados["camaras"] if c not in ativas]
    if sem_leituras:
        conteudo.append(texto(f"Câmaras sem leituras no período: {len(sem_leituras)} de {len(dados['camaras'])}. Identificações nos detalhes.", "nota"))
    conteudo.extend([Spacer(1, 5), texto(f"Leituras: {dados['quantidade_leituras']}. Gerado em: {dados['gerado_em']:%d/%m/%Y %H:%M:%S} (America/Sao_Paulo).", "nota")])
    if dados["quantidade_leituras"]:
        conteudo.append(texto(f"Primeira leitura: {dados['primeira_leitura']:%d/%m/%Y %H:%M:%S}. Última: {dados['ultima_leitura']:%d/%m/%Y %H:%M:%S}.", "nota"))
    conteudo.extend([texto("Registros disponíveis: não comprovam histórico contínuo ou condição atual. Linhas apenas conectam leituras, sem valores medidos entre pontos.", "nota"),
                     PageBreak(), faixa("Câmaras selecionadas e disponibilidade"), Spacer(1, 10)])
    for c in dados["camaras"]:
        disponibilidade = "Sem leituras no período" if c in sem_leituras else "Com leituras no período"
        conteudo.append(texto(f"{c['modelo']} - {c['localizacao']}: {disponibilidade}.", "nota"))
    conteudo.extend([texto("Estatísticas calculadas sobre todas as leituras da seleção, não média das médias. Cadastro e vínculo com termômetros são os atuais.", "nota"),
                     Spacer(1, 14), faixa("Ocorrências do período"), Spacer(1, 10),
                     texto("Inclui todos os status. Status e gravidade são os registrados na consulta, não uma reconstrução de seu estado passado.", "nota"), Spacer(1, 8)])
    if dados["alertas"]:
        camaras = {c["camara_id"]: c for c in dados["camaras"]}
        linhas = [[texto(c, "rotulo") for c in ("Câmara", "Tipo", "Horário", "Gravidade", "Status")]]
        for _id, camara_id, tipo, data, gravidade, status in dados["alertas"]:
            c = camaras[camara_id]
            linhas.append([texto(f"{c['modelo']} - {c['localizacao']}", "nota"), texto(tipo.replace("_", " "), "nota"),
                           texto(data.strftime("%d/%m/%Y %H:%M:%S"), "nota"), texto(gravidade, "nota"), texto(status, "nota")])
        tabela = Table(linhas, colWidths=[largura * p for p in (0.28, 0.23, 0.21, 0.14, 0.14)], repeatRows=1,
                       style=TableStyle([("BACKGROUND", (0, 0), (-1, 0), CLARO),
                                         ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F6FA")]),
                                         ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                         ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        conteudo.append(tabela)
    else:
        conteudo.append(texto("Sem alertas no período."))
    documento = BaseDocTemplate(saida, pagesize=A4, title="Relatório de monitoramento Skadi", author="Skadi")
    documento.addPageTemplates([
        PageTemplate(id="Resumo", frames=[Frame(36, 48, largura, A4[1] - 154, leftPadding=0, rightPadding=0,
                                               topPadding=0, bottomPadding=0)], onPage=cabecalho),
        PageTemplate(id="Detalhes", frames=[Frame(36, 48, largura, A4[1] - 106, leftPadding=0, rightPadding=0,
                                                 topPadding=0, bottomPadding=0)], onPage=cabecalho_detalhes),
    ])
    documento.build(conteudo, canvasmaker=partial(CanvasPaginado, ano=dados["gerado_em"].year))
    return saida.getvalue()
