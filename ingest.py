"""Pipeline de ingesta: extrae texto del PDF, lo segmenta en chunks con overlap,
genera embeddings con Gemini (gemini-embedding-001) y los carga en ChromaDB.

Ejecutar con: python ingest.py
"""

import logging

import chromadb
import pdfplumber
from google import genai
from google.genai import types

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _extract_pages(pdf_path) -> list[tuple[int, str]]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append((i, text))
            # pdfplumber cachea objetos de layout por pagina; sin liberarlos la
            # memoria crece con cada pagina y en PDFs grandes (340 pags) puede
            # agotar la RAM de una VM chica. page.close() libera esa cache.
            page.close()
    return pages


def _build_chunks(pages: list[tuple[int, str]]) -> list[dict]:
    """Concatena el texto de todas las paginas y desliza una ventana de CHUNK_SIZE
    caracteres con CHUNK_OVERLAP de superposicion, conservando la pagina de origen
    de cada chunk (para poder citarla despues en las respuestas del bot)."""
    full_text = ""
    offset_to_page: list[tuple[int, int]] = []
    for page_num, text in pages:
        offset_to_page.append((len(full_text), page_num))
        full_text += text + "\n"

    def _page_for_offset(offset: int) -> int:
        page = offset_to_page[0][1]
        for start_offset, page_num in offset_to_page:
            if start_offset > offset:
                break
            page = page_num
        return page

    chunks = []
    step = config.CHUNK_SIZE - config.CHUNK_OVERLAP
    start = 0
    while start < len(full_text):
        end = min(start + config.CHUNK_SIZE, len(full_text))
        chunk_text = full_text[start:end].strip()
        if chunk_text:
            chunks.append({"text": chunk_text, "page": _page_for_offset(start)})
        if end == len(full_text):
            break
        start += step
    return chunks


def _get_client() -> genai.Client:
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _embed_batch(client: genai.Client, texts: list[str]) -> list[list[float]]:
    response = client.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            output_dimensionality=config.EMBEDDING_OUTPUT_DIMENSIONALITY,
            task_type="RETRIEVAL_DOCUMENT",
        ),
    )
    return [e.values for e in response.embeddings]


def run_ingest() -> int:
    config.validate_env()
    if not config.PDF_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro el PDF en '{config.PDF_PATH}'. "
            f"Coloca 'normativa_pavimentacion.pdf' en la carpeta 'data/' antes de continuar."
        )

    log.info("Extrayendo texto de %s...", config.PDF_PATH.name)
    pages = _extract_pages(config.PDF_PATH)
    log.info("Extraidas %d paginas.", len(pages))

    chunks = _build_chunks(pages)
    log.info("Generados %d chunks (tamano=%d, overlap=%d).",
              len(chunks), config.CHUNK_SIZE, config.CHUNK_OVERLAP)

    client = _get_client()
    chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    existing_names = [c.name for c in chroma_client.list_collections()]
    if config.COLLECTION_NAME in existing_names:
        chroma_client.delete_collection(config.COLLECTION_NAME)
    collection = chroma_client.create_collection(config.COLLECTION_NAME)

    for i in range(0, len(chunks), config.EMBEDDING_BATCH_SIZE):
        batch = chunks[i:i + config.EMBEDDING_BATCH_SIZE]
        texts = [c["text"] for c in batch]
        embeddings = _embed_batch(client, texts)
        collection.add(
            ids=[f"chunk-{i + j}" for j in range(len(batch))],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"page": c["page"]} for c in batch],
        )
        log.info("Indexados chunks %d-%d de %d...", i + 1, i + len(batch), len(chunks))

    log.info("Ingesta completa: %d chunks indexados en '%s'.", len(chunks), config.CHROMA_DIR)
    return len(chunks)


if __name__ == "__main__":
    run_ingest()
