"""Diagnostico puntual de endpoints (uso interno durante el desarrollo)."""

from __future__ import annotations

import asyncio
import json

import httpx

BASE = "http://localhost:8000/api"
PASSWORD = "PruebaHumo123"


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as cliente:
        inicio = await cliente.post("/auth/login", json={"correo": "humo@admin.local", "password": PASSWORD})
        if inicio.status_code != 200:
            print("login:", inicio.status_code, inicio.text[:200])
            return
        sesion = inicio.json()
        cab = {"Authorization": f"Bearer {sesion['access_token']}", "X-CSRF-Token": sesion["csrf_token"]}
        for ruta in [
            "/analitica/resumen",
            "/exportaciones",
            "/campanas",
            "/kb/articulos",
            "/calidad-inventario",
            "/equipo-ti/panel",
            "/ia/asistente/preguntas",
            "/auditoria",
            "/configuracion",
        ]:
            r = await cliente.get(ruta, headers=cab)
            print(f"GET {ruta:35} -> {r.status_code} {r.text[:150]}")

        pref = await cliente.post("/auth/preferencia-ia", json={"recomendaciones_ia": False}, headers=cab)
        print("POST /auth/preferencia-ia ->", pref.status_code, json.dumps(pref.json(), ensure_ascii=False)[:300])

        exp = await cliente.post("/exportaciones", json={"tipo": "tickets", "formato": "pdf", "filtros": {}}, headers=cab)
        print("POST /exportaciones ->", exp.status_code, exp.text[:200])
        if exp.status_code == 200:
            url = exp.json()["descarga_url"]
            desc = await cliente.get(url, headers=cab)
            print("GET", url, "->", desc.status_code, desc.content[:20])


asyncio.run(main())