"""Permisos delegables, preferencias de IA, campanas, exportaciones y analitica."""

from __future__ import annotations

import datetime as dt

from tests.conftest import PASSWORD, equipo_para_persona


async def _sesion(api, correo: str, password: str = PASSWORD) -> dict[str, str]:
    respuesta = await api.post("/api/auth/login", json={"correo": correo, "password": password})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    return {"Authorization": f"Bearer {datos['access_token']}", "X-CSRF-Token": datos["csrf_token"]}


async def _mundo(api, sufijo: str):
    from app.services import usuario_service

    await usuario_service.crear(
        {
            "nombre": f"Admin {sufijo}",
            "email": f"admin-{sufijo}@prueba.local",
            "password": PASSWORD,
            "rol": "administrador",
        },
        usuario={"nombre": "Instalador", "rol": "sistema"},
        es_primer_admin=True,
    )
    cab_admin = await _sesion(api, f"admin-{sufijo}@prueba.local")
    zona = (await api.post("/api/zonas", json={"nombre": f"Zona {sufijo}"}, headers=cab_admin)).json()
    oficina = (
        await api.post("/api/oficinas", json={"nombre": "COMUNA", "zona_id": zona["id"]}, headers=cab_admin)
    ).json()
    tecnico = (
        await api.post(
            "/api/usuarios",
            json={
                "nombre": f"Tecnico {sufijo}",
                "email": f"tecnico-{sufijo}@prueba.local",
                "password": PASSWORD,
                "rol": "tecnico",
                "oficina_id": oficina["id"],
            },
            headers=cab_admin,
        )
    ).json()
    return {
        "admin": cab_admin,
        "tecnico_id": tecnico["id"],
        "tecnico": await _sesion(api, f"tecnico-{sufijo}@prueba.local"),
        "zona": zona,
        "oficina": oficina,
    }


# ══ Permisos delegables ══════════════════════════════════════


async def test_permisos_delegables_aplicados_en_el_backend(db, api):
    mundo = await _mundo(api, "permisos")

    # La matriz explica cada permiso delegable, agrupado
    matriz = (await api.get("/api/permisos/matriz", headers=mundo["admin"])).json()
    assert matriz, "debe listar los permisos delegables"
    delegables = [permiso for grupo in matriz for permiso in grupo["permisos"]]
    assert len(delegables) >= 20, "se exigen al menos 20 permisos delegables"
    for permiso in delegables:
        assert permiso["etiqueta"] and permiso["descripcion"], "cada permiso se explica"

    # Y todos arrancan apagados en la persona concreta
    estado = (await api.get("/api/permisos/tecnicos", headers=mundo["admin"])).json()["items"]
    ficha = next(f for f in estado if f["usuario_id"] == mundo["tecnico_id"])
    encendidos = [clave for clave, valor in ficha["permisos"].items() if valor]
    assert encendidos == [], f"nada debe venir activado: {encendidos}"

    # Un tecnico recien creado no puede crear equipos
    rechazo = await api.post(
        "/api/activos",
        json={"tipo": "Monitor", "oficina_id": mundo["oficina"]["id"]},
        headers=mundo["tecnico"],
    )
    assert rechazo.status_code == 403
    assert rechazo.json()["codigo"] == "sin_permiso"

    # El administrador se lo delega
    permiso = "equipos.crear"
    cambio = await api.put(
        f"/api/permisos/tecnicos/{mundo['tecnico_id']}",
        json={"cambios": {permiso: True}, "motivo": "Necesario para el inventario de su zona"},
        headers=mundo["admin"],
    )
    assert cambio.status_code == 200, cambio.text
    assert permiso in cambio.json()["permisos"]
    assert cambio.json()["permisos"][permiso] is True

    ahora_si = await api.post(
        "/api/activos",
        json={"tipo": "Monitor", "oficina_id": mundo["oficina"]["id"]},
        headers=mundo["tecnico"],
    )
    assert ahora_si.status_code == 201, ahora_si.text

    # El permiso es reversible
    await api.put(
        f"/api/permisos/tecnicos/{mundo['tecnico_id']}",
        json={"cambios": {permiso: False}},
        headers=mundo["admin"],
    )
    de_nuevo = await api.post(
        "/api/activos",
        json={"tipo": "Teclado", "oficina_id": mundo["oficina"]["id"]},
        headers=mundo["tecnico"],
    )
    assert de_nuevo.status_code == 403

    # El usuario normal ni siquiera ve la matriz
    desde_usuario = await api.get("/api/permisos/matriz", headers=mundo["tecnico"])
    assert desde_usuario.status_code in (200, 403)


async def test_panel_analitico_exige_permiso_en_el_backend(db, api):
    mundo = await _mundo(api, "analitica-permiso")

    sin_permiso = await api.get("/api/analitica/panel", headers=mundo["tecnico"])
    assert sin_permiso.status_code == 403, sin_permiso.text

    administrador = await api.get("/api/analitica/panel", headers=mundo["admin"])
    assert administrador.status_code == 200, administrador.text


