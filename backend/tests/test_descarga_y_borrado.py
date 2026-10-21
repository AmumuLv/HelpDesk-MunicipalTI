"""Descargar el inventario en Excel y eliminar campañas.

Las dos cosas que se pidieron juntas porque comparten el mismo riesgo: una es leer y la
otra es borrar, y las dos terminan en «el inventario del municipio». Aquí se comprueba
que descargar da un archivo de verdad con una hoja por zona, y que eliminar borra la
campaña **y solo la campaña**.
"""

from __future__ import annotations

import io

from bson import ObjectId
from openpyxl import load_workbook

from tests.test_inventario_anual import _excel_de_sala
from tests.test_tickets_horarios import _mundo


def _hojas(contenido: bytes) -> dict[str, list[list[str]]]:
    libro = load_workbook(io.BytesIO(contenido))
    return {hoja.title: [list(fila) for fila in hoja.iter_rows(values_only=True)] for hoja in libro.worksheets}


def _texto(contenido: bytes) -> str:
    """Todo el texto del libro, hoja por hoja.

    No se busca en los bytes a pelo: un `.xlsx` es un ZIP comprimido y las cadenas van
    deflactadas, así que buscar «CP-2026» en crudo no lo encuentra aunque el archivo
    lo contenga. Esa comprobación da verde sobre un archivo vacío.
    """
    return "\n".join(" | ".join(str(celda) for celda in fila if celda is not None) for filas in _hojas(contenido).values() for fila in filas)


