"""Asistente conversacional de analisis (solo lectura, sobre datos reales).

Dos caminos, ambos honestos:
1. Con modelo de lenguaje disponible: tool calling sobre consultas seguras.
2. Sin modelo: deteccion de intencion por palabras clave y respuesta directa con
   los mismos datos reales. Nunca responde "inventando" cifras.

El chat del ticket (usuario <-> TI) es otro modulo: ver ticket_service.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from bson import ObjectId

from app.core.db import agregar, get_db
from app.core.errors import AppError, Prohibido, Validacion
from app.core.ids import clave, clave_oscura, normalizar_texto
from app.core.time import business_tz, local_date, utcnow
from app.domain.permissions import tiene_permiso
from app.services import analitica_service, horario_service, ia_provider, inventario_service

ROLES_CON_ACCESO = {"tecnico", "administrador"}

PREGUNTAS_SUGERIDAS = [
    "¿Qué oficina tiene más incidencias en el periodo seleccionado?",
    "¿Qué zona tiene más tickets?",
    "¿Qué técnico está disponible ahora?",
    "¿Cuáles son las causas más frecuentes?",
    "¿Qué familias de equipos tienen más fallas?",
    "¿Para qué sirve este asistente?",
    "¿Qué significa el porcentaje de datos faltantes?",
]

REGLAS_PERMISOS: dict[str, str] = {
    'ranking_conjuntos': 'analitica.ver',
    "ranking_oficinas": "analitica.ver",
    "ranking_zonas": "analitica.ver",
    "causas_recurrentes": "analitica.ver",
    "metricas_generales": "analitica.ver",
    "tecnicos_rendimiento": "analitica.ver",
    "disponibilidad_equipo": "equipo_ti.ver",
    "equipos_de_usuario": "equipo_ti.ver",
    "equipos_con_fallas": "equipo_ti.ver",
    "tickets_de_usuario": "tickets.ver_propios",
}


# ── Herramientas de solo lectura ─────────────────────────────
async def herramienta_ranking_oficinas(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    filtros = {**filtros, **(argumentos or {})}
    datos = await analitica_service.ranking_oficinas(filtros)
    return {
        "periodo": datos["periodo"],
        "top": datos["items"][:8],
        "total_oficinas": len(datos["items"]),
    }


async def herramienta_ranking_zonas(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    filtros = {**filtros, **(argumentos or {})}
    datos = await analitica_service.ranking_zonas(filtros)
    return {"periodo": analitica_service.resolver_periodo(filtros)[:2], "zonas": datos["items"][:8]}


async def herramienta_causas(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    filtros = {**filtros, **(argumentos or {})}
    tipo = (argumentos or {}).get("tipo_activo")
    if tipo:
        filtros["tipo_activo"] = tipo
    datos = await analitica_service.causas_recurrentes(filtros, limite=10)
    return {"items": datos["items"], "suficiente_datos": datos["suficiente_datos"]}


async def herramienta_disponibilidad(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    panel = await horario_service.panel_equipo()
    return {
        "equipo": [
            {
                "tecnico": t["tecnico_nombre"],
                "estado": t["etiqueta"],
                "carga_asignados": t["carga_asignados"],
                "carga_espera": t["carga_espera"],
                "horario_hoy": t["horario_hoy"],
                "ticket_actual": t["ticket_actual_codigo"],
            }
            for t in panel
        ],
        "consultado_en": utcnow().astimezone(business_tz()).isoformat(),
        "nota": "El estado respeta horario semanal, dias libres y ausencias registradas.",
    }


async def herramienta_tecnicos_rendimiento(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    filtros = {**filtros, **(argumentos or {})}
    datos = await analitica_service.carga_tecnicos(filtros)
    return {"items": datos["items"]}


async def herramienta_equipos_de_usuario(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    nombre = normalizar_texto((argumentos or {}).get("nombre", ""))
    if not nombre:
        raise Validacion("Indica el nombre de la persona.")
    db = get_db()
    usuarios = await db["usuarios"].find(
        {"activo": True, "$or": [{"nombre": {"$regex": re.escape(nombre), "$options": "i"}}, {"nombre_busqueda": clave_oscura(nombre)}]},
        {"nombre": 1, "oficina_nombre": 1, "email": 1},
    ).to_list(5)
    if not usuarios:
        return {"encontrado": False, "consulta": nombre, "mensaje": "No hay ninguna persona con ese nombre en el directorio."}
    exactos = [u for u in usuarios if clave_oscura(u.get("nombre", "")) == clave_oscura(nombre)]
    candidatos = exactos or usuarios
    if len(candidatos) != 1:
        return {"encontrado": False, "mensaje": "Hay varias personas con ese nombre. Indica el nombre completo: " + ", ".join(u["nombre"] for u in candidatos) + "."}
    usuario = candidatos[0]
    equipos = await inventario_service.equipos_de_usuario(usuario["_id"])
    tickets = await db["tickets"].count_documents({"afectado_id": usuario["_id"], "eliminado": {"$ne": True}})
    return {
        "encontrado": True,
        "persona": {
            "nombre": usuario.get("nombre"),
            "oficina": usuario.get("oficina_nombre"),
            "email": usuario.get("email"),
            "alternativos": [u.get("nombre") for u in usuarios[1:]],
        },
        "equipos_a_cargo": equipos["por_conjunto"],
        "uso_comun_oficina": [e["nombre_equipo"] or e["tipo"] for e in equipos["uso_comun_oficina"]][:10],
        "tickets_historial": tickets,
    }


async def herramienta_equipos_con_fallas(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    from app.services import ml_service

    familias = await ml_service.predecir_familias(limite=10)
    return {
        "familias": familias,
        "modelo": {
            "muestras": familias[0].get("suficiente_datos") if familias else False,
            "minimo_requerido": ml_service.MINIMO_MUESTRAS_MODELO,
        },
    }


async def herramienta_tickets_de_usuario(filtros: dict[str, Any], argumentos: dict[str, Any]) -> dict[str, Any]:
    nombre = normalizar_texto((argumentos or {}).get("nombre", ""))
    db = get_db()
    usuarios = await db["usuarios"].find(
        {"nombre": {"$regex": re.escape(nombre), "$options": "i"}}, {"nombre": 1}
    ).to_list(3) if nombre else []
    if not usuarios:
        return {"encontrado": False, "mensaje": "Indica el nombre de la persona."}
    exactos = [u for u in usuarios if clave_oscura(u.get("nombre", "")) == clave_oscura(nombre)]
    candidatos = exactos or usuarios
    if len(candidatos) != 1:
        return {"encontrado": False, "mensaje": "Hay varias personas con ese nombre. Indica el nombre completo: " + ", ".join(u["nombre"] for u in candidatos) + "."}
    persona = candidatos[0]
    id_usuario = persona["_id"]
    totales = await agregar("tickets", [
            {"$match": {"eliminado": {"$ne": True}, "$or": [{"reportante_id": id_usuario}, {"afectado_id": id_usuario}]}},
            {"$group": {"_id": "$estado", "total": {"$sum": 1}}},
        ])
    return {
        "encontrado": True,
        "persona": persona.get("nombre"),
        "por_estado": [{"estado": t["_id"], "total": t["total"]} for t in totales],
    }


async def herramienta_ranking_conjuntos(filtros, argumentos):
    return await analitica_service.ranking_conjuntos({**filtros, **(argumentos or {})})


HERRAMIENTAS: dict[str, dict[str, Any]] = {
    'ranking_conjuntos': {'funcion': herramienta_ranking_conjuntos, 'descripcion': 'Computadoras o conjuntos con más incidencias, incluidos sus programas y componentes, con oficina y responsable actual.', 'esquema': {'type': 'object', 'properties': {}}},
    "ranking_oficinas": {
        "funcion": herramienta_ranking_oficinas,
        "descripcion": "Ranking de incidencias por oficina con total y tasa normalizada por equipo y usuario.",
        "esquema": {
            "type": "object",
            "properties": {"periodo": {"type": "string", "enum": ["7d", "30d", "90d", "mes", "anio"]}},
        },
    },
    "ranking_zonas": {
        "funcion": herramienta_ranking_zonas,
        "descripcion": "Ranking de incidencias por zona con desglose por oficina.",
        "esquema": {"type": "object", "properties": {}},
    },
    "causas_recurrentes": {
        "funcion": herramienta_causas,
        "descripcion": "Causas y problemas que mas se repiten, con tendencia respecto al periodo anterior.",
        "esquema": {
            "type": "object",
            "properties": {"tipo_activo": {"type": "string", "description": "Tipo de equipo, por ejemplo Impresora"}},
        },
    },
    "disponibilidad_equipo": {
        "funcion": herramienta_disponibilidad,
        "descripcion": "Estado actual de cada tecnico segun horario, ausencias y carga de tickets.",
        "esquema": {"type": "object", "properties": {}},
    },
    "tecnicos_rendimiento": {
        "funcion": herramienta_tecnicos_rendimiento,
        "descripcion": "Carga y desempenho por tecnico normalizados por horas laborables reales.",
        "esquema": {"type": "object", "properties": {}},
    },
    "equipos_de_usuario": {
        "funcion": herramienta_equipos_de_usuario,
        "descripcion": "Equipos a cargo de una persona y equipos de uso comun de su oficina.",
        "esquema": {
            "type": "object",
            "properties": {"nombre": {"type": "string", "description": "Nombre de la persona"}},
            "required": ["nombre"],
        },
    },
    "equipos_con_fallas": {
        "funcion": herramienta_equipos_con_fallas,
        "descripcion": "Familias de equipos con mayor tasa de falla y prediccion de probabilidad.",
        "esquema": {"type": "object", "properties": {}},
    },
    "tickets_de_usuario": {
        "funcion": herramienta_tickets_de_usuario,
        "descripcion": "Resumen de tickets de una persona por estado.",
        "esquema": {
            "type": "object",
            "properties": {"nombre": {"type": "string"}},
            "required": ["nombre"],
        },
    },
}


def esquema_herramientas_openai() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": nombre,
                "description": config["descripcion"],
                "parameters": config["esquema"],
            },
        }
        for nombre, config in HERRAMIENTAS.items()
    ]


async def ejecutar_herramienta(
    nombre: str, argumentos: dict[str, Any], *, filtros: dict[str, Any], usuario: dict[str, Any]
) -> Any:
    config = HERRAMIENTAS.get(nombre)
    if config is None:
        raise Validacion(f"Herramienta desconocida: {nombre}")
    permiso = REGLAS_PERMISOS.get(nombre)
    if permiso and not tiene_permiso(usuario, permiso) and usuario.get("rol") != "administrador":
        raise Prohibido("Tu rol no tiene acceso a esa consulta.", codigo="sin_permiso_analitica")
    return await config["funcion"](filtros, argumentos or {})


# ── Deteccion de intencion sin modelo ────────────────────────
INTENCIONES: list[tuple[str, str]] = [
    (r"oficina.*(mas|más|top|primer)|cual oficina|que oficina", "ranking_oficinas"),
    (r"zona.*(mas|más|top|que zona)|cual zona", "ranking_zonas"),
    (r"(impresora|printer).*(falla|error|problema)|falla.*impresora", "equipos_con_fallas"),
    (r"(falla|error).*(equipo|computadora|monitor|router|cpu|laptop)", "equipos_con_fallas"),
    (r"(libre|disponible|disponibilidad|carga).*(tecnico|equipo ti|ahora)|quien esta (libre|disponible)", "disponibilidad_equipo"),
    (r"(resuelve mas rapido|mejor tecnico|mas rapido|buen tecnico|recomienda.*tecnico)", "tecnicos_rendimiento"),
    (r"que (equipos|computadoras).*(tiene|asignad)|equipos de .*|tiene asignados", "equipos_de_usuario"),
    (r"tickets? de |tickets? de .*persona", "tickets_de_usuario"),
    (r"(repite|recurrente|mas comun|más común|causa)", "causas_recurrentes"),
    (r"reducir tickets|recomienda.*(oficina|comuna|zona)|mejorar", "ranking_oficinas"),
]


def _detectar_intencion(pregunta: str) -> tuple[str | None, dict[str, Any]]:
    import unicodedata
    texto = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower()) if not unicodedata.combining(c))
    if re.search(r'conjunto|pc.*(incidencia|falla)|computadora.*(incidencia|falla)', texto):
        return 'ranking_conjuntos', {}
    if re.search(r"(tecnico|equipo ti).*(libre|disponible|disponibilidad|carga)", texto):
        return "disponibilidad_equipo", {}
    if re.search(r"(equipo|familia).*(falla|incidencia)|fallaron", texto):
        return "equipos_con_fallas", {}
    if re.search(r"(zona).*(ticket|incidencia)|que zona", texto):
        return "ranking_zonas", {}
    if re.search(r"(frecuente|mas comun|causa)", texto):
        return "causas_recurrentes", {}
    for patron, herramienta in INTENCIONES:
        if re.search(patron, texto):
            argumentos: dict[str, Any] = {}
            for tipo in ("impresora", "monitor", "laptop", "cpu", "router", "teclado", "mouse", "impresoras"):
                if tipo in texto or f"{tipo}s" in texto:
                    argumentos["tipo_activo"] = tipo.capitalize()
                    break
            nombre = re.search(r"(?:equipos?|tickets?) de ([a-zA-ZñÑáéíóúÁÉÍÓÚ\s]+)", pregunta, re.IGNORECASE)
            if not nombre:
                nombre = re.search(r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)", pregunta)
            if nombre and herramienta in {"equipos_de_usuario", "tickets_de_usuario"}:
                argumentos["nombre"] = nombre.group(1).strip()
            return herramienta, argumentos
    # Sin intencion clara: el asistente responde con consultas directas y lo dice
    return None, {}


def _formatear(herramienta: str, datos: Any) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None]:
    """Texto claro + tabla + enlaces, a partir de datos reales."""
    if herramienta == 'ranking_conjuntos':
        filas = datos.get('items', [])[:10]
        if not filas:
            return 'No hay incidencias vinculadas a computadoras en este periodo.', [], None
        lineas = ['Computadoras con más incidencias (componentes y programas incluidos):']
        lineas.extend(f"- {f['nombre']} · {f['oficina']} · {f['responsable']}: {f['total']} tickets, {f['programas']} de programas." for f in filas)
        return '\n'.join(lineas), [], None
    if herramienta == "ranking_oficinas" and datos.get("top"):
        primero = datos['top'][0]
        lideres = [i['oficina'] for i in datos['top'] if i['total'] == primero['total']]
        sujeto = ', '.join(lideres)
        resultado = f"{sujeto} registra {primero['total']} tickets" if len(lideres) == 1 else f"{sujeto} comparten el primer lugar con {primero['total']} tickets cada una"
        lineas = [f"{resultado}, entre el {_fecha_visible(datos['periodo']['desde'])} y el {_fecha_visible(datos['periodo']['hasta'])}.",
                  'La comparación por equipo y por usuario ayuda a considerar el tamaño de cada oficina; el volumen de tickets por sí solo no mide la gravedad de las fallas.']
        tabla = {
            "columnas": [
                {"clave": "oficina", "titulo": "Oficina"},
                {"clave": "total", "titulo": "Tickets"},
                {"clave": "por_equipo", "titulo": "Por equipo"},
                {"clave": "por_usuario", "titulo": "Por usuario"},
            ],
            "filas": datos["top"][:10],
        }
        enlaces = [{"texto": item["oficina"], "href": f"/panel/oficinas/{item['id']}"} for item in datos["top"][:5] if item.get("id")]
        return "\n".join(lineas), [], {"tabla": tabla, "enlaces": enlaces}
    if herramienta == "ranking_zonas" and datos.get("zonas"):
        primero = datos['zonas'][0]
        lideres = [z['zona'] for z in datos['zonas'] if z['total'] == primero['total']]
        resultado = f"{', '.join(lideres)} concentra {primero['total']} tickets" if len(lideres) == 1 else f"{', '.join(lideres)} empatan con {primero['total']} tickets por zona"
        periodo = datos.get('periodo') or []
        rango = f", entre el {_fecha_visible(periodo[0])} y el {_fecha_visible(periodo[1])}" if len(periodo) >= 2 else ' en el periodo consultado'
        detalle = ''
        if len(lideres) == 1 and primero.get('oficinas'):
            oficina = primero['oficinas'][0]
            detalle = f"\n\nSu oficina con mayor volumen es {oficina['oficina']}, con {oficina['total']} tickets."
        tabla = {'columnas': [{'clave': 'zona', 'titulo': 'Zona'}, {'clave': 'total', 'titulo': 'Tickets'}, {'clave': 'abiertos', 'titulo': 'Abiertos'}], 'filas': datos['zonas']}
        return resultado + rango + '.' + detalle, [], {'tabla': tabla}
    if herramienta == "disponibilidad_equipo" and datos.get("equipo"):
        lineas = [f"Disponibilidad del equipo TI al {_fecha_visible(datos['consultado_en'])}:"]
        for tecnico in datos["equipo"]:
            detalle = f"{tecnico['carga_asignados']} ticket(s) asignados"
            if tecnico.get("ticket_actual"):
                detalle += f", trabajando en {tecnico['ticket_actual']}"
            lineas.append(f"- {tecnico['tecnico']}: {tecnico['estado']} - {detalle}")
        lineas.append(datos["nota"])
        tabla = {
            "columnas": [
                {"clave": "tecnico", "titulo": "Tecnico"},
                {"clave": "estado", "titulo": "Estado"},
                {"clave": "carga_asignados", "titulo": "Asignados"},
                {"clave": "carga_espera", "titulo": "En espera"},
            ],
            "filas": datos["equipo"],
        }
        return "\n".join(lineas), [], {"tabla": tabla}
    if herramienta == "tecnicos_rendimiento" and datos.get("items"):
        lineas = ["Carga y tiempo de resolución por técnico (normalizado por horas laborables):"]
        filas = []
        for item in datos["items"]:
            if not item.get("tecnico"):
                continue
            if not item.get("suficiente_datos"):
                lineas.append(
                    f"- {item['tecnico']}: {item['resueltos']} ticket(s) resueltos. Datos insuficientes para comparar rendimiento."
                )
                continue
            lineas.append(
                f"- {item['tecnico']}: {item['resueltos']} resueltos, {item['tiempo_medio_resolucion_min']} min en promedio, "
                f"{item['tickets_por_hora']} ticket(s) por hora laborable, cumplimiento de SLA {item['cumplimiento_sla']}%."
            )
            filas.append(item)
        tabla = {
            "columnas": [
                {"clave": "tecnico", "titulo": "Tecnico"},
                {"clave": "resueltos", "titulo": "Resueltos"},
                {"clave": "tiempo_medio_resolucion_min", "titulo": "Min promedio"},
                {"clave": "tickets_por_hora", "titulo": "Ticket/hora"},
                {"clave": "cumplimiento_sla", "titulo": "SLA %"},
            ],
            "filas": filas,
        }
        return "\n".join(lineas), [], {"tabla": tabla}
    if herramienta == "equipos_de_usuario":
        if not datos.get("encontrado"):
            return datos.get("mensaje", "No se encontro la persona solicitada."), [], None
        persona = datos["persona"]
        lineas = [f"Equipos de {persona['nombre']} ({persona.get('oficina') or 'sin oficina'}):"]
        for grupo in datos.get("equipos_a_cargo", []):
            nombres = ", ".join(
                f"{e.get('nombre_equipo') or e.get('tipo')} ({e.get('estado') or 'sin estado'})" for e in grupo.get("equipos", [])
            )
            lineas.append(f"- {grupo['conjunto']}: {nombres or 'sin equipos'}")
        if not datos.get("equipos_a_cargo"):
            lineas.append("- No tiene equipos asignados como responsable.")
        if datos.get("uso_comun_oficina"):
            lineas.append(f"- Equipos de uso comun de la oficina: {', '.join(datos['uso_comun_oficina'])}")
        lineas.append(f"- Tickets en su historial: {datos.get('tickets_historial', 0)}")
        return "\n".join(lineas), [], None
    if herramienta == "equipos_con_fallas":
        familias = datos.get("familias") or []
        if not familias:
            return "No hay historial de fallas por tipo de equipo todavia.", [], None
        lineas = ['Historial de incidencias por tipo de equipo en los últimos 12 meses. Este periodo es independiente del filtro de la pantalla.']
        filas = []
        for familia in familias[:6]:
            linea = (
                f"- {familia['tipo']}: {familia['tickets_12m']} ticket(s) en {familia['activos']} equipos "
                f"({familia['tickets_por_equipo']} por equipo, riesgo {familia['nivel']})"
            )
            if not familia.get("suficiente_datos"):
                linea += f". El modelo necesita {familia.get('minimo_requerido', 30)} equipos con historial; hoy hay datos parciales."
            linea += f". Equipos con incidencias en los últimos 12 meses: {round(100 * familia['tasa_falla'], 1)}%. No es una predicción futura."
            if len(filas) == 0:
                lineas.append(linea.lstrip('- '))
            filas.append({**familia, 'porcentaje_afectados': round(100 * familia['tasa_falla'], 1)})
        tabla = {
            "columnas": [
                {"clave": "tipo", "titulo": "Tipo"},
                {"clave": "activos", "titulo": "Equipos"},
                {"clave": "tickets_12m", "titulo": "Tickets 12m"},
                {"clave": "tickets_por_equipo", "titulo": "Por equipo"},
                {"clave": "porcentaje_afectados", "titulo": "Equipos con incidencias (%)"},
            ],
            "filas": filas,
        }
        return "\n".join(lineas), [], {"tabla": tabla}
    if herramienta == "causas_recurrentes":
        items = datos.get("items") or []
        if not items:
            return "Todavia no hay suficientes tickets en el periodo para identificar causas recurrentes.", [], None
        lineas = ["Lo que mas se repite:"]
        for item in items[:6]:
            tendencia = ""
            if item.get("tendencia") is not None:
                if item["tendencia"] > 0:
                    tendencia = f" (sube {abs(item['tendencia'])}%)"
                elif item["tendencia"] < 0:
                    tendencia = f" (baja {abs(item['tendencia'])}%)"
                else:
                    tendencia = " (estable)"
            lineas.append(
                f"- {item.get('categoria') or 'sin categoria'} / {item.get('equipo') or 'sin equipo'}: {item['total']} casos{tendencia}"
            )
        return "\n".join(lineas), [], None
    if herramienta == "tickets_de_usuario":
        if not datos.get("encontrado"):
            return datos.get("mensaje", "No se encontro la persona."), [], None
        resumen = ", ".join(f"{t['estado']}: {t['total']}" for t in datos.get("por_estado", []))
        return f"Tickets de {datos['persona']} - {resumen or 'sin tickets registrados'}.", [], None
    if herramienta in {'ranking_oficinas', 'ranking_zonas', 'tecnicos_rendimiento'}:
        return 'No se encontraron registros para esta consulta en el periodo elegido. Esto no permite comparar resultados; prueba otro rango de fechas.', [], None
    return "No pude obtener datos para esa consulta.", [], None


def _fecha_visible(valor):
    from datetime import date, datetime
    if isinstance(valor, datetime):
        return valor.astimezone(business_tz()).strftime('%d/%m/%Y %H:%M')
    if isinstance(valor, date):
        return valor.strftime('%d/%m/%Y')
    try:
        if 'T' in str(valor):
            return datetime.fromisoformat(str(valor)).astimezone(business_tz()).strftime('%d/%m/%Y %H:%M')
        return date.fromisoformat(str(valor)).strftime('%d/%m/%Y')
    except ValueError:
        return str(valor)


def _periodo_pregunta(pregunta: str, filtros: dict[str, Any]) -> dict[str, Any]:
    """Las fechas explícitas de la pregunta prevalecen sobre el selector."""
    texto = clave(pregunta).lower()
    resultado = dict(filtros)
    fechas = re.findall(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b", pregunta)
    if fechas:
        if len(fechas) > 2:
            raise Validacion("Indica una fecha o un rango de dos fechas.")
        try:
            dias = [date.fromisoformat(f) if '-' in f else date(*map(int, reversed(f.split('/')))) for f in fechas]
        except ValueError:
            raise Validacion("Las fechas de la pregunta no son válidas. Usa día/mes/año.")
        resultado.update(desde=dias[0], hasta=dias[-1])
    elif re.search(r"\b(hoy|ayer)\b", texto):
        if re.search(r"\bhoy\b", texto) and re.search(r"\bayer\b", texto):
            raise Validacion("Indica un rango de fechas para comparar hoy y ayer.")
        dia = local_date() - timedelta(days=1 if re.search(r"\bayer\b", texto) else 0)
        resultado.update(desde=dia, hasta=dia)
    else:
        for expresion, periodo in (("este mes", "mes"), ("este ano", "anio"), ("ultimos 90", "90d"), ("ultimos 30", "30d"), ("ultimos 7", "7d")):
            if expresion in texto:
                resultado.update(periodo=periodo)
                resultado.pop("desde", None)
                resultado.pop("hasta", None)
                break
    analitica_service.resolver_periodo(resultado)
    if fechas or re.search(r"\b(hoy|ayer)\b", texto):
        resultado["periodo"] = f"{resultado['desde']:%d/%m/%Y} – {resultado['hasta']:%d/%m/%Y}"
    return resultado


async def responder(
    pregunta: str,
    *,
    usuario: dict[str, Any],
    filtros: dict[str, Any] | None = None,
    conversacion_id: ObjectId | None = None,
    historial: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Responde una pregunta de analitica usando datos reales del sistema."""
    if usuario.get("rol") not in ROLES_CON_ACCESO:
        raise Prohibido("El asistente de analisis es solo para personal autorizado.")
    from app.services.ayuda_analisis import responder_ayuda
    ayuda = responder_ayuda(pregunta)
    if ayuda:
        return {'texto': ayuda, 'tabla': None, 'enlaces': [], 'fuentes': ['guia_analisis'],
                'explicacion': 'Orientación funcional del sistema, sin consultar un modelo externo. No representa un recuento de registros.',
                'periodo': None, 'confianza': 1.0, 'suficiente_datos': True, 'herramientas': []}
    filtros = _periodo_pregunta(pregunta, filtros or {})
    db = get_db()
    proveedor = ia_provider.obtener_proveedor()
    # Las preguntas reconocidas se resuelven directamente: no necesitan tokens
    # de un proveedor ni dependen de su disponibilidad para redactar cifras.
    conocida, _ = _detectar_intencion(pregunta)
    llm = False if conocida else await proveedor.disponible()
    mensajes_usados: list[str] = []
    explicacion = ""

    if llm:
        herramientas = [h for h in esquema_herramientas_openai() if _permitida(h["function"]["name"], usuario)]
        mensajes = [
            {
                "role": "system",
                "content": (
                    "Eres el asistente de analisis de una mesa de ayuda TI municipal. Respondes SOLO con datos "
                    "obtenidos de las herramientas. Si una herramienta no esta disponible, dilo. No inventes cifras, "
                    "equipos ni personas. Cita siempre el periodo consultado. Responde en espanol claro y breve. "
                    "Responde unicamente a la pregunta; no realices acciones."
                    f" Filtros de esta consulta: {json.dumps(filtros, default=str, ensure_ascii=False)}."
                ),
            }
        ]
        for item in (historial or [])[-6:]:
            if item.get("rol") in {"user", "assistant"} and item.get("texto"):
                mensajes.append({"role": item["rol"], "content": item["texto"][:800]})
        mensajes.append({"role": "user", "content": pregunta})
        respuesta = await proveedor.completar(mensajes, herramientas=herramientas or None, temperatura=0.0)
        if respuesta.disponible:
            if respuesta.llamadas:
                resultados: list[dict[str, Any]] = []
                for llamada in respuesta.llamadas[:3]:
                    nombre = llamada.get("nombre") or ""
                    if nombre not in HERRAMIENTAS or not _permitida(nombre, usuario):
                        continue
                    argumentos = llamada.get("argumentos") or {}
                    if not isinstance(argumentos, dict):
                        continue
                    datos = await ejecutar_herramienta(nombre, argumentos, filtros=filtros, usuario=usuario)
                    mensajes_usados.append(nombre)
                    resultados.append({"herramienta": nombre, "datos": datos})
                if not resultados:
                    return {"texto": "No se obtuvo una consulta autorizada que respalde la respuesta. Elige una consulta sugerida.",
                            "tabla": None, "enlaces": [], "confianza": 0.0, "fuentes": [], "herramientas": [],
                            "suficiente_datos": False, "puede_responder": False, "periodo": filtros.get("periodo", "30d")}
                segunda = await proveedor.completar(
                    mensajes
                    + [
                        {
                            "role": "user",
                            "content": json.dumps(resultados, ensure_ascii=False, default=str)[:8000],
                        },
                        {"role": "system", "content": "Redacta la respuesta final usando solo estos resultados."},
                    ],
                    temperatura=0.0,
                )
                texto = segunda.texto if segunda.disponible else ""
                if not texto.strip() and resultados:
                    texto = "\n\n".join(_formatear(r["herramienta"], r["datos"])[0] for r in resultados)
                if not texto.strip():
                    texto = "No pude completar la consulta. Inténtalo de nuevo."
                extras = {"datos": resultados}
                detalle = _formatear(resultados[0]["herramienta"], resultados[0]["datos"])[2] if len(resultados) == 1 else None
                await ia_service_registrar(pregunta, texto, usuario, mensajes_usados)
                return {
                    "texto": texto,
                    "tabla": (detalle or {}).get("tabla"),
                    "enlaces": (detalle or {}).get("enlaces"),
                    "confianza": 0.75,
                    "explicacion": explicacion or "Respuesta construida con datos reales del sistema.",
                    "herramientas": mensajes_usados,
                    "fuentes": mensajes_usados,
                    "suficiente_datos": bool(resultados) and all(r["datos"].get("suficiente_datos", True) for r in resultados),
                    "extras": extras,
                    "periodo": filtros.get("periodo", "30d"),
                }
            # Sin herramientas no hay respaldo para cifras del modelo:
            # se utiliza la consulta directa que corresponde a la pregunta.

    # ── Camino sin modelo: intencion + datos reales ──────────
    herramienta, argumentos = _detectar_intencion(pregunta)
    if herramienta is None:
        texto = (
            "Esta pregunta no coincide con una consulta de datos disponible. Puedo comparar tickets por zona u oficina, "
            "revisar causas frecuentes, disponibilidad de TI e inventario por persona.\n\n"
            "Elige una sugerencia para obtener un resultado verificable. Para orientación técnica o preguntas generales, usa el chatbot TI."
        )
        return {
            "texto": texto,
            "tabla": {"columnas": [], "filas": []},
            "confianza": 0.0,
            "explicacion": "No se obtuvo una consulta verificable que respalde una respuesta a esta pregunta.",
            "herramientas": [],
            "fuentes": [],
            "puede_responder": False,
            "preguntas_sugeridas": PREGUNTAS_SUGERIDAS,
            "periodo": filtros.get("periodo", "30d"),
        }
    try:
        datos = await ejecutar_herramienta(herramienta, argumentos, filtros=filtros, usuario=usuario)
    except Exception as exc:
        return {
            "texto": exc.mensaje if isinstance(exc, AppError) else 'No se pudo completar la lectura de datos. Revisa el periodo e inténtalo nuevamente.',
            "tabla": None,
            "confianza": 0.0,
            "explicacion": "La consulta no pudo completarse.",
            "herramientas": [],
            "fuentes": [],
            "puede_responder": False,
            "periodo": filtros.get("periodo", "30d"),
        }
    texto, _, extras = _formatear(herramienta, datos)
    explicacion = 'Resultado calculado mediante una consulta de solo lectura a los datos del sistema. No se ha utilizado un modelo externo para redactar esta respuesta.'
    await ia_service_registrar(pregunta, texto, usuario, [herramienta])
    suficiente = bool(datos.get("suficiente_datos", True)) if isinstance(datos, dict) else True
    respuesta: dict[str, Any] = {
        "texto": texto,
        "tabla": (extras or {}).get("tabla"),
        "confianza": 0.7,
        "explicacion": explicacion,
        "herramientas": [herramienta],
        "fuentes": [herramienta],
        "suficiente_datos": suficiente,
        "periodo": filtros.get("periodo", "30d"),
        "enlaces": (extras or {}).get("enlaces"),
    }
    if not suficiente and isinstance(datos, dict):
        # Honestidad: si no hay datos, dice cuantos necesita en vez de inventar
        respuesta["minimo_requerido"] = datos.get("minimo_requerido")
        minimo = datos.get('minimo_requerido')
        respuesta["explicacion"] = f"{explicacion} Datos insuficientes" + (f": se necesitan {minimo} registros." if minimo else " para obtener conclusiones fiables.")
    return respuesta


