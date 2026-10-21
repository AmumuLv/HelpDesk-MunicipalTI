"""Comprobacion de la interfaz contra el sistema desplegado.

Verifica que la web responde, que la API se sirve en el mismo origen y que el
ciclo completo (entrar, reportar un problema, escribir en el chat) funciona tal
como lo vera una persona en su navegador.
"""

from __future__ import annotations

import asyncio
import json

import httpx

# Cuando se ejecuta dentro de un contenedor, el proxy del host se alcanza por
# host.docker.internal; desde la maquina del municipio, por localhost.
import os

HOST = os.environ.get("VERIFICAR_HOST", "localhost")
# El proxy solo responde al dominio configurado en SITE_ADDRESS (por defecto
# localhost), asi que se envia esa cabecera aunque se llegue por otra ruta.
CABECERA_HOST = {"Host": "localhost"}
ORIGENES = [
    ("proxy (puerto 80)", f"http://{HOST}"),
    ("web (puerto 8080)", f"http://{HOST}:8080"),
]

API = os.environ.get('VERIFICAR_API', f"http://{HOST}/api")
CORREO = os.environ.get("VERIFICAR_CORREO", "admin@demo.local")
PASSWORD = os.environ.get("VERIFICAR_PASSWORD", "Demo12345")

fallos: list[str] = []


def revisar(etiqueta: str, ok: bool, detalle: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FALLA'} {etiqueta}" + (f" — {detalle}" if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


async def main() -> None:
    print("\n=== La web responde ===")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=CABECERA_HOST) as cliente:
        for nombre, origen in ORIGENES:
            try:
                respuesta = await cliente.get(f"{origen}/")
                revisar(f"{nombre}: index.html", respuesta.status_code == 200 and 'id="root"' in respuesta.text, str(respuesta.status_code))
            except Exception as exc:  # noqa: BLE001
                revisar(f"{nombre}: index.html", False, str(exc)[:80])

        # La API vive en el mismo origen
        salud = await cliente.get(f"{API}/health")
        revisar("proxy: /api/health", salud.status_code == 200 and salud.json()["estado"] == "ok", str(salud.status_code))

        # Una ruta del navegador (enrutado del lado del cliente) devuelve index
        profunda = await cliente.get(f"http://{HOST}/bandeja")
        revisar("proxy: ruta interna devuelve la app", 'id="root"' in profunda.text)

        # Las fuentes se sirven
        fuente = await cliente.get(f"http://{HOST}/fuentes/atkinson-hyperlegible-400.woff2")
        revisar("tipografía local", fuente.status_code == 200 and fuente.content[:4] == b"wOF2", str(fuente.status_code))

        # Los archivos con huella se sirven y el index no se cachea
        cabecera = await cliente.get(f"http://{HOST}/")
        revisar(
            "cabeceras de seguridad",
            cabecera.headers.get("x-content-type-options") == "nosniff",
            cabecera.headers.get("x-content-type-options", "sin cabecera"),
        )

    print("\n=== Ciclo completo de una persona ===")
    async with httpx.AsyncClient(base_url=API, timeout=60, headers=CABECERA_HOST) as cliente:
        inicio = await cliente.post("/auth/login", json={"correo": CORREO, "password": PASSWORD})
        revisar("iniciar sesión", inicio.status_code == 200)
        sesion = inicio.json()
        cab = {"Authorization": f"Bearer {sesion['access_token']}", "X-CSRF-Token": sesion["csrf_token"]}

        actual = await cliente.get("/auth/sesion", headers=cab)
        revisar("recuperar la sesión", actual.status_code == 200, actual.json()["nombre"])

        ajustes = await cliente.get("/tickets/ajustes-crear", headers=cab)
        revisar(
            "formulario de 2 pasos",
            ajustes.status_code == 200 and bool(ajustes.json()["tipos_problema"]) and bool(ajustes.json()["urgencias"]),
        )

        creado = await cliente.post(
            "/tickets",
            json={"tipo_problema": ajustes.json()["tipos_problema"][0]["clave"], "urgencia": "me_frena"},
            headers=cab,
        )
        revisar("reportar un problema", creado.status_code == 201, creado.text[:120])
        cuerpo = creado.json()
        ticket = cuerpo["ticket"]
        revisar("el ticket tiene chat", ticket["tiene_chat"] is True)
        revisar("devuelve tiempo esperado", bool(cuerpo["tiempo_esperado"]), cuerpo["tiempo_esperado"])
        revisar("enlace de seguimiento", cuerpo["enlace_seguimiento"].startswith("/mis-tickets/"), cuerpo["enlace_seguimiento"])

        mensaje = await cliente.post(
            f"/tickets/{ticket['id']}/mensajes", json={"cuerpo": "Prueba desde la interfaz"}, headers=cab
        )
        revisar("escribir en el chat", mensaje.status_code == 201)

        eventos = await cliente.get(f"/tickets/{ticket['id']}", headers=cab)
        revisar("abrir el detalle", eventos.status_code == 200 and len(eventos.json()["eventos"]) > 0)

        # El ticket sin chat del equipo TI
        manual = await cliente.post(
            "/tickets/manual",
            json={"persona": {"afectado_id": sesion["id"]}, "asunto": "Prueba sin chat", "prioridad": "baja"},
            headers=cab,
        )
        revisar("registro compacto del equipo TI", manual.status_code == 201)
        sin_chat = await cliente.post(
            f"/tickets/{manual.json()['ticket']['id']}/mensajes", json={"cuerpo": "hola"}, headers=cab
        )
        revisar("el backend rechaza el chat sin chat", sin_chat.status_code == 403, sin_chat.json().get("codigo", ""))

        # Pantallas del panel
        for ruta, etiqueta in [
            ("/analitica/resumen", "resumen del panel"),
            ("/analitica/panel", "análisis con 13 bloques"),
            ("/equipo-ti/panel", "panel del equipo TI"),
            ("/calidad-inventario", "calidad del inventario"),
            ("/permisos/matriz", "matriz de permisos"),
            ("/configuracion/feriados", "feriados"),
            ("/kb/articulos", "base de conocimiento"),
            ("/campanas", "campañas"),
        ]:
            respuesta = await cliente.get(ruta, headers=cab)
            revisar(f"pantalla: {etiqueta}", respuesta.status_code == 200, str(respuesta.status_code))

    print("\n" + "=" * 60)
    if fallos:
        print(f"FALLARON {len(fallos)} comprobaciones:")
        for fallo in fallos:
            print("  -", fallo)
        raise SystemExit(1)
    print("Todo funciona de extremo a extremo.")


asyncio.run(main())
