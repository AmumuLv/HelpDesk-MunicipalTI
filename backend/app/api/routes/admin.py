"""Rutas de configuracion, permisos delegables, catalogos, equipo TI, feriados, KB, campanas,
analitica, asistente, auditoria, reportes y exportaciones."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import DependeUsuario, DependeUsuarioCsrf, id_opcional, requiere
from app.core.db import get_db
from app.core.errors import Prohibido, Validacion
from app.core.ids import id_requerido, normalizar_texto
from app.core.time import local_date, utcnow
from app.domain.constants import ROL_TECNICO
from app.domain.permissions import (
    CLAVES_PERMISOS,
    GRUPOS_PERMISOS,
    PERMISOS_DELEGABLES,
    matriz_inicial,
)
from app.schemas.admin import (
    AplicarPermisosTecnico,
    ArticuloActualizar,
    ArticuloCrear,
    ArticuloDetalle,
    ArticuloResumen,
    AusenciaCrear,
    CampanaActualizar,
    CampanaCrear,
    ConfigRespuesta,
    ConversacionIA,
    ExportarSolicitud,
    Feriado,
    HorarioSemanal,
    ImportarCampana,
    MatrizPermisos,
    PreguntaIA,
    PreguntasSugeridas,
    RespuestaRapida,
    TecnicoPerfilActualizar,
    ValorarArticulo,
)
from app.services import (
    analitica_chat,
    analitica_service,
    campana_service,
    catalogo_service,
    config_service,
    export_service,
    horario_service,
    ia_provider,
    kb_service,
    ml_service,
    usuario_service,
)

config_router = APIRouter(tags=["configuracion"])
permisos_router = APIRouter(tags=["permisos"])
equipo_router = APIRouter(tags=["equipo-ti"])
kb_router = APIRouter(tags=["conocimiento"])
campanas_router = APIRouter(tags=["campanas-inventario"])
analitica_router = APIRouter(tags=["analitica"])
ia_router = APIRouter(tags=["ia"])
auditoria_router = APIRouter(tags=["auditoria"])
export_router = APIRouter(tags=["exportaciones"])

DependeReportes = Annotated[None, Depends(requiere("reportes.ver"))]
DependeExportar = Annotated[None, Depends(requiere("exportar"))]
DependeAnalitica = Annotated[None, Depends(requiere("analitica.ver"))]
DependeKB = Annotated[None, Depends(requiere("kb.editar"))]
DependeCampanas = Annotated[None, Depends(requiere("equipos.campanas"))]


# ══ Configuracion ═══════════════════════════════════════════
@config_router.get("/configuracion")
async def leer_configuracion(sesion: DependeUsuario):
    sesion.exigir_admin()
    return await config_service.obtener()


@config_router.patch("/configuracion")
async def actualizar_configuracion(
    sesion: DependeUsuarioCsrf, datos: ConfigRespuesta
):
    sesion.exigir_admin()
    cambios: dict[str, Any] = {}
    if datos.negocio:
        campos: dict[str, Any] = {}
        if datos.negocio.get("institucion_nombre"):
            campos["nombre"] = datos.negocio["institucion_nombre"]
        if datos.negocio.get("institucion_nombre_corto"):
            campos["nombre_corto"] = datos.negocio["institucion_nombre_corto"]
        if datos.negocio.get("institucion_correo"):
            campos["correo"] = datos.negocio["institucion_correo"]
        if campos:
            cambios["institucion"] = campos
        negocio = {}
        if datos.negocio.get("zona_horaria"):
            negocio["zona_horaria"] = datos.negocio["zona_horaria"]
        if datos.negocio.get("horario_inicio_global"):
            negocio["horario_inicio_global"] = datos.negocio["horario_inicio_global"]
        if datos.negocio.get("horario_fin_global"):
            negocio["horario_fin_global"] = datos.negocio["horario_fin_global"]
        if negocio:
            cambios["negocio"] = negocio
    if datos.sla:
        cambios["sla"] = datos.sla.model_dump(mode="json", exclude_unset=True)
    if datos.ia:
        cambios["ia"] = datos.ia.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    if datos.notificaciones:
        cambios["notificaciones"] = datos.notificaciones.model_dump(mode="json", exclude_none=True, exclude_unset=True)
    if not cambios:
        raise Validacion("No hay cambios para guardar.")
    return await config_service.actualizar(cambios, usuario=sesion.como_dict(), aviso=datos.aviso_global)


@config_router.get("/configuracion/catalogos")
async def leer_catalogos(sesion: DependeUsuario):
    sesion.exigir_admin()
    return {"catalogos": await catalogo_service.todos(), "esquemas": await catalogo_service.todos_los_esquemas()}


@config_router.put("/configuracion/catalogo")
async def guardar_catalogo(sesion: DependeUsuarioCsrf, cuerpo: dict[str, Any]):
    sesion.exigir_admin()
    clave = cuerpo.get("clave")
    valores = cuerpo.get("valores") or []
    return {"items": await catalogo_service.actualizar_catalogo(clave, valores, usuario=sesion.como_dict())}


@config_router.put("/configuracion/esquema/{tipo}")
async def guardar_esquema(tipo: str, sesion: DependeUsuarioCsrf, cuerpo: dict[str, Any]):
    sesion.exigir_admin()
    return await catalogo_service.actualizar_esquema(tipo, cuerpo, usuario=sesion.como_dict())


@config_router.get("/configuracion/feriados")
async def listar_feriados(sesion: DependeUsuario):
    sesion.exigir_admin()
    return {"items": await horario_service.feriados()}


@config_router.post("/configuracion/feriados")
async def guardar_feriado(datos: Feriado, sesion: DependeUsuarioCsrf):
    sesion.exigir_admin()
    return await horario_service.guardar_feriado(datos.model_dump(), usuario=sesion.como_dict())


@config_router.delete("/configuracion/feriados/{feriado_id}")
async def eliminar_feriado(feriado_id: str, sesion: DependeUsuarioCsrf):
    sesion.exigir_admin()
    await horario_service.eliminar_feriado(id_requerido(feriado_id, "feriado"), usuario=sesion.como_dict())
    return {"mensaje": "Feriado eliminado."}


@config_router.get("/configuracion/estado-ia")
async def estado_ia(sesion: DependeUsuario):
    sesion.exigir_admin()
    return await ia_provider.estado()


# ══ Permisos delegables ═════════════════════════════════════
@permisos_router.get("/permisos/matriz", response_model=list[MatrizPermisos])
async def matriz(sesion: DependeUsuario):
    sesion.exigir_admin()
    salida = []
    for grupo in GRUPOS_PERMISOS:
        permisos = [
            {
                "clave": clave_permiso,
                "etiqueta": datos["etiqueta"],
                "descripcion": datos["descripcion"],
            }
            for clave_permiso, datos in PERMISOS_DELEGABLES.items()
            if datos["grupo"] == grupo
        ]
        salida.append({"grupo": grupo, "etiqueta": grupo, "descripcion": f"Permisos de {grupo.lower()}", "permisos": permisos})
    return salida


@permisos_router.get("/permisos/tecnicos")
async def permisos_tecnicos(sesion: DependeUsuario):
    sesion.exigir_admin()
    db = get_db()
    usuarios = await (db["usuarios"].find({"rol": {"$in": [ROL_TECNICO, "administrador"]}, "activo": True}).sort("nombre", 1).to_list(None))
    salida = []
    for usuario in usuarios:
        permisos = {clave_permiso: bool((usuario.get("permisos") or {}).get(clave_permiso, False)) for clave_permiso in CLAVES_PERMISOS}
        if usuario.get("rol") == "administrador":
            permisos = {clave_permiso: True for clave_permiso in CLAVES_PERMISOS}
        salida.append(
            {
                "usuario_id": str(usuario["_id"]),
                "nombre": usuario.get("nombre"),
                "rol": usuario.get("rol"),
                "activo": bool(usuario.get("activo", True)),
                "permisos": permisos,
            }
        )
    return {"items": salida, "matriz_inicial": matriz_inicial()}


@permisos_router.put("/permisos/tecnicos/{usuario_id}")
async def aplicar_permisos(usuario_id: str, datos: AplicarPermisosTecnico, sesion: DependeUsuarioCsrf):
    sesion.exigir_admin()
    permisos = await usuario_service.aplicar_permisos(
        id_requerido(usuario_id, "usuario"), datos.cambios, usuario=sesion.como_dict()
    )
    return {"permisos": permisos}


# ══ Equipo TI y horarios ═════════════════════════════════════
@equipo_router.get("/equipo-ti/panel")
async def panel_equipo(sesion: DependeUsuario):
    sesion.exigir_tecnico()
    return {"items": await horario_service.panel_equipo(), "actualizado_en": utcnow()}


@equipo_router.get("/equipo-ti/tecnicos")
async def tecnicos(sesion: DependeUsuario):
    sesion.exigir_tecnico()
    db = get_db()
    usuarios = await horario_service.tecnicos_activos()
    return {"items": [usuario_service.publico(u, con_preferencias=True) for u in usuarios]}


@equipo_router.get("/equipo-ti/calendario")
async def calendario(sesion: DependeUsuario, desde: date | None = None, hasta: date | None = None):
    sesion.exigir_tecnico()
    inicio = desde or local_date()
    fin = hasta or (inicio + timedelta(days=27))
    filas = await horario_service.calendario_equipo(inicio, fin)
    return {
        "desde": inicio.isoformat(),
        "hasta": fin.isoformat(),
        "items": [{**f, "fecha": f["fecha"].isoformat()} for f in filas],
        "dias_semana": horario_service.DIAS_SEMANA,
    }


# Las rutas fijas van ANTES de "/equipo-ti/{tecnico_id}": en FastAPI gana la
# primera que coincide y el parametro se tragaria nombres como "calendario".
@equipo_router.get("/equipo-ti/{tecnico_id}")
async def obtener_tecnico(tecnico_id: str, sesion: DependeUsuario):
    sesion.exigir_tecnico()
    detalle = await horario_service.obtener_tecnico(id_requerido(tecnico_id, "tecnico"))
    detalle["id"] = str(detalle["id"])
    detalle["disponibilidad"]["tecnico_id"] = str(detalle["disponibilidad"]["tecnico_id"])
    for ausencia in detalle.get("ausencias", []):
        ausencia["id"] = str(ausencia["id"])
        ausencia["tecnico_id"] = str(ausencia["tecnico_id"])
    return detalle


@equipo_router.put("/equipo-ti/{tecnico_id}/horario")
async def guardar_horario(tecnico_id: str, horario: HorarioSemanal, sesion: DependeUsuarioCsrf):
    objetivo = id_requerido(tecnico_id, "tecnico")
    sesion.exigir_tecnico()
    if objetivo != sesion.id:
        sesion.exigir("horarios.editar_todos")
    return await horario_service.actualizar_horario(
        objetivo, horario.model_dump(), usuario=sesion.como_dict(), puede_editar_todos=sesion.tiene("horarios.editar_todos")
    )


@equipo_router.patch("/equipo-ti/{tecnico_id}/perfil")
async def guardar_perfil(tecnico_id: str, datos: TecnicoPerfilActualizar, sesion: DependeUsuarioCsrf):
    sesion.exigir_tecnico()
    objetivo = id_requerido(tecnico_id, "tecnico")
    if objetivo == sesion.id:
        sesion.exigir("horarios.editar_propio")
    if objetivo != sesion.id and not sesion.es_admin:
        sesion.exigir("horarios.editar_todos")
    return await horario_service.actualizar_perfil(objetivo, datos.model_dump(exclude_unset=True), usuario=sesion.como_dict())


@equipo_router.get("/equipo-ti/mi-horario/permiso")
async def puedo_editar_mi_horario(sesion: DependeUsuario):
    return {
        "puedo": sesion.tiene("horarios.editar_propio"),
        "explicacion": "Tu horario solo lo editas si el administrador te habilito ese permiso.",
    }


@equipo_router.get("/ausencias")
async def listar_ausencias(sesion: DependeUsuario, tecnico_id: str | None = None):
    sesion.exigir_tecnico()
    objetivo = id_opcional(tecnico_id, "tecnico")
    if objetivo is None and sesion.tiene("horarios.ver_todos"):
        return {"items": await horario_service.ausencias_de()}
    objetivo = objetivo or sesion.id
    if objetivo != sesion.id:
        sesion.exigir("horarios.ver_todos")
    return {"items": await horario_service.ausencias_de(objetivo)}


@equipo_router.post("/ausencias", status_code=201)
async def crear_ausencia(datos: AusenciaCrear, sesion: DependeUsuarioCsrf):
    objetivo = id_requerido(str(datos.tecnico_id), "tecnico")
    sesion.exigir("horarios.editar_propio" if objetivo == sesion.id else "horarios.editar_todos")
    return await horario_service.crear_ausencia({**datos.model_dump(), "tecnico_id": objetivo}, usuario=sesion.como_dict())


@equipo_router.delete("/ausencias/{ausencia_id}")
async def eliminar_ausencia(ausencia_id: str, sesion: DependeUsuarioCsrf):
    sesion.exigir_tecnico()
    objetivo = id_requerido(ausencia_id, "ausencia")
    tecnico_id = await horario_service.tecnico_de_ausencia(objetivo)
    if tecnico_id == sesion.id:
        sesion.exigir("horarios.editar_propio")
    elif tecnico_id is not None:
        sesion.exigir("horarios.editar_todos")
    await horario_service.eliminar_ausencia(objetivo, usuario=sesion.como_dict())
    return {"mensaje": "Ausencia eliminada."}


# ══ Base de conocimiento ═════════════════════════════════════
@kb_router.get("/kb/articulos")
async def listar_articulos(
    sesion: DependeUsuario,
    categoria: str | None = None,
    texto: str | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    orden: str = Query("relevancia"),
    visibilidad: str | None = Query(None, pattern='^(todos|equipo_ti)$'),
):
    return await kb_service.listar(categoria=categoria, texto=texto, pagina=pagina, por_pagina=por_pagina, orden=orden, usuario=sesion.usuario, visibilidad=visibilidad)


@kb_router.get("/kb/articulos/{articulo_id}", response_model=ArticuloDetalle)
async def obtener_articulo(articulo_id: str, sesion: DependeUsuario):
    return await kb_service.obtener(id_requerido(articulo_id, "articulo"), usuario=sesion.usuario)


@kb_router.post("/kb/articulos", status_code=201, response_model=ArticuloResumen)
async def crear_articulo(datos: ArticuloCrear, sesion: DependeUsuarioCsrf):
    sesion.exigir_tecnico()
    return await kb_service.crear(datos.model_dump(), usuario=sesion.como_dict())


@kb_router.patch("/kb/articulos/{articulo_id}", response_model=ArticuloResumen)
async def actualizar_articulo(articulo_id: str, datos: ArticuloActualizar, sesion: DependeUsuarioCsrf, _: DependeKB):
    return await kb_service.actualizar(id_requerido(articulo_id, "articulo"), datos.model_dump(exclude_unset=True), usuario=sesion.como_dict())


@kb_router.delete("/kb/articulos/{articulo_id}")
async def eliminar_articulo(articulo_id: str, sesion: DependeUsuarioCsrf, _: DependeKB):
    await kb_service.eliminar(id_requerido(articulo_id, "articulo"), usuario=sesion.como_dict())
    return {"mensaje": "Articulo desactivado."}


@kb_router.post("/kb/articulos/{articulo_id}/valorar")
async def valorar_articulo(articulo_id: str, datos: ValorarArticulo, sesion: DependeUsuarioCsrf):
    return await kb_service.valorar(id_requerido(articulo_id, "articulo"), datos.util, datos.comentario, usuario=sesion.usuario)


@kb_router.get('/kb/articulos/{articulo_id}/me-gusta')
async def personas_me_gusta(articulo_id: str, sesion: DependeUsuario, pagina: int = Query(1, ge=1), por_pagina: int = Query(10, ge=1, le=25)):
    return await kb_service.personas_me_gusta(id_requerido(articulo_id, 'artículo'), usuario=sesion.usuario, pagina=pagina, por_pagina=por_pagina)


@kb_router.delete('/kb/articulos/{articulo_id}/valorar')
async def quitar_valoracion_articulo(articulo_id: str, sesion: DependeUsuarioCsrf):
    return await kb_service.quitar_valoracion(id_requerido(articulo_id, 'artículo'), usuario=sesion.usuario)


@kb_router.get("/kb/categorias")
async def categorias_kb(sesion: DependeUsuario):
    return {"items": await kb_service.categorias(usuario=sesion.usuario)}


@kb_router.get("/kb/respuestas-rapidas")
async def respuestas_rapidas(sesion: DependeUsuario):
    sesion.exigir_tecnico()
    return {"items": await kb_service.respuestas_rapidas()}


@kb_router.post("/kb/respuestas-rapidas")
async def guardar_respuesta_rapida(datos: RespuestaRapida, sesion: DependeUsuarioCsrf, _: DependeKB):
    resultado = await kb_service.guardar_respuesta_rapida(datos.model_dump(), None, usuario=sesion.usuario)
    resultado["id"] = str(resultado["id"])
    return resultado


@kb_router.delete("/kb/respuestas-rapidas/{respuesta_id}")
async def eliminar_respuesta_rapida(respuesta_id: str, sesion: DependeUsuarioCsrf, _: DependeKB):
    await kb_service.eliminar_respuesta_rapida(id_requerido(respuesta_id, "respuesta"), usuario=sesion.usuario)
    return {"mensaje": "Respuesta rapida eliminada."}


@kb_router.patch("/kb/respuestas-rapidas/{respuesta_id}")
async def editar_respuesta_rapida(respuesta_id: str, datos: RespuestaRapida, sesion: DependeUsuarioCsrf, _: DependeKB):
    return await kb_service.guardar_respuesta_rapida(datos.model_dump(), id_requerido(respuesta_id, "respuesta"), usuario=sesion.usuario)


# ══ Campanas de inventario ══════════════════════════════════
@campanas_router.get("/campanas")
async def listar_campanas(sesion: DependeUsuario, _: DependeCampanas):
    campanas = await campana_service.listar()
    for campana in campanas:
        campana["id"] = str(campana["id"])
    return {"items": campanas, "campana_activa": await campana_service.campana_activa()}


@campanas_router.post("/campanas", status_code=201)
async def crear_campana(datos: CampanaCrear, sesion: DependeUsuarioCsrf, _: DependeCampanas):
    await campana_service.validar_alcance(datos.model_dump())
    campana = await campana_service.crear(datos.model_dump(), usuario=sesion.usuario)
    campana_id = campana.pop("_id")
    campana["id"] = str(campana_id)
    campana["resumen"] = await campana_service.progreso(campana_id)
    campana["zona_ids"] = [str(z) for z in campana.get("zona_ids") or []]
    campana["oficina_ids"] = [str(o) for o in campana.get("oficina_ids") or []]
    campana["responsables"] = [str(r) for r in campana.get("responsables") or []]
    return campana


@campanas_router.post('/campanas/anual/importar', status_code=201)
async def importar_inventario_anual(sesion: DependeUsuarioCsrf, _: DependeCampanas, archivo: Annotated[UploadFile, File()], anio: Annotated[int, Form()], zona_csv: Annotated[str | None, Form()] = None):
    from app.services import inventario_anual_service
    return await inventario_anual_service.importar(anio, await archivo.read(), archivo.filename or 'inventario.xlsx', zona_csv, sesion.usuario)


@campanas_router.get('/campanas/versiones/{version_id}/equipos')
async def equipos_version_anual(version_id: str, sesion: DependeUsuario, _: DependeCampanas, pagina: int = Query(1, ge=1), por_pagina: int = Query(25, ge=1, le=100), texto: str = ''):
    from app.services import inventario_anual_service
    return await inventario_anual_service.equipos(id_requerido(version_id, 'versión'), pagina, por_pagina, texto)


@campanas_router.delete('/campanas/versiones/{version_id}')
async def eliminar_archivo_anual(version_id: str, sesion: DependeUsuarioCsrf, _: DependeCampanas):
    if sesion.usuario.get('rol') != 'administrador':
        raise Prohibido('Solo el administrador puede eliminar versiones anuales.')
    from app.services import inventario_anual_service
    return await inventario_anual_service.eliminar(id_requerido(version_id, 'versión'), sesion.usuario)


@campanas_router.post("/campanas/previa")
async def previa_campana(cuerpo: dict[str, Any], sesion: DependeUsuarioCsrf, _: DependeCampanas):
    """
    Cuántos equipos entran en la campaña con ese alcance, **sin crearla**.

    Responde a «¿qué significa "solo algunas zonas"?». Una descripción ayuda poco:
    lo que responde de verdad es cuántas máquinas hay que ir a mirar en la sala,
    y eso solo se sabe contando.
    """
    return {"total": await campana_service.contar_por_alcance(cuerpo)}


@campanas_router.get("/campanas/{campana_id}")
async def obtener_campana(campana_id: str, sesion: DependeUsuario, _: DependeCampanas):
    campana = await campana_service.obtener(id_requerido(campana_id, "campana"), usuario=sesion.usuario)
    campana["id"] = str(campana["id"])
    for clave in ("zona_ids", "oficina_ids", "responsables"):
        campana[clave] = [str(x) for x in campana.get(clave) or []]
    return campana


@campanas_router.patch("/campanas/{campana_id}")
async def actualizar_campana(campana_id: str, datos: CampanaActualizar, sesion: DependeUsuarioCsrf, _: DependeCampanas):
    campana = await campana_service.actualizar(id_requerido(campana_id, "campana"), datos.model_dump(exclude_unset=True), usuario=sesion.usuario)
    campana["id"] = str(campana["id"])
    return campana


@campanas_router.get("/campanas/{campana_id}/items")
async def items_campana(
    campana_id: str,
    sesion: DependeUsuario,
    _: DependeCampanas,
    zona_id: str | None = None,
    oficina_id: str | None = None,
    estado: str | None = None,
    solo_pendientes: bool = False,
    texto: str | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
):
    resultado = await campana_service.items(
        id_requerido(campana_id, "campana"),
        zona_id=id_opcional(zona_id, "zona"),
        oficina_id=id_opcional(oficina_id, "oficina"),
        estado=estado,
        solo_pendientes=solo_pendientes,
        texto=texto,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    for item in resultado["items"]:
        item["activo_id"] = str(item["activo_id"]) if item.get("activo_id") else None
    return resultado


@campanas_router.post("/campanas/{campana_id}/items/{item_id}")
async def verificar_item(campana_id: str, item_id: str, cuerpo: dict[str, Any], sesion: DependeUsuarioCsrf, _: DependeCampanas):
    item = await campana_service.verificar_item(
        id_requerido(campana_id, "campana"), id_requerido(item_id, "item"), cuerpo, usuario=sesion.usuario
    )
    item["id"] = str(item["_id"])
    return item


@campanas_router.post("/campanas/{campana_id}/excel")
async def comparar_excel(
    campana_id: str,
    sesion: DependeUsuarioCsrf,
    _: DependeCampanas,
    archivo: Annotated[UploadFile, File()],
):
    contenido = await archivo.read()
    return await campana_service.importar_excel(
        id_requerido(campana_id, "campana"), contenido, archivo.filename or "campana.xlsx", usuario=sesion.usuario
    )


@campanas_router.post("/campanas/{campana_id}/excel/aceptar")
async def aceptar_excel(campana_id: str, cuerpo: ImportarCampana, sesion: DependeUsuarioCsrf, _: DependeCampanas):
    return await campana_service.aceptar_cambios(
        id_requerido(campana_id, "campana"),
        cuerpo.lote_id,
        acepta=cuerpo.estados_aceptados,
        rechazar=cuerpo.estados_rechazados,
        usuario=sesion.usuario,
    )


@campanas_router.post("/campanas/{campana_id}/cerrar")
async def cerrar_campana(campana_id: str, cuerpo: dict[str, Any], sesion: DependeUsuarioCsrf, _: DependeCampanas):
    return await campana_service.cerrar(
        id_requerido(campana_id, "campana"),
        marcar_no_localizados=bool(cuerpo.get("marcar_no_localizados", True)),
        nota=cuerpo.get("nota"),
        confirmacion=bool(cuerpo.get("confirmacion")),
        usuario=sesion.usuario,
    )


@campanas_router.get("/campanas/versiones/historico")
async def historial_campanas(sesion: DependeUsuario, _: DependeCampanas):
    versiones = await campana_service.versiones()
    for version in versiones:
        version["campana_id"] = str(version["campana_id"])
    return {"items": versiones}


@campanas_router.get("/campanas/versiones/{version_id}/excel")
async def descargar_version_excel(version_id: str, sesion: DependeUsuario, _: DependeCampanas):
    """El inventario de un año cerrado, en el Excel del municipio (una hoja por zona)."""
    contenido, _total, nombre = await campana_service.exportar_version_excel(
        id_requerido(version_id, "version")
    )
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.xlsx"'},
    )


@campanas_router.delete("/campanas/{campana_id}")
async def eliminar_campana(campana_id: str, sesion: DependeUsuarioCsrf, _: DependeCampanas):
    """
    Borra la campaña. El inventario no se toca.

    Se escribe como `delete` y no como `post` porque es lo que es, y porque un botón
    de «eliminar» tiene que poder detectarse con una petición que no se puede repetir
    por accidente al recargar.
    """
    return await campana_service.eliminar(id_requerido(campana_id, "campana"), usuario=sesion.usuario)


@campanas_router.get("/campanas/versiones/comparar")
async def comparar_versiones(anio_a: int, anio_b: int, sesion: DependeUsuario, _: DependeCampanas):
    from app.services import inventario_anual_service
    return await inventario_anual_service.comparar(anio_a, anio_b)


# ══ Analitica ════════════════════════════════════════════════
def _filtros_analitica(
    periodo: str | None = "30d",
    desde: date | None = None,
    hasta: date | None = None,
    zona_id: str | None = None,
    oficina_id: str | None = None,
    categoria: str | None = None,
    tipo_activo: str | None = None,
    tecnico_id: str | None = None,
    equipo_id: str | None = None,
) -> dict[str, Any]:
    return {
        "periodo": periodo,
        "desde": desde,
        "hasta": hasta,
        "zona_id": id_opcional(zona_id, "zona"),
        "oficina_id": id_opcional(oficina_id, "oficina"),
        "categoria": categoria,
        "tipo_activo": tipo_activo,
        "tecnico_id": id_opcional(tecnico_id, "tecnico"),
        "equipo_id": id_opcional(equipo_id, "activo"),
    }


@analitica_router.get("/analitica/panel")
async def panel_analitica(sesion: DependeUsuario, _: DependeAnalitica, periodo: str = "30d", desde: date | None = None, hasta: date | None = None, zona_id: str | None = None, oficina_id: str | None = None, categoria: str | None = None, tecnico_id: str | None = None, tipo_activo: str | None = None):
    filtros = _filtros_analitica(periodo, desde, hasta, zona_id, oficina_id, categoria, tipo_activo, tecnico_id)
    panel = await analitica_service.panel_completo(filtros)
    panel["minimos"] = await analitica_service.minimo_para_pronostico()
    return panel


@analitica_router.get("/analitica/resumen")
async def resumen_panel(sesion: DependeUsuario):
    """Resumen del panel TI (cabecera)."""
    from app.services import dashboard_service

    return await dashboard_service.resumen(sesion)


@analitica_router.get("/analitica/equipos-prediccion")
async def prediccion_equipos(sesion: DependeUsuario, _: DependeAnalitica):
    familias = await ml_service.predecir_familias()
    metodo = familias[0]["metodo"] if familias else "regla_heuristica"
    return {
        "familias": familias,
        # La prediccion declara siempre como se calculo y con que confianza
        "metodo": metodo,
        "explicacion": familias[0]["metodo_explicacion"] if familias else "Sin datos suficientes: se usa la regla de tickets por equipo.",
        "suficiente_datos": all(f.get("suficiente_datos") for f in familias) if familias else False,
        "minimo_requerido": ml_service.MINIMO_MUESTRAS_MODELO,
        "actualizado_en": utcnow(),
    }


@analitica_router.post("/analitica/modelo/refrescar")
async def refrescar_modelo(sesion: DependeUsuarioCsrf):
    sesion.exigir_admin()
    await ml_service.invalidar_cache()
    await ml_service.predecir_familias()
    return {"mensaje": "Modelo recalculado con los datos actuales."}


# ══ Asistente conversacional ════════════════════════════════
@ia_router.get("/ia/asistente/preguntas")
async def preguntas_sugeridas(sesion: DependeUsuario, _: DependeAnalitica):
    return PreguntasSugeridas(preguntas=analitica_chat.PREGUNTAS_SUGERIDAS)


@ia_router.post("/ia/asistente")
async def preguntar(datos: PreguntaIA, sesion: DependeUsuarioCsrf, _: DependeAnalitica):
    sesion.exigir_tecnico()
    filtros = datos.filtros.model_dump(exclude_none=True)
    analitica_service.resolver_periodo(filtros)
    conversacion = await analitica_chat.guardar_conversacion(
        sesion.usuario, titulo=datos.pregunta[:60], conversacion_id=datos.conversacion_id
    )
    historial = conversacion.get("mensajes") or []
    filtros.setdefault("periodo", "30d")
    respuesta = await analitica_chat.responder(
        datos.pregunta,
        usuario=sesion.usuario,
        filtros=filtros,
        conversacion_id=conversacion["_id"],
        historial=historial,
    )
    await analitica_chat.agregar_mensaje(conversacion["_id"], "user", datos.pregunta, None, sesion.usuario)
    await analitica_chat.agregar_mensaje(conversacion["_id"], "assistant", respuesta["texto"], respuesta, sesion.usuario)
    return {
        "conversacion_id": str(conversacion["_id"]),
        **respuesta,
        "lectura_solo": True,
        "periodo": respuesta.get("periodo"),
    }


@ia_router.get("/ia/asistente/conversaciones")
async def conversaciones(sesion: DependeUsuario, _: DependeAnalitica):
    sesion.exigir_tecnico()
    items = await analitica_chat.listar_conversaciones(sesion.usuario)
    for item in items:
        item["id"] = str(item["id"])
        item["usuario_id"] = str(item["usuario_id"])
    return {"items": items}


@ia_router.get("/ia/asistente/conversaciones/{conversacion_id}")
async def conversacion(conversacion_id: str, sesion: DependeUsuario, _: DependeAnalitica) -> ConversacionIA:
    sesion.exigir_tecnico()
    datos = await analitica_chat.obtener_conversacion(id_requerido(conversacion_id, "conversacion"), sesion.usuario)
    datos["id"] = str(datos["id"])
    datos["usuario_id"] = str(datos["usuario_id"])
    return datos


@ia_router.delete("/ia/asistente/conversaciones/{conversacion_id}")
async def borrar_conversacion(conversacion_id: str, sesion: DependeUsuarioCsrf, _: DependeAnalitica):
    sesion.exigir_tecnico()
    await analitica_chat.eliminar_conversacion(id_requerido(conversacion_id, "conversacion"), sesion.usuario)
    return {"mensaje": "Conversacion eliminada."}


# ══ Auditoria ════════════════════════════════════════════════
@auditoria_router.get("/auditoria")
async def auditoria(
    sesion: DependeUsuario,
    _: DependeReportes,
    accion: str | None = None,
    entidad: str | None = None,
    usuario_id: str | None = None,
    resultado: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
):
    sesion.exigir_admin()
    db = get_db()
    from app.core.audit import accion_legible, consulta_movimientos

    consulta = consulta_movimientos(desde=desde, hasta=hasta, accion=accion, entidad=entidad,
                                    usuario_id=id_opcional(usuario_id, "usuario"), resultado=resultado)
    total = await db["auditoria"].count_documents(consulta)
    documentos = await (
        db["auditoria"].find(consulta).sort([("fecha", -1), ("_id", -1)]).skip((pagina - 1) * por_pagina).limit(por_pagina).to_list(None)
    )
    for documento in documentos:
        documento["id"] = documento.pop("_id")
        documento["accion_texto"] = accion_legible(documento.get("accion", ""), documento.get("entidad", ""))
    from app.core.audit import ACCIONES, ACCIONES_COTIDIANAS

    return {
        "items": documentos,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "acciones": [{"clave": clave_accion, "texto": texto} for clave_accion, texto in ACCIONES.items() if clave_accion not in ACCIONES_COTIDIANAS],
        "importable": True,
    }


# ══ Exportaciones ════════════════════════════════════════════
@export_router.get("/exportaciones")
async def listar_exportaciones(sesion: DependeUsuario, _: DependeExportar):
    items = await export_service.listar(sesion.usuario)
    for item in items:
        item["id"] = str(item["id"])
    return {"items": items}


@export_router.post("/exportaciones")
async def crear_exportacion(solicitud: ExportarSolicitud, request: Request, sesion: DependeUsuarioCsrf, _: DependeExportar):
    directo = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
    return await export_service.exportar(solicitud.model_dump(), usuario=sesion.usuario, ip=directo)


@export_router.delete('/exportaciones')
async def limpiar_reportes(sesion: DependeUsuarioCsrf, _: DependeExportar):
    return await export_service.eliminar_archivos(sesion.usuario)


@export_router.delete('/exportaciones/{exportacion_id}')
async def eliminar_reporte(exportacion_id: str, sesion: DependeUsuarioCsrf, _: DependeExportar):
    return await export_service.eliminar_archivos(sesion.usuario, id_requerido(exportacion_id, 'reporte'))


@auditoria_router.delete('/auditoria')
async def vaciar_auditoria(sesion: DependeUsuarioCsrf, _: DependeReportes):
    sesion.exigir_admin()
    resultado = await get_db()['auditoria'].delete_many({})
    return {'eliminados': resultado.deleted_count}


@export_router.get("/exportaciones/{exportacion_id}/descargar")
async def descargar(exportacion_id: str, sesion: DependeUsuario, _: DependeExportar) -> Response:
    from fastapi.responses import FileResponse

    ruta, nombre = await export_service.descargar(id_requerido(exportacion_id, "exportacion"), sesion.usuario)
    formato = ruta.suffix.lstrip(".")
    return FileResponse(ruta, media_type=export_service.MIME.get(formato, "application/octet-stream"), filename=nombre)
