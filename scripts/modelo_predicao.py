"""Comando administrativo local; não é endpoint nem ferramenta do LLM."""

import argparse
from datetime import UTC, datetime
from uuid import UUID

from app.modelos_predicao import carregar_modelo, momento, salvar_modelo, treinar_modelo
from app.predicao import consultar_serie, validar_acesso_predicao
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from app.tools.monitoramento import consultar_camaras_permitidas
from psycopg2 import Error as PostgreSQLError


def main():
    parser = argparse.ArgumentParser(description="Treinar em revisão ou aprovar versão explicitamente autorizada.")
    comandos = parser.add_subparsers(dest="acao", required=True)
    treino = comandos.add_parser("treinar")
    aprovacao = comandos.add_parser("aprovar")
    for comando in (treino, aprovacao):
        comando.add_argument("--usuario-id", type=int, required=True, help="Operador administrativo local; não é autenticação mobile.")
        comando.add_argument("--camara-id", type=int, required=True)
    treino.add_argument("--inicio-coleta", required=True, help="ISO do início efetivo da coleta contínua, registrado pelo worker.")
    treino.add_argument("--inicio", required=True)
    treino.add_argument("--fim", required=True)
    treino.add_argument("--cadencia-segundos", type=int, required=True)
    treino.add_argument("--horizontes-minutos", nargs="+", type=int, required=True)
    aprovacao.add_argument("--modelo-id", type=UUID, required=True)
    aprovacao.add_argument("--confirmar-aprovacao", action="store_true", help="Somente após aprovação humana das métricas.")
    argumentos = parser.parse_args()
    token = definir_usuario_contexto(argumentos.usuario_id)
    try:
        usuario = validar_acesso_predicao()
        camaras = consultar_camaras_permitidas(usuario, argumentos.camara_id)
        if len(camaras) != 1 or camaras[0]["termometro"] is None:
            raise ValueError("Câmara única com termômetro não encontrada no escopo.")
        camara = camaras[0]
        if argumentos.acao == "treinar":
            inicio_coleta, inicio, fim = map(momento, (
                argumentos.inicio_coleta, argumentos.inicio, argumentos.fim,
            ))
            if not inicio_coleta <= inicio < fim:
                raise ValueError("Período deve estar dentro da coleta contínua.")
            linhas = consultar_serie(camara, inicio, fim)
            modelo = treinar_modelo(
                linhas, camara_id=camara["camara_id"], termometro_id=camara["termometro"],
                cadencia_segundos=argumentos.cadencia_segundos, inicio_coleta=inicio_coleta,
                horizontes_minutos=argumentos.horizontes_minutos,
            )
            salvar_modelo(modelo)
            print(modelo.model_dump_json(indent=2))
            print("Modelo EM_REVISAO. Não foi ativado; compare as métricas e solicite aprovação.")
        else:
            modelo = carregar_modelo(camara["camara_id"], pendente=True)
            if (modelo is None or modelo.modelo_id != argumentos.modelo_id
                    or modelo.termometro_id != camara["termometro"]
                    or modelo.status != "EM_REVISAO" or not argumentos.confirmar_aprovacao):
                raise ValueError("Versão pendente, vínculo ou confirmação de aprovação inválidos.")
            aprovado = modelo.model_copy(update={"status": "APROVADO", "aprovado_em": datetime.now(UTC)})
            salvar_modelo(aprovado)
            print("Versão aprovada ativada. Não houve escrita em dados operacionais.")
    except (ValueError, TypeError, OverflowError) as erro:
        # Mensagens locais de validação; não são erros com URIs de SDKs.
        raise SystemExit(f"Operação não concluída: {erro}") from None
    except (PermissionError, OSError, RuntimeError, PostgreSQLError) as erro:
        raise SystemExit(f"Operação não concluída ({type(erro).__name__}).") from None
    finally:
        restaurar_usuario_contexto(token)


if __name__ == "__main__":
    main()