def _permitida(herramienta: str, usuario: dict[str, Any]) -> bool:
    permiso = REGLAS_PERMISOS.get(herramienta)
    if usuario.get("rol") == "administrador":
        return True
    return bool(permiso) and tiene_permiso(usuario, permiso)


async def ia_service_registrar(pregunta: str, respuesta: str, usuario: dict[str, Any], herramientas: list[str]) -> None:
    from app.services import ia_service

    await ia_service.registrar_consulta(
        pregunta, respuesta, usuario=usuario, fuentes=[{"herramienta": h} for h in herramientas]
    )


# ── Conversaciones ───────────────────────────────────────────
async def guardar_conversacion(
    usuario: dict[str, Any], *, titulo: str | None = None, conversacion_id: ObjectId | None = None
) -> dict[str, Any]:
    db = get_db()
    if conversacion_id:
        existente = await db["conversaciones_ia"].find_one({"_id": conversacion_id, "usuario_id": usuario["_id"]})
        if existente:
            return existente
        raise Prohibido("No se encontró esa conversación.")
    documento = {
        "titulo": titulo or "Consulta de analisis",
        "usuario_id": usuario["_id"],
        "usuario_nombre": usuario.get("nombre"),
        "rol": usuario.get("rol"),
        "mensajes": [],
        "creado_en": utcnow(),
        "actualizado_en": utcnow(),
    }
    resultado = await db["conversaciones_ia"].insert_one(documento)
    documento["_id"] = resultado.inserted_id
    return documento