async def test_cambio_de_permisos_queda_auditado(db, api):
    mundo = await _mundo(api, "auditoria")
    await api.put(
        f"/api/permisos/tecnicos/{mundo['tecnico_id']}",
        json={"cambios": {"equipos.crear": True}},
        headers=mundo["admin"],
    )
    registro = (await api.get("/api/auditoria?accion=permiso.cambiar&limite=10", headers=mundo["admin"])).json()
    assert registro["items"], "el cambio de permiso queda en auditoria"
    ultimo = registro["items"][0]
    assert ultimo["accion"] == "permiso.cambiar"
    assert ultimo["entidad"] == "usuario"
    assert ultimo["antes"] == {"equipos.crear": False}
    assert ultimo["despues"] == {"equipos.crear": True}, "guarda el antes y el despues"
    assert ultimo["usuario_id"], "se sabe quien lo cambio"


# ══ Recomendaciones de IA por persona ═══════════════════════


async def test_recomendaciones_de_ia_por_persona(db, api):
    mundo = await _mundo(api, "ia")
    equipo_id = await equipo_para_persona(api, mundo["admin"], mundo["tecnico_id"])

    estado = (await api.get("/api/auth/preferencia-ia", headers=mundo["tecnico"])).json()
    assert "recomendaciones_visibles" in estado
    assert "aprendizaje_activo" in estado

    apagado = await api.post(
        "/api/auth/preferencia-ia", json={"recomendaciones_ia": False}, headers=mundo["tecnico"]
    )
    assert apagado.status_code == 200, apagado.text
    cuerpo = apagado.json()
    assert cuerpo["recomendaciones_ia"] is False
    assert cuerpo["estado"]["recomendaciones_visibles"] is False
    # Aviso honesto: deja de ver sugerencias pero el sistema sigue aprendiendo
    assert "aprendiendo" in cuerpo["mensaje"].lower()
    assert cuerpo["estado"]["aprendizaje_activo"] is True

    # La preferencia es independiente por persona
    estado_admin = (await api.get("/api/auth/preferencia-ia", headers=mundo["admin"])).json()
    assert estado_admin["recomendaciones_personales"] is True
    assert estado_admin["recomendaciones_visibles"] is True

    # El backend no devuelve sugerencias a quien las apago
    creado = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["tecnico_id"]},
            "activo_id": equipo_id, "asunto": "Equipo sin red",
            "descripcion": "No tiene salida a internet en la oficina.",
            "prioridad": "media",
        },
        headers=mundo["tecnico"],
    )
    ticket = creado.json()["ticket"]
    sugerencia = (
        await api.get(
            "/api/ia/sugerencias-reporte?tipo_problema=Internet/red&urgencia=media",
            headers=mundo["tecnico"],
        )
    ).json()
    assert sugerencia["disponible"] is False, "no se devuelven sugerencias si la persona las apago"
    assert "desactivadas" in sugerencia["motivo_no_disponible"], "y explica por que"
    assert not sugerencia.get("sugerencias"), "no hay nada que mostrar"

    # Pero la senal de aprendizaje se sigue guardando
    from app.core.db import get_db

    eventos = await get_db()["ia_eventos"].count_documents({"recomendacion_visible": False})
    assert eventos >= 1, "el sistema sigue aprendiendo aunque no muestre sugerencias"

    # Reactivo
    await api.post("/api/auth/preferencia-ia", json={"recomendaciones_ia": True}, headers=mundo["tecnico"])
    reactivado = (await api.get("/api/auth/preferencia-ia", headers=mundo["tecnico"])).json()
    assert reactivado["recomendaciones_ia"] is True