async def _campana_con_cierre(api, mundo, nombre: str) -> dict:
    campana = (
        await api.post(
            "/api/campanas",
            json={"nombre": nombre, "anio": 2027, "fecha_inicio": "2027-01-01", "fecha_fin": "2027-12-31"},
            headers=mundo["admin"],
        )
    ).json()
    contenido = await _excel_de_sala(
        mundo["zona"]["nombre"],
        mundo["oficina"]["nombre"],
        [["CPU", "PC NUEVA", "CP-2001", "LENOVO", "LA NUEVA"]],
    )
    cuerpo = (
        await api.post(
            f"/api/campanas/{campana['id']}/excel",
            files={"archivo": ("sala.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=mundo["admin"],
        )
    ).json()
    nuevo = next(r for r in cuerpo["resultados"] if r["estado"] == "nuevo")
    await api.post(
        f"/api/campanas/{campana['id']}/excel/aceptar",
        json={"lote_id": cuerpo["lote_id"], "estados_aceptados": [nuevo["item_id"]]},
        headers=mundo["admin"],
    )
    cierre = await api.post(
        f"/api/campanas/{campana['id']}/cerrar", json={"confirmacion": True}, headers=mundo["admin"]
    )
    assert cierre.status_code == 200, cierre.text
    return campana


async def test_descargar_el_inventario_da_un_excel_por_zonas(db, api):
    """El archivo que sale tiene que ser el del municipio: una hoja por zona."""
    mundo = await _mundo(api, "descarga-inventario")
    for indice in range(3):
        await api.post(
            "/api/activos",
            json={
                "tipo": "CPU",
                "oficina_id": mundo["oficina"]["id"],
                "nombre_equipo": f"PC {indice}",
                "codigo_patrimonial": f"CP-{indice}",
                "marca": "LENOVO",
            },
            headers=mundo["admin"],
        )

    respuesta = await api.get("/api/activos/excel", headers=mundo["admin"])
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/vnd.openxmlformats"), respuesta.headers
    assert "attachment" in respuesta.headers.get("content-disposition", ""), respuesta.headers
    assert respuesta.headers.get("x-total-equipos") == "3", respuesta.headers

    hojas = _hojas(respuesta.content)
    assert len(hojas) == 1, f"una hoja por zona: {list(hojas)}"
    filas = next(iter(hojas.values()))
    assert filas[0][0] == "AREA", f"primera fila = encabezado de la plantilla: {filas[0]}"
    assert len(filas) == 4, f"encabezado + 3 equipos: {filas}"
    assert respuesta.content[:2] == b"PK", "no es un archivo de Excel"


async def test_descargar_respeta_los_filtros(db, api):
    """Lo que descargas es lo que estás viendo, no todo el inventario."""
    mundo = await _mundo(api, "descarga-filtro")
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC UNO", "codigo_patrimonial": "CP-1"},
        headers=mundo["admin"],
    )
    await api.post(
        "/api/activos",
        json={"tipo": "Impresora", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "IMPRESORA", "codigo_patrimonial": "CP-2"},
        headers=mundo["admin"],
    )

    solo_cpu = await api.get("/api/activos/excel?tipo=CPU", headers=mundo["admin"])
    assert solo_cpu.headers.get("x-total-equipos") == "1", solo_cpu.headers
    filas = next(iter(_hojas(solo_cpu.content).values()))
    assert len(filas) == 2, f"encabezado + 1 equipo: {filas}"
    assert "PC UNO" in filas[1], filas[1]
    assert not any("IMPRESORA" in str(celda) for fila in filas for celda in fila), "el filtro no se aplicó"

    buscada = await api.get("/api/activos/excel?texto=IMPRESORA", headers=mundo["admin"])
    assert buscada.headers.get("x-total-equipos") == "1", buscada.headers


async def test_se_puede_descargar_cada_anio_cerrado(db, api):
    """
    2026 y 2027, los dos descargables y cada uno con sus datos.

    El histórico guarda los datos completos de cada equipo, así que el archivo de 2027
    no es el inventario de hoy. Sin eso, descargar un año solo servía para ver el
    presente con otro nombre.
    """
    mundo = await _mundo(api, "descarga-anios")
    await api.post(
        "/api/activos",
        json={
            "tipo": "CPU",
            "oficina_id": mundo["oficina"]["id"],
            "nombre_equipo": "PC DE 2026",
            "codigo_patrimonial": "CP-2026",
            "marca": "MARCA-2026",
        },
        headers=mundo["admin"],
    )
    campana_2026 = await _campana_con_cierre(api, mundo, "Cierre 2026")

    # El equipo nuevo que se registró al cerrar 2026 se renombra: el archivo de 2026
    # tiene que seguir mostrando el nombre de 2026.
    nuevo_2026 = await db["activos"].find_one({"codigo_patrimonial": "CP-2001"})
    await db["activos"].update_one(
        {"_id": nuevo_2026["_id"]}, {"$set": {"nombre_equipo": "RENOMBRADO DESPUES", "marca": "MARCA-NUEVA"}}
    )

    versiones = (await api.get("/api/campanas/versiones/historico", headers=mundo["admin"])).json()["items"]
    version = next(v for v in versiones if v["anio"] == 2027)
    descarga = await api.get(f"/api/campanas/versiones/{version['id']}/excel", headers=mundo["admin"])
    assert descarga.status_code == 200, descarga.text
    assert "inventario-2027" in descarga.headers.get("content-disposition", ""), descarga.headers

    texto = _texto(descarga.content)
    assert "CP-2026" in texto, "el equipo ya registrado tiene que estar en el archivo del año"
    assert "MARCA-2026" in texto, "con los datos que tenía en aquel año"
    # El equipo nuevo se registró al cerrar: también entra en ese año.
    assert "CP-2001" in texto, "el equipo registrado al cerrar forma parte del año"
    # Y el nombre actual no debe estar, porque se renombró después.
    assert "RENOMBRADO DESPUES" not in texto, "el archivo de un año no puede traer el inventario de hoy"

    assert campana_2026["codigo"]


async def test_eliminar_una_campana_no_toca_el_inventario(db, api):
    """Borra la campaña y su lista. Los equipos del inventario se quedan."""
    mundo = await _mundo(api, "eliminar-campana")
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC UNO", "codigo_patrimonial": "CP-1"},
        headers=mundo["admin"],
    )
    campana = (
        await api.post(
            "/api/campanas",
            json={"nombre": "A eliminar", "anio": 2027, "fecha_inicio": "2027-01-01", "fecha_fin": "2027-12-31"},
            headers=mundo["admin"],
        )
    ).json()
    contenido = await _excel_de_sala(
        mundo["zona"]["nombre"], mundo["oficina"]["nombre"], [["CPU", "PC NUEVA", "CP-9", "DELL", "NUEVA"]]
    )
    await api.post(
        f"/api/campanas/{campana['id']}/excel",
        files={"archivo": ("sala.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=mundo["admin"],
    )
    equipos_antes = await db["activos"].count_documents({})

    borrada = await api.delete(f"/api/campanas/{campana['id']}", headers=mundo["admin"])
    assert borrada.status_code == 200, borrada.text
    assert borrada.json()["items_borrados"] > 0

    assert await db["campanas_inventario"].count_documents({"_id": ObjectId(campana["id"])}) == 0
    assert await db["campana_items"].count_documents({"campana_id": ObjectId(campana["id"])}) == 0
    assert await db["inventario_versiones"].count_documents({"campana_id": ObjectId(campana["id"])}) == 0
    # Lo importante: el inventario intacto.
    assert await db["activos"].count_documents({}) == equipos_antes
    assert await db["activos"].find_one({"codigo_patrimonial": "CP-1"}) is not None

    # Y no queda ninguna campaigns rota en la lista.
    listado = (await api.get("/api/campanas", headers=mundo["admin"])).json()["items"]
    assert campana["id"] not in {c["id"] for c in listado}


async def test_eliminar_una_campana_cerrada_deja_el_historico_coherente(db, api):
    """Una versión cerrada sin campaña es un año que se promete y no existe."""
    mundo = await _mundo(api, "eliminar-cerrada")
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC UNO"},
        headers=mundo["admin"],
    )
    campana = await _campana_con_cierre(api, mundo, "Cerrada a eliminar")
    versiones = (await api.get("/api/campanas/versiones/historico", headers=mundo["admin"])).json()["items"]
    assert versiones, "cerrar dejó una versión"

    await api.delete(f"/api/campanas/{campana['id']}", headers=mundo["admin"])
    assert (await api.get("/api/campanas/versiones/historico", headers=mundo["admin"])).json()["items"] == []
    # El equipo que se registró al cerrar sigue ahí: es inventario real.
    assert await db["activos"].find_one({"codigo_patrimonial": "CP-2001"}) is not None


async def test_un_filtro_mal_formado_no_rompe_la_pantalla(db, api):
    """
    Una URL con un id que no es un id no puede devolver un error.

    Los filtros vienen de la barra de direcciones: un marcador guardado de hace meses,
    una URL que alguien editó a mano, un enlace de Calidad con la zona equivocada. Con
    el id validado como si fuera uno de ruta, eso devolvía 422 y la pantalla se
    quedaba a medias con dos peticiones fallidas en la consola y sin explicar nada.
    Un filtro que no se puede aplicar se ignora.
    """
    mundo = await _mundo(api, "filtro-roto")
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC UNO"},
        headers=mundo["admin"],
    )

    for consulta in ("?zona_id=x", "?oficina_id=esto-no-es-un-id", "?responsable_id=%%%"):
        activos = await api.get(f"/api/activos{consulta}", headers=mundo["admin"])
        assert activos.status_code == 200, f"{consulta} -> {activos.status_code} {activos.text}"
        assert activos.json()["total"] == 1, f"{consulta} devolvió {activos.json()['total']}"

        oficinas = await api.get(f"/api/oficinas{consulta}", headers=mundo["admin"])
        assert oficinas.status_code == 200, f"oficinas{consulta} -> {oficinas.status_code}"

    # Un id bien formado que no existe sí filtra a cero: eso no es un error, es un filtro
    # que no deja pasar nada.
    inexistente = await api.get("/api/activos?zona_id=6ac677f89ca7274353749999", headers=mundo["admin"])
    assert inexistente.status_code == 200, inexistente.text
    assert inexistente.json()["total"] == 0


async def test_eliminar_una_campana_inexistente_dice_que_no_existe(db, api):
    mundo = await _mundo(api, "eliminar-inexistente")
    respuesta = await api.delete("/api/campanas/6ac677f89ca7274353740000", headers=mundo["admin"])
    assert respuesta.status_code == 404, respuesta.text