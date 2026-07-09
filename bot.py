"""Bot de Telegram (polling) que responde preguntas sobre la normativa de
pavimentacion del MINVU usando el motor RAG.

Ejecutar con: python bot.py
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import config
import rag_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola. Soy un asistente tecnico sobre el Codigo de Normas y Especificaciones "
        "Tecnicas de Obras de Pavimentacion del MINVU. Preguntame lo que necesites."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = update.message.text
    await update.message.chat.send_action("typing")
    try:
        answer = await asyncio.to_thread(rag_engine.answer_question, question)
    except Exception:
        log.exception("Fallo respondiendo la pregunta: %s", question)
        answer = "Ocurrio un error procesando tu pregunta. Intenta de nuevo en un momento."
    await update.message.reply_text(answer)


def main() -> None:
    config.validate_env()
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Bot iniciado (polling)...")
    # allowed_updates explicito: si Telegram quedo con un filtro viejo (ej. solo
    # callback_query) de un uso anterior de este token, run_polling() sin este
    # parametro NO lo resetea y los mensajes de texto se descartan en silencio.
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
