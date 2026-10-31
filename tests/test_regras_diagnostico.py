from app.regras_diagnostico import carregar_regras


def test_carrega_apenas_regras_aprovadas_e_ativas():
    regras = carregar_regras()

    assert regras
    assert all(regra.status == "APROVADA" and regra.ativa for regra in regras.values())


def test_cada_regra_tem_fonte_e_limitacao():
    regra = next(iter(carregar_regras().values()))

    assert regra.fontes
    assert regra.limitacoes
