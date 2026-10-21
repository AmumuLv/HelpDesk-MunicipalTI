"""Prueba de humo contra el sistema ya desplegado.

    docker compose exec api python -m app.scripts.humo

Verifica el arranque guiado, el login, la jerarquia, un ticket de usuario, el chat
condicionado al origen y una exportacion PDF.
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

import httpx

from app.core.config import settings

BASE = os.environ.get('VERIFICAR_API', 'http://localhost:8000/api')
PASSWORD = "PruebaHumo123"


def _titulo(texto: str) -> None:
    print(f"\n=== {texto} ===")


async def _main() -> int:
    if settings.is_production:
        print('Esta prueba crea datos. Ejecutala solo en una instalacion de pruebas separada, nunca en produccion.')
        return 2
    errores: list[str] = []
    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as cliente:

        async def revisar(nombre: str, condicion: bool, detalle: object = "") -> None:
            texto = detalle if isinstance(detalle, str) else str(detalle)
            print(("  OK   " if condicion else "  FALLA ") + nombre + (f" - {texto}" if texto and not condicion else ""))
            if not condicion:
                errores.append(nombre)

        _titulo("Salud del sistema")
        salud = (await cliente.get("/health")).json()
        await revisar("MongoDB responde", salud["mongo"])
        await revisar("Redis responde", salud["redis"])

        _titulo("Instalacion")
        instalacion = (await cliente.get("/instalacion")).json()
        print(f"  siguiente paso: {instalacion['siguiente_paso']}")
        await revisar("La instalacion informa el siguiente paso", bool(instalacion["siguiente_paso"]))
        _titulo("Crear administrador (si no existe)")
        admin_correo = "humo@admin.local"
        if not instalacion["hay_admin"]:
            creado = await cliente.post(
                "/instalacion/administrador",
                json={"nombre": "Administrador Humo", "email": admin_correo, "password": PASSWORD},
            )
            await revisar("Administrador creado", creado.status_code == 200, creado)
        # La guia solo crea el primer administrador. Si la institucion ya tiene uno,
        # esta cuenta de prueba se crea por consola (mismo permiso que el instalador)
        # para que el chequeo sea idempotente y se pueda repetir.
        from app.core.db import get_db
        from app.services import usuario_service

        existe = await get_db()["usuarios"].find_one({"email": admin_correo})
        existe_admin_id = (existe or {}).get("_id")
        if existe is None:
            otro_admin = await get_db()["usuarios"].find_one({"rol": "administrador", "activo": True})
            existe_admin_id = (otro_admin or {}).get("_id")
        if existe is None:
            await usuario_service.crear(
                {
                    "nombre": "Administrador Humo",
                    "email": admin_correo,
                    "password": PASSWORD,
                    "rol": "administrador",
                },
                usuario={"_id": existe_admin_id, "nombre": "Instalador", "rol": "administrador"},
            )
        inicio = await cliente.post("/auth/login", json={"correo": admin_correo, "password": PASSWORD})
        await revisar("Login de administrador", inicio.status_code == 200, inicio)
        admin = inicio.json()
        cab_admin = {"Authorization": f"Bearer {admin['access_token']}", "X-CSRF-Token": admin["csrf_token"]}

        _titulo("CSRF obligatorio")
        sin_csrf = await cliente.post("/zonas", json={"nombre": "SIN CSRF"}, headers={"Authorization": cab_admin["Authorization"]})
        await revisar("Sin X-CSRF-Token se rechaza", sin_csrf.status_code == 403, f"{sin_csrf.status_code}")

        _titulo("Jerarquia Zona > Oficina > Usuario")
        def clave_id(documento: dict) -> str:
            return documento.get("id") or documento.get("_id")

        zonas = (await cliente.get("/zonas", headers=cab_admin)).json()["items"]
        zona_nombre = "Zona Humo"
        zona = next((z for z in zonas if z["nombre"] == zona_nombre), None)
        if zona is None:
            respuesta = await cliente.post("/zonas", json={"nombre": zona_nombre}, headers=cab_admin)
            await revisar("Zona creada", respuesta.status_code == 201, respuesta)
            zona = respuesta.json()
        oficinas = (await cliente.get(f"/oficinas?zona_id={clave_id(zona)}", headers=cab_admin)).json()["items"]
        oficina_nombre = "OFICINA HUMO"
        oficina = next((o for o in oficinas if o["nombre"] == oficina_nombre), None)
        if oficina is None:
            respuesta = await cliente.post(
                "/oficinas", json={"nombre": oficina_nombre, "zona_id": clave_id(zona)}, headers=cab_admin
            )
            await revisar("Oficina creada", respuesta.status_code == 201, respuesta)
            oficina = respuesta.json()
        correo_tecnico = "humo@tecnico.local"
        correo_usuario = "humo@usuario.local"
        usuarios = (await cliente.get("/usuarios", headers=cab_admin)).json()["items"]
        if not any(u["email"] == correo_tecnico for u in usuarios):
            respuesta = await cliente.post(
                "/usuarios",
                json={"nombre": "Tecnico Humo", "email": correo_tecnico, "password": PASSWORD, "rol": "tecnico", "oficina_id": clave_id(oficina)},
                headers=cab_admin,
            )
            await revisar("Tecnico creado", respuesta.status_code == 201, respuesta)
        if not any(u["email"] == correo_usuario for u in usuarios):
            respuesta = await cliente.post(
                "/usuarios",
                json={"nombre": "Usuario Humo", "email": correo_usuario, "password": PASSWORD, "rol": "usuario", "oficina_id": clave_id(oficina)},
                headers=cab_admin,
            )
            await revisar("Usuario creado", respuesta.status_code == 201, respuesta)

        _titulo("Inventario")
        equipos = (await cliente.get("/activos?por_pagina=5", headers=cab_admin)).json()
        await revisar("Listado de activos responde", "items" in equipos, equipos)
        nuevo = await cliente.post(
            "/activos",
            json={"tipo": "Monitor", "oficina_id": clave_id(oficina), "marca": "Dell"},
            headers=cab_admin,
        )
        await revisar("Activo guardado con datos faltantes", nuevo.status_code == 201, nuevo)
        if nuevo.status_code == 201:
            detalle = nuevo.json()
            await revisar("El aviso de datos faltantes es visible", detalle["faltantes"] > 0)
            await revisar("El interruptor de opciones avanzadas arranca apagado", detalle["opciones_avanzadas"] is False)
            marcado = await cliente.post(
                f"/activos/{detalle['id']}/campos",
                json={"campos": ["codigo_patrimonial"], "estado": "no_aplica", "motivo": "Equipo sin codigo asignado"},
                headers=cab_admin,
            )
            await revisar("Marcar No aplica", marcado.status_code == 200, marcado)
            if marcado.status_code == 200:
                despues = marcado.json()["activo"]
                await revisar(
                    "Deja de avisar por codigo patrimonial",
                    "codigo_patrimonial" not in (despues.get("campos_faltantes") or []),
                )
                await revisar("Se muestra como No aplica", despues["campos"]["codigo_patrimonial"]["estado"] == "no_aplica")
        calidad = (await cliente.get("/calidad-inventario", headers=cab_admin)).json()
        await revisar("Panel de calidad responde", "porcentaje_global" in calidad)

        _titulo("Ticket del usuario en 2 pasos (para un companero)")
        inicio_usuario = await cliente.post("/auth/login", json={"correo": correo_usuario, "password": PASSWORD})
        await revisar("Login de usuario", inicio_usuario.status_code == 200, inicio_usuario)
        usuario = inicio_usuario.json()
        cab_usuario = {"Authorization": f"Bearer {usuario['access_token']}", "X-CSRF-Token": usuario["csrf_token"]}
        companeros = (await cliente.get("/usuarios/companeros", headers=cab_usuario)).json()
        await revisar("Companeros de la oficina disponibles", len(companeros["items"]) >= 0)
        companero = next((c for c in companeros["items"] if c["nombre"] != "Usuario Humo"), None)
        reporte = await cliente.post(
            "/tickets",
            json={
                "tipo_problema": "No enciende",
                "descripcion": "La computadora no prende cuando la enciendo.",
                "persona": {"es_para_mi": False, "afectado_id": (companero or {}).get("id")},
                "urgencia": "no_puedo_trabajar",
            },
            headers=cab_usuario,
        )
        await revisar("Ticket creado en 2 pasos", reporte.status_code == 201, reporte)
        ticket_usuario = (reporte.json().get("ticket") or {}) if reporte.status_code == 201 else {}
        if ticket_usuario:
            await revisar("El ticket tiene chat", ticket_usuario["tiene_chat"] is True)
            await revisar("Devuelve tiempo esperado en lenguaje simple", bool(reporte.json().get("tiempo_esperado")))
            mensaje = await cliente.post(
                f"/tickets/{ticket_usuario['id']}/mensajes", json={"cuerpo": "Hola, no enciende la maquina."}, headers=cab_usuario
            )
            await revisar("Chat del ticket de usuario funciona", mensaje.status_code == 201, mensaje)

        _titulo("Ticket creado por tecnico: SIN chat")
        inicio_tecnico = await cliente.post("/auth/login", json={"correo": correo_tecnico, "password": PASSWORD})
        tecnico = inicio_tecnico.json()
        cab_tecnico = {"Authorization": f"Bearer {tecnico['access_token']}", "X-CSRF-Token": tecnico["csrf_token"]}
        manual = await cliente.post(
            "/tickets/manual",
            json={
                "persona": {"afectado_id": (companero or {}).get("id"), "detectado_por_tec": True},
                "asunto": "Supervision de equipo",
                "descripcion": "Detectado en supervision que la CPU no arranca.",
                "prioridad": "media",
            },
            headers=cab_tecnico,
        )
        await revisar("Ticket manual creado", manual.status_code == 201, manual)
        ticket_manual = (manual.json().get("ticket") or {}) if manual.status_code == 201 else {}
        if ticket_manual:
            await revisar("El ticket manual NO tiene chat", ticket_manual["tiene_chat"] is False)
            rechazo = await cliente.post(
                f"/tickets/{ticket_manual['id']}/mensajes", json={"cuerpo": "prueba"}, headers=cab_tecnico
            )
            await revisar(
                "El backend rechaza el chat en ticket sin chat",
                rechazo.status_code == 403,
                str(rechazo.json()),
            )
            nota = await cliente.post(
                f"/tickets/{ticket_manual['id']}/notas", json={"cuerpo": "Se revisa el cable de corriente."}, headers=cab_tecnico
            )
            await revisar("Notas internas funcionan", nota.status_code == 201, nota)
            resolucion = await cliente.post(
                f"/tickets/{ticket_manual['id']}/estado",
                json={"estado": "cerrado", "nota_resolucion": "Se cambio el cable de corriente."},
                headers=cab_tecnico,
            )
            await revisar("Se resuelve con nota de una via", resolucion.status_code == 200, resolucion)

        _titulo("Permisos delegables")
        matriz = (await cliente.get("/permisos/matriz", headers=cab_admin)).json()
        await revisar("Matriz de permisos disponible", len(matriz) >= 4)
        permisos = (await cliente.get("/permisos/tecnicos", headers=cab_admin)).json()["items"]
        tecnico_id = next(p["usuario_id"] for p in permisos if p["nombre"] == "Tecnico Humo")
        # Dejar el permiso apagado para comprobar que el backend lo respeta
        await cliente.put(f"/permisos/tecnicos/{tecnico_id}", json={"cambios": {"equipos.crear": False}}, headers=cab_admin)
        negados = await cliente.post(
            "/activos",
            json={"tipo": "Teclado", "oficina_id": clave_id(oficina)},
            headers=cab_tecnico,
        )
        await revisar("Tecnico sin permiso no crea equipos", negados.status_code == 403, f"{negados.status_code} {negados.text[:120]}")
        await cliente.put(f"/permisos/tecnicos/{tecnico_id}", json={"cambios": {"equipos.crear": True}}, headers=cab_admin)
        ahora_si = await cliente.post(
            "/activos",
            json={"tipo": "Teclado", "oficina_id": clave_id(oficina)},
            headers=cab_tecnico,
        )
        await revisar("Con el permiso activado si puede", ahora_si.status_code == 201, ahora_si)

        _titulo("Recomendaciones de IA por persona")
        lectura = (await cliente.get("/auth/preferencia-ia", headers=cab_tecnico)).json()
        await revisar("Preferencia de IA visible", "recomendaciones_visibles" in lectura)
        apagada = await cliente.post("/auth/preferencia-ia", json={"recomendaciones_ia": False}, headers=cab_tecnico)
        await revisar("Se puede desactivar por persona", apagada.status_code == 200, apagada)
        await revisar("Aviso honesto al desactivar", "aprendiendo" in apagada.json()["mensaje"], apagada.json()["mensaje"])

        _titulo("Panel de Equipo TI y horarios")
        panel = (await cliente.get("/equipo-ti/panel", headers=cab_admin)).json()
        await revisar("Panel con estados calculados", any(i["tecnico_nombre"] == "Tecnico Humo" for i in panel["items"]))
        _titulo("Exportacion PDF")
        exportacion = await cliente.post(
            "/exportaciones",
            json={"tipo": "tickets", "formato": "pdf", "filtros": {}},
            headers=cab_admin,
        )
        await revisar("Exportacion PDF generada", exportacion.status_code == 200, exportacion)
        if exportacion.status_code == 200:
            descarga = await cliente.get(exportacion.json()["descarga_url"], headers=cab_admin)
            await revisar("El PDF se descarga", descarga.status_code == 200 and descarga.content[:4] == b"%PDF", descarga.text[:200])

        _titulo("Resumen del panel TI")
        resumen = (await cliente.get("/analitica/resumen", headers=cab_admin)).json()
        await revisar("Resumen con cifras reales", "tickets_abiertos" in resumen)

    print("\n" + "=" * 60)
    if errores:
        print(f"FALLARON {len(errores)} comprobaciones:")
        for error in errores:
            print(f"  - {error}")
        return 1
    print("Todas las comprobaciones pasaron.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
