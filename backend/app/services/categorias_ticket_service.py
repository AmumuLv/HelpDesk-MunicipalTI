"""Clasificacion del portal usando exclusivamente el catalogo vigente."""

import re

from app.core.ids import clave
from app.services import catalogo_service
from app.services.presentacion_ticket import CATEGORIA_POR_TIPO


async def categorias_activas() -> list[str]:
    return [v['valor'] for v in await catalogo_service.listar_detallado('categorias') if v['activo']]


def categoria_del_catalogo(candidata: str | None, categorias: list[str]) -> str | None:
    return next((c for c in categorias if candidata and clave(c) == clave(candidata)), None)


def categoria_reporte(tipo: str | None, descripcion: str, categorias: list[str]) -> str | None:
    candidata = CATEGORIA_POR_TIPO.get(tipo)
    if tipo == 'Sistema/programa' and re.search(r'formate', descripcion, re.I):
        candidata = 'Formateo'
    elif tipo == 'Otro':
        candidata = 'Correo / Cuenta' if re.search(r'\b(correo|outlook|email|cuenta)\b', descripcion, re.I) else 'Otros'
    return categoria_del_catalogo(candidata, categorias)
