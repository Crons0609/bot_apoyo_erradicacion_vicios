"""
app/bot/main.py — Inicialización y gestión del bot de Telegram.
Maneja un loop de asyncio dedicado para la Application de PTB.
Protegido para Webhooks y Render.
"""
import asyncio
import logging
import threading
from typing import Optional

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from app.config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET

logger = logging.getLogger(__name__)

_application: Optional[Application] = None
_bot_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """Crea un event loop dedicado en un hilo en segundo plano."""
    global _bot_loop
    if _bot_loop is not None and _bot_loop.is_running():
        return _bot_loop

    with _loop_lock:
        if _bot_loop is not None and _bot_loop.is_running():
            return _bot_loop

        loop = asyncio.new_event_loop()

        def _run_loop(lp: asyncio.AbstractEventLoop):
            asyncio.set_event_loop(lp)
            lp.run_forever()

        t = threading.Thread(target=_run_loop, args=(loop,), daemon=True, name="BotEventLoop")
        t.start()

        # Esperar a que arranque
        import time
        while not loop.is_running():
            time.sleep(0.01)

        _bot_loop = loop
        logger.info("✅ Event loop de Telegram en segundo plano creado.")
    return _bot_loop


def get_application() -> Application:
    """Crea y retorna la app singleton con los handlers registrados."""
    global _application
    if _application is None:
        _application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        from app.bot.handlers import register_handlers
        register_handlers(_application)
        logger.info("✅ Application (PTB) construida y handlers cargados.")
    return _application


def setup_webhook_sync() -> None:
    """Inicializa la app y luego configura el webhook (Run once)."""
    app = get_application()
    loop = _get_or_create_loop()
    webhook_full_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"

    async def _start_and_hook():
        # Inicializamos el bot (setup interno de PTB)
        if not app.bot_data.get("_initialized"):
            await app.initialize()
            await app.start()
            app.bot_data["_initialized"] = True

        if WEBHOOK_URL:
            await app.bot.set_webhook(
                url=webhook_full_url,
                secret_token=WEBHOOK_SECRET,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
            )
            logger.info(f"✅ Webhook configurado: {webhook_full_url}")
        else:
            logger.warning("⚠️ WEBHOOK_URL no configurado, modo manual asíncrono.")

    # Lanzamos el comando synchronously, esperando su fin (max 10s) 
    # para que la app ya esté lista cuando entren requests HTTP
    future = asyncio.run_coroutine_threadsafe(_start_and_hook(), loop)
    try:
        future.result(timeout=15)
    except Exception as e:
        logger.error(f"❌ Error configurando webhook: {e}")


def process_update_sync(update_data: dict) -> None:
    """Envía un update json a la aplicación sin bloquear Flask."""
    app = get_application()
    loop = _get_or_create_loop()

    async def _process():
        try:
            update = Update.de_json(update_data, app.bot)
            await app.process_update(update)
            logger.info(f"⚡ Update {update.update_id} enviado a PTB queue.")
        except Exception as e:
            logger.error(f"❌ Error interno procesando update: {e}", exc_info=True)

    # Fire-and-forget: metemos el update en la cola sin bloquear con .result()
    asyncio.run_coroutine_threadsafe(_process(), loop)
