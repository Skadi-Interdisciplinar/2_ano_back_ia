from app.diagnostico import RelatoDiagnostico, _relato_descreve_requisito
from app.regras_diagnostico import carregar_regras


def test_carrega_apenas_regras_aprovadas_e_ativas():
    regras = carregar_regras()

    assert regras
    assert all(regra.status == "APROVADA" and regra.ativa for regra in regras.values())


def test_cada_regra_tem_fonte_e_limitacao():
    regra = next(iter(carregar_regras().values()))

    assert regra.fontes
    assert regra.limitacoes


def test_regra_de_porta_inclui_relato_de_porta_aberta():
    regra = carregar_regras()["DIAG-TEC-001"]
    relato = RelatoDiagnostico(
        origem_ref="mensagem:1",
        requisito="porta_aberta",
        trecho="A porta ficou aberta durante a operação.",
        situacao="afirmado",
        vinculo_confirmado=True,
        atualidade_confirmada=True,
    )

    assert regra.versao == "0.4"
    assert "porta_aberta" in regra.grupos_requisitos[0]
    assert _relato_descreve_requisito(relato) is True
