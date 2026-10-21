"""Cierre, reapertura y permisos: lo que el equipo TI hace al terminar un caso."""

from __future__ import annotations

from bson import ObjectId
from tests.conftest import PASSWORD, equipo_para_persona


async def test_ticket_nuevo_avisa_al_equipo_de_soporte(db, api):
    """Crear un ticket tiene que dejar aviso en la campana del equipo TI.

    Antes solo se publicaba un evento por websocket: si nadie estaba mirando la
    lista en ese momento, el aviso se perdia. Y en un despliegue con un unico
    administrador que reporta y atiende a la vez, la campana se quedaba siempre
    vacia, porque el unico destinatario posible era el mismo.
    """
    mundo = await _mundo(api, "aviso_nuevo")

    # Lo reporta la persona usuaria: tiene que avisar al tecnico, que no lo ha hecho.
    creado = await api.post(
        "/api/tickets",
        json={"descripcion": "la impresora no enciende", "urgencia": "me_frena"},
        headers=mundo["persona"],
    )
    assert creado.status_code == 201, creado.text
    codigo = creado.json()["ticket"]["codigo"]

    campana_tec1 = (await api.get("/api/notificaciones", headers=mundo["tec1"])).json()
    assert campana_tec1["no_leidas"] >= 1, "el tecnico tiene que enterarse de que hay ticket nuevo"
    aviso = campana_tec1["items"][0]
    assert aviso["titulo"].endswith(codigo), f"el aviso identifica el caso: {aviso['titulo']!r}"
    assert aviso["ticket_id"] == creado.json()["ticket"]["id"]

    # Quien lo reporto no se avisa a si mismo: ya sabe que lo ha creado.
    campana_persona = (await api.get("/api/notificaciones", headers=mundo["persona"])).json()
    assert campana_persona["no_leidas"] == 0, "no se avisa a quien reporta"

    # El alta manual la firma alguien del equipo TI y a si mismo no se avisa: lo que
# cuenta es que la campana no crecer por esa via.
    antes_manual = (await api.get("/api/notificaciones", headers=mundo["admin"])).json()["no_leidas"]
    manual = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["persona_id"]},
            "activo_id": await equipo_para_persona(api, mundo["admin"], mundo["persona_id"]),
            "asunto": "Equipo sin red",
            "prioridad": "alta",
        },
        headers=mundo["admin"],
    )
    assert manual.status_code == 201, manual.text
    despues_manual = (await api.get("/api/notificaciones", headers=mundo["admin"])).json()["no_leidas"]
    assert despues_manual == antes_manual, "el alta manual no avisa a quien la firma"


