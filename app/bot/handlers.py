"""
handlers.py — Handlers de comandos y callbacks para el bot de Telegram.
Implementa la máquina de estados de conversación del usuario.
"""
import logging
from datetime import datetime, timezone
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
    kb_escrow_decision,
    kb_main_menu,
    kb_mission_done,
    kb_pill_reminder,
    kb_relapse_confirm,
    VICIOS,
)
from app.services import firebase_db as fdb
from app.services import messages as msg
from app.services.invitations import generate_invitation_links, register_as_helper
from app.services.relapse import handle_relapse, handle_recovery_start
from app.services.xp_system import add_xp, get_progress_summary, XP_MISION_COMPLETADA
from app.services.missions import get_daily_missions, get_mission

logger = logging.getLogger(__name__)

RISK_KEYWORDS = [
    "ansiedad", "ganas", "impulso", "recaída", "estrés", "noche", "fumar",
    "beber", "apostar", "necesito", "no aguanto", "quiero caer", "tentación",
    "marihuana", "pastilla", "aposté", "fumé", "bebí", "caí",
]


# ─── /start ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    telegram_id = str(tg_user.id)
    args = context.args or []
    message = update.message

    # ── Flujo de ayudante (deep link) ─────────────────────────────────────────
    if args and args[0].startswith("inv_"):
        token = args[0][4:]
        try:
            result = register_as_helper(
                token=token,
                helper_telegram_id=telegram_id,
                helper_username=tg_user.username or "",
                helper_nombre=tg_user.first_name or "Ayudante",
            )
            principal = result["usuario_principal"]
            rol = result["rol"]
            await message.reply_text(
                f"✅ *¡Bienvenido/a, {tg_user.first_name}!*\n\n"
                f"Ahora eres *{rol}* de *{principal.get('nombre', 'tu compañero/a')}*.\n\n"
                "Tu misión es acompañar, escuchar y motivar. Sin juzgar.\n\n"
                "Recibirás avisos cuando necesite apoyo. ¡Gracias por estar ahí! 🤝",
                parse_mode=ParseMode.MARKDOWN,
            )
        except ValueError as e:
            await message.reply_text(f"⚠️ {str(e)}")
        return

    # ── Usuario principal ──────────────────────────────────────────────────────
    existing_user = fdb.get_user(telegram_id)

    if existing_user and existing_user.get("estado_plan") not in ("configurando", None):
        nombre = existing_user.get("nombre", tg_user.first_name)
        await message.reply_text(
            f"👋 ¡Hola de nuevo, *{nombre}*! Tu plan ya está activo.\n"
            "Usa el menú para continuar tu camino. 💪",
            reply_markup=kb_main_menu(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Crear o actualizar el usuario
    fdb.create_user(
        telegram_id=telegram_id,
        username=tg_user.username or "",
        nombre=tg_user.first_name or "Amigo/a",
    )

    await message.reply_text(
        f"🌟 *¡Hola, {tg_user.first_name}!*\n\n"
        "Has dado un paso enorme al estar aquí. 🙌\n"
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
        "/ayuda — Pedir apoyo en crisis\n"
        "/configurar — Ver configuración del plan\n"
        "/help — Este menú",
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── /estado ─────────────────────────────────────────────────────────────────

async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    user = fdb.get_user(telegram_id)
    if not user:
        await update.message.reply_text("Usa /start para comenzar.")
        return

    estado = user.get("estado_plan", "sin plan")
    racha = user.get("racha_dias", 0)
    vicio = user.get("vicio", "sin configurar")
    xp = user.get("xp", 0)
    nivel = user.get("nivel", 1)
    fecha_inicio = user.get("fecha_inicio")
    dias_activos = "—"
    if fecha_inicio:
        try:
            inicio = datetime.fromisoformat(fecha_inicio)
            dias_activos = (datetime.now(timezone.utc) - inicio).days
        except Exception:
            pass

    await update.message.reply_text(
        f"📋 *Tu estado actual:*\n\n"
        f"🎯 Hábito/Vicio: *{vicio}*\n"
        f"🔥 Racha: *{racha} días* sin consumo\n"
        f"📅 Días en el plan: *{dias_activos}*\n"
        f"⭐ XP Total: *{xp}* | Nivel *{nivel}*\n"
        f"📌 Estado: *{estado}*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main_menu(),
    )


# ─── /progreso ───────────────────────────────────────────────────────────────

async def cmd_progreso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    resumen = get_progress_summary(telegram_id)
    if not resumen:
        await update.message.reply_text(
            "Aún no tienes plan activo. Usa /start para comenzar."
        )
        return
    await update.message.reply_text(resumen, parse_mode=ParseMode.MARKDOWN)


# ─── /misiones ───────────────────────────────────────────────────────────────

async def cmd_misiones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    # Obtener el objeto mensaje correcto
    message = update.message or (
        update.callback_query.message if update.callback_query else None
    )
    if not message:
        return

    user = fdb.get_user(telegram_id)
    if not user or user.get("estado_plan") not in ("activo", "recuperacion"):
        await message.reply_text(
            "Tu plan no está activo todavía. Usa /start para comenzar. 🚀"
        )
        return

    misiones = get_daily_missions(user.get("vicio", "general"), count=3)
    if not misiones:
        await message.reply_text("🎉 No hay misiones pendientes. ¡Sigue así!")
        return

    await message.reply_text(
        "📋 *Tus misiones del día:*\n_Completa cada una para ganar XP._",
        parse_mode=ParseMode.MARKDOWN,
    )
    for mision in misiones:
        await message.reply_text(
            f"🎯 *{mision['titulo']}*\n\n"
            f"{mision['desc']}\n\n"
            f"⭐ Recompensa: *+{mision['xp']} XP*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_mission_done(mision["id"]),
        )


# ─── /recaida ────────────────────────────────────────────────────────────────

async def cmd_recaida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message or (
        update.callback_query.message if update.callback_query else None
    )
    if not message:
        return
    await message.reply_text(
        "😔 Reportar una recaída es un acto de valentía.\n\n"
        "¿Confirmas que quieres registrar una recaída?\n"
        "_Tu racha se reducirá parcialmente, pero no perderás todo tu progreso._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_relapse_confirm(),
    )


# ─── /ayuda ──────────────────────────────────────────────────────────────────

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nombre = update.effective_user.first_name or "amigo/a"
    telegram_id = str(update.effective_user.id)
    crisis_msg = msg.get_motivational_message(
        nombre=nombre, contexto="crisis", usuario_id=telegram_id
    )
    await update.message.reply_text(
        crisis_msg + "\n\n_¿Qué quieres hacer ahora?_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main_menu(),
    )


# ─── /configurar ─────────────────────────────────────────────────────────────

async def cmd_configurar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    user = fdb.get_user(telegram_id)
    if not user:
        await update.message.reply_text("Usa /start para comenzar.")
        return
    await update.message.reply_text(
        f"⚙️ *Configuración del plan*\n\n"
        f"🎯 Vicio/Hábito: *{user.get('vicio', '—')}*\n"
        f"📅 Duración: *{user.get('duracion_meses', '—')} meses*\n"
        f"🔥 Racha actual: *{user.get('racha_dias', 0)} días*\n\n"
        "Para reiniciar el plan usa /start.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main_menu(),
    )


# ─── Finalizar Plan ───────────────────────────────────────────────────────────

async def _do_finalize_plan(
    telegram_id: str,
    query,
    nombre: str,
    escrow_active: bool,
) -> None:
    """Activa el plan, genera invitaciones y muestra mensaje de bienvenida."""
    user = fdb.get_user(telegram_id)
    if not user:
        await query.edit_message_text("Error: usa /start de nuevo.")
        return

    vicio = user.get("vicio", "algún hábito")
    meses = user.get("duracion_meses", 5)
    num_helpers = user.get("num_helpers_esperados", 0)

    updates = {
        "fecha_inicio": datetime.now(timezone.utc).isoformat(),
        "estado_plan": "activo",
        "conversacion_estado": "plan_activo",
    }

    if escrow_active:
        updates["retencion_compromiso"] = {
            "estado": "activo_simbolico",
            "monto_simbolico": 1000,
            "iniciado_el": datetime.now(timezone.utc).isoformat(),
            "proveedor": "simbolico",
        }
        fdb.log_event(telegram_id, "escrow_iniciado", "Compromiso simbólico de 1000 pts activado.")

    fdb.save_user(telegram_id, updates)

    try:
        texto = msg.get_welcome_message(nombre, vicio, meses)
    except Exception:
        texto = (
            f"🌟 *¡{nombre}, tu plan de {meses} meses ha comenzado!*\n\n"
            f"Hábito a superar: *{vicio}*\n\n"
            "Cada día que pases sin caer es una victoria. ¡Tú puedes! 💪"
        )

    if escrow_active:
        texto += "\n\n💰 *Compromiso simbólico:* 1000 puntos en retención. ¡Eso demuestra que vas en serio!"

    if num_helpers > 0:
        try:
            _token, link = generate_invitation_links(telegram_id)
            texto += (
                f"\n\n🔗 *Link de invitación para tus ayudantes:*\n"
                f"`{link}`\n\n"
                f"_{num_helpers} ayudante(s) pueden usar este link._"
            )
        except Exception as e:
            logger.warning(f"No se pudo generar link de invitación: {e}")

    await query.edit_message_text(texto, parse_mode=ParseMode.MARKDOWN)
    await query.message.reply_text(
        "¡Tu plan ha comenzado! Usa el menú cuando lo necesites:",
        reply_markup=kb_main_menu(),
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
        vicio_key = data.replace("vicio_", "")
        if vicio_key == "Otro":
            fdb.save_user(telegram_id, {"conversacion_estado": "esperando_nombre_vicio"})
            await query.edit_message_text(
                "✏️ *¿Cómo llamarías a tu hábito o vicio a superar?*\n\n"
                "_Escríbelo con tus propias palabras, por ejemplo: «redes sociales», «comer de noche», etc._",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            nombre_vicio = next((v[0] for v in VICIOS if v[1] == data), vicio_key)
            fdb.save_user(telegram_id, {
                "vicio": nombre_vicio.split(" ", 1)[-1].strip(),
                "conversacion_estado": "seleccionando_duracion",
            })
            await query.edit_message_text(
                f"✅ Excelente decisión afrontar *{nombre_vicio}*.\n\n"
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
        fdb.save_user(telegram_id, {
            "num_helpers_esperados": num_helpers,
            "conversacion_estado": "configurando_escrow",
        })
        await query.edit_message_text(
            "💰 *Compromiso simbólico*\n\n"
            "Puedes registrar un depósito simbólico que permanecerá "
            "«retenido» como recordatorio de tu compromiso contigo mismo/a.\n\n"
            "_Este sistema es completamente simbólico y no involucra dinero real._\n\n"
            "¿Quieres registrar este compromiso?",
            reply_markup=kb_escrow_decision(),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Escrow ────────────────────────────────────────────────────────────────
    elif data == "escrow_accept":
        await _do_finalize_plan(telegram_id, query, nombre, escrow_active=True)

    elif data == "escrow_skip":
        await _do_finalize_plan(telegram_id, query, nombre, escrow_active=False)

    # ── Acción: misiones ──────────────────────────────────────────────────────
    elif data == "action_misiones":
        await cmd_misiones(update, context)

    # ── Acción: progreso ──────────────────────────────────────────────────────
    elif data == "action_progreso":
        resumen = get_progress_summary(telegram_id)
        if resumen:
            await query.message.reply_text(resumen, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_text("No tienes plan activo. Usa /start.")

    # ── Acción: respirar ─────────────────────────────────────────────────────
    elif data == "action_respirar":
        await query.message.reply_text(
            "🌬️ *Ejercicio de respiración 4-7-8:*\n\n"
            "1. Inhala por la nariz *4 segundos*\n"
            "2. Mantén el aire *7 segundos*\n"
            "3. Exhala lentamente *8 segundos*\n\n"
            "Repite 3 veces. Esto calma el sistema nervioso en minutos. 💙",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Acción: ayuda / crisis ────────────────────────────────────────────────
    elif data == "action_ayuda":
        crisis = msg.get_motivational_message(
            nombre=nombre, contexto="crisis", usuario_id=telegram_id
        )
        await query.message.reply_text(crisis, parse_mode=ParseMode.MARKDOWN)

    # ── Acción: recaída ───────────────────────────────────────────────────────
    elif data == "action_recaida":
        await cmd_recaida(update, context)

    # ── Acción: pausar ────────────────────────────────────────────────────────
    elif data == "action_pausar":
        fdb.save_user(telegram_id, {"estado_plan": "pausado"})
        fdb.log_event(telegram_id, "plan_pausado", "El usuario pausó el plan.")
        await query.message.reply_text(
            "⏸️ Plan pausado. Cuando estés listo/a, usa /start para continuar.\n"
            "_Tu progreso y racha se conservan._",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Acción: reintentar ────────────────────────────────────────────────────
    elif data == "action_reintentar":
        fdb.save_user(telegram_id, {"estado_plan": "activo", "conversacion_estado": "plan_activo"})
        fdb.log_event(telegram_id, "plan_reintento", "Usuario eligió reintentar el plan.")
        motivacional = msg.get_motivational_message(
            nombre=nombre, contexto="logro", usuario_id=telegram_id
        )
        await query.message.reply_text(
            f"🔄 *¡De vuelta en pie, {nombre}!*\n\n{motivacional}\n\n"
            "Cada nuevo intento es progreso real. 💪",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_main_menu(),
        )

    # ── Acción: llamar ayudante ───────────────────────────────────────────────
    elif data == "action_llamar":
        helpers = fdb.get_helpers_for_user(telegram_id)
        if not helpers:
            await query.message.reply_text(
                "No tienes ayudantes registrados todavía.\n"
                "Al configurar tu plan puedes generar un link de invitación."
            )
        else:
            texto = "📞 *Tus personas de apoyo:*\n\n"
            for h in helpers:
                un = h.get("username", "")
                username_str = f"@{un}" if un else "sin username"
                texto += f"• *{h.get('rol')}:* {h.get('nombre')} — {username_str}\n"
            await query.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

    # ── Pastilla tomada ───────────────────────────────────────────────────────
    elif data.startswith("pill_taken_"):
        mision_id = data.replace("pill_taken_", "")
        mision = get_mission(mision_id)
        xp = mision.get("puntos_recompensa", 10) if mision else 10
        add_xp(telegram_id, xp, f"Pastilla tomada: {mision_id}")
        fdb.log_mission_completed(telegram_id, mision_id, xp)
        fdb.log_event(telegram_id, "pastilla_tomada", f"Pastilla tomada: {mision_id}")
        await query.edit_message_text(
            f"✅ *¡Bien hecho!* Pastilla registrada.\n\n"
            f"+{xp} puntos ganados. ¡Cada dosis cuenta! 💊",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Pastilla: snooze ─────────────────────────────────────────────────────
    elif data.startswith("pill_snooze_"):
        mision_id = data.replace("pill_snooze_", "")
        fdb.enqueue_notification(
            telegram_id,
            f"⏰ *Recordatorio:* Es hora de tu pastilla 💊\n"
            f"¿Ya la tomaste? Usa el botón para confirmar.",
            {"tipo": "pill_snooze", "mision_id": mision_id}
        )
        await query.edit_message_text(
            "⏰ Te recordaré en 10 minutos. ¡No olvides tu pastilla!",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Misión completada ─────────────────────────────────────────────────────
    elif data.startswith("mision_done_"):
        mision_id = data.replace("mision_done_", "")
        mision = get_mission(mision_id)
        xp = mision.get("puntos_recompensa", XP_MISION_COMPLETADA) if mision else XP_MISION_COMPLETADA
        xp_result = add_xp(telegram_id, xp, f"Misión completada: {mision_id}")
        fdb.log_mission_completed(telegram_id, mision_id, xp)
        logro = msg.get_motivational_message(
            nombre=nombre, contexto="logro", usuario_id=telegram_id
        )
        await query.edit_message_text(
            f"✅ *¡Misión completada!*\n\n+{xp} XP ganados. {logro}",
            parse_mode=ParseMode.MARKDOWN,
        )
        if xp_result.get("subio_nivel"):
            nivel_nombre = xp_result.get("nivel_nuevo", {}).get("nombre", "nuevo nivel")
            await query.message.reply_text(
                f"🎉 *¡Subiste de nivel!* Ahora eres *{nivel_nombre}* 🏆",
                parse_mode=ParseMode.MARKDOWN,
            )

    # ── Confirmar recaída ─────────────────────────────────────────────────────
    elif data == "recovery_start":
        result = handle_relapse(telegram_id)
        if result:
            await query.edit_message_text(
                result.get("mensaje_usuario", "💙 Recaída registrada. ¡Sigues en pie!"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb_main_menu(),
            )
            handle_recovery_start(telegram_id)
        else:
            await query.edit_message_text(
                "💙 Recaída registrada. Cada tropiezo nos enseña. ¡Vuelve a levantarte!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb_main_menu(),
            )

    elif data == "cancel_relapse":
        await query.edit_message_text(
            "✅ No se registró ninguna recaída. ¡Sigue fuerte! 💪"
        )

    # ── Acciones de ayudante ──────────────────────────────────────────────────
    elif data.startswith("hlp_apoyo_"):
        principal_id = data.replace("hlp_apoyo_", "")
        fdb.enqueue_notification(
            principal_id,
            f"💙 Tu ayudante *{nombre}* te envía fuerza y ánimo. ¡No estás solo/a!",
            {"tipo": "apoyo_ayudante"}
        )
        await query.message.reply_text("✅ Mensaje de apoyo enviado.")

    elif data.startswith("hlp_check_"):
        principal_id = data.replace("hlp_check_", "")
        fdb.log_event(principal_id, "chequeo_ayudante", f"El ayudante {nombre} confirmó un chequeo.")
        await query.message.reply_text("✅ Chequeo confirmado y registrado. ¡Gracias!")

    elif data.startswith("hlp_contact_"):
        principal_id = data.replace("hlp_contact_", "")
        principal = fdb.get_user(principal_id)
        if principal:
            username = principal.get("username", "")
            if username:
                await query.message.reply_text(
                    f"📞 Escríbele directamente: *@{username}*",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await query.message.reply_text(
                    f"📞 {principal.get('nombre', 'Tu compañero/a')} no tiene username. "
                    "Búscalo/a por su nombre en Telegram."
                )

    else:
        logger.warning(f"Callback no manejado: {data}")


# ─── Handler de texto libre ───────────────────────────────────────────────────

async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text_lower = update.message.text.lower()
    text_original = update.message.text
    telegram_id = str(update.effective_user.id)
    nombre = update.effective_user.first_name or "amigo/a"

    user = fdb.get_user(telegram_id)
    conv_estado = (user or {}).get("conversacion_estado", "")

    # ── Capturar nombre de vicio personalizado ────────────────────────────────
    if conv_estado == "esperando_nombre_vicio":
        vicio_personalizado = text_original.strip()[:80]
        fdb.save_user(telegram_id, {
            "vicio": vicio_personalizado,
            "conversacion_estado": "seleccionando_duracion",
        })
        await update.message.reply_text(
            f"✅ Entendido: *«{vicio_personalizado}»*.\n\n"
            "¿Cuánto tiempo durará tu plan?",
            reply_markup=kb_select_duracion(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── Detección de palabras de riesgo ───────────────────────────────────────
    is_risk = any(kw in text_lower for kw in RISK_KEYWORDS)
    if is_risk:
        crisis = msg.get_motivational_message(
            nombre=nombre, contexto="crisis", usuario_id=telegram_id
        )
        await update.message.reply_text(
            crisis + "\n\n*¿Quieres activar el modo de apoyo?*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_main_menu(),
        )
        fdb.log_event(telegram_id, "deteccion_riesgo", f"Texto: '{text_original[:80]}'")
    else:
        motivacional = msg.get_motivational_message(nombre=nombre, usuario_id=telegram_id)
        await update.message.reply_text(motivacional, parse_mode=ParseMode.MARKDOWN)


# ─── Registro ─────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
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
    logger.info("✅ Handlers registrados correctamente.")
