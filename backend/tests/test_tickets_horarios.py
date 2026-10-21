"""Tickets en 2 pasos, chat condicionado al origen, horarios y disponibilidad."""

from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import PASSWORD, equipo_para_persona


async def _sesion(api, correo: str, password: str = PASSWORD) -> dict[str, str]:
    respuesta = await api.post("/api/auth/login", json={"correo": correo, "password": password})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    return {"Authorization": f"Bearer {datos['access_token']}", "X-CSRF-Token": datos["csrf_token"]}


async def _mundo(api, sufijo: str):
    """Crea zona, oficinas, un técnico y dos usuarios; devuelve ids y cabeceras."""
    from app.services import usuario_service

    await usuario_service.crear(
        {"nombre": f"Admin {sufijo}", "email": f"admin-{sufijo}@prueba.local", "password": PASSWORD, "rol": "administrador"},
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
    usuario = (
        await api.post(
            "/api/usuarios",
            json={
                "nombre": f"Usuario {sufijo}",
                "email": f"usuario-{sufijo}@prueba.local",
                "password": PASSWORD,
                "rol": "usuario",
                "oficina_id": oficina["id"],
            },
            headers=cab_admin,
        )
    ).json()
    companero = (
        await api.post(
            "/api/usuarios",
            json={
                "nombre": f"Companero {sufijo}",
                "email": f"companero-{sufijo}@prueba.local",
                "password": PASSWORD,
                "rol": "usuario",
                "oficina_id": oficina["id"],
            },
            headers=cab_admin,
        )
    ).json()
    return {
        "admin": cab_admin,
        "tecnico": await _sesion(api, f"tecnico-{sufijo}@prueba.local"),
        "usuario": await _sesion(api, f"usuario-{sufijo}@prueba.local"),
        "zona": zona,
        "oficina": oficina,
        "tecnico_id": tecnico["id"],
        "usuario_id": usuario["id"],
        "companero_id": companero["id"],
    }


async def test_ticket_usuario_dos_pasos_para_companero(db, api):
    mundo = await _mundo(api, "dospasos")

    ajustes = (await api.get("/api/tickets/ajustes-crear", headers=mundo["usuario"])).json()
    assert ajustes["categorias"], "el formulario necesita las categorias"
    assert {u["clave"] for u in ajustes["urgencias"]} == {"puede_esperar", "me_frena", "no_puedo_trabajar"}

    companeros = (await api.get("/api/usuarios/companeros", headers=mundo["usuario"])).json()
    nombres = {c["nombre"] for c in companeros["items"]}
    assert any("Companero dospasos" in n for n in nombres), "lista los compañeros de la oficina"
    assert all(c.get("iniciales") for c in companeros["items"]), "muestra iniciales para elegir"

    creado = await api.post(
        "/api/tickets",
        json={
            "tipo_problema": "No enciende",
            "descripcion": "La computadora no prende.",
            "persona": {"es_para_mi": False, "afectado_id": mundo["companero_id"]},
            "urgencia": "no_puedo_trabajar",
        },
        headers=mundo["usuario"],
    )
    assert creado.status_code == 201, creado.text
    cuerpo = creado.json()
    assert cuerpo["ticket"]["tiene_chat"] is True
    assert cuerpo["tiempo_esperado"], "explica el tiempo esperado en lenguaje simple"
    assert cuerpo["enlace_seguimiento"].startswith("/mis-tickets/")

    detalle = (await api.get(f"/api/tickets/{cuerpo['ticket']['id']}", headers=mundo["tecnico"])).json()
    assert detalle["afectado_id"] == mundo["companero_id"], "guarda a quien afecta"
    assert detalle["reportante_id"] == mundo["usuario_id"], "guarda quien reporta"
    assert detalle["reportante_id"] != detalle["afectado_id"]
    assert detalle["origen"] == "usuario_por_companero"
    assert detalle["prioridad"] == "alta", "la urgencia define la prioridad inicial"
    assert detalle["zona_id"] == mundo["zona"]["id"], "la zona se toma del afectado"
    assert detalle["oficina_id"] == mundo["oficina"]["id"]

    # El afectado puede ver el estado en solo lectura y escribir en el chat
    cab_afectado = await _sesion(api, "companero-dospasos@prueba.local")
    visto = await api.get(f"/api/tickets/{cuerpo['ticket']['id']}", headers=cab_afectado)
    assert visto.status_code == 200
    assert visto.json().get("solo_lectura") is True
    assert "notas_internas" not in visto.json(), "el usuario nunca ve notas internas"


 
    # "Otra persona" sin cuenta: nombre suelto
    sin_registrar = await api.post(
        "/api/tickets",
        json={
            "tipo_problema": "Internet/red",
            "persona": {
                "es_para_mi": False,
                "persona_no_registrada": {"nombre": "Visitante Externo"},
            },
            "urgencia": "me_frena",
        },
        headers=mundo["usuario"],
    )
    assert sin_registrar.status_code == 403, sin_registrar.text

    # Mensaje de la persona afectada
    mensaje = await api.post(
        f"/api/tickets/{cuerpo['ticket']['id']}/mensajes",
        json={"cuerpo": "Hola, sigue sin prender."},
        headers=cab_afectado,
    )
    assert mensaje.status_code == 201
    mensajes = (await api.get(f"/api/tickets/{cuerpo['ticket']['id']}/mensajes", headers=mundo["tecnico"])).json()
    assert [m["cuerpo"] for m in mensajes["items"]] == ["Hola, sigue sin prender."]


async def test_resumen_usuario_cuenta_todos_los_estados(db, api):
    mundo = await _mundo(api, "resumen_usuario")

    async def crear_ticket(asunto: str):
        return await api.post(
            "/api/tickets",
            json={
                "tipo_problema": "No enciende",
                "descripcion": asunto,
                "persona": {"es_para_mi": True, "afectado_id": mundo["usuario_id"]},
                "urgencia": "me_frena",
            },
            headers=mundo["usuario"],
        )

    nuevo = await crear_ticket("La computadora no enciende.")
    atendiendo = await crear_ticket("El equipo no prende desde la mañana.")
    cerrado = await crear_ticket("La computadora muestra una pantalla apagada.")
    assert all(respuesta.status_code == 201 for respuesta in (nuevo, atendiendo, cerrado))

    for respuesta, estado in ((atendiendo, "en_progreso"), (cerrado, "cerrado")):
        cambio = await api.post(
            f"/api/tickets/{respuesta.json()['ticket']['id']}/estado",
            json={"estado": estado, "nota_resolucion": "Verificado en la prueba." if estado == "cerrado" else None},
            headers=mundo["admin"],
        )
        assert cambio.status_code == 200, cambio.text

    resumen = await api.get("/api/tickets/resumen", headers=mundo["usuario"])
    assert resumen.status_code == 200, resumen.text
    assert resumen.json() == {"es_usuario": True, "abiertos": 2, "en_atencion": 1, "resueltos": 1}


async def test_cerrar_desde_cualquier_estado_activo_deja_cierre_y_aparece_en_historial(db, api):
    mundo = await _mundo(api, "cierre_directo")
    activo = await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "CPU de prueba"},
        headers=mundo["admin"],
    )
    assert activo.status_code == 201, activo.text
    creados = []

    for indice, estado in enumerate(("nuevo", "en_progreso", "en_espera")):
        respuesta = await api.post(
            "/api/tickets",
            json={
                "tipo_problema": "No enciende",
                "descripcion": f"Prueba de cierre {indice}.",
                "persona": {"es_para_mi": True, "afectado_id": mundo["usuario_id"]},
                "activo_id": activo.json()["id"],
                "urgencia": "me_frena",
            },
            headers=mundo["usuario"],
        )
        assert respuesta.status_code == 201, respuesta.text
        ticket_id = respuesta.json()["ticket"]["id"]
        creados.append(ticket_id)
        if estado != "nuevo":
            cambio = await api.post(
                f"/api/tickets/{ticket_id}/estado",
                json={"estado": estado},
                headers=mundo["admin"],
            )
            assert cambio.status_code == 200, cambio.text

        cierre = await api.post(
            f"/api/tickets/{ticket_id}/estado",
            json={"estado": "cerrado", "nota_resolucion": "Se verificó el funcionamiento del equipo."},
            headers=mundo["admin"],
        )
        assert cierre.status_code == 200, cierre.text
        assert cierre.json()["estado"] == "cerrado"
        assert cierre.json()["nota_resolucion"] == "Se verificó el funcionamiento del equipo."
        assert cierre.json()["resuelto_en"] and cierre.json()["cerrado_en"]

    en_historial = await api.post(
        "/api/tickets",
        json={
            "tipo_problema": "No enciende",
            "descripcion": "Ticket ya cerrado para el historial.",
            "persona": {"es_para_mi": True, "afectado_id": mundo["usuario_id"]},
            "activo_id": activo.json()["id"],
            "urgencia": "me_frena",
        },
        headers=mundo["usuario"],
    )
    assert en_historial.status_code == 201, en_historial.text
    historial_id = en_historial.json()["ticket"]["id"]
    creados.append(historial_id)
    cambio_historial = await api.post(
        f"/api/tickets/{historial_id}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Equipo comprobado."},
        headers=mundo["admin"],
    )
    assert cambio_historial.status_code == 200, cambio_historial.text

    activos = await api.get("/api/tickets?solo_abiertos=true", headers=mundo["admin"])
    assert not set(creados).intersection(ticket["id"] for ticket in activos.json()["items"])

    historial = await api.get(
        "/api/tickets",
        params=[("estado", "cerrado"), ("por_pagina", "25")],
        headers=mundo["admin"],
    )
    assert historial.status_code == 200, historial.text
    assert {ticket["id"] for ticket in historial.json()["items"]} >= set(creados)
    assert all(ticket["activo_nombre"] == "CPU de prueba" for ticket in historial.json()["items"])


