from unittest.mock import Mock

import pytest
from app import diagnostico as dominio
from app.diagnostico import ContextoDiagnostico
from app.regras_diagnostico import carregar_regras
from app.tools import diagnostico, monitoramento
from app.tools.access import EscopoAcesso
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from pydantic import ValidationError
from tests.conftest import banco_sql


@pytest.fixture
def contexto(monkeypatch):
    usuario = definir_usuario_contexto(2)
    contexto = ContextoDiagnostico(2)
    token = dominio.contexto_diagnostico.set(contexto)
    monkeypatch.setattr(diagnostico, "validar_acesso", Mock(return_value=EscopoAcesso(2, "ADMIN", 2)))
    monkeypatch.setattr(diagnostico, "consultar_camaras_permitidas", Mock(return_value=[{
        "camara_id": 3, "modelo": "A", "localizacao": "Setor 1", "termometro": 9,
        "limite_minimo": "2", "limite_maximo": "6",
    }]))
    monkeypatch.setattr(diagnostico, "consultar_alertas_permitidos", Mock(return_value=[]))
    monkeypatch.setattr(diagnostico, "_ultimas_leituras_permitidas", Mock(return_value={
        "9": {"temperatura": "8", "data_hora": "2026-10-11T10:00:00"},
    }))
    yield contexto
    dominio.contexto_diagnostico.reset(token)
    restaurar_usuario_contexto(usuario)


def alerta(id=1):
    return {
        "alerta_id": id, "camara_id": 3, "camara": "A — Setor 1",
        "tipo": "TEMPERATURA_FORA_PADRAO", "status": "ATIVO", "gravidade": "URGENTE",
        "data_hora": "2026-10-11T09:00:00",
    }


def test_evidencias_sem_alerta_nao_inventa_justificativa(contexto, monkeypatch):
    banco = Mock()
    monkeypatch.setattr(diagnostico, "get_conn", banco)

    resultado = diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})

    assert resultado["status"] == "ok"
    assert resultado["alerta"] is None
    assert resultado["justificativas"] == []
    assert resultado["leitura"]["temperatura"] == "8"
    assert resultado["referencia"] in contexto.evidencias
    assert "_camara_id" not in resultado
    diagnostico.consultar_camaras_permitidas.assert_called_once_with(2, 3, None, None)
    banco.assert_not_called()


@pytest.mark.parametrize("camaras,status", [
    ([], "nao_encontrada"),
    ([{"modelo": "A", "localizacao": "1", "limite_minimo": "2", "limite_maximo": "6"}] * 2, "camara_ambigua"),
])
def test_camara_invalida_nao_consulta_leituras_ou_alertas(contexto, monkeypatch, camaras, status):
    diagnostico.consultar_camaras_permitidas.return_value = camaras

    resultado = diagnostico.consultar_evidencias_diagnostico.invoke({"modelo": "A"})

    assert resultado["status"] == status
    diagnostico._ultimas_leituras_permitidas.assert_not_called()
    diagnostico.consultar_alertas_permitidos.assert_not_called()


def test_sem_identificacao_nao_lista_todas(contexto):
    resultado = diagnostico.consultar_evidencias_diagnostico.invoke({})

    assert resultado["status"] == "identificacao_necessaria"
    diagnostico.consultar_camaras_permitidas.assert_not_called()


def test_alerta_ambiguo_pede_escolha_e_nao_busca_justificativa(contexto, monkeypatch):
    diagnostico.consultar_alertas_permitidos.return_value = [alerta(1), alerta(2)]
    banco = Mock()
    monkeypatch.setattr(diagnostico, "get_conn", banco)

    resultado = diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})

    assert resultado["status"] == "alerta_ambiguo"
    assert len(resultado["opcoes"]) == 2
    banco.assert_not_called()
    diagnostico._ultimas_leituras_permitidas.assert_not_called()


