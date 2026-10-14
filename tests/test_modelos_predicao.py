from datetime import UTC, datetime, timedelta

import pytest
from app import modelos_predicao as modelos
from app.erros import ServicoIndisponivel


def leituras(valores):
    inicio = datetime(2026, 10, 12, tzinfo=UTC)
    return [(v, inicio + timedelta(minutes=i)) for i, v in enumerate(valores)]


def treinar(valores, horizontes=None):
    return modelos.treinar_modelo(
        leituras(valores), camara_id=3, termometro_id=9, cadencia_segundos=60,
        inicio_coleta=datetime(2026, 10, 12, tzinfo=UTC), horizontes_minutos=horizontes or [1],
    )


@pytest.mark.parametrize("valores", [list(range(20)), list(range(20, 0, -1)), [4] * 20])
def test_ajuste_e_metricas_para_series_basicas(valores):
    modelo = treinar(valores, [1, 2])

    assert modelo.status == "EM_REVISAO"
    assert modelo.leituras_treino == 16
    assert modelo.leituras_avaliacao == 4
    assert modelo.fim_treino < modelo.inicio_avaliacao
    assert [m.casos for m in modelo.metricas] == [4, 3]
    assert all(m.mae == pytest.approx(0) for m in modelo.metricas)
    assert all(m.rmse == pytest.approx(0) for m in modelo.metricas)
    assert modelo.metricas[0].mae_referencia == (0 if len(set(valores)) == 1 else 1)


def test_avaliacao_nao_alimenta_ajuste():
    a = treinar(list(range(20)))
    b = treinar(list(range(16)) + [100, 80, 50, 20])

    assert (a.intercepto, a.coeficiente) == (b.intercepto, b.coeficiente)
    assert b.metricas[0].mae > a.metricas[0].mae


def test_horizonte_sem_caso_posterior_ao_treino_nao_gera_modelo():
    with pytest.raises(ValueError, match="casos observados"):
        treinar(list(range(20)), [5])


@pytest.mark.parametrize("valores", [[], [1], [1, 2, 3]])
def test_dados_insuficientes(valores):
    with pytest.raises(ValueError, match="insuficientes"):
        treinar(valores)


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), "abc", None, True])
def test_valor_invalido(valor):
    with pytest.raises((ValueError, TypeError)):
        treinar([valor] * 20)


def test_lacuna_nao_e_interpolada():
    linhas = leituras(list(range(20)))
    linhas.pop(5)
    with pytest.raises(ValueError, match="lacunas"):
        modelos.preparar_serie(linhas, 60, linhas[0][1])


def test_duplicata_identica_e_deduplicada_mas_conflito_e_rejeitado():
    linhas = leituras([2, 3, 4])
    assert len(modelos.preparar_serie(linhas + [linhas[0]], 60, linhas[0][1])) == 3
    with pytest.raises(ValueError, match="conflitantes"):
        modelos.preparar_serie(linhas + [(99, linhas[0][1])], 60, linhas[0][1])


def test_horario_ausente_e_dados_anteriores_a_coleta():
    with pytest.raises((ValueError, TypeError)):
        modelos.preparar_serie([(4, None)], 60, datetime.now(UTC))
    linhas = leituras([2, 3])
    with pytest.raises(ValueError, match="anterior"):
        modelos.preparar_serie(linhas, 60, linhas[1][1])


@pytest.mark.parametrize("horizontes", [[0], [-1], [1, 1]])
def test_horizonte_invalido(horizontes):
    with pytest.raises(ValueError):
        treinar(list(range(20)), horizontes)


def test_horizonte_incompativel_com_cadencia():
    linhas = [(v, datetime(2026, 10, 12, tzinfo=UTC) + timedelta(seconds=90 * i)) for i, v in enumerate(range(20))]
    with pytest.raises(ValueError, match="cadência"):
        modelos.treinar_modelo(linhas, camara_id=3, termometro_id=9, cadencia_segundos=90,
                               inicio_coleta=linhas[0][1], horizontes_minutos=[1])


def test_serializacao_pendente_nao_substitui_aprovado(tmp_path, monkeypatch):
    monkeypatch.setattr(modelos, "PASTA_MODELOS", tmp_path)
    modelo = treinar(list(range(20)))
    modelos.salvar_modelo(modelo)
    assert modelos.carregar_modelo(3) is None
    assert modelos.carregar_modelo(3, pendente=True) == modelo
    aprovado = modelo.model_copy(update={"status": "APROVADO", "aprovado_em": datetime.now(UTC)})
    modelos.salvar_modelo(aprovado)
    modelos.salvar_modelo(treinar([4] * 20))
    assert modelos.carregar_modelo(3) == aprovado


def test_artefato_invalido_nao_vira_ausencia(tmp_path, monkeypatch):
    monkeypatch.setattr(modelos, "PASTA_MODELOS", tmp_path)
    (tmp_path / "camara_3.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ServicoIndisponivel):
        modelos.carregar_modelo(3)


def test_artefato_de_outra_camara_e_rejeitado(tmp_path, monkeypatch):
    monkeypatch.setattr(modelos, "PASTA_MODELOS", tmp_path)
    modelo = treinar([4] * 20)
    (tmp_path / "camara_4.json").write_text(modelo.model_dump_json(), encoding="utf-8")
    with pytest.raises(ServicoIndisponivel):
        modelos.carregar_modelo(4)


def test_fuso_corresponde_ao_worker():
    assert modelos.momento("2026-10-12T08:00:00").hour == 11


def test_projecao_nao_finita_e_rejeitada():
    with pytest.raises(ValueError):
        modelos.estimar(0, 1e308, 1e308, 2)