async def test_ticket_eliminado_desaparece_de_la_cola(db, api):
    """El borrado es lógico, pero el ticket no puede seguir en la bandeja.

    Regresión: `eliminar` marca `eliminado: True` y `listar` no lo excluía, así que
    la API respondía «Ticket eliminado» y el caso seguía en la cola.
    """
    mundo = await _mundo(api, "eliminado")
    activo = await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "CPU de la baja"},
        headers=mundo["admin"],
    )
    assert activo.status_code == 201, activo.text
    creado = await api.post(
        "/api/tickets",
        json={
            "tipo_problema": "No enciende",
            "descripcion": "Ticket que se va a eliminar.",
            "persona": {"es_para_mi": True, "afectado_id": mundo["usuario_id"]},
            "activo_id": activo.json()["id"],
            "urgencia": "me_frena",
        },
        headers=mundo["usuario"],
    )
    assert creado.status_code == 201, creado.text
    ticket_id = creado.json()["ticket"]["id"]

    antes = await api.get("/api/tickets", params={"por_pagina": 100}, headers=mundo["admin"])
    assert ticket_id in {item["id"] for item in antes.json()["items"]}

    borrado = await api.post(f"/api/tickets/{ticket_id}/eliminar", headers=mundo["admin"])
    assert borrado.status_code == 200, borrado.text

    despues = await api.get("/api/tickets", params={"por_pagina": 100}, headers=mundo["admin"])
    assert ticket_id not in {item["id"] for item in despues.json()["items"]}

    # Tampoco en el resumen de la bandeja, ni con una vista rápida
    resumen = await api.get("/api/tickets/resumen", headers=mundo["admin"])
    assert resumen.status_code == 200, resumen.text

    detalle = await api.get(f"/api/tickets/{ticket_id}", headers=mundo["admin"])
    assert detalle.status_code == 404, detalle.text


