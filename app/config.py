from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# A variavel especifica do Skadi prevalece quando o processo tambem carrega
# chaves de outro projeto para teste de provedores de IA.
DATABASE_URL = os.getenv("POSTGRES_URL_SEGUNDO") or os.getenv("DATABASE_URL")
MONGODB_URI = os.getenv("MONGODB_URI")
REDIS_URL = os.getenv("REDIS_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def autenticacao_mock_habilitada() -> bool:
    """Indica se a autenticacao simulada foi ativada explicitamente no ambiente."""

    return os.getenv("SKADI_MOCK_AUTH_ENABLED", "false").strip().lower() == "true"


def configuracoes_ausentes() -> list[str]:
    """Lista configuracoes necessarias que ainda nao foram fornecidas."""

    configuracoes = {
        "DATABASE_URL": DATABASE_URL,
        "MONGODB_URI": MONGODB_URI,
        "REDIS_URL": REDIS_URL,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "GROQ_API_KEY": GROQ_API_KEY,
    }
    return [nome for nome, valor in configuracoes.items() if not valor]
