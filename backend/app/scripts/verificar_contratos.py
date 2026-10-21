"""Contrasta las respuestas de la API con lo que espera la interfaz."""

from __future__ import annotations

import asyncio
import json
import os

import httpx

API = os.environ.get('VERIFICAR_API', 'http://host.docker.internal/api')
CORREO = os.environ.get("VERIFICAR_CORREO", "admin@demo.local")
PASSWORD = os.environ.get("VERIFICAR_PASSWORD", "Demo12345")

# Rutas que consume la interfaz y campos que esta lee de la respuesta.
CONTRATOS: list[tuple[str, list[str]]] = [
    ("/auth/sesion", ["id", "nombre", "email", "rol", "iniciales", "permisos", "institucion", "csrf_token"]),
    ("/tickets/ajustes-crear", ["categorias", "tipos_equipo", "urgencias", "tipos_problema", "estados"]),
    ("/inventario-placeholder", []),
]

problemas: list[str] = []


async def main() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=60, headers={"Host": "localhost"}) as cliente:
        inicio = await cliente.post("/auth/login", json={"correo": CORREO, "password": PASSWORD})
        sesion = inicio.json()
        cab = {"Authorization": f"Bearer {sesion['access_token']}", "X-CSRF-Token": sesion["csrf_token"]}

        for ruta, campos in CONTRATOS:
            if not campos:
                continue
            respuesta = await cliente.get(ruta, headers=cab)
            cuerpo = respuesta.json()
            faltan = [campo for campo in campos if campo not in cuerpo]
            estado = "OK  " if not faltan else "FALLA"
            print(f"  {estado} {ruta}" + (f" — faltan {faltan}" if faltan else ""))

        # Comprobaciones puntuales de lo que la interfaz realmente dibuja
        equipos = await cliente.get("/equipos/mis", headers=cab)
        print("\n  /equipos/mis:", list(equipos.json().keys()))
        for clave in ("por_conjunto", "uso_comun_oficina", "conjuntos"):
            if clave not in equipos.json():
                problemas.append(f"/equipos/mis no trae {clave}")

        tickets = await cliente.get("/tickets?pagina=1", headers=cab)
        primero = (tickets.json().get("items") or [{}])[0]
        print("  /tickets primer item:", list(primero.keys()))
        for clave in ("id", "codigo", "estado", "prioridad", "tiene_chat", "sla", "reportante_nombre", "afectado_nombre"):
            if clave not in primero:
                problemas.append(f"/tickets no trae {clave}")

        panel = await cliente.get("/equipo-ti/panel", headers=cab)
        tecnico = (panel.json().get("items") or [{}])[0]
        print("  /equipo-ti/panel item:", list(tecnico.keys()))
        for clave in ("tecnico_id", "tecnico_nombre", "estado", "etiqueta", "porcentaje_carga", "metricas"):
            if clave not in tecnico:
                problemas.append(f"/equipo-ti/panel no trae {clave}")

        activos = await cliente.get("/activos", headers=cab)
        activo = (activos.json().get("items") or [{}])[0]
        print("  /activos primer item:", list(activo.keys()))
        for clave in ("id", "tipo", "oficina_nombre", "completitud", "campos_faltantes", "opciones_avanzadas"):
            if clave not in activo:
                problemas.append(f"/activos no trae {clave}")

        zonas = await cliente.get("/zonas", headers=cab)
        print("  /zonas item:", list((zonas.json().get("items") or [{}])[0].keys()))

        campanas = await cliente.get("/campanas", headers=cab)
        print("  /campanas:", list(campanas.json().keys()))

        calidad = await cliente.get("/calidad-inventario", headers=cab)
        print("  /calidad-inventario:", list(calidad.json().keys()))

        permisos = await cliente.get("/permisos/matriz", headers=cab)
        grupo = permisos.json()[0]
        print("  /permisos/matriz grupo:", list(grupo.keys()))
        if "permisos" not in grupo:
            problemas.append("/permisos/matriz no agrupa los permisos")

        console = await cliente.get("/configuracion/estado-ia", headers=cab)
        print("  /configuracion/estado-ia:", list(console.json().keys()))
        for clave in ("proveedor", "modelo", "disponible", "motivo"):
            if clave not in console.json():
                problemas.append(f"/configuracion/estado-ia no trae {clave}")

        configuracion = await cliente.get("/configuracion", headers=cab)
        seccion_ia = configuracion.json().get("ia") or {}
        print("  /configuracion seccion ia:", list(seccion_ia.keys()))
        for clave in ("global_activa", "aprendizaje_activo", "recomendaciones_activas", "confianza_minima"):
            if clave not in seccion_ia:
                problemas.append(f"/configuracion ia no trae {clave}")

    if problemas:
        print("\nProblemas de contrato:")
        for problema in problemas:
            print("  -", problema)
        raise SystemExit(1)
    print("\nLos contratos coinciden con la interfaz.")


asyncio.run(main())