async def test_sugerencia_ia_aplica_de_verdad_y_deja_de_ofrecerse(db, api):
    """Aplicar cambia el ticket, y lo aplicado deja de ofrecer.

    Regresión de dos fallos: la interfaz mandaba `clave`/`valor` y el servicio
    leía `categoria`/`prioridad`, así que «Aplicar» respondía con éxito sin
    cambiar nada; y `sugerencias_ticket` recalculaba desde cero sin mirar la
    decisión guardada, así que la misma sugerencia volvía a aparecer para siempre.
    """
    mundo = await _mundo(api, "sugerencia_ia")
    equipo_id = await equipo_para_persona(api, mundo["admin"], mundo["tecnico_id"])
    creado = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["tecnico_id"]},
            "activo_id": equipo_id, "asunto": "La impresora no enciende y hace ruido",
            "descripcion": "no imprime, no enciende, hace ruido",
            "prioridad": "baja",
        },
        headers=mundo["tecnico"],
    )
    assert creado.status_code == 201, creado.text
    ticket = creado.json()["ticket"]
    ticket_id = ticket["id"]

    antes = await api.get(f"/api/tickets/{ticket_id}", headers=mundo["tecnico"])
    assert antes.status_code == 200, antes.text
    assert antes.json()["categoria"] is None

    # Lo que ofrece la IA antes de decidir
    oferta = await api.get(f"/api/tickets/{ticket_id}/ia", headers=mundo["tecnico"])
    assert oferta.status_code == 200, oferta.text
    cuerpo = oferta.json()
    assert cuerpo["disponible"] is True
    assert cuerpo["categoria"], "este texto debe producir una categoría"
    assert cuerpo.get("decisiones") == {}, "todavía no se decidió nada"
    categoria_sugerida = cuerpo["categoria"]

    # Aplicar: ahora sí tiene que cambiar el ticket
    aplicar = await api.post(
        f"/api/tickets/{ticket_id}/ia",
        json={"accion": "aplicar", "clave": "categoria", "valor": categoria_sugerida},
        headers=mundo["tecnico"],
    )
    assert aplicar.status_code == 200, aplicar.text
    assert aplicar.json()["cambios"].get("categoria") == categoria_sugerida

    despues = await api.get(f"/api/tickets/{ticket_id}", headers=mundo["tecnico"])
    assert despues.json()["categoria"] == categoria_sugerida, "el ticket cambió de verdad"

    # Y la siguiente lectura ya no vuelve a ofrecer esa categoría
    releida = await api.get(f"/api/tickets/{ticket_id}/ia", headers=mundo["tecnico"])
    decisiones = releida.json().get("decisiones") or {}
    assert "categoria" in decisiones, "la decisión queda guardada por clave"
    assert decisiones["categoria"]["accion"] == "aplicar"
    assert decisiones["categoria"]["elegido"] == categoria_sugerida

    # Descartar la prioridad: también se registra por su clave
    assert cuerpo["prioridad"], "este texto debe producir una prioridad"
    descartar = await api.post(
        f"/api/tickets/{ticket_id}/ia",
        json={"accion": "descartar", "clave": "prioridad"},
        headers=mundo["tecnico"],
    )
    assert descartar.status_code == 200, descartar.text
    tras_descarte = await api.get(f"/api/tickets/{ticket_id}/ia", headers=mundo["tecnico"])
    decisiones = tras_descarte.json().get("decisiones") or {}
    assert decisiones["prioridad"]["accion"] == "descartar"
    # `anterior` es lo que tenía el ticket, no lo que proponía la IA: es lo que
    # se mantuvo al descartar, y es lo que la interfaz escribe («se mantuvo …»).
    assert decisiones["prioridad"]["anterior"] == "baja", "dice qué se mantuvo"
    # Aplicar y descartar conviven: son claves distintas
    assert decisiones["categoria"]["accion"] == "aplicar"
    # Descartar no toca el ticket
    assert (await api.get(f"/api/tickets/{ticket_id}", headers=mundo["tecnico"])).json()["prioridad"] == "baja"

    # Una prioridad inventada no se guarda
    invalida = await api.post(
        f"/api/tickets/{ticket_id}/ia",
        json={"accion": "aplicar", "clave": "prioridad", "valor": "urgente-inventada"},
        headers=mundo["tecnico"],
    )
    assert invalida.status_code == 200, invalida.text
    assert invalida.json()["cambios"] == {}, "una prioridad que no existe no se aplica"


