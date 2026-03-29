"""
handlers.py — Handlers de comandos y callbacks para el bot de Telegram.
Implementa la máquina de estados de conversación del usuario.
"""
import logging
import random
from typing import Optional

from telegram import Update, Message
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from app.bot.keyboards import (
    kb_select_vicio,
    kb_select_duracion,
    kb_select_num_helpers,
    kb_main_menu,
    kb_mission_done,
    kb_relapse_confirm,
    kb_helper_actions,
    VICIOS,
)
from app.services import firebase_db as fdb
from app.services import messages as msg
from app.services.invitations import generate_invitation_links, register_as_helper
from app.services.relapse import handle_relapse, handle_recovery_start
from app.services.xp_system import add_xp, get_progress_summary, XP_MISION_COMPLETADA
from app.services.missions import get_daily_missions

logger = logging.getLogger(__name__)

# ─── Palabras clave de riesgo ─────────────────────────────────────────────────

RISK_KEYWORDS = [
    "ansiedad", "ganas", "impulso", "recaída", "estrés", "noche", "fumar",
    "beber", "apostar", "necesito", "no aguanto", "quiero caer", "tentación",
    "marihuana", "pastilla", "aposté", "fumé", "bebí", "caí",
]


# ─── Helpers internos ─────────────────────────────────────────────────────────

async def _get_or_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
    """
    Obtiene el usuario de Firebase. Si no existe, da la bienvenida con /start.
    """
    tg_user = update.effective_user
    user = fdb.get_user(str(tg_user.id))
    return user


