"""Generacion de PDF con WeasyPrint (HTML/CSS -> PDF).

Plantillas institucionales sobrias, con encabezado, paginacion correcta y pie con
la fecha de generacion y el responsable. Sin dependencias a Internet.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from app.core.config import settings
from app.core.time import business_tz, local_date
from app.domain.constants import (
    ESTADO_CERRADO,
    ESTADO_EN_ESPERA,
    ESTADO_EN_PROGRESO,
    ESTADO_NUEVO,
    PRIORIDAD_ALTA,
    PRIORIDAD_BAJA,
    PRIORIDAD_CRITICA,
    PRIORIDAD_MEDIA,
)
from app.services import config_service

logger = logging.getLogger(__name__)

ETIQUETAS_ESTADO = {
    ESTADO_NUEVO: "Nuevo",
    ESTADO_EN_PROGRESO: "En progreso",
    ESTADO_EN_ESPERA: "En espera",
    ESTADO_CERRADO: "Cerrado",
}

ETIQUETAS_PRIORIDAD = {
    PRIORIDAD_BAJA: "Baja",
    PRIORIDAD_MEDIA: "Media",
    PRIORIDAD_ALTA: "Alta",
    PRIORIDAD_CRITICA: "Critica",
}

# Colores de marca en HEX: solo dentro de la plantilla impresa (no en componentes React)
AZUL = "#173B7A"
AZUL_CLARO = "#EAF1FF"
GRIS_BORDE = "#D9E0EA"
TEXTO = "#162033"
TEXTO_SUAVE = "#5E6B7E"
VERDE = "#178A55"
AMBAR = "#C87900"
ROJO = "#C43D4B"
TEAL = "#0D8A8A"

CSS_BASE = """
@page {
  size: A4;
  margin: 18mm 14mm 16mm 14mm;
  @bottom-left { content: element(datos-pie); font-size: 7pt; color: #5E6B7E; }
  @bottom-right { content: "Página " counter(page) " de " counter(pages); font-size: 8pt; color: #5E6B7E; }
}
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", "Liberation Sans", sans-serif; font-size: 9.5pt; color: #162033; line-height: 1.45; }
h1 { font-size: 17pt; margin: 0 0 2mm; color: #173B7A; }
h2 { font-size: 12pt; margin: 6mm 0 2mm; color: #173B7A; border-bottom: 1px solid #D9E0EA; padding-bottom: 1.5mm; }
h3 { font-size: 10.5pt; margin: 4mm 0 1.5mm; color: #162033; }
p { margin: 0 0 2mm; }
.subtitulo { color: #5E6B7E; font-size: 9pt; margin-bottom: 4mm; }
.cabecera { border-bottom: 2px solid #173B7A; padding-bottom: 3mm; margin-bottom: 4mm; }
.identidad { color: #5E6B7E; font-size: 7pt; letter-spacing: 1pt; margin-bottom: 2mm; }
.alcance { background: #F3F6FC; border-left: 3px solid #173B7A; padding: 3mm; margin-bottom: 4mm; }
.alcance p:last-child { margin-bottom: 0; }
.ayuda { color: #5E6B7E; font-size: 8pt; margin-bottom: 3mm; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; margin-bottom: 4mm; }
thead { display: table-header-group; }
td, th { overflow-wrap: anywhere; }
tbody tr:nth-child(even) { background: #F7F9FC; }
h2, h3 { break-after: avoid; }
.zona-inventario + .zona-inventario { break-before: page; }
th { background: #EAF1FF; color: #173B7A; text-align: left; padding: 2mm 2.5mm; font-size: 8.5pt; border-bottom: 1.5px solid #173B7A; }
td { padding: 1.8mm 2.5mm; border-bottom: 1px solid #D9E0EA; font-size: 8.5pt; vertical-align: top; }
tr { page-break-inside: avoid; }
.kpis { display: flex; flex-wrap: wrap; gap: 3mm; margin-bottom: 5mm; }
.kpi { border: 1px solid #D9E0EA; border-top: 2px solid #173B7A; border-radius: 2mm; padding: 2.5mm 3mm; width: 31%; }
.kpi .valor { font-size: 14pt; font-weight: bold; color: #173B7A; }
.kpi .etiqueta { font-size: 8pt; color: #5E6B7E; }
.badge { display: inline-block; padding: 0.4mm 2mm; border-radius: 2mm; font-size: 7.5pt; border: 1px solid #D9E0EA; }
.badge-nuevo { background: #EAF1FF; color: #173B7A; border-color: #173B7A; }
.badge-asignado { background: #1B3C80; color: #ffffff; border-color: #1B3C80; }
.badge-progreso { background: #E3F2F2; color: #0D8A8A; border-color: #0D8A8A; }
.badge-espera { background: #FFF4E0; color: #C87900; border-color: #C87900; }
.badge-cerrado { background: #F0F3F7; color: #5E6B7E; border-color: #5E6B7E; }
.badge-critica { background: #FBE9EB; color: #C43D4B; border-color: #C43D4B; }
.badge-alta { background: #FFF4E0; color: #C87900; border-color: #C87900; }
.nota-interna { background: #FDF6E7; border-left: 3px solid #C87900; padding: 2mm 3mm; margin-bottom: 2mm; }
.linea-tiempo { border-left: 2px solid #D9E0EA; margin-left: 2mm; padding-left: 4mm; }
.linea-tiempo .evento { margin-bottom: 2.5mm; }
.linea-tiempo .fecha { color: #5E6B7E; font-size: 8pt; }
.aviso { background: #FDF6E7; border: 1px solid #C87900; padding: 2.5mm 3mm; border-radius: 2mm; margin-bottom: 3mm; }
.vacio { color: #5E6B7E; font-style: italic; }
.pie-datos { position: running(datos-pie); font-size: 7pt; color: #5E6B7E; }
"""


def etiqueta_campo(nombre: str) -> str:
    return {'codigo_patrimonial': 'Código patrimonial', 'nombre_equipo': 'Nombre del equipo',
            'memoria_ram': 'Memoria RAM', 'direccion_ip': 'Dirección IP', 'direccion_mac': 'Dirección MAC',
            'tamano_pantalla': 'Tamaño de pantalla'}.get(nombre, nombre.replace('_', ' ').capitalize())


def _esc(valor: Any) -> str:
    if valor is None:
        return "-"
    texto = str(valor)
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _badge_estado(estado: str) -> str:
    clases = {
        ESTADO_NUEVO: "badge-nuevo",
        ESTADO_EN_PROGRESO: "badge-progreso",
        ESTADO_EN_ESPERA: "badge-espera",
        ESTADO_CERRADO: "badge-cerrado",
    }
    return f'<span class="badge {clases.get(estado, "badge-cerrado")}">{_esc(ETIQUETAS_ESTADO.get(estado, estado))}</span>'


def _badge_prioridad(prioridad: str) -> str:
    clases = {PRIORIDAD_CRITICA: "badge-critica", PRIORIDAD_ALTA: "badge-alta"}
    return f'<span class="badge {clases.get(prioridad, "badge-nuevo")}">{_esc(ETIQUETAS_PRIORIDAD.get(prioridad, prioridad))}</span>'


def _tabla(cabeceras: list[str], filas: list[list[Any]], *, vacio: str = "Sin datos para este filtro", anchos: list[int] | None = None) -> str:
    if not filas:
        return f'<p class="vacio">{_esc(vacio)}</p>'
    encabezado = "".join(f"<th>{_esc(c)}</th>" for c in cabeceras)
    cuerpo = "".join(
        "<tr>" + "".join(f"<td>{_esc(celda).replace(chr(10), '<br>')}</td>" for celda in fila) + "</tr>"
        for fila in filas
    )
    columnas = '<colgroup>' + ''.join(f'<col style="width:{ancho}%">' for ancho in anchos) + '</colgroup>' if anchos else ''
    return f"<table>{columnas}<thead><tr>{encabezado}</tr></thead><tbody>{cuerpo}</tbody></table>"


def _kpis(valores: list[tuple[str, Any]]) -> str:
    celdas = "".join(
        f'<div class="kpi"><div class="valor">{_esc(valor)}</div><div class="etiqueta">{_esc(etiqueta)}</div></div>'
        for etiqueta, valor in valores
    )
    return f'<div class="kpis">{celdas}</div>'


def _pagina(titulo: str, cuerpo: str, *, subtitulo: str = "", pie_extra: str = "", horizontal: bool = False) -> bytes:
    css = CSS_BASE.replace('{{institucion}} - ', '')
    if horizontal:
        css += '@page { size: A4 landscape; margin: 12mm; } body { font-size: 9pt; } h1 { font-size: 16pt; } .kpi { width: 23%; padding: 2mm; } .kpi .valor { font-size: 12pt; } td, th { font-size: 8pt; padding: 1.5mm 2mm; }'
    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>{_esc(titulo)}</title><style>{css}</style></head>
<body>
  <div class="pie-datos">Generado el {local_date().strftime('%d/%m/%Y')}{pie_extra}</div>
  <div class="cabecera">
    <div class="identidad">MESA DE AYUDA · SOPORTE TI</div>
    <h1>{_esc(titulo)}</h1>
    <div class="subtitulo">{_esc(subtitulo)}</div>
  </div>
  {cuerpo}
</body></html>"""
    return _render(html)


def _render(html: str) -> bytes:
    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception as exc:  # pragma: no cover - depende de librerias del sistema
        logger.error("WeasyPrint fallo: %s", exc)
        raise RuntimeError(f"No se pudo generar el PDF: {exc}") from exc


def _formatear_fecha(valor: Any) -> str:
    if not valor:
        return "-"
    if isinstance(valor, datetime):
        return (valor.astimezone(business_tz()) if valor.tzinfo else valor).strftime('%d/%m/%Y %H:%M')
    if isinstance(valor, date):
        return valor.strftime('%d/%m/%Y')
    return str(valor)


def _formatear_minutos(minutos: Any) -> str:
    if minutos is None:
        return "-"
    total = max(0, round(float(minutos)))
    dias, resto = divmod(total, 1440)
    horas, minutos = divmod(resto, 60)
    return ' '.join(p for p in [f"{dias} día{'s' if dias != 1 else ''}" if dias else '', f"{horas} hora{'s' if horas != 1 else ''}" if horas else '', f'{minutos} min' if minutos or not total else ''] if p)


# ── Documentos ───────────────────────────────────────────────
async def ticket_individual(ticket: dict[str, Any], *, eventos: list[dict[str, Any]], mensajes: list[dict[str, Any]], notas: list[dict[str, Any]], equipo: dict[str, Any] | None, incluir_notas: bool, generado_por: str) -> bytes:
    institucion = await config_service.nombre_institucion()
    sla = ticket.get("sla") or {}
    cuerpo = [
        _kpis(
            [
                ("Estado", ETIQUETAS_ESTADO.get(ticket.get("estado"), ticket.get("estado"))),
                ("Prioridad", ETIQUETAS_PRIORIDAD.get(ticket.get("prioridad"), ticket.get("prioridad"))),
                ("SLA", (sla.get("estado") or "-")),
                ("Resolucion", _formatear_minutos(ticket.get("tiempo_resolucion_min"))),
            ]
        ),
        "<h2>Datos del ticket</h2>",
        _tabla(
            ["Campo", "Valor"],
            [
                ["Codigo", ticket.get("codigo")],
                ["Asunto", ticket.get("asunto")],
                ["Descripcion", ticket.get("descripcion") or "-"],
                ["Tipo de problema", ticket.get("tipo_problema") or "-"],
                ["Categoria", ticket.get("categoria") or "-"],
                ["Reporto", ticket.get("reportante_nombre")],
                ["Afecta a", ticket.get("afectado_nombre")],
                ["Origen", ticket.get("origen")],
                ["Zona", ticket.get("zona_nombre") or "-"],
                ["Oficina", ticket.get("oficina_nombre") or "-"],
                ["Equipo", ticket.get("activo_nombre") or "-"],
                ["Conjunto", ticket.get("conjunto_nombre") or "-"],
                ["Tecnico asignado", ticket.get("tecnico_nombre") or "Sin asignar"],
                ["Creado", _formatear_fecha(ticket.get("creado_en"))],
                ["Resuelto", _formatear_fecha(ticket.get("resuelto_en") or ticket.get("cerrado_en"))],
                ["Cerrado", _formatear_fecha(ticket.get("cerrado_en"))],
                ["Reaperturas", ticket.get("veces_reabierto", 0)],
                ["Satisfaccion", f"{ticket.get('satisfaccion')}/5" if ticket.get("satisfaccion") else "-"],
            ],
        ),
    ]
    if ticket.get("origen") in {"usuario", "usuario_por_companero"}:
        cuerpo.append("<h2>Conversacion con la persona</h2>")
        if mensajes:
            for mensaje in mensajes:
                cuerpo.append(
                    f'<div class="linea-tiempo"><div class="evento"><strong>{_esc(mensaje.get("autor_nombre"))}</strong> '
                    f'<span class="fecha">{_esc(_formatear_fecha(mensaje.get("creado_en")))}</span><br>{_esc(mensaje.get("cuerpo"))}</div></div>'
                )
        else:
            cuerpo.append('<p class="vacio">Sin mensajes.</p>')
    if ticket.get("nota_resolucion"):
        cuerpo.append(
            f'<h2>Nota de resolucion</h2><div class="aviso">{_esc(ticket.get("nota_resolucion"))}</div>'
        )
    if incluir_notas and notas:
        cuerpo.append("<h2>Notas internas</h2>")
        for nota in notas:
            cuerpo.append(
                f'<div class="nota-interna"><strong>{_esc(nota.get("autor_nombre"))}</strong> '
                f'<span class="fecha">{_esc(_formatear_fecha(nota.get("creado_en")))}</span><br>{_esc(nota.get("cuerpo"))}</div>'
            )
    if equipo:
        cuerpo.append("<h2>Equipo informado</h2>")
        cuerpo.append(
            _tabla(
                ["Campo", "Valor"],
                [
                    ["Tipo", equipo.get("tipo")],
                    ["Codigo patrimonial", equipo.get("codigo_patrimonial") or "-"],
                    ["Marca / Modelo", f"{equipo.get('marca') or '-'} {equipo.get('modelo') or ''}".strip()],
                    ["Procesador", equipo.get("procesador") or "-"],
                    ["Memoria RAM", equipo.get("memoria_ram") or "-"],
                    ["Almacenamiento", equipo.get("almacenamiento") or "-"],
                    ["Estado", equipo.get("estado") or "-"],
                    ["Oficina", equipo.get("oficina_nombre") or "-"],
                    ["Responsable", equipo.get("responsable_nombre") or "Uso comun de la oficina"],
                ],
            )
        )
    cuerpo.append("<h2>Linea de tiempo</h2>")
    if eventos:
        for evento in eventos:
            actor = (evento.get("actor") or {}).get("nombre", "Sistema")
            visible = "" if evento.get("visible_usuario", True) else " (interna)"
            cuerpo.append(
                f'<div class="linea-tiempo"><div class="evento"><span class="fecha">'
                f'{_esc(_formatear_fecha(evento.get("fecha")))}</span> - <strong>{_esc(evento.get("tipo"))}</strong>{_esc(visible)}<br>'
                f"{_esc(evento.get('resumen'))} ({_esc(actor)})</div></div>"
            )
    else:
        cuerpo.append('<p class="vacio">Sin eventos.</p>')
    return _pagina(
        f"Ticket {ticket.get('codigo')}",
        "".join(cuerpo),
        subtitulo=f"{institucion} | {ticket.get('zona_nombre') or 'Sin zona'} > {ticket.get('oficina_nombre') or 'Sin oficina'}",
        pie_extra=f" | Responsable: {_esc(generado_por)}",
    )


async def informe_consolidado(
    *,
    titulo: str,
    subtitulo: str,
    kpis: list[tuple[str, Any]],
    tablas: list[dict[str, Any]],
    filtros_texto: str,
    generado_por: str,
    comparacion: dict[str, Any] | None = None,
) -> bytes:
    institucion = await config_service.nombre_institucion()
    cuerpo: list[str] = [f'<div class="alcance"><p><strong>Alcance del informe</strong></p><p>{_esc(subtitulo)}</p><p>{_esc(filtros_texto)}</p></div>', _kpis(kpis)]
    if comparacion:
        filas = [
            [etiqueta, comparacion.get("actual", "-"), comparacion.get("anterior", "-"), comparacion.get("variacion", "-")]
            for etiqueta in comparacion.get("etiquetas", [])
        ]
        cuerpo.append("<h2>Comparación con el periodo anterior</h2>")
        cuerpo.append(_tabla(["Indicador", "Periodo actual", "Periodo anterior", "Variacion"], filas))
    for bloque in tablas:
        cuerpo.append(f"<h2>{_esc(bloque.get('titulo'))}</h2>")
        if bloque.get('descripcion'):
            cuerpo.append(f'<p class="ayuda">{_esc(bloque["descripcion"])}</p>')
        cuerpo.append(_tabla(bloque.get("cabeceras", []), bloque.get("filas", []), vacio=bloque.get("vacio", "Sin datos"), anchos=bloque.get('anchos')))
    return _pagina(
        titulo,
        "".join(cuerpo),
        subtitulo=institucion,
        pie_extra=f" | Responsable: {_esc(generado_por)}",
        horizontal=True,
    )


async def inventario(filas: list[dict[str, Any]], *, titulo: str = "Inventario de equipos", generado_por: str, filtros_texto: str = "Situacion actual") -> bytes:
    from collections import defaultdict
    institucion = await config_service.nombre_institucion()
    zonas = defaultdict(list)
    for fila in filas:
        zonas[fila.get('zona_nombre') or 'Sin zona'].append(fila)
    cuerpo = []
    for zona, equipos in sorted(zonas.items()):
        tabla = [[f.get('oficina_nombre') or 'Sin oficina', f"{f.get('tipo') or '-'}\n{f.get('nombre_equipo') or '-'}", f.get('codigo_patrimonial') or 'Sin codigo', f.get('conjunto_nombre') or '-', f"{f.get('marca') or '-'} / {f.get('modelo') or '-'}", f.get('estado'), f.get('responsable_nombre') or 'Uso comun'] for f in equipos]
        cuerpo.append('<section class="zona-inventario">')
        cuerpo.append(f"<h2>{_esc(zona)} | {len(equipos)} equipos</h2>")
        cuerpo.append(_tabla(['Oficina', 'Equipo / tipo', 'Patrimonio', 'Conjunto', 'Marca / modelo', 'Estado', 'Responsable'], tabla, anchos=[21, 22, 12, 12, 12, 8, 13]))
        cuerpo.append('</section>')
    if not filas:
        cuerpo.append('<p class="vacio">No hay equipos que cumplan los filtros.</p>')
    return _pagina(titulo, ''.join(cuerpo), subtitulo=f"{institucion} | {filtros_texto}", pie_extra=f" | Responsable: {_esc(generado_por)}", horizontal=True)


async def ficha_equipo(activo: dict[str, Any], *, generado_por: str) -> bytes:
    institucion = await config_service.nombre_institucion()
    campos = activo.get("campos") or {}
    filas_campos = []
    for nombre, info in campos.items():
        valor = info.get("valor")
        if info.get("estado") == "no_aplica":
            valor = "No aplica"
        elif info.get("estado") == "no_disponible":
            valor = "No disponible"
        estado = info.get('estado', 'pendiente')
        filas_campos.append([etiqueta_campo(nombre), valor if valor not in (None, '') else 'Pendiente', {'no_aplica': 'No aplica', 'no_disponible': 'No disponible', 'pendiente': 'Pendiente', 'completo': 'Completo', 'presente': 'Registrado'}.get(estado, estado), info.get('motivo') or '-'])
    prediccion = activo.get("prediccion") or {}
    cuerpo = [
        _kpis(
            [
                ("Completitud", f"{activo.get('completitud', 0)}%"),
                ("Datos faltantes", activo.get("faltantes", 0)),
                ("Opciones avanzadas", "Activas" if activo.get("opciones_avanzadas") else "Desactivadas"),
                ("Riesgo 90 dias", f"{round((prediccion.get('probabilidad') or 0) * 100)}%" if prediccion else "-"),
            ]
        ),
        _tabla(
            ["Campo", "Valor", "Estado", "Motivo"],
            filas_campos,
            vacio="Este equipo no tiene campos registrados.",
        ),
    ]
    if prediccion:
        cuerpo.append("<h2>Predictivo de fallas</h2>")
        cuerpo.append(
            f'<div class="aviso">Probabilidad de falla en {prediccion.get("horizonte_dias")} dias: '
            f'{round((prediccion.get("probabilidad") or 0) * 100)}% (confianza {prediccion.get("confianza")}, '
            f'nivel {prediccion.get("nivel")}). Metodo: {_esc(prediccion.get("metodo"))}. '
            f"{_esc(prediccion.get('aviso'))}</div>"
        )
        if prediccion.get("factores"):
            cuerpo.append("<p>Factores considerados: " + _esc(", ".join(prediccion["factores"])) + "</p>")
    if activo.get("opciones_avanzadas") and activo.get("detalle_avanzado"):
        cuerpo.append("<h2>Detalle tecnico avanzado</h2>")
        filas_avanzadas = []
        for seccion, valor in activo["detalle_avanzado"].items():
            filas_avanzadas.append([seccion.replace("_", " "), valor])
        cuerpo.append(_tabla(["Seccion", "Detalle"], filas_avanzadas))
    return _pagina(
        f"Ficha de equipo: {activo.get('nombre_equipo') or activo.get('tipo')}",
        "".join(cuerpo),
        subtitulo=f"{institucion} | {activo.get('zona_nombre') or 'Sin zona'} > {activo.get('oficina_nombre') or 'Sin oficina'}",
        pie_extra=f" | Responsable: {_esc(generado_por)}",
    )


async def cierre_campana(campana: dict[str, Any], *, resumen: dict[str, Any], filas: list[dict[str, Any]], generado_por: str) -> bytes:
    institucion = await config_service.nombre_institucion()
    cuerpo = [
        _kpis(
            [
                ("Equipos revisados", resumen.get("total_items", 0)),
                ("Verificados", resumen.get("verificados", 0)),
                ("Nuevos", resumen.get("nuevos", 0)),
                ("Modificados", resumen.get("modificados", 0)),
                ("No localizados", resumen.get("discrepancias", 0)),
                ("Progreso", f"{resumen.get('progreso', 0)}%"),
            ]
        ),
        _tabla(
            ["Campo", "Valor"],
            [
                ["Campana", campana.get("codigo")],
                ["Nombre", campana.get("nombre")],
                ["Año", campana.get("anio")],
                ["Alcance", campana.get("alcance")],
                ["Periodo", f"{_formatear_fecha(campana.get('fecha_inicio'))} a {_formatear_fecha(campana.get('fecha_fin'))}"],
                ["Estado", 'Cerrada' if campana.get('estado') == 'cerrada' else 'En verificación'],
                ["Fecha de cierre", _formatear_fecha(campana.get("cerrado_en"))],
            ],
        ),
        "<h2>Detalle por equipo</h2>",
        _tabla(
            ["Equipo", "Codigo", "Oficina", "Responsable", "Estado de verificacion", "Observaciones"],
            [
                [
                    f.get("activo_nombre"),
                    f.get("activo_codigo"),
                    f.get("oficina_nombre"),
                    f.get("responsable_nombre"),
                    f.get("estado_item"),
                    f.get("observaciones"),
                ]
                for f in filas
            ],
            vacio="La campana no tiene elementos.",
        ),
    ]
    return _pagina(
        f"{'Cierre' if campana.get('estado') == 'cerrada' else 'Verificación'} de inventario {campana.get('codigo') or ''}",
        "".join(cuerpo),
        subtitulo=institucion,
        pie_extra=f" | Responsable: {_esc(generado_por)}",
    )
