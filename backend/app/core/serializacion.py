"""Normalizacion de documentos de MongoDB para las respuestas de la API.

Las colecciones guardan ``_id``; la API expone siempre ``id``. Esta funcion
recorre la estructura y renombra la clave para que el frontend tenga un unico
nombre de identificador en toda la aplicacion.
"""

from __future__ import annotations

from typing import Any

from bson import ObjectId


def normalizar(valor: Any) -> Any:
    """Renombra ``_id`` a ``id`` de forma recursiva, sin tocar el resto."""
    if isinstance(valor, dict):
        salida: dict[str, Any] = {}
        for clave, item in valor.items():
            nueva_clave = "id" if clave == "_id" else clave
            salida[nueva_clave] = normalizar(item)
        return salida
    if isinstance(valor, list):
        return [normalizar(item) for item in valor]
    return valor


def id_de(documento: dict[str, Any]) -> Any:
    return documento.get("id") or documento.get("_id")