async def test_ticket_por_usuario_para_mi(db, api):
    mundo = await _mundo(api, "parami")
    creado = await api.post(
        "/api/tickets",
        json={"tipo_problema": "Impresora", "urgencia": "puede_esperar"},
        headers=mundo["usuario"],
    )
    assert creado.status_code == 201, creado.text
    ticket = creado.json()["ticket"]
    assert ticket["tiene_chat"] is True
    assert ticket["prioridad"] == "baja"
    detalle = (await api.get(f"/api/tickets/{ticket['id']}", headers=mundo["usuario"])).json()
    assert detalle["afectado_id"] == detalle["reportante_id"] == mundo["usuario_id"]


async def test_chat_solo_si_lo_reporto_un_usuario(db, api):
    mundo = await _mundo(api, "chatorigen")

    # 1) Reportado por un usuario: hay chat
    de_usuario = await api.post(
        "/api/tickets",
        json={"tipo_problema": "Correo/cuenta", "urgencia": "me_frena"},
        headers=mundo["usuario"],
    )
    ticket_usuario = de_usuario.json()["ticket"]
    assert ticket_usuario["tiene_chat"] is True
    permitido = await api.post(
        f"/api/tickets/{ticket_usuario['id']}/mensajes",
        json={"cuerpo": "No puedo entrar a mi correo"},
        headers=mundo["usuario"],
    )
    assert permitido.status_code == 201

    # 2) Registrado por el técnico: NO hay chat y el backend lo rechaza
    manual = await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["usuario_id"], "detectado_por_tec": True},
            "asunto": "Revision de supervision",
            "activo_id": await equipo_para_persona(api, mundo["admin"], mundo["usuario_id"]),
            "descripcion": "El equipo no arranca; detectado por el equipo TI.",
            "prioridad": "media",
        },
        headers=mundo["tecnico"],
    )
    assert manual.status_code == 201, manual.text
    ticket_manual = manual.json()["ticket"]
    assert ticket_manual["tiene_chat"] is False
    assert manual.json()["sugerencia"], "sugiere pedir el reporte al usuario, sin bloquear"

    rechazo = await api.post(
        f"/api/tickets/{ticket_manual['id']}/mensajes",
        json={"cuerpo": "hola"},
        headers=mundo["tecnico"],
    )
    assert rechazo.status_code == 403, "el backend rechaza el chat en ticket sin chat"
    assert rechazo.json()["codigo"] == "sin_chat"

    listado = (await api.get(f"/api/tickets/{ticket_manual['id']}/mensajes", headers=mundo["tecnico"])).json()
    assert listado["items"] == []

    # Notas internas y nota de resolucion de una sola via
    nota = await api.post(
        f"/api/tickets/{ticket_manual['id']}/notas",
        json={"cuerpo": "Se reviso el cable de corriente."},
        headers=mundo["tecnico"],
    )
    assert nota.status_code == 201
    resolucion = await api.post(
        f"/api/tickets/{ticket_manual['id']}/estado",
        json={"estado": "cerrado", "nota_resolucion": "Se cambio el cable y el equipo arranca."},
        headers=mundo["tecnico"],
    )
    assert resolucion.status_code == 200
    assert resolucion.json()["nota_resolucion"]
    assert resolucion.json()["estado"] == "cerrado"

    # Cerrar sin nota de solucion no se permite
    otro = (await api.post(
        "/api/tickets/manual",
        json={
            "persona": {"afectado_id": mundo["usuario_id"]},
            "asunto": "Otro caso sin resolver",
            "activo_id": await equipo_para_persona(api, mundo["admin"], mundo["usuario_id"]),
            "prioridad": "baja",
        },
        headers=mundo["tecnico"],
    )).json()["ticket"]
    sin_nota = await api.post(
        f"/api/tickets/{otro['id']}/estado", json={"estado": "cerrado"}, headers=mundo["tecnico"]
    )
    assert sin_nota.status_code == 422

    # 3) Si el usuario confirma desde su cuenta, el chat se habilita con trazabilidad
    adopcion = await api.post(f"/api/tickets/{otro['id']}/confirmar", headers=mundo["usuario"])
    assert adopcion.status_code == 200
    assert adopcion.json()["tiene_chat"] is True
    ahora_si = await api.post(
        f"/api/tickets/{otro['id']}/mensajes", json={"cuerpo": "Confirmo que no enciende"}, headers=mundo["usuario"]
    )
    assert ahora_si.status_code == 201
    detalle = (await api.get(f"/api/tickets/{otro['id']}", headers=mundo["tecnico"])).json()
    tipos = [e["tipo"] for e in detalle["eventos"]]
    assert "chat_habilitado" in tipos, "queda registrado cuando se habilito el chat"


