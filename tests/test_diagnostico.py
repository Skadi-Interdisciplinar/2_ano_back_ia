from unittest.mock import Mock, patch

import pytest
from app import diagnostico, graph
from app.diagnostico import (
    ContextoDiagnostico,
    PropostaDiagnostico,
    RelatoDiagnostico,
    SaidaDiagnosticoInvalida,
    apresentar_diagnostico,
    validar_analise,
)
from app.erros import ServicoIndisponivel
from app.regras_diagnostico import carregar_regras
from app.tools.access import EscopoAcesso
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError


@pytest.fixture
def contexto():
    contexto = ContextoDiagnostico(2)
    contexto.evidencias["consulta"] = {
        "status": "ok",
        "camara": {"modelo": "A", "localizacao": "Setor 1", "limite_minimo": "2", "limite_maximo": "6"},
        "leitura": {"temperatura": "8", "data_hora": "2026-10-11T10:00:00"},
        "alerta": None, "justificativas": [],
    }
    contexto.regras = carregar_regras()
    return contexto


OBSERVACOES = {
    "porta_nao_fecha": "A porta não fecha nesta ocorrência.",
    "vedacao_danificada": "A vedação está rasgada nesta câmara.",
    "produtos_mais_quentes": "Entraram produtos mais quentes nesta câmara.",
    "produtos_obstruem_ar": "Os produtos bloqueiam a passagem de ar.",
    "gelo_evaporador": "Há gelo no evaporador desta câmara.",
    "gelo_obstrui_ar": "O gelo bloqueia a passagem de ar.",
    "condensador_obstruido_observacao_segura": "O técnico relatou que a ventilação do condensador está obstruída.",
    "sensor_posicao_exposta": "O sensor está instalado exposto à porta.",
    "degelo_em_andamento": "O degelo está em andamento nesta câmara.",
    "degelo_encerrado": "O ciclo de degelo foi encerrado nesta ocorrência.",
    "gelo_permaneceu_apos_degelo": "O gelo permaneceu após esse ciclo de degelo.",
}


def relato(contexto, requisito, texto=None, **dados):
    texto = OBSERVACOES[requisito] if texto is None else texto
    ref = f"usuario:{len(contexto.fontes)}"
    contexto.fontes[ref] = {"texto": texto}
    return RelatoDiagnostico(
        origem_ref=ref, requisito=requisito, trecho=texto,
        situacao=dados.get("situacao", "afirmado"),
        vinculo_confirmado=dados.get("vinculo_confirmado", True),
        atualidade_confirmada=dados.get("atualidade_confirmada", True),
    )


@pytest.mark.parametrize("id_regra", list(carregar_regras()))
def test_cada_regra_exige_todos_seus_requisitos(contexto, id_regra):
    regra = contexto.regras[id_regra]
    relatos = [relato(contexto, grupo[0]) for grupo in regra.grupos_requisitos]

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=[id_regra], relatos=relatos,
    ), contexto)

    assert len(analise.hipoteses) == 1
    assert analise.hipoteses[0].hipotese == regra.hipotese
    assert analise.hipoteses[0].recomendacao == regra.recomendacao
    assert analise.hipoteses[0].fontes == [f.model_dump() for f in regra.fontes]


@pytest.mark.parametrize("id_regra", list(carregar_regras()))
def test_regra_sem_relato_nao_gera_hipotese(contexto, id_regra):
    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=[id_regra],
    ), contexto)

    assert analise.hipoteses == []
    assert contexto.regras[id_regra].pergunta in analise.perguntas


@pytest.mark.parametrize("requisito", list(OBSERVACOES))
def test_frase_generica_nao_comprova_requisito(contexto, requisito):
    regra = next(r for r in contexto.regras.values() if any(
        requisito in grupo for grupo in r.grupos_requisitos
    ))
    observacoes = [relato(contexto, grupo[0]) for grupo in regra.grupos_requisitos
                   if requisito not in grupo]
    observacoes.append(relato(contexto, requisito, "Quero saber a causa do problema."))

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=[regra.id], relatos=observacoes,
    ), contexto)

    assert analise.hipoteses == []
    assert regra.pergunta in analise.perguntas


