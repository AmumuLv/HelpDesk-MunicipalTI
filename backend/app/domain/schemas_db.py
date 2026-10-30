"""Nombres de colecciones y definicion de indices.

Un solo lugar donde se declara la forma de la base de datos. Las colecciones se
crean con validacion ``$jsonSchema`` y los indices se crean al migrar.
"""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING  # reexportado: los indices de este modulo lo usan

# ── Colecciones ──────────────────────────────────────────────
COLECCIONES = (
    "zonas",
    "oficinas",
    "usuarios",
    "sesiones",
    "tecnicos_perfil",
    "ausencias",
    "feriados",
    "catalogos",
    "esquemas_tipos",
    "valores_inventario",
    "respuestas_rapidas",
    "conjuntos",
    "activos",
    "historial_responsables",
    "activos_cambios_componentes",
    "tickets",
    "ticket_eventos",
    "ticket_mensajes",
    "notas_internas",
    "adjuntos",
    "articulos_kb",
    "articulos_kb_valoraciones",
    "campanas_inventario",
    "campana_items",
    "inventario_versiones",
    "importaciones",
    "ia_eventos",
    "auditoria",
    "exportaciones",
    "notificaciones",
    "conversaciones_ia",
    "vistas_guardadas",
    "configuracion",
    "contadores",
    "_migraciones",
)

# ── Validadores de esquema (colecciones criticas) ────────────
# Son deliberadamente permisivos en tipos opcionales: el sistema nunca debe
# perder informacion por una validacion demasiado estricta.
VALIDADORES: dict[str, dict[str, Any]] = {
    "zonas": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["nombre", "nombre_normalizado"],
            "properties": {
                "nombre": {"bsonType": "string", "minLength": 1, "maxLength": 120},
                "nombre_normalizado": {"bsonType": "string"},
                "activa": {"bsonType": "bool"},
            },
        }
    },
    "oficinas": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["nombre", "nombre_normalizado", "zona_id"],
            "properties": {
                "nombre": {"bsonType": "string", "minLength": 1, "maxLength": 120},
                "nombre_normalizado": {"bsonType": "string"},
                "zona_id": {"bsonType": "objectId"},
            },
        }
    },
    "usuarios": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["nombre", "rol", "nombre_busqueda"],
            "properties": {
                "nombre": {"bsonType": "string", "minLength": 1, "maxLength": 160},
                "nombre_busqueda": {"bsonType": "string"},
                "rol": {"enum": ["usuario", "tecnico", "administrador"]},
                "superadministrador": {"bsonType": "bool"},
                "activo": {"bsonType": "bool"},
                "zona_id": {"bsonType": ["objectId", "null"]},
                "oficina_id": {"bsonType": ["objectId", "null"]},
                "preferencias": {
                    "bsonType": "object",
                    "properties": {
                        "recomendaciones_ia": {"bsonType": "bool"},
                        "idioma": {"bsonType": "string"},
                    },
                },
                "permisos": {"bsonType": "object"},
            },
        }
    },
    "tickets": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["codigo", "asunto", "estado", "origen"],
            "properties": {
                "codigo": {"bsonType": "string"},
                "asunto": {"bsonType": "string"},
                "estado": {
                    "enum": [
                        "nuevo",
                        "en_progreso",
                        "en_espera",
                        "cerrado",
                    ]
                },
                "prioridad": {"enum": ["baja", "media", "alta", "critica"]},
                "origen": {
                    "enum": [
                        "usuario",
                        "usuario_por_companero",
                        "tecnico",
                        "administrador",
                        "automatico",
                    ]
                },
            },
        }
    },
    "activos": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["tipo", "oficina_id", "campos_estado"],
            "properties": {
                "tipo": {"bsonType": "string", "minLength": 1},
                "oficina_id": {"bsonType": "objectId"},
                "zona_id": {"bsonType": ["objectId", "null"]},
                "codigo_patrimonial": {"bsonType": ["string", "null"]},
                "opciones_avanzadas": {"bsonType": "bool"},
                "campos_estado": {"bsonType": "object"},
            },
        }
    },
}

# ── Indices ──────────────────────────────────────────────────
# (coleccion, nombre, clave, opciones)
INDICE_CODIGO_ACTIVO = [("codigo_patrimonial", 1)]

