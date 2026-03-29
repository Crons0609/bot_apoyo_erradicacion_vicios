"""
main.py — Inicialización del bot de Telegram.
Configura el bot con Webhook integrado en Flask.
"""
import logging
from telegram import Bot
from telegram.ext import Application, ApplicationBuilder

from app.config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBHOOK_SECRET

logger = logging.getLogger(__name__)

_application: Application | None = None


def get_application() -> Application:
    """Retorna la instancia singleton de la Application del bot."""
    global _application
    if _application is None:
        _application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        from app.bot.handlers import register_handlers
        register_handlers(_application)
        logger.info("✅ Bot de Telegram inicializado.")
    return _application


async def setup_webhook() -> None:
    """Configura el webhook en los servidores de Telegram."""
    app = get_application()
    webhook_full_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await app.bot.set_webhook(
        url=webhook_full_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=["message", "callback_query"],
    )
    logger.info(f"✅ Webhook configurado en: {webhook_full_url}")