async def test_el_historial_no_enseña_estados_que_ya_no_existen(db, api):
    """El registro dice lo que pasó, pero con los nombres de hoy.

    En el historial seguían apareciendo transiciones como «Estado: asignado ->
    en_espera» y «resuelto -> cerrado», con dos estados que se retiraron del
    catálogo. Leer eso en una pantalla donde no existe ningún estado «asignado»
    obliga a buscar a qué corresponde, y es justo lo que se pidió al retirarlos.

    El documento guardado **no** se reescribe: dice lo que pasó cuando pasó. Solo
    se traduce al mostrar, y cada estado retirado tiene un sustituto claro.
    """
    from app.core.db import get_db
    from app.core.time import utcnow

    mundo = await _mundo(api, "historial_estados")
    ticket = await _ticket(api, mundo, "historial")

    db = get_db()
    documento = await db["tickets"].find_one({"codigo": ticket["codigo"]})
    await db["ticket_eventos"].insert_many(
        [
            {
                "ticket_id": documento["_id"],
                "tipo": "estado",
                "fecha": utcnow(),
                "actor": {"id": None, "nombre": "Administrador", "rol": "administrador"},
                # Se escribe a mano lo que dejó el código antes de retirar los estados.
                "resumen": "Estado: asignado -> en_espera",
                "detalle": {"estado_anterior": "asignado", "estado_nuevo": "en_espera"},
                "visible_usuario": False,
                "origen_ia": False,
            },
            {
                "ticket_id": documento["_id"],
                "tipo": "estado",
                "fecha": utcnow(),
                "actor": {"id": None, "nombre": "Administrador", "rol": "administrador"},
                "resumen": "Estado: resuelto -> cerrado",
                "detalle": {"estado_anterior": "resuelto", "estado_nuevo": "cerrado"},
                "visible_usuario": False,
                "origen_ia": False,
            },
            {
                "ticket_id": documento["_id"],
                "tipo": "estado",
                "fecha": utcnow(),
                "actor": {"id": None, "nombre": "Administrador", "rol": "administrador"},
                # El caso difícil: el ticket sale de «en progreso» y entra en
                # «asignado», que hoy también se llama «en progreso». Traducirlo a
                # la letra daría «en progreso → en progreso»: el cambio desaparecería.
                "resumen": "Estado: en_progreso -> asignado",
                "detalle": {"estado_anterior": "en_progreso", "estado_nuevo": "asignado"},
                "visible_usuario": False,
                "origen_ia": False,
            },
        ]
    )

    detalle = (await api.get(f"/api/tickets/{ticket['id']}", headers=mundo["admin"])).json()
    resúmenes = [evento["resumen"] for evento in detalle["eventos"]]
    assert "Estado: asignado -> en_espera" not in resúmenes, "no puede quedar un estado retirado a la vista"
    assert "Estado: en progreso → en espera" in resúmenes, "«asignado» se muestra con el nombre de hoy"
    assert "Estado: resuelto (estado antiguo) → cerrado" in resúmenes, (
        "«resuelto» se marca como antiguo porque si no el cambio desaparece"
    )
    # El caso que no puede traducirse: «en progreso» y «asignado» se llaman igual hoy,
    # así que la traducción borraría el cambio. Se deja el nombre de entonces.
    assert "Estado: en progreso → asignado (estado antiguo)" in resúmenes, (
        "no puede leerse como que el ticket no cambió de estado"
    )
    assert "Estado: en progreso → en progreso" not in resúmenes, (
        "traducir a la letra convierte un cambio real en uno inexistente"
    )
    # Y los estados nuevos se escriben con palabras, no con el valor de la base.
    assert not any("en_progreso" in r or "en_espera" in r for r in resúmenes), (
        "ningún estado sale con el guion bajo del valor interno"
    )

    # Y el documento guardado sigue diciendo lo que decía.
    guardado = await db["ticket_eventos"].find_one({"ticket_id": documento["_id"], "detalle.estado_nuevo": "en_espera"})
    assert guardado["resumen"] == "Estado: asignado -> en_espera", "el registro no se reescribe"