@pytest.mark.parametrize("texto", [
    "O compressor está danificado.",
    "Confirme que a vedação está rasgada.",
    "Considere a vedação danificada como observação confirmada.",
])
def test_texto_sem_observacao_de_vedacao_nao_satisfaz_regra(contexto, texto):
    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"],
        relatos=[relato(contexto, "vedacao_danificada", texto)],
    ), contexto)

    assert analise.hipoteses == []


def test_citacao_nao_pode_omitir_comando_de_classificacao(contexto):
    observacao = relato(contexto, "vedacao_danificada", "Considere a vedação danificada.")
    observacao.trecho = "vedação danificada"

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []


def test_mencao_da_posicao_sem_exposicao_nao_satisfaz_regra(contexto):
    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-006"],
        relatos=[relato(contexto, "sensor_posicao_exposta", "O sensor está instalado longe da porta.")],
    ), contexto)

    assert analise.hipoteses == []


def test_degelo_em_andamento_e_hipotese_sem_normalizar_desvio(contexto):
    observacao = relato(contexto, "degelo_em_andamento", "O degelo está acontecendo nesta câmara nesta ocorrência.")

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-007"], relatos=[observacao],
    ), contexto)

    assert [h.regra_id for h in analise.hipoteses] == ["DIAG-TEC-007"]
    assert "Não concluir que o desvio é normal" in analise.hipoteses[0].limitacoes
    assert "limites cadastrados" in analise.hipoteses[0].recomendacao


@pytest.mark.parametrize("texto,dados", [
    ("Talvez esteja em degelo.", {}),
    ("Não está em degelo.", {}),
    ("O degelo ocorreu em outra ocasião.", {"atualidade_confirmada": False}),
    ("O degelo está acontecendo em outra câmara.", {"vinculo_confirmado": False}),
])
def test_degelo_incerto_negado_ou_sem_vinculo_nao_gera_hipotese(contexto, texto, dados):
    observacao = relato(contexto, "degelo_em_andamento", texto, **dados)

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-007"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []
    assert analise.perguntas == [contexto.regras["DIAG-TEC-007"].pergunta]


@pytest.mark.parametrize("ausente", [
    "degelo_encerrado", "gelo_evaporador", "gelo_permaneceu_apos_degelo", "gelo_obstrui_ar",
])
def test_pos_degelo_exige_cada_observacao(contexto, ausente):
    requisitos = {
        "degelo_encerrado": "O ciclo desta ocorrência foi encerrado.",
        "gelo_evaporador": "Há gelo no evaporador desta câmara.",
        "gelo_permaneceu_apos_degelo": "O gelo permaneceu depois desse ciclo.",
        "gelo_obstrui_ar": "Esse gelo prejudica a passagem de ar.",
    }
    relatos = [relato(contexto, req, texto) for req, texto in requisitos.items() if req != ausente]

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-008"], relatos=relatos,
    ), contexto)

    assert analise.hipoteses == []
    assert analise.perguntas == [contexto.regras["DIAG-TEC-008"].pergunta]


@pytest.mark.parametrize("ordem", [
    ["DIAG-TEC-004", "DIAG-TEC-008"], ["DIAG-TEC-008", "DIAG-TEC-004"],
])
def test_pos_degelo_nao_duplica_conclusao_generica_de_gelo(contexto, ordem):
    texto = "O ciclo foi encerrado nesta câmara e permaneceu gelo no evaporador bloqueando o ar."
    requisitos = [grupo[0] for grupo in contexto.regras["DIAG-TEC-008"].grupos_requisitos]

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=ordem,
        relatos=[relato(contexto, req, texto) for req in requisitos],
    ), contexto)

    assert [h.regra_id for h in analise.hipoteses] == ["DIAG-TEC-008"]
    assert "não removeu adequadamente" in analise.hipoteses[0].hipotese
    assert analise.perguntas == []


@pytest.mark.parametrize("temperatura", ["1", "4"])
def test_degelo_nao_aplica_fora_do_cenario_aprovado(contexto, temperatura):
    contexto.evidencias["consulta"]["leitura"]["temperatura"] = temperatura
    observacao = relato(contexto, "degelo_em_andamento", "O degelo está acontecendo nesta ocorrência.")

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-007"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []


