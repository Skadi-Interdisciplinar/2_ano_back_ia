from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# A variavel especifica do Skadi prevalece quando o processo tambem carrega
# chaves de outro projeto para teste de provedores de IA.
DATABASE_URL = os.getenv("POSTGRES_URL_SEGUNDO") or os.getenv("DATABASE_URL")
MONGODB_URI = os.getenv("MONGODB_URI")
REDIS_URL = os.getenv("REDIS_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Somente a configuração vetorial pode vir do ambiente de referência.
_assessor_env = os.getenv("ASSESSOR_ENV_FILE")
_referencia = dotenv_values(_assessor_env) if _assessor_env else {}
QDRANT_URL = os.getenv("QDRANT_URL") or _referencia.get("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or _referencia.get("QDRANT_API_KEY")
