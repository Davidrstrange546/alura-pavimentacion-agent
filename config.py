"""Configuracion centralizada del agente RAG de normativa de pavimentacion MINVU."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

PDF_PATH = BASE_DIR / "data" / "normativa_pavimentacion.pdf"
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "normativa_pavimentacion"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_BATCH_SIZE = 20

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_OUTPUT_DIMENSIONALITY = 768
CHAT_MODEL = "gemini-2.5-flash"
TOP_K_RESULTS = 5

SYSTEM_PROMPT_TEMPLATE = (
    "Eres un asistente tecnico experto en la normativa de pavimentacion del MINVU.\n"
    "Responde la siguiente pregunta utilizando SOLO el contexto provisto a continuacion, "
    "extraido del Codigo de Normas y Especificaciones Tecnicas de Obras de Pavimentacion "
    "del MINVU. Si la respuesta no esta en el contexto, di explicitamente que no posees "
    "esa informacion en la norma actual — no inventes ni completes con conocimiento "
    "externo.\n\nContexto:\n{context}\n\nPregunta: {question}\n\nRespuesta:"
)


def validate_env() -> None:
    """Falla temprano y con mensaje claro si falta configuracion obligatoria."""
    missing = [name for name, value in [
        ("GEMINI_API_KEY", GEMINI_API_KEY),
        ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
    ] if not value]
    if missing:
        raise RuntimeError(
            f"Faltan variables de entorno: {', '.join(missing)}. "
            f"Configuralas en '{BASE_DIR / '.env'}' antes de continuar."
        )
