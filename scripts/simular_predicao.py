"""Lote sintético aprovado: câmara 3, dois dias, cadência de cinco minutos.

Não é produtor permanente nem coleta real. Reutiliza a persistência do worker,
preserva triggers e publica eventos identificados no Redis. Nunca aprova modelo.
"""

import argparse
import importlib.util
import json
import os
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.config import BASE_DIR, DATABASE_URL, REDIS_URL
from app.modelos_predicao import (
    FUSO_LEITURAS,
    carregar_modelo,
    momento,
    salvar_modelo,
    treinar_modelo,
)
from app.predicao import consultar_serie, validar_acesso_predicao
from app.tools.contexto import definir_usuario_contexto, restaurar_usuario_contexto
from app.tools.db import get_conn
from app.tools.monitoramento import consultar_camaras_permitidas


def gerar_leituras(fim, lote: UUID) -> list[dict]:
    """577 pontos incluindo extremos de 48h; cenários explícitos, sem ruído oculto."""
    fim = momento(fim)
    inicio = fim - timedelta(days=2)
    leituras = []
    for indice in range(577):
        trecho, passo = divmod(indice % 288, 72)
        fase = Decimal(passo) / Decimal(36) if passo <= 36 else Decimal(72 - passo) / Decimal(36)
        if trecho == 0:
            nome = "normal_oscilante"
            pontos = (Decimal(4), Decimal(5), Decimal(3), Decimal(4))
            parte, deslocamento = divmod(passo, 24)
            temperatura = pontos[parte] + (pontos[parte + 1] - pontos[parte]) * Decimal(deslocamento) / Decimal(24)
        elif trecho == 1:
            nome, temperatura = "subida_recuperacao", Decimal(4) + Decimal(4) * fase
        elif trecho == 2:
            nome, temperatura = "queda_recuperacao", Decimal(4) - Decimal(4) * fase
        else:
            nome = "picos_pontuais"
            temperatura = Decimal(8) if passo == 12 else Decimal(0) if passo == 36 else Decimal(4)
        leituras.append({
            "id_evento_redis": f"sim-trimmy-{lote}-{indice:04d}",
            "cod_termometro": "3",
            "temperatura": str(temperatura.quantize(Decimal("0.01"))),
            "data_hora": (inicio + timedelta(minutes=5 * indice)).astimezone(FUSO_LEITURAS).isoformat(),
            "origem": "SIMULADO", "lote_simulacao": str(lote), "cenario": nome,
        })
    return leituras