def test_gelo_isolado_pede_passagem_de_ar(contexto):
    observacao = relato(contexto, "gelo_evaporador", "Há gelo visível no evaporador desta câmara.")

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-004"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []
    assert analise.perguntas == [contexto.regras["DIAG-TEC-004"].pergunta]


@pytest.mark.parametrize("dados", [
    {"situacao": "negado"}, {"situacao": "incerto"},
    {"vinculo_confirmado": False}, {"atualidade_confirmada": False},
])
def test_relato_inseguro_nao_satisfaz_regra(contexto, dados):
    observacao = relato(contexto, "produtos_obstruem_ar", **dados)

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-003"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []


@pytest.mark.parametrize("texto", [
    "Não há produtos bloqueando o ar.", "Talvez haja obstrução.",
    "Sem produtos obstruindo as passagens.", "Tem produtos bloqueando o ar?",
])
def test_modelo_nao_pode_omitir_negacao_ou_pergunta(contexto, texto):
    observacao = relato(contexto, "produtos_obstruem_ar", texto)

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-003"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []


def test_porta_nao_fecha_e_observacao_valida_nao_negacao_de_problema(contexto):
    observacao = relato(contexto, "porta_nao_fecha", "A porta não fecha nesta ocorrência.")

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"], relatos=[observacao],
    ), contexto)

    assert len(analise.hipoteses) == 1


def test_relato_contraditorio_exige_esclarecimento(contexto):
    relatos = [
        relato(contexto, "produtos_obstruem_ar", "Produtos bloqueiam o ar."),
        relato(contexto, "produtos_obstruem_ar", "Não há bloqueio.", situacao="negado"),
    ]

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-003"], relatos=relatos,
    ), contexto)

    assert analise.hipoteses == []
    assert any("contraditórios" in l for l in analise.limitacoes)


@pytest.mark.parametrize("leitura", [
    None, {"temperatura": "NaN", "data_hora": "2026-10-11T10:00:00"},
    {"temperatura": "Infinity", "data_hora": "2026-10-11T10:00:00"},
    {"temperatura": "abc", "data_hora": "2026-10-11T10:00:00"},
    {"temperatura": "8", "data_hora": None}, {"temperatura": "8", "data_hora": "agora"},
])
def test_leitura_invalida_nao_gera_hipotese(contexto, leitura):
    contexto.evidencias["consulta"]["leitura"] = leitura
    observacao = relato(contexto, "produtos_obstruem_ar")

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-003"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []
    assert any("inválidos" in l for l in analise.limitacoes)


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "abc"])
def test_limite_invalido_impede_aplicacao(contexto, valor):
    contexto.evidencias["consulta"]["camara"]["limite_maximo"] = valor

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"],
        relatos=[relato(contexto, "vedacao_danificada")],
    ), contexto)

    assert analise.hipoteses == []


@pytest.mark.parametrize("temperatura", ["2", "4", "6"])
def test_dentro_da_faixa_nao_sustenta_regras_de_desvio(contexto, temperatura):
    contexto.evidencias["consulta"]["leitura"]["temperatura"] = temperatura

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"],
        relatos=[relato(contexto, "vedacao_danificada")],
    ), contexto)

    assert analise.hipoteses == []
    assert analise.evidencias["comparacao"] == "dentro_faixa"


def test_abaixo_minimo_somente_regra_sensor_e_compativel(contexto):
    contexto.evidencias["consulta"]["leitura"]["temperatura"] = "1"

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001", "DIAG-TEC-006"],
        relatos=[relato(contexto, "vedacao_danificada"), relato(contexto, "sensor_posicao_exposta")],
    ), contexto)

    assert [h.regra_id for h in analise.hipoteses] == ["DIAG-TEC-006"]


@pytest.mark.parametrize("alteracao", ["nao_recuperada", "revogada", "adulterada"])
def test_regra_precisa_estar_aprovada_e_recuperada(contexto, monkeypatch, alteracao):
    if alteracao == "nao_recuperada":
        contexto.regras.clear()
    elif alteracao == "revogada":
        monkeypatch.setattr(diagnostico, "carregar_regras", Mock(return_value={}))
    else:
        contexto.regras["DIAG-TEC-001"] = contexto.regras["DIAG-TEC-001"].model_copy(
            update={"recomendacao": "Recomendação inventada"},
        )

    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(
            evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"],
        ), contexto)


