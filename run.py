"""
run.py — Punto de entrada de la aplicación.
Inicia todos los componentes de la arquitectura del bot (Webhook, Scheduler, etc.)
y exporta o levanta el servidor Flask.
"""
import logging
import os
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Semáforo para asegurarnos de que el bootstrap corre una sola vez
_bootstrapped = False
_boot_lock = threading.Lock()


def _bootstrap():
    """Inicializa Firebase, Webhooks de Telegram y el Scheduler de tareas en 2do plano."""
    global _bootstrapped
    with _boot_lock:
        if _bootstrapped:
            return
        
        logger.info("🔥 Inicializando Firebase...")
        try:
            from app.services import firebase_db  # noqa: F401
            logger.info("✅ Firebase listo.")
        except Exception as e:
            logger.error(f"❌ Firebase no pudo inicializarse: {e}")

        logger.info("🔗 Configurando webhook de Telegram...")
        try:
            from app.bot.main import setup_webhook_sync
            setup_webhook_sync()
        except Exception as e:
            logger.error(f"❌ Error configurando webhook: {e}")

        logger.info("⏰ Iniciando Scheduler en segundo plano...")
        try:
            from app.worker.scheduler import start_scheduler
            start_scheduler()
            logger.info("✅ Scheduler activo.")
        except Exception as e:
            logger.error(f"❌ Error iniciando scheduler: {e}")

        _bootstrapped = True
        logger.info("🚀 Bootstrap completado con éxito.")


# 1. Ejecutar el bootstrap al cargar este archivo
_bootstrap()

# 2. Exportar la app para Gunicorn (usado si el Start Command es: gunicorn run:flask_app)
from app.api.main import flask_app  # noqa: E402


# 3. Arranque directo (usado si el Start Command es: python run.py)
if __name__ == "__main__":
    from app.config import PORT, DEBUG
    logger.info(f"▶ Arrancando servidor Flask en el puerto {PORT}...")
    
    # En Render, a veces flask.run() falla en reportar el puerto. 
    # Es mucho mejor usar un servidor WSGI de producción, pero lo dejamos como fallback.
    flask_app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)