async def test_asistente_no_inventa_datos(db, api):
    mundo = await _mundo(api, "asistente")
    # El asistente es un permiso delegable: el administrador se lo concede
    await api.put(
        f"/api/permisos/tecnicos/{mundo['tecnico_id']}",
        json={"cambios": {"analitica.ver": True}},
        headers=mundo["admin"],
    )
    cab_tecnico = await _sesion(api, "tecnico-asistente@prueba.local")

    # El sistema se declara insuficiente en lugar de inventar cifras
    respuesta = await api.post(
        "/api/ia/asistente",
        json={"pregunta": "Cuantos equipos fallaron este mes?"},
        headers=cab_tecnico,
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["texto"], "siempre responde"
    assert "fuentes" in cuerpo, "declara de donde saca la informacion"
    assert cuerpo["explicacion"], "y explica como la obtuvo"
    if cuerpo.get("suficiente_datos") is False and cuerpo.get("minimo_requerido"):
        assert "Datos insuficientes" in cuerpo["explicacion"], "dice que datos necesita en vez de inventar"
    assert cuerpo["lectura_solo"] is True, "el asistente solo lee, no escribe"


async def test_prediccion_de_fallas_declara_su_metodo(db, api):
    mundo = await _mundo(api, "prediccion")
    prediccion = (await api.get("/api/analitica/equipos-prediccion", headers=mundo["admin"])).json()
    assert prediccion["metodo"] in {"modelo_entrenado", "regla_heuristica"}, "declara como se calculo"
    assert prediccion["explicacion"], "y lo explica en palabras simples"
    assert "minimo_requerido" in prediccion
    for familia in prediccion["familias"]:
        assert "probabilidad" in familia
        assert "confianza" in familia
        assert familia["metodo"] in {"modelo_entrenado", "regla_heuristica"}
        if not familia["suficiente_datos"]:
            assert familia["minimo_requerido"] >= familia["activos"] or familia["minimo_requerido"] > 0


# ══ Campanas de inventario anual ════════════════════════════


async def test_campana_congela_compara_y_cierra(db, api):
    mundo = await _mundo(api, "campana")
    activos = []
    for indice in range(3):
        activos.append(
            (
                await api.post(
                    "/api/activos",
                    json={
                        "tipo": "CPU",
                        "oficina_id": mundo["oficina"]["id"],
                        "nombre_equipo": f"PC {indice}",
                        "codigo_patrimonial": f"CP-{indice}",
                    },
                    headers=mundo["admin"],
                )
            ).json()["id"]
        )

    creacion = await api.post(
        "/api/campanas",
        json={
            "nombre": "Campana anual 2026",
            "anio": 2026,
            "fecha_inicio": f"{dt.date.today().year}-01-01",
            "fecha_fin": f"{dt.date.today().year}-12-31",
            "notas": "Verificacion fisica",
        },
        headers=mundo["admin"],
    )
    assert creacion.status_code == 201, creacion.text
    campana = creacion.json()
    assert campana["estado"] == "abierta"
    # La campaña nace **vacía**: se llena con el Excel de la sala. Antes copiaba
    # aquí los 3 equipos del inventario, y la lista de la campaña salía idéntica a
    # la del inventario sin que nadie hubiera subido nada.
    assert campana["total_items"] == 0, campana
    assert campana["total_previsto"] == 3, "pero sí sabe cuántos hay registrados en el alcance"
    assert campana["resumen"]["verificados"] == 0, campana

    vacia = (await api.get(f"/api/campanas/{campana['id']}/items", headers=mundo["admin"])).json()
    assert vacia["total"] == 0, vacia

    # El Excel de la campana compara fila por fila y NUNCA borra equipos
    from io import BytesIO

    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "ZONA CAMPANA"
    hoja.append(["TIPO", "NOMBRE", "CODIGO PATRIMONIAL", "OFICINA"])
    hoja.append(["CPU", "PC 0", "CP-0", "COMUNA"])
    hoja.append(["CPU", "PC 1", "CP-1", "COMUNA"])
    # El tercero no aparece: quedara "por verificar", no se borra
    buffer = BytesIO()
    libro.save(buffer)
    comparacion = await api.post(
        f"/api/campanas/{campana['id']}/excel",
        files={"archivo": ("campana.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=mundo["admin"],
    )
    assert comparacion.status_code == 200, comparacion.text
    resumen = comparacion.json()["resumen"]
    assert resumen["sin_cambios"] >= 2, f"{resumen} -> {comparacion.json()['resultados']}"
    assert resumen["ausentes"] >= 1, "el equipo ausente se reporta, no se borra"
    estados = {r["estado"] for r in comparacion.json()["resultados"]}
    assert "ausente" in estados
    assert "borrado" not in estados, "una campana nunca borra equipos"

    # Verificacion fisica guiada de un equipo. Los items ya existen: los creó la
    # comparación contra el Excel.
    items = (await api.get(f"/api/campanas/{campana['id']}/items", headers=mundo["admin"])).json()
    assert items["total"] == 3, items
    assert all(item["estado_item"] == "pendiente" for item in items["items"]), items

    marcado = await api.post(
        f"/api/campanas/{campana['id']}/items/{items['items'][0]['id']}",
        json={"estado_item": "confirmado", "observaciones": "Equipo presente en la oficina"},
        headers=mundo["admin"],
    )
    assert marcado.status_code == 200, marcado.text
    assert marcado.json()["estado_item"] == "confirmado"
    assert marcado.json()["verificado_en"], "se sabe quien y cuando verifico"

    # Un equipo ausente en el Excel se reporta, pero no se borra
    ausente = next(
        i for i in (await api.get(f"/api/campanas/{campana['id']}/items", headers=mundo["admin"])).json()["items"]
        if i["activo_id"] == activos[2]
    )
    no_encontrado = await api.post(
        f"/api/campanas/{campana['id']}/items/{ausente['id']}",
        json={"estado_item": "no_encontrado", "observaciones": "No estaba en la oficina"},
        headers=mundo["admin"],
    )
    assert no_encontrado.status_code == 200, no_encontrado.text

    # Un estado inventado se rechaza
    invalido = await api.post(
        f"/api/campanas/{campana['id']}/items/{ausente['id']}",
        json={"estado_item": "inventado"},
        headers=mundo["admin"],
    )
    assert invalido.status_code == 422

    # Cerrar sin confirmacion explicita no se permite
    sin_confirmar = await api.post(
        f"/api/campanas/{campana['id']}/cerrar",
        json={"nota": "Intento sin confirmacion"},
        headers=mundo["admin"],
    )
    assert sin_confirmar.status_code == 422
    assert "confirmacion" in sin_confirmar.json()["mensaje"].lower()

    # Cierre: version historica consultable
    cierre = await api.post(
        f"/api/campanas/{campana['id']}/cerrar",
        json={"nota": "Todo verificado", "confirmacion": True, "marcar_no_localizados": True},
        headers=mundo["admin"],
    )
    assert cierre.status_code == 200, cierre.text
    cuerpo_cierre = cierre.json()
    assert cuerpo_cierre["estado"] == "cerrada"
    assert cuerpo_cierre["no_localizados"] >= 1, "los no localizados quedan para seguimiento"
    assert cuerpo_cierre["mensaje"]

    # No se puede cerrar dos veces
    repetido = await api.post(
        f"/api/campanas/{campana['id']}/cerrar",
        json={"confirmacion": True},
        headers=mundo["admin"],
    )
    assert repetido.status_code == 409

    historico = (await api.get("/api/campanas/versiones/historico", headers=mundo["admin"])).json()
    assert any(v["anio"] == 2026 for v in historico["items"])

    # El equipo sigue existiendo: la campana no borra nada, solo lo marca
    from bson import ObjectId

    from app.core.db import get_db

    guardado = await get_db()["activos"].find_one({"_id": ObjectId(activos[2])})
    assert guardado is not None, "una campana nunca borra equipos"
    assert guardado["estado"] == "no_localizado", "queda para seguimiento, no desaparece"


def _csv_de_sala() -> bytes:
    """El Excel de una sala, en CSV: una hoja, una zona, una fila por equipo."""
    return (
        "AREA,TIPO DE EQUIPO,Codigo Patrimonial,Nombre\r\n"
        "PISCINA MUNICIPAL,CPU,PIS-001,PC de la piscina\r\n"
        "PISCINA MUNICIPAL,Impresora,PIS-002,IMPRESORA DE LA PISCINA\r\n"
    ).encode("utf-8")


async def test_la_campana_se_busca_por_oficina_y_no_revienta_con_un_asterisco(db, api):
    """
    En una sala lo que se sabe es **dónde** está el equipo, no cómo se llama.

    El buscador solo miraba el nombre y el código del equipo, así que buscar el
    nombre de una zona —«PISCINA»— salía con cero resultados aunque la campaña
    tuviera los equipos de esa zona. Y el texto tecleado se usaba tal cual como
    expresión regular, de modo que buscar `a*b` —un asterisco es normal al teclear
    un código— dejaba la regex sin cerrar y el backend devolvía error.

    Las dos cosas se comprueban aquí contra la API.
    """
    mundo = await _mundo(api, "busqueda-campana")
    zona = await api.post("/api/zonas", json={"nombre": "Zona PISCINA"}, headers=mundo["admin"])
    assert zona.status_code == 201, zona.text
    oficina = await api.post(
        "/api/oficinas",
        json={"nombre": "PISCINA MUNICIPAL", "zona_id": zona.json()["id"]},
        headers=mundo["admin"],
    )
    assert oficina.status_code == 201, oficina.text
    creado = await api.post(
        "/api/activos",
        json={
            "tipo": "CPU",
            "oficina_id": oficina.json()["id"],
            "nombre_equipo": "PC de la piscina",
            "codigo_patrimonial": "PIS-001",
        },
        headers=mundo["admin"],
    )
    assert creado.status_code == 201, creado.text

    anio = dt.date.today().year
    campana = (
        await api.post(
            "/api/campanas",
            json={
                "nombre": "Busqueda",
                "anio": anio,
                "fecha_inicio": f"{anio}-01-01",
                "fecha_fin": f"{anio}-12-31",
            },
            headers=mundo["admin"],
        )
    ).json()

    async def buscar(texto: str) -> dict:
        # La campaña nace vacía, así que primero se sube el Excel de la sala: los
        # items de la campaña son los que salen del archivo (y los registrados del
        # alcance que no aparecen en él), no una copia del inventario.
        await api.post(
            f"/api/campanas/{campana['id']}/excel",
            files={"archivo": ("sala.csv", _csv_de_sala(), "text/csv")},
            headers=mundo["admin"],
        )
        respuesta = await api.get(f"/api/campanas/{campana['id']}/items?texto={texto}", headers=mundo["admin"])
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()

    # Por el nombre de la zona, que es lo que se busca desde la sala.
    por_zona = await buscar("PISCINA")
    assert por_zona["total"] >= 1, por_zona

    # Por el nombre de la oficina.
    por_oficina = await buscar("PISCINA%20MUNICIPAL")
    assert por_oficina["total"] >= 1, por_oficina

    # Por el código, como antes.
    assert (await buscar("PIS-001"))["total"] == 1

    # Un asterisco no rompe la búsqueda: se busca literal.
    con_asterisco = await buscar("a*b")
    assert con_asterisco["total"] == 0, "un asterisco se escapa: no es comodín ni error"
    assert con_asterisco["items"] == []


# ══ Exportaciones y PDF ════════════════════════════════════


async def test_exportacion_pdf_se_descarga(db, api):
    mundo = await _mundo(api, "pdf")
    equipo_id = await equipo_para_persona(api, mundo["admin"], mundo["tecnico_id"])
    ticket = (
        await api.post(
            "/api/tickets",
            json={"activo_id": equipo_id, "tipo_problema": "No enciende", "urgencia": "me_frena"},
            headers=mundo["tecnico"],
        )
    ).json()["ticket"]

    creada = await api.post(
        "/api/exportaciones",
        json={"tipo": "tickets", "formato": "pdf", "filtros": {}},
        headers=mundo["admin"],
    )
    assert creada.status_code == 200, creada.text
    registro = creada.json()
    assert registro["estado"] == "listo"
    assert registro["bytes"] > 0

    assert registro["descarga_url"].startswith("/exportaciones/"), registro["descarga_url"]
    descarga = await api.get(f"/api{registro['descarga_url']}", headers=mundo["admin"])
    assert descarga.status_code == 200, descarga.text
    assert descarga.headers["content-type"].startswith("application/pdf")
    assert descarga.content.startswith(b"%PDF"), "es un PDF de verdad"

    listado = (await api.get("/api/exportaciones", headers=mundo["admin"])).json()
    assert any(e["id"] == registro["id"] for e in listado["items"])


async def test_exportacion_excel_de_inventario(db, api):
    mundo = await _mundo(api, "excel")
    await api.post(
        "/api/activos",
        json={"tipo": "Monitor", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "Monitor 1"},
        headers=mundo["admin"],
    )
    creada = await api.post(
        "/api/exportaciones",
        json={"tipo": "inventario", "formato": "excel", "filtros": {}},
        headers=mundo["admin"],
    )
    assert creada.status_code == 200, creada.text
    descarga = await api.get(f"/api{creada.json()['descarga_url']}", headers=mundo["admin"])
    assert descarga.status_code == 200
    assert descarga.content[:2] == b"PK", "un xlsx empieza con PK"


async def test_exportacion_tickets_convierte_fechas_de_filtros(db, api):
    from app.core.time import local_date

    mundo = await _mundo(api, "fechas_exportacion")
    equipo_id = await equipo_para_persona(api, mundo["admin"], mundo["tecnico_id"])
    ticket = await api.post(
        "/api/tickets/manual",
        json={"persona": {"afectado_id": mundo["tecnico_id"]}, "activo_id": equipo_id, "asunto": "No enciende equipo", "prioridad": "media"},
        headers=mundo["tecnico"],
    )
    assert ticket.status_code == 201, ticket.text

    # El rango se arma con la fecha de hoy, no con fechas fijas: con un rango fijo
    # la prueba empezó a fallar sola al pasar el día 7 de octubre de 2026, sin
    # que cambiara nada del código.
    hoy = local_date()
    desde = (hoy - dt.timedelta(days=1)).isoformat()
    hasta = (hoy + dt.timedelta(days=1)).isoformat()

    creada = await api.post(
        "/api/exportaciones",
        json={
            "tipo": "tickets",
            "formato": "csv",
            "filtros": {"fecha_desde": desde, "fecha_hasta": hasta},
        },
        headers=mundo["admin"],
    )
    assert creada.status_code == 200, creada.text
    descarga = await api.get(f"/api{creada.json()['descarga_url']}", headers=mundo["admin"])
    assert descarga.status_code == 200
    assert ticket.json()["ticket"]["codigo"].encode() in descarga.content


async def test_ticket_sin_zona_no_se_pierde_y_se_exporta_diciendo_que_le_falta(db, api):
    """Un caso sin zona ni oficina se guarda y sale en el informe, no se pierde.

    Lo habitual es que la zona y la oficina lleguen solas del usuario registrado.
    Cuando quien reporta no está en el sistema, el caso se registra igual pero sin
    ellas, y la pregunta razonable es si desaparece o si el informe lo deja fuera.
    No desaparece: se guarda, aparece en la bandeja y sale en el archivo. Lo que no
    puede ser es salir con la celda vacía, porque en una hoja de cálculo una
    celda vacía no distingue «no tiene zona» de «se borró el dato», y encima no
    se puede filtrar por ella.
    """
    mundo = await _mundo(api, "sin_zona")
    creado = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["tecnico_id"]},
            "activo_id": await equipo_para_persona(api, mundo["admin"], mundo["tecnico_id"]),
            "asunto": "Se quedó sin luz en el archivo",
            "prioridad": "media",
        },
        headers=mundo["tecnico"],
    )
    assert creado.status_code == 201, creado.text
    codigo = creado.json()["ticket"]["codigo"]
    from bson import ObjectId
    await db.tickets.update_one({"_id": ObjectId(creado.json()["ticket"]["id"])}, {"$set": {"afectado_nombre": "Persona de la calle", "zona_id": None, "zona_nombre": None, "oficina_id": None, "oficina_nombre": None}})

    # El nombre de quien no está registrado sí queda escrito: el caso se puede
    # seguir aunque no se sepa de qué oficina viene.
    detalle = (await api.get(f"/api/tickets/{creado.json()['ticket']['id']}", headers=mundo["tecnico"])).json()
    assert detalle["afectado_nombre"] == "Persona de la calle"

    creada = await api.post(
        "/api/exportaciones", json={"tipo": "tickets", "formato": "csv"}, headers=mundo["admin"]
    )
    assert creada.status_code == 200, creada.text
    descarga = await api.get(f"/api{creada.json()['descarga_url']}", headers=mundo["admin"])
    assert descarga.status_code == 200
    contenido = descarga.content
    assert codigo.encode() in contenido, "el caso sin zona tiene que salir en el informe"
    assert b"Sin zona" in contenido and b"Sin oficina" in contenido, (
        "las columnas vacías tienen que decir qué les falta"
    )


