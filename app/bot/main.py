"""
app/bot/main.py — Integración limpia de telegram.ext.Application con Flask.
Versión robusta para Webhooks usando asyncio.run() puro para cada update,
evitando choques entre hilos de Flask WSGI (Gunicorn) y el EventLoop.
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from app.config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET

logger = logging.getLogger(__name__)

_application: Application | None = None


def get_application() -> Application:
    """Retorna la instancia singleton de la Application."""
    global _application
    if _application is None:
        _application = (
            ApplicationBuilder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )
        from app.bot.handlers import register_handlers
        register_handlers(_application)
        logger.info("✅ Application de Telegram inicializada y handlers montados.")
    return _application


def process_update_sync(update_data: dict) -> None:
    """
    Procesa un Update crudo (JSON) que viene del webhook de Flask.
    Inyectamos el trabajo en un event loop temporal para manejar asincronía limpiamente
    sin usar threads persistentes o colas raras.
    """
    app = get_application()

    async def _process_update() -> None:
        """Inicia y detiene la app limpiamente si no lo estaba, luego procesa."""
        if not app.bot_data.get("_initialized"):
            await app.initialize()
            await app.start()
            app.bot_data["_initialized"] = True

        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)

    try:
        # En Python 3.7+, asyncio.run crea un loop, corre la corutina y lo cierra.
        # Es perfecto para handlers bloqueantes de Flask.
        asyncio.run(_process_update())
    except Exception as e:
        logger.error(f"❌ Error procesando update de Telegram: {e}")


def setup_webhook_sync() -> None:
    """Configura el webhook en TG, bloqueando el hilo actual."""
    if not WEBHOOK_URL:
        logger.warning("⚠️ WEBHOOK_URL no configurado. El bot no recibirá mensajes vía push.")
        return

    app = get_application()
    webhook_full_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"

    async def _set_wh():
        if not app.bot_data.get("_initialized"):
            await app.initialize()
            app.bot_data["_initialized"] = True

        await app.bot.set_webhook(
            url=webhook_full_url,
            secret_token=WEBHOOK_SECRET,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
        info = await app.bot.get_webhook_info()
        logger.info(f"✅ Webhook ACTIVO: {info.url}")

    try:
        asyncio.run(_set_wh())
    except Exception as e:
        logger.error(f"❌ Error al configurar webhook: {e}")


def start_bot_app():
    """Para compatibilidad con `run.py`, no necesitamos arrancar polling acá."""
    logger.info("ℹ️ start_bot_app ignorado en modo webhook (lazily loaded en _process_update).")