async def test_un_tipo_de_equipo_no_inventa_un_equipo(db, api):
    """Escribir «CPU» no engancha una máquina cualquiera del inventario.

    El alta manual tenía un cuadro de texto libre que, al guardar, buscaba lo
    escrito con una coincidencia **sin ancar** y se quedaba con el primero. En la
    base de inventario «CPU» coincide con **6 equipos de 5 zonas distintas**, así
    que el caso acababa con la zona, el conjunto y el historial de fallos de una
    máquina que no era de nadie.

    Y por nombre tampoco se puede saber: nombres como «COMPUTADORA N°01 - TECLADO»
    se repiten **52 veces** repartidas entre las cinco zonas.

    Ahora el equipo se elige de una lista —el `activo_id` llega elegido— y el tipo
    solo es un tipo: información verdadera, sin enlace a nada.
    """
    mundo = await _mundo(api, "equipo")
    from app.core.db import get_db
    from app.core.ids import nuevo_id

    db = get_db()
    # El inventario exige `tipo`, `oficina_id` y `campos_estado`. Lo que importa
    # aquí no es que el equipo sea real, sino que **existen varios con el mismo
    # texto en el nombre**: eso es lo que hace que el texto no pueda decidir.
    await db["activos"].insert_many(
        [
            {
                "nombre_equipo": "COMPUTADORA N°01 - CPU",
                "tipo": "CPU",
                "oficina_id": nuevo_id(),
                "clave_natural": "cpu-palacio",
                "campos_estado": {},
                "zona_nombre": "PALACIO",
                "activo": True,
            },
            {
                "nombre_equipo": "COMPUTADORA N°02 - CPU",
                "tipo": "CPU",
                "oficina_id": nuevo_id(),
                "clave_natural": "cpu-mercado",
                "campos_estado": {},
                "zona_nombre": "MERCADO",
                "activo": True,
            },
        ]
    )

    creado = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["persona_id"], "detectado_por_tec": True},
            "asunto": "la compu no prende",
            "activo_tipo": "CPU",
        },
        headers=mundo["admin"],
    )
    assert creado.status_code == 422, creado.text
    # Y el texto libre tampoco engancha nada, que era el otro camino del fallo.
    con_texto = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["persona_id"], "detectado_por_tec": True},
            "asunto": "la compu no prende",
            "activo_no_identificado": "CPU",
        },
        headers=mundo["admin"],
    )
    assert con_texto.status_code == 422, con_texto.text
    assert await db.tickets.count_documents({}) == 0


async def test_el_equipo_elegido_de_la_lista_si_se_enlaza(db, api):
    """Si se elige un equipo de la lista, ese equipo queda enlazado.

    Lo contrario del anterior: quitar el enlace sin comprobar que el camino
    bueno sigue funcionando sería arreglar el fallo borrando la función.
    """
    mundo = await _mundo(api, "equipo_ok")
    from app.core.db import get_db
    from app.core.ids import nuevo_id

    db = get_db()
    equipo_id = nuevo_id()
    await db["activos"].insert_one(
        {
            "_id": equipo_id,
            "nombre_equipo": "PC DE VENTANILLA",
            "tipo": "CPU",
            "oficina_id": nuevo_id(),
            "clave_natural": "pc-ventanilla",
            "responsable_id": ObjectId(mundo["persona_id"]),
            "campos_estado": {},
            "zona_nombre": "PALACIO",
            "activo": True,
        }
    )

    creado = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["persona_id"], "detectado_por_tec": True},
            "asunto": "la compu de ventanilla no prende",
            "activo_id": str(equipo_id),
        },
        headers=mundo["admin"],
    )
    assert creado.status_code == 201, creado.text
    detalle = (await api.get(f"/api/tickets/{creado.json()['ticket']['id']}", headers=mundo["admin"])).json()
    assert detalle["activo_id"] == str(equipo_id)
    assert detalle["activo_tipo"] == "CPU", "el tipo sale del propio equipo"
    assert detalle["activo_nombre"] == "PC DE VENTANILLA"


async def test_no_existe_el_estado_resuelto(db, api):
    """«Resuelto» se retiró: decía lo mismo que «cerrado» y era un paso de más.

    El catálogo tiene cinco estados —cuatro abiertos y uno final— y «resuelto» no
    está entre ellos. Pedirlo a la API tiene que rechazarse, no aceptarse en
    silencio: si volviera a existir, aparecerían de nuevo tickets en «resuelto» que
    nadie cierra y la misma pregunta de siempre.
    """
    from app.domain.constants import ESTADO_RESUELTO_LEGADO, ESTADOS_TICKET

    assert ESTADO_RESUELTO_LEGADO not in ESTADOS_TICKET, "el estado retirado no puede volver al catálogo"
    assert ESTADOS_TICKET == ("nuevo", "en_progreso", "en_espera", "cerrado")
    assert ESTADOS_TICKET.count("cerrado") == 1, "un ticket concluido queda en cerrado, y solo en cerrado"

    mundo = await _mundo(api, "sin_resuelto")
    ticket = await _ticket(api, mundo, "sin_resuelto")
    respuesta = await api.post(
        f"/api/tickets/{ticket['id']}/estado",
        json={"estado": "resuelto", "nota_resolucion": "Prueba."},
        headers=mundo["tec1"],
    )
    assert respuesta.status_code == 422, "«resuelto» ya no se acepta como estado"

    # Y cerrar es un paso directo, sin estado intermedio de por medio
    cerrado = await api.post(
        f"/api/tickets/{ticket['id']}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Prueba."},
        headers=mundo["tec1"],
    )
    assert cerrado.status_code == 200, cerrado.text
    assert cerrado.json()["estado"] == "cerrado"
    eventos = (await api.get(f"/api/tickets/{ticket['id']}", headers=mundo["tec1"])).json()["eventos"]
    estados = [evento.get("detalle", {}).get("estado_nuevo") for evento in eventos]
    assert "resuelto" not in estados, "ningún evento pasa por el estado retirado"