INDEXES: tuple[tuple[str, str, Any, dict[str, Any]], ...] = (
    # ── Organizacion ──
    ("zonas", "uq_zonas_nombre", [("nombre_normalizado", 1)], {"unique": True}),
    ("oficinas", "uq_oficinas_zona_nombre", [("zona_id", 1), ("nombre_normalizado", 1)], {"unique": True}),
    ("oficinas", "ix_oficinas_zona", [("zona_id", 1)], {}),
    # ── Usuarios ──
    (
        "usuarios",
        "uq_usuarios_email",
        [("email_normalizado", 1)],
        {"unique": True, "partialFilterExpression": {"email_normalizado": {"$type": "string"}}},
    ),
    ("usuarios", "ix_usuarios_nombre", [("nombre_busqueda", 1)], {}),
    ("usuarios", "ix_usuarios_oficina", [("oficina_id", 1), ("activo", 1)], {}),
    ("usuarios", "ix_usuarios_zona", [("zona_id", 1), ("activo", 1)], {}),
    ("usuarios", "ix_usuarios_rol", [("rol", 1), ("activo", 1)], {}),
    (
        "usuarios",
        "ix_usuarios_busqueda",
        [("nombre", "text"), ("email", "text")],
        {"weights": {"nombre": 10, "email": 5}, "default_language": "none"},
    ),
    ("sesiones", "ix_sesiones_usuario", [("usuario_id", 1), ("revocado", 1)], {}),
    ("sesiones", "ix_sesiones_expira", [("expira", 1)], {"expireAfterSeconds": 0}),
    ("tecnicos_perfil", "uq_tecnicos_usuario", [("usuario_id", 1)], {"unique": True}),
    ("ausencias", "ix_ausencias_tecnico", [("tecnico_id", 1), ("inicio", 1)], {}),
    ("feriados", "uq_feriados_fecha", [("fecha", 1)], {"unique": True}),
    ("esquemas_tipos", "ix_esquemas_tipo", [("tipo", 1)], {"unique": True}),
    (
        "valores_inventario",
        "ix_valores_campo_tipo",
        [("campo", 1), ("tipo", 1), ("frecuencia", -1)],
        {},
    ),
    ("valores_inventario", "ix_valores_marca", [("campo", 1), ("marca", 1), ("frecuencia", -1)], {}),
    ("respuestas_rapidas", "ix_rapidas_categoria", [("categoria", 1)], {}),
    # ── Inventario ──
    ("conjuntos", "ix_conjuntos_oficina", [("oficina_id", 1)], {}),
    ("conjuntos", "uq_conjuntos_oficina_numero", [("oficina_id", 1), ("numero", 1)], {"unique": True}),
    ("conjuntos", "ix_conjuntos_responsable", [("responsable_id", 1)], {}),
    (
        "activos",
        "ix_activos_codigo",
        INDICE_CODIGO_ACTIVO,
        {},
    ),
    ("activos", "uq_activos_clave_natural", [("clave_natural", 1)], {"unique": True}),
    ("activos", "ix_activos_oficina", [("oficina_id", 1), ("tipo", 1)], {}),
    ("activos", "ix_activos_zona", [("zona_id", 1), ("tipo", 1)], {}),
    ("activos", "ix_activos_responsable", [("responsable_id", 1)], {}),
    ("activos", "ix_activos_conjunto", [("conjunto_id", 1)], {}),
    ("activos", "ix_activos_estado", [("estado", 1)], {}),
    ("activos", "ix_activos_nombre", [("nombre_equipo", 1)], {}),
    ("activos", "ix_activos_ip", [("direccion_ip", 1)], {}),
    (
        "activos",
        "ix_activos_busqueda",
        [
            ("codigo_patrimonial", "text"),
            ("nombre_equipo", "text"),
            ("marca", "text"),
            ("modelo", "text"),
            ("responsable_nombre", "text"),
        ],
        {"weights": {"codigo_patrimonial": 10, "nombre_equipo": 6, "marca": 3, "modelo": 3, "responsable_nombre": 2}, "default_language": "none"},
    ),
    ("historial_responsables", "ix_hist_activo", [("activo_id", 1), ("fecha", -1)], {}),
    ("historial_responsables", "ix_hist_conjunto", [("conjunto_id", 1), ("fecha", -1)], {}),
    ("activos_cambios_componentes", "ix_cambios_activo", [("activo_id", 1), ("fecha", -1)], {}),
    # ── Tickets ──
    ("tickets", "uq_tickets_codigo", [("codigo", 1)], {"unique": True}),
    ("tickets", "ix_tickets_estado", [("estado", 1), ("actualizado_en", -1)], {}),
    ("tickets", "ix_tickets_asignado", [("tecnico_id", 1), ("estado", 1)], {}),
    ("tickets", "ix_tickets_reportante", [("reportante_id", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_afectado", [("afectado_id", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_oficina", [("oficina_id", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_zona", [("zona_id", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_activo", [("activo_id", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_conjunto", [("conjunto_id", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_categoria", [("categoria", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_prioridad", [("prioridad", 1), ("creado_en", -1)], {}),
    ("tickets", "ix_tickets_sla", [("sla_deadline", 1)], {}),
    ("tickets", "ix_tickets_conversacion", [("conversacion_id", 1), ("creado_en", 1)], {}),
    ("ticket_eventos", "ix_eventos_ticket", [("ticket_id", 1), ("fecha", 1)], {}),
    ("ticket_mensajes", "ix_mensajes_ticket", [("ticket_id", 1), ("creado_en", 1)], {}),
    ("ticket_mensajes", "ix_mensajes_conv", [("conversacion_id", 1), ("creado_en", 1)], {}),
    ("notas_internas", "ix_notas_ticket", [("ticket_id", 1), ("creado_en", -1)], {}),
    ("adjuntos", "ix_adjuntos_ticket", [("ticket_id", 1), ("creado_en", -1)], {}),
    ("adjuntos", "ix_adjuntos_mensaje", [("mensaje_id", 1)], {}),
    # ── Conocimiento ──
    ("articulos_kb", "ix_kb_categoria", [("categoria", 1), ("activo", 1)], {}),
    ("articulos_kb", "ix_kb_popular", [("popularidad", -1)], {}),
    (
        "articulos_kb",
        "ix_kb_busqueda",
        [("titulo", "text"), ("resumen", "text"), ("cuerpo", "text"), ("etiquetas", "text")],
        {"weights": {"titulo": 10, "etiquetas": 6, "resumen": 4, "cuerpo": 2}, "default_language": "none"},
    ),
    # ── Campanas ──
    ("campanas_inventario", "ix_campanas_anio", [("anio", -1)], {}),
    # Un equipo no puede repetirse dentro de la misma campaña. **Parcial a
    # propósito**: los equipos nuevos detectados en el Excel de la sala se
    # guardan como items con `activo_id: null` porque todavía no son un equipo.
    # Sin el filtro, Mongo los trata a todos como la misma clave (null) y el
    # segundo nuevo revienta con «duplicate key»: solo se podía registrar **un**
    # equipo nuevo por campaña. El índice dice «un equipo, una vez», y un null no
    # es un equipo.
    (
        "campana_items",
        "uq_item_campana_activo",
        [("campana_id", 1), ("activo_id", 1)],
        {"unique": True, "partialFilterExpression": {"activo_id": {"$type": "objectId"}}},
    ),
    ("campana_items", "ix_items_campana_estado", [("campana_id", 1), ("estado_item", 1)], {}),
    ("inventario_versiones", "ix_versiones_anio", [("anio", -1)], {}),
    # ── Importaciones ──
    ("importaciones", "ix_importaciones_fecha", [("creado_en", -1)], {}),
    # ── IA ──
    ("ia_eventos", "ix_ia_ticket", [("ticket_id", 1), ("creado_en", -1)], {}),
    ("ia_eventos", "ix_ia_tipo_fecha", [("tipo", 1), ("creado_en", -1)], {}),
    ("ia_eventos", "ix_ia_usuario", [("usuario_id", 1), ("creado_en", -1)], {}),
    # ── Operacion ──
    ("auditoria", "ix_auditoria_fecha", [("fecha", -1)], {}),
    ("auditoria", "ix_auditoria_usuario", [("usuario_id", 1), ("fecha", -1)], {}),
    ("auditoria", "ix_auditoria_entidad", [("entidad", 1), ("entidad_id", 1)], {}),
    ("auditoria", "ix_auditoria_accion", [("accion", 1), ("fecha", -1)], {}),
    ("exportaciones", "ix_exportaciones_fecha", [("creado_en", -1)], {}),
    ("exportaciones", "ix_exportaciones_estado", [("estado", 1)], {}),
    ("notificaciones", "ix_notif_usuario", [("usuario_id", 1), ("leida", 1), ("creado_en", -1)], {}),
    ("conversaciones_ia", "ix_conv_usuario", [("usuario_id", 1), ("actualizado_en", -1)], {}),
    ("vistas_guardadas", "ix_vistas_usuario", [("creada_por", 1)], {}),
    ("vistas_guardadas", "ix_vistas_compartidas", [("compartida", 1)], {}),
)

# ── Contadores atomicos ──────────────────────────────────────
CONTADOR_TICKETS = "tickets"
CONTADOR_CONJUNTOS = "conjuntos"
CONTADOR_CAMPANAS = "campanas"
CONTADOR_NOTAS = "notas"


async def asegurar_estructura(db) -> dict[str, list[str]]:
    """Crea colecciones, validadores e indices de forma idempotente."""
    existentes = await db.list_collection_names()
    creadas: list[str] = []
    for nombre in COLECCIONES:
        if nombre not in existentes:
            opciones: dict = {}
            if nombre in VALIDADORES:
                opciones["validator"] = VALIDADORES[nombre]
                opciones["validationLevel"] = "moderate"
                opciones["validationAction"] = "error"
            await db.create_collection(nombre, **opciones)
            creadas.append(nombre)

    # Indices
    indices_creados: list[str] = []
    for coleccion, nombre_indice, clave, opciones in INDEXES:
        try:
            await db[coleccion].create_index(clave, name=nombre_indice, **opciones)
            indices_creados.append(f"{coleccion}.{nombre_indice}")
        except Exception:  # pragma: no cover - indice existente o conflicto
            continue

    # Contadores base
    for clave in (CONTADOR_TICKETS, CONTADOR_CONJUNTOS, CONTADOR_CAMPANAS, CONTADOR_NOTAS):
        await db["contadores"].update_one(
            {"clave": clave}, {"$setOnInsert": {"valor": 0}}, upsert=True
        )

    return {"colecciones": creadas, "indices": indices_creados}


__all__ = ["ASCENDING", "COLECCIONES", "VALIDADORES", "INDEXES", "asegurar_estructura"]
