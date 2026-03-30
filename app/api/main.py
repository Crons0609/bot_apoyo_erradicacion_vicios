"""
app/api/main.py — API Flask: Panel Administrativo + Webhook de Telegram.
"""
import asyncio
import hashlib
import hmac
import json
import logging

from flask import Flask, render_template, request, jsonify, redirect, url_for, abort

from app.config import (
    FLASK_SECRET_KEY,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    DEBUG,
)
from app.services import firebase_db as fdb
from app.services.xp_system import get_nivel_actual

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
    """Verifica el header X-Telegram-Bot-Api-Secret-Token."""
    return hmac.compare_digest(token or "", WEBHOOK_SECRET)


# ─── Webhook de Telegram ─────────────────────────────────────────────────────

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    """Recibe updates de Telegram y los despacha al bot."""
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
    """Login / landing page del panel admin."""
    return render_template("index.html")


@flask_app.route("/ping")
def ping():
    """Endpoint ligero para que el cronjob interno lo alcance y no deje dormir la app."""
    return jsonify({"ok": True, "status": "awake"})


@flask_app.route("/admin")
@flask_app.route("/admin/")
def admin_panel():
    """Dashboard principal del panel admin."""
    return render_template("admin/panel.html")


# ─── API REST para el Panel Admin (lectura protegida por Firebase Auth en el cliente) ───

@flask_app.route("/api/users")
def api_list_users():
    """Lista todos los usuarios para el panel."""
    users = fdb.get_all_users()
    # Enriquecer con nivel
    for u in users:
        u["nivel_info"] = get_nivel_actual(u.get("xp", 0))
    return jsonify({"ok": True, "data": users})


@flask_app.route("/api/users/<telegram_id>")
def api_get_user(telegram_id: str):
    """Detalle de un usuario."""
    user = fdb.get_user(telegram_id)
    if not user:
        return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
    user["nivel_info"] = get_nivel_actual(user.get("xp", 0))
    user["ayudantes_list"] = fdb.get_helpers_for_user(telegram_id)
    user["recaidas"] = fdb.get_user_relapses(telegram_id)
    user["misiones_log"] = fdb.get_user_mission_logs(telegram_id)
    return jsonify({"ok": True, "data": user})


@flask_app.route("/api/users/<telegram_id>", methods=["PATCH"])
def api_update_user(telegram_id: str):
    """Actualiza datos del usuario desde el panel admin."""
    payload = request.get_json()
    if not payload:
        return jsonify({"ok": False, "error": "Payload vacío"}), 400
    # Campos permitidos para edición manual
    allowed = {"nombre", "vicio", "duracion_meses", "estado_plan", "racha_dias", "xp", "nivel"}
    cambios = {k: v for k, v in payload.items() if k in allowed}
    if not cambios:
        return jsonify({"ok": False, "error": "No hay campos válidos para actualizar"}), 400
    fdb.save_user(telegram_id, cambios)
    fdb.log_event(telegram_id, "admin_edicion", f"Admin editó: {list(cambios.keys())}")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/pause", methods=["POST"])
def api_pause_user(telegram_id: str):
    fdb.save_user(telegram_id, {"estado_plan": "pausado"})
    fdb.log_event(telegram_id, "admin_pausa", "Admin pausó el plan del usuario.")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/resume", methods=["POST"])
def api_resume_user(telegram_id: str):
    fdb.save_user(telegram_id, {"estado_plan": "activo"})
    fdb.log_event(telegram_id, "admin_reanudo", "Admin reactivó el plan del usuario.")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/finish", methods=["POST"])
def api_finish_user(telegram_id: str):
    fdb.save_user(telegram_id, {"estado_plan": "completado"})
    fdb.log_event(telegram_id, "admin_completo", "Admin marcó el plan como completado.")
    return jsonify({"ok": True})


@flask_app.route("/api/users/<telegram_id>/notify", methods=["POST"])
def api_notify_user(telegram_id: str):
    """Envía un mensaje personalizado desde el panel al usuario vía Telegram."""
    payload = request.get_json()
    mensaje = (payload or {}).get("mensaje", "").strip()
    if not mensaje:
        return jsonify({"ok": False, "error": "Mensaje vacío"}), 400
    fdb.enqueue_notification(telegram_id, mensaje, {"tipo": "admin_manual"})
    fdb.log_event(telegram_id, "admin_notificacion", f"Admin envió mensaje: {mensaje[:80]}")
    return jsonify({"ok": True})


@flask_app.route("/api/events")
def api_events():
    """Últimos eventos del sistema para el panel admin."""
    limit = int(request.args.get("limit", 50))
    events = fdb.get_recent_events(limit)
    return jsonify({"ok": True, "data": events})


@flask_app.route("/api/stats")
def api_stats():
    """KPIs globales para el dashboard."""
    users = fdb.get_all_users()
    total = len(users)
    activos = sum(1 for u in users if u.get("estado_plan") == "activo")
    completados = sum(1 for u in users if u.get("estado_plan") == "completado")
    pausados = sum(1 for u in users if u.get("estado_plan") == "pausado")
    racha_max = max((u.get("racha_dias", 0) for u in users), default=0)
    return jsonify({
        "ok": True,
        "data": {
            "total_usuarios": total,
            "activos": activos,
            "completados": completados,
            "pausados": pausados,
            "racha_maxima": racha_max,
        }
    })