def executar_lote(usuario_id: int, lote: UUID, fim, caminho_worker: Path) -> dict:
    """Administração local explícita; não é tool ou endpoint do aplicativo."""
    token = definir_usuario_contexto(usuario_id)
    try:
        usuario = validar_acesso_predicao()
        camaras = consultar_camaras_permitidas(usuario, camara_id=3)
        if len(camaras) != 1:
            raise PermissionError("Câmara 3 não encontrada no escopo administrativo.")
        camara = camaras[0]
        if (camara["termometro"] != 3 or Decimal(camara["limite_minimo"]) != 2
                or Decimal(camara["limite_maximo"]) != 6):
            raise ValueError("Cadastro mudou; os parâmetros da simulação precisam de nova validação.")
        if carregar_modelo(3) is not None:
            raise ValueError("Há modelo ativo; não misturar simulação com operação existente.")
        pendente = carregar_modelo(3, pendente=True)
        if pendente is not None and pendente.lote_simulacao != lote:
            raise ValueError("Há outra versão em revisão; não será sobrescrita.")
        eventos = gerar_leituras(fim, lote)
        inicio, final = momento(eventos[0]["data_hora"]), momento(eventos[-1]["data_hora"])
        if final > momento(datetime.now(FUSO_LEITURAS)):
            raise ValueError("O histórico sintético não pode terminar no futuro.")
        pasta = BASE_DIR / "simulacoes_predicao"
        pasta.mkdir(exist_ok=True)
        manifesto = pasta / f"{lote}.json"
        parametros = {"origem": "SIMULADO", "lote": str(lote), "camara_id": 3,
                      "cadencia_segundos": 300, "eventos": eventos}
        if manifesto.exists():
            anterior = json.loads(manifesto.read_text(encoding="utf-8"))
            if anterior["eventos"] != eventos:
                raise ValueError("O lote existente tem outro período; não reutilizar seus IDs.")
        # Manifesto antes de efeitos externos permite identificar e retomar o lote.
        manifesto.write_text(json.dumps(parametros, ensure_ascii=False, indent=2), encoding="utf-8")
        if not caminho_worker.is_file() or caminho_worker.name != "worker.py":
            raise ValueError("Informe o worker existente do projeto.")
        import redis

        cliente = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5, socket_timeout=10)
        cliente.ping()
        # Configuração da IA explicitamente passada; nenhum .env externo substitui o banco.
        os.environ["DATABASE_URL"] = DATABASE_URL
        os.environ["REDIS_URL"] = REDIS_URL
        especificacao = importlib.util.spec_from_file_location("worker_simulacao_local", caminho_worker)
        worker = importlib.util.module_from_spec(especificacao)
        especificacao.loader.exec_module(worker)
        repositorio = worker.PostgresRepository()
        ids = []
        with closing(get_conn()) as conexao:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT set_config('app.usuario_atual', %s, true)", (str(usuario),))
                cursor.execute(
                    "SELECT id_evento_redis FROM tb_leitura_temperatura WHERE cod_termometro = %s "
                    "AND data_hora BETWEEN %s AND %s",
                    (3, inicio.astimezone(FUSO_LEITURAS).replace(tzinfo=None),
                     final.astimezone(FUSO_LEITURAS).replace(tzinfo=None)),
                )
                esperados = {e["id_evento_redis"] for e in eventos}
                if any(linha[0] not in esperados for linha in cursor.fetchall()):
                    raise ValueError("Há leituras de outro lote no período; não misturar históricos.")
            for evento in eventos:
                ids.append(repositorio.persist_reading(
                    conexao, evento["id_evento_redis"], 3, Decimal(evento["temperatura"]),
                    worker.parse_timestamp(evento["data_hora"]),
                ))
            conexao.commit()  # Todas as leituras/triggers ou nenhuma, caso exista conflito.
        # Os eventos usam o mesmo ID do PostgreSQL: reprocessamento pelo worker é idempotente.
        # Não inicia scheduler, não escalona alertas e não altera consumer groups.
        ja_publicados = {campos.get("id_evento_redis") for _, campos in
                         cliente.xrange(worker.TEMPERATURE_STREAM)
                         if campos.get("lote_simulacao") == str(lote)}
        with cliente.pipeline(transaction=True) as pipeline:
            for evento in eventos:
                if evento["id_evento_redis"] not in ja_publicados:
                    pipeline.xadd(worker.TEMPERATURE_STREAM, evento)
            pipeline.execute()
        linhas = consultar_serie(camara, inicio, final)
        if len(linhas) != len(eventos):
            raise ValueError("A contagem gravada não corresponde ao lote; treinamento interrompido.")
        modelo = treinar_modelo(linhas, camara_id=3, termometro_id=3,
                               cadencia_segundos=300, inicio_coleta=inicio, horizontes_minutos=[30])
        modelo = modelo.model_copy(update={"lote_simulacao": lote})
        salvar_modelo(modelo)
        with closing(get_conn()) as conexao, conexao.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM tb_leitura_temperatura WHERE id = ANY(%s) AND cod_alerta IS NOT NULL", (ids,))
            alertas = cursor.fetchone()[0]
        return {"lote": str(lote), "leituras": len(linhas), "leituras_com_alerta": alertas,
                "modelo": modelo.model_dump(mode="json"), "manifesto": str(manifesto)}
    finally:
        restaurar_usuario_contexto(token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usuario-id", type=int, required=True)
    parser.add_argument("--lote", type=UUID, required=True)
    parser.add_argument("--fim", required=True, help="Horário ISO com fuso; representa medição sintética, não coleta real.")
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--confirmar-bancos-de-teste", action="store_true", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(executar_lote(args.usuario_id, args.lote, args.fim, args.worker), ensure_ascii=False, indent=2))
    except (ValueError, PermissionError) as erro:
        raise SystemExit(f"Simulação não concluída: {erro}") from None
    except Exception as erro:  # noqa: BLE001 -- fronteira CLI sanitiza erros de drivers externos
        # A saída administrativa não expõe URIs ou mensagens de driver com credenciais.
        raise SystemExit(f"Simulação não concluída ({type(erro).__name__}). Confira o manifesto antes de repetir.") from None


if __name__ == "__main__":
    main()
