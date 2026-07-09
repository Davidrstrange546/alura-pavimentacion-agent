"""Motor RAG: busqueda semantica en ChromaDB + generacion de respuesta con Gemini."""

import logging

import chromadb
from google import genai
from google.genai import types

import config

log = logging.getLogger(__name__)

_client: genai.Client | None = None
_collection = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        _collection = chroma_client.get_collection(config.COLLECTION_NAME)
    return _collection


def embed_query(question: str) -> list[float]:
    client = _get_client()
    response = client.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=[question],
        config=types.EmbedContentConfig(
            output_dimensionality=config.EMBEDDING_OUTPUT_DIMENSIONALITY,
            task_type="RETRIEVAL_QUERY",
        ),
    )
    return response.embeddings[0].values


def retrieve_relevant_chunks(question: str, top_k: int = config.TOP_K_RESULTS) -> list[dict]:
    query_embedding = embed_query(question)
    collection = _get_collection()
    result = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    chunks = []
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    for text, metadata in zip(documents, metadatas):
        chunks.append({"text": text, "page": metadata.get("page")})
    return chunks


def build_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(f"[Pagina {c['page']}]\n{c['text']}" for c in chunks)
    return config.SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question)


def answer_question(question: str) -> str:
    chunks = retrieve_relevant_chunks(question)
    if not chunks:
        return "No poseo esa informacion en la norma actual."

    prompt = build_prompt(question, chunks)
    client = _get_client()
    response = client.models.generate_content(
        model=config.CHAT_MODEL,
        contents=prompt,
    )
    return response.text
