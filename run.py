"""
run.py — Punto de entrada de la aplicación.
Inicia Flask + APScheduler + configura el webhook de Telegram.
"""
import asyncio
import logging

from app.api.main import flask_app
from app.bot.main import setup_webhook
from app.worker.scheduler import start_scheduler
from app.config import PORT, DEBUG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # 1. Iniciar la Application del bot de Telegram en su propio loop
    logger.info("Iniciando componentes del bot...")
    from app.bot.main import start_bot_app, setup_webhook, get_bot_loop
    start_bot_app()
    
    # 2. Configurar webhook en Telegram
    logger.info("Configurando webhook de Telegram...")
    try:
        loop = get_bot_loop()
        asyncio.run_coroutine_threadsafe(setup_webhook(), loop).result()
    except Exception as e:
        logger.error(f"Error configurando webhook: {e}")

    # 2. Iniciar el scheduler en segundo plano
    start_scheduler()

    # 3. Iniciar Flask
    logger.info(f"Iniciando servidor Flask en puerto {PORT}...")
    flask_app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)


if __name__ == "__main__":
    main()
