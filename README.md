# Agente RAG — Normativa de Pavimentación MINVU (Challenge Alura Latam)

Agente conversacional por Telegram que responde preguntas técnicas basándose
**estrictamente** en el Código de Normas y Especificaciones Técnicas de Obras de
Pavimentación del MINVU, usando una arquitectura RAG (Retrieval-Augmented Generation)
sobre Google Gemini.

## Arquitectura

El sistema tiene dos flujos completamente independientes: uno de **indexación**
(offline, se corre una vez o cada vez que cambia el PDF fuente) y uno de **consulta**
(online, se ejecuta en cada pregunta que llega por Telegram).

```
                         ── INDEXACION (ingest.py) ──

normativa_pavimentacion.pdf
        │  pdfplumber: extraccion de texto pagina por pagina
        ▼
   chunks de 1000 caracteres, 200 de overlap, con pagina de origen
        │  Gemini gemini-embedding-001 (task_type=RETRIEVAL_DOCUMENT), en lotes de 20
        ▼
   ChromaDB (persistente, local, carpeta chroma_db/)


                         ── CONSULTA (bot.py) ──

Usuario (Telegram) ──pregunta de texto──▶ bot.py (python-telegram-bot, polling)
                                              │
                                              ▼
                          Gemini gemini-embedding-001 (task_type=RETRIEVAL_QUERY)
                                              │
                                              ▼
                     busqueda semantica en ChromaDB → top-5 chunks mas relevantes
                                              │
                                              ▼
                 prompt con el contexto recuperado ──▶ Gemini 2.5 Flash ──▶ respuesta
                                              │
                                              ▼
                                Usuario (Telegram) ◀── respuesta
```

**Decisiones de diseño relevantes:**
- **Embeddings asimétricos:** se usa `task_type=RETRIEVAL_DOCUMENT` al indexar y
  `task_type=RETRIEVAL_QUERY` al buscar — es el modo recomendado por Google para
  maximizar la calidad del retrieval en escenarios de pregunta/respuesta.
- **Guardrail estricto en el prompt:** el modelo recibe la instrucción explícita de
  responder *solo* con el contexto recuperado, y de declarar abiertamente cuando la
  norma no cubre lo preguntado, en vez de inventar una respuesta plausible pero falsa.
- **No bloquear al usuario:** las llamadas a ChromaDB y Gemini son sincrónicas, así que
  `bot.py` las corre con `asyncio.to_thread` para no congelar el loop de eventos del bot
  mientras responde a otros usuarios en simultáneo.

## Flujo de procesamiento del PDF (RAG)

1. **Extracción** (`pdfplumber`): se abre el PDF y se extrae el texto página por página,
   conservando el número de página de cada fragmento.
2. **Chunking con overlap**: todo el texto se concatena y se recorre con una ventana
   deslizante de `CHUNK_SIZE=1000` caracteres y `CHUNK_OVERLAP=200` — el overlap evita que
   un concepto quede cortado justo en el borde entre dos chunks. Cada chunk conserva la
   página donde comienza, para poder trazar de qué parte de la norma salió cada respuesta.
3. **Embeddings en lote**: los chunks se agrupan de a `EMBEDDING_BATCH_SIZE=20` y se
   convierten a vectores de 768 dimensiones con `gemini-embedding-001`.
4. **Indexación**: los vectores, el texto original y la metadata (número de página) se
   cargan a una colección persistente de ChromaDB.
5. **Consulta**: la pregunta del usuario se embebe con el mismo modelo (modo
   `RETRIEVAL_QUERY`) y se buscan los 5 chunks más similares por distancia vectorial.
6. **Generación acotada**: los chunks recuperados arman el contexto de un prompt que
   fuerza a Gemini 2.5 Flash a responder solo con esa información.

**Corrida real de referencia** (con el PDF oficial del MINVU): 340 páginas extraídas →
1525 chunks indexados, sin errores, en un par de minutos.

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
5. Abrí Telegram y hablale al bot. Ejemplo real de interacción:

   > **Usuario:** ¿Cuáles son los requisitos de compactación para la sub-base granular?
   >
   > **Bot:** La compactación de la subbase granular se realizará por medios mecánicos
   > hasta obtener un 95% de la densidad máxima seca determinada por el ensayo Proctor
   > Modificado (NCh 1534/2) o de 80% de la densidad relativa (NCh 1726), según
   > corresponda. Además, la disposición de materiales de subbase colocados deberá
   > presentar una compactación homogénea, que no muestre nidos de piedra o depresiones.

   Y si se pregunta algo fuera de la norma (ej. "¿cuál es la capital de Francia?"), el bot
   responde explícitamente que no posee esa información en la norma actual, en vez de
   inventar una respuesta.

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

## Auto-evaluación del proyecto

> Nota: esta sección es un checklist propio, honesto, de qué implementa efectivamente
> este repositorio — **no es la rúbrica oficial del Challenge Alura Latam**. Si contás
> con el brief/rúbrica oficial, reemplazá esta sección por los criterios reales.

| Aspecto | Estado |
|---|---|
| Extracción y chunking del PDF con overlap | ✅ Implementado y probado (340 páginas → 1525 chunks) |
| Base vectorial persistente local | ✅ ChromaDB, con metadata de página por chunk |
| Embeddings con modelo vigente de Google | ✅ `gemini-embedding-001` (GA), no el deprecado `text-embedding-004` |
| Generación acotada al contexto (anti-alucinación) | ✅ Verificado con pregunta dentro y fuera de la norma |
| Interfaz conversacional funcional | ✅ Bot de Telegram probado en vivo, respuestas correctas |
| Manejo de errores en la conversación | ✅ Try/except en el handler, no crashea ante fallos puntuales |
| Configuración vía variables de entorno, sin credenciales hardcodeadas | ✅ `.env` + `.env.example`, `.gitignore` verificado antes del primer commit |
| Control de versiones con historial limpio | ✅ Repo en GitHub, working tree limpio |
| Despliegue en OCI | ⏳ Pendiente — solo notas preliminares en este README |
| Migración a webhook para producción | ⏳ Pendiente — actualmente corre en modo polling |