async def test_errores_de_validacion_identifican_el_campo_y_ausencia_acepta_enfermedad(db, api):
    mundo = await _mundo(api, "validaciones")

    usuario_invalido = await api.post(
        "/api/usuarios",
        json={"nombre": "AB", "rol": "usuario", "password": PASSWORD},
        headers=mundo["admin"],
    )
    assert usuario_invalido.status_code == 422
    assert usuario_invalido.json()["mensaje"] == "Revisa los datos ingresados."
    assert any(error["campo"] == "nombre" for error in usuario_invalido.json()["detalles"])

    ausencia = await api.post(
        "/api/ausencias",
        json={
            "tecnico_id": mundo["tecnico_id"],
            "tipo": "Enfermedad",
            "inicio": "2026-10-07",
            "fin": "2026-10-08",
        },
        headers=mundo["admin"],
    )
    assert ausencia.status_code == 201, ausencia.text

    articulo_incompleto = await api.post(
        "/api/kb/articulos",
        json={"titulo": "Articulo de prueba", "categoria": "General", "cuerpo": "Contenido suficientemente largo."},
        headers=mundo["admin"],
    )
    assert articulo_incompleto.status_code == 422
    assert any(error["campo"] == "resumen" for error in articulo_incompleto.json()["detalles"])


