"""
invitations.py — Servicio de invitaciones para ayudantes.
Genera tokens únicos, los valida y hace trazabilidad.
"""
import logging
from typing import Optional, Dict, Tuple

from app.config import MAX_HELPERS, INVITATION_EXPIRY_HOURS, TELEGRAM_BOT_TOKEN
from app.services import firebase_db as fdb

logger = logging.getLogger(__name__)


def generate_invitation_links(telegram_id: str) -> Tuple[str, str]:
    """
    Genera un token único de invitación para Persona2 y Persona3.
    El mismo token puede ser usado por hasta MAX_HELPERS ayudantes.
    Retorna (token, link_telegram)
    """
    user = fdb.get_user(telegram_id)
    if not user:
        raise ValueError(f"Usuario {telegram_id} no encontrado.")

    # Calcular cuántos ayudantes ya tiene
    ayudantes_actuales = len(user.get("ayudantes", {}))
    usos_restantes = MAX_HELPERS - ayudantes_actuales

    if usos_restantes <= 0:
        raise ValueError("Ya has alcanzado el número máximo de ayudantes.")

    token = fdb.create_invitation(telegram_id, max_usos=usos_restantes)

    # El bot de Telegram usa deep links: t.me/BOT_USERNAME?start=TOKEN
    # Para obtener el username del bot desde el token de configuración
    link = f"https://t.me/TU_BOT_USERNAME?start=inv_{token}"

    logger.info(f"Invitación generada: token={token}, para usuario={telegram_id}")
    return token, link


def validate_and_consume(token: str) -> Optional[Dict]:
    """
    Valida un token de invitación y consume un uso.
    Retorna el dict de la invitación si es válida, None si no.
    """
    inv = fdb.get_invitation(token)
    if not inv:
        logger.warning(f"Token de invitación no encontrado: {token}")
        return None
    if not inv.get("activo"):
        logger.warning(f"Token expirado o inválido: {token}")
        return None

    consumed = fdb.use_invitation(token)
    if not consumed:
        return None

    return inv


def register_as_helper(
    token: str,
    helper_telegram_id: str,
    helper_username: str,
    helper_nombre: str
) -> Dict:
    """
    Valida el token, registra al ayudante y lo vincula al usuario principal.
    """
    inv = validate_and_consume(token)
    if not inv:
        raise ValueError("El link de invitación no es válido o expiró.")

    usuario_principal_id = inv["usuario_principal_id"]
    user = fdb.get_user(usuario_principal_id)
    if not user:
        raise ValueError("Usuario principal no encontrado.")

    # Determinar rol (Persona2 o Persona3) basándose en cuántos ya hay
    ayudantes = user.get("ayudantes", {})
    rol = "Persona2" if len(ayudantes) == 0 else "Persona3"

    # Verificar que el ayudante no esté registrado ya
    existing_helper = fdb.get_helper(helper_telegram_id)
    if existing_helper and existing_helper.get("usuario_principal_id") == usuario_principal_id:
        raise ValueError("Ya estás registrado como ayudante de este usuario.")

    helper = fdb.register_helper(
        helper_telegram_id=helper_telegram_id,
        username=helper_username,
        nombre=helper_nombre,
        usuario_principal_id=usuario_principal_id,
        rol=rol,
    )

    fdb.log_event(
        usuario_principal_id,
        "ayudante_registrado",
        f"{helper_nombre} ({rol}) se unió como ayudante",
        {"helper_id": helper_telegram_id}
    )

    return {
        "helper": helper,
        "usuario_principal_id": usuario_principal_id,
        "usuario_principal": user,
        "rol": rol,
    }
