"""Cruza las llamadas del frontend con las rutas reales del OpenAPI.

    python tools/verificar_rutas.py

Si una pantalla llama a un endpoint que no existe, el botón falla en tiempo de
ejecución y el usuario solo ve un error. Este script lo detecta sin abrir el
navegador.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
OPENAPI = RAIZ / "frontend" / "openapi.json"
FUENTE = RAIZ / "frontend" / "src"

# patrón de llamada: api.crear('/ruta', ...), api.obtener<Tipo>('/ruta') ...
LLAMADA = re.compile(r'''api\.(crear|editar|borrar|subir|reemplazar|obtener|listar)(?:<[^>]*>)?\(\s*(`\/[^`]*`|'\/[^']*'|"\/[^\"]*")''')
PLANTILLA = re.compile(r"\{[^}]+\}")
ALTERNATIVA = re.compile(r"\$\{[^{}]*\?\s*'([^']+)'\s*:\s*'([^']+)'\s*\}")


def alternativas(ruta: str) -> list[str]:
    """Comprueba las dos ramas de los segmentos condicionales del frontend."""
    condicion = ALTERNATIVA.search(ruta)
    if not condicion:
        return [ruta]
    return [variante for rama in condicion.groups() for variante in alternativas(
        ruta[:condicion.start()] + rama + ruta[condicion.end():]
    )]

# método esperado por cada helper del cliente
METODO = {
    "crear": "post",
    "subir": "post",
    "editar": "patch",
    "reemplazar": "put",
    "borrar": "delete",
    "obtener": "get",
    "listar": "get",
}

# rutas montadas a mano en el cliente, con su método real
MONTADAS = {
    ("post", "/auth/login"),
    ("post", "/auth/logout"),
    ("post", "/auth/password"),
    ("get", "/auth/sesion"),
    ("get", "/mi-perfil"),
    ("get", "/publico/configuracion"),
    ("get", "/instalacion"),
}


def norm(ruta: str) -> str:
    """Quita el prefijo /api, los query y las plantillas variables.

    `${equipoId}` y `{activo_id}` son la misma cosa: ambas se reducen a `{x}`,
    porque el nombre del parámetro no importa para la comparación.
    """
    ruta = ruta.split("${consulta(", 1)[0]
    if ruta.startswith("/api"):
        ruta = ruta[4:]
    ruta = ruta.replace("${", "{")
    return PLANTILLA.sub("{x}", ruta).split("?", 1)[0]


def main() -> int:
    if not OPENAPI.exists():
        print("Falta frontend/openapi.json: ejecuta el volcado del backend.")
        return 2

    documento = json.loads(OPENAPI.read_text(encoding="utf-8"))
    existentes: set[tuple[str, str]] = set()
    for ruta, metodos in documento.get("paths", {}).items():
        clave = norm(ruta)
        for metodo in metodos:
            if metodo in {"get", "post", "put", "patch", "delete"}:
                existentes.add((metodo, clave))
    existentes |= MONTADAS

    problemas: list[str] = []
    total = 0
    for archivo in sorted(FUENTE.rglob("*.ts*")):
        texto = archivo.read_text(encoding="utf-8")
        for helper, literal in LLAMADA.findall(texto):
            for ruta in alternativas(literal[1:-1]):
                total += 1
                metodo = METODO[helper]
                clave = norm(ruta)
                if (metodo, clave) in existentes:
                    continue
                verbos = sorted(m for m, r in existentes if r == clave)
                if verbos:
                    problemas.append(
                        f"{archivo.relative_to(RAIZ)}: api.{helper}('{ruta}') usa {metodo.upper()} "
                        f"pero la ruta declara {', '.join(v.upper() for v in verbos)}"
                    )
                else:
                    problemas.append(f"{archivo.relative_to(RAIZ)}: api.{helper}('{ruta}') -> no existe {metodo.upper()} {clave}")

    print(f"{total} llamada(s) revisada(s) contra {len(documento.get('paths', {}))} ruta(s) del OpenAPI\n")
    if not problemas:
        print("OK: todas las llamadas apuntan a una ruta que existe.")
        return 0
    print(f"{len(problemas)} problema(s):")
    for problema in problemas:
        print(f"  {problema}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