async def test_usuario_no_ve_tickets_de_otros(db, api):
    mundo = await _mundo(api, "privacidad")
    ajeno = (await api.post(
        "/api/tickets",
        json={"tipo_problema": "Equipo lento"},
        headers=mundo["usuario"],
    )).json()["ticket"]
    cab_tecnico = await _sesion(api, "tecnico-privacidad@prueba.local")
    # El tecnico ve la bandeja
    bandeja = (await api.get("/api/tickets", headers=cab_tecnico)).json()
    assert any(t["id"] == ajeno["id"] for t in bandeja["items"])

    # El usuario solo ve los suyos
    cab_usuario = mundo["usuario"]
    propios = (await api.get("/api/tickets", headers=cab_usuario)).json()
    assert all(t["id"] == ajeno["id"] for t in propios["items"])
    ajenos = await api.get(f"/api/tickets/{ajeno['id']}", headers=mundo["usuario"])
    assert ajenos.status_code == 200  # es el suyo


async def test_disponibilidad_con_horario_y_ausencias(db, api):
    mundo = await _mundo(api, "horarios")
    from app.core.time import utcnow, business_tz
    hoy = utcnow().astimezone(business_tz()).date()

    # Sin horario definido: fuera de horario
    await api.put(
        f"/api/equipo-ti/{mundo['tecnico_id']}/horario", json={"dias": {}}, headers=mundo["admin"]
    )
    panel = (await api.get("/api/equipo-ti/panel", headers=mundo["admin"])).json()
    tecnico = next(t for t in panel["items"] if t["tecnico_id"] == mundo["tecnico_id"])
    assert tecnico["estado"] in {"dia_libre", "fuera_de_horario"}, tecnico["estado"]

    # Horario de 08:00 a 18:00 **los siete dias**.
    # El indice interno es 0 = lunes ... 6 = domingo. Antes el horario era solo de
    # lunes a viernes y la prueba fallaba los fines de semana: un tecnico con
    # sabado libre sale «dia_libre», no «fuera_de_horario», y la asercion pedia lo
    # segundo. Una prueba que solo pasa de lunes a viernes no prueba nada, porque
    # la mitad de las ejecuciones son un falso negativo.
    dias = {str(d): {"tramos": [{"entrada": "08:00", "salida": "18:00"}], "libre": False} for d in range(7)}
    horario = await api.put(
        f"/api/equipo-ti/{mundo['tecnico_id']}/horario", json={"dias": dias}, headers=mundo["admin"]
    )
    assert horario.status_code == 200, horario.text

    # Dia libre explicito: se marca libre el dia de hoy, sea el que sea. Antes se
    # marcaban solo sabado y domingo, que es el mismo error por el otro lado: en
    # un dia laborable no se llegaba a comprobar nada.
    con_hoy_libre = dict(dias)
    con_hoy_libre[str(hoy.weekday())] = {"tramos": [], "libre": True}
    await api.put(f"/api/equipo-ti/{mundo['tecnico_id']}/horario", json={"dias": con_hoy_libre}, headers=mundo["admin"])

    panel = (await api.get("/api/equipo-ti/panel", headers=mundo["admin"])).json()
    tecnico = next(t for t in panel["items"] if t["tecnico_id"] == mundo["tecnico_id"])
    assert tecnico["estado"] == "dia_libre", tecnico["estado"]
    assert tecnico["etiqueta"] == "Dia libre"

    # Y quitando ese dia libre vuelve a estar disponible o fuera de horario
    await api.put(f"/api/equipo-ti/{mundo['tecnico_id']}/horario", json={"dias": dias}, headers=mundo["admin"])
    panel = (await api.get("/api/equipo-ti/panel", headers=mundo["admin"])).json()
    tecnico = next(t for t in panel["items"] if t["tecnico_id"] == mundo["tecnico_id"])
    assert tecnico["estado"] in {"disponible", "fuera_de_horario"}, tecnico["estado"]
    assert tecnico["etiqueta"] in {"Disponible", "Fuera de horario"}
    assert "horas_laborables_periodo" in tecnico["metricas"]

    # Ausencia hoy -> Ausente
    ausencia = await api.post(
        "/api/ausencias",
        json={
            "tecnico_id": mundo["tecnico_id"],
            "tipo": "Vacaciones",
            "inicio": hoy.isoformat(),
            "fin": (hoy + timedelta(days=2)).isoformat(),
        },
        headers=mundo["admin"],
    )
    assert ausencia.status_code == 201, ausencia.text
    panel = (await api.get("/api/equipo-ti/panel", headers=mundo["admin"])).json()
    tecnico = next(t for t in panel["items"] if t["tecnico_id"] == mundo["tecnico_id"])
    assert tecnico["estado"] == "ausente"
    assert tecnico["etiqueta"] == "Ausente"

    # Los dias libres y ausencias NO penalizan el rendimiento: las horas laborables lo excluyen
    metricas = tecnico["metricas"]
    assert metricas["horas_laborables_periodo"] >= 0
    assert "cumplimiento_sla" in metricas

    # Calendario del equipo
    respuesta_calendario = await api.get(
        f"/api/equipo-ti/calendario?desde={hoy.isoformat()}&hasta={(hoy + timedelta(days=7)).isoformat()}",
        headers=mundo["admin"],
    )
    assert respuesta_calendario.status_code == 200, respuesta_calendario.text
    calendario = respuesta_calendario.json()
    assert calendario["items"], "el calendario muestra el equipo"
    assert all("tecnico_nombre" in fila for fila in calendario["items"])


