"""
keyboards.py — Teclados y botones inline para el bot de Telegram.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ─── Vicios ──────────────────────────────────────────────────────────────────

VICIOS = [
    ("🚬 Cigarros",               "vicio_Cigarros"),
    ("🍺 Alcohol",                "vicio_Alcohol"),
    ("🌿 Marihuana",              "vicio_Marihuana"),
    ("💊 Cocaína / Crack",        "vicio_Cocaina"),
    ("🎰 Apuestas",               "vicio_Apuestas"),
    ("☕ Cafeína",                "vicio_Cafeina"),
    ("💊 Benzodiacepinas",        "vicio_Benzodiacepinas"),
    ("📱 Adicción Digital",       "vicio_AddiccionDigital"),
    ("🍽️ Trastornos Alimenticios","vicio_TrastornosAlimenticios"),
    ("✏️ Otro hábito",            "vicio_Otro"),
]

DURACIONES = [
    ("5 meses",  "dur_5"),
    ("6 meses",  "dur_6"),
    ("7 meses",  "dur_7"),
    ("8 meses",  "dur_8"),
    ("9 meses",  "dur_9"),
    ("10 meses", "dur_10"),
    ("11 meses", "dur_11"),
    ("12 meses", "dur_12"),
]


def kb_select_vicio() -> InlineKeyboardMarkup:
    """Menú de selección de vicio/hábito."""
    buttons = []
    for i in range(0, len(VICIOS), 2):
        row = [InlineKeyboardButton(VICIOS[i][0], callback_data=VICIOS[i][1])]
        if i + 1 < len(VICIOS):
            row.append(InlineKeyboardButton(VICIOS[i+1][0], callback_data=VICIOS[i+1][1]))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def kb_select_duracion() -> InlineKeyboardMarkup:
    """Menú de selección de duración del plan."""
    buttons = []
    for i in range(0, len(DURACIONES), 4):
        row = [
            InlineKeyboardButton(d[0], callback_data=d[1])
            for d in DURACIONES[i:i+4]
        ]
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def kb_select_num_helpers() -> InlineKeyboardMarkup:
    """Selección del número de ayudantes."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("0 ayudantes", callback_data="helpers_0"),
            InlineKeyboardButton("1 ayudante",  callback_data="helpers_1"),
            InlineKeyboardButton("2 ayudantes", callback_data="helpers_2"),
        ]
    ])


def kb_main_menu() -> InlineKeyboardMarkup:
    """Menú principal durante el plan activo."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Mis misiones",    callback_data="action_misiones"),
            InlineKeyboardButton("📊 Mi progreso",     callback_data="action_progreso"),
        ],
        [
            InlineKeyboardButton("🆘 Pedir ayuda",     callback_data="action_ayuda"),
            InlineKeyboardButton("🌬️ Respirar",        callback_data="action_respirar"),
        ],
        [
            InlineKeyboardButton("⚠️ Reportar recaída", callback_data="action_recaida"),
            InlineKeyboardButton("⏸️ Pausar plan",      callback_data="action_pausar"),
        ],
        [
            InlineKeyboardButton("📞 Llamar ayudante",  callback_data="action_llamar"),
        ],
    ])


def kb_mission_done(mision_id: str) -> InlineKeyboardMarkup:
    """Botón para marcar una misión como completada."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Completé esta misión", callback_data=f"mision_done_{mision_id}")]
    ])


def kb_relapse_confirm() -> InlineKeyboardMarkup:
    """Confirmación de recaída con botón para iniciar recuperación."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💪 Iniciar recuperación", callback_data="recovery_start"),
            InlineKeyboardButton("🗣️ Hablar con alguien",   callback_data="action_llamar"),
        ],
        [
            InlineKeyboardButton("🔙 Cancelar",             callback_data="cancel_relapse"),
        ],
    ])


def kb_helper_actions(principal_nombre: str, principal_id: str) -> InlineKeyboardMarkup:
    """Botones de acción para los ayudantes."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📞 Llamar/Mensajear",    callback_data=f"hlp_contact_{principal_id}"),
            InlineKeyboardButton("💪 Enviar apoyo",        callback_data=f"hlp_apoyo_{principal_id}"),
        ],
        [
            InlineKeyboardButton("✅ Confirmar chequeo",   callback_data=f"hlp_check_{principal_id}"),
        ],
    ])


def kb_confirm_cancel(callback_confirm: str, callback_cancel: str = "cancel") -> InlineKeyboardMarkup:
    """Teclado genérico de confirmación / cancelación."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=callback_confirm),
            InlineKeyboardButton("❌ Cancelar",  callback_data=callback_cancel),
        ]
    ])
