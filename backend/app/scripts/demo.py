"""Script de linea de comandos para cargar o eliminar los datos de demostracion.

    python -m app.scripts.demo cargar
    python -m app.scripts.demo eliminar
"""

from __future__ import annotations

import asyncio
import json
import sys

from app.core.db import close_connections
from app.core.logging_config import configurar_logging


async def _cargar() -> int:
    from app.services import demo_service

    resultado = await demo_service.cargar()
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    return 0


async def _eliminar() -> int:
    from app.services import demo_service

    resultado = await demo_service.eliminar()
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    return 0


async def _estado() -> int:
    from app.services import demo_service

    existe = await demo_service.hay_demo()
    print("Datos de demostracion cargados: " + ("si" if existe else "no"))
    return 0


async def _principal(accion: str) -> int:
    acciones = {"cargar": _cargar, "eliminar": _eliminar, "estado": _estado}
    try:
        return await acciones[accion]()
    finally:
        await close_connections()


def main() -> None:
    configurar_logging("WARNING")
    accion = sys.argv[1] if len(sys.argv) > 1 else "estado"
    if accion not in {"cargar", "eliminar", "estado"}:
        print("Uso: python -m app.scripts.demo [cargar|eliminar|estado]")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_principal(accion)))


if __name__ == "__main__":
    main()