async def test_ausencias_filtradas_y_permisos_de_edicion(db, api):
    mundo = await _mundo(api, "permisos-ausencias")
    from app.core.time import business_tz, utcnow

    otro_tecnico = await api.post(
        "/api/usuarios",
        json={
            "nombre": "Tecnico adicional",
            "email": "tecnico-adicional-permisos-ausencias@prueba.local",
            "password": PASSWORD,
            "rol": "tecnico",
            "oficina_id": mundo["oficina"]["id"],
        },
        headers=mundo["admin"],
    )
    assert otro_tecnico.status_code == 201, otro_tecnico.text

    hoy = utcnow().astimezone(business_tz()).date()
    ausencia = await api.post(
        "/api/ausencias",
        json={
            "tecnico_id": otro_tecnico.json()["id"],
            "tipo": "Vacaciones",
            "inicio": hoy.isoformat(),
            "fin": (hoy + timedelta(days=2)).isoformat(),
        },
        headers=mundo["admin"],
    )
    assert ausencia.status_code == 201, ausencia.text
    ausencia_id = ausencia.json()["id"]

    filtradas = await api.get(
        f"/api/ausencias?tecnico_id={otro_tecnico.json()['id']}",
        headers=mundo["tecnico"],
    )
    assert filtradas.status_code == 200, filtradas.text
    assert [fila["id"] for fila in filtradas.json()["items"]] == [ausencia_id]

    sin_permiso = await api.delete(f"/api/ausencias/{ausencia_id}", headers=mundo["tecnico"])
    assert sin_permiso.status_code == 403, sin_permiso.text

    no_tecnico = await api.get("/api/ausencias", headers=mundo["usuario"])
    assert no_tecnico.status_code == 403, no_tecnico.text

    todo_el_equipo = await api.get("/api/ausencias", headers=mundo["admin"])
    assert todo_el_equipo.status_code == 200, todo_el_equipo.text
    assert ausencia_id in {fila["id"] for fila in todo_el_equipo.json()["items"]}


