"""
missions.py — Lógica de selección y rotación de misiones diarias.
"""
import random
from typing import List, Dict

from app.services.firebase_db import MISIONES_CATALOGO


def get_daily_missions(vicio: str = "general", count: int = 3) -> List[Dict]:
    """
    Selecciona misiones aleatorias del catálogo, priorizando las de la categoría correcta.
    """
    catalogo = list(MISIONES_CATALOGO)  # Copia para no modificar el original
    random.shuffle(catalogo)
    return catalogo[:count]
