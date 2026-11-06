"""Diagnóstico de solo lectura: API, MongoDB y Redis, sin cuentas de prueba.

Ejecutar dentro de la API con ``python -m app.scripts.diagnostico``. La ruta
health comprueba ambas dependencias. No inicia sesión, modifica preferencias ni
crea exportaciones. No imprime el cuerpo recibido ni la configuración.
"""

from __future__ import annotations

import argparse
import asyncio
import os

import httpx


async def comprobar(
    url: str | None = None,
    *,
    transporte: httpx.AsyncBaseTransport | None = None,
) -> int:
    prefijo = os.environ.get("API_PREFIX", "/api").rstrip("/")
    destino = url or f"http://localhost:8000{prefijo}/health"
    try:
        async with httpx.AsyncClient(timeout=30, transport=transporte, trust_env=False) as cliente:
            respuesta = await cliente.get(destino)
    except httpx.HTTPError:
        print("FALLA: no se pudo conectar con la API. Comprueba que esté iniciada.")
        return 1

    if respuesta.status_code != 200:
        print(f"FALLA: la API respondió HTTP {respuesta.status_code}.")
        return 1
    try:
        salud = respuesta.json()
    except ValueError:
        print("FALLA: la API no devolvió un diagnóstico válido.")
        return 1
    if not isinstance(salud, dict):
        print("FALLA: la API no devolvió un diagnóstico válido.")
        return 1

    print("OK: la API responde.")
    mongo_ok = salud.get("mongo") is True
    redis_ok = salud.get("redis") is True
    print("OK: MongoDB responde." if mongo_ok else "FALLA: MongoDB no confirmó disponibilidad.")
    print("OK: Redis responde." if redis_ok else "FALLA: Redis no confirmó disponibilidad.")
    if salud.get("estado") != "ok" or not mongo_ok or not redis_ok:
        print("Diagnóstico incompleto: revisa los servicios con docker compose ps.")
        return 1
    print("Diagnóstico correcto. Comprueba también el acceso web y tus archivos desde el navegador.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="URL del endpoint health; por defecto, la API local del contenedor.")
    args = parser.parse_args()
    return asyncio.run(comprobar(args.url))


if __name__ == "__main__":
    raise SystemExit(main())