async def test_asignar_es_poner_en_progreso_y_no_hay_estado_asignado(db, api):
    """Asignar un técnico pone el caso «en progreso», en un solo paso.

    Existió un estado «asignado» entre «nuevo» y «en progreso», y obligaba a dos
    clics para decir una cosa: asignar dejaba el ticket ahí, y pasarlo a «en
    progreso» exigía un segundo paso que nadie daba. Trece tickets se quedaron
    parados en «asignado» y ni uno llegó a «en progreso», y ninguna pantalla
    informaba de la diferencia. Ahora no existe el estado.
    """
    import app.services.usuario_service as usuario_service

    from app.domain.constants import ESTADO_ASIGNADO_LEGADO, ESTADOS_TICKET

    assert ESTADO_ASIGNADO_LEGADO not in ESTADOS_TICKET, "el estado retirado no puede volver al catálogo"

    mundo = await _mundo(api, "asignar_progreso")
    # Se reporta desde el portal, no desde el equipo TI: así el caso nace en la
    # cola, sin técnico, que es justo el punto de partida que se quiere comprobar.
    creado = await api.post(
        "/api/tickets",
        json={"descripcion": "la impresora no enciende", "urgencia": "me_frena"},
        headers=mundo["persona"],
    )
    assert creado.status_code == 201, creado.text
    ticket = creado.json()["ticket"]
    assert ticket["estado"] == "nuevo", "sin técnico sigue en la cola"

    tecnico = (await usuario_service.buscar_global("tec1-asignar_progreso@prueba.local"))[0]
    asignar = await api.post(
        f"/api/tickets/{ticket['id']}/asignar",
        # El técnico de la prueba no tiene horario, así que el servidor pide
        # confirmación. Se acepta siempre: si el test dependiera del día de la
        # semana, unas fechas asignaría y otras no.
        json={"tecnico_id": str(tecnico["id"]), "confirmar_fuera_de_horario": True},
        headers=mundo["admin"],
    )
    assert asignar.status_code == 200, asignar.text
    assert "requiere_confirmacion" not in asignar.json(), asignar.json()

    detalle = (await api.get(f"/api/tickets/{ticket['id']}", headers=mundo["admin"])).json()
    assert detalle["estado"] == "en_progreso", (
        f"asignar tiene que ser un solo paso; quedó en {detalle['estado']!r}"
    )
    assert detalle["tecnico_id"] == str(tecnico["id"])

    # Y el estado retirado no se puede pedir por la API.
    resp = await api.post(
        f"/api/tickets/{ticket['id']}/estado", json={"estado": "asignado"}, headers=mundo["admin"]
    )
    assert resp.status_code == 422, resp.text


