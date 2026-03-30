"""
app/api/main.py — API Flask: Panel Administrativo + Webhook de Telegram.
Incluye endpoints para misiones (CRUD), broadcast, marketing y stats completos.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, abort

from app.config import (
    FLASK_SECRET_KEY,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    DEBUG,
    CRON_KEY,
)
from app.services import firebase_db as fdb
from app.services.xp_system import get_nivel_actual
from app.services import missions as missions_svc

logger = logging.getLogger(__name__)

flask_app = Flask(
    __name__,
    template_folder="../../templates",
    static_folder="../../assets",
    static_url_path="/assets",
)
flask_app.secret_key = FLASK_SECRET_KEY


# ─── Utilidades ──────────────────────────────────────────────────────────────

def _verify_webhook_secret(token: str) -> bool:
    return hmac.compare_digest(token or "", WEBHOOK_SECRET)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _calc_progreso_pct(user: dict) -> int:
    """Calcula el porcentaje de progreso del plan (0–100)."""
    fecha_inicio = user.get("fecha_inicio")
    duracion_meses = user.get("duracion_meses", 5)
    if not fecha_inicio or not duracion_meses:
        return 0
    try:
        inicio = datetime.fromisoformat(fecha_inicio)
        ahora = datetime.now(timezone.utc)
        dias_plan = duracion_meses * 30
        dias_transcurridos = (ahora - inicio).days
        return min(int((dias_transcurridos / dias_plan) * 100), 100)
    except:
        return 0


# ─── Webhook de Telegram ─────────────────────────────────────────────────────

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not _verify_webhook_secret(secret):
        logger.warning("Webhook: token secreto inválido.")
        abort(403)

    data = request.get_json(force=True)
    if not data:
        return jsonify({"ok": True})

    from app.bot.main import process_update_sync
    process_update_sync(data)
    return jsonify({"ok": True})


# ─── Panel Admin ─────────────────────────────────────────────────────────────

@flask_app.route("/")
def index():
    return render_template("index.html")


@flask_app.route("/ping")
def ping():
    return jsonify({"ok": True, "status": "awake"})


@flask_app.route("/admin")
@flask_app.route("/admin/")
def admin_panel():
    return render_template("admin/panel.html")


# ─── API: Stats ───────────────────────────────────────────────────────────────

@flask_app.route("/api/stats")
def api_stats():
    users = fdb.get_all_users()
    total = len(users)
    activos = sum(1 for u in users if u.get("estado_plan") == "activo")
    completados = sum(1 for u in users if u.get("estado_plan") == "completado")
    pausados = sum(1 for u in users if u.get("estado_plan") == "pausado")
    abandonados = sum(1 for u in users if u.get("estado_plan") == "abandonado")
    racha_max = max((u.get("racha_dias", 0) for u in users), default=0)
    xp_promedio = int(sum(u.get("xp", 0) for u in users) / total) if total else 0
    return jsonify({
        "ok": True,
        "data": {
            "total_usuarios": total,
            "activos": activos,
            "completados": completados,
            "pausados": pausados,
            "abandonados": abandonados,
            "racha_maxima": racha_max,
            "xp_promedio": xp_promedio,
        }
    })


# ─── API: Usuarios ────────────────────────────────────────────────────────────

@flask_app.route("/api/users")
def api_list_users():
    users = fdb.get_all_users()
    for u in users:
        u["nivel_info"] = get_nivel_actual(u.get("xp", 0))
        u["progreso_pct"] = _calc_progreso_pct(u)
        # Calcular fecha fin estimada
        fecha_inicio = u.get("fecha_inicio")
        duracion = u.get("duracion_meses", 0)
        if fecha_inicio and duracion:
            try:
                inicio = datetime.fromisoformat(fecha_inicio)
                from datetime import timedelta
                fin = inicio + timedelta(days=duracion * 30)
                u["fecha_fin_estimada"] = fin.isoformat()
            except:
                u["fecha_fin_estimada"] = None
        else:
            u["fecha_fin_estimada"] = None
    return jsonify({"ok": True, "data": users})


@flask_app.route("/api/users/<telegram_id>")
def api_get_user(telegram_id: str):
    user = fdb.get_user(telegram_id)
    if not user:
        return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
    user["nivel_info"] = get_nivel_actual(user.get("xp", 0))
    user["progreso_pct"] = _calc_progreso_pct(user)
    user["ayudantes_list"] = fdb.get_helpers_for_user(telegram_id)
    user["recaidas"] = fdb.get_user_relapses(telegram_id)
    user["misiones_log"] = fdb.get_user_mission_logs(telegram_id)
    return jsonify({"ok": True, "data": user})


@flask_app.route("/api/users/<telegram_id>", methods=["PATCH"])
def api_update_user(telegram_id: str):
    payload = request.get_json()
    if not payload:
        return jsonify({"ok": False, "error": "Payload vacío"}), 400
    allowed = {"nombre", "vicio", "duracion_meses", "estado_plan", "racha_dias", "xp", "nivel"}
    cambios = {k: v for k, v in payload.items() if k in allowed}
    if not cambios:
        return jsonify({"ok": False, "error": "No hay campos válidos"}), 400
    fdb.save_user(telegram_id, cambios)
    fdb.log_event(telegram_id, "admin_edicion", f"Admin editó: {list(cambios.keys())}")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/pause", methods=["POST"])
def api_pause_user(telegram_id: str):
    fdb.save_user(telegram_id, {"estado_plan": "pausado"})
    fdb.log_event(telegram_id, "admin_pausa", "Admin pausó el plan.")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/resume", methods=["POST"])
def api_resume_user(telegram_id: str):
    fdb.save_user(telegram_id, {"estado_plan": "activo"})
    fdb.log_event(telegram_id, "admin_reanudo", "Admin reactivó el plan.")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/finish", methods=["POST"])
def api_finish_user(telegram_id: str):
    fdb.save_user(telegram_id, {"estado_plan": "completado"})
    fdb.log_event(telegram_id, "admin_completo", "Admin marcó el plan como completado.")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/notify", methods=["POST"])
def api_notify_user(telegram_id: str):
    payload = request.get_json()
    mensaje = (payload or {}).get("mensaje", "").strip()
    if not mensaje:
        return jsonify({"ok": False, "error": "Mensaje vacío"}), 400
    fdb.enqueue_notification(telegram_id, mensaje, {"tipo": "admin_manual"})
    fdb.log_event(telegram_id, "admin_notificacion", f"Admin envió mensaje: {mensaje[:80]}")
    return jsonify({"ok": True})


# ─── API: Eventos ─────────────────────────────────────────────────────────────

@flask_app.route("/api/events")
def api_events():
    limit = int(request.args.get("limit", 50))
    events = fdb.get_recent_events(limit)
    return jsonify({"ok": True, "data": events})


# ─── API: Misiones (CRUD) ────────────────────────────────────────────────────

@flask_app.route("/api/missions", methods=["GET"])
def api_list_missions():
    """Lista todas las misiones."""
    try:
        missions_svc.seed_default_missions()
    except Exception:
        pass
    missions = missions_svc.get_all_missions()
    return jsonify({"ok": True, "data": missions})


@flask_app.route("/api/missions", methods=["POST"])
def api_create_mission():
    """Crea una nueva misión."""
    payload = request.get_json()
    if not payload or not payload.get("nombre"):
        return jsonify({"ok": False, "error": "Nombre requerido"}), 400
    mission = missions_svc.create_mission(payload)
    return jsonify({"ok": True, "data": mission}), 201


@flask_app.route("/api/missions/<mission_id>", methods=["PATCH"])
def api_update_mission(mission_id: str):
    """Actualiza una misión existente."""
    payload = request.get_json()
    if not payload:
        return jsonify({"ok": False, "error": "Payload vacío"}), 400
    updated = missions_svc.update_mission(mission_id, payload)
    if not updated:
        return jsonify({"ok": False, "error": "Misión no encontrada"}), 404
    return jsonify({"ok": True})


@flask_app.route("/api/missions/<mission_id>", methods=["DELETE"])
def api_delete_mission(mission_id: str):
    """Elimina o desactiva una misión."""
    deleted = missions_svc.delete_mission(mission_id)
    if not deleted:
        return jsonify({"ok": False, "error": "Misión no encontrada"}), 404
    return jsonify({"ok": True})


# ─── API: Broadcast / Mensajes masivos ───────────────────────────────────────

@flask_app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    """
    Envía un mensaje a todos los usuarios activos.
    Body: { "mensaje": "...", "tipo": "broadcast" | "marketing" }
    """
    payload = request.get_json()
    mensaje = (payload or {}).get("mensaje", "").strip()
    tipo = (payload or {}).get("tipo", "broadcast")
    if not mensaje:
        return jsonify({"ok": False, "error": "Mensaje vacío"}), 400

    users = fdb.get_all_users()
    activos = [u for u in users if u.get("estado_plan") in ("activo", "recuperacion")]

    if not activos:
        return jsonify({"ok": True, "enviados": 0, "mensaje": "Sin usuarios activos"})

    broadcast_id = str(uuid.uuid4())
    # Encolar para cada usuario activo
    for u in activos:
        tid = u.get("telegram_id")
        if tid:
            fdb.enqueue_notification(tid, mensaje, {"tipo": tipo, "broadcast_id": broadcast_id})

    # Registrar el broadcast
    from firebase_admin import db
    db.reference(f"mensajes_masivos/{broadcast_id}").set({
        "contenido": mensaje,
        "tipo": tipo,
        "fecha": _now_iso(),
        "total_destinatarios": len(activos),
    })

    return jsonify({"ok": True, "enviados": len(activos), "broadcast_id": broadcast_id})


@flask_app.route("/api/broadcasts", methods=["GET"])
def api_list_broadcasts():
    """Lista el historial de mensajes masivos."""
    from firebase_admin import db
    snap = db.reference("mensajes_masivos").order_by_child("fecha").limit_to_last(50).get()
    if not snap:
        return jsonify({"ok": True, "data": []})
    data = [{"id": k, **v} for k, v in snap.items() if v]
    data.sort(key=lambda x: x.get("fecha", ""), reverse=True)
    return jsonify({"ok": True, "data": data})


# ─── Endpoints de Cron / Keep-Alive ─────────────────────────────────────────
# Úsalos en UptimeRobot, cron-job.org o cualquier scheduler externo:
#   https://bot-apoyo-erradicacion-vicios.onrender.com/api/cron/keep-alive?key=TU_CRON_KEY

def _check_cron_key() -> bool:
    """Valida la clave de cron desde query param o header X-Cron-Key."""
    key = request.args.get("key") or request.headers.get("X-Cron-Key", "")
    return hmac.compare_digest(key, CRON_KEY)


@flask_app.route("/api/cron/keep-alive")
def cron_keep_alive():
    """
    Endpoint principal de keep-alive para Render Free Tier.
    Llamar periódicamente desde un cron externo para evitar el sleep.
    URL: /api/cron/keep-alive?key=<CRON_KEY>
    """
    if not _check_cron_key():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    return jsonify({
        "ok":      True,
        "status":  "alive",
        "ts":      _now_iso(),
        "service": "bot-apoyo-erradicacion-vicios",
    })


@flask_app.route("/api/cron/ping")
def cron_ping():
    """
    Endpoint ligero de ping (sin clave). Útil para health checks simples.
    URL: /api/cron/ping
    """
    return jsonify({"ok": True, "pong": True, "ts": _now_iso()})


@flask_app.route("/api/cron/stats")
def cron_stats():
    """
    Devuelve estadísticas básicas del sistema en formato JSON liviano.
    Útil para monitoreo externo con cron.
    URL: /api/cron/stats?key=<CRON_KEY>
    """
    if not _check_cron_key():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    try:
        users = fdb.get_all_users()
        activos    = sum(1 for u in users if u.get("estado_plan") == "activo")
        completados= sum(1 for u in users if u.get("estado_plan") == "completado")
        racha_max  = max((u.get("racha_dias", 0) for u in users), default=0)
        return jsonify({
            "ok":           True,
            "ts":           _now_iso(),
            "total":        len(users),
            "activos":      activos,
            "completados":  completados,
            "racha_max":    racha_max,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@flask_app.route("/api/cron/notify-inactive")
def cron_notify_inactive():
    """
    Dispara manualmente el job de inactividad.
    URL: /api/cron/notify-inactive?key=<CRON_KEY>
    """
    if not _check_cron_key():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    try:
        from app.worker.scheduler import job_check_inactive_users
        job_check_inactive_users()
        return jsonify({"ok": True, "msg": "Job de inactividad ejecutado."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── Ruta de fallback para SPA ────────────────────────────────────────────────

@flask_app.errorhandler(404)
def not_found(e):
    return jsonify({"ok": False, "error": "Ruta no encontrada"}), 404
