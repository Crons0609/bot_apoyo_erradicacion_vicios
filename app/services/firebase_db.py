"""
firebase_db.py — Servicio central de Firebase Realtime Database.
Usa el Admin SDK de Python para todas las operaciones del backend.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, db

from app.config import FIREBASE_CREDENTIALS_PATH, FIREBASE_DATABASE_URL

logger = logging.getLogger(__name__)

# ─── Inicialización ──────────────────────────────────────────────────────────

def _initialize_firebase() -> None:
    """Inicializa la app de Firebase Admin si no está ya inicializada."""
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DATABASE_URL})
            logger.info("✅ Firebase Admin SDK inicializado correctamente.")
        except Exception as e:
            logger.error(f"❌ Error inicializando Firebase Admin SDK: {e}")
            raise

_initialize_firebase()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ref(path: str) -> db.Reference:
    return db.reference(path)


# ─── USUARIOS ────────────────────────────────────────────────────────────────

def get_user(telegram_id: str) -> Optional[Dict]:
    """Obtiene los datos de un usuario por su Telegram ID."""
    snap = _ref(f"usuarios/{telegram_id}").get()
    return snap if snap else None


def save_user(telegram_id: str, data: Dict) -> None:
    """Guarda o actualiza los datos de un usuario."""
    _ref(f"usuarios/{telegram_id}").update({
        **data,
        "ultima_actualizacion": _now_iso()
    })


def create_user(telegram_id: str, username: str, nombre: str, foto_perfil: str = "") -> Dict:
    """
    Crea un nuevo usuario en la base de datos con valores iniciales.
    Retorna el diccionario del usuario creado.
    """
    user_data = {
        "id_interno": str(uuid.uuid4()),
        "telegram_id": telegram_id,
        "username": username,
        "nombre": nombre,
        "foto_perfil": foto_perfil,
        "vicio": None,
        "fecha_inicio": None,
        "duracion_meses": None,
        "estado_plan": "configurando",   # configurando | activo | pausado | completado | abandonado
        "racha_dias": 0,
        "xp": 0,
        "nivel": 1,
        "fase_actual": "dia_1",           # dia_1 | semana_1 | semana_2 | semana_3+ | mes_2+
        "ayudantes": {},                  # {telegram_id_ayudante: true}
        "conversacion_estado": "inicio",  # Estado de la máquina de conversación
        "retencion_compromiso": {
            "estado": "sin_configurar",   # sin_configurar | pendiente_link | custodia_activa | completado | cancelado
            "monto_simbolico": 0,
            "transaccion_id": None,
            "proveedor": None
        },
        "creado_el": _now_iso(),
        "ultima_actualizacion": _now_iso()
    }
    _ref(f"usuarios/{telegram_id}").set(user_data)
    logger.info(f"✅ Nuevo usuario creado: {telegram_id} ({nombre})")
    return user_data


def get_all_users() -> List[Dict]:
    """Obtiene todos los usuarios registrados."""
    snap = _ref("usuarios").get()
    if not snap:
        return []
    return [{"_key": k, **v} for k, v in snap.items() if v]


def update_user_field(telegram_id: str, field: str, value: Any) -> None:
    """Actualiza un campo específico del usuario."""
    _ref(f"usuarios/{telegram_id}/{field}").set(value)
    _ref(f"usuarios/{telegram_id}/ultima_actualizacion").set(_now_iso())


# ─── AYUDANTES ───────────────────────────────────────────────────────────────

def get_helper(helper_telegram_id: str) -> Optional[Dict]:
    """Obtiene los datos de un ayudante."""
    return _ref(f"ayudantes/{helper_telegram_id}").get()


def register_helper(helper_telegram_id: str, username: str, nombre: str,
                    usuario_principal_id: str, rol: str = "Persona2") -> Dict:
    """Registra a un nuevo ayudante vinculado a un usuario principal."""
    helper_data = {
        "telegram_id": helper_telegram_id,
        "username": username,
        "nombre": nombre,
        "usuario_principal_id": usuario_principal_id,
        "rol": rol,
        "registrado_el": _now_iso()
    }
    _ref(f"ayudantes/{helper_telegram_id}").set(helper_data)
    # Añadir referencia en el usuario principal
    _ref(f"usuarios/{usuario_principal_id}/ayudantes/{helper_telegram_id}").set(True)
    logger.info(f"✅ Ayudante registrado: {helper_telegram_id} para usuario {usuario_principal_id}")
    return helper_data


def get_helpers_for_user(usuario_principal_id: str) -> List[Dict]:
    """Retorna la lista de ayudantes de un usuario principal."""
    helpers_ids = _ref(f"usuarios/{usuario_principal_id}/ayudantes").get()
    if not helpers_ids:
        return []
    result = []
    for helper_id in helpers_ids:
        helper = get_helper(helper_id)
        if helper:
            result.append(helper)
    return result


# ─── INVITACIONES ────────────────────────────────────────────────────────────

def create_invitation(usuario_principal_id: str, max_usos: int = 2) -> str:
    """Crea un token único de invitación y lo guarda en Firebase."""
    token = str(uuid.uuid4()).replace("-", "")[:24]
    _ref(f"invitaciones/{token}").set({
        "usuario_principal_id": usuario_principal_id,
        "usos_restantes": max_usos,
        "creado_el": _now_iso(),
        "activo": True
    })
    return token


def get_invitation(token: str) -> Optional[Dict]:
    """Obtiene una invitación por token."""
    return _ref(f"invitaciones/{token}").get()


def use_invitation(token: str) -> bool:
    """
    Consume un uso de la invitación. Retorna True si fue válida.
    Marca como inactiva si los usos llegan a 0.
    """
    inv = get_invitation(token)
    if not inv or not inv.get("activo"):
        return False
    usos = inv.get("usos_restantes", 0)
    if usos <= 0:
        return False
    new_usos = usos - 1
    updates: Dict = {"usos_restantes": new_usos}
    if new_usos <= 0:
        updates["activo"] = False
    _ref(f"invitaciones/{token}").update(updates)
    return True


# ─── MISIONES ────────────────────────────────────────────────────────────────

MISIONES_CATALOGO = [
    {"id": "agua", "titulo": "Bebe agua 💧", "desc": "Toma un vaso grande de agua ahora mismo.", "xp": 5, "categoria": "salud"},
    {"id": "caminata", "titulo": "Camina 10 minutos 🚶", "desc": "Sal a caminar aunque sea dentro de tu espacio.", "xp": 10, "categoria": "actividad"},
    {"id": "respirar", "titulo": "Respira profundo 🌬️", "desc": "Haz 10 respiraciones profundas, inhala 4s, exhala 6s.", "xp": 5, "categoria": "mindfulness"},
    {"id": "escribir_razones", "titulo": "Escribe tus razones ✍️", "desc": "Escribe 3 razones por las que quieres lograrlo.", "xp": 15, "categoria": "reflexion"},
    {"id": "alejarte", "titulo": "Aléjate del trigger ⏱️", "desc": "Ponte en un lugar seguro 15 minutos, lejos del gatillo.", "xp": 10, "categoria": "crisis"},
    {"id": "llamar_ayudante", "titulo": "Llama a tu ayudante 📞", "desc": "Contáctate con tu persona de apoyo ahora.", "xp": 20, "categoria": "social"},
    {"id": "sin_celular", "titulo": "Pausa digital 📵", "desc": "No uses el celular por 20 minutos (excepto para esto).", "xp": 10, "categoria": "digital"},
    {"id": "emociones", "titulo": "Registra tus emociones 💭", "desc": "¿Cómo te sientes ahora mismo? Descríbelo en 3 palabras.", "xp": 10, "categoria": "reflexion"},
    {"id": "meditacion", "titulo": "Medita 5 minutos 🧘", "desc": "Busca un lugar tranquilo y enfócate en tu respiración.", "xp": 15, "categoria": "mindfulness"},
    {"id": "logro_dia", "titulo": "Celebra tu logro de hoy 🏆", "desc": "Has llegado hasta aquí. Reconoce tu esfuerzo.", "xp": 20, "categoria": "motivacion"},
]


def log_mission_completed(usuario_id: str, mision_id: str, xp_ganada: int) -> str:
    """Registra el completado de una misión y retorna el ID del log."""
    log_id = str(uuid.uuid4())
    _ref(f"misiones_logs/{log_id}").set({
        "usuario_id": usuario_id,
        "mision_id": mision_id,
        "completada": True,
        "timestamp": _now_iso(),
        "xp_ganada": xp_ganada
    })
    return log_id


def get_user_mission_logs(usuario_id: str, limit: int = 20) -> List[Dict]:
    """Obtiene los últimos logs de misiones de un usuario."""
    snap = _ref("misiones_logs").order_by_child("usuario_id").equal_to(usuario_id).limit_to_last(limit).get()
    if not snap:
        return []
    return sorted(snap.values(), key=lambda x: x.get("timestamp", ""), reverse=True)


# ─── RECAÍDAS ────────────────────────────────────────────────────────────────

def log_relapse(usuario_id: str, racha_previa: int, detalles: str = "") -> str:
    """Registra una recaída sin borrar el progreso completo."""
    relapse_id = str(uuid.uuid4())
    _ref(f"recaidas/{relapse_id}").set({
        "usuario_id": usuario_id,
        "timestamp": _now_iso(),
        "racha_previa": racha_previa,
        "detalles": detalles,
        "recuperado": False
    })
    return relapse_id


def get_user_relapses(usuario_id: str) -> List[Dict]:
    """Obtiene el historial de recaídas de un usuario."""
    snap = _ref("recaidas").order_by_child("usuario_id").equal_to(usuario_id).get()
    if not snap:
        return []
    return sorted(snap.values(), key=lambda x: x.get("timestamp", ""), reverse=True)


# ─── EVENTOS / LOG GENERAL ───────────────────────────────────────────────────

def log_event(usuario_id: str, tipo: str, descripcion: str, metadata: Optional[Dict] = None) -> None:
    """Registra un evento en el historial general del sistema."""
    event_id = str(uuid.uuid4())
    _ref(f"eventos/{event_id}").set({
        "usuario_id": usuario_id,
        "tipo": tipo,
        "descripcion": descripcion,
        "metadata": metadata or {},
        "timestamp": _now_iso()
    })


def get_recent_events(limit: int = 50) -> List[Dict]:
    """Obtiene los eventos más recientes del sistema."""
    snap = _ref("eventos").order_by_child("timestamp").limit_to_last(limit).get()
    if not snap:
        return []
    return sorted(snap.values(), key=lambda x: x.get("timestamp", ""), reverse=True)


# ─── NOTIFICACIONES ──────────────────────────────────────────────────────────

def enqueue_notification(telegram_id: str, mensaje: str, metadata: Optional[Dict] = None) -> None:
    """Añade una notificación a la cola para el scheduler."""
    notif_id = str(uuid.uuid4())
    _ref(f"cola_notificaciones/{notif_id}").set({
        "telegram_id": telegram_id,
        "mensaje": mensaje,
        "metadata": metadata or {},
        "creado_el": _now_iso(),
        "enviado": False,
        "intentos": 0
    })


def get_pending_notifications(limit: int = 50) -> Dict:
    """Obtiene las notificaciones pendientes de enviar."""
    snap = _ref("cola_notificaciones").order_by_child("enviado").equal_to(False).limit_to_first(limit).get()
    return snap or {}


def mark_notification_sent(notif_id: str) -> None:
    """Marca una notificación como enviada."""
    _ref(f"cola_notificaciones/{notif_id}").update({
        "enviado": True,
        "enviado_el": _now_iso()
    })


def mark_notification_failed(notif_id: str) -> None:
    """Incrementa el contador de intentos fallidos."""
    snap = _ref(f"cola_notificaciones/{notif_id}/intentos").get()
    intentos = (snap or 0) + 1
    _ref(f"cola_notificaciones/{notif_id}").update({
        "intentos": intentos,
        "ultimo_intento": _now_iso()
    })