def test_consulta_justificativa_vinculada_antes_da_resposta(contexto, monkeypatch):
    diagnostico.consultar_alertas_permitidos.return_value = [alerta()]
    cursor, conexao = banco_sql(retornos=[(
        4, "Porta", "A porta não fecha nesta ocorrência.", "2026-10-11T09:10:00",
    )])
    monkeypatch.setattr(diagnostico, "get_conn", Mock(return_value=conexao))

    resultado = diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})

    assert resultado["status"] == "ok"
    justificativa = resultado["justificativas"][0]
    assert justificativa["descricao"] == "A porta não fecha nesta ocorrência."
    assert justificativa["origem_ref"] in contexto.fontes
    assert cursor.execute.call_args.args[1] == (1, 3)
    sql = cursor.execute.call_args.args[0]
    assert "j.cod_atendimento" in sql
    assert "atendimento.cod_alerta" in sql
    diagnostico.consultar_alertas_permitidos.assert_called_with(2, 3, 1)
    conexao.close.assert_called_once()


def test_alerta_so_pode_ser_escolhido_de_consulta_desta_execucao(contexto):
    diagnostico.consultar_alertas_permitidos.return_value = [alerta()]

    with pytest.raises(PermissionError):
        diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3, "alerta_id": 1})


def test_escolha_de_alerta_reconsulta_autorizacao(contexto, monkeypatch):
    diagnostico.consultar_alertas_permitidos.return_value = [alerta(1), alerta(2)]
    diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})
    diagnostico.consultar_alertas_permitidos.return_value = [alerta(1), alerta(2)]
    cursor, conexao = banco_sql()
    monkeypatch.setattr(diagnostico, "get_conn", Mock(return_value=conexao))

    resultado = diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3, "alerta_id": 2})

    assert resultado["status"] == "ok"
    assert cursor.execute.call_args.args[1] == (2, 3)


def test_alerta_de_outra_camara_nao_e_seletor_valido(contexto):
    contexto.evidencias["outra"] = {"_camara_id": 8, "_alertas": [alerta(1)]}

    with pytest.raises(PermissionError):
        diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3, "alerta_id": 1})


@pytest.mark.parametrize("nivel", ["SUPER_ADMIN", "ADMIN", "GESTOR", "OPERADOR"])
def test_quatro_perfis_recuperam_regras_apos_consulta(contexto, monkeypatch, nivel):
    diagnostico.validar_acesso.return_value = EscopoAcesso(2, nivel, None if nivel == "SUPER_ADMIN" else 2)
    diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})
    regra = carregar_regras()["DIAG-TEC-001"]
    recuperar = Mock(return_value=[regra])
    monkeypatch.setattr(diagnostico, "recuperar_regras", recuperar)

    resultado = diagnostico.buscar_regras_diagnostico.invoke({"busca": "porta"})

    assert resultado == [regra.model_dump()]
    assert contexto.regras == {regra.id: regra}
    recuperar.assert_called_once_with("porta")


@pytest.mark.parametrize("nivel", ["SUPER_ADMIN", "ADMIN", "GESTOR", "OPERADOR"])
def test_regras_gerais_nao_exigem_camara_nem_consultam_dados_operacionais(contexto, monkeypatch, nivel):
    diagnostico.validar_acesso.return_value = EscopoAcesso(2, nivel, None if nivel == "SUPER_ADMIN" else 2)
    regra = carregar_regras()["DIAG-TEC-001"]
    recuperar = Mock(return_value=[regra])
    monkeypatch.setattr(diagnostico, "recuperar_regras", recuperar)

    assert diagnostico.buscar_regras_diagnostico.invoke({"busca": "porta"}) == [regra.model_dump()]

    recuperar.assert_called_once_with("porta")
    diagnostico.validar_acesso.assert_called_once_with(2)
    diagnostico.consultar_camaras_permitidas.assert_not_called()
    diagnostico.consultar_alertas_permitidos.assert_not_called()
    diagnostico._ultimas_leituras_permitidas.assert_not_called()
    assert contexto.evidencias == {}
    assert contexto.regras_consultadas is True


