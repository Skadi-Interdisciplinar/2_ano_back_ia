from __future__ import annotations

import json

from app.erros import SaidaModeloInvalida
from langchain_core.messages import ToolMessage


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
            respostas.append("Alertas permitidos para você: " + " ".join(
                f'{a["camara"]}: {a["tipo"]}, gravidade {a["gravidade"]}, '
                f'status {a["status"]}, registrado em {a["data_hora"]}.'
                for a in dados
            ) if dados else "Não encontrei alertas ativos ou reconhecidos por você no seu escopo.")
            continue
        camaras = dados if isinstance(dados, list) else dados["camaras"]
        if not isinstance(dados, list) and dados.get("status") == "ambigua":
            respostas.append("Encontrei mais de uma câmara. Qual deseja consultar? " + "; ".join(
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
    return " ".join(dict.fromkeys(respostas)) or None
