"""Matriz de autorizacion por endpoint y por rol, con identificadores ajenos.

Cubre administrador, tecnico, trabajador (rol ``usuario``) y sin sesion contra
objetos de otra persona: tickets, adjuntos, equipos, usuarios, conversaciones
del Chatbot TI y del asistente de analisis, reportes, exportaciones y auditoria.

Cada fila fija el contrato vigente. Lo que queda abierto a proposito —o por
decision pendiente— esta marcado con un comentario y se lista en
``docs/evidencias/autorizacion/01-hallazgos.md``. Nunca se oculta un boton del
frontend como sustituto de estas comprobaciones.
"""

from __future__ import annotations

from bson import ObjectId

from app.services import conversaciones_chatbot
from tests.conftest import PASSWORD, crear_admin, crear_tecnico, crear_usuario

SIN_SESION: dict[str, str] = {}


async def _sesion(api, correo: str) -> dict[str, str]:
    respuesta = await api.post("/api/auth/login", json={"correo": correo, "password": PASSWORD})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    return {"Authorization": f"Bearer {datos['access_token']}", "X-CSRF-Token": datos["csrf_token"]}


async def _subir(api, cabeceras: dict[str, str], *, ambito: str = "ticket", nombre: str = "nota.txt") -> str:
    respuesta = await api.post(
        f"/api/adjuntos?ambito={ambito}",
        headers=cabeceras,
        files={"archivo": (nombre, b"contenido de prueba", "text/plain")},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


async def _ticket_de(api, cabeceras: dict[str, str], descripcion: str) -> dict:
    respuesta = await api.post(
        "/api/tickets",
        json={"tipo_problema": "No enciende", "descripcion": descripcion, "urgencia": "me_frena"},
        headers=cabeceras,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["ticket"]


async def _preparar(db, api) -> dict:
    """Mundo con dos tecnicos y dos trabajadores de la misma oficina."""
    await crear_admin(db)
    cab = {"admin": await _sesion(api, "admin@prueba.local")}
    zona = (await api.post("/api/zonas", json={"nombre": "Zona matriz"}, headers=cab["admin"])).json()
    oficina = (
        await api.post("/api/oficinas", json={"nombre": "COMUNA", "zona_id": zona["id"]}, headers=cab["admin"])
    ).json()
    tecnico_a = await crear_tecnico(db, "Tecnico Matriz A", "tec-a@prueba.local", oficina["id"])
    tecnico_b = await crear_tecnico(db, "Tecnico Matriz B", "tec-b@prueba.local", oficina["id"])
    usuario_a = await crear_usuario(db, "Usuario Matriz A", "usr-a@prueba.local", oficina["id"])
    usuario_b = await crear_usuario(db, "Usuario Matriz B", "usr-b@prueba.local", oficina["id"])
    for rol, correo in (
        ("tecnico", "tec-a@prueba.local"),
        ("tecnico_b", "tec-b@prueba.local"),
        ("usuario", "usr-a@prueba.local"),
        ("usuario_b", "usr-b@prueba.local"),
    ):
        cab[rol] = await _sesion(api, correo)
    cab["sin_sesion"] = SIN_SESION

    # Los tecnicos reciben los permisos delegables que habilitan analitica y
    # exportaciones: asi la matriz mide aislamiento por dueno, no solo permisos.
    for tecnico in (tecnico_a, tecnico_b):
        cambio = await api.put(
            f"/api/permisos/tecnicos/{tecnico['_id']}",
            json={"cambios": {"analitica.ver": True, "exportar": True, "reportes.ver": True}},
            headers=cab["admin"],
        )
        assert cambio.status_code == 200, cambio.text

    ticket_a = await _ticket_de(api, cab["usuario"], "Equipo de A")
    ticket_b = await _ticket_de(api, cab["usuario_b"], "Equipo de B")

    # Adjunto de B dentro de su ticket (el de A solo para el dueno).
    libre_b = await _subir(api, cab["usuario_b"])
    vinculado_b = await _subir(api, cab["usuario_b"])
    creado_b = await api.post(
        "/api/tickets",
        json={
            "tipo_problema": "No enciende",
            "descripcion": "Ticket con adjunto de B",
            "urgencia": "me_frena",
            "adjuntos": [vinculado_b],
        },
        headers=cab["usuario_b"],
    )
    assert creado_b.status_code == 201, creado_b.text

    # Nota interna con adjunto de ambito "nota" (solo equipo TI).
    adjunto_nota = await _subir(api, cab["tecnico"], ambito="nota", nombre="nota.txt")
    nota = await api.post(
        f"/api/tickets/{ticket_a['id']}/notas",
        json={"cuerpo": "Revisado en sitio", "adjuntos": [adjunto_nota]},
        headers=cab["tecnico"],
    )
    assert nota.status_code == 200, nota.text

    # Adjunto de conocimiento: lo comparte cualquier sesion (documentado).
    adjunto_kb = await _subir(api, cab["tecnico"], ambito="kb", nombre="guia.txt")

    equipo = (
        await api.post(
            "/api/activos",
            json={
                "tipo": "CPU",
                "oficina_id": oficina["id"],
                "responsable_id": str(usuario_a["_id"]),
                "nombre_equipo": "PC de A",
            },
            headers=cab["admin"],
        )
    ).json()

    conversacion_chatbot = await conversaciones_chatbot.crear(tecnico_a, "Consulta de A")
    creada_ia = await api.post(
        "/api/ia/asistente", json={"pregunta": "Resumen del servicio hoy"}, headers=cab["tecnico"]
    )
    assert creada_ia.status_code == 200, creada_ia.text
    conversacion_ia = creada_ia.json()["conversacion_id"]

    exportacion = await api.post(
        "/api/exportaciones", json={"tipo": "tickets", "formato": "csv", "filtros": {}}, headers=cab["admin"]
    )
    assert exportacion.status_code == 200, exportacion.text

    return {
        "cabeceras": cab,
        "ids": {
            "ticket_ajeno": ticket_b["id"],
            "ticket_propio": ticket_a["id"],
            "equipo": equipo["id"],
            "usuario_ajeno": str(usuario_b["_id"]),
            "usuario_propio": str(usuario_a["_id"]),
            "adjunto_libre_ajeno": libre_b,
            "adjunto_vinculado_ajeno": vinculado_b,
            "adjunto_nota": adjunto_nota,
            "adjunto_kb": adjunto_kb,
            "conversacion_chatbot": str(conversacion_chatbot["id"]),
            "conversacion_ia": conversacion_ia,
            "exportacion": exportacion.json()["id"],
        },
    }


# (rol, metodo, ruta, esperado, cuerpo)
CASOS: list[tuple[str, str, str, int, dict | None]] = [
    # ── Tickets ──────────────────────────────────────────────
    ("sin_sesion", "GET", "/api/tickets/{ticket_ajeno}", 401, None),
    ("usuario", "GET", "/api/tickets/{ticket_ajeno}", 403, None),
    # El equipo TI ve todos los tickets a proposito; no se restringe.
    ("tecnico", "GET", "/api/tickets/{ticket_ajeno}", 200, None),
    ("admin", "GET", "/api/tickets/{ticket_ajeno}", 200, None),
    ("usuario", "GET", "/api/tickets/{ticket_ajeno}/mensajes", 403, None),
    ("usuario", "GET", "/api/tickets/{ticket_ajeno}/notas", 403, None),
    ("usuario", "GET", "/api/tickets/{ticket_ajeno}/ia", 403, None),
    ("usuario", "POST", "/api/tickets/{ticket_ajeno}/estado", 403, {"estado": "en_progreso"}),
    ("usuario", "POST", "/api/tickets/{ticket_ajeno}/eliminar", 403, {"motivo": "prueba"}),
    ("sin_sesion", "POST", "/api/tickets", 401, {"descripcion": "Sin sesion"}),
    # ── Adjuntos ─────────────────────────────────────────────
    ("sin_sesion", "GET", "/api/adjuntos/{adjunto_kb}", 401, None),
    ("usuario", "GET", "/api/adjuntos/{adjunto_libre_ajeno}", 403, None),
    ("usuario", "GET", "/api/adjuntos/{adjunto_vinculado_ajeno}", 403, None),
    ("tecnico", "GET", "/api/adjuntos/{adjunto_vinculado_ajeno}", 200, None),
    ("usuario", "GET", "/api/adjuntos/{adjunto_nota}", 403, None),
    ("tecnico", "GET", "/api/adjuntos/{adjunto_nota}", 200, None),
    # Abierto a proposito: el conocimiento es comun a cualquier sesion.
    ("usuario", "GET", "/api/adjuntos/{adjunto_kb}", 200, None),
    # ── Equipos ──────────────────────────────────────────────
    # HAY HALLAZGO: el inventario completo se sirve a cualquier trabajador.
    ("usuario", "GET", "/api/activos/{equipo}", 200, None),
    ("usuario", "PATCH", "/api/activos/{equipo}", 403, {"nombre_equipo": "Cambiado"}),
    ("usuario", "GET", "/api/equipos/de-persona/{usuario_ajeno}", 403, None),
    ("tecnico", "GET", "/api/equipos/de-persona/{usuario_ajeno}", 200, None),
    # ── Usuarios ─────────────────────────────────────────────
    ("sin_sesion", "GET", "/api/usuarios/{usuario_ajeno}", 401, None),
    ("usuario", "GET", "/api/usuarios/{usuario_ajeno}", 403, None),
    ("usuario", "GET", "/api/usuarios", 403, None),
    ("usuario", "GET", "/api/usuarios/{usuario_ajeno}/dispositivos", 403, None),
    ("usuario", "GET", "/api/usuarios/{usuario_ajeno}/foto", 403, None),
    ("usuario", "PATCH", "/api/usuarios/{usuario_ajeno}", 403, {"nombre": "Cambiado"}),
    ("tecnico", "GET", "/api/usuarios/{usuario_ajeno}", 200, None),
    ("admin", "GET", "/api/usuarios/{usuario_ajeno}", 200, None),
    # ── Chatbot TI ───────────────────────────────────────────
    ("usuario", "GET", "/api/ia/chatbot/conversaciones/{conversacion_chatbot}", 403, None),
    ("tecnico_b", "GET", "/api/ia/chatbot/conversaciones/{conversacion_chatbot}", 404, None),
    ("tecnico_b", "DELETE", "/api/ia/chatbot/conversaciones/{conversacion_chatbot}", 404, None),
    # ── Analisis IA ──────────────────────────────────────────
    ("usuario", "GET", "/api/ia/asistente/conversaciones/{conversacion_ia}", 403, None),
    ("tecnico_b", "GET", "/api/ia/asistente/conversaciones/{conversacion_ia}", 404, None),
    ("tecnico_b", "DELETE", "/api/ia/asistente/conversaciones/{conversacion_ia}", 404, None),
    # ── Reportes ─────────────────────────────────────────────
    ("usuario", "GET", "/api/analitica/panel", 403, None),
    ("tecnico", "GET", "/api/analitica/resumen", 200, None),
    ("admin", "GET", "/api/analitica/panel", 200, None),
    # ── Exportaciones ────────────────────────────────────────
    ("usuario", "GET", "/api/exportaciones", 403, None),
    ("usuario", "POST", "/api/exportaciones", 403, {"tipo": "tickets", "formato": "csv"}),
    ("tecnico_b", "GET", "/api/exportaciones/{exportacion}/descargar", 403, None),
    ("tecnico_b", "DELETE", "/api/exportaciones/{exportacion}", 403, None),
    ("admin", "GET", "/api/exportaciones/{exportacion}/descargar", 200, None),
    # ── Auditoria ────────────────────────────────────────────
    ("sin_sesion", "GET", "/api/auditoria", 401, None),
    ("usuario", "GET", "/api/auditoria", 403, None),
    # Con reportes.ver delegado sigue sin poder leerla: exige administrador.
    ("tecnico", "GET", "/api/auditoria", 403, None),
    ("admin", "GET", "/api/auditoria", 200, None),
]


async def test_matriz_de_autorizacion_por_rol(db, api):
    mundo = await _preparar(db, api)
    fallos: list[str] = []
    for rol, metodo, ruta, esperado, cuerpo in CASOS:
        destino = ruta.format(**mundo["ids"])
        respuesta = await api.request(
            metodo, destino, headers=mundo["cabeceras"][rol], json=cuerpo
        )
        if respuesta.status_code != esperado:
            fallos.append(
                f"{rol:10} {metodo:6} {destino}: {respuesta.status_code} (se esperaba {esperado}) -> {respuesta.text[:160]}"
            )
    assert not fallos, "Filas de la matriz que no cumplen:\n" + "\n".join(fallos)


async def test_adjunto_ajeno_no_se_puede_secuestrar_al_crear_ticket(db, api):
    """Un trabajador no puede quedarse el adjunto libre de otro pasando su id."""
    mundo = await _preparar(db, api)
    ajeno = mundo["ids"]["adjunto_libre_ajeno"]
    intento = await api.post(
        "/api/tickets",
        json={
            "tipo_problema": "No enciende",
            "descripcion": "Intento con un adjunto ajeno",
            "urgencia": "me_frena",
            "adjuntos": [ajeno],
        },
        headers=mundo["cabeceras"]["usuario"],
    )
    assert intento.status_code == 403, intento.text
    assert intento.json()["codigo"] != "error_interno"
    # Y el archivo sigue siendo de su dueno, sin ticket asociado.
    documento = await db["adjuntos"].find_one({"_id": ObjectId(ajeno)})
    assert documento["ticket_id"] is None
    assert documento["subido_por"] != ObjectId(mundo["ids"]["usuario_propio"])


async def test_exportacion_con_permiso_no_abre_la_auditoria_por_la_puerta_de_atras(db, api):
    """Hallazgo documentado: exportar auditoria no exige administrador.

    ``GET /api/auditoria`` si lo exige (fila de la matriz), pero el tipo
    ``auditoria`` de ``POST /api/exportaciones`` solo pide ``reportes.ver`` y
    ``exportar``, permisos delegables a un tecnico. Se deja fijado aqui para que
    el cambio de criterio, si se decide, rompa esta prueba primero.
    """
    mundo = await _preparar(db, api)
    creada = await api.post(
        "/api/exportaciones",
        json={"tipo": "auditoria", "formato": "csv", "filtros": {}},
        headers=mundo["cabeceras"]["tecnico"],
    )
    assert creada.status_code == 200, creada.text
