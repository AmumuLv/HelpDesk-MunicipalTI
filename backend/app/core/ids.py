"""Identificadores, normalizacion de texto y codigos de negocio."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.core.errors import Validacion

ESPACIOS = re.compile(r"\s+")
NO_ALFA = re.compile(r"[^A-Z0-9 ]")


def nuevo_id() -> ObjectId:
    return ObjectId()


def a_id(valor: Any) -> ObjectId | None:
    """Convierte a ObjectId devolviendo None si no es valido."""
    if valor is None:
        return None
    if isinstance(valor, ObjectId):
        return valor
    try:
        return ObjectId(str(valor))
    except (InvalidId, TypeError):
        return None


def id_requerido(valor: Any, campo: str = "id") -> ObjectId:
    resultado = a_id(valor)
    if resultado is None:
        raise Validacion(f"El identificador de {campo} no es valido.", detalles={"campo": campo})
    return resultado


def normalizar_texto(valor: Any) -> str:
    """Recorta espacios (incluidos los no separables) sin alterar acentos."""
    if valor is None:
        return ""
    texto = str(valor).replace("\u00a0", " ")
    return ESPACIOS.sub(" ", texto).strip()


def clave(valor: Any) -> str:
    """Clave de comparacion: sin acentos, sin mayusculas, sin puntuacion extra."""
    texto = normalizar_texto(valor)
    if not texto:
        return ""
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return ESPACIOS.sub(" ", NO_ALFA.sub(" ", sin_acentos.upper())).strip()


def clave_oscura(texto: str) -> str:
    """Version para busqueda difusa de usuarios: sin acentos, solo alfanumericos."""
    base = clave(texto)
    return base.replace(" ", "")


def igual_texto(a: Any, b: Any) -> bool:
    return clave(a) == clave(b)


def slug(texto: str, maximo: int = 80) -> str:
    base = clave(texto).lower().replace(" ", "-")
    base = re.sub(r"-{2,}", "-", base).strip("-")
    return base[:maximo] or "sin-nombre"


def codigo_activo(prefijo: str, numero: int) -> str:
    return f"{prefijo}-{numero:05d}"


def codigo_ticket(anio: int, numero: int) -> str:
    return f"TKT-{anio}-{numero:06d}"


def codigo_campana(anio: int, numero: int) -> str:
    return f"INV-{anio}-{numero:03d}"


def siguiente_numero_conjunto(oficina_id: ObjectId, existentes: list[str]) -> int:
    """Calcula el siguiente numero libre de conjunto para una oficina.

    Acepta nombres ya guardados en la forma 'Computadora N°3'.
    """
    patron = re.compile(r"(\d+)")
    maximo = 0
    for nombre in existentes:
        if not nombre:
            continue
        coincidencia = patron.search(str(nombre))
        if coincidencia:
            maximo = max(maximo, int(coincidencia.group(1)))
    return maximo + 1


def limpiar_codigo_patrimonial(valor: Any) -> str | None:
    """Codigo patrimonial normalizado; '' o '-' significan 'sin codigo'."""
    texto = normalizar_texto(valor)
    if not texto:
        return None
    if texto.lower() in {"-", "--", "n/a", "na", "s/n", "s/c", "sin codigo", "sin código", "no tiene", "no aplica", "no disponible", "ninguno", "."}:
        return None
    return texto


def mcp_ip(valor: Any) -> str | None:
    texto = normalizar_texto(valor)
    if not texto:
        return None
    partes = texto.split(".")
    if len(partes) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in partes):
        return texto
    return None


def mcp_mac(valor: Any) -> str | None:
    texto = normalizar_texto(valor).upper().replace("-", ":")
    if not texto:
        return None
    if re.fullmatch(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", texto):
        return texto
    if re.fullmatch(r"[0-9A-F]{12}", texto):
        return ":".join(texto[i : i + 2] for i in range(0, 12, 2))
    if re.fullmatch(r"[0-9A-F]{4}(\.[0-9A-F]{4}){2}", texto):
        plano = texto.replace(".", "")
        return ":".join(plano[i : i + 2] for i in range(0, 12, 2))
    if re.fullmatch(r"[0-9A-F]{2}(\.[0-9A-F]{2}){5}", texto):
        return texto.replace('.', ':')
    return None


def ip_en_red(ip: str, prefijo: int = 24) -> str | None:
    try:
        octetos = [int(p) for p in ip.split(".")]
    except (ValueError, AttributeError):
        return None
    if len(octetos) != 4:
        return None
    mascara = (0xFFFFFFFF << (32 - prefijo)) & 0xFFFFFFFF
    valor = sum(o << (24 - 8 * i) for i, o in enumerate(octetos))
    red = valor & mascara
    return ".".join(str((red >> (24 - 8 * i)) & 255) for i in range(4))


def rango_fechas(periodo: str | None, referencia: date) -> tuple[date, date]:
    """Traduce el selector de periodo de la UI a un rango de dias locales."""
    from app.core.time import month_bounds

    hoy = referencia
    if periodo in (None, "", "30d"):
        return hoy - _dias(29), hoy
    if periodo == "7d":
        return hoy - _dias(6), hoy
    if periodo == "90d":
        return hoy - _dias(89), hoy
    if periodo == "365d":
        return hoy - _dias(364), hoy
    if periodo == "mes":
        return month_bounds(hoy)
    if periodo == "mes_anterior":
        _, fin_prev = month_bounds(hoy)
        return month_bounds(_dias_mes(fin_prev))
    if periodo == "anio":
        return hoy.replace(month=1, day=1), hoy
    return hoy - _dias(29), hoy


def _dias(n: int):
    """Intervalo de ``n`` dias hacia atras (se resta de la fecha de referencia)."""
    from datetime import timedelta

    return timedelta(days=n)


def _dias_mes(dia: date) -> date:
    from datetime import timedelta

    return dia - timedelta(days=1)