async def test_un_ticket_borrado_no_cuenta_como_trabajo_del_tecnico(db, api):
    """Un caso eliminado no puede marcar al técnico como ocupado ni inflar su carga.

    El borrado es lógico: el documento se queda con `eliminado`, y el panel de
    carga del equipo lo leía como si siguiera vivo. Pasaban tres cosas: el técnico
    aparecía «Ocupado» por un caso que ya no existe, su carga iba inflada y el
    enlace «Atendiendo TKT-…» llevaba a un ticket borrado, con un 404 al pulsarlo.
    """
    import app.services.usuario_service as usuario_service
    from app.core.db import get_db

    mundo = await _mundo(api, "borrado_no_carga")
    ticket = await _ticket(api, mundo, "carga")
    tecnico = (await usuario_service.buscar_global("tec1-borrado_no_carga@prueba.local"))[0]

    await api.post(
        f"/api/tickets/{ticket['id']}/asignar",
        json={"tecnico_id": str(tecnico["id"]), "confirmar_fuera_de_horario": True},
        headers=mundo["admin"],
    )
    antes = (await api.get("/api/equipo-ti/panel", headers=mundo["admin"])).json()["items"]
    fila = [t for t in antes if t["tecnico_id"] == str(tecnico["id"])][0]
    assert fila["carga_asignados"] == 1, "el caso vivo sí cuenta"
    assert fila["ticket_actual_codigo"] == ticket["codigo"]

    await get_db()["tickets"].update_one(
        {"codigo": ticket["codigo"]}, {"$set": {"eliminado": True}}
    )

    despues = (await api.get("/api/equipo-ti/panel", headers=mundo["admin"])).json()["items"]
    fila = [t for t in despues if t["tecnico_id"] == str(tecnico["id"])][0]
    assert fila["carga_asignados"] == 0, "un caso borrado no carga trabajo"
    assert fila["ticket_actual_codigo"] is None, "no se puede ofrecer un enlace a un ticket que no existe"
    assert fila["estado"] != "ocupado", "el técnico no está ocupado por un caso borrado"


async def _mundo(api, sufijo: str):
    """Administrador, dos técnicos y una persona usuaria, ya con sesión."""
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
    for nombre in ("tec1", "tec2"):
        await usuario_service.crear(
            {
                "nombre": f"Tecnico {nombre} {sufijo}",
                "email": f"{nombre}-{sufijo}@prueba.local",
                "password": PASSWORD,
                "rol": "tecnico",
            },
            usuario={"nombre": "Instalador", "rol": "sistema"},
        )
    await usuario_service.crear(
        {
            "nombre": f"Persona {sufijo}",
            "email": f"persona-{sufijo}@prueba.local",
            "password": PASSWORD,
            "rol": "usuario",
        },
        usuario={"nombre": "Instalador", "rol": "sistema"},
    )


    async def sesion(correo: str) -> dict[str, str]:
        r = await api.post("/api/auth/login", json={"correo": correo, "password": PASSWORD})
        assert r.status_code == 200, r.text
        datos = r.json()
        return {"Authorization": f"Bearer {datos['access_token']}", "X-CSRF-Token": datos["csrf_token"]}

    return {
        "admin": await sesion(f"admin-{sufijo}@prueba.local"),
        "tec1": await sesion(f"tec1-{sufijo}@prueba.local"),
        "tec2": await sesion(f"tec2-{sufijo}@prueba.local"),
        "persona": await sesion(f"persona-{sufijo}@prueba.local"),
        # El id de la persona va aparte porque sirve para registrarle un caso, no
        # como cabecera. No va dentro de `sesion` porque eso es lo que se pasa a
        # `headers=`.
        "persona_id": (await api.post("/api/auth/login", json={"correo": f"persona-{sufijo}@prueba.local", "password": PASSWORD})).json()["id"],
    }


async def _ticket(api, mundo: dict[str, str], sufijo: str) -> dict:
    creado = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["persona_id"]},
            "activo_id": await equipo_para_persona(api, mundo["admin"], mundo["persona_id"]),
            "asunto": f"No enciende el equipo {sufijo}",
            "descripcion": "no prende",
            "prioridad": "media",
        },
        headers=mundo["tec1"],
    )
    assert creado.status_code == 201, creado.text
    return creado.json()["ticket"]


