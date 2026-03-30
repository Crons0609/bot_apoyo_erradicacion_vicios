"""
scheduler.py — Worker de tareas programadas.
Usa APScheduler para enviar mensajes, calcular fases y gestionar la cola.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.services import firebase_db as fdb
from app.services import messages as msg
from app.services.xp_system import calculate_phase, PHASE_INTERVALS, update_streak
from app.config import WEBHOOK_URL

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="UTC")


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
                continue  # Descartar si falló demasiadas veces
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
    basado en su fase actual y calcula la próxima ventana de envío.
    """
    users = fdb.get_all_users()
    now = datetime.now(timezone.utc)

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
        intervalo_segundos = PHASE_INTERVALS.get(fase, 3600)

        # Verificar si ya se envió en esta ventana de tiempo
        ultimo_envio_str = user.get("ultimo_mensaje_programado")
        if ultimo_envio_str:
            try:
                ultimo_envio = datetime.fromisoformat(ultimo_envio_str)
                if (now - ultimo_envio).total_seconds() < intervalo_segundos:
                    continue  # No es momento todavía
            except ValueError:
                pass

        # Generar mensaje motivacional
        vicio = user.get("vicio")
        mensaje = msg.get_motivational_message(nombre=nombre, vicio=vicio, usuario_id=telegram_id)

        # Encolar para envío
        fdb.enqueue_notification(telegram_id, mensaje, {"tipo": "programado", "fase": fase})

        # Actualizar timestamp de último mensaje
        fdb.update_user_field(telegram_id, "ultimo_mensaje_programado", now.isoformat())


# ─── Job: actualizar racha diaria ────────────────────────────────────────────

def job_update_daily_streak():
    """
    Corre 1 vez por día (a las 00:01 UTC).
    Incrementa la racha de todos los usuarios activos que no hayan reportado recaída.
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

        # Milestone notifications
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
    Detecta usuarios que no han interactuado en más de 24 horas y envía un ping silencioso.
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
    """
    Hace un ping (GET request) al propio endpoint /ping del servidor.
    En la capa gratuita de Render (Web Service), esto ayuda a reiniciar el
    contador de inactividad de 15 minutos, manteniendo la app despierta.
    """
    if not WEBHOOK_URL:
        # Si no hay URL configurada, no hacemos ping externo
        return

    url = f"{WEBHOOK_URL.rstrip('/')}/ping"
    try:
        import requests
        resp = requests.get(url, timeout=10)
        logger.info(f"[KEEP ALIVE] Ping a {url} exitoso. Status: {resp.status_code}")
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

    # Enviar mensajes programados según fase cada 3 minutos
    scheduler.add_job(
        job_send_scheduled_messages,
        "interval",
        minutes=3,
        id="send_scheduled",
        replace_existing=True,
        max_instances=1,
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
    logger.info("✅ Scheduler iniciado con 5 jobs activos.")
