"""
config.py — Configuración central del proyecto.
Las credenciales sensibles (token del bot) se pasan como variables de entorno
en el dashboard de Render. Las de Firebase están aquí directamente.
"""
import os

# ─── Telegram ────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8488189037:AAH8XEkrOTXEWhBwhf2F4IPbm1hCzImBE-E"
)
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")       # Se pone en Render dashboard
WEBHOOK_PATH: str = "/webhook/telegram"
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "RenovaBot_Webhook_Secret_2026")

# ─── Firebase Realtime Database ───────────────────────────────────────────────
# Credenciales del Admin SDK (archivo JSON de cuenta de servicio)
# Descárgalo desde: Firebase Console > Configuración > Cuentas de Servicio > Generar clave
FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
FIREBASE_DATABASE_URL: str = "https://bot-apoyo-erradicacion-vicios-default-rtdb.firebaseio.com"

# ─── Flask ───────────────────────────────────────────────────────────────────
FLASK_SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "RenovaBot_Flask_Key_2026_Panel_Admin")
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
PORT: int = int(os.getenv("PORT", 10000))

# ─── Lógica de negocio ───────────────────────────────────────────────────────
MAX_HELPERS: int = 2
MIN_PLAN_MONTHS: int = 5
MAX_PLAN_MONTHS: int = 12
INVITATION_EXPIRY_HOURS: int = 72
