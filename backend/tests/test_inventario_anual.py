"""Inventario anual: el recorrido que faltaba, de principio a fin.

Detectar un equipo **nuevo** con el Excel del año, aceptarlo y comprobar que al
cerrar la campaña aparece en el inventario. Antes el equipo se perdía: al
aceptarlo se saltaba en silencio y al cerrar no se creaba.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from bson import ObjectId

from tests.test_tickets_horarios import _mundo


async def _excel_de_sala(zona_nombre: str, oficina_nombre: str, filas: list[list[str]]) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = zona_nombre.upper()
    hoja.append(["AREA", "Tipo de equipo", "Dispositivo", "Código patrimonial", "Marca", "Nombre"])
    for fila in filas:
        hoja.append([oficina_nombre, *fila])
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


async def test_un_equipo_nuevo_se_detecta_se_acepta_y_se_registra(db, api):
    mundo = await _mundo(api, "anual-nuevo")
    zona_nombre = mundo["zona"]["nombre"]
    oficina_nombre = mundo["oficina"]["nombre"]
    oficina_id = mundo["oficina"]["id"]

    # Un equipo ya registrado: sirve de referencia para el «ausente».
    creado = await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": oficina_id, "nombre_equipo": "PC ANTIGUA", "codigo_patrimonial": "CP-0001"},
        headers=mundo["admin"],
    )
    assert creado.status_code == 201, creado.text
    total_antes = await db["activos"].count_documents({})

    campana = await api.post(
        "/api/campanas",
        json={
            "nombre": "Verificacion 2027",
            "anio": 2027,
            "fecha_inicio": "2027-01-01",
            "fecha_fin": "2027-12-31",
        },
        headers=mundo["admin"],
    )
    assert campana.status_code == 201, campana.text
    campana = campana.json()
    # Nace vacía: su contenido llega con el Excel de la sala.
    assert campana["total_items"] == 0, campana
    assert campana["total_previsto"] == 1, "sí sabe que hay un equipo registrado en el alcance"

    contenido = await _excel_de_sala(
        zona_nombre,
        oficina_nombre,
        [["CPU", "PC NUEVA", "CP-9999", "LENOVO", "PC DE LA SALA NUEVA"]],
    )
    comparacion = await api.post(
        f"/api/campanas/{campana['id']}/excel",
        files={"archivo": ("nuevo.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=mundo["admin"],
    )
    assert comparacion.status_code == 200, comparacion.text
    cuerpo = comparacion.json()
    assert cuerpo["resumen"]["nuevos"] == 1, cuerpo["resultados"]
    assert cuerpo["resumen"]["ausentes"] == 1, "el conocido no aparece en el archivo nuevo"

    nuevo = next(r for r in cuerpo["resultados"] if r["estado"] == "nuevo")
    assert nuevo["item_id"], "el equipo nuevo tiene que quedar guardado como item para poder aceptarlo"

    items = (await api.get(f"/api/campanas/{campana['id']}/items", headers=mundo["admin"])).json()
    item_nuevo = next(i for i in items["items"] if i["id"] == nuevo["item_id"])
    assert item_nuevo["estado_item"] == "pendiente", "nace pendiente: no se crea nada hasta cerrarlo"
    assert await db["activos"].count_documents({}) == total_antes, "subir el Excel no crea equipos"
    # El equipo ausente también es un item, pendiente de verificar a mano: se
    # reporta y no se borra nunca.
    assert items["total"] == 2, items
    assert {i["estado_item"] for i in items["items"]} == {"pendiente"}, items

    aceptado = await api.post(
        f"/api/campanas/{campana['id']}/excel/aceptar",
        json={"lote_id": cuerpo["lote_id"], "estados_aceptados": [nuevo["item_id"]]},
        headers=mundo["admin"],
    )
    assert aceptado.status_code == 200, aceptado.text
    assert aceptado.json()["nuevos_creados"] == 1, aceptado.json()
    assert await db["activos"].count_documents({}) == total_antes, "aceptar marca; todavía no crea"

    cierre = await api.post(
        f"/api/campanas/{campana['id']}/cerrar",
        json={"nota": "Alta 2027", "confirmacion": True, "marcar_no_localizados": True},
        headers=mundo["admin"],
    )
    assert cierre.status_code == 200, cierre.text
    resultado = cierre.json()
    assert resultado["nuevos_registrados"] == 1, resultado
    assert resultado["nuevos_fallidos"] == [], resultado

    assert await db["activos"].count_documents({}) == total_antes + 1
    nuevo_activo = await db["activos"].find_one({"codigo_patrimonial": "CP-9999"})
    assert nuevo_activo is not None, "el equipo nuevo tiene que quedar en el inventario"
    assert str(nuevo_activo["oficina_id"]) == oficina_id, "tiene que quedar en la oficina de la hoja"
    assert nuevo_activo["nombre_equipo"] == "PC DE LA SALA NUEVA"
    assert nuevo_activo["marca"] == "LENOVO"
    # El tipo sale de la columna «Tipo de equipo» (CPU), no de «Dispositivo»
    # (PC NUEVA DE LA SALA), que es una descripción y no un tipo de equipo.
    assert nuevo_activo["tipo"] == "CPU", f"el tipo quedó como: {nuevo_activo['tipo']}"

    historico = (await api.get("/api/campanas/versiones/historico", headers=mundo["admin"])).json()
    version = next(v for v in historico["items"] if v["campana_id"] == campana["id"])
    assert version["nuevos_registrados"] == 1, version
    guardada = await db['inventario_versiones'].find_one({'_id': ObjectId(version['id'])})
    assert all(i.get('activo_id') for i in guardada['instantanea'])
    assert any(str(i['activo_id']) == str(nuevo_activo['_id']) for i in guardada['instantanea'])
    assert (await api.post(f"/api/campanas/{campana['id']}/items/{nuevo['item_id']}", json={'estado_item': 'pendiente'}, headers=mundo['admin'])).status_code == 403
    assert (await api.post(f"/api/campanas/{campana['id']}/excel/aceptar", json={'lote_id': cuerpo['lote_id'], 'estados_aceptados': [nuevo['item_id']]}, headers=mundo['admin'])).status_code == 403


async def test_historial_no_aplica_cambios_pendientes_y_valida_fechas(db, api):
    mundo = await _mundo(api, 'anual-pendiente')
    cab = mundo['admin']
    equipo = (await api.post('/api/activos', headers=cab, json={'tipo': 'CPU', 'oficina_id': mundo['oficina']['id'], 'nombre_equipo': 'PC ORIGINAL', 'codigo_patrimonial': 'HIS-001', 'marca': 'LENOVO'})).json()
    datos = {'nombre': 'Revision historica', 'anio': 2027, 'fecha_inicio': '2027-01-01', 'fecha_fin': '2027-12-31'}
    assert (await api.post('/api/campanas', headers=cab, json={**datos, 'anio': 2028})).status_code == 422
    campana = (await api.post('/api/campanas', headers=cab, json=datos)).json()
    assert (await api.patch(f"/api/campanas/{campana['id']}", headers=cab, json={'fecha_fin': '2026-01-01'})).status_code == 422
    assert (await api.post('/api/campanas/previa', headers=cab, json={'alcance': 'invalido'})).status_code == 422
    archivo = await _excel_de_sala(mundo['zona']['nombre'], mundo['oficina']['nombre'], [['CPU', 'CPU', 'HIS-001', 'DELL', 'PC ORIGINAL']])
    comparado = await api.post(f"/api/campanas/{campana['id']}/excel", headers=cab, files={'archivo': ('sala.xlsx', archivo)})
    assert comparado.status_code == 200, comparado.text
    item = (await api.get(f"/api/campanas/{campana['id']}/items", headers=cab)).json()['items'][0]
    assert (await api.post(f"/api/campanas/{campana['id']}/items/{item['id']}", headers=cab, json={})).status_code == 422
    cierre = await api.post(f"/api/campanas/{campana['id']}/cerrar", headers=cab, json={'confirmacion': True})
    assert cierre.status_code == 200, cierre.text
    version = await db['inventario_versiones'].find_one({'campana_id': ObjectId(campana['id'])})
    assert version['instantanea'][0]['campos']['marca'] == 'LENOVO'
    assert (await db['activos'].find_one({'_id': ObjectId(equipo['id'])}))['marca'] == 'LENOVO'


async def test_alcance_archivos_invalidos_y_paginacion_completa(db, api):
    mundo = await _mundo(api, 'anual-alcance')
    cab = mundo['admin']
    campana = (await api.post('/api/campanas', headers=cab, json={'nombre': 'Revision de alcance', 'anio': 2027, 'fecha_inicio': '2027-01-01', 'fecha_fin': '2027-12-31', 'alcance': 'zonas', 'zona_ids': [mundo['zona']['id']]})).json()
    url = f"/api/campanas/{campana['id']}"
    fuera = await _excel_de_sala('OTRA ZONA', 'COMUNA', [['CPU', 'PC', 'FUERA-1', 'DELL', 'PC FUERA']])
    assert (await api.post(f'{url}/excel', headers=cab, files={'archivo': ('fuera.xlsx', fuera)})).status_code == 422
    assert (await api.get(f'{url}/items', headers=cab)).json()['total'] == 0
    assert (await api.post(f'{url}/excel', headers=cab, files={'archivo': ('roto.xlsx', b'no es un excel')})).status_code == 422
    vacio = await _excel_de_sala(mundo['zona']['nombre'], 'COMUNA', [])
    assert (await api.post(f'{url}/excel', headers=cab, files={'archivo': ('vacio.xlsx', vacio)})).status_code == 422
    libro = await _excel_de_sala(mundo['zona']['nombre'], 'COMUNA', [['CPU', 'PC', f'PAG-{i:02}', 'DELL', f'PC {i:02}'] for i in range(30)])
    resultado = await api.post(f'{url}/excel', headers=cab, files={'archivo': ('sala.xlsx', libro)})
    assert resultado.status_code == 200, resultado.text
    pagina_uno = (await api.get(f'{url}/items?pagina=1&por_pagina=25', headers=cab)).json()
    pagina_dos = (await api.get(f'{url}/items?pagina=2&por_pagina=25', headers=cab)).json()
    assert len(pagina_uno['items']) == 25 and len(pagina_dos['items']) == 5
    assert len({i['id'] for i in pagina_uno['items'] + pagina_dos['items']}) == 30
    assert (await api.get(f'{url}/items', headers=cab, params={'texto': '['})).status_code == 200


async def test_una_campana_en_verificacion_sigue_admiendo_equipos_nuevos(db, api):
    """
    Marcar un equipo no puede cerrar la campaña.

    El backend cambia la campaña a `verificacion` **sola** en cuanto se marca el
    primer equipo. La pantalla-era cualquier estado que no fuera `abierta`, así que
    a partir del primer equipo marcado la campaña se volvía inservible: sin
    botones para verificar el resto, sin poder subir el Excel de la sala y sin
    poder cerrar. Con `verificacion` no se bloquea nada, así que tampoco puede
    rechazarse la subida.
    """
    mundo = await _mundo(api, "anual-verificacion")
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC UNO", "codigo_patrimonial": "CP-0001"},
        headers=mundo["admin"],
    )
    campana = (
        await api.post(
            "/api/campanas",
            json={"nombre": "En verificacion", "anio": 2027, "fecha_inicio": "2027-01-01", "fecha_fin": "2027-12-31"},
            headers=mundo["admin"],
        )
    ).json()

    vacia = (await api.get(f"/api/campanas/{campana['id']}/items", headers=mundo["admin"])).json()
    assert vacia["total"] == 0, "la campaña nace vacía: aún no se ha subido ningún Excel"

    # Primera subida: el equipo registrado aparece en el archivo y el nuevo no.
    contenido = await _excel_de_sala(
        mundo["zona"]["nombre"],
        mundo["oficina"]["nombre"],
        [
            ["CPU", "PC UNO", "CP-0001", "LENOVO", "EN LA OFICINA"],
            ["CPU", "PC NUEVA", "CP-5001", "DELL", "APARECIDA"],
        ],
    )
    primera = await api.post(
        f"/api/campanas/{campana['id']}/excel",
        files={"archivo": ("sala.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=mundo["admin"],
    )
    assert primera.status_code == 200, primera.text
    assert primera.json()["resumen"]["nuevos"] == 1, primera.json()["resumen"]

    items = (await api.get(f"/api/campanas/{campana['id']}/items", headers=mundo["admin"])).json()
    assert items["total"] == 2, items
    registrado = next(i for i in items['items'] if i.get('activo_id'))
    marcado = await api.post(
        f"/api/campanas/{campana['id']}/items/{registrado['id']}",
        json={"estado_item": "confirmado", "observaciones": "Esta en la oficina"},
        headers=mundo["admin"],
    )
    assert marcado.status_code == 200, marcado.text

    # El backend ya no la llama «abierta».
    despues = (await api.get(f"/api/campanas/{campana['id']}", headers=mundo["admin"])).json()
    assert despues["estado"] == "verificacion", despues
    assert despues["resumen"]["verificados"] == 1, despues["resumen"]

    # Y aun así se puede seguir verificando y volver a subir el Excel.
    segunda = await api.post(
        f"/api/campanas/{campana['id']}/excel",
        files={"archivo": ("sala.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=mundo["admin"],
    )
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["resumen"]["nuevos"] == 1, segunda.json()["resumen"]

    cuerpo = segunda.json()
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
    assert cierre.json()["nuevos_registrados"] == 1, cierre.json()


async def test_varios_equipos_nuevos_a_la_vez_no_reventan(db, api):
    """
    Dos equipos nuevos en el mismo archivo, no uno.

    El índice único de `(campana_id, activo_id)` trataba `null` como un valor, así
    que todos los items sin equipo compartían clave y **el segundo equipo nuevo
    reventaba la subida entera** con «duplicate key». La primera prueba de este
    archivo tenía un solo nuevo y pasaba de largo: el fallo solo aparece con dos.
    """
    mundo = await _mundo(api, "anual-varios")
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC ANTIGUA", "codigo_patrimonial": "CP-0001"},
        headers=mundo["admin"],
    )
    campana = (
        await api.post(
            "/api/campanas",
            json={"nombre": "Varios nuevos", "anio": 2027, "fecha_inicio": "2027-01-01", "fecha_fin": "2027-12-31"},
            headers=mundo["admin"],
        )
    ).json()

    contenido = await _excel_de_sala(
        mundo["zona"]["nombre"],
        mundo["oficina"]["nombre"],
        [
            ["CPU", "PC NUEVA UNO", "CP-7001", "LENOVO", "PRIMERA"],
            ["Impresora", "IMPRESORA NUEVA", "CP-7002", "HP", "SEGUNDA"],
            ["Laptop", "LAPTOP NUEVA", "CP-7003", "DELL", "TERCERA"],
        ],
    )
    comparacion = await api.post(
        f"/api/campanas/{campana['id']}/excel",
        files={"archivo": ("nuevo.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=mundo["admin"],
    )
    assert comparacion.status_code == 200, comparacion.text
    cuerpo = comparacion.json()
    assert cuerpo["resumen"]["nuevos"] == 3, cuerpo["resultados"]
    ids = {r["item_id"] for r in cuerpo["resultados"] if r["estado"] == "nuevo"}
    assert len(ids) == 3 and all(ids), "los tres nuevos tienen que quedar guardados con id propio"

    # Y los tres se registran de una vez al cerrar.
    aceptado = await api.post(
        f"/api/campanas/{campana['id']}/excel/aceptar",
        json={"lote_id": cuerpo["lote_id"], "estados_aceptados": sorted(ids)},
        headers=mundo["admin"],
    )
    assert aceptado.json()["nuevos_creados"] == 3, aceptado.json()
    cierre = await api.post(
        f"/api/campanas/{campana['id']}/cerrar", json={"confirmacion": True}, headers=mundo["admin"]
    )
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["nuevos_registrados"] == 3, cierre.json()
    for codigo in ("CP-7001", "CP-7002", "CP-7003"):
        assert await db["activos"].find_one({"codigo_patrimonial": codigo}), f"{codigo} no quedó registrado"


async def test_recargar_el_mismo_archivo_da_el_mismo_resultado(db, api):
    """
    Subir dos veces el mismo Excel no puede cambiar el resultado.

    El equipo nuevo queda guardado como item de la campaña, así que la segunda
    subida lo emparejaba y lo comparaba contra una instantánea vacía: salía como
    «con cambios». En pantalla decía que un equipo registrado había cambiado de
    datos, siendo que no está registrado. La primera subida es la que dice la
    verdad, y recargar tiene que decir lo mismo.
    """
    mundo = await _mundo(api, "anual-recarga")
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC ANTIGUA", "codigo_patrimonial": "CP-0001"},
        headers=mundo["admin"],
    )
    campana = (
        await api.post(
            "/api/campanas",
            json={"nombre": "Recarga", "anio": 2027, "fecha_inicio": "2027-01-01", "fecha_fin": "2027-12-31"},
            headers=mundo["admin"],
        )
    ).json()

    contenido = await _excel_de_sala(
        mundo["zona"]["nombre"],
        mundo["oficina"]["nombre"],
        [["CPU", "PC NUEVA", "CP-6001", "LENOVO", "DE LA SALA"]],
    )
    archivo = {"archivo": ("nuevo.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

    primera = (await api.post(f"/api/campanas/{campana['id']}/excel", files=archivo, headers=mundo["admin"])).json()
    segunda = (await api.post(f"/api/campanas/{campana['id']}/excel", files=archivo, headers=mundo["admin"])).json()

    assert primera["resumen"]["nuevos"] == 1, primera["resumen"]
    assert segunda["resumen"] == primera["resumen"], (
        f"la segunda subida dio otro resultado: {segunda['resumen']} frente a {primera['resumen']}"
    )
    # Los datos del resumen se refrescan con el archivo: el tipo sale de «Tipo de
    # equipo» (CPU), no de «Dispositivo» (PC NUEVA), que es una descripción.
    nuevo = next(r for r in segunda["resultados"] if r["estado"] == "nuevo")
    assert nuevo["activo_tipo"] == "CPU", nuevo
    assert nuevo["activo_codigo"] == "CP-6001", nuevo

    # Marcarlo **no** lo convierte en verificado. Está en el Excel, no en una sala:
    # nadie ha ido a buscarlo. Antes «verificados» era «todo lo que no estaba
    # pendiente», así que marcarlo ponía «Verificados 1» y 100 % de progreso sin
    # que nadie hubiera mirado nada.
    await api.post(
        f"/api/campanas/{campana['id']}/excel/aceptar",
        json={"lote_id": segunda["lote_id"], "estados_aceptados": [nuevo["item_id"]]},
        headers=mundo["admin"],
    )
    resumen = (await api.get(f"/api/campanas/{campana['id']}", headers=mundo["admin"])).json()["resumen"]
    assert resumen["nuevos_aceptados"] == 1, resumen
    assert resumen["verificados"] == 0, f"un equipo nuevo no está verificado: {resumen}"
    assert resumen["progreso"] == 0.0, resumen
    assert resumen["total_registrados"] == 1, "sigue habiendo un solo equipo registrado"
    assert resumen["por_verificar"] == 1, "el equipo registrado sigue sin verificar"

    # Y no se duplica el equipo nuevo: sigue siendo uno.
    assert (
        await db["campana_items"].count_documents(
            {"campana_id": ObjectId(campana["id"]), "origen": "excel_nuevo"}
        )
        == 1
    )


async def test_rechazar_un_equipo_nuevo_no_lo_registra(db, api):
    """Rechazar es no crear. Un equipo que no quieres añadir, no se añade."""
    mundo = await _mundo(api, "anual-rechazar")
    # La campaña exige que el alcance tenga algún equipo; se crea uno para poder
    # llegar a la fase de comparación.
    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC DE REFERENCIA"},
        headers=mundo["admin"],
    )
    campana = await api.post(
        "/api/campanas",
        json={
            "nombre": "Campana Rechazar",
            "anio": 2027,
            "fecha_inicio": "2027-01-01",
            "fecha_fin": "2027-12-31",
            "zona_ids": [mundo["zona"]["id"]],
            "alcance": "zonas",
        },
        headers=mundo["admin"],
    )
    assert campana.status_code == 201, campana.text
    campana = campana.json()
    total_antes = await db["activos"].count_documents({})

    contenido = await _excel_de_sala(
        mundo["zona"]["nombre"],
        mundo["oficina"]["nombre"],
        [["CPU", "PC QUE NO QUIERO", "CP-8888", "DELL", "NO ME SIRVE"]],
    )
    cuerpo = (
        await api.post(
            f"/api/campanas/{campana['id']}/excel",
            files={"archivo": ("nuevo.xlsx", contenido, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=mundo["admin"],
        )
    ).json()
    nuevo = next(r for r in cuerpo["resultados"] if r["estado"] == "nuevo")

    await api.post(
        f"/api/campanas/{campana['id']}/excel/aceptar",
        json={"lote_id": cuerpo["lote_id"], "estados_rechazados": [nuevo["item_id"]]},
        headers=mundo["admin"],
    )
    # Rechazar deja el equipo en la lista como pendiente de verificar a mano: no
    # se borra, simplemente no se registra solo.
    tras_rechazar = (await api.get(f"/api/campanas/{campana['id']}/items", headers=mundo["admin"])).json()
    item = next(i for i in tras_rechazar["items"] if i["id"] == nuevo["item_id"])
    assert item["estado_item"] == "pendiente", item

    cierre = await api.post(
        f"/api/campanas/{campana['id']}/cerrar",
        json={"confirmacion": True},
        headers=mundo["admin"],
    )
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["nuevos_registrados"] == 0
    assert await db["activos"].count_documents({}) == total_antes, "rechazado no se crea"
    assert await db["activos"].count_documents({"codigo_patrimonial": "CP-8888"}) == 0
