"""
run.py — Punto de entrada de la aplicación.
Usa la estructura recomendada por PTB v21+ para Flask Webhooks.

Despliegue:
  gunicorn run:flask_app --worker-class gthread --workers 1 --threads 4
"""
import logging
from app.api.main import flask_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Flask y los componentes del bot se inicializarán al importar `app.api.main`
# (o cuando Gunicorn importe `flask_app` desde aquí).

if __name__ == "__main__":
    from app.config import PORT, DEBUG
    logger.info(f"▶ Servidor Flask en http://0.0.0.0:{PORT} (debug={DEBUG})")
    flask_app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)