async def test_asignacion_fuera_de_horario_pide_confirmacion(db, api):
    mundo = await _mundo(api, "asignacion")
    ticket = (
        await api.post(
            "/api/tickets",
            json={"tipo_problema": "Impresora", "urgencia": "me_frena"},
            headers=mundo["usuario"],
        )
    ).json()["ticket"]

    # Sin horario: el sistema avisa y exige confirmacion
    respuesta = await api.post(
        f"/api/tickets/{ticket['id']}/asignar",
        json={"tecnico_id": mundo["tecnico_id"]},
        headers=mundo["tecnico"],
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    if cuerpo.get("requiere_confirmacion"):
        assert cuerpo["advertencia"]["requiere_confirmacion"] is True
        confirmado = await api.post(
            f"/api/tickets/{ticket['id']}/asignar",
            json={"tecnico_id": mundo["tecnico_id"], "confirmar_fuera_de_horario": True},
            headers=mundo["tecnico"],
        )
        assert confirmado.status_code == 200
        assert confirmado.json()["tecnico_id"] == mundo["tecnico_id"]


async def test_usuario_no_puede_asignar(db, api):
    mundo = await _mundo(api, "noasigna")
    ticket = (
        await api.post("/api/tickets", json={"tipo_problema": "Equipo lento"}, headers=mundo["usuario"])
    ).json()["ticket"]
    intento = await api.post(
        f"/api/tickets/{ticket['id']}/asignar",
        json={"tecnico_id": mundo["tecnico_id"]},
        headers=mundo["usuario"],
    )
    assert intento.status_code == 403
