"""Comandos de operacion.

    python -m app.scripts.demo cargar      # carga datos de DEMOSTRACION
    python -m app.scripts.demo eliminar    # los elimina
    python -m app.scripts.migraciones      # aplica migraciones pendientes
    python -m app.scripts.admin_crear      # crea el administrador inicial
    python -m app.scripts.salud            # comprueba Mongo, Redis y migraciones
"""

from __future__ import annotations

import asyncio
import json
import sys

from app.core.config import settings
from app.core.db import close_connections, ping_mongo, ping_redis
from app.core.logging_config import configurar_logging


def _pizarra(mensaje: str) -> None:
    print(f"\n{mensaje}\n")


async def _principal() -> None:
    from app.migrations import runner

    _pizarra(f"Mesa de Ayuda TI - {settings.institution_name}")
    _pizarra("Aplicando migraciones...")
    aplicadas = await runner.ejecutar()
    print("Aplicadas: " + (", ".join(aplicadas) if aplicadas else "ninguna (ya estaban al dia)"))
    print("\nEstado de migraciones:")
    for fila in await runner.estado():
        marca = "OK " if fila["aplicada"] else "-- "
        print(f"  {marca}{fila['version']}  {fila['descripcion']}")
    await close_connections()


def main() -> None:
    configurar_logging("WARNING")
    asyncio.run(_principal())


if __name__ == "__main__":
    main()