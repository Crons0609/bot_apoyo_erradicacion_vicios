"""
relapse.py — Lógica de recaídas y plan de recuperación.
Maneja el registro, notificación a ayudantes y recuperación de racha.
"""
import logging
from typing import Dict, List

from app.services import firebase_db as fdb
from app.services import messages as msg
from app.services.xp_system import PENALIZACION_RECAIDA, add_xp

logger = logging.getLogger(__name__)


def handle_relapse(telegram_id: str, detalles: str = "") -> Dict:
    """
    Procesa una recaída:
      1. Guarda el evento en Firebase
      2. Actualiza la racha (reducción suave, no a 0)
      3. Penaliza XP suavemente
      4. Activa el estado de recuperación
      5. Prepara notificaciones para ayudantes
    
    Retorna información completa del evento para el bot.
    """
    user = fdb.get_user(telegram_id)
    if not user:
        logger.warning(f"handle_relapse: Usuario {telegram_id} no encontrado.")
        return {}

    nombre = user.get("nombre", "Usuario")
    racha_actual = user.get("racha_dias", 0)

    # Reducción suave de racha (no va a 0 de golpe, pierde el 50% o al menos 1 día)
    reduccion = max(1, racha_actual // 2)
    nueva_racha = max(0, racha_actual - reduccion)

    # Guardar log de recaída
    relapse_id = fdb.log_relapse(telegram_id, racha_actual, detalles)

    # Actualizar racha y estado
    fdb.save_user(telegram_id, {
        "racha_dias": nueva_racha,
        "estado_plan": "recuperacion",
    })

    # Penalización suave de XP
    xp_result = add_xp(telegram_id, PENALIZACION_RECAIDA, "Recaída registrada")

    # Preparar mensajes para ayudantes
    helpers = fdb.get_helpers_for_user(telegram_id)
    mensajes_ayudantes = []
    for helper in helpers:
        msg_ayudante = msg.get_helper_notification(nombre, helper["nombre"], "recaida")
        mensajes_ayudantes.append({
            "telegram_id": helper["telegram_id"],
            "mensaje": msg_ayudante,
        })
        # Encolar notificación en Firebase para que el scheduler la procese
        fdb.enqueue_notification(helper["telegram_id"], msg_ayudante, {"tipo": "recaida", "usuario_id": telegram_id})

    # Mensaje empático para el usuario
    mensaje_usuario = msg.get_relapse_response(nombre, racha_actual)

    # Log del evento
    fdb.log_event(telegram_id, "recaida", f"Recaída registrada. Racha previa: {racha_actual}. Nueva racha: {nueva_racha}.")

    logger.info(f"[RECAÍDA] {telegram_id}: racha {racha_actual} → {nueva_racha}")

    return {
        "relapse_id": relapse_id,
        "racha_anterior": racha_actual,
        "nueva_racha": nueva_racha,
        "xp_result": xp_result,
        "mensaje_usuario": mensaje_usuario,
        "mensajes_ayudantes": mensajes_ayudantes,
        "nombre": nombre,
    }


def handle_recovery_start(telegram_id: str) -> bool:
    """
    Activa el plan de recuperación después de una recaída.
    """
    user = fdb.get_user(telegram_id)
    if not user:
        return False

    fdb.save_user(telegram_id, {
        "estado_plan": "activo",
        "conversacion_estado": "inicio",
    })
    fdb.log_event(telegram_id, "recuperacion_iniciada", "El usuario inició su plan de recuperación.")
    return True
