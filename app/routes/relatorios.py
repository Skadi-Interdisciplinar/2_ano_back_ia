"""Download por botão do mobile; não participa do grafo conversacional."""

import logging

from app.auth import obter_usuario_autenticado
from app.erros import SaidaModeloInvalida, ServicoIndisponivel
from app.relatorios import (
    DadosRelatorioInvalidos,
    FiltroRelatorioInvalido,
    SelecaoRelatorioNaoEncontrada,
    gerar_relatorio_pdf,
)
from app.schemas import RelatorioRequest
from fastapi import APIRouter, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from psycopg2 import Error as PostgreSQLError

logger = logging.getLogger(__name__)


class RotaRelatorio(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validar_sem_expor_corpo(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Confira o token, os IDs e as datas do relatório. Use datas no formato AAAA-MM-DD, com a data inicial anterior ou igual à final."})

        return validar_sem_expor_corpo


router = APIRouter(tags=["relatorios"], route_class=RotaRelatorio)


@router.post(
    "/relatorios/pdf", response_class=Response,
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
        403: {"description": "Acesso não permitido."},
        404: {"description": "Seleção não encontrada no escopo permitido."},
        409: {"description": "Dados de origem inconsistentes."},
        422: {"description": "Filtros inválidos."},
        500: {"description": "Falha de geração do PDF."},
        502: {"description": "Relatório reprovado ou veredito inválido."},
        503: {"description": "Banco de dados indisponível."},
    },
)
def baixar_relatorio(requisicao: RelatorioRequest) -> Response:
    try:
        usuario = obter_usuario_autenticado(requisicao.token)
        pdf = gerar_relatorio_pdf(usuario.usuario_id, requisicao)
    except PermissionError:
        raise HTTPException(403, "Não foi possível autorizar o relatório. Confira o cadastro do usuário e selecione somente o CD vinculado a ele.") from None
    except SelecaoRelatorioNaoEncontrada:
        raise HTTPException(404, "Nenhuma câmara foi encontrada na seleção permitida. Confira o CD e a câmara informados.") from None
    except FiltroRelatorioInvalido as erro:
        raise HTTPException(422, str(erro)) from None
    except DadosRelatorioInvalidos:
        raise HTTPException(409, "O período contém leituras com temperatura ou horário inválidos. Corrija os registros de origem antes de gerar o relatório.") from None
    except SaidaModeloInvalida:
        raise HTTPException(502, "O relatório não passou pela conferência de conteúdo e apresentação ou o juiz devolveu uma avaliação inválida. O arquivo não foi disponibilizado.") from None
    except ServicoIndisponivel:
        raise HTTPException(503, "O serviço que confere o relatório está indisponível. Isso pode ocorrer por limite de uso do provedor ou falha de conexão. Aguarde e tente novamente; o PDF ainda não foi disponibilizado.") from None
    except PostgreSQLError:
        raise HTTPException(503, "Não foi possível consultar ou registrar o relatório no PostgreSQL. Confira a conexão com o banco e tente novamente.") from None
    except Exception as erro:  # noqa: BLE001 - Fronteira HTTP: não expor erros internos do renderizador.
        logger.error("Falha ao gerar relatório: %s", type(erro).__name__)
        raise HTTPException(500, "Ocorreu uma falha inesperada ao montar o PDF. O arquivo não foi disponibilizado. Consulte o log do servidor para investigar.") from None
    nome = f"skadi-relatorio-{requisicao.data_inicial.isoformat()}-{requisicao.data_final.isoformat()}.pdf"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{nome}"', "Cache-Control": "no-store",
    })