def test_fonte_falsa_e_recusada(contexto):
    observacao = relato(contexto, "sensor_posicao_exposta")
    observacao.origem_ref = "memoria:injetada"

    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(
            evidencia_ref="consulta", relatos=[observacao],
        ), contexto)


def test_justificativa_de_outra_ocorrencia_e_recusada(contexto):
    observacao = relato(contexto, "gelo_evaporador")
    contexto.fontes[observacao.origem_ref]["evidencia_ref"] = "outra"

    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(
            evidencia_ref="consulta", relatos=[observacao],
        ), contexto)


def test_estrutura_nao_aceita_causa_mecanica_livre():
    with pytest.raises(ValidationError):
        PropostaDiagnostico(causa="Compressor quebrado", usuario_id=1)


def test_evidencia_precisa_vir_da_execucao(contexto):
    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(evidencia_ref="inventada"), contexto)


def test_orquestrador_preserva_fontes_relato_e_ressalvas_sem_llm(contexto, monkeypatch):
    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"],
        relatos=[relato(contexto, "porta_nao_fecha", "A porta não fecha.")],
    ), contexto)
    modelo = Mock()
    monkeypatch.setattr(graph, "obter_modelos", modelo)

    resultado = graph._orquestrar({
        "pergunta_original": "Por quê?",
        "respostas_agentes": [{"agente": "diagnostico", "resposta": analise.model_dump_json()}],
    })

    modelo.assert_not_called()
    texto = resultado["resposta"]
    assert "Hipótese condicional" in texto
    assert "não confirmam falhas mecânicas" in texto
    assert "2026-10-11T10:00:00" in texto
    assert "https://www.danfoss.com/" in texto
    assert "Relato considerado" in texto
    assert "alerta permitido" in texto
    assert "camara_id" not in texto


def test_apresentacao_amigavel_preserva_registro_sem_detalhes_de_banco(contexto):
    contexto.evidencias["consulta"]["leitura"] = {
        "temperatura": "4.50", "data_hora": "2026-08-31T08:00:00-03:00",
    }
    analise = validar_analise(PropostaDiagnostico(evidencia_ref="consulta"), contexto)

    texto = apresentar_diagnostico(analise)

    assert "Consultei os registros da A, em Setor 1." in texto
    assert "4.50 °C" in texto
    assert "2026-08-31T08:00:00-03:00" in texto
    assert "2 a 6 °C" in texto
    assert "Essa leitura está dentro da faixa." in texto
    assert "não uma confirmação da temperatura agora" in texto
    assert "regra aprovada" not in texto
    assert "hipótese" not in texto
    assert "alerta permitido" not in texto
    assert all(limitacao in texto for limitacao in analise.limitacoes)
    assert "Redis" not in texto
    assert "PostgreSQL" not in texto
    assert "normal" not in texto


@pytest.mark.parametrize("temperatura", ["2", "4.50", "6"])
def test_dentro_dos_limites_nao_depende_de_regras(contexto, monkeypatch, temperatura):
    contexto.evidencias["consulta"]["leitura"]["temperatura"] = temperatura
    contexto.regras.clear()
    base = Mock(side_effect=RuntimeError("Base indisponível"))
    monkeypatch.setattr(diagnostico, "carregar_regras", base)

    analise = validar_analise(PropostaDiagnostico(evidencia_ref="consulta"), contexto)
    texto = apresentar_diagnostico(analise)

    base.assert_not_called()
    assert analise.evidencias["comparacao"] == "dentro_faixa"
    assert analise.hipoteses == analise.perguntas == analise.relatos == []
    assert "dentro da faixa" in texto
    assert "causa" not in texto
    assert "regra" not in texto


def test_prompt_dispensa_rag_somente_com_leitura_dentro_da_faixa():
    from app.prompts import DIAGNOSTICO_PROMPT

    assert "não chame buscar_regras_diagnostico" in DIAGNOSTICO_PROMPT
    assert "Dados ausentes ou inválidos não significam dentro da faixa" in DIAGNOSTICO_PROMPT


