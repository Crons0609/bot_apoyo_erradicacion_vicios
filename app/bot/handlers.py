"""
handlers.py — Handlers de comandos y callbacks para el bot de Telegram.
Implementa la máquina de estados de conversación del usuario.
"""
import logging
import random
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
    kb_helper_actions,
    VICIOS,
)
from app.services import firebase_db as fdb
from app.services import messages as msg
from app.services.invitations import generate_invitation_links, register_as_helper
from app.services.relapse import handle_relapse, handle_recovery_start
from app.services.xp_system import add_xp, get_progress_summary, XP_MISION_COMPLETADA
from app.services.missions import get_daily_missions, get_mission

logger = logging.getLogger(__name__)

# ─── Palabras clave de riesgo ─────────────────────────────────────────────────

RISK_KEYWORDS = [
    "ansiedad", "ganas", "impulso", "recaída", "estrés", "noche", "fumar",
    "beber", "apostar", "necesito", "no aguanto", "quiero caer", "tentación",
    "marihuana", "pastilla", "aposté", "fumé", "bebí", "caí",
]


# ─── Helpers internos ─────────────────────────────────────────────────────────

async def _get_or_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
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

    fdb.create_user(
        telegram_id=telegram_id,
        username=tg_user.username or "",
        nombre=tg_user.first_name or "Amigo/a",
        foto_perfil="",
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
    xp = user.get("xp", 0)
    nivel = user.get("nivel", 1)
    # Calcular días activos
    fecha_inicio = user.get("fecha_inicio")
    dias_activos = "—"
    if fecha_inicio:
        try:
            inicio = datetime.fromisoformat(fecha_inicio)
            dias_activos = (datetime.now(timezone.utc) - inicio).days
        except:
            pass
    await update.message.reply_text(
        f"📋 *Tu estado actual:*\n\n"
        f"🎯 Vicio/Hábito: {vicio}\n"
        f"🔥 Racha: {racha} días sin consumo\n"
        f"📅 Días en el plan: {dias_activos}\n"
        f"⭐ XP Total: {xp} | Nivel {nivel}\n"
        f"📌 Estado: *{estado}*",
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

    # Mensaje intro
    msg_obj = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg_obj:
        return

    await msg_obj.reply_text(
        "📋 *Tus misiones del día:*\n_Completa cada una para ganar XP y puntos._",
        parse_mode=ParseMode.MARKDOWN,
    )
    for mision in misiones:
        await msg_obj.reply_text(
            f"🎯 *{mision['titulo']}*\n\n{mision['desc']}\n\n"
            f"⭐ Recompensa: +{mision['xp']} XP",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_mission_done(mision["id"]),
        )


# ─── /recaida ────────────────────────────────────────────────────────────────

async def cmd_recaida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg_obj = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg_obj:
        return
    await msg_obj.reply_text(
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
    telegram_id = str(update.effective_user.id)
    user = fdb.get_user(telegram_id)
    if not user:
        await update.message.reply_text("Usa /start para comenzar.")
        return
    vicio = user.get("vicio", "—")
    meses = user.get("duracion_meses", "—")
    racha = user.get("racha_dias", 0)
    await update.message.reply_text(
        f"⚙️ *Configuración del plan*\n\n"
        f"🎯 Vicio/Hábito: *{vicio}*\n"
        f"📅 Duración: *{meses} meses*\n"
        f"🔥 Racha actual: *{racha} días*\n\n"
        "Para reiniciar tu plan completamente, usa /start.\n"
        "Para pausar el plan usa el botón de abajo.",
        parse_mode=ParseMode.MARKDOWN,
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
            fdb.save_user(telegram_id, {
                "conversacion_estado": "esperando_nombre_vicio",
            })
            await query.edit_message_text(
                "✏️ *¿Cómo llamarías a tu hábito o vicio a superar?*\n\n"
                "_Escribe con tus propias palabras, por ejemplo: «redes sociales», «comer de noche», etc._",
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
        user = fdb.get_user(telegram_id)
        if not user:
            await query.edit_message_text("Error: usa /start de nuevo.")
            return

        # Guardar número de helpers esperados
        fdb.save_user(telegram_id, {
            "num_helpers_esperados": num_helpers,
            "conversacion_estado": "configurando_escrow",
        })

        # Preguntar por compromiso simbólico
        await query.edit_message_text(
            "💰 *Compromiso simbólico*\n\n"
            "Una parte clave del plan es el *compromiso*.\n\n"
            "Puedes registrar un depósito simbólico que permanecerá «retenido» "
            "hasta completar tu plan. Si abandonas o tienes demasiadas recaídas, "
            "el depósito se pierde simbólicamente.\n\n"
            "_Este sistema es completamente simbólico y no involucra dinero real. "
            "Es un recordatorio de tu compromiso contigo mismo/a._\n\n"
            "¿Quieres registrar este compromiso?",
            reply_markup=kb_escrow_decision(),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Escrow: aceptar ───────────────────────────────────────────────────────
    elif data == "escrow_accept":
        _finalize_plan(telegram_id, query, nombre, escrow_active=True)

    elif data == "escrow_skip":
        _finalize_plan_async = None  # Necesitamos llamar la función async
        await _do_finalize_plan(telegram_id, query, nombre, escrow_active=False)
        return

    # Manejador de escrow_accept también requiere await
    if data == "escrow_accept":
        await _do_finalize_plan(telegram_id, query, nombre, escrow_active=True)
        return

    # ── Acción: ver misiones ──────────────────────────────────────────────────
    if data == "action_misiones":
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

    # ── Acción: reintentar (después de pausa o recaída) ───────────────────────
    elif data == "action_reintentar":
        user = fdb.get_user(telegram_id)
        if user:
            fdb.save_user(telegram_id, {"estado_plan": "activo", "conversacion_estado": "plan_activo"})
            fdb.log_event(telegram_id, "plan_reintento", "Usuario eligió reintentar el plan.")
            motivacional = msg.get_motivational_message(nombre=nombre, contexto="logro", usuario_id=telegram_id)
            await query.message.reply_text(
                f"🔄 *¡De vuelta en pie!*\n\n{motivacional}\n\n"
                "Tu plan sigue activo. Cada nuevo intento es progreso.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb_main_menu(),
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

    # ── Pastilla tomada ───────────────────────────────────────────────────────
    elif data.startswith("pill_taken_"):
        mision_id = data.replace("pill_taken_", "")
        mision = get_mission(mision_id)
        xp = mision.get("puntos_recompensa", 10) if mision else 10
        xp_result = add_xp(telegram_id, xp, f"Pastilla tomada: {mision_id}")
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
        mision = get_mission(mision_id)
        nombre_pastilla = mision.get("nombre", "pastilla") if mision else "pastilla"
        # Encolar recordatorio en 10 minutos
        fdb.enqueue_notification(
            telegram_id,
            f"⏰ *Recordatorio:* Es hora de tomar tu {nombre_pastilla} 💊\n¿Ya la tomaste?",
            {"tipo": "pill_snooze", "mision_id": mision_id, "delay_min": 10}
        )
        await query.edit_message_text(
            "⏰ Te recordaré en 10 minutos. No olvides tomarte la pastilla.",
            parse_mode=ParseMode.MARKDOWN,
        )

    # ── Misión completada ─────────────────────────────────────────────────────
    elif data.startswith("mision_done_"):
        mision_id = data.replace("mision_done_", "")
        mision = get_mission(mision_id)
        xp = mision.get("puntos_recompensa", XP_MISION_COMPLETADA) if mision else XP_MISION_COMPLETADA
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

    # ── Ayudante: contactar ───────────────────────────────────────────────────
    elif data.startswith("hlp_contact_"):
        principal_id = data.replace("hlp_contact_", "")
        principal = fdb.get_user(principal_id)
        if principal:
            username = principal.get("username", "")
            if username:
                await query.message.reply_text(
                    f"📞 Puedes escribirle directamente a: @{username}",
                )
            else:
                await query.message.reply_text(
                    f"📞 {principal.get('nombre', 'Tu compañero/a')} no tiene username configurado. "
                    "Búscalo/a por su nombre en Telegram."
                )


# ─── Finalize plan helper ─────────────────────────────────────────────────────

async def _do_finalize_plan(telegram_id: str, query, nombre: str, escrow_active: bool) -> None:
    """Activa el plan del usuario, genera links de invitación y muestra el mensaje de bienvenida."""
    user = fdb.get_user(telegram_id)
    if not user:
        await query.edit_message_text("Error: usa /start de nuevo.")
        return

    vicio = user.get("vicio", "algún hábito")
    meses = user.get("duracion_meses", 5)
    num_helpers = user.get("num_helpers_esperados", 0)

    # Activar plan
    updates = {
        "fecha_inicio": datetime.now(timezone.utc).isoformat(),
        "estado_plan": "activo",
        "conversacion_estado": "plan_activo",
    }

    if escrow_active:
        updates["retencion_compromiso"] = {
            "estado": "activo_simbolico",
            "monto_simbolico": 1000,  # 1000 puntos simbólicos
            "iniciado_el": datetime.now(timezone.utc).isoformat(),
            "proveedor": "simbolico",
        }
        fdb.log_event(telegram_id, "escrow_iniciado", "Compromiso simbólico de 1000 puntos activado.")

    fdb.save_user(telegram_id, updates)

    texto = msg.get_welcome_message(nombre, vicio, meses)
    if escrow_active:
        texto += "\n\n💰 *Compromiso registrado:* 1000 puntos simbólicos en retención. ¡Eso demuestra que vas en serio!"

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


def _finalize_plan(telegram_id, query, nombre, escrow_active):
    """Wrapper síncrono — no usarlo directamente; usar await _do_finalize_plan."""
    pass


# ─── Handler de texto libre ───────────────────────────────────────────────────

async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detecta palabras de riesgo, captura el nombre del vicio personalizado, o responde motivacionalmente."""
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

    # ── Detección de riesgo ───────────────────────────────────────────────────
    is_risk = any(kw in text_lower for kw in RISK_KEYWORDS)

    if is_risk:
        crisis_msg = msg.get_motivational_message(nombre=nombre, contexto="crisis", usuario_id=telegram_id)
        await update.message.reply_text(
            crisis_msg + "\n\n¿Quieres activar el modo de apoyo?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_main_menu(),
        )
        fdb.log_event(telegram_id, "deteccion_riesgo", f"Texto de riesgo: '{update.message.text[:100]}'")
    else:
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
