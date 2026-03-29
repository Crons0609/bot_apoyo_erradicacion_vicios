"""
escrow.py — Módulo abstracto de retención/escrow/compromiso.
NO maneja dinero real. Es un stub preparado para integrarse con
una pasarela de pago o proveedor de escrow certificado.
El sistema solo registra estados y genera links de terceros.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.services import firebase_db as fdb

logger = logging.getLogger(__name__)

# ─── Estados posibles del compromiso ────────────────────────────────────────
ESTADO_SIN_CONFIGURAR = "sin_configurar"
ESTADO_LINK_ENVIADO = "link_enviado"
ESTADO_CUSTODIA_ACTIVA = "custodia_activa"   # Tercero confirmó la retención
ESTADO_COMPLETADO = "completado"              # Plan completado, retención liberada
ESTADO_CANCELADO = "cancelado"
ESTADO_FALLIDO = "fallido"


def initiate_commitment(telegram_id: str, monto_simbolico: float, proveedor: str = "stub") -> Dict:
    """
    Inicia el proceso de retención de compromiso.
    
    En producción, aquí se llamaría al API del proveedor de escrow autorizado
    para generar un link de pago único. Por ahora, es un stub.
    
    El sistema NUNCA custodia el dinero. Solo registra el estado.
    """
    if proveedor == "stub":
        # STUB: En producción reemplazar con integración real (ej. Stripe, PayPal, escrow.com)
        logger.warning("[ESCROW STUB] Usando implementación stub. No se procesa dinero real.")
        transaccion_id = f"stub_txn_{str(uuid.uuid4())[:12]}"
        link_pago = f"https://TU_PROVEEDOR_ESCROW.com/pagar/{transaccion_id}"  # REEMPLAZAR
    else:
        # EXTENSIÓN: Llamar al proveedor real aquí
        raise NotImplementedError(f"Proveedor de escrow '{proveedor}' no implementado aún.")

    compromiso = {
        "estado": ESTADO_LINK_ENVIADO,
        "monto_simbolico": monto_simbolico,
        "transaccion_id": transaccion_id,
        "proveedor": proveedor,
        "link_pago": link_pago,
        "iniciado_el": datetime.now(timezone.utc).isoformat(),
    }

    fdb.save_user(telegram_id, {"retencion_compromiso": compromiso})
    fdb.log_event(telegram_id, "escrow_iniciado", f"Link de compromiso enviado. Proveedor: {proveedor}")

    return compromiso


def confirm_commitment(telegram_id: str, transaccion_id: str) -> bool:
    """
    Webhook callback: El proveedor externo confirma que se hizo la retención.
    Solo actualiza el estado en Firebase; el dinero nunca pasa por el sistema.
    """
    user = fdb.get_user(telegram_id)
    if not user:
        return False

    compromiso = user.get("retencion_compromiso", {})
    if compromiso.get("transaccion_id") != transaccion_id:
        logger.warning(f"[ESCROW] transaccion_id no coincide para {telegram_id}")
        return False

    fdb.save_user(telegram_id, {
        "retencion_compromiso": {
            **compromiso,
            "estado": ESTADO_CUSTODIA_ACTIVA,
            "confirmado_el": datetime.now(timezone.utc).isoformat(),
        }
    })
    fdb.log_event(telegram_id, "escrow_confirmado", "El proveedor confirmó la retención del compromiso.")
    return True


def release_commitment(telegram_id: str, motivo: str = "plan_completado") -> bool:
    """
    Marca el compromiso como liberado (cuando el usuario completa el plan).
    El proveedor externo devuelve el dinero al usuario.
    """
    user = fdb.get_user(telegram_id)
    if not user:
        return False

    compromiso = user.get("retencion_compromiso", {})
    fdb.save_user(telegram_id, {
        "retencion_compromiso": {
            **compromiso,
            "estado": ESTADO_COMPLETADO,
            "liberado_el": datetime.now(timezone.utc).isoformat(),
            "motivo_liberacion": motivo,
        }
    })
    fdb.log_event(telegram_id, "escrow_liberado", f"Compromiso liberado: {motivo}")
    return True


def get_commitment_status(telegram_id: str) -> Optional[Dict]:
    """Obtiene el estado actual del compromiso del usuario."""
    user = fdb.get_user(telegram_id)
    if not user:
        return None
    return user.get("retencion_compromiso")