def test_busca_geral_sem_resultado_registra_consulta(contexto, monkeypatch):
    monkeypatch.setattr(diagnostico, "recuperar_regras", Mock(return_value=[]))

    assert diagnostico.buscar_regras_diagnostico.invoke({"busca": "assunto"}) == []
    assert contexto.regras_consultadas is True
    assert contexto.regras == {}


def test_perfil_sem_cd_nao_recupera_regras(contexto, monkeypatch):
    diagnostico.validar_acesso.return_value = EscopoAcesso(2, "OPERADOR", None)
    recuperar = Mock()
    monkeypatch.setattr(diagnostico, "recuperar_regras", recuperar)

    with pytest.raises(PermissionError):
        diagnostico.buscar_regras_diagnostico.invoke({"busca": "porta"})

    recuperar.assert_not_called()


def test_tool_recusa_usuario_e_permissoes_do_modelo(contexto):
    with pytest.raises(ValidationError):
        diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3, "usuario_id": 1})
    with pytest.raises(ValidationError):
        diagnostico.buscar_regras_diagnostico.invoke({"busca": "porta", "aprovado": True})


def test_falha_redis_interrompe_sem_evidencia_registrada(contexto):
    diagnostico._ultimas_leituras_permitidas.side_effect = RuntimeError("Redis indisponível")

    with pytest.raises(RuntimeError, match="Redis"):
        diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})

    assert contexto.evidencias == {}


def test_falha_postgres_nao_e_ausencia_de_camara(contexto):
    diagnostico.consultar_camaras_permitidas.side_effect = RuntimeError("Banco indisponível")

    with pytest.raises(RuntimeError, match="Banco"):
        diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})


def test_falha_qdrant_nao_e_lista_vazia(contexto, monkeypatch):
    diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})
    monkeypatch.setattr(diagnostico, "recuperar_regras", Mock(side_effect=RuntimeError("Qdrant indisponível")))

    with pytest.raises(RuntimeError, match="Qdrant"):
        diagnostico.buscar_regras_diagnostico.invoke({"busca": "porta"})


@pytest.mark.parametrize("nivel,cd,parametros", [
    ("SUPER_ADMIN", None, ["ATIVO", "RECONHECIDO", 2, 3, 1]),
    ("ADMIN", 7, ["ATIVO", "RECONHECIDO", 2, 7, 3, 1]),
    ("GESTOR", 7, ["ATIVO", "RECONHECIDO", 2, 7, 3, 1]),
    ("OPERADOR", 7, ["ATIVO", "RECONHECIDO", 2, 7, "OPERADOR", 3, 1]),
])
def test_consulta_comum_preserva_todos_filtros(monkeypatch, nivel, cd, parametros):
    cursor, conexao = banco_sql()
    monkeypatch.setattr(monitoramento, "get_conn", Mock(return_value=conexao))
    monkeypatch.setattr(monitoramento, "validar_acesso", Mock(return_value=EscopoAcesso(2, nivel, cd)))

    assert monitoramento.consultar_alertas_permitidos(2, 3, 1) == []

    sql, recebidos = cursor.execute.call_args.args
    assert recebidos == parametros
    assert "atendimento.cod_usuario = %s" in sql
    assert "a.cod_camara_frigorifica = %s" in sql
    assert "a.id = %s" in sql
    assert ("a.nivel_atual = %s" in sql) == (nivel == "OPERADOR")


def test_tool_nao_funciona_sem_contexto_de_diagnostico():
    usuario = definir_usuario_contexto(2)
    try:
        with pytest.raises(PermissionError):
            diagnostico.consultar_evidencias_diagnostico.invoke({"camara_id": 3})
    finally:
        restaurar_usuario_contexto(usuario)


def test_existem_apenas_duas_tools_de_diagnostico():
    assert [t.name for t in diagnostico.TOOLS] == [
        "consultar_evidencias_diagnostico", "buscar_regras_diagnostico",
    ]

