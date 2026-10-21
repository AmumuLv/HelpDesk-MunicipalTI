"""Prueba critica: importacion del Excel de muestra (hoja = zona)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.db import get_db
from tests.conftest import PASSWORD


async def test_importacion_crea_dos_zonas_y_sus_oficinas(db, api, archivo_muestra):
    from app.services import org_service, usuario_service

    admin = await usuario_service.crear(
        {"nombre": "Admin Importacion", "email": "admin@imp.local", "password": PASSWORD, "rol": "administrador"},
        usuario={"nombre": "Test", "rol": "sistema"},
        es_primer_admin=True,
    )
    inicio = await api.post("/api/auth/login", json={"correo": "admin@imp.local", "password": PASSWORD})
    assert inicio.status_code == 200, inicio.text
    sesion = inicio.json()
    cabeceras = {"Authorization": f"Bearer {sesion['access_token']}", "X-CSRF-Token": sesion["csrf_token"]}

    contenido = Path(archivo_muestra).read_bytes()
    subida = await api.post(
        "/api/importacion/subir",
        files={"archivo": ("inventario.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=cabeceras,
    )
    assert subida.status_code == 200, subida.text
    analisis = subida.json()
    hojas = {h["nombre_hoja"]: h for h in analisis["hojas"]}

    # Cada hoja es una zona (el nombre de la hoja puede traer espacios sobrantes)
    assert {h["zona_nombre"] for h in analisis["hojas"]} == {"ZONA COMPLEJO", "ZONA MERCADO"}
    assert {h["nombre_hoja"].strip() for h in analisis["hojas"]} == {"ZONA COMPLEJO", "ZONA MERCADO"}
    hojas = {h["nombre_hoja"].strip(): h for h in analisis["hojas"]}
    # AREA -> oficinas; "ARCHIVO GENERAL " con espacio se normaliza
    assert "COMUNA" in hojas["ZONA COMPLEJO"]["oficinas"]
    assert "ATM" in hojas["ZONA COMPLEJO"]["oficinas"]
    assert any(o.strip() == "ARCHIVO GENERAL" for o in hojas["ZONA MERCADO"]["oficinas"])

    previsualizacion = await api.post(f"/api/importacion/{analisis['lote_id']}/previsualizar", json={}, headers=cabeceras)
    assert previsualizacion.status_code == 200, previsualizacion.text
    previa = previsualizacion.json()
    assert previa["total_filas"] == 39  # 21 filas en hoja 1 + 18 en hoja 2
    assert previa["con_error"] == 0, [f for f in previa["filas"] if f["errores"]]

    confirmado = await api.post(f"/api/importacion/{analisis['lote_id']}/confirmar", json={}, headers=cabeceras)
    assert confirmado.status_code == 200, confirmado.text
    resultado = confirmado.json()
    assert resultado["creados"] > 0
    assert resultado["errores"] == 0

    base = get_db()
    zonas = await base["zonas"].find().to_list(None)
    assert {z["nombre"] for z in zonas} == {"ZONA COMPLEJO", "ZONA MERCADO"}

    comuna = await base["oficinas"].find_one({"nombre_normalizado": "COMUNA"})
    archivo_general = await base["oficinas"].find_one({"nombre_normalizado": "ARCHIVO GENERAL"})
    assert comuna and archivo_general
    # El espacio sobrante del Excel queda recortado
    assert archivo_general["nombre"] == "ARCHIVO GENERAL"

    activos = await base["activos"].find().to_list(None)
    assert len(activos) >= 39
    tipos = {a["tipo"] for a in activos}
    assert "Mouse" in tipos, "MAUSE debe corregirse a Mouse"
    assert "Teclado" in tipos
    assert "Monitor" in tipos

    # Conjuntos: "COMPUTADORA N°1" de COMUNA con 4 componentes
    conjunto = await base["conjuntos"].find_one({"nombre": "Computadora N°1", "oficina_id": comuna["_id"]})
    assert conjunto is not None
    componentes = await base["activos"].find({"conjunto_id": conjunto["_id"]}).to_list(None)
    assert len(componentes) == 4
    assert {c["tipo"] for c in componentes} == {"Monitor", "Teclado", "Mouse", "CPU"}

    # Impresora sola -> activo individual, sin conjunto
    impresora = await base["activos"].find_one({"tipo": "Impresora", "oficina_id": comuna["_id"]})
    assert impresora is not None
    assert impresora["conjunto_id"] is None

    # Codigos numericos como texto y "-" tratado como sin codigo
    cpu = await base["activos"].find_one({"tipo": "CPU", "oficina_id": comuna["_id"]})
    assert cpu["codigo_patrimonial"] == "457821566"
    teclado = await base["activos"].find_one({"tipo": "Teclado", "oficina_id": comuna["_id"]})
    assert teclado["codigo_patrimonial"] is None

    # Sin responsable en el Excel -> uso comun de la oficina
    assert comuna is not None
    uso_comun = await base["activos"].count_documents({"oficina_id": comuna["_id"], "responsable_id": None})
    assert uso_comun > 0

    # Los incompletos NO son error de importacion
    incompletos = await base["activos"].count_documents({"oficina_id": comuna["_id"], "marca": None})
    assert incompletos > 0


async def test_reimportacion_es_idempotente(db, api, archivo_muestra):
    from app.services import usuario_service

    await usuario_service.crear(
        {"nombre": "Admin Idem", "email": "admin@idem.local", "password": PASSWORD, "rol": "administrador"},
        usuario={"nombre": "Test", "rol": "sistema"},
        es_primer_admin=True,
    )
    inicio = await api.post("/api/auth/login", json={"correo": "admin@idem.local", "password": PASSWORD})
    sesion = inicio.json()
    cabeceras = {"Authorization": f"Bearer {sesion['access_token']}", "X-CSRF-Token": sesion["csrf_token"]}
    contenido = Path(archivo_muestra).read_bytes()

    async def importar(nombre: str):
        subida = await api.post(
            "/api/importacion/subir",
            files={"archivo": (nombre, contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=cabeceras,
        )
        lote = subida.json()["lote_id"]
        confirmacion = await api.post(f"/api/importacion/{lote}/confirmar", json={}, headers=cabeceras)
        return confirmacion.json()

    primero = await importar("inventario.xlsx")
    assert primero["creados"] > 0
    base = get_db()
    total_primero = await base["activos"].count_documents({})

    segundo = await importar("inventario-2027.xlsx")
    # Con codigo patrimonial se actualiza; sin codigo se empareja por clave natural
    assert segundo["creados"] == 0, f"No debe duplicar equipos: {segundo}"
    assert segundo["actualizados"] > 0
    assert await base["activos"].count_documents({}) == total_primero


async def test_deshacer_importacion(db, api, archivo_muestra):
    from app.services import usuario_service

    await usuario_service.crear(
        {"nombre": "Admin Deshacer", "email": "admin@deshacer.local", "password": PASSWORD, "rol": "administrador"},
        usuario={"nombre": "Test", "rol": "sistema"},
        es_primer_admin=True,
    )
    inicio = await api.post("/api/auth/login", json={"correo": "admin@deshacer.local", "password": PASSWORD})
    sesion = inicio.json()
    cabeceras = {"Authorization": f"Bearer {sesion['access_token']}", "X-CSRF-Token": sesion["csrf_token"]}
    contenido = Path(archivo_muestra).read_bytes()
    subida = await api.post(
        "/api/importacion/subir",
        files={"archivo": ("inv.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=cabeceras,
    )
    lote = subida.json()["lote_id"]
    await api.post(f"/api/importacion/{lote}/confirmar", json={}, headers=cabeceras)
    base = get_db()
    assert await base["activos"].count_documents({}) > 0

    deshecho = await api.post(f"/api/importacion/{lote}/deshacer", headers=cabeceras)
    assert deshecho.status_code == 200, deshecho.text
    assert await base["activos"].count_documents({}) == 0
    documento = await base["importaciones"].find_one({"lote_id": lote})
    assert documento["estado"] == "deshecho"


async def test_plantilla_oficial_es_descargable(db, api):
    from app.services import usuario_service

    await usuario_service.crear(
        {"nombre": "Admin Plantilla", "email": "admin@plantilla.local", "password": PASSWORD, "rol": "administrador"},
        usuario={"nombre": "Test", "rol": "sistema"},
        es_primer_admin=True,
    )
    inicio = await api.post("/api/auth/login", json={"correo": "admin@plantilla.local", "password": PASSWORD})
    sesion = inicio.json()
    respuesta = await api.get(
        "/api/importacion/plantilla", headers={"Authorization": f"Bearer {sesion['access_token']}"}
    )
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/vnd.openxmlformats")

    from app.services import excel_service

    hojas = excel_service.leer_archivo(respuesta.content, "plantilla.xlsx")
    assert "Instrucciones" not in hojas
    assert "Inventario" in hojas
    cabeceras, registros = excel_service.hoja_a_registros(hojas["Inventario"])
    assert "Código patrimonial" in cabeceras
    assert registros == []
    _, detalle = excel_service.hoja_a_registros(hojas["Detalle avanzado"])
    assert detalle == []


async def test_ver_un_lote_exige_permiso_de_importar(db, api, archivo_muestra):
    """
    Leer la ficha de un lote es leer el Excel del municipio: su nombre, sus
    hojas y la estructura de sus columnas.

    Antes `GET /importacion/{lote_id}` solo exigía estar conectado, mientras que
    `/resumen` sí pedía `equipos.importar`. Dos rutas al mismo dato, una con
    llave y otra sin ella: cualquier cuenta de la aplicación —una persona que
    solo reporta tickets— podía abrir el análisis del archivo importado.
    """
    from app.services import org_service, usuario_service

    await usuario_service.crear(
        {"nombre": "Admin Lote", "email": "admin@lote.local", "password": PASSWORD, "rol": "administrador"},
        usuario={"nombre": "Test", "rol": "sistema"},
        es_primer_admin=True,
    )
    zona = await org_service.crear_zona({"nombre": "Zona Lote"}, usuario={"nombre": "Test", "rol": "sistema"})
    await org_service.crear_oficina({"nombre": "COMUNA", "zona_id": zona}, usuario={"nombre": "Test", "rol": "sistema"})

    inicio_admin = await api.post("/api/auth/login", json={"correo": "admin@lote.local", "password": PASSWORD})
    sesion_admin = inicio_admin.json()
    cabeceras_admin = {"Authorization": f"Bearer {sesion_admin['access_token']}", "X-CSRF-Token": sesion_admin["csrf_token"]}

    contenido = Path(archivo_muestra).read_bytes()
    subida = await api.post(
        "/api/importacion/subir",
        files={"archivo": ("inventario.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=cabeceras_admin,
    )
    assert subida.status_code == 200, subida.text
    lote = subida.json()["lote_id"]

    # Quien sí puede ver el lote lo ve.
    permitido = await api.get(f"/api/importacion/{lote}", headers={"Authorization": f"Bearer {sesion_admin['access_token']}"})
    assert permitido.status_code == 200, permitido.text
    assert permitido.json()["nombre_archivo"] == "inventario.xlsx"

    # Una persona que solo reporta tickets, no.
    await usuario_service.crear(
        {"nombre": "Vecina Reportante", "email": "vecina@lote.local", "password": PASSWORD, "rol": "usuario"},
        usuario={"nombre": "Test", "rol": "sistema"},
    )
    inicio_vecina = await api.post("/api/auth/login", json={"correo": "vecina@lote.local", "password": PASSWORD})
    sesion_vecina = inicio_vecina.json()
    cabecera_vecina = {"Authorization": f"Bearer {sesion_vecina['access_token']}"}

    prohibido = await api.get(f"/api/importacion/{lote}", headers=cabecera_vecina)
    assert prohibido.status_code == 403, prohibido.text
    assert "inventario.xlsx" not in prohibido.text

    # Y tampoco puede aplicar la importación, ni aunque se saltara el paso anterior.
    confirmar = await api.post(
        f"/api/importacion/{lote}/confirmar", json={}, headers={**cabecera_vecina, "X-CSRF-Token": sesion_vecina["csrf_token"]}
    )
    assert confirmar.status_code == 403, confirmar.text
    assert await db["activos"].count_documents({}) == 0