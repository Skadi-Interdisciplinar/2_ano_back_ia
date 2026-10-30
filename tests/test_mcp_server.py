import asyncio
from unittest.mock import Mock

import pytest
from app import mcp_server
from app.auth import AuthenticatedUser
from app.tools.contexto import (
    definir_usuario_contexto,
    obter_usuario_contexto,
    restaurar_usuario_contexto,
)
from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError
from psycopg2 import OperationalError


def test_listagem_mcp_declara_apenas_consultas_sem_identidade_nos_argumentos():
    ferramentas = asyncio.run(mcp_server.mcp.list_tools())

    assert {f.name for f in ferramentas} == {
        "listar_camaras_responsaveis", "consultar_temperaturas", "consultar_alertas_atuais_do_usuario",
    }
    for ferramenta in ferramentas:
        assert ferramenta.annotations.read_only_hint is True
        assert not {"usuario_id", "token", "nivel_acesso"}.intersection(ferramenta.input_schema.get("properties", {}))


def test_mcp_reutiliza_tool_com_usuario_do_jwt_e_restaura_contexto(monkeypatch):
    monkeypatch.setattr(mcp_server.config, "TRIMMY_MCP_TOKEN", "jwt-ficticio")
    autenticar = Mock(return_value=AuthenticatedUser(12))
    monkeypatch.setattr(mcp_server, "obter_usuario_autenticado", autenticar)
    ferramenta = Mock()
    ferramenta.invoke.side_effect = lambda argumentos: {"usuario": obter_usuario_contexto()}
    monkeypatch.setattr(mcp_server, "_listar_camaras", ferramenta)
    contexto = definir_usuario_contexto(99)
    try:
        resposta = mcp_server.listar_camaras_responsaveis(localizacao="Setor Carnes")

        assert resposta == {"usuario": 12}
        autenticar.assert_called_once_with("jwt-ficticio")
        ferramenta.invoke.assert_called_once_with({"camara_id": None, "modelo": None, "localizacao": "Setor Carnes"})
        assert obter_usuario_contexto() == 99
    finally:
        restaurar_usuario_contexto(contexto)


def test_mcp_sem_jwt_nao_consulta_dados(monkeypatch):
    monkeypatch.setattr(mcp_server.config, "TRIMMY_MCP_TOKEN", None)
    autenticar = Mock()
    monkeypatch.setattr(mcp_server, "obter_usuario_autenticado", autenticar)

    with pytest.raises(ToolError, match="TRIMMY_MCP_TOKEN"):
        mcp_server.consultar_alertas_atuais_do_usuario()

    autenticar.assert_not_called()


def test_mcp_token_expirado_nao_executa_tool(monkeypatch):
    monkeypatch.setattr(mcp_server.config, "TRIMMY_MCP_TOKEN", "jwt-expirado")
    monkeypatch.setattr(mcp_server, "obter_usuario_autenticado", Mock(side_effect=HTTPException(401, "Sessão expirada.")))
    ferramenta = Mock()
    monkeypatch.setattr(mcp_server, "_consultar_alertas", ferramenta)

    with pytest.raises(ToolError, match="Sessão expirada"):
        mcp_server.consultar_alertas_atuais_do_usuario()

    ferramenta.invoke.assert_not_called()


@pytest.mark.parametrize("falha,mensagem", [
    (PermissionError("dado privado"), "Consulta não permitida"),
    (OperationalError("senha interna"), "Não foi possível consultar"),
    (ValueError("detalhe interno"), "Filtros inválidos"),
])
def test_mcp_falha_sem_expor_detalhes_e_remove_contexto(monkeypatch, falha, mensagem):
    monkeypatch.setattr(mcp_server.config, "TRIMMY_MCP_TOKEN", "jwt-ficticio")
    monkeypatch.setattr(mcp_server, "obter_usuario_autenticado", Mock(return_value=AuthenticatedUser(12)))
    ferramenta = Mock()
    ferramenta.invoke.side_effect = falha
    monkeypatch.setattr(mcp_server, "_consultar_temperaturas", ferramenta)

    with pytest.raises(ToolError, match=mensagem) as erro:
        mcp_server.consultar_temperaturas(camara_id=3)

    assert str(falha) not in str(erro.value)
    with pytest.raises(RuntimeError, match="autenticado"):
        obter_usuario_contexto()
