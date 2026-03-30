"""
main.py — Inicialización del bot de Telegram.
Configura el bot con Webhook integrado en Flask.
"""
import logging
import asyncio
import threading
from telegram import Bot, Update
from telegram.ext import Application, ApplicationBuilder

from app.config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET

logger = logging.getLogger(__name__)

_application: Application | None = None
_bot_loop: asyncio.AbstractEventLoop | None = None


def get_application() -> Application:
    """Retorna la instancia singleton de la Application del bot."""
    global _application
    if _application is None:
        _application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        from app.bot.handlers import register_handlers
        register_handlers(_application)
        logger.info("✅ Bot de Telegram inicializado.")
    return _application


def get_bot_loop() -> asyncio.AbstractEventLoop:
    """Devuelve (y crea si no existe) un event loop dedicado para el bot."""
    global _bot_loop
    if _bot_loop is None:
        _bot_loop = asyncio.new_event_loop()
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        threading.Thread(target=start_loop, args=(_bot_loop,), daemon=True).start()
    return _bot_loop


def start_bot_app():
    """Inicializa la Application de Telegram en el bg loop."""
    app = get_application()
    loop = get_bot_loop()
    
    async def _init_app():
        await app.initialize()
        await app.start()
        
    asyncio.run_coroutine_threadsafe(_init_app(), loop).result()


async def setup_webhook() -> None:
    """Configura el webhook en los servidores de Telegram."""
    app = get_application()
    webhook_full_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    await app.bot.set_webhook(
        url=webhook_full_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=["message", "callback_query"],
    )
    logger.info(f"✅ Webhook configurado en: {webhook_full_url}")


def process_update_sync(data: dict):
    """Encola un update al bot loop desde una vista síncrona (Flask)."""
    app = get_application()
    loop = get_bot_loop()
    
    async def _process():
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        
    asyncio.run_coroutine_threadsafe(_process(), loop).result()

