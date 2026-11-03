"""Execute na raiz: python -m scripts.indexar_regras_diagnostico."""

from app.regras_diagnostico import indexar_regras
from google.genai.errors import APIError
from httpx import HTTPError
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse


def main():
    try:
        quantidade = indexar_regras()
    except (RuntimeError, APIError, HTTPError, ResponseHandlingException, UnexpectedResponse) as erro:
        # Não imprimir exceções de SDKs: podem conter endereços e credenciais.
        raise SystemExit(f"Indexação não concluída ({type(erro).__name__}).") from None
    print(f"{quantidade} regras aprovadas indexadas.")


if __name__ == "__main__":
    main()

