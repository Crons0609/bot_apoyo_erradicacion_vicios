"""
scheduler.py — Worker de tareas programadas.
Usa APScheduler para enviar mensajes, calcular fases, gestionar la cola,
recordatorios de medicamentos y frecuencia nocturna aumentada.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.services import firebase_db as fdb
from app.services import messages as msg
from app.services.xp_system import calculate_phase, PHASE_INTERVALS, update_streak
from app.config import (
    WEBHOOK_URL,
    NIGHT_START_UTC, NIGHT_END_UTC,
    PILL_REMINDER_1_HOUR_UTC, PILL_REMINDER_1_MIN_UTC, PILL_REMINDER_1_NAME,
    PILL_REMINDER_2_HOUR_UTC, PILL_REMINDER_2_MIN_UTC, PILL_REMINDER_2_NAME,
)

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="UTC")


# ─── Utilidades ───────────────────────────────────────────────────────────────

def _is_night_time() -> bool:
    """Verifica si la hora actual UTC está en el rango nocturno configurado."""
    hour = datetime.now(timezone.utc).hour
    if NIGHT_START_UTC <= NIGHT_END_UTC:
        return NIGHT_START_UTC <= hour < NIGHT_END_UTC
    else:  # Cruza medianoche (ej. 22-6)
        return hour >= NIGHT_START_UTC or hour < NIGHT_END_UTC


def _get_effective_interval(fase: str) -> int:
    """
    Retorna el intervalo de envío en segundos según la fase.
    En horario nocturno, el intervalo se reduce a la mitad (más mensajes de apoyo).
    """
    base = PHASE_INTERVALS.get(fase, 3600)
    if _is_night_time():
        return max(base // 2, 180)  # Mínimo 3 min en noche
    return base


# ─── Job: procesar cola de notificaciones ────────────────────────────────────

def job_process_notification_queue():
    """
    Lee la cola de notificaciones pendientes de Firebase y las envía por Telegram.
    Reintenta hasta 3 veces antes de descartar.
    """
    from app.bot.main import get_application

    pendientes = fdb.get_pending_notifications(limit=30)
    if not pendientes:
        return

    app = get_application()

    async def _send_all():
        for notif_id, notif in pendientes.items():
            if notif.get("intentos", 0) >= 3:
                continue
            try:
                await app.bot.send_message(
                    chat_id=notif["telegram_id"],
                    text=notif["mensaje"],
                    parse_mode="Markdown",
                )
                fdb.mark_notification_sent(notif_id)
            except Exception as e:
                logger.warning(f"[SCHEDULER] Fallo al enviar notif {notif_id}: {e}")
                fdb.mark_notification_failed(notif_id)

    asyncio.run(_send_all())


# ─── Job: enviar mensajes programados a usuarios activos ─────────────────────

def job_send_scheduled_messages():
    """
    Evalúa para cada usuario activo si corresponde enviar un mensaje motivacional
    basado en su fase actual. En horario nocturno incrementa la frecuencia.
    """
    users = fdb.get_all_users()
    now = datetime.now(timezone.utc)
    is_night = _is_night_time()

    for user in users:
        if user.get("estado_plan") not in ("activo", "recuperacion"):
            continue

        telegram_id = user.get("telegram_id")
        nombre = user.get("nombre", "amigo/a")
        fecha_inicio_str = user.get("fecha_inicio")

        if not fecha_inicio_str:
            continue

        try:
            fecha_inicio = datetime.fromisoformat(fecha_inicio_str)
        except ValueError:
            continue

        dias_activo = (now - fecha_inicio).days + 1
        fase = calculate_phase(dias_activo)
        intervalo_segundos = _get_effective_interval(fase)

        ultimo_envio_str = user.get("ultimo_mensaje_programado")
        if ultimo_envio_str:
            try:
                ultimo_envio = datetime.fromisoformat(ultimo_envio_str)
                if (now - ultimo_envio).total_seconds() < intervalo_segundos:
                    continue
            except ValueError:
                pass

        vicio = user.get("vicio")

        # Mensaje nocturno especial
        if is_night:
            contexto = "noche" if now.hour >= 4 else "madrugada"  # UTC: noche o madrugada
            mensaje = msg.get_motivational_message(
                nombre=nombre, vicio=vicio, contexto=contexto, usuario_id=telegram_id
            )
            # Prefijo de alerta nocturna
            mensaje = f"🌙 *Apoyo nocturno:*\n\n{mensaje}"
        else:
            mensaje = msg.get_motivational_message(nombre=nombre, vicio=vicio, usuario_id=telegram_id)

        fdb.enqueue_notification(telegram_id, mensaje, {"tipo": "programado", "fase": fase, "nocturno": is_night})
        fdb.update_user_field(telegram_id, "ultimo_mensaje_programado", now.isoformat())


# ─── Job: recordatorio de pastilla 1 (7:00 AM) ───────────────────────────────

def job_pill_reminder_1():
    """
    Envía recordatorio de Anciocrol a todos los usuarios activos y a sus ayudantes.
    """
    from app.bot.keyboards import kb_pill_reminder, kb_helper_pill_reminder

    users = fdb.get_all_users()
    for user in users:
        if user.get("estado_plan") not in ("activo", "recuperacion"):
            continue

        telegram_id = user.get("telegram_id")
        nombre = user.get("nombre", "amigo/a")

        # Notificación al usuario principal con botón
        fdb.enqueue_notification(
            telegram_id,
            f"⏰ *¡Hora de tu pastilla!*\n\n"
            f"💊 Es momento de tomar *{PILL_REMINDER_1_NAME}*.\n"
            "Esta dosis es parte de tu proceso de recuperación. ¡No la olvides!",
            {
                "tipo": "pill_reminder",
                "mision_id": "pill_anciocrol",
                "keyboard_type": "pill",
                "keyboard_mision_id": "pill_anciocrol",
            }
        )

        # Notificación a ayudantes
        helpers = fdb.get_helpers_for_user(telegram_id)
        for helper in helpers:
            fdb.enqueue_notification(
                helper["telegram_id"],
                f"👋 *Recordatorio para ayudante*\n\n"
                f"⏰ Son las 7:00 AM. Recuerda a *{nombre}* que tome su pastilla de *{PILL_REMINDER_1_NAME}*.",
                {
                    "tipo": "pill_helper_reminder",
                    "principal_id": telegram_id,
                    "principal_nombre": nombre,
                    "keyboard_type": "helper_pill",
                }
            )


# ─── Job: recordatorio de pastilla 2 (7:10 AM) ───────────────────────────────

def job_pill_reminder_2():
    """
    Envía recordatorio de Pasinerva a todos los usuarios activos y a sus ayudantes.
    """
    users = fdb.get_all_users()
    for user in users:
        if user.get("estado_plan") not in ("activo", "recuperacion"):
            continue

        telegram_id = user.get("telegram_id")
        nombre = user.get("nombre", "amigo/a")

        fdb.enqueue_notification(
            telegram_id,
            f"⏰ *Segunda pastilla del día*\n\n"
            f"💊 Es momento de tomar *{PILL_REMINDER_2_NAME}*.\n"
            "Cada dosis es un paso más en tu recuperación. ¡Tú puedes!",
            {
                "tipo": "pill_reminder",
                "mision_id": "pill_pasinerva",
                "keyboard_type": "pill",
                "keyboard_mision_id": "pill_pasinerva",
            }
        )

        helpers = fdb.get_helpers_for_user(telegram_id)
        for helper in helpers:
            fdb.enqueue_notification(
                helper["telegram_id"],
                f"👋 *Recordatorio para ayudante*\n\n"
                f"⏰ Son las 7:10 AM. Recuerda a *{nombre}* que tome su pastilla de *{PILL_REMINDER_2_NAME}*.",
                {
                    "tipo": "pill_helper_reminder",
                    "principal_id": telegram_id,
                    "principal_nombre": nombre,
                    "keyboard_type": "helper_pill",
                }
            )


# ─── Job: actualizar racha diaria ────────────────────────────────────────────

def job_update_daily_streak():
    """
    Corre 1 vez por día (a las 00:01 UTC).
    Incrementa la racha de todos los usuarios activos.
    """
    users = fdb.get_all_users()
    now = datetime.now(timezone.utc)

    for user in users:
        if user.get("estado_plan") != "activo":
            continue

        telegram_id = user.get("telegram_id")
        racha_actual = user.get("racha_dias", 0)
        nueva_racha = racha_actual + 1

        update_streak(telegram_id, nueva_racha)

        if nueva_racha in (1, 3, 7, 14, 21, 30, 60, 90, 120, 180, 360):
            nombre = user.get("nombre", "amigo/a")
            milestone_msg = (
                f"🎉 *¡{nueva_racha} días sin consumir!* {nombre}, esto es un logro enorme.\n"
                "Cada día que pasa, eres más fuerte. ¡Sigue así! 🏆"
            )
            fdb.enqueue_notification(telegram_id, milestone_msg, {"tipo": "milestone", "dias": nueva_racha})


# ─── Job: revisar inactividad ────────────────────────────────────────────────

def job_check_inactive_users():
    """
    Detecta usuarios que no han interactuado en más de 24 horas y envía un ping.
    """
    users = fdb.get_all_users()
    now = datetime.now(timezone.utc)
    umbral = timedelta(hours=24)

    for user in users:
        if user.get("estado_plan") != "activo":
            continue
        ultima = user.get("ultima_actualizacion")
        if not ultima:
            continue
        try:
            dt = datetime.fromisoformat(ultima)
            if (now - dt) > umbral:
                nombre = user.get("nombre", "amigo/a")
                telegram_id = user.get("telegram_id")
                silence_msg = msg.get_motivational_message(
                    nombre=nombre, contexto="silencio", usuario_id=telegram_id
                )
                fdb.enqueue_notification(telegram_id, silence_msg, {"tipo": "inactividad"})
        except ValueError:
            continue


# ─── Job: Keep Alive (Render Free Tier) ──────────────────────────────────────

def job_keep_alive():
    """Hace ping al endpoint /ping para mantener el servidor despierto en Render Free."""
    if not WEBHOOK_URL:
        return

    url = f"{WEBHOOK_URL.rstrip('/')}/ping"
    try:
        import requests
        resp = requests.get(url, timeout=10)
        logger.info(f"[KEEP ALIVE] Ping a {url} → Status: {resp.status_code}")
    except Exception as e:
        logger.warning(f"[KEEP ALIVE] Falló el ping a {url}: {e}")


# ─── Inicialización del scheduler ────────────────────────────────────────────

def start_scheduler():
    """Inicia el scheduler con todos los jobs configurados."""
    if scheduler.running:
        return

    # Procesar cola cada 60 segundos
    scheduler.add_job(
        job_process_notification_queue,
        "interval",
        seconds=60,
        id="process_queue",
        replace_existing=True,
        max_instances=1,
    )

    # Enviar mensajes según fase cada 3 minutos (detecta internamente la ventana necesaria)
    scheduler.add_job(
        job_send_scheduled_messages,
        "interval",
        minutes=3,
        id="send_scheduled",
        replace_existing=True,
        max_instances=1,
    )

    # Recordatorio pastilla 1 (Anciocrol) — hora UTC configurable
    scheduler.add_job(
        job_pill_reminder_1,
        "cron",
        hour=PILL_REMINDER_1_HOUR_UTC,
        minute=PILL_REMINDER_1_MIN_UTC,
        id="pill_reminder_1",
        replace_existing=True,
    )

    # Recordatorio pastilla 2 (Pasinerva) — hora UTC configurable
    scheduler.add_job(
        job_pill_reminder_2,
        "cron",
        hour=PILL_REMINDER_2_HOUR_UTC,
        minute=PILL_REMINDER_2_MIN_UTC,
        id="pill_reminder_2",
        replace_existing=True,
    )

    # Actualizar racha diaria a las 00:01 UTC
    scheduler.add_job(
        job_update_daily_streak,
        "cron",
        hour=0,
        minute=1,
        id="daily_streak",
        replace_existing=True,
    )

    # Revisar inactividad cada 6 horas
    scheduler.add_job(
        job_check_inactive_users,
        "interval",
        hours=6,
        id="check_inactive",
        replace_existing=True,
        max_instances=1,
    )

    # Keep Alive para Render (cada 14 minutos)
    scheduler.add_job(
        job_keep_alive,
        "interval",
        minutes=14,
        id="keep_alive",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("✅ Scheduler iniciado con 7 jobs activos (incluyendo 2 recordatorios de pastillas y frecuencia nocturna).")
