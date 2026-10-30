from __future__ import annotations

import json

from app.erros import SaidaModeloInvalida
from langchain_core.messages import ToolMessage


def resumir_alertas(alertas: list[dict]) -> list[dict]:
    grupos = {}
    for alerta in alertas:
        chave = tuple(alerta[campo] for campo in ("camara", "tipo", "gravidade", "status"))
        if chave not in grupos:
            grupos[chave] = {**{campo: alerta[campo] for campo in ("camara", "tipo", "gravidade", "status")},
                             "quantidade": 0, "primeiro_horario": alerta["data_hora"], "ultimo_horario": alerta["data_hora"]}
        grupo = grupos[chave]
        grupo["quantidade"] += 1
        grupo["primeiro_horario"] = min(grupo["primeiro_horario"], alerta["data_hora"])
        grupo["ultimo_horario"] = max(grupo["ultimo_horario"], alerta["data_hora"])
    return list(grupos.values())


def apresentar_consultas(mensagens: list) -> str | None:
    respostas = []
    for mensagem in mensagens:
        if not isinstance(mensagem, ToolMessage) or mensagem.name not in {
            "consultar_temperaturas", "listar_camaras_responsaveis",
            "consultar_alertas_atuais_do_usuario",
        }:
            continue
        try:
            dados = json.loads(mensagem.content)
        except (TypeError, ValueError) as erro:
            raise SaidaModeloInvalida("Resultado de consulta inválido.") from erro
        if mensagem.name == "consultar_alertas_atuais_do_usuario":
            respostas.append(f"Encontrei {len(dados)} alerta(s) disponíveis para você. Resumo por câmara, tipo, gravidade e status: " + " ".join(
                f'{a["camara"]}: {a["quantidade"]} alerta(s) de {a["tipo"]}, gravidade {a["gravidade"]}, '
                f'status {a["status"]}, entre {a["primeiro_horario"]} e {a["ultimo_horario"]}.'
                for a in resumir_alertas(dados)
            ) if dados else "No momento, não encontrei alertas ativos ou reconhecidos por você no seu escopo.")
            continue
        camaras = dados if isinstance(dados, list) else dados["camaras"]
        if not isinstance(dados, list) and dados.get("status") == "ambigua":
            respostas.append("Encontrei mais de uma opção para você. Qual câmara deseja consultar? " + "; ".join(
                f'{c["modelo"]} — {c["localizacao"]}' for c in camaras
            ) + ".")
            continue
        if not camaras:
            respostas.append("Não encontrei câmaras com essa seleção no seu acesso permitido.")
        for camara in camaras:
            texto = f'{camara["modelo"]} — {camara["localizacao"]}: '
            if "leitura_disponivel" in camara:
                if camara["leitura_disponivel"]:
                    texto += f'última leitura de {camara["temperatura"]} °C, registrada em {camara["data_hora"]}. '
                elif camara.get("leitura_invalida"):
                    texto += "o registro de leitura está inválido; não posso informar uma temperatura confiável. "
                else:
                    texto += "sem leitura disponível. "
            texto += f'Limites cadastrados: {camara["limite_minimo"]} a {camara["limite_maximo"]} °C.'
            respostas.append(texto)
        if mensagem.name == "consultar_temperaturas" and any(c.get("leitura_disponivel") for c in camaras):
            respostas.append("Essas são as últimas leituras disponíveis, não uma confirmação da temperatura agora.")
    texto = " ".join(dict.fromkeys(respostas))
    return f"Claro! {texto}" if texto else None
