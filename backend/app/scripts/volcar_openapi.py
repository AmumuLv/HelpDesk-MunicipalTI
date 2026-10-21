"""Vuelca el esquema OpenAPI real de la API a disco.

    python -m app.scripts.volcar_openapi

Deja el archivo en frontend/openapi.json, que es la fuente de la que se generan
los tipos de TypeScript. Asi la interfaz nunca inventa un campo que el backend
no envia.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request


def abrir(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as respuesta:  # noqa: S310
        return json.load(respuesta)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    # Dentro del contenedor solo existe /app, asi que la ruta de salida se indica
    # de forma explicita (o se deja en el directorio actual).
    salida = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path.cwd() / "openapi.json"

    datos = abrir(f"{base}/api/openapi.json")
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")

    rutas = datos["paths"]
    esquemas = datos.get("components", {}).get("schemas", {})

    print(f"OpenAPI {datos['info']['version']} - {datos['info']['title']}")
    print(f"rutas documentadas: {len(rutas)}")
    print(f"esquemas: {len(esquemas)}")
    print(f"escrito en: {salida}")

    areas: dict[str, set[str]] = {}
    for ruta, operaciones in rutas.items():
        areas.setdefault(ruta.strip("/").split("/")[0], set()).update(m.upper() for m in operaciones)

    print("")
    print("Endpoints por area:")
    for area in sorted(areas):
        verbos = ",".join(sorted(areas[area]))
        total = sum(len(rutas[r]) for r in rutas if r.strip("/").split("/")[0] == area)
        print(f"  {area:<14} {total:>3} operaciones  [{verbos}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())