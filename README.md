# Agente RAG — Normativa de Pavimentación MINVU (Challenge Alura Latam)

Agente conversacional por Telegram que responde preguntas técnicas basándose
**estrictamente** en el Código de Normas y Especificaciones Técnicas de Obras de
Pavimentación del MINVU, usando una arquitectura RAG (Retrieval-Augmented Generation).

## Arquitectura

```
normativa_pavimentacion.pdf
        │  (pdfplumber: extraccion por pagina)
        ▼
   chunks (1000 caracteres, 200 de overlap, con pagina de origen)
        │  (Gemini gemini-embedding-001, task_type=RETRIEVAL_DOCUMENT)
        ▼
   ChromaDB (persistente, local)

Usuario (Telegram) ──pregunta──▶ bot.py
                                    │  (Gemini gemini-embedding-001, task_type=RETRIEVAL_QUERY)
                                    ▼
                          busqueda semantica en ChromaDB (top-5 chunks)
                                    │
                                    ▼
                    prompt con contexto ──▶ Gemini 2.5 Flash ──▶ respuesta
                                    │
                                    ▼
                           Usuario (Telegram) ◀── respuesta
```

El prompt fuerza al modelo a responder **solo** con el contexto recuperado, y a admitir
explícitamente cuando la norma no cubre lo preguntado (sin inventar información).

## Requisitos del Challenge Alura Latam

Proyecto desarrollado para el Challenge Alura Latam de agentes IA: agente RAG conectado
a Telegram, con plan de despliegue en Oracle Cloud Infrastructure (OCI).

## Instrucciones de uso

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

1. Completa `.env` (o copiá `.env.example`) con `GEMINI_API_KEY` y `TELEGRAM_BOT_TOKEN`.
2. Coloca el PDF real en `data/normativa_pavimentacion.pdf`.
3. Corre la ingesta una sola vez (o cada vez que cambie el PDF):
   ```bash
   python ingest.py
   ```
4. Levanta el bot:
   ```bash
   python bot.py
   ```
5. Hablale al bot desde Telegram.

## Despliegue en OCI (preliminar)

Pendiente como paso posterior. Notas iniciales:
- Migrar el bot de polling a webhook (requiere HTTPS público — certificado + dominio o
  balanceador de OCI).
- Empaquetar como servicio systemd o contenedor en una instancia Compute de OCI.
- `chroma_db/` debe persistir en un volumen del compute (no se versiona en git).

## Estructura del repositorio

- `config.py` — configuración centralizada (modelos, chunking, límites, prompt).
- `ingest.py` — pipeline de ingesta del PDF a ChromaDB.
- `rag_engine.py` — búsqueda semántica + generación de respuesta.
- `bot.py` — interfaz de Telegram (polling).
- `data/` — PDF fuente de la normativa.
- `chroma_db/` — base vectorial persistente (gitignored, se genera con `ingest.py`).