async def test_cerrar_exige_permiso_o_ser_el_tecnico_asignado(db, api):
    """Cerrar el ticket de otra persona exige `tickets.cerrar_reabrir`.

    Ese permiso es delegable y arranca apagado, así que el caso por defecto es
    que un técnico NO pueda cerrar el ticket de un compañero. La interfaz
    necesita saberlo para no ofrecer un botón que el servidor va a rechazar.
    """
    mundo = await _mundo(api, "cierre_permiso")
    ticket = await _ticket(api, mundo, "permiso")
    tid = ticket["id"]

    # El administrador lo asigna a tec1, que es quien puede cerrarlo por ser suyo
    import app.services.usuario_service as usuario_service

    encontrados = await usuario_service.buscar_global("tec1-cierre_permiso@prueba.local")
    assert encontrados, "el técnico de la prueba tiene que existir"
    tec1 = encontrados[0]
    asignar = await api.post(
        f"/api/tickets/{tid}/asignar",
        json={"tecnico_id": str(tec1["id"])},
        headers=mundo["admin"],
    )
    assert asignar.status_code == 200, asignar.text

    detalle_t1 = (await api.get(f"/api/tickets/{tid}", headers=mundo["tec1"])).json()
    detalle_t2 = (await api.get(f"/api/tickets/{tid}", headers=mundo["tec2"])).json()
    assert detalle_t1["puede_cerrar"] is True, "el asignado sí puede cerrar el suyo"
    assert detalle_t2["puede_cerrar"] is False, "otro técnico no puede cerrarlo"

    # Y el servidor lo confirma: sin nota de resolución tampoco avanza
    sin_nota = await api.post(f"/api/tickets/{tid}/estado", json={"estado": "cerrado"}, headers=mundo["tec2"])
    assert sin_nota.status_code == 403, sin_nota.text
    assert sin_nota.json()["codigo"] == "sin_permiso"


async def test_cerrar_pide_solucion_y_deja_las_dos_fechas(db, api):
    """La nota es obligatoria y el cierre deja constancia de las dos fechas.

    «Resuelto» ya no es un estado: cerrar es un solo paso. Pero las dos fechas se
    siguen escribiendo, porque de ellas salen los tiempos de resolución y el SLA.
    """
    mundo = await _mundo(api, "cierre_nota")
    ticket = await _ticket(api, mundo, "nota")
    tid = ticket["id"]

    sin_nota = await api.post(f"/api/tickets/{tid}/estado", json={"estado": "cerrado"}, headers=mundo["tec1"])
    assert sin_nota.status_code == 422, "sin solución no se cierra"
    assert "solución" in sin_nota.json()["mensaje"].lower()

    cerrado = await api.post(
        f"/api/tickets/{tid}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Se cambió la fuente de poder."},
        headers=mundo["tec1"],
    )
    assert cerrado.status_code == 200, cerrado.text

    detalle = (await api.get(f"/api/tickets/{tid}", headers=mundo["tec1"])).json()
    assert detalle["estado"] == "cerrado"
    assert detalle["nota_resolucion"] == "Se cambió la fuente de poder."
    assert detalle["resuelto_en"] and detalle["cerrado_en"], "el cierre deja las dos fechas"
    assert detalle["tiempo_resolucion_min"] is not None, "y con ellas, el tiempo que se tardó"


