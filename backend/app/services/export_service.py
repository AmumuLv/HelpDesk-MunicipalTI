"""Exportaciones en PDF, Excel y CSV, con registro de estado y descarga.

Los volumenes grandes se generan en segundo plano (worker ARQ); el usuario recibe
un aviso con el enlace cuando el archivo esta listo. Cada exportacion queda en
auditoria.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from bson import ObjectId

from app.core.audit import registrar
from app.core.config import settings
from app.core.db import get_db
from app.core.errors import NoEncontrado, Prohibido, Validacion
from app.core.ids import id_requerido, normalizar_texto
from app.core.time import business_tz, local_date, utcnow
from app.domain.constants import ESTADOS_CERRADOS
from app.domain.permissions import tiene_permiso
from app.services import (
    analitica_service,
    campana_service,
    excel_service,
    inventario_service,
    pdf_service,
    reportes_service,
    ticket_service,
)

logger = logging.getLogger(__name__)

TIPOS = {
    "tickets",
    "ticket_individual",
    "inventario",
    "pendientes_calidad",
    "campana",
    "analitica",
    "auditoria",
    "equipo",
    "carga_equipo",
}
UMBRAL_ASINCRONO = 200


def _directorio() -> Path:
    ruta = Path(settings.export_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


async def _crear_registro(
    tipo: str, formato: str, nombre: str, usuario: dict[str, Any], estado: str = "en_proceso"
) -> dict[str, Any]:
    db = get_db()
    documento = {
        "tipo": tipo,
        "formato": formato,
        "nombre_archivo": nombre,
        "estado": estado,
        "usuario_id": usuario.get("_id"),
        "usuario_nombre": usuario.get("nombre", ""),
        "tamanio": None,
        "ruta": None,
        "error": None,
        "creado_en": utcnow(),
        "completado_en": None,
    }
    resultado = await db["exportaciones"].insert_one(documento)
    documento["id"] = resultado.inserted_id
    return documento


def _nombre_archivo(tipo: str, formato: str) -> str:
    extension = {"pdf": "pdf", "excel": "xlsx", "csv": "csv"}[formato]
    marca = utcnow().astimezone(business_tz()).strftime("%Y%m%d-%H%M%S")
    return f"{tipo}-{marca}.{extension}"


# ── Generadores ──────────────────────────────────────────────
async def _generar_tickets(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    return await reportes_service.tickets(filtros, formato, usuario)


def _excel_valor(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.astimezone(business_tz()).strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, ObjectId):
        return str(valor)
    return valor


async def _generar_ticket_individual(ticket_id: ObjectId, usuario: dict[str, Any], incluir_notas: bool) -> bytes:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id, "eliminado": {"$ne": True}})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    ticket_service._verificar_acceso(ticket, usuario)
    from app.services import sla_service

    resumen = await ticket_service._resumen(ticket)
    resumen["sla"] = await sla_service.estado_sla(ticket)
    eventos = await (db["ticket_eventos"].find({"ticket_id": ticket_id}).sort("fecha", 1).to_list(None))
    if usuario.get("rol") == "usuario":
        eventos = [e for e in eventos if e.get("visible_usuario")]
    mensajes = await (db["ticket_mensajes"].find({"ticket_id": ticket_id}).sort("creado_en", 1).to_list(None))
    notas = []
    if incluir_notas and usuario.get("rol") in {"tecnico", "administrador"}:
        notas = await (db["notas_internas"].find({"ticket_id": ticket_id}).sort("creado_en", 1).to_list(None))
    equipo = None
    if ticket.get("activo_id"):
        activo = await db["activos"].find_one({"_id": ticket["activo_id"]})
        if activo:
            equipo = activo
    return await pdf_service.ticket_individual(
        resumen, eventos=eventos, mensajes=mensajes, notas=notas, equipo=equipo,
        incluir_notas=incluir_notas and usuario.get("rol") in {"tecnico", "administrador"},
        generado_por=usuario.get("nombre", ""),
    )


async def _generar_inventario(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    return await reportes_service.inventario(filtros, formato, usuario)


async def _generar_pendientes(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    from app.services import calidad_service

    pendientes = await calidad_service.pendientes_exportables(filtros)
    if formato == "pdf":
        return await pdf_service.informe_consolidado(
            titulo="Pendientes de completar inventario",
            subtitulo="Datos faltantes por equipo",
            kpis=[("Equipos pendientes", len(pendientes))],
            tablas=[
                {
                    "titulo": "Detalle",
                    "cabeceras": ["Equipo", "Tipo", "Oficina", "Responsable", "Faltantes", "Campos"],
                    "filas": [
                        [p["nombre"], p["tipo"], p["oficina_nombre"], p["responsable_nombre"], p["faltantes"], ", ".join(p["campos_faltantes"])]
                        for p in pendientes
                    ],
                    "vacio": "No hay equipos con datos faltantes.",
                }
            ],
            filtros_texto=_texto_filtros(filtros),
            generado_por=usuario.get("nombre", ""),
        )
    columnas = ["nombre", "tipo", "codigo_patrimonial", "zona_nombre", "oficina_nombre", "responsable_nombre", "porcentaje", "faltantes", "campos_faltantes"]
    filas = [{columna: (", ".join(p[columna]) if columna == "campos_faltantes" else p.get(columna)) for columna in columnas} for p in pendientes]
    if formato == "csv":
        return excel_service.a_csv(filas, columnas)
    return excel_service.escribir_tablas({"Pendientes": filas}, {"Pendientes": columnas})


async def _generar_campana(campana_id: ObjectId, formato: str, usuario: dict[str, Any]) -> bytes:
    campana = await campana_service.obtener(campana_id, usuario=usuario)
    datos = await campana_service.items(campana_id, pagina=1, por_pagina=2000)
    items = datos["items"]
    if formato == "pdf":
        return await pdf_service.cierre_campana(
            campana, resumen=campana.get("resumen") or {}, filas=items, generado_por=usuario.get("nombre", "")
        )
    columnas = ["zona_nombre", "oficina_nombre", "conjunto_nombre", "activo_tipo", "activo_codigo", "activo_nombre", "responsable_nombre", "estado_item", "observaciones"]
    filas = [{columna: _excel_valor(i.get(columna)) for columna in columnas} for i in items]
    if formato == "csv":
        return excel_service.a_csv(filas, columnas)
    return excel_service.escribir_tablas({f"Campana {campana['anio']}": filas}, {f"Campana {campana['anio']}": columnas})


async def _generar_analitica(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    panel = await analitica_service.panel_completo(filtros)
    kpis = panel["kpis"]
    if formato == "pdf":
        return await pdf_service.informe_consolidado(
            titulo="Informe de Analisis IA",
            subtitulo="Datos reales del sistema",
            kpis=[
                ("Tickets analizados", kpis["tickets_analizados"]),
                ("Tiempo medio", pdf_service._formatear_minutos(kpis["tiempo_medio_resolucion_min"])),
                ("Cumplimiento SLA", f"{kpis['cumplimiento_sla']}%" if kpis["cumplimiento_sla"] is not None else "-"),
                ("Satisfacción (de 5)", kpis["satisfaccion_promedio"] if kpis["satisfaccion_promedio"] is not None else "N/A"),
                ("Riesgos detectados", kpis["riesgos_detectados"]),
                ("Confianza media", f"{kpis['confianza_media_modelo'] * 100:.1f}%" if kpis['confianza_media_modelo'] is not None else "N/A"),
            ],
            comparacion={
                "etiquetas": ["Tickets del periodo"],
                "actual": kpis["tickets_analizados"],
                "anterior": kpis["tickets_periodo_anterior"],
                "variacion": f"{kpis['variacion']}%" if kpis["variacion"] is not None else "-",
            },
            tablas=[
                {
                    "titulo": "Ranking de incidencias por oficina",
                    "cabeceras": ["Oficina", "Zona", "Tickets", "Por equipo", "Por usuario", "Criticas"],
                    "filas": [
                        [i["oficina"], i["zona"], i["total"], i["por_equipo"], i["por_usuario"], i["criticas"]]
                        for i in panel["ranking_oficinas"]["items"][:20]
                    ],
                    "vacio": "Sin tickets en el periodo.",
                },
                {
                    "titulo": "Riesgo de incumplimiento de SLA por categoria",
                    "cabeceras": ["Categoria", "Total", "Seguro", "Atencion", "Critico"],
                    "filas": [
                        [i["nombre"], i["total"], i["seguro"], i["atencion"], i["critico"]]
                        for i in panel["riesgo_sla_categoria"]["items"]
                    ],
                },
                {
                    "titulo": "Carga y desempenho por tecnico (normalizado por horas laborables)",
                    "cabeceras": ["Tecnico", "Asignados", "Resueltos", "Resolucion media", "Ticket/hora", "SLA %"],
                    "filas": [
                        [i["tecnico"], i["asignados"], i["resueltos"], pdf_service._formatear_minutos(i["tiempo_medio_resolucion_min"]), i["tickets_por_hora"], i["cumplimiento_sla"]]
                        for i in panel["carga_tecnicos"]["items"]
                    ],
                },
                {
                    "titulo": "Equipos y familias con mayor tasa de falla",
                    "cabeceras": ["Tipo", "Equipos", "Tickets 12m", "Por equipo", "Con incidencias (12m, %)", "Alcance"],
                    "filas": [
                        [f["tipo"], f["activos"], f["tickets_12m"], f["tickets_por_equipo"], round(f["tasa_falla"] * 100, 1), "Historico"]
                        for f in panel["familias_equipos"]
                    ],
                },
                {
                    "titulo": "Calidad de recomendaciones de IA",
                    "cabeceras": ["Aplicadas", "Editadas", "Descartadas", "Precision confirmada"],
                    "filas": [
                        [
                            panel["calidad_recomendaciones"]["aplicadas"],
                            panel["calidad_recomendaciones"]["editadas"],
                            panel["calidad_recomendaciones"]["descartadas"],
                            panel["calidad_recomendaciones"]["precision_confirmada"],
                        ]
                    ],
                },
            ],
            filtros_texto=reportes_service.texto_filtros({**filtros, "desde": date.fromisoformat(kpis["periodo"]["desde"]), "hasta": date.fromisoformat(kpis["periodo"]["hasta"])}),
            generado_por=usuario.get("nombre", ""),
        )
    def dato(clave, etiqueta, unidad='', grupo='Atención', convertir=None):
        valor = kpis.get(clave)
        if convertir and valor is not None:
            valor = convertir(valor)
        return {'Área': grupo, 'Indicador': etiqueta, 'Resultado': valor if valor is not None else 'N/A', 'Unidad': unidad}
    duracion = kpis.get('tiempo_medio_resolucion_min')
    resumen = [
        {'Área': 'Alcance', 'Indicador': 'Periodo de atención', 'Resultado': f"{date.fromisoformat(kpis['periodo']['desde']).strftime('%d/%m/%Y')} al {date.fromisoformat(kpis['periodo']['hasta']).strftime('%d/%m/%Y')}", 'Unidad': ''},
        dato('tickets_analizados', 'Tickets analizados', 'tickets'),
        dato('tickets_periodo_anterior', 'Tickets del periodo anterior', 'tickets'),
        dato('variacion', 'Variación respecto al periodo anterior', '%'),
        dato('cerrados', 'Tickets atendidos o cerrados', 'tickets'),
        dato('tiempo_medio_resolucion_min', 'Tiempo medio de resolución', 'horas' if duracion is not None and duracion >= 60 else 'minutos', convertir=lambda v: float((Decimal(str(v)) / (60 if v >= 60 else 1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))),
        dato('cumplimiento_sla', 'Cumplimiento del plazo de atención', '%'),
        dato('satisfaccion_promedio', 'Satisfacción media', 'de 5'),
        dato('precision_clasificacion', 'Precisión de clasificación validada', '%', 'Asistente'),
        dato('cobertura_clasificacion', 'Tickets con clasificación automática', '%', 'Asistente'),
        dato('riesgos_detectados', 'Riesgos detectados', 'casos', 'Asistente'),
        dato('casos_atendidos_anticipadamente', 'Casos atendidos anticipadamente', 'casos', 'Asistente'),
        dato('tiempo_potencial_ahorrado_h', 'Tiempo potencial ahorrado (estimación)', 'horas', 'Asistente'),
        dato('confianza_media_modelo', 'Confianza media de las sugerencias', '%', 'Asistente', lambda v: round(v * 100, 1)),
        dato('recomendaciones_aplicadas', 'Recomendaciones aplicadas', 'recomendaciones', 'Asistente'),
        {'Área': 'Calidad de la muestra', 'Indicador': 'Muestra suficiente para el análisis', 'Resultado': 'Sí' if kpis.get('suficiente_datos') else 'No', 'Unidad': ''},
        dato('minimo_requerido', 'Mínimo de tickets requerido', 'tickets', 'Calidad de la muestra'),
    ]
    hojas = {'Resumen de atención': resumen,
        'Por oficina': [{'Oficina': i['oficina'], 'Zona': i['zona'], 'Tickets': i['total'], 'Por equipo': i['por_equipo'], 'Por persona': i['por_usuario'], 'Críticos': i['criticas']} for i in panel['ranking_oficinas']['items']],
        'Por zona': [{'Zona': i['zona'], 'Tickets': i['total'], 'Abiertos': i['abiertos']} for i in panel['ranking_zonas']['items']],
        'Carga de técnicos': [{'Técnico': i['tecnico'], 'Asignados': i['asignados'], 'Resueltos': i['resueltos'], 'Resolución media': pdf_service._formatear_minutos(i.get('tiempo_medio_resolucion_min')), 'Tickets por hora laboral': i['tickets_por_hora'], 'Cumplimiento de plazo (%)': i['cumplimiento_sla'] if i['cumplimiento_sla'] is not None else 'N/A'} for i in panel['carga_tecnicos']['items']],
    }
    hojas['Riesgo de plazo'] = [{'Categoría': i.get('nombre'), 'Total': i.get('total'), 'Sin riesgo': i.get('seguro'), 'En atención': i.get('atencion'), 'Críticos': i.get('critico'), 'Vencidos': i.get('vencidos')} for i in panel['riesgo_sla_categoria']['items']]
    hojas['Causas frecuentes'] = [{'Categoría': i.get('categoria'), 'Equipo': i.get('equipo'), 'Tickets': i.get('total'), 'Tendencia': i.get('tendencia')} for i in panel['causas']['items']]
    hojas['Familias de equipos'] = [{'Tipo': i.get('tipo'), 'Equipos': i.get('activos'), 'Tickets últimos 12 meses': i.get('tickets_12m'), 'Tickets por equipo': i.get('tickets_por_equipo'), 'Equipos con incidencias (%)': round(i['tasa_falla'] * 100, 1) if i.get('tasa_falla') is not None else 'N/A'} for i in panel['familias_equipos']]
    titulos = {nombre: list(filas[0]) if filas else {'Por oficina': ['Oficina', 'Zona', 'Tickets', 'Por equipo', 'Por persona', 'Críticos'], 'Por zona': ['Zona', 'Tickets', 'Abiertos'], 'Carga de técnicos': ['Técnico', 'Asignados', 'Resueltos', 'Resolución media', 'Tickets por hora laboral', 'Cumplimiento de plazo (%)'], 'Riesgo de plazo': ['Categoría', 'Total', 'Sin riesgo', 'En atención', 'Críticos', 'Vencidos'], 'Causas frecuentes': ['Categoría', 'Equipo', 'Tickets', 'Tendencia'], 'Familias de equipos': ['Tipo', 'Equipos', 'Tickets últimos 12 meses', 'Tickets por equipo', 'Equipos con incidencias (%)']}[nombre] for nombre, filas in hojas.items()}
    if formato == 'csv':
        filas = [{'Seccion': seccion, **fila} for seccion, registros in hojas.items() for fila in registros]
        columnas = list(dict.fromkeys(['Seccion'] + [c for columnas in titulos.values() for c in columnas]))
        return excel_service.a_csv(filas, columnas)
    return excel_service.escribir_tablas(hojas, titulos)


async def _generar_auditoria(filtros: dict[str, Any], formato: str, usuario: dict[str, Any]) -> bytes:
    return await reportes_service.auditoria(filtros, formato, usuario)


async def _generar_equipo(activo_id: ObjectId, formato: str, usuario: dict[str, Any]) -> bytes:
    activo = await inventario_service.detalle(activo_id, usuario=usuario)
    if formato == "excel" or formato == "csv":
        filas = [{"campo": campo, "valor": info.get("valor") or "", "estado": info.get("estado")} for campo, info in (activo.get("campos") or {}).items()]
        columnas = ["campo", "valor", "estado"]
        if formato == "csv":
            return excel_service.a_csv(filas, columnas)
        return excel_service.escribir_tablas({"Equipo": filas}, {"Equipo": columnas})
    return await pdf_service.ficha_equipo(activo, generado_por=usuario.get("nombre", ""))


def _texto_filtros(filtros: dict[str, Any]) -> str:
    return reportes_service.texto_filtros(filtros)


# ── Orquestacion ─────────────────────────────────────────────
async def exportar(solicitud: dict[str, Any], *, usuario: dict[str, Any], ip: str | None = None) -> dict[str, Any]:
    tipo = solicitud.get("tipo", "tickets")
    formato = solicitud.get("formato", "pdf")
    if tipo not in TIPOS:
        raise Validacion(f"Tipo de exportacion no soportado: {tipo}")
    if not tiene_permiso(usuario, "exportar"):
        raise Prohibido("No tienes permiso para exportar informacion.")
    filtros = await reportes_service.preparar_filtros(tipo, solicitud.get("filtros") or {})
    if tipo == "auditoria" and not tiene_permiso(usuario, "reportes.ver"):
        raise Prohibido("No tienes permiso para consultar auditoria.")
    if tipo == "analitica" and not tiene_permiso(usuario, "analitica.ver"):
        raise Prohibido("No tienes permiso para consultar analitica.")
    if tipo == "ticket_individual" and formato != "pdf":
        raise Validacion("El informe individual de ticket se genera en PDF.")
    incluir_notas = bool(solicitud.get('incluir_notas_internas'))
    if incluir_notas and tipo not in {"tickets", "ticket_individual"}:
        raise Validacion("Las notas internas solo se incluyen en reportes de tickets.")
    if incluir_notas and usuario.get('rol') not in {'administrador', 'tecnico'}:
        raise Prohibido("Las notas internas son exclusivas del equipo TI.")
    nombre = _nombre_archivo(tipo if tipo != "ticket_individual" else "ticket", formato)
    registro = await _crear_registro(tipo, formato, nombre, usuario)
    await get_db()['exportaciones'].update_one({'_id': registro['id']}, {'$set': {'filtros': {k: v.isoformat() if isinstance(v, date) else str(v) if isinstance(v, ObjectId) else v for k, v in filtros.items() if not k.startswith('_')}, 'alcance': reportes_service.texto_filtros(filtros, inventario=tipo == 'inventario')}})
    try:
        contenido = await _producir(tipo, formato, filtros, solicitud, usuario)
    except Exception as exc:
        await get_db()["exportaciones"].update_one(
            {"_id": registro["id"]}, {"$set": {"estado": "error", "error": str(exc), "completado_en": utcnow()}}
        )
        raise
    destino = _directorio() / f"{registro['id']}_{nombre}"
    destino.write_bytes(contenido)
    await get_db()["exportaciones"].update_one(
        {"_id": registro["id"]},
        {
            "$set": {
                "estado": "listo",
                "ruta": str(destino),
                "tamanio": len(contenido),
                "completado_en": utcnow(),
            }
        },
    )
    await registrar(
        "exportacion.pdf" if formato == "pdf" else "exportacion.excel",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="exportacion",
        entidad_id=registro["id"],
        resumen=f"Exportacion {tipo} en {formato}: {nombre}",
        despues={"tipo": tipo, "formato": formato, "filtros": solicitud.get("filtros") or {}, "bytes": len(contenido)},
        ip=ip,
    )
    return {
        "id": str(registro["id"]),
        "nombre": nombre,
        "formato": formato,
        "estado": "listo",
        "descarga_url": f"/exportaciones/{registro['id']}/descargar",
        "bytes": len(contenido),
    }


async def _producir(
    tipo: str, formato: str, filtros: dict[str, Any], solicitud: dict[str, Any], usuario: dict[str, Any]
) -> bytes:
    if tipo == "tickets":
        return await reportes_service.tickets(filtros, formato, usuario, incluir_notas=bool(solicitud.get("incluir_notas_internas")))
    if tipo == "ticket_individual":
        ids = solicitud.get("ids") or [filtros.get("ticket_id")]
        if not ids or not ids[0]:
            raise Validacion("Indica el ticket a exportar.")
        return await _generar_ticket_individual(id_requerido(ids[0], "ticket"), usuario, bool(solicitud.get("incluir_notas_internas")))
    if tipo == "inventario":
        return await _generar_inventario(filtros, formato, usuario)
    if tipo == "pendientes_calidad":
        return await _generar_pendientes(filtros, formato, usuario)
    if tipo == "campana":
        return await _generar_campana(id_requerido(filtros.get("campana_id"), "campana"), formato, usuario)
    if tipo == "analitica":
        return await _generar_analitica(filtros, formato, usuario)
    if tipo == "carga_equipo":
        return await reportes_service.carga_equipo(filtros, formato, usuario)
    if tipo == "auditoria":
        return await _generar_auditoria(filtros, formato, usuario)
    if tipo == "equipo":
        return await _generar_equipo(id_requerido(filtros.get("activo_id"), "activo"), formato, usuario)
    raise Validacion("Tipo de exportacion no soportado.")  # pragma: no cover


async def listar(usuario: dict[str, Any], limite: int = 25) -> list[dict[str, Any]]:
    consulta: dict[str, Any] = {}
    if usuario.get("rol") != "administrador":
        consulta["usuario_id"] = usuario.get("_id")
    documentos = await (
        get_db()["exportaciones"].find(consulta).sort("creado_en", -1).limit(limite).to_list(None)
    )
    for documento in documentos:
        documento["id"] = documento.pop("_id")
        documento.pop("ruta", None)
        documento["descarga_url"] = f"/exportaciones/{documento['id']}/descargar" if documento.get("estado") == "listo" else None
    return documentos


async def descargar(exportacion_id: ObjectId, usuario: dict[str, Any]) -> tuple[Path, str]:
    documento = await get_db()["exportaciones"].find_one({"_id": exportacion_id})
    if documento is None:
        raise NoEncontrado("La exportacion no existe.")
    if usuario.get("rol") != "administrador" and documento.get("usuario_id") != usuario.get("_id"):
        raise Prohibido("Esa exportacion pertenece a otra persona.")
    if documento.get("estado") != "listo" or not documento.get("ruta"):
        raise Validacion(f"La exportacion esta en estado '{documento.get('estado')}'.")
    ruta = Path(documento["ruta"])
    if not ruta.exists():
        raise NoEncontrado("El archivo ya no esta disponible. Genera la exportacion de nuevo.")
    return ruta, documento.get("nombre_archivo") or ruta.name


async def limpiar_antiguos(dias: int = 7) -> dict[str, Any]:
    """Tarea del worker: borra archivos de mas de N dias y sus registros."""
    db = get_db()
    limite = utcnow() - timedelta(days=dias)
    documentos = await (db["exportaciones"].find({"creado_en": {"$lt": limite}}).to_list(None))
    borrados = 0
    for documento in documentos:
        ruta = documento.get("ruta")
        if ruta:
            try:
                Path(ruta).unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                pass
        borrados += 1
    await db["exportaciones"].delete_many({"creado_en": {"$lt": limite}})
    return {"eliminados": borrados}


async def eliminar_archivos(usuario: dict[str, Any], exportacion_id: ObjectId | None = None) -> dict:
    consulta = {} if usuario.get('rol') == 'administrador' else {'usuario_id': usuario['_id']}
    if exportacion_id:
        consulta['_id'] = exportacion_id
    documentos = await get_db()['exportaciones'].find(consulta).to_list(None)
    if exportacion_id and not documentos:
        raise NoEncontrado('El reporte no existe o no te pertenece.')
    eliminados = 0
    base = Path(settings.export_dir).resolve()
    for doc in documentos:
        if doc.get('estado') in {'pendiente', 'procesando', 'en_proceso'}:
            continue
        if doc.get('ruta'):
            ruta = Path(doc['ruta']).resolve()
            if not ruta.is_relative_to(base):
                raise Validacion('La ruta del reporte está fuera de la carpeta de exportaciones.')
            ruta.unlink(missing_ok=True)
        await get_db()['exportaciones'].delete_one({'_id': doc['_id']})
        eliminados += 1
    return {'eliminados': eliminados}


MIME = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}
