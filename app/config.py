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

# ─── Username del bot (para deep links de invitación) ─────────────────────────
# En Render, configura la variable BOT_USERNAME con el username real de tu bot sin @
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "Synapse_ftp_bot")

# ─── Firebase Realtime Database ───────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
FIREBASE_DATABASE_URL: str = "https://synapse-ftp-default-rtdb.firebaseio.com/"

# ─── Flask ───────────────────────────────────────────────────────────────────
FLASK_SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "RenovaBot_Flask_Key_2026_Panel_Admin")
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
PORT: int = int(os.getenv("PORT", 10000))

# ─── Lógica de negocio ───────────────────────────────────────────────────────
MAX_HELPERS: int = 2
MIN_PLAN_MONTHS: int = 5
MAX_PLAN_MONTHS: int = 12
INVITATION_EXPIRY_HOURS: int = 72

# ─── Horario nocturno (hora UTC) ──────────────────────────────────────────────
# UTC-6 (México/Centro): 22:00 local = 04:00 UTC | 06:00 local = 12:00 UTC
# Ajusta con tus variables de entorno NIGHT_START_UTC / NIGHT_END_UTC si es otra zona
NIGHT_START_UTC: int = int(os.getenv("NIGHT_START_UTC", "4"))   # 22:00 UTC-6 → 04:00 UTC
NIGHT_END_UTC: int   = int(os.getenv("NIGHT_END_UTC",   "12"))  # 06:00 UTC-6 → 12:00 UTC

# ─── Recordatorios de medicamentos (hora UTC) ─────────────────────────────────
# 7:00 AM UTC-6 = 13:00 UTC | 7:10 AM UTC-6 = 13:10 UTC
PILL_REMINDER_1_HOUR_UTC: int = int(os.getenv("PILL_1_HOUR_UTC", "13"))
PILL_REMINDER_1_MIN_UTC: int  = int(os.getenv("PILL_1_MIN_UTC",  "0"))
PILL_REMINDER_1_NAME: str     = os.getenv("PILL_1_NAME", "Anciocrol")

PILL_REMINDER_2_HOUR_UTC: int = int(os.getenv("PILL_2_HOUR_UTC", "13"))
PILL_REMINDER_2_MIN_UTC: int  = int(os.getenv("PILL_2_MIN_UTC",  "10"))
PILL_REMINDER_2_NAME: str     = os.getenv("PILL_2_NAME", "Pasinerva")