async def test_reabrir_requiere_confirmacion_y_deja_rastro(db, api):
    """Reabrir un ticket cerrado exige permiso y queda anotado en el historial."""
    mundo = await _mundo(api, "reapertura")
    ticket = await _ticket(api, mundo, "reapertura")
    tid = ticket["id"]

    await api.post(
        f"/api/tickets/{tid}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Se reinició el equipo."},
        headers=mundo["tec1"],
    )

    detalle = (await api.get(f"/api/tickets/{tid}", headers=mundo["tec1"])).json()
    assert detalle["estado"] == "cerrado"

    reabrir = await api.post(f"/api/tickets/{tid}/estado", json={"estado": "en_progreso"}, headers=mundo["tec1"])
    assert reabrir.status_code == 200, reabrir.text

    tras = (await api.get(f"/api/tickets/{tid}", headers=mundo["tec1"])).json()
    assert tras["estado"] == "en_progreso"
    assert tras["veces_reabierto"] == 1, "queda cuenta de cuántas veces se reabrió"
    assert tras["puede_reabrir"] is True


async def test_el_aviso_de_resolucion_lleva_el_ticket_que_se_puede_abrir(db, api):
    """El aviso de la campana tiene que decir a qué caso lleva.

    El campo `enlace` que guarda la API tiene la forma `/tickets/{id}`, que no
    corresponde a ninguna ruta: el panel usa `/panel/tickets/{id}` y el portal
    `/mis-tickets/{id}`. Por eso la interfaz arma la ruta con `ticket_id`, y este
    contrato es lo que hay que proteger para que el enlace siga funcionando.
    """
    mundo = await _mundo(api, "aviso")
    from app.services import usuario_service

    # El reporte lo hace la persona usuaria, así queda como reportante
    creado = await api.post(
        "/api/tickets",
        json={"descripcion": "la pantalla se queda en negro", "urgencia": "me_frena"},
        headers=mundo["persona"],
    )
    assert creado.status_code == 201, creado.text
    ticket_id = creado.json()["ticket"]["id"]
    codigo = creado.json()["ticket"]["codigo"]

    # El caso se asigna antes de cerrarse: quien cierra es su técnico, que es como
    # pasa en la vida real. Antes el test cerraba «sin estar asignado», porque para
    # pasar por «resuelto» no hacía falta el permiso; cerrar sí lo exige.
    encontrados = await usuario_service.buscar_global("tec1-aviso@prueba.local")
    assert encontrados, "el técnico de la prueba tiene que existir"
    asignar = await api.post(
        f"/api/tickets/{ticket_id}/asignar",
        # El técnico de la prueba no tiene horario, así que la asignación pide
        # confirmación; sin ella responde 200 pero no asigna nada.
        json={"tecnico_id": str(encontrados[0]["id"]), "confirmar_fuera_de_horario": True},
        headers=mundo["admin"],
    )
    assert asignar.status_code == 200, asignar.text
    # La respuesta es el ticket ya actualizado, no un envoltorio.
    assert asignar.json().get("tecnico_id"), f"la asignación tiene que quedar: {asignar.json()}"

    cerrar = await api.post(
        f"/api/tickets/{ticket_id}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Se cambió el cable de video."},
        headers=mundo["tec1"],
    )
    assert cerrar.status_code == 200, cerrar.text

    campana = await api.get("/api/notificaciones", headers=mundo["persona"])
    assert campana.status_code == 200, campana.text
    cuerpo = campana.json()
    assert cuerpo["no_leidas"] >= 1, "cerrar un caso avisa a quien lo reportó"

    aviso = cuerpo["items"][0]
    assert aviso["ticket_id"] == ticket_id, "el aviso tiene que señalar el ticket"
    assert aviso["titulo"].endswith(codigo), f"el aviso identifica el caso: {aviso['titulo']!r}"

    # Y se puede marcar solo ese, que es lo que hace la campana al pulsarlo
    marcadas = await api.post("/api/notificaciones/leer", params={"ids": aviso["id"]}, headers=mundo["persona"])
    assert marcadas.status_code == 200, marcadas.text
    assert marcadas.json()["actualizadas"] == 1

    despues = (await api.get("/api/notificaciones", headers=mundo["persona"])).json()
    assert all(item["leida"] for item in despues["items"] if item["id"] == aviso["id"])
    assert despues["no_leidas"] == cuerpo["no_leidas"] - 1, "el contador baja uno, no todos"


