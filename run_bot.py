"""
run_bot.py — Runner local del bot usando POLLING (sin webhook, sin Render).
Úsalo para probar el bot en tu PC directamente.

Ejecutar:
    python run_bot.py
"""
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8488189037:AAH8XEkrOTXEWhBwhf2F4IPbm1hCzImBE-E"


def main():
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        filters,
    )

    logger.info("🤖 Iniciando bot en modo POLLING...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # ── Intentar cargar Firebase (opcional para pruebas) ──────────────────────
    firebase_ok = False
    try:
        import firebase_admin
        from firebase_admin import credentials, db as rtdb
        if not firebase_admin._apps:
            cred_path = "firebase_credentials.json"
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {
                    "databaseURL": "https://bot-apoyo-erradicacion-vicios-default-rtdb.firebaseio.com"
                })
                firebase_ok = True
                logger.info("✅ Firebase conectado correctamente.")
            else:
                logger.warning("⚠️  firebase_credentials.json no encontrado. "
                               "El bot responderá pero NO guardará datos en Firebase.")
    except Exception as e:
        logger.warning(f"⚠️  Firebase no disponible: {e}")

    # ── Registrar handlers ────────────────────────────────────────────────────
    if firebase_ok:
        from app.bot.handlers import register_handlers
        register_handlers(app)
        logger.info("✅ Handlers completos cargados (con Firebase).")
    else:
        _register_basic_handlers(app)
        logger.info("✅ Handlers básicos cargados (sin Firebase).")

    logger.info("🚀 Bot corriendo. Escribe /start en Telegram...")
    logger.info("   Presiona Ctrl+C para detener.")

    # PTB v20+ usa run_polling() de forma síncrona
    app.run_polling(drop_pending_updates=True)


