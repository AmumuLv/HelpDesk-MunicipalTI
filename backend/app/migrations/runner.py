"""Migraciones versionadas y propias.

Cada migracion es un modulo ``mXXX_descripcion.py`` que expone ``async def aplicar(db)``
y, opcionalmente, ``async def revertir(db)``. El ejecutor guarda lo aplicado en la
coleccion ``_migraciones`` y nunca corre dos veces la misma version.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any

from app.core.db import get_db
from app.core.time import utcnow
from app.migrations import __path__ as _paquete

logger = logging.getLogger(__name__)


async def _aplicadas() -> set[str]:
    docs = await (get_db()["_migraciones"].find({}, {"version": 1}).to_list(None))
    return {d["version"] for d in docs}


def _descubrir() -> list[tuple[int, str, Any]]:
    modulos: list[tuple[int, str, Any]] = []
    for info in pkgutil.iter_modules(_paquete):
        if not info.name.startswith("m") or "_" not in info.name:
            continue
        prefijo = info.name.split("_", 1)[0]
        if not prefijo[1:].isdigit():
            continue
        modulo = importlib.import_module(f"app.migrations.{info.name}")
        if hasattr(modulo, "aplicar"):
            modulos.append((int(prefijo[1:]), info.name, modulo))
    return sorted(modulos, key=lambda x: x[0])


async def ejecutar(hasta: str | None = None) -> list[str]:
    """Aplica las migraciones pendientes en orden. ``hasta`` limita la version."""
    db = get_db()
    ya = await _aplicadas()
    aplicadas: list[str] = []
    for numero, nombre, modulo in _descubrir():
        version = f"{numero:03d}_{nombre.split('_', 1)[1]}"
        if version in ya:
            continue
        if hasta and version > hasta:
            break
        logger.info("Migracion %s: aplicando %s", version, getattr(modulo, "DESCRIPCION", ""))
        inicio = utcnow()
        await modulo.aplicar(db)
        await db["_migraciones"].insert_one(
            {
                "version": version,
                "numero": numero,
                "descripcion": getattr(modulo, "DESCRIPCION", ""),
                "aplicada_en": inicio,
                "duracion_ms": int((utcnow() - inicio).total_seconds() * 1000),
            }
        )
        aplicadas.append(version)
    return aplicadas


async def estado() -> list[dict[str, Any]]:
    ya = {d["version"]: d for d in await (get_db()["_migraciones"].find({}).to_list(None))}
    filas: list[dict[str, Any]] = []
    for numero, nombre, modulo in _descubrir():
        version = f"{numero:03d}_{nombre.split('_', 1)[1]}"
        filas.append(
            {
                "version": version,
                "descripcion": getattr(modulo, "DESCRIPCION", ""),
                "aplicada": version in ya,
                "aplicada_en": ya.get(version, {}).get("aplicada_en"),
            }
        )
    return filas


async def revertir(version: str) -> bool:
    """Revierte una migracion aplicada usando su funcion ``revertir``."""
    for numero, nombre, modulo in _descubrir():
        v = f"{numero:03d}_{nombre.split('_', 1)[1]}"
        if v == version and hasattr(modulo, "revertir"):
            await modulo.revertir(get_db())
            await get_db()["_migraciones"].delete_one({"version": v})
            return True
    return False
