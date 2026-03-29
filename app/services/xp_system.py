"""
xp_system.py — Sistema de experiencia, niveles, insignias y rachas.
"""
import logging
from typing import Dict, Tuple, Optional

from app.services import firebase_db as fdb

logger = logging.getLogger(__name__)

# ─── Configuración de niveles ────────────────────────────────────────────────

NIVELES = [
    {"nivel": 1,  "nombre": "Iniciado",       "xp_requerida": 0},
    {"nivel": 2,  "nombre": "Decidido",        "xp_requerida": 50},
    {"nivel": 3,  "nombre": "Firme",           "xp_requerida": 150},
    {"nivel": 4,  "nombre": "Resistente",      "xp_requerida": 300},
    {"nivel": 5,  "nombre": "Constante",       "xp_requerida": 500},
    {"nivel": 6,  "nombre": "Tenaz",           "xp_requerida": 800},
    {"nivel": 7,  "nombre": "Inquebrantable",  "xp_requerida": 1200},
    {"nivel": 8,  "nombre": "Inspirador",      "xp_requerida": 1800},
    {"nivel": 9,  "nombre": "Campeón",         "xp_requerida": 2600},
    {"nivel": 10, "nombre": "Leyenda",         "xp_requerida": 3600},
]

# ─── Recompensas de XP ───────────────────────────────────────────────────────

XP_MISION_COMPLETADA = 10
XP_DIA_SIN_CONSUMO = 20
XP_RACHA_BONUS_SEMANAL = 50       # Bonus al completar 7 días
XP_RACHA_BONUS_MENSUAL = 200      # Bonus al completar 30 días
XP_ACTIVIDAD_NOCTURNA = 15        # XP extra por completar misión de noche (20:00 - 06:00)
PENALIZACION_RECAIDA = -15        # Penalización suave, nunca destruye todo


def get_nivel_actual(xp: int) -> Dict:
    """Retorna el nivel actual basado en XP total."""
    nivel_actual = NIVELES[0]
    for nivel_info in NIVELES:
        if xp >= nivel_info["xp_requerida"]:
            nivel_actual = nivel_info
    return nivel_actual


def get_xp_para_siguiente_nivel(xp: int) -> Tuple[int, int]:
    """Retorna (XP actual en nivel, XP para subir de nivel)."""
    nivel_actual = get_nivel_actual(xp)
    idx = NIVELES.index(nivel_actual)
    if idx >= len(NIVELES) - 1:
        return (xp - nivel_actual["xp_requerida"], 0)  # Nivel máximo
    siguiente = NIVELES[idx + 1]
    xp_en_nivel = xp - nivel_actual["xp_requerida"]
    xp_para_subir = siguiente["xp_requerida"] - nivel_actual["xp_requerida"]
    return (xp_en_nivel, xp_para_subir)


def add_xp(telegram_id: str, cantidad: int, motivo: str = "") -> Dict:
    """
    Añade XP a un usuario, verifica subida de nivel.
    Retorna dict con info de la transacción XP.
    """
    user = fdb.get_user(telegram_id)
    if not user:
        logger.warning(f"add_xp: Usuario {telegram_id} no encontrado.")
        return {}

    xp_anterior = user.get("xp", 0)
    nivel_anterior = get_nivel_actual(xp_anterior)

    # XP nunca baja de 0
    nueva_xp = max(0, xp_anterior + cantidad)

    nivel_nuevo = get_nivel_actual(nueva_xp)
    subio_nivel = nivel_nuevo["nivel"] > nivel_anterior["nivel"]

    fdb.save_user(telegram_id, {"xp": nueva_xp, "nivel": nivel_nuevo["nivel"]})

    # Log del evento
    fdb.log_event(
        telegram_id,
        "xp_ganada" if cantidad > 0 else "xp_penalizada",
        f"{motivo}: {'+' if cantidad >= 0 else ''}{cantidad} XP",
        {"xp_anterior": xp_anterior, "xp_nueva": nueva_xp}
    )

    logger.info(f"XP: {telegram_id} {'+' if cantidad >= 0 else ''}{cantidad} → {nueva_xp} XP ({nivel_nuevo['nombre']})")

    return {
        "xp_anterior": xp_anterior,
        "xp_nueva": nueva_xp,
        "xp_delta": cantidad,
        "nivel_anterior": nivel_anterior,
        "nivel_nuevo": nivel_nuevo,
        "subio_nivel": subio_nivel,
    }


def update_streak(telegram_id: str, nueva_racha: int) -> None:
    """Actualiza la racha del usuario y da bonus si corresponde."""
    fdb.update_user_field(telegram_id, "racha_dias", nueva_racha)

    if nueva_racha > 0 and nueva_racha % 7 == 0:
        add_xp(telegram_id, XP_RACHA_BONUS_SEMANAL, f"Bonus de racha: {nueva_racha} días")
    if nueva_racha > 0 and nueva_racha % 30 == 0:
        add_xp(telegram_id, XP_RACHA_BONUS_MENSUAL, f"Bonus mensual: {nueva_racha} días")


def calculate_phase(dias_activo: int) -> str:
    """
    Calcula la fase del ciclo (para determinar frecuencia de mensajes).
    Retorna el identificador de fase.
    """
    if dias_activo <= 1:
        return "dia_1"       # cada 3 min
    elif dias_activo <= 3:
        return "dias_2_3"    # cada 3 min
    elif dias_activo <= 7:
        return "semana_1"    # cada 10 min
    elif dias_activo <= 14:
        return "semana_2"    # cada 30 min
    elif dias_activo <= 60:
        return "semana_3+"   # cada 60 min
    else:
        return "mes_2+"      # cada 120 min


PHASE_INTERVALS: Dict[str, int] = {
    "dia_1":   3 * 60,      # 3 minutos en segundos
    "dias_2_3": 3 * 60,
    "semana_1": 10 * 60,
    "semana_2": 30 * 60,
    "semana_3+": 60 * 60,
    "mes_2+":  120 * 60,
}


def get_progress_summary(telegram_id: str) -> Optional[str]:
    """Retorna un resumen de progreso formateado para Telegram."""
    user = fdb.get_user(telegram_id)
    if not user:
        return None

    nombre = user.get("nombre", "amigo/a")
    vicio = user.get("vicio", "sin registrar")
    racha = user.get("racha_dias", 0)
    xp = user.get("xp", 0)
    nivel_info = get_nivel_actual(xp)
    xp_actual, xp_para_subir = get_xp_para_siguiente_nivel(xp)

    barra_progreso = ""
    if xp_para_subir > 0:
        progreso = min(int((xp_actual / xp_para_subir) * 10), 10)
        barra_progreso = "█" * progreso + "░" * (10 - progreso)
        barra_str = f"`{barra_progreso}` {xp_actual}/{xp_para_subir} XP"
    else:
        barra_str = "🏆 Nivel máximo alcanzado"

    return (
        f"📊 *Progreso de {nombre}*\n\n"
        f"🎯 Vicio: {vicio}\n"
        f"🔥 Racha: {racha} días sin consumo\n"
        f"⭐ XP Total: {xp}\n"
        f"🏅 Nivel: {nivel_info['nivel']} — _{nivel_info['nombre']}_\n"
        f"📈 Progreso al siguiente: {barra_str}\n"
    )
