"""Rutas de la campana de importacion de inventario (asistente por pasos)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import DependeUsuario, DependeUsuarioCsrf, requiere
from app.core.errors import Validacion
from app.services import catalogo_service, excel_service, import_service

router = APIRouter(tags=["importacion"])

DependeImportar = Annotated[None, Depends(requiere("equipos.importar"))]
DependeEditarUsuarios = Annotated[None, Depends(requiere("usuarios.editar"))]


def _ip(request: Request) -> str:
    directo = request.headers.get("x-real-ip")
    if directo:
        return directo
    encadenado = request.headers.get("x-forwarded-for")
    return encadenado.split(",")[0].strip() if encadenado else (request.client.host if request.client else None)


@router.get("/importacion/plantilla")
async def descargar_plantilla(sesion: DependeUsuario) -> Response:
    """Plantilla oficial con la estructura exacta que espera el asistente."""
    contenido = excel_service.plantilla_oficial()
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla-inventario.xlsx"'},
    )


@router.get("/importacion/regolas")
async def reglas(sesion: DependeUsuario):
    """Reglas de normalizacion visibles y diccionario de sinonimos editable."""
    return {
        "columnas": excel_service.COLUMNAS_OFICIALES,
        "sinonimos": await catalogo_service.listar("sinonimos_dispositivo"),
        "valores_sin_dato": await catalogo_service.listar("motivos_sin_dato"),
        "patron_conjunto": "COMPUTADORA N°1, IMPRESORA N°2, LAPTOP N°1",
        "reglas": [
            "Cada hoja es una zona; la columna AREA es la oficina.",
            "Tipo de equipo se rellena hacia abajo dentro de la misma oficina.",
            "Un grupo con varios dispositivos se importa como conjunto; uno solo, como equipo individual.",
            "Los sinónimos corrigen el nombre del dispositivo (por ejemplo MAUSE -> Mouse).",
            "'-', 'N/A', 'S/N', 'NO TIENE' y 'SIN CODIGO' equivalen a 'No aplica'.",
            "Los campos vacíos se importan como 'Pendiente' y nunca son error.",
            "Sin código patrimonial se usa la clave oficina + conjunto + dispositivo.",
            "Equipos sin responsable quedan como uso común de la oficina.",
        ],
    }


@router.get("/importacion/responsables-excel")
async def responsables_excel(
    sesion: DependeUsuario, _: DependeImportar, __: DependeEditarUsuarios
):
    return {"items": await import_service.listar_responsables_excel()}


@router.post("/importacion/responsables-excel/confirmar")
async def confirmar_responsables_excel(
    cuerpo: dict[str, Any], sesion: DependeUsuarioCsrf, _: DependeImportar, __: DependeEditarUsuarios
):
    selecciones = cuerpo.get("selecciones")
    if not isinstance(selecciones, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("clave"), str)
        or not isinstance(item.get("usuario_id"), str)
        for item in selecciones
    ):
        raise Validacion("Envía una opción válida para cada responsable del Excel.")
    return await import_service.confirmar_responsables_excel(selecciones, usuario=sesion.usuario)


@router.post("/importacion/subir")
async def subir(
    request: Request,
    sesion: DependeUsuarioCsrf,
    _: DependeImportar,
    archivo: Annotated[UploadFile, File()],
):
    contenido = await archivo.read()
    if not contenido:
        raise Validacion("El archivo esta vacio.")
    nombre = archivo.filename or "inventario.xlsx"
    return await import_service.subir(contenido, nombre, usuario=sesion.usuario)


@router.get("/importacion/{lote_id}")
async def obtener(lote_id: str, sesion: DependeUsuario):
    """
    Ficha de un lote: qué archivo era, sus hojas, su mapeo y su resumen.

    Pide `equipos.importar` como las demás rutas del lote. Antes solo exigía
    estar conectado, así que cualquier cuenta —incluso una de persona
    reportante— podía leer el nombre del archivo y la estructura de la hoja de
    cálculo que importó el municipio. La ruta hermana `/resumen` ya lo exigía:
    dos puertas al mismo dato, una con llave y otra sin ella.
    """
    sesion.exigir("equipos.importar")
    documento = await import_service.obtener_lote(lote_id)
    return {
        "lote_id": lote_id,
        "nombre_archivo": documento.get("nombre_archivo"),
        "estado": documento.get("estado"),
        "analisis": documento.get("analisis"),
        "mapeo": documento.get("mapeo"),
        "ajustes": documento.get("ajustes") or {},
        "resumen": documento.get("resumen") or {},
        "reversible": bool(documento.get("reversible")) and documento.get("estado") == "confirmado",
    }


@router.post("/importacion/{lote_id}/ajustes")
async def ajustes(lote_id: str, cuerpo: dict[str, Any], sesion: DependeUsuarioCsrf, _: DependeImportar):
    return await import_service.guardar_ajustes(lote_id, cuerpo, usuario=sesion.usuario)


@router.post("/importacion/mapeo-guardable")
async def guardar_mapeo(cuerpo: dict[str, Any], sesion: DependeUsuarioCsrf, _: DependeImportar):
    return await import_service.guardar_mapeo_reutilizable(cuerpo, usuario=sesion.usuario)


@router.post("/importacion/{lote_id}/previsualizar")
async def previsualizar(lote_id: str, sesion: DependeUsuarioCsrf, _: DependeImportar, cuerpo: dict[str, Any] | None = None):
    cuerpo = cuerpo or {}
    return await import_service.previsualizar(
        lote_id,
        filas_excluidas=cuerpo.get("filas_excluidas") or [],
        no_aplicar_confirmado=cuerpo.get("no_aplicar_confirmado") or [],
        usuario=sesion.usuario,
    )


@router.post("/importacion/{lote_id}/confirmar")
async def confirmar(lote_id: str, sesion: DependeUsuarioCsrf, _: DependeImportar, cuerpo: dict[str, Any] | None = None):
    cuerpo = cuerpo or {}
    return await import_service.confirmar(
        lote_id,
        filas_excluidas=cuerpo.get("filas_excluidas") or [],
        no_aplicar_confirmado=cuerpo.get("no_aplicar_confirmado") or [],
        crear_usuarios_faltantes=bool(cuerpo.get("crear_usuarios_faltantes")),
        usuario=sesion.usuario,
    )


@router.post("/importacion/{lote_id}/deshacer")
async def deshacer(lote_id: str, sesion: DependeUsuarioCsrf, _: DependeImportar):
    return await import_service.deshacer(lote_id, usuario=sesion.usuario)


@router.get("/importacion")
async def listar(sesion: DependeUsuario, limite: int = Query(25, ge=1, le=100)):
    sesion.exigir("equipos.importar")
    return {"items": await import_service.listar_importaciones(limite)}


@router.get("/importacion/{lote_id}/resumen")
async def resumen(lote_id: str, sesion: DependeUsuario):
    sesion.exigir("equipos.importar")
    return await import_service.resultado(lote_id)


@router.delete('/importacion')
async def limpiar_historial(sesion: DependeUsuarioCsrf, _: DependeImportar, conservar_lote: str | None = None):
    sesion.exigir_admin()
    from app.core.db import get_db
    consulta = {'estado': {'$nin': ['confirmando', 'procesando']}, 'operacion_en_curso': {'$ne': True}}
    if conservar_lote:
        consulta['lote_id'] = {'$ne': conservar_lote}
    resultado = await get_db()['importaciones'].delete_many(consulta)
    return {'eliminados': resultado.deleted_count}
