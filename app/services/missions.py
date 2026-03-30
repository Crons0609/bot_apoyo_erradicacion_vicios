"""
missions.py — CRUD completo de misiones en Firebase Realtime Database.
Las misiones pueden tener horario programado (para recordatorios automáticos como pastillas).
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import firebase_db as fdb

logger = logging.getLogger(__name__)


# ─── Catálogo base (misiones estáticas de referencia) ────────────────────────

MISIONES_BASE: List[Dict] = [
    {"id": "agua",            "nombre": "Bebe agua 💧",           "descripcion": "Toma un vaso grande de agua ahora mismo.",                 "categoria": "salud",       "puntos_recompensa": 5,  "activa": True},
    {"id": "caminata",        "nombre": "Camina 10 minutos 🚶",   "descripcion": "Sal a caminar aunque sea dentro de tu espacio.",            "categoria": "actividad",   "puntos_recompensa": 10, "activa": True},
    {"id": "respirar",        "nombre": "Respira profundo 🌬️",    "descripcion": "Haz 10 respiraciones profundas, inhala 4s, exhala 6s.",     "categoria": "mindfulness", "puntos_recompensa": 5,  "activa": True},
    {"id": "escribir_razones","nombre": "Escribe tus razones ✍️", "descripcion": "Escribe 3 razones por las que quieres lograrlo.",           "categoria": "reflexion",   "puntos_recompensa": 15, "activa": True},
    {"id": "alejarte",        "nombre": "Aléjate del trigger ⏱️", "descripcion": "Ponte en un lugar seguro 15 minutos, lejos del gatillo.",   "categoria": "crisis",      "puntos_recompensa": 10, "activa": True},
    {"id": "llamar_ayudante", "nombre": "Llama a tu ayudante 📞", "descripcion": "Contáctate con tu persona de apoyo ahora.",                 "categoria": "social",      "puntos_recompensa": 20, "activa": True},
    {"id": "sin_celular",     "nombre": "Pausa digital 📵",       "descripcion": "No uses el celular por 20 minutos (excepto para esto).",    "categoria": "digital",     "puntos_recompensa": 10, "activa": True},
    {"id": "emociones",       "nombre": "Registra emociones 💭",  "descripcion": "¿Cómo te sientes ahora mismo? Descríbelo en 3 palabras.",   "categoria": "reflexion",   "puntos_recompensa": 10, "activa": True},
    {"id": "meditacion",      "nombre": "Medita 5 minutos 🧘",    "descripcion": "Busca un lugar tranquilo y enfócate en tu respiración.",    "categoria": "mindfulness", "puntos_recompensa": 15, "activa": True},
    {"id": "logro_dia",       "nombre": "Celebra tu logro 🏆",    "descripcion": "Has llegado hasta aquí. Reconoce tu esfuerzo.",             "categoria": "motivacion",  "puntos_recompensa": 20, "activa": True},
    # Misiones de medicamentos (con horario_programado)
    {"id": "pill_anciocrol",  "nombre": "Pastilla Anciocrol 💊",  "descripcion": "Toma tu pastilla de Anciocrol. Es parte de tu recuperación.", "categoria": "medicamento", "puntos_recompensa": 10, "activa": True, "horario_programado": {"hora": 7, "minuto": 0}},
    {"id": "pill_pasinerva",  "nombre": "Pastilla Pasinerva 💊",  "descripcion": "Toma tu pastilla de Pasinerva. Cada dosis cuenta.",           "categoria": "medicamento", "puntos_recompensa": 10, "activa": True, "horario_programado": {"hora": 7, "minuto": 10}},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ref(path: str):
    from firebase_admin import db
    return db.reference(path)


# ─── Inicializar catálogo en Firebase si está vacío ──────────────────────────

def seed_default_missions() -> None:
    """
    Puebla Firebase con las misiones base si la colección está vacía.
    Llamar una vez al iniciar la aplicación.
    """
    snap = _ref("misiones").get()
    if snap:
        return  # Ya hay misiones, no sobrescribir
    for m in MISIONES_BASE:
        mision_id = m["id"]
        data = {
            **m,
            "creado_el": _now_iso(),
        }
        _ref(f"misiones/{mision_id}").set(data)
    logger.info(f"✅ {len(MISIONES_BASE)} misiones base registradas en Firebase.")


# ─── LECTURA ─────────────────────────────────────────────────────────────────

def get_all_missions() -> List[Dict]:
    """Retorna todas las misiones (activas e inactivas)."""
    snap = _ref("misiones").get()
    if not snap:
        return MISIONES_BASE  # Fallback al catálogo local
    return [{"id": k, **v} for k, v in snap.items() if v]


def get_active_missions(categoria: Optional[str] = None) -> List[Dict]:
    """Retorna misiones activas, opcionalmente filtradas por categoría."""
    missions = get_all_missions()
    active = [m for m in missions if m.get("activa", True)]
    if categoria and categoria != "general":
        cat_missions = [m for m in active if m.get("categoria") == categoria]
        # Si hay misiones de la categoría específica, se mezclan con generales
        general = [m for m in active if m.get("categoria") in ("salud", "mindfulness", "reflexion", "actividad")]
        return (cat_missions + general)[:10]
    return active


def get_missions_with_schedule() -> List[Dict]:
    """Retorna misiones que tienen horario_programado definido."""
    missions = get_all_missions()
    return [m for m in missions if m.get("horario_programado") and m.get("activa", True)]


def get_mission(mision_id: str) -> Optional[Dict]:
    """Obtiene una misión específica por ID."""
    snap = _ref(f"misiones/{mision_id}").get()
    if snap:
        return {"id": mision_id, **snap}
    # Fallback al catálogo local
    return next((m for m in MISIONES_BASE if m["id"] == mision_id), None)


# ─── ESCRITURA / CRUD ────────────────────────────────────────────────────────

def create_mission(data: Dict) -> Dict:
    """
    Crea una nueva misión en Firebase.

    Args:
        data: Dict con nombre, descripcion, categoria, puntos_recompensa,
              activa (bool), horario_programado (opcional: {hora, minuto}).
    Returns:
        La misión creada con su ID.
    """
    mision_id = data.get("id") or str(uuid.uuid4())[:12]
    mission_data = {
        "nombre":           data.get("nombre", "Sin nombre"),
        "descripcion":      data.get("descripcion", ""),
        "categoria":        data.get("categoria", "general"),
        "puntos_recompensa": int(data.get("puntos_recompensa", 10)),
        "activa":           bool(data.get("activa", True)),
        "creado_el":        _now_iso(),
    }
    if data.get("horario_programado"):
        hp = data["horario_programado"]
        mission_data["horario_programado"] = {
            "hora":   int(hp.get("hora", 0)),
            "minuto": int(hp.get("minuto", 0)),
        }
    _ref(f"misiones/{mision_id}").set(mission_data)
    logger.info(f"✅ Misión creada: {mision_id} — {mission_data['nombre']}")
    return {"id": mision_id, **mission_data}


def update_mission(mision_id: str, data: Dict) -> bool:
    """
    Actualiza una misión existente.
    Retorna True si la misión existía, False si no.
    """
    snap = _ref(f"misiones/{mision_id}").get()
    if not snap:
        return False

    allowed = {"nombre", "descripcion", "categoria", "puntos_recompensa", "activa", "horario_programado"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return True

    updates["actualizado_el"] = _now_iso()
    _ref(f"misiones/{mision_id}").update(updates)
    logger.info(f"✏️ Misión actualizada: {mision_id}")
    return True


def delete_mission(mision_id: str) -> bool:
    """
    Elimina una misión. Las misiones base se marcan como inactivas en vez de borrar.
    """
    base_ids = {m["id"] for m in MISIONES_BASE}
    if mision_id in base_ids:
        # Misión base → solo desactivar
        _ref(f"misiones/{mision_id}").update({"activa": False, "actualizado_el": _now_iso()})
        logger.info(f"⚠️ Misión base desactivada (no eliminada): {mision_id}")
        return True
    snap = _ref(f"misiones/{mision_id}").get()
    if not snap:
        return False
    _ref(f"misiones/{mision_id}").delete()
    logger.info(f"🗑️ Misión eliminada: {mision_id}")
    return True


# ─── Selección para usuarios ─────────────────────────────────────────────────

def get_daily_missions(vicio: str = "general", count: int = 3) -> List[Dict]:
    """
    Retorna una selección de misiones del día para un usuario,
    mezclando misiones del vicio con misiones generales.
    Excluye misiones de medicamento (tienen su propio flujo de recordatorio).
    """
    import random
    all_active = get_active_missions(vicio)
    # Excluir medicamentos del flujo de misiones diarias normales
    candidates = [m for m in all_active if m.get("categoria") != "medicamento"]
    if not candidates:
        candidates = MISIONES_BASE[:5]
    # Mapear a formato esperado por el handler
    result = []
    for m in random.sample(candidates, min(count, len(candidates))):
        result.append({
            "id":     m.get("id", ""),
            "titulo": m.get("nombre", "Misión"),
            "desc":   m.get("descripcion", ""),
            "xp":     m.get("puntos_recompensa", 10),
        })
    return result