async def _send_main_menu(message: Message, nombre: str) -> None:
    await message.reply_text(
        f"¿Qué quieres hacer ahora, *{nombre}*?",
        reply_markup=kb_main_menu(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── /start ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja el comando /start.
    Si viene con un arg de invitación (inv_TOKEN), activa el flujo de ayudante.
    Si no, inicia el flujo de registro del usuario principal.
    """
    tg_user = update.effective_user
    telegram_id = str(tg_user.id)
    args = context.args or []

    # ── Flujo de ayudante ─────────────────────────────────────────────────────
    if args and args[0].startswith("inv_"):
        token = args[0][4:]  # Quitar "inv_"
        try:
            result = register_as_helper(
                token=token,
                helper_telegram_id=telegram_id,
                helper_username=tg_user.username or "",
                helper_nombre=tg_user.first_name or "Ayudante",
            )
            principal = result["usuario_principal"]
            rol = result["rol"]
            await update.message.reply_text(
                f"✅ *¡Bienvenido/a, {tg_user.first_name}!*\n\n"
                f"Ahora eres *{rol}* de *{principal.get('nombre', 'tu compañero/a')}*.\n\n"
                "Tu misión es acompañar, escuchar y motivar. Sin juzgar.\n\n"
                "Recibirás avisos cuando necesite apoyo. ¡Gracias por estar ahí! 🤝",
                parse_mode=ParseMode.MARKDOWN,
            )
        except ValueError as e:
            await update.message.reply_text(f"⚠️ {str(e)}")
        return

    # ── Flujo de usuario principal ────────────────────────────────────────────
    existing_user = fdb.get_user(telegram_id)

    if existing_user and existing_user.get("estado_plan") not in ("configurando", None):
        nombre = existing_user.get("nombre", tg_user.first_name)
        await update.message.reply_text(
            f"👋 ¡Hola de nuevo, *{nombre}*! Tu plan ya está activo.\n"
            "Usa el menú para continuar tu camino.",
            reply_markup=kb_main_menu(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Crear usuario nuevo o reiniciar configuración
    fdb.create_user(
        telegram_id=telegram_id,
        username=tg_user.username or "",
        nombre=tg_user.first_name or "Amigo/a",
        foto_perfil="",  # Se podría obtener con getProfilePhotos
    )

    await update.message.reply_text(
        f"🌟 *¡Hola, {tg_user.first_name}!*\n\n"
        "Has dado un paso enorme al estar aquí.\n"
        "Este bot te acompañará en tu proceso de cambio, día a día.\n\n"
        "Primero dime, ¿qué hábito o vicio quieres superar?",
        reply_markup=kb_select_vicio(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── /help ───────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *Comandos disponibles:*\n\n"
        "/start — Iniciar o reiniciar el bot\n"
        "/estado — Ver tu estado actual\n"
        "/progreso — Ver tu progreso y XP\n"
        "/misiones — Ver misiones del día\n"
        "/recaida — Reportar una recaída\n"
        "/ayuda — Pedir apoyo ahora\n"
        "/configurar — Modificar tu plan\n"
        "/help — Ver este menú",
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── /estado ─────────────────────────────────────────────────────────────────

async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    user = await _get_or_welcome(update, context)
    if not user:
        await update.message.reply_text("Usa /start para comenzar.")
        return
    estado = user.get("estado_plan", "sin plan")
    racha = user.get("racha_dias", 0)
    vicio = user.get("vicio", "sin configurar")
    await update.message.reply_text(
        f"📋 *Tu estado actual:*\n\n"
        f"🎯 Vicio/Hábito: {vicio}\n"
        f"🔥 Racha: {racha} días\n"
        f"📌 Estado del plan: *{estado}*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main_menu(),
    )


# ─── /progreso ───────────────────────────────────────────────────────────────

async def cmd_progreso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    resumen = get_progress_summary(telegram_id)
    if not resumen:
        await update.message.reply_text("Usa /start para comenzar tu plan.")
        return
    await update.message.reply_text(resumen, parse_mode=ParseMode.MARKDOWN)


# ─── /misiones ───────────────────────────────────────────────────────────────

async def cmd_misiones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    user = fdb.get_user(telegram_id)
    if not user or user.get("estado_plan") not in ("activo", "recuperacion"):
        await update.message.reply_text("Tu plan no está activo. Usa /start.")
        return

    misiones = get_daily_missions(user.get("vicio", "general"), count=3)
    if not misiones:
        await update.message.reply_text("🎉 No hay misiones pendientes por ahora. ¡Sigue así!")
        return

    for mision in misiones:
        await update.message.reply_text(
            f"🎯 *{mision['titulo']}*\n\n{mision['desc']}\n\n"
            f"⭐ Recompensa: +{mision['xp']} XP",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_mission_done(mision["id"]),
        )


# ─── /recaida ────────────────────────────────────────────────────────────────

async def cmd_recaida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "😔 Entiendo. Reportar una recaída es un acto de valentía.\n\n"
        "¿Confirmas que quieres registrar una recaída?\n"
        "_Tu racha se reducirá parcialmente, pero no perderás todo tu progreso._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_relapse_confirm(),
    )


# ─── /ayuda ──────────────────────────────────────────────────────────────────

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    crisis_msg = msg.get_motivational_message(
        nombre=update.effective_user.first_name or "amigo/a",
        contexto="crisis",
        usuario_id=str(update.effective_user.id)
    )
    await update.message.reply_text(
        crisis_msg + "\n\n_¿Qué quieres hacer ahora?_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main_menu(),
    )


# ─── /configurar ─────────────────────────────────────────────────────────────

async def cmd_configurar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⚙️ *Configuración del plan*\n\n"
        "Por ahora puedes reiniciar tu plan con /start o contactar a tu ayudante.\n"
        "Pronto habrá más opciones de configuración desde aquí.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Callback Query Handler ───────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    telegram_id = str(query.from_user.id)
    nombre = query.from_user.first_name or "amigo/a"

    # ── Selección de vicio ────────────────────────────────────────────────────
    if data.startswith("vicio_"):
        nombre_vicio = next((v[0] for v in VICIOS if v[1] == data), data.replace("vicio_", ""))
        fdb.save_user(telegram_id, {
            "vicio": nombre_vicio.split(" ", 1)[-1].strip(),  # Quitar emoji
            "conversacion_estado": "seleccionando_duracion",
        })
        await query.edit_message_text(
            f"✅ Excelente elección afrontar *{nombre_vicio}*.\n\n"
            "¿Cuánto tiempo durará tu plan?",
            reply_markup=kb_select_duracion(),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Selección de duración ─────────────────────────────────────────────────
    elif data.startswith("dur_"):
        meses = int(data.replace("dur_", ""))
        fdb.save_user(telegram_id, {
            "duracion_meses": meses,
            "conversacion_estado": "seleccionando_ayudantes",
        })
        await query.edit_message_text(
            f"📅 Plan de *{meses} meses* configurado.\n\n"
            "¿Cuántas personas de apoyo quieres invitar? (máximo 2)",
            reply_markup=kb_select_num_helpers(),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Selección de ayudantes ────────────────────────────────────────────────
    elif data.startswith("helpers_"):
        num_helpers = int(data.replace("helpers_", ""))
        user = fdb.get_user(telegram_id)
        if not user:
            await query.edit_message_text("Error: usa /start de nuevo.")
            return

        vicio = user.get("vicio", "algún hábito")
        meses = user.get("duracion_meses", 5)

        # Activar plan
        from datetime import datetime, timezone
        fdb.save_user(telegram_id, {
            "fecha_inicio": datetime.now(timezone.utc).isoformat(),
            "estado_plan": "activo",
            "conversacion_estado": "plan_activo",
        })

        texto = msg.get_welcome_message(nombre, vicio, meses)

        if num_helpers > 0:
            try:
                token, link = generate_invitation_links(telegram_id)
                texto += (
                    f"\n\n🔗 *Link de invitación para tus ayudantes:*\n"
                    f"`{link}`\n\n"
                    f"_{num_helpers} ayudante(s) pueden usar este link._\n"
                    "El link expira cuando se completen los cupos."
                )
            except ValueError as e:
                texto += f"\n\n⚠️ No se pudo generar el link: {e}"

        await query.edit_message_text(texto, parse_mode=ParseMode.MARKDOWN)
        await query.message.reply_text(
            "¡Tu plan ha comenzado! Usa el menú cuando lo necesites:",
            reply_markup=kb_main_menu(),
        )

    # ── Acción: ver misiones ──────────────────────────────────────────────────
    elif data == "action_misiones":
        await cmd_misiones(update, context)

    # ── Acción: ver progreso ──────────────────────────────────────────────────
    elif data == "action_progreso":
        await cmd_progreso(update, context)

    # ── Acción: respirar ─────────────────────────────────────────────────────
    elif data == "action_respirar":
        await query.message.reply_text(
            "🌬️ *Ejercicio de respiración 4-7-8:*\n\n"
            "1. Inhala por la nariz durante *4 segundos*\n"
            "2. Mantén el aire *7 segundos*\n"
            "3. Exhala lentamente durante *8 segundos*\n\n"
            "Repite 3 veces. Esto calma el sistema nervioso en minutos.\n\n"
            "_¿Cómo te sientes después?_",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Acción: pedir ayuda / crisis ──────────────────────────────────────────
    elif data == "action_ayuda":
        crisis_msg = msg.get_motivational_message(nombre=nombre, contexto="crisis", usuario_id=telegram_id)
        await query.message.reply_text(crisis_msg, parse_mode=ParseMode.MARKDOWN)

    # ── Acción: reportar recaída ──────────────────────────────────────────────
    elif data == "action_recaida":
        await cmd_recaida(update, context)

    # ── Acción: pausar plan ───────────────────────────────────────────────────
    elif data == "action_pausar":
        fdb.save_user(telegram_id, {"estado_plan": "pausado"})
        fdb.log_event(telegram_id, "plan_pausado", "El usuario pausó el plan.")
        await query.message.reply_text(
            "⏸️ Plan pausado. Cuando estés listo/a, usa /start para continuar.\n"
            "_Tu progreso y racha se conservan._",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Acción: llamar ayudante ───────────────────────────────────────────────
    elif data == "action_llamar":
        helpers = fdb.get_helpers_for_user(telegram_id)
        if not helpers:
            await query.message.reply_text(
                "No tienes ayudantes registrados todavía.\n"
                "Genera un link de invitación al configurar tu plan.",
            )
        else:
            texto = "📞 *Tus personas de apoyo:*\n\n"
            for h in helpers:
                u = h.get("username", "")
                username_str = f"@{u}" if u else h.get("nombre", "Ayudante")
                texto += f"• {h.get('rol')}: {h.get('nombre')} — {username_str}\n"
            await query.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

    # ── Misión completada ─────────────────────────────────────────────────────
    elif data.startswith("mision_done_"):
        mision_id = data.replace("mision_done_", "")
        from app.services.firebase_db import MISIONES_CATALOGO
        mision = next((m for m in MISIONES_CATALOGO if m["id"] == mision_id), None)
        xp = mision["xp"] if mision else XP_MISION_COMPLETADA
        xp_result = add_xp(telegram_id, xp, f"Misión completada: {mision_id}")
        fdb.log_mission_completed(telegram_id, mision_id, xp)
        logro_msg = msg.get_motivational_message(nombre=nombre, contexto="logro", usuario_id=telegram_id)
        await query.edit_message_text(
            f"✅ *¡Misión completada!*\n\n"
            f"+{xp} XP ganados. {logro_msg}",
            parse_mode=ParseMode.MARKDOWN,
        )
        if xp_result.get("subio_nivel"):
            nivel = xp_result["nivel_nuevo"]["nombre"]
            await query.message.reply_text(
                f"🎉 *¡Subiste de nivel!* Ahora eres *{nivel}* 🏆",
                parse_mode=ParseMode.MARKDOWN,
            )

    # ── Confirmar recaída ─────────────────────────────────────────────────────
    elif data == "recovery_start":
        result = handle_relapse(telegram_id)
        if result:
            await query.edit_message_text(
                result.get("mensaje_usuario", "💙 Recaída registrada. ¡Sigues en pie!"),
                parse_mode=ParseMode.MARKDOWN,
            )
        handle_recovery_start(telegram_id)

    elif data == "cancel_relapse":
        await query.edit_message_text("✅ Bien, no se registró ninguna recaída.")

    # ── Ayudante: enviar apoyo ────────────────────────────────────────────────
    elif data.startswith("hlp_apoyo_"):
        principal_id = data.replace("hlp_apoyo_", "")
        principal = fdb.get_user(principal_id)
        if principal:
            apoyo_msg = f"💙 Tu ayudante {nombre} te envía fuerza y ánimo. ¡No estás solo/a!"
            fdb.enqueue_notification(principal_id, apoyo_msg, {"tipo": "apoyo_ayudante"})
            await query.message.reply_text("✅ Mensaje de apoyo enviado.")

    # ── Ayudante: confirmar chequeo ───────────────────────────────────────────
    elif data.startswith("hlp_check_"):
        principal_id = data.replace("hlp_check_", "")
        fdb.log_event(principal_id, "chequeo_ayudante", f"El ayudante {nombre} confirmó un chequeo.")
        await query.message.reply_text("✅ Chequeo confirmado y registrado.")


# ─── Handler de texto libre ───────────────────────────────────────────────────

async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detecta palabras de riesgo y responde con soporte, o con mensaje genérico."""
    text_lower = update.message.text.lower()
    telegram_id = str(update.effective_user.id)
    nombre = update.effective_user.first_name or "amigo/a"

    is_risk = any(kw in text_lower for kw in RISK_KEYWORDS)

    if is_risk:
        crisis_msg = msg.get_motivational_message(nombre=nombre, contexto="crisis", usuario_id=telegram_id)
        await update.message.reply_text(
            crisis_msg + "\n\n¿Quieres activar el modo de apoyo?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_main_menu(),
        )
        fdb.log_event(telegram_id, "deteccion_riesgo", f"Texto de riesgo detectado: '{update.message.text[:100]}'")
    else:
        # Respuesta genérica motivacional
        motivational = msg.get_motivational_message(nombre=nombre, usuario_id=telegram_id)
        await update.message.reply_text(motivational, parse_mode=ParseMode.MARKDOWN)


# ─── Registro de handlers ─────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Registra todos los handlers en la Application de python-telegram-bot."""
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("estado",     cmd_estado))
    app.add_handler(CommandHandler("progreso",   cmd_progreso))
    app.add_handler(CommandHandler("misiones",   cmd_misiones))
    app.add_handler(CommandHandler("recaida",    cmd_recaida))
    app.add_handler(CommandHandler("ayuda",      cmd_ayuda))
    app.add_handler(CommandHandler("configurar", cmd_configurar))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))