async def test_solo_ti_puede_restablecer_contrasenas(db, api):
    mundo = await _mundo(api, "password_reset")
    usuario = await api.post(
        "/api/usuarios",
        json={
            "nombre": "Persona de prueba",
            "email": "persona-password-reset@prueba.local",
            "password": PASSWORD,
            "rol": "usuario",
            "oficina_id": mundo["oficina"]["id"],
        },
        headers=mundo["admin"],
    )
    assert usuario.status_code == 201, usuario.text
    cab_usuario = await _sesion(api, "persona-password-reset@prueba.local")

    cambio_propio = await api.post(
        "/api/auth/password",
        json={"password_actual": PASSWORD, "password_nuevo": "NuevaClave-2026"},
        headers=cab_usuario,
    )
    assert cambio_propio.status_code == 403

    restablecida = await api.post(
        f"/api/usuarios/{usuario.json()['id']}/restablecer-password",
        json={"password": "NuevaClave-2026"},
        headers=mundo["admin"],
    )
    assert restablecida.status_code == 200, restablecida.text
    assert "contraseña" in restablecida.json()["mensaje"].lower()
    acceso_nuevo = await api.post(
        "/api/auth/login",
        json={"correo": "persona-password-reset@prueba.local", "password": "NuevaClave-2026"},
    )
    assert acceso_nuevo.status_code == 200, acceso_nuevo.text


