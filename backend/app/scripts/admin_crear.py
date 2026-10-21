"""Crea el administrador inicial por consola (arranque guiado sin interfaz).

    python -m app.scripts.admin_crear --nombre "Admin" --email admin@muni.gob.pe --password "ClaveSegura1"
"""

from __future__ import annotations

import asyncio
import getpass
import json
import sys

from app.core.db import close_connections
from app.core.errors import Prohibido
from app.core.logging_config import configurar_logging
from app.migrations import runner


def _argumentos() -> dict[str, str]:
    valores = {"nombre": "", "email": "", "password": ""}
    argv = sys.argv[1:]
    indice = 0
    while indice < len(argv):
        clave = argv[indice].lstrip("-")
        if clave in valores and indice + 1 < len(argv):
            valores[clave] = argv[indice + 1]
            indice += 2
        else:
            indice += 1
    if not valores["nombre"]:
        valores["nombre"] = input("Nombre completo: ").strip()
    if not valores["email"]:
        valores["email"] = input("Correo: ").strip()
    if not valores["password"]:
        valores["password"] = getpass.getpass("Contrasena (minimo 8 caracteres): ")
    return valores


async def _principal() -> int:
    from app.services import auth_service

    await runner.ejecutar()
    datos = _argumentos()
    try:
        admin = await auth_service.crear_admin_inicial(datos)
    except Prohibido as exc:
        print(f"No se pudo crear: {exc.mensaje}")
        return 1
    print(json.dumps({"id": str(admin["_id"]), "nombre": admin["nombre"], "email": admin["email"]}, ensure_ascii=False, indent=2))
    print("\nYa puedes ingresar con esa cuenta. El sistema esta listo.")
    return 0


def main() -> None:
    configurar_logging("WARNING")
    try:
        codigo = asyncio.run(_principal())
    finally:
        asyncio.run(close_connections())
    raise SystemExit(codigo)


if __name__ == "__main__":
    main()