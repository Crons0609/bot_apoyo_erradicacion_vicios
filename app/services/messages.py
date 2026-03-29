"""
messages.py — Motor de mensajes motivacionales.
Maneja plantillas por vicio, hora del día, estado emocional y contexto.
Usa rotación aleatoria controlada para evitar repeticiones consecutivas.
"""
import logging
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Banco de mensajes ───────────────────────────────────────────────────────

MENSAJES: Dict[str, Dict[str, List[str]]] = {
    "general": {
        "mañana": [
            "☀️ Buenos días, {nombre}. Un nuevo día sin el vicio es un gran logro. ¡Tú puedes!",
            "🌅 {nombre}, empieza el día con una decisión: hoy es un día más lejos de tu viejo hábito.",
            "💪 Cada mañana que te despiertas decidido vale más que mil promesas. Buenos días, {nombre}.",
            "🌄 El día de hoy no te pide que seas perfecto, solo que sigas intentando. Buenos días.",
        ],
        "tarde": [
            "🌞 A mitad del día, {nombre}. ¿Cómo vas? Estás más cerca del final que del principio.",
            "⚡ Tardes como estas son las que más forjan el carácter. Sigue adelante, {nombre}.",
            "🕐 Ya llevas la mitad del día. Cada hora que pasa suma a tu racha. ¡Vas muy bien!",
        ],
        "noche": [
            "🌙 La noche puede ser difícil, {nombre}. Recuerda: después de cada noche, hay un amanecer.",
            "😴 Es normal sentir más impulsos de noche. Respira, bebe agua y recuerda tu propósito.",
            "⭐ Aguanta esta noche, {nombre}. Mañana te despertarás con un día más en tu racha.",
            "🌠 Las noches fuertes construyen días épicos. Tú lo sabes mejor que nadie.",
        ],
        "madrugada": [
            "🌌 Son momentos difíciles, {nombre}. Pero el hecho de que estés aquí significa que sigues luchando.",
            "🕯️ La madrugada es una prueba de fuego. Quien pasa la noche en pie de lucha, gana el día.",
            "🌃 A esta hora, cada minuto que pasa sin caer es una victoria pequeña pero real.",
        ],
        "crisis": [
            "🆘 Entiendo que estás en un momento difícil, {nombre}. Respira. Esto también pasará.",
            "💙 La ansiedad es temporal. El impulso dura minutos. Tu bienestar dura toda la vida.",
            "📞 Llama a tu ayudante ahora mismo. No estás solo/a en esto.",
            "🧊 Pon tu cara en agua fría o toma hielo en las manos. Tu cuerpo calmará tu mente.",
        ],
        "logro": [
            "🏆 ¡Felicidades, {nombre}! Completaste otra misión. Cada pequeño paso suma.",
            "🎉 ¡Bravo! Acabas de demostrar que puedes. Eso no tiene precio.",
            "⭐ Misión completada. Tu racha sigue viva y tu XP crece. ¡Sigue así!",
        ],
        "recaida": [
            "💔 Una recaída no es el final, {nombre}. Es una señal de que el camino sigue.",
            "🌱 Cada árbol grande ha caído antes. Lo que importa es volver a levantarse.",
            "🔄 Reiniciar no es perder. Es aprender cuándo y por qué sucedió para que no vuelva a pasar.",
        ],
        "inicio_semana": [
            "📅 Nueva semana, {nombre}. Es tu oportunidad de hacer que la próxima semana cuente.",
            "💫 Lunes de nuevas oportunidades. Tu plan sigue activo. ¿Listo para ganar esta semana?",
        ],
        "fin_semana": [
            "🎊 Llegaste al fin de semana, {nombre}. ¡Otra semana sin ceder. Mereces reconocerlo!",
            "🛡️ Los fines de semana son los más difíciles. Sé tu propio guardián estas 48 horas.",
        ],
        "silencio": [
            "👋 Hola, {nombre}. Llevamos un rato sin saber de ti. ¿Cómo estás?",
            "💌 Solo quería recordarte que tu plan sigue activo y tu racha no ha terminado.",
        ],
    },
    "Alcohol": {
        "noche": [
            "🍵 Esta noche, cambia la copa por una taza de té caliente. Tu hígado te lo agradecerá.",
            "🌙 Hoy, {nombre}, por cada impulso de beber, bebe un vaso grande de agua. Funciona.",
        ],
    },
    "Cigarros": {
        "crisis": [
            "🚬 Ese cigarrillo que sientes, dura 3 minutos. La satisfacción de no fumarlo dura toda la vida.",
            "🫁 Respira profundo sin cigarrillo. Ese aire limpio ya está sanando tus pulmones.",
        ],
    },
    "Apuestas": {
        "noche": [
            "🎰 Cierra las apps de apuestas por esta noche. El dinero que no pierdes es el que ganas.",
            "💸 Cada vez que no apuestas, estás apostando por tu futuro.",
        ],
    },
}

# Último mensaje enviado por usuario (para anti-repetición en memoria)
_ultimo_mensaje: Dict[str, str] = {}


def _hora_del_dia() -> str:
    hour = datetime.now(timezone.utc).hour
    if 6 <= hour < 13:
        return "mañana"
    elif 13 <= hour < 20:
        return "tarde"
    elif 20 <= hour < 24:
        return "noche"
    else:
        return "madrugada"


def get_motivational_message(
    nombre: str,
    vicio: Optional[str] = None,
    contexto: str = "auto",
    usuario_id: Optional[str] = None
) -> str:
    """
    Genera un mensaje motivacional evitando repetición consecutiva.
    
    Args:
        nombre: Nombre del usuario para personalizar.
        vicio: Vicio específico para mensajes extra personalizados.
        contexto: auto | mañana | tarde | noche | madrugada | crisis | logro | recaida | silencio
        usuario_id: ID para rastrear último mensaje enviado.
    """
    if contexto == "auto":
        contexto = _hora_del_dia()

    # Construir pool de candidatos
    pool: List[str] = []

    # Primero buscar en el vicio específico
    if vicio and vicio in MENSAJES and contexto in MENSAJES[vicio]:
        pool.extend(MENSAJES[vicio][contexto])

    # Luego del banco general
    if contexto in MENSAJES["general"]:
        pool.extend(MENSAJES["general"][contexto])

    if not pool:
        pool = MENSAJES["general"]["tarde"]  # Fallback

    # Anti-repetición
    ultimo = _ultimo_mensaje.get(usuario_id or nombre)
    candidatos = [m for m in pool if m != ultimo] or pool

    seleccionado = random.choice(candidatos)
    msg = seleccionado.format(nombre=nombre)

    if usuario_id:
        _ultimo_mensaje[usuario_id] = seleccionado

    return msg


def get_helper_notification(
    nombre_principal: str,
    nombre_ayudante: str,
    tipo: str = "recordatorio"
) -> str:
    """Genera mensajes específicos para los ayudantes."""
    mensajes_ayudante = {
        "recordatorio": f"👋 Hola {nombre_ayudante}, es un buen momento para revisar cómo está {nombre_principal}. Un mensaje o llamada puede marcar la diferencia.",
        "crisis": f"⚠️ {nombre_ayudante}, {nombre_principal} puede estar pasando un momento difícil ahora. Por favor, intenta contactarlo/a lo antes posible.",
        "mision": f"📋 {nombre_ayudante}, {nombre_principal} tiene una misión por completar. Tu apoyo puede motivarlo/a a terminarla.",
        "recaida": f"💙 {nombre_ayudante}, {nombre_principal} ha reportado una recaída. Es el momento más importante para estar presente. Contáctalo/a con compasión.",
        "logro": f"🎉 {nombre_ayudante}, ¡{nombre_principal} completó una misión exitosamente! Mándale un mensaje de felicitación.",
    }
    return mensajes_ayudante.get(tipo, mensajes_ayudante["recordatorio"])


def get_welcome_message(nombre: str, vicio: str, duracion_meses: int) -> str:
    return (
        f"🎯 *¡Bienvenido/a a tu plan, {nombre}!*\n\n"
        f"Has decidido enfrentar tu hábito con: *{vicio}*.\n"
        f"Tu plan tiene una duración de *{duracion_meses} meses*.\n\n"
        "Esto no será fácil, pero tampoco será imposible. "
        "Cada día sin caer es una victoria que se acumula.\n\n"
        "🌟 _Tu futuro yo ya te está agradeciendo._\n\n"
        "Escribe /misiones para ver tu primera misión del día."
    )


def get_relapse_response(nombre: str, racha_previa: int) -> str:
    return (
        f"💙 *{nombre}, entiendo que fue difícil.*\n\n"
        f"Tenías una racha de *{racha_previa} días*. Eso no desaparece.\n"
        "Una recaída no define quién eres. Define de qué material estás hecho/a.\n\n"
        "🔄 Tu plan de recuperación se activó. Hablemos:\n"
        "¿Qué pasó? ¿Qué lo desencadenó? Entender esto es el siguiente paso.\n\n"
        "_Pulsa el botón de abajo para empezar tu plan de recuperación._"
    )