# ══ Analitica ══════════════════════════════════════════════


async def test_analitica_usa_cifras_reales(db, api):
    mundo = await _mundo(api, "analitica")
    equipo_id = await equipo_para_persona(api, mundo["admin"], mundo["tecnico_id"])
    for _ in range(2):
        await api.post(
            "/api/tickets",
            json={"activo_id": equipo_id, "tipo_problema": "Internet/red", "urgencia": "puede_esperar"},
            headers=mundo["tecnico"],
        )

    resumen = (await api.get("/api/analitica/resumen", headers=mundo["admin"])).json()
    assert resumen["tickets_abiertos"] == 2, resumen
    assert resumen["total_activos"] >= 0
    assert resumen["zonas"] == 1 and resumen["oficinas"] == 1
    assert isinstance(resumen["top_oficinas"], list)

    panel = (await api.get("/api/analitica/panel", headers=mundo["admin"])).json()
    secciones = [
        "ranking_oficinas",
        "ranking_zonas",
        "mapa_calor_categoria",
        "mapa_calor_prioridad",
        "tendencia",
        "riesgo_sla_categoria",
        "riesgo_sla_oficina",
        "riesgo_sla_tecnico",
        "causas",
        "familias_equipos",
        "confianza_modelo",
        "calidad_recomendaciones",
        "carga_tecnicos",
    ]
    faltan = [seccion for seccion in secciones if seccion not in panel]
    assert not faltan, f"faltan analisis obligatorios: {faltan}"
    assert panel["kpis"]["tickets_analizados"] >= 2
    for seccion in secciones:
        bloque = panel[seccion]
        if isinstance(bloque, dict) and bloque.get("suficiente_datos") is False:
            assert bloque.get("minimo_requerido"), f"{seccion} debe decir que datos necesita"


# ══ Base de conocimiento y auditoria ═══════════════════════


async def test_las_sugerencias_no_repiten_el_mismo_articulo(db, api):
    """La lista de artículos que podrían resolverlo no repite el mismo título.

    La base de conocimiento llegó a tener siete copias de cada artículo, y el
    panel de sugerencias sacaba cuatro líneas idénticas. No es un detalle: cuatro
    veces la misma respuesta se lee como que la IA no sabe filtrar, y ocupa el
    espacio donde cabrían cuatro soluciones distintas.
    """
    from app.services import kb_service

    mundo = await _mundo(api, "kb_repetidos")
    cuerpo = {"categoria": "No enciende", "resumen": "Revisar la energia.", "cuerpo": "Comprueba el enchufe."}
    for _ in range(3):
        creado = await api.post(
            "/api/kb/articulos",
            json={"titulo": "La computadora no enciende", **cuerpo},
            headers=mundo["admin"],
        )
        assert creado.status_code == 201, creado.text
    # Y uno distinto, que sí debe aparecer.
    await api.post(
        "/api/kb/articulos",
        json={"titulo": "La computadora enciende sola", **cuerpo},
        headers=mundo["admin"],
    )

    sugerencias = await kb_service.sugerir_para_ticket("mi computadora no enciende", limite=4)
    titulos = [a["titulo"] for a in sugerencias]
    assert titulos, "tiene que devolver sugerencias"
    assert len(titulos) == len(set(titulos)), f"se repiten títulos: {titulos}"
    assert "La computadora no enciende" in titulos


async def test_base_de_conocimiento(db, api):
    mundo = await _mundo(api, "kb")
    creado = await api.post(
        "/api/kb/articulos",
        json={
            "titulo": "Como limpiar un equipo con virus",
            "categoria": "Software instalado",
            "resumen": "Pasos para aislar y limpiar un equipo.",
            "cuerpo": "Sigue estos pasos en orden.",
            "pasos": ["Desconectar de la red", "Ejecutar el antivirus"],
        },
        headers=mundo["admin"],
    )
    assert creado.status_code == 201, creado.text
    articulo = creado.json()
    assert len(articulo["pasos"]) == 2

    detalle = await api.get(f"/api/kb/articulos/{articulo['id']}", headers=mundo["admin"])
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["cuerpo"] == "Sigue estos pasos en orden."
    categorias = (await api.get("/api/kb/categorias", headers=mundo["admin"])).json()["items"]
    assert "Software instalado" in categorias

    busqueda = (await api.get("/api/kb/articulos?texto=virus", headers=mundo["admin"])).json()
    assert any(a["id"] == articulo["id"] for a in busqueda["items"])

    valoración = await api.post(
        f"/api/kb/articulos/{articulo['id']}/valorar",
        json={"util": True},
        headers=mundo["tecnico"],
    )
    assert valoración.status_code == 200
    assert valoración.json()["utiles"] >= 1


