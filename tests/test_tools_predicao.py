import pytest
from app import predicao
from app.tools import predicao as tools
from app.tools.access import EscopoAcesso
from pydantic import ValidationError
from tests.test_modelos_predicao import leituras, treinar


@pytest.mark.parametrize("nivel", ["SUPER_ADMIN", "ADMIN", "GESTOR"])
def test_perfis_autorizados_usam_apenas_camara_permitida(contexto, monkeypatch, nivel):
    predicao.validar_acesso.return_value = EscopoAcesso(2, nivel, None if nivel == "SUPER_ADMIN" else 7)
    resposta = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    assert resposta["status"] == "ok"
    assert resposta["temperatura_prevista"] == 4
    assert resposta["comparacao"] == "dentro_faixa"
    assert resposta["referencia"] in contexto.resultados
    tools.consultar_camaras_permitidas.assert_called_once_with(2, 3, None, None)
    assert "camara_id" not in resposta["camara"]


@pytest.mark.parametrize("nivel,cd", [("OPERADOR", 7), ("ADMIN", None), ("VISITANTE", 7)])
def test_acesso_negado_antes_de_consulta_ou_modelo(contexto, nivel, cd):
    predicao.validar_acesso.return_value = EscopoAcesso(2, nivel, cd)
    with pytest.raises(PermissionError):
        tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    tools.consultar_camaras_permitidas.assert_not_called()
    tools.carregar_modelo.assert_not_called()


@pytest.mark.parametrize("camaras", [[], [{"modelo": "A", "localizacao": "1"}] * 2])
def test_camara_nao_encontrada_ou_ambigua_nao_amplia_busca(contexto, camaras):
    tools.consultar_camaras_permitidas.return_value = camaras
    resposta = tools.prever_temperatura.invoke({"modelo": "A", "horizonte_minutos": 1})
    assert resposta["status"] == "esclarecimento"
    tools.carregar_modelo.assert_not_called()
    tools.consultar_serie.assert_not_called()


def test_sem_identificacao_nao_lista_camaras(contexto):
    assert tools.prever_temperatura.invoke({"horizonte_minutos": 1})["status"] == "esclarecimento"
    tools.consultar_camaras_permitidas.assert_not_called()


def test_sem_horizonte_nao_inventa_padrao(contexto):
    resposta = tools.prever_temperatura.invoke({"camara_id": 3})
    assert "quantos minutos" in resposta["mensagem"]
    tools.carregar_modelo.assert_not_called()


@pytest.mark.parametrize("alteracao", ["ausente", "pendente", "outro_sensor", "horizonte"])
def test_modelo_ou_horizonte_indisponivel_nao_calcula(contexto, alteracao):
    if alteracao == "ausente":
        tools.carregar_modelo.return_value = None
    elif alteracao == "pendente":
        tools.carregar_modelo.return_value = treinar([4] * 20)
    elif alteracao == "outro_sensor":
        tools.carregar_modelo.return_value.termometro_id = 99
    resposta = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 2 if alteracao == "horizonte" else 1})
    assert resposta["status"] != "ok"
    tools.consultar_serie.assert_not_called()


@pytest.mark.parametrize("linhas", [[], [(4, None)], leituras([float("nan"), 4]), leituras([4])])
def test_dados_invalidos_nao_geram_valores(contexto, linhas):
    tools.consultar_serie.return_value = linhas
    resposta = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    assert resposta["status"] == "dados_invalidos"
    assert resposta["temperatura_prevista"] is None


@pytest.mark.parametrize("temperatura,comparacao", [(1, "abaixo_minimo"), (8, "acima_maximo"), (2, "dentro_faixa"), (6, "dentro_faixa")])
def test_compara_apenas_com_faixa_cadastrada(contexto, temperatura, comparacao):
    tools.carregar_modelo.return_value.intercepto = temperatura
    resposta = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    assert resposta["comparacao"] == comparacao


def test_resultado_do_modelo_nao_altera_snapshot(contexto):
    resposta = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    resposta["temperatura_prevista"] = 999
    assert contexto.resultados[resposta["referencia"]].temperatura_prevista == 4


@pytest.mark.parametrize("dados", [{"usuario_id": 9}, {"aprovado": True}, {"horizonte_minutos": 0}, {"horizonte_minutos": True}])
def test_schema_nao_aceita_permissoes_nem_horizonte_invalido(contexto, dados):
    with pytest.raises(ValidationError):
        tools.prever_temperatura.invoke(dados)


def test_so_existe_uma_tool():
    assert [t.name for t in tools.TOOLS] == ["prever_temperatura"]


def test_outra_camara_fora_do_cd_nao_revela_modelo(contexto):
    tools.consultar_camaras_permitidas.side_effect = PermissionError("Acesso negado")
    with pytest.raises(PermissionError):
        tools.prever_temperatura.invoke({"camara_id": 99, "horizonte_minutos": 1})
    tools.carregar_modelo.assert_not_called()
    tools.consultar_serie.assert_not_called()


def test_leitura_anterior_ao_ajuste_nao_usa_conhecimento_futuro(contexto):
    tools.consultar_serie.return_value = leituras([4, 4])
    resposta = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    assert resposta["status"] == "dados_invalidos"


@pytest.mark.parametrize("campo,valor", [("limite_minimo", "NaN"), ("limite_maximo", "abc"), ("limite_minimo", "10")])
def test_limites_invalidos_nao_sustentam_comparacao(contexto, campo, valor):
    tools.consultar_camaras_permitidas.return_value[0][campo] = valor
    resposta = tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    assert resposta["status"] == "dados_invalidos"


def test_postgres_indisponivel_nao_vira_resultado_sem_leitura(contexto):
    from psycopg2 import OperationalError

    tools.consultar_serie.side_effect = OperationalError("Falha de conexão")
    with pytest.raises(OperationalError):
        tools.prever_temperatura.invoke({"camara_id": 3, "horizonte_minutos": 1})
    assert contexto.resultados == {}
