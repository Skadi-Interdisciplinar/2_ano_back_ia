"""Relatórios determinísticos: snapshot PostgreSQL, cálculos e auditoria."""

from contextlib import closing
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from app.schemas import RelatorioRequest
from app.tools.access import validar_acesso
from app.tools.db import get_conn
from app.tools.monitoramento import FiltrosCamaraArgs, _selecionar_camaras


class FiltroRelatorioInvalido(ValueError):
    pass


class SelecaoRelatorioNaoEncontrada(LookupError):
    pass


class DadosRelatorioInvalidos(ValueError):
    pass


def _cd_permitido(escopo, cd_id: int | None) -> int:
    if escopo.nivel_acesso == "SUPER_ADMIN":
        if cd_id is None:
            raise FiltroRelatorioInvalido("Informe o CD para gerar o relatório.")
        return cd_id
    if escopo.nivel_acesso != "GESTOR" or escopo.cd_id is None:
        raise PermissionError("Perfil sem acesso aos relatórios.")
    if cd_id is not None and cd_id != escopo.cd_id:
        raise PermissionError("CD não permitido.")
    return escopo.cd_id


def consultar_dados_relatorio(usuario_id: int, filtros: RelatorioRequest) -> dict:
    """Datas sem fuso no banco seguem a convenção America/Sao_Paulo do produtor."""
    inicio = datetime.combine(filtros.data_inicial, time.min)
    fim = datetime.combine(filtros.data_final + timedelta(days=1), time.min)
    with closing(get_conn()) as conexao:
        conexao.set_session(isolation_level="REPEATABLE READ", readonly=True)
        with conexao.cursor() as cursor:
            escopo = validar_acesso(usuario_id, cursor=cursor)
            cd_id = _cd_permitido(escopo, filtros.cd_id)
            cursor.execute("SELECT nome FROM tb_cd WHERE id = %s", (cd_id,))
            cd = cursor.fetchone()
            if cd is None:
                raise SelecaoRelatorioNaoEncontrada("Seleção não encontrada no escopo permitido.")
            camaras = _selecionar_camaras(
                escopo, FiltrosCamaraArgs(camara_id=filtros.camara_id), cursor=cursor,
                cd_id=cd_id if escopo.nivel_acesso == "SUPER_ADMIN" else None,
            )
            if not camaras:
                raise SelecaoRelatorioNaoEncontrada("Seleção não encontrada no escopo permitido.")
            cursor.execute(
                "SELECT cod_termometro, temperatura, data_hora, id_evento_redis "
                "FROM tb_leitura_temperatura WHERE cod_termometro = ANY(%s) "
                "AND data_hora >= %s AND data_hora < %s ORDER BY data_hora, id",
                ([c["termometro"] for c in camaras], inicio, fim),
            )
            leituras = cursor.fetchall()
            cursor.execute(
                "SELECT id, cod_camara_frigorifica, tipo, data_hora, nivel_gravidade, status "
                "FROM tb_alerta WHERE cod_camara_frigorifica = ANY(%s) "
                "AND data_hora >= %s AND data_hora < %s ORDER BY data_hora DESC, id DESC",
                ([c["camara_id"] for c in camaras], inicio, fim),
            )
            alertas = cursor.fetchall()
            cursor.execute("SELECT CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'")
            gerado_em = cursor.fetchone()[0]
    # O PDF é renderizado apenas depois de fechar a transação de leitura.
    valores = []
    for sensor, valor, horario, evento in leituras:
        try:
            temperatura = Decimal(str(valor))
        except (InvalidOperation, ValueError):
            raise DadosRelatorioInvalidos("Há leituras inválidas no período.") from None
        if (not temperatura.is_finite() or not isinstance(horario, datetime)
                or horario.tzinfo is not None or not inicio <= horario < fim):
            raise DadosRelatorioInvalidos("Há leituras inválidas no período.")
        valores.append(temperatura)
    return {
        "cd_id": cd_id, "cd_nome": cd[0], "camaras": camaras,
        "todas": filtros.camara_id is None,
        "data_inicial": filtros.data_inicial, "data_final": filtros.data_final,
        "gerado_em": gerado_em, "leituras": leituras, "alertas": alertas,
        "quantidade_leituras": len(valores),
        "minima": min(valores) if valores else None,
        "media": sum(valores) / len(valores) if valores else None,
        "maxima": max(valores) if valores else None,
        "primeira_leitura": min(l[2] for l in leituras) if leituras else None,
        "ultima_leitura": max(l[2] for l in leituras) if leituras else None,
        "total_alertas": len(alertas),
        "ocorrencias_criticas": sum(a[4] == "CRITICA" for a in alertas),
    }


def registrar_relatorio(usuario_id: int, dados: dict, pdf: bytes) -> None:
    """Registra disponibilização, não comprova recebimento ou salvamento no mobile."""
    with closing(get_conn()) as conexao:
        try:
            with conexao.cursor() as cursor:
                # A renderização não mantém transação aberta; reconferir o acesso.
                _cd_permitido(validar_acesso(usuario_id, cursor=cursor), dados["cd_id"])
                cursor.execute(
                    "INSERT INTO tb_relatorio "
                    "(cod_usuario_gerador, periodo_inicio, periodo_fim, hash_conteudo, status) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (usuario_id, dados["data_inicial"], dados["data_final"], sha256(pdf).hexdigest(), "GERADO"),
                )
                relatorio_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO tb_log_acesso_relatorio (cod_relatorio, cod_usuario, acao) "
                    "VALUES (%s, %s, %s)",
                    (relatorio_id, usuario_id, "BAIXOU"),
                )
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise


def gerar_relatorio_pdf(usuario_id: int, filtros: RelatorioRequest) -> bytes:
    from app.pdf_relatorio import renderizar_pdf

    dados = consultar_dados_relatorio(usuario_id, filtros)
    pdf = renderizar_pdf(dados)
    registrar_relatorio(usuario_id, dados, pdf)
    return pdf