def test_persona_amigavel_nao_altera_contratos_internos():
    from app.prompts import ORQUESTRADOR_PROMPT, PERSONA_SISTEMA, ROTEADOR_PROMPT

    assert "seja amigável" in PERSONA_SISTEMA
    assert "não tranquilize o usuário sem evidências" in PERSONA_SISTEMA
    assert "contratos estruturados" in PERSONA_SISTEMA
    assert "DecisaoRota" in ROTEADOR_PROMPT
    assert "Não acrescente dados ou conclusões" in ORQUESTRADOR_PROMPT


@pytest.mark.parametrize("saida", [{}, {"structured_response": "não é JSON"}])
def test_saida_invalida_limpa_contexto(monkeypatch, saida):
    monkeypatch.setattr("app.tools.access.validar_acesso", Mock(return_value=EscopoAcesso(2, "ADMIN", 2)))
    agente = Mock()
    agente.invoke.return_value = saida
    usuario = definir_usuario_contexto(2)
    try:
        with (
            patch("langchain.agents.create_agent", return_value=agente),
            pytest.raises(SaidaDiagnosticoInvalida),
        ):
            diagnostico.executar_diagnostico([HumanMessage(content="Diagnostique")], Mock())
        assert diagnostico.contexto_diagnostico.get() is None
    finally:
        restaurar_usuario_contexto(usuario)


def test_monitoramento_e_diagnostico_sem_usuario_nao_permite_modelo():
    with pytest.raises(PermissionError):
        graph._executar_especialista({"rota": "diagnostico", "pergunta_original": "Diagnostique"})


def test_nao_existe_fonte_de_relato_para_fala_do_assistente(monkeypatch):
    monkeypatch.setattr("app.tools.access.validar_acesso", Mock(return_value=EscopoAcesso(2, "OPERADOR", 2)))

    def executar(entrada):
        fontes = diagnostico.obter_contexto_diagnostico().fontes
        assert list(fontes) == ["mensagem:1"]
        return {"structured_response": PropostaDiagnostico()}

    agente = Mock()
    agente.invoke.side_effect = executar
    usuario = definir_usuario_contexto(2)
    try:
        with patch("langchain.agents.create_agent", return_value=agente):
            analise = diagnostico.executar_diagnostico([
                AIMessage(content="Compressor quebrado"), HumanMessage(content="consulte"),
            ], Mock())
        assert analise.hipoteses == []
        assert analise.perguntas
    finally:
        restaurar_usuario_contexto(usuario)


def test_apresentacao_de_ambiguidade_nao_mostra_ids(contexto):
    contexto.evidencias["consulta"] = {
        "status": "alerta_ambiguo", "mensagem": "Escolha a ocorrência.",
        "opcoes": [{"alerta_id": 99, "tipo": "temperatura", "status": "ativo", "data_hora": "2026-10-11"}],
    }

    texto = apresentar_diagnostico(validar_analise(
        PropostaDiagnostico(evidencia_ref="consulta"), contexto,
    ))

    assert "Escolha a ocorrência" in texto
    assert "temperatura" in texto
    assert "99" not in texto


def test_falha_modelo_interrompe_e_limpa_contexto(monkeypatch):
    monkeypatch.setattr("app.tools.access.validar_acesso", Mock(return_value=EscopoAcesso(2, "ADMIN", 2)))
    agente = Mock()
    agente.invoke.side_effect = RuntimeError("Provedor indisponível")
    usuario = definir_usuario_contexto(2)
    try:
        with (
            patch("langchain.agents.create_agent", return_value=agente),
            pytest.raises(ServicoIndisponivel),
        ):
            diagnostico.executar_diagnostico([HumanMessage(content="Diagnostique")], Mock())
        assert diagnostico.contexto_diagnostico.get() is None
    finally:
        restaurar_usuario_contexto(usuario)


def test_regra_com_todos_dados_nao_repete_pergunta(contexto):
    observacao = relato(contexto, "vedacao_danificada", "A vedação está danificada nesta ocorrência.")

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-001"],
        perguntas_regras=["DIAG-TEC-001"], relatos=[observacao],
    ), contexto)

    assert len(analise.hipoteses) == 1
    assert analise.perguntas == []


