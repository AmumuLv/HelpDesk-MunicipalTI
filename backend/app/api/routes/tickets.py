"""Rutas de tickets, chat condicionado al origen, notas, adjuntos y vistas guardadas."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import DependeUsuario, DependeUsuarioCsrf, id_opcional, requiere
from app.core.config import settings
from app.core.errors import Prohibido, Validacion
from app.core.ids import id_requerido, normalizar_texto
from app.domain.constants import (
    ESTADO_EN_ESPERA,
    ESTADO_EN_PROGRESO,
    ESTADOS_ABIERTOS,
    ESTADOS_CERRADOS,
    ESTADOS_TICKET,
    ORIGENES_TICKET,
    PRIORIDADES,
)
from app.schemas.tickets import (
    AsignarTicket,
    CambiarEstado,
    FiltrosTicket,
    MensajeCrear,
    NotaCrear,
    SugerenciaAplicar,
    TicketActualizar,
    TicketManualCrear,
    TicketUsuarioCrear,
    Valoracion,
    VistasGuardadas,
)
from app.services import (
    adjuntos_service,
    catalogo_service,
    ia_service,
    inventario_service,
    ticket_service,
    usuario_service,
)

router = APIRouter(tags=["tickets"])

DependeReasignar = Annotated[None, Depends(requiere("tickets.reasignar"))]
DependeCerrar = Annotated[None, Depends(requiere("tickets.cerrar_reabrir"))]
DependeEliminar = Annotated[None, Depends(requiere("tickets.eliminar"))]


def _datos_envio(datos: dict, request: Request) -> dict:
    clave = request.headers.get('Idempotency-Key')
    if clave:
        try:
            datos['_solicitud_id'] = str(UUID(clave))
        except ValueError:
            raise Validacion('El identificador del envío no es válido.')
    return datos


def _ip(request: Request) -> str:
    directo = request.headers.get("x-real-ip")
    if directo:
        return directo
    encadenado = request.headers.get("x-forwarded-for")
    return (encadenado.split(",")[0].strip() if encadenado else (request.client.host if request.client else None))


# ── Creacion ─────────────────────────────────────────────────
@router.post("/tickets", status_code=201)
async def crear_ticket_usuario(
    datos: TicketUsuarioCrear, request: Request, sesion: DependeUsuarioCsrf
):
    """Paso 1 + Paso 2 del reporte del usuario."""
    ticket = await ticket_service.crear_desde_usuario(
        _datos_envio(datos.model_dump(), request), usuario=sesion.usuario, ip=_ip(request)
    )
    detalle = await ticket_service.obtener(ticket["_id"], usuario=sesion.usuario)
    esperado = _tiempo_esperado(detalle)
    return {
        "ticket": {k: detalle.get(k) for k in ("id", "codigo", "estado", "prioridad", "afectado_nombre", "zona_nombre", "oficina_nombre", "tiene_chat", "sla")},
        "mensaje": "Problema reportado. El equipo de soporte ya lo puede ver.",
        "tiempo_esperado": esperado,
        "enlace_seguimiento": f"/mis-tickets/{ticket['_id']}",
    }


@router.get('/tickets/{ticket_id}/tecnico-perfil')
async def perfil_tecnico_asignado(ticket_id: str, sesion: DependeUsuario):
    from app.core.db import get_db
    from app.core.errors import NoEncontrado
    ticket = await ticket_service.obtener(id_requerido(ticket_id, 'ticket'), usuario=sesion.usuario)
    if not ticket.get('tecnico_id'):
        raise NoEncontrado('Este reporte todavía no tiene un técnico asignado.')
    tecnico_id = id_requerido(str(ticket['tecnico_id']), 'tecnico')
    db = get_db()
    tecnico = await db.usuarios.find_one({'_id': tecnico_id, 'rol': {'$in': ['tecnico', 'administrador']}}, {'nombre': 1, 'cargo': 1, 'oficina_id': 1})
    if not tecnico:
        raise NoEncontrado('El perfil del técnico no está disponible.')
    perfil = await db.tecnicos_perfil.find_one({'usuario_id': tecnico_id}, {'especialidades': 1}) or {}
    oficina = await db.oficinas.find_one({'_id': tecnico['oficina_id']}, {'nombre': 1}) if tecnico.get('oficina_id') else None
    return {'nombre': tecnico.get('nombre') or ticket.get('tecnico_nombre'), 'cargo': tecnico.get('cargo') or 'Soporte TI',
            'oficina': oficina.get('nombre') if oficina else None, 'especialidades': perfil.get('especialidades') or []}


def _tiempo_esperado(detalle: dict[str, Any]) -> str:
    sla = detalle.get("sla") or {}
    minutos = sla.get("minutos_restantes")
    if minutos is None:
        return "El equipo de soporte lo revisara en orden de llegada."
    if minutos <= 60:
        return "El equipo de soporte lo vera en menos de una hora (horario laboral)."
    if minutos <= 240:
        return "El equipo de soporte lo vera en unas horas (horario laboral)."
    horas = round(minutos / 60)
    if horas <= 24:
        return f"El equipo de soporte lo vera dentro de unas {horas} horas de trabajo."
    # Se habla de dias completos de trabajo, nunca de decimales
    dias = max(2, round(horas / 8))
    plural = "dia" if dias == 1 else "dias"
    return f"El equipo de soporte lo vera en unos {dias} {plural} de trabajo."


@router.post("/tickets/manual", status_code=201)
async def crear_ticket_manual(
    datos: TicketManualCrear, request: Request, sesion: DependeUsuarioCsrf
):
    sesion.exigir_tecnico()
    ticket = await ticket_service.crear_manual(_datos_envio(datos.model_dump(), request), usuario=sesion.usuario, ip=_ip(request))
    detalle = await ticket_service.obtener(ticket["_id"], usuario=sesion.usuario)
    return {
        "ticket": {k: detalle.get(k) for k in ("id", "codigo", "estado", "prioridad", "tiene_chat", "afectado_nombre")},
        "sugerencia": (
            "Registraste el problema por deteccion propia. Invita a la persona a reportarlo desde su cuenta "
            "para que quede mejor trazada."
            if datos.persona.detectado_por_tec
            else None
        ),
    }


@router.get("/tickets/ajustes-crear")
async def ajustes_crear(sesion: DependeUsuario):
    """Datos que necesitan los formularios de los dos pasos."""
    from app.services.categorias_ticket_service import categorias_activas, categoria_reporte
    categorias = await categorias_activas()
    tipos = await catalogo_service.tipos_existentes()
    zonas = []
    if sesion.usuario.get("zona_id"):
        zonas = [
            {
                "id": sesion.usuario["zona_id"],
                "nombre": sesion.usuario.get("zona_nombre"),
                "oficinas": await _oficinas_de_zona(sesion.usuario["zona_id"]),
            }
        ]
    return {
        "categorias": categorias,
        "tipos_equipo": tipos,
        "estados": await catalogo_service.listar("estados_activo"),
        "propiedades": await catalogo_service.listar("propiedades"),
        "urgencias": [
            {"clave": "puede_esperar", "titulo": "Puede esperar", "texto": "Puedo seguir trabajando"},
            {"clave": "me_frena", "titulo": "Me frena", "texto": "Me cuesta trabajar, pero puedo continuar"},
            {"clave": "no_puedo_trabajar", "titulo": "No puedo trabajar", "texto": "Me detiene por completo"},
        ],
        "tipos_problema": [{**tipo, "categoria": categoria_reporte(tipo["clave"], "", categorias)} for tipo in await _tipos_problema()],
        "categorias_especiales": {"formateo": categoria_reporte("Sistema/programa", "formateo", categorias), "correo": categoria_reporte("Otro", "correo", categorias)},
        "zonas": zonas,
        "origenes": list(ORIGENES_TICKET),
        "prioridades": list(PRIORIDADES),
        "estados_ticket": list(ESTADOS_TICKET),
    }


async def _oficinas_de_zona(zona_id) -> list[dict[str, Any]]:
    from app.services import org_service

    oficinas = await org_service.listar_oficinas(zona_id=zona_id)
    return [{"id": o["_id"], "nombre": o["nombre"], "usuarios": o.get("total_usuarios", 0)} for o in oficinas]


async def _tipos_problema() -> list[dict[str, Any]]:
    """Botones grandes del paso 1, con el icono que usa el frontend."""
    return [
        {"clave": "Sistema/programa", "titulo": "Office, programas o formateo", "descripcion": "Quiero instalar o quitar programas, o formatear mi PC.", "icono": "disc"},
        {"clave": "SIGA/Casita/Servidor", "titulo": "SIGA, Casita o servidor", "descripcion": "No puedo entrar, se queda colgado o muestra un error.", "icono": "server"},
        {"clave": "Carpeta compartida", "titulo": "La compartida", "descripcion": "No abre o no conecta la carpeta compartida de la oficina.", "icono": "folder-network"},
        {"clave": "Impresora", "titulo": "Impresora", "descripcion": "No imprime, se atascó la hoja o no puedo escanear.", "icono": "printer"},
        {"clave": "Huella dactilar", "titulo": "Huella dactilar", "descripcion": "El lector no reconoce mi huella o no enciende.", "icono": "fingerprint"},
        {"clave": "Internet/red", "titulo": "Internet", "descripcion": "Mi PC no tiene internet o está muy lento.", "icono": "wifi"},
        {"clave": "No enciende", "titulo": "No enciende o falla el equipo", "descripcion": "Mi PC no prende, o falla la pantalla, el teclado o el mouse.", "icono": "power"},
        {"clave": "Otro", "titulo": "Otro problema", "descripcion": "Correo, cuentas o algo que no encuentres en esta lista.", "icono": "message-circle"},
    ]


# ── Listado y detalle ────────────────────────────────────────
@router.get("/tickets")
async def listar_tickets(sesion: DependeUsuario, filtros: Annotated[FiltrosTicket, Query()]):
    if sesion.rol == "usuario":
        filtros.vista = None
        filtros.orden = "actualizacion"
    return await ticket_service.listar(filtros.model_dump(), usuario=sesion.usuario)


@router.get("/tickets/resumen")
async def resumen_bandeja(sesion: DependeUsuario):
    if sesion.rol == "usuario":
        base = {"pagina": 1, "por_pagina": 1, "periodo": None}
        abiertos = await ticket_service.listar({**base, "estado": list(ESTADOS_ABIERTOS)}, usuario=sesion.usuario)
        atencion = await ticket_service.listar(
            {**base, "estado": [ESTADO_EN_PROGRESO, ESTADO_EN_ESPERA]},
            usuario=sesion.usuario,
        )
        resueltos = await ticket_service.listar(
            {**base, "estado": list(ESTADOS_CERRADOS)}, usuario=sesion.usuario
        )
        return {
            "es_usuario": True,
            "abiertos": abiertos["total"],
            "en_atencion": atencion["total"],
            "resueltos": resueltos["total"],
        }
    base = {"pagina": 1, "por_pagina": 1, "solo_abiertos": True}
    total = await ticket_service.listar(base, usuario=sesion.usuario)
    sin_asignar = await ticket_service.listar({**base, "vista": "sin_asignar"}, usuario=sesion.usuario)
    en_atencion = await ticket_service.listar(
        {**base, "estado": [ESTADO_EN_PROGRESO, ESTADO_EN_ESPERA]},
        usuario=sesion.usuario,
    )
    riesgo = await ticket_service.listar({**base, "sla": "riesgo"}, usuario=sesion.usuario)
    criticos = await ticket_service.listar({**base, "vista": "criticos"}, usuario=sesion.usuario)
    mios = await ticket_service.listar({**base, "solo_mios": True}, usuario=sesion.usuario)
    cerrados = await ticket_service.listar(
        {"pagina": 1, "por_pagina": 1, "estado": list(ESTADOS_CERRADOS), "periodo": None}, usuario=sesion.usuario
    )
    return {
        "es_usuario": False,
        "abiertos": total["total"],
        "en_atencion": en_atencion["total"],
        "sin_asignar": sin_asignar["total"],
        "sla_riesgo": riesgo["total"],
        "criticos": criticos["total"],
        "mios": mios["total"],
        "cerrados": cerrados["total"],
        "resueltos": cerrados["total"],
        "puede_ver_reportes": sesion.tiene("reportes.ver"),
    }


@router.get("/tickets/{ticket_id}")
async def obtener_ticket(ticket_id: str, sesion: DependeUsuario):
    return await ticket_service.obtener(id_requerido(ticket_id, "ticket"), usuario=sesion.usuario)


@router.patch("/tickets/{ticket_id}")
async def actualizar_ticket(ticket_id: str, datos: TicketActualizar, sesion: DependeUsuarioCsrf):
    return await ticket_service.actualizar(
        id_requerido(ticket_id, "ticket"), datos.model_dump(exclude_unset=True), usuario=sesion.usuario
    )


@router.get('/tickets/{ticket_id}/vinculos')
async def opciones_vinculo(ticket_id: str, sesion: DependeUsuario, corregir_origen: bool = False):
    sesion.exigir('tickets.operar')
    from app.core.db import get_db
    from app.services.historial_inventario_service import opciones_ticket
    objetivo = id_requerido(ticket_id, 'ticket')
    await ticket_service.obtener(objetivo, usuario=sesion.usuario)
    if corregir_origen and sesion.usuario.get('rol') not in {'tecnico', 'administrador'}:
        raise Prohibido('La identificación del equipo corresponde a TI.')
    return await opciones_ticket(await get_db().tickets.find_one({'_id': objetivo}), corregir_origen=corregir_origen)


@router.post("/tickets/{ticket_id}/asignar")
async def asignar(ticket_id: str, datos: AsignarTicket, sesion: DependeUsuarioCsrf):
    sesion.exigir_tecnico()
    return await ticket_service.asignar(id_requerido(ticket_id, "ticket"), datos.model_dump(), usuario=sesion.usuario)


@router.post("/tickets/{ticket_id}/estado")
async def cambiar_estado(ticket_id: str, datos: CambiarEstado, sesion: DependeUsuarioCsrf):
    return await ticket_service.cambiar_estado(
        id_requerido(ticket_id, "ticket"), datos.model_dump(), usuario=sesion.usuario
    )


@router.post("/tickets/{ticket_id}/eliminar")
async def eliminar(ticket_id: str, sesion: DependeUsuarioCsrf, _: DependeEliminar, motivo: str | None = None):
    await ticket_service.eliminar(id_requerido(ticket_id, "ticket"), usuario=sesion.usuario, motivo=motivo)
    return {"mensaje": "Ticket eliminado."}


@router.post("/tickets/{ticket_id}/confirmar")
async def confirmar_desde_usuario(ticket_id: str, sesion: DependeUsuarioCsrf):
    """Un usuario confirma desde su cuenta un ticket creado por el equipo TI: se habilita el chat."""
    return await ticket_service.adoptar_por_usuario(id_requerido(ticket_id, "ticket"), sesion.usuario)


@router.post("/tickets/{ticket_id}/valorar")
async def valorar(ticket_id: str, datos: Valoracion, sesion: DependeUsuarioCsrf):
    return await ticket_service.valorar(
        id_requerido(ticket_id, "ticket"), datos.puntuacion, datos.comentario, usuario=sesion.usuario
    )


# ── Chat (solo tickets reportados por un usuario) ────────────
@router.get("/tickets/{ticket_id}/mensajes")
async def listar_mensajes(ticket_id: str, sesion: DependeUsuario, desde: str | None = None):
    momento = None
    if desde:
        from app.core.time import utcnow
        from datetime import datetime

        try:
            momento = datetime.fromisoformat(desde)
        except ValueError:
            momento = None
    mensajes = await ticket_service.mensajes(id_requerido(ticket_id, "ticket"), usuario=sesion.usuario, desde=momento)
    return {"items": mensajes}


@router.post("/tickets/{ticket_id}/mensajes", status_code=201)
async def enviar_mensaje(ticket_id: str, datos: MensajeCrear, sesion: DependeUsuarioCsrf):
    mensaje = await ticket_service.enviar_mensaje(
        id_requerido(ticket_id, "ticket"), datos.cuerpo, datos.adjuntos, usuario=sesion.usuario
    )
    return {"id": str(mensaje["id"]), "creado_en": mensaje["creado_en"].isoformat()}


# ── Notas internas ───────────────────────────────────────────
@router.get("/tickets/{ticket_id}/notas")
async def listar_notas(ticket_id: str, sesion: DependeUsuario):
    sesion.exigir_tecnico()
    from app.core.db import get_db

    notas = await (get_db()["notas_internas"].find({"ticket_id": id_requerido(ticket_id, "ticket")}).sort("creado_en", -1).to_list(None))
    for nota in notas:
        nota["id"] = nota.pop("_id")
    return {"items": notas}


@router.post("/tickets/{ticket_id}/notas", status_code=201)
async def crear_nota(ticket_id: str, datos: NotaCrear, sesion: DependeUsuarioCsrf):
    sesion.exigir_tecnico()
    nota = await ticket_service.crear_nota(
        id_requerido(ticket_id, "ticket"), datos.cuerpo, datos.adjuntos, usuario=sesion.usuario
    )
    return {"id": str(nota["id"]), "creado_en": nota["creado_en"].isoformat()}


@router.delete("/notas/{nota_id}")
async def eliminar_nota(nota_id: str, sesion: DependeUsuarioCsrf, _: DependeEliminar):
    sesion.exigir_tecnico()
    await ticket_service.eliminar_nota(id_requerido(nota_id, "nota"), usuario=sesion.usuario)
    return {"mensaje": "Nota eliminada."}


# ── Adjuntos ─────────────────────────────────────────────────
@router.post("/adjuntos", status_code=201)
async def subir_adjunto(
    sesion: DependeUsuarioCsrf,
    archivo: Annotated[UploadFile, File()],
    ambito: str = Query("ticket", pattern="^(ticket|kb|nota)$"),
):
    contenido = await archivo.read()
    if len(contenido) > settings.max_upload_bytes:
        raise Validacion(
            f"El archivo supera el limite de {settings.max_upload_mb} MB.",
            detalles={"limite_mb": settings.max_upload_mb},
        )
    documento = await adjuntos_service.guardar_archivo(
        contenido,
        nombre_original=archivo.filename or "archivo",
        mime_declarado=archivo.content_type or "application/octet-stream",
        usuario=sesion.usuario,
        ambito=ambito,
    )
    return {
        "id": str(documento["id"]),
        "nombre": documento["nombre_original"],
        "mime": documento["mime"],
        "tamano": documento["tamano"],
    }


@router.get("/adjuntos/{adjunto_id}")
async def descargar_adjunto(adjunto_id: str, sesion: DependeUsuario):
    from fastapi.responses import FileResponse

    documento = await adjuntos_service.obtener(id_requerido(adjunto_id, "adjunto"))
    if documento.get("ambito") == "ticket" and not documento.get("ticket_id") and documento.get("subido_por") != sesion.usuario.get("_id"):
        raise Prohibido("No tienes acceso a este archivo.")
    if documento.get("nota_id") and sesion.rol == "usuario":
        raise Prohibido("Las notas internas son del equipo de soporte.")
    if sesion.rol == "usuario" and documento.get("ticket_id"):
        await ticket_service.obtener(documento["ticket_id"], usuario=sesion.usuario)
    if documento.get("ambito") == "ticket" and documento.get("ticket_id"):
        await ticket_service.obtener(documento["ticket_id"], usuario=sesion.usuario)
    ruta = documento.get("ruta")
    if not ruta:
        raise Validacion("El archivo no esta disponible.")
    return FileResponse(ruta, media_type=documento["mime"], filename=documento["nombre_original"])


# ── IA en el ticket ──────────────────────────────────────────
@router.get("/tickets/{ticket_id}/ia")
async def sugerencias_ticket(ticket_id: str, sesion: DependeUsuario):
    sesion.exigir_tecnico()
    return await ia_service.sugerencias_ticket(id_requerido(ticket_id, "ticket"), usuario=sesion.usuario)


@router.post("/tickets/{ticket_id}/ia")
async def aplicar_sugerencia(ticket_id: str, datos: SugerenciaAplicar, sesion: DependeUsuarioCsrf):
    sesion.exigir_tecnico()
    return await ia_service.aplicar_sugerencia(
        id_requerido(ticket_id, "ticket"),
        accion=datos.accion,
        clave=datos.clave,
        valor=datos.valor,
        categoria=datos.categoria,
        prioridad=datos.prioridad,
        respuesta_sugerida=datos.respuesta_sugerida,
        usuario=sesion.usuario,
    )


@router.get("/ia/sugerencias-reporte")
async def sugerencias_reporte(
    sesion: DependeUsuario,
    tipo_problema: str | None = None,
    descripcion: str | None = None,
    urgencia: str | None = None,
    activo_tipo: str | None = None,
):
    """Sugerencia discreta del paso 1 (solo si la persona tiene las recomendaciones activas)."""
    return await ia_service.sugerencias_para_crear(
        tipo_problema=tipo_problema,
        descripcion=descripcion,
        urgencia=urgencia,
        activo_tipo=activo_tipo,
        usuario=sesion.usuario,
    )


# ── Vistas guardadas ─────────────────────────────────────────
@router.get("/vistas-guardadas")
async def listar_vistas(sesion: DependeUsuario):
    from app.core.db import get_db

    consulta: dict[str, Any] = {"$or": [{"creada_por": sesion.id}, {"compartida": True}]}
    vistas = await (get_db()["vistas_guardadas"].find(consulta).sort("nombre", 1).to_list(None))
    for vista in vistas:
        vista["id"] = vista.pop("_id")
        vista["puede_editar"] = bool(vista.get("creada_por") == sesion.id or sesion.tiene("vistas.compartidas"))
    return {"items": vistas}


@router.post("/vistas-guardadas", status_code=201)
async def guardar_vista(datos: VistasGuardadas, sesion: DependeUsuarioCsrf):
    from app.core.db import get_db
    from app.core.time import utcnow

    if datos.compartida and not sesion.tiene("vistas.compartidas"):
        raise Prohibido("No tienes permiso para crear vistas compartidas.")
    documento = {
        "nombre": normalizar_texto(datos.nombre),
        "vista": datos.vista,
        "filtros": datos.filtros,
        "columnas": datos.columnas,
        "compartida": datos.compartida,
        "creada_por": sesion.id,
        "creada_por_nombre": sesion.usuario.get("nombre"),
        "creado_en": utcnow(),
    }
    resultado = await get_db()["vistas_guardadas"].insert_one(documento)
    documento["id"] = resultado.inserted_id
    return documento


@router.delete("/vistas-guardadas/{vista_id}")
async def eliminar_vista(vista_id: str, sesion: DependeUsuarioCsrf):
    from app.core.db import get_db

    vista = await get_db()["vistas_guardadas"].find_one({"_id": id_requerido(vista_id, "vista")})
    if vista is None:
        raise Validacion("La vista no existe.")
    if vista.get("creada_por") != sesion.id and not sesion.tiene("vistas.compartidas"):
        raise Prohibido("Esa vista no es tuya.")
    await get_db()["vistas_guardadas"].delete_one({"_id": vista["_id"]})
    return {"mensaje": "Vista eliminada."}