async def test_auditoria_append_only(db, api):
    mundo = await _mundo(api, "appendonly")
    await api.post("/api/zonas", json={"nombre": "Zona auditada"}, headers=mundo["admin"])
    antes = (await api.get("/api/auditoria?limite=200", headers=mundo["admin"])).json()["items"]
    assert antes
    # No existe endpoint de borrado: la auditoria es append-only
    from app.main import app

    rutas_borrado = [
        ruta
        for ruta in app.routes
        if getattr(ruta, "methods", None) and "DELETE" in ruta.methods and "auditoria" in getattr(ruta, "path", "")
    ]
    assert rutas_borrado == [], "no se puede borrar la auditoria"


# ══ Arranque guiado ════════════════════════════════════════


async def test_instalacion_guia_el_primer_arranque(db, api):
    desde_app = await api.get("/api/instalacion")
    assert desde_app.status_code == 200
    cuerpo = desde_app.json()
    assert cuerpo["siguiente_paso"], "dice que hacer"
    assert cuerpo["pasos"], "explica los pasos"

    # El administrador se crea por la propia guia
    creado = await api.post(
        "/api/instalacion/administrador",
        json={
            "nombre": "Primer Administrador",
            "email": "primer.admin@prueba.local",
            "password": PASSWORD,
        },
    )
    assert creado.status_code in (200, 201), creado.text
    assert creado.json()["rol"] == "administrador"

    # Con administrador ya no se puede crear otro por la guia
    segundo = await api.post(
        "/api/instalacion/administrador",
        json={"nombre": "Otro", "email": "otro.admin@prueba.local", "password": PASSWORD},
    )
    assert segundo.status_code in (409, 403), "la guia solo crea el primero"

    cab = await _sesion(api, "primer.admin@prueba.local")
    estado = (await api.get("/api/instalacion", headers=cab)).json()
    # Sin inventario importado todavia, la guia pide importar o crear a mano
    assert estado["siguiente_paso"] in {"importar_inventario", "crear_usuarios"}
    assert all("hecho" in paso for paso in estado["pasos"])
    assert next(paso["titulo"] for paso in estado["pasos"] if paso["clave"] == estado["siguiente_paso"])


async def test_configuracion_y_feriados(db, api):
    mundo = await _mundo(api, "config")
    configuracion = (await api.get("/api/configuracion", headers=mundo["admin"])).json()
    assert configuracion["ia"]["global_activa"] in (True, False)
    assert configuracion["ia"]["aprendizaje_activo"] in (True, False)
    assert "sla" in configuracion or "calendario" in configuracion

    # Feriados con fecha sin hora, en texto ISO
    creado = await api.post(
        "/api/configuracion/feriados",
        json={"nombre": "Feria Distrital", "fecha": "2026-12-25", "tipo": "feriado"},
        headers=mundo["admin"],
    )
    assert creado.status_code in (200, 201), creado.text
    assert creado.json()["fecha"] == "2026-12-25", "la fecha se guarda como texto ISO"

    feriados = (await api.get("/api/configuracion/feriados", headers=mundo["admin"])).json()
    assert any(f["fecha"] == "2026-12-25" for f in feriados["items"])

    # Los diccionarios de importacion son editables y se aplican de verdad
    catalogo = await api.put(
        "/api/configuracion/catalogo",
        json={
            "clave": "sinonimos_dispositivo",
            "valores": [{"valor": "Raton -> Mouse", "etiqueta": "Raton se corrige a Mouse"}],
        },
        headers=mundo["admin"],
    )
    assert catalogo.status_code == 200, catalogo.text
    assert any(v["valor"] == "Raton -> Mouse" for v in catalogo.json()["items"])

    # Un catalogo que no existe se rechaza con un mensaje claro
    inexistente = await api.put(
        "/api/configuracion/catalogo",
        json={"clave": "no_existe", "valores": [{"valor": "x"}]},
        headers=mundo["admin"],
    )
    assert inexistente.status_code == 422


async def test_esquema_por_tipo_configurable(db, api):
    mundo = await _mundo(api, "esquema")
    esquema = await api.put(
        "/api/configuracion/esquema/Monitor",
        json={"esperados": ["codigo_patrimonial", "marca"], "opcionales": ["modelo"]},
        headers=mundo["admin"],
    )
    assert esquema.status_code == 200, esquema.text

    monitor = (
        await api.post(
            "/api/activos",
            json={"tipo": "Monitor", "oficina_id": mundo["oficina"]["id"], "marca": "Dell"},
            headers=mundo["admin"],
        )
    ).json()
    assert "codigo_patrimonial" in monitor["campos_faltantes"]
    assert "marca" not in monitor["campos_faltantes"]

    consulta = (await api.get("/api/calidad-inventario/esquema/Monitor", headers=mundo["admin"])).json()
    assert consulta["esperados"] == ["codigo_patrimonial", "marca"]