def _register_basic_handlers(app):
    """
    Handlers básicos que funcionan SIN Firebase.
    Perfectos para probar que el bot recibe mensajes.
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.constants import ParseMode
    from telegram.ext import (
        CommandHandler, CallbackQueryHandler, MessageHandler,
        ContextTypes, filters,
    )

    VICIOS_BASICO = [
        ("🚬 Cigarros",          "v_Cigarros"),
        ("🍺 Alcohol",           "v_Alcohol"),
        ("🌿 Marihuana",         "v_Marihuana"),
        ("💊 Cocaína / Crack",   "v_Cocaina"),
        ("🎰 Apuestas",          "v_Apuestas"),
        ("☕ Cafeína",           "v_Cafeina"),
        ("💊 Benzodiacepinas",   "v_Benzo"),
        ("📱 Adicción Digital",  "v_Digital"),
        ("🍽️ T. Alimenticios",   "v_Alimenticios"),
        ("✏️ Otro hábito",       "v_Otro"),
    ]

    def _kb_vicios():
        rows = []
        for i in range(0, len(VICIOS_BASICO), 2):
            row = [InlineKeyboardButton(VICIOS_BASICO[i][0], callback_data=VICIOS_BASICO[i][1])]
            if i + 1 < len(VICIOS_BASICO):
                row.append(InlineKeyboardButton(VICIOS_BASICO[i+1][0], callback_data=VICIOS_BASICO[i+1][1]))
            rows.append(row)
        return InlineKeyboardMarkup(rows)

    def _kb_duracion():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("5 meses", callback_data="d_5"),
             InlineKeyboardButton("6 meses", callback_data="d_6"),
             InlineKeyboardButton("7 meses", callback_data="d_7"),
             InlineKeyboardButton("8 meses", callback_data="d_8")],
            [InlineKeyboardButton("9 meses",  callback_data="d_9"),
             InlineKeyboardButton("10 meses", callback_data="d_10"),
             InlineKeyboardButton("11 meses", callback_data="d_11"),
             InlineKeyboardButton("12 meses", callback_data="d_12")],
        ])

    def _kb_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Misiones",     callback_data="m_misiones"),
             InlineKeyboardButton("📊 Progreso",     callback_data="m_progreso")],
            [InlineKeyboardButton("🆘 Pedir ayuda",  callback_data="m_ayuda"),
             InlineKeyboardButton("🌬️ Respirar",     callback_data="m_respirar")],
            [InlineKeyboardButton("⚠️ Reportar recaída", callback_data="m_recaida")],
        ])

    # Estado temporal en memoria (solo para pruebas, no persiste)
    _estado = {}

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        nombre = update.effective_user.first_name or "amigo/a"
        uid = str(update.effective_user.id)
        _estado[uid] = {"nombre": nombre, "vicio": None, "meses": None}
        await update.message.reply_text(
            f"🌟 *¡Hola, {nombre}!*\n\n"
            "Has dado un paso enorme al estar aquí.\n"
            "Este bot te acompañará en tu proceso de cambio, día a día.\n\n"
            "Primero dime, ¿qué hábito o vicio quieres superar?",
            reply_markup=_kb_vicios(),
            parse_mode=ParseMode.MARKDOWN,
        )

    async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Comandos disponibles:*\n\n"
            "/start — Iniciar el plan\n"
            "/progreso — Ver tu progreso\n"
            "/misiones — Ver misiones del día\n"
            "/recaida — Reportar una recaída\n"
            "/ayuda — Pedir apoyo ahora\n"
            "/help — Este menú",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def progreso_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        datos = _estado.get(uid, {})
        nombre = datos.get("nombre", update.effective_user.first_name or "amigo/a")
        vicio = datos.get("vicio", "no configurado")
        await update.message.reply_text(
            f"📊 *Tu progreso, {nombre}*\n\n"
            f"🎯 Vicio: {vicio}\n"
            f"🔥 Racha: 0 días (modo prueba — sin Firebase)\n"
            f"⭐ XP: 0 (modo prueba)\n"
            f"🏅 Nivel: 1 — Iniciado",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_kb_menu(),
        )

    async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        data = q.data
        uid = str(q.from_user.id)
        nombre = q.from_user.first_name or "amigo/a"

        if data.startswith("v_"):
            vicio = data[2:]
            if uid not in _estado:
                _estado[uid] = {}
            _estado[uid]["vicio"] = vicio
            await q.edit_message_text(
                f"✅ Vas a superar: *{vicio}*\n\n¿Cuánto tiempo durará tu plan?",
                reply_markup=_kb_duracion(),
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data.startswith("d_"):
            meses = data[2:]
            if uid not in _estado:
                _estado[uid] = {}
            _estado[uid]["meses"] = meses
            vicio = _estado.get(uid, {}).get("vicio", "tu hábito")
            await q.edit_message_text(
                f"🎯 *¡Bienvenido/a a tu plan, {nombre}!*\n\n"
                f"Has decidido enfrentar: *{vicio}*\n"
                f"Duración del plan: *{meses} meses*\n\n"
                "Esto no será fácil, pero tampoco imposible.\n"
                "Cada día sin caer es una victoria.\n\n"
                "🌟 _Tu futuro yo ya te está agradeciendo._\n\n"
                "⚠️ *Nota:* Estás en modo prueba sin Firebase.\n"
                "Los datos no se guardan aún.",
                parse_mode=ParseMode.MARKDOWN,
            )
            await q.message.reply_text(
                f"¿Qué quieres hacer ahora, *{nombre}*?",
                reply_markup=_kb_menu(),
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data == "m_respirar":
            await q.message.reply_text(
                "🌬️ *Ejercicio de respiración 4-7-8:*\n\n"
                "1. Inhala por la nariz *4 segundos*\n"
                "2. Mantén el aire *7 segundos*\n"
                "3. Exhala lentamente *8 segundos*\n\n"
                "Repite 3 veces. Esto calma tu sistema nervioso. 💙",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data == "m_ayuda":
            await q.message.reply_text(
                "🆘 Entiendo que es difícil ahora mismo.\n\n"
                "💙 La ansiedad es temporal. El impulso dura minutos. Tu bienestar dura toda la vida.\n\n"
                "Respira profundo. Bebe agua. Aléjate del gatillo 15 minutos.\n"
                "Puedes con esto. 💪",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data == "m_misiones":
            await q.message.reply_text(
                "📋 *Misiones de hoy:*\n\n"
                "1. 💧 Bebe agua — +5 XP\n"
                "2. 🚶 Camina 10 minutos — +10 XP\n"
                "3. ✍️ Escribe 3 razones para continuar — +15 XP\n\n"
                "_Conecta Firebase para guardar tu progreso._",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data == "m_progreso":
            vicio = _estado.get(uid, {}).get("vicio", "no configurado")
            await q.message.reply_text(
                f"📊 Progreso:\n\n🎯 Vicio: {vicio}\n🔥 Racha: 0 días\n⭐ XP: 0\n"
                "_Modo prueba sin Firebase_",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif data == "m_recaida":
            await q.message.reply_text(
                "💙 Una recaída no es el final.\n\n"
                "Es una señal de que el camino sigue.\n"
                "Lo que importa es volver a levantarse.\n\n"
                "¿Qué pasó? Escríbeme cómo te sientes.",
                parse_mode=ParseMode.MARKDOWN,
            )

    async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        nombre = update.effective_user.first_name or "amigo/a"
        risk_words = ["ansiedad","ganas","impulso","recaída","estrés","fumar",
                      "beber","apostar","no aguanto","caer","tentación"]
        text = update.message.text.lower()
        if any(w in text for w in risk_words):
            await update.message.reply_text(
                f"💙 {nombre}, entiendo que estás pasando un momento difícil.\n\n"
                "Respira. Esto también pasará.\n\n"
                "¿Quieres activar el modo de apoyo?",
                reply_markup=_kb_menu(),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                f"👋 Hola {nombre}. Usa /start para comenzar o /help para ver los comandos.",
            )

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("help",     help_cmd))
    app.add_handler(CommandHandler("progreso", progreso_cmd))
    app.add_handler(CommandHandler("misiones", lambda u, c: u.message.reply_text("Usa /start primero.")))
    app.add_handler(CommandHandler("recaida",  lambda u, c: u.message.reply_text("💙 Reportar recaída: /start para activar tu plan.")))
    app.add_handler(CommandHandler("ayuda",    lambda u, c: u.message.reply_text("🆘 Estoy aquí. Respira. 💙")))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))


if __name__ == "__main__":
    main()