async def test_cerrar_avisa_una_sola_vez(db, api):
    """Un cierre, un aviso. Ni dos, ni tres.

    En la base de la municipalidad hay cuatro tickets con **dos** avisos de
    «Problema resuelto» cada uno. TKT-2026-000071 los tiene con **40 segundos de
    diferencia** y TKT-2026-000072 con **17**, con el ticket cerrado una sola vez:
    `cerrado_en` coincide con el primer aviso y el segundo no cambió nada. Eso no
    es que alguien cerrara, abriera y cerrara otra vez —eso dejaría una
    reapertura en la línea de tiempo—, es el mismo cierre contando dos veces.

    Por eso la prueba comprueba la **cantidad exacta**, no que haya al menos uno.
    Con «>= 1» el duplicado pasaba inadvertido.
    """
    mundo = await _mundo(api, "aviso_unico")
    from app.services import usuario_service

    creado = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["persona_id"], "detectado_por_tec": True},
            "asunto": "la compu se apaga de golpe",
            "activo_id": await equipo_para_persona(api, mundo["admin"], mundo["persona_id"]),
        },
        headers=mundo["admin"],
    )
    assert creado.status_code == 201, creado.text
    ticket_id = creado.json()["ticket"]["id"]

    # Quien cierra tiene que ser el técnico asignado: cerrar el caso de otra
    # persona da 403, así que el caso se asigna antes.
    encontrados = await usuario_service.buscar_global("tec1-aviso_unico@prueba.local")
    assert encontrados, "el técnico de la prueba tiene que existir"
    asignar = await api.post(
        f"/api/tickets/{ticket_id}/asignar",
        json={"tecnico_id": str(encontrados[0]["id"]), "confirmar_fuera_de_horario": True},
        headers=mundo["admin"],
    )
    assert asignar.status_code == 200, asignar.text

    cerrar = await api.post(
        f"/api/tickets/{ticket_id}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Se cambió la fuente de poder."},
        headers=mundo["tec1"],
    )
    assert cerrar.status_code == 200, cerrar.text

    campana = await api.get("/api/notificaciones", headers=mundo["persona"])
    assert campana.status_code == 200, campana.text

    avisos = [item for item in campana.json()["items"] if item.get("ticket_id") == ticket_id]
    assert len(avisos) == 1, f"un cierre debe dejar un aviso, y dejaron {len(avisos)}"

    # Y cerrarlo otra vez —o intentar— no puede añadir un segundo aviso.
    repetir = await api.post(
        f"/api/tickets/{ticket_id}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Otra vez."},
        headers=mundo["tec1"],
    )
    assert repetir.status_code in (200, 409), repetir.text
    tras = [
        item
        for item in (await api.get("/api/notificaciones", headers=mundo["persona"])).json()["items"]
        if item.get("ticket_id") == ticket_id
    ]
    assert len(tras) == 1, f"volver a cerrar no puede añadir otro aviso, y hay {len(tras)}"


async def test_un_ticket_cerrado_no_aparece_en_la_cola_activa(db, api):
    """Cerrado sale de la cola y es el estado terminal del archivo."""
    mundo = await _mundo(api, "cola")
    ticket = await _ticket(api, mundo, "cola")
    tid = ticket["id"]

    await api.post(
        f"/api/tickets/{tid}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Se limpió la impresora."},
        headers=mundo["tec1"],
    )

    abiertos = await api.get("/api/tickets", params={"solo_abiertos": "true", "por_pagina": 100}, headers=mundo["tec1"])
    assert tid not in {item["id"] for item in abiertos.json()["items"]}, "un ticket cerrado no sigue en la cola"

    historial = await api.get(
        "/api/tickets",
        params=[("estado", "cerrado"), ("por_pagina", 100)],
        headers=mundo["tec1"],
    )
    assert tid in {item["id"] for item in historial.json()["items"]}, "pero sí aparece en el historial"