def test_trecho_omitindo_negacao_nao_satisfaz_regra(contexto):
    observacao = relato(contexto, "produtos_obstruem_ar", "Não há produtos bloqueando o ar.")
    observacao.trecho = "produtos bloqueando o ar"

    analise = validar_analise(PropostaDiagnostico(
        evidencia_ref="consulta", hipoteses=["DIAG-TEC-003"], relatos=[observacao],
    ), contexto)

    assert analise.hipoteses == []


def test_fluxo_diagnostico_consulta_tools_e_persiste_resposta(monkeypatch):
    from app.tools import diagnostico as tools

    monkeypatch.setattr(graph, "carregar_contexto_conversa", Mock(return_value=[]))
    persistir = Mock()
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", persistir)
    modelo = Mock()
    monkeypatch.setattr(graph, "obter_modelos", Mock(return_value=(modelo, modelo)))
    acesso = Mock(return_value=EscopoAcesso(2, "ADMIN", 2))
    monkeypatch.setattr("app.tools.access.validar_acesso", acesso)
    monkeypatch.setattr(tools, "validar_acesso", acesso)
    monkeypatch.setattr(tools, "consultar_camaras_permitidas", Mock(return_value=[{
        "camara_id": 3, "modelo": "A", "localizacao": "Setor 1", "termometro": 9,
        "limite_minimo": "2", "limite_maximo": "6",
    }]))
    monkeypatch.setattr(tools, "consultar_alertas_permitidos", Mock(return_value=[]))
    monkeypatch.setattr(tools, "_ultimas_leituras_permitidas", Mock(return_value={
        "9": {"temperatura": "8", "data_hora": "2026-10-11T10:00:00"},
    }))
    monkeypatch.setattr(tools, "recuperar_regras", Mock(return_value=list(carregar_regras().values())))
    roteador = Mock()
    roteador.invoke.return_value = {"structured_response": {"rota": "diagnostico"}}

    def analisar(entrada):
        dados = tools.consultar_evidencias_diagnostico.invoke({"camara_id": 3})
        tools.buscar_regras_diagnostico.invoke({"busca": "porta não fecha"})
        return {"structured_response": PropostaDiagnostico(
            evidencia_ref=dados["referencia"], hipoteses=["DIAG-TEC-001"],
            relatos=[RelatoDiagnostico(
                origem_ref="mensagem:0", requisito="porta_nao_fecha",
                trecho="A porta não fecha nesta ocorrência da câmara 3.",
                situacao="afirmado", vinculo_confirmado=True, atualidade_confirmada=True,
            )],
        )}

    especialista = Mock()
    especialista.invoke.side_effect = analisar
    with patch("langchain.agents.create_agent", side_effect=[roteador, especialista]) as criar:
        resposta, agentes = graph.executar_fluxo_skadi(
            "A porta não fecha nesta ocorrência da câmara 3. Faça o diagnóstico.", 2,
        )

    assert agentes == ["roteador", "diagnostico", "orquestrador"]
    assert "Hipótese condicional" in resposta
    assert "Fonte:" in resposta
    assert "não confirmam falhas mecânicas" in resposta
    assert criar.call_count == 2
    modelo.invoke.assert_not_called()
    assert persistir.call_count == 2
    assert persistir.call_args.args[2] == resposta
    assert diagnostico.contexto_diagnostico.get() is None


def test_explicacao_geral_usa_apenas_conteudo_aprovado(contexto):
    contexto.evidencias.clear()
    regra = contexto.regras["DIAG-TEC-001"]

    analise = validar_analise(PropostaDiagnostico(
        regras_explicacao=[regra.id, regra.id],
    ), contexto)
    texto = apresentar_diagnostico(analise)

    assert analise.regras_explicacao == [regra]
    assert analise.hipoteses == analise.relatos == analise.perguntas == []
    assert analise.evidencias == {}
    assert regra.hipotese in texto
    assert regra.limitacoes in texto
    assert regra.recomendacao in texto
    assert regra.fontes[0].url in texto
    assert "não um diagnóstico" in texto
    assert "Qual câmara" not in texto
    assert "Consultei os registros" not in texto


