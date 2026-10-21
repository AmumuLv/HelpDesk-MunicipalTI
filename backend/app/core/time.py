"""Utilidades de tiempo: todo se almacena en UTC, se muestra en la zona de negocio."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings


def utcnow() -> datetime:
    """Instante actual con zona horaria UTC explicita."""
    return datetime.now(ZoneInfo("UTC"))


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo("UTC"))


def business_tz() -> ZoneInfo:
    return settings.tz


def now_business() -> datetime:
    return utcnow().astimezone(business_tz())


def local_date(value: datetime | None = None) -> date:
    return (value or utcnow()).astimezone(business_tz()).date()


def business_start_of_day(day: date) -> datetime:
    """Inicio del dia local convertido a UTC (instante real de comienzo)."""
    return datetime.combine(day, time(0, 0), tzinfo=business_tz()).astimezone(ZoneInfo("UTC"))


def business_end_of_day(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=business_tz()).astimezone(
        ZoneInfo("UTC")
    )


def business_day_bounds(day: date) -> tuple[datetime, datetime]:
    return business_start_of_day(day), business_end_of_day(day)


def humanize_delta(delta: timedelta, *, max_units: int = 2) -> str:
    """Texto corto y comprensible para una duracion ('2 dias 3 horas')."""
    if delta.total_seconds() <= 0:
        return "vencido"
    segundos = int(delta.total_seconds())
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)
    partes: list[str] = []
    if dias:
        partes.append(f"{dias} dia{'s' if dias != 1 else ''}")
    if horas and len(partes) < max_units:
        partes.append(f"{horas} h")
    if not partes and minutos:
        partes.append(f"{minutos} min")
    return " ".join(partes) if partes else "menos de 1 min"


def month_bounds(anchor: date) -> tuple[date, date]:
    inicio = anchor.replace(day=1)
    if inicio.month == 12:
        fin = inicio.replace(year=inicio.year + 1, month=1) - timedelta(days=1)
    else:
        fin = inicio.replace(month=inicio.month + 1) - timedelta(days=1)
    return inicio, fin


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# ── Fechas sin hora ──────────────────────────────────────────
# BSON no tiene un tipo "solo fecha": PyMongo rechaza datetime.date. Por eso las
# fechas (feriados, ausencias, campanas) se guardan como texto ISO "AAAA-MM-DD",
# que ademas se compara correctamente en las consultas de MongoDB.
def fecha_iso(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.astimezone(business_tz()).date().isoformat() if valor.tzinfo else valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)[:10]


def a_fecha(valor: Any) -> date | None:
    """Convierte texto ISO, datetime o date a date."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.astimezone(business_tz()).date() if valor.tzinfo else valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None