async def agregar_mensaje(
    conversacion_id: ObjectId, rol: str, texto: str, extras: dict[str, Any] | None, usuario: dict[str, Any]
) -> None:
    db = get_db()
    mensaje = {
        "rol": rol,
        "texto": texto,
        "created_at": utcnow().isoformat(),
        "tabla": (extras or {}).get("tabla"),
        "enlaces": (extras or {}).get("enlaces"),
        "confianza": (extras or {}).get("confianza"),
        "explicacion": (extras or {}).get("explicacion"),
        "fuentes": (extras or {}).get("fuentes") or [],
        "periodo": (extras or {}).get("periodo"),
    }
    await db["conversaciones_ia"].update_one(
        {"_id": conversacion_id},
        {"$push": {"mensajes": mensaje}, "$set": {"actualizado_en": utcnow()}},
    )


async def listar_conversaciones(usuario: dict[str, Any], limite: int = 20) -> list[dict[str, Any]]:
    documentos = await (
        get_db()["conversaciones_ia"]
        .find({"usuario_id": usuario["_id"]}, {"mensajes": 0})
        .sort("actualizado_en", -1)
        .limit(limite)
        .to_list(None)
    )
    for documento in documentos:
        documento["id"] = documento.pop("_id")
    return documentos


async def obtener_conversacion(conversacion_id: ObjectId, usuario: dict[str, Any]) -> dict[str, Any]:
    documento = await get_db()["conversaciones_ia"].find_one({"_id": conversacion_id, "usuario_id": usuario["_id"]})
    if documento is None:
        raise Prohibido("No se encontro esa conversacion.")
    documento["id"] = documento.pop("_id")
    return documento


async def eliminar_conversacion(conversacion_id: ObjectId, usuario: dict[str, Any]) -> None:
    await get_db()["conversaciones_ia"].delete_one({"_id": conversacion_id, "usuario_id": usuario["_id"]})