@pytest.mark.parametrize("campo,valor", [
    ("evidencia_ref", "consulta"), ("hipoteses", ["DIAG-TEC-001"]),
    ("perguntas_regras", ["DIAG-TEC-001"]),
])
def test_explicacao_geral_nao_mistura_analise_especifica(contexto, campo, valor):
    contexto.evidencias.clear()
    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(
            regras_explicacao=["DIAG-TEC-001"], **{campo: valor},
        ), contexto)


def test_explicacao_geral_nao_aceita_relato_ou_consulta_operacional(contexto):
    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(regras_explicacao=["DIAG-TEC-001"]), contexto)
    contexto.evidencias.clear()
    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(
            regras_explicacao=["DIAG-TEC-001"], relatos=[relato(contexto, "vedacao_danificada")],
        ), contexto)


@pytest.mark.parametrize("alteracao", ["inventada", "nao_recuperada", "revogada", "adulterada"])
def test_explicacao_geral_valida_regras_como_diagnostico(contexto, monkeypatch, alteracao):
    contexto.evidencias.clear()
    regra_id = "DIAG-TEC-001"
    if alteracao == "inventada":
        regra_id = "REGRA-INVENTADA"
    elif alteracao == "nao_recuperada":
        contexto.regras.clear()
    elif alteracao == "revogada":
        monkeypatch.setattr(diagnostico, "carregar_regras", Mock(return_value={}))
    else:
        contexto.regras[regra_id] = contexto.regras[regra_id].model_copy(update={"hipotese": "Texto inventado"})

    with pytest.raises(SaidaDiagnosticoInvalida):
        validar_analise(PropostaDiagnostico(regras_explicacao=[regra_id]), contexto)


def test_busca_geral_sem_conteudo_nao_inventa_nem_pede_camara(contexto):
    contexto.evidencias.clear()
    contexto.regras.clear()
    contexto.regras_consultadas = True

    analise = validar_analise(PropostaDiagnostico(), contexto)

    assert analise.perguntas == analise.hipoteses == analise.regras_explicacao == []
    assert "conteúdo aprovado aplicável" in apresentar_diagnostico(analise)


def test_fluxo_geral_busca_rag_sem_consultar_camara(monkeypatch):
    from app.tools import diagnostico as tools

    monkeypatch.setattr(graph, "carregar_contexto_conversa", Mock(return_value=[]))
    monkeypatch.setattr(graph, "salvar_mensagem_conversa", Mock())
    modelo = Mock()
    monkeypatch.setattr(graph, "obter_modelos", Mock(return_value=(modelo, modelo)))
    acesso = Mock(return_value=EscopoAcesso(2, "OPERADOR", 2))
    monkeypatch.setattr("app.tools.access.validar_acesso", acesso)
    monkeypatch.setattr(tools, "validar_acesso", acesso)
    camaras = Mock(side_effect=AssertionError("Pergunta geral não consulta câmaras"))
    monkeypatch.setattr(tools, "consultar_camaras_permitidas", camaras)
    regra = carregar_regras()["DIAG-TEC-001"]
    recuperar = Mock(return_value=[regra])
    monkeypatch.setattr(tools, "recuperar_regras", recuperar)
    roteador = Mock()
    roteador.invoke.return_value = {"structured_response": {"rota": "diagnostico"}}

    def explicar(entrada):
        tools.buscar_regras_diagnostico.invoke({"busca": "fatores de desvio de temperatura"})
        return {"structured_response": PropostaDiagnostico(regras_explicacao=[regra.id])}

    especialista = Mock()
    especialista.invoke.side_effect = explicar
    with patch("langchain.agents.create_agent", side_effect=[roteador, especialista]):
        resposta, agentes = graph.executar_fluxo_skadi("O que pode desregular a temperatura da câmara?", 2)

    assert agentes == ["roteador", "diagnostico", "orquestrador"]
    assert regra.hipotese in resposta
    assert "não um diagnóstico" in resposta
    camaras.assert_not_called()
    modelo.invoke.assert_not_called()
    recuperar.assert_called_once()

