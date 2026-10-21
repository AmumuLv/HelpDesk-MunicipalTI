"""Catalogos base: tipos de dispositivo, estados, propiedad, categorias y esquemas."""

DESCRIPCION = "Catalogos iniciales, esquemas por tipo y categorias de ticket"

from app.domain.constants import (
    CAMPOS_BASE,
    COMPONENTES_CONJUNTO_POR_DEFECTO,
    ESQUEMAS_POR_TIPO,
    ESQUEMA_GENERICO,
    ESTADOS_ACTIVO_INICIALES,
    OPCIONES_AVANZADAS_POR_TIPO,
    PROPIEDADES_INICIALES,
    SINONIMOS_DISPOSITIVO,
    TIPOS_DISPOSITIVO_INICIALES,
    VALORES_SIN_DATO,
)
from app.core.time import utcnow

CATALOGOS = {
    "tipos_dispositivo": TIPOS_DISPOSITIVO_INICIALES,
    "estados_activo": ESTADOS_ACTIVO_INICIALES,
    "propiedades": PROPIEDADES_INICIALES,
    "categorias": [
        "No enciende",
        "Internet / Red",
        "Impresora",
        "Sistema / Programa",
        "Correo / Cuenta",
        "Hardware",
        "Software instalado",
        "Accesos y permisos",
        "Red / Conectividad",
        "Equipo lento",
        "Otros",
    ],
    "motivos_sin_dato": VALORES_SIN_DATO,
    "motivos_no_aplica": ["No aplica a este equipo", "Este equipo no tiene ni tendra ese dato"],
    "motivos_no_disponible": [
        "Equipo en desuso",
        "Informacion no disponible",
        "No se pudo averiguar",
    ],
    "sinonimos_dispositivo": [f"{k}={v}" for k, v in SINONIMOS_DISPOSITIVO.items()],
    "componentes_conjunto": COMPONENTES_CONJUNTO_POR_DEFECTO,
    "tipos_ausencia": ["Vacaciones", "Licencia", "Permiso", "Guardia", "Capacitacion", "Otros"],
    "canales_notificacion": ["sistema", "email", "web"],
}


async def aplicar(db) -> None:
    ahora = utcnow()
    for clave, valores in CATALOGOS.items():
        await db["catalogos"].update_one(
            {"clave": clave},
            {
                "$setOnInsert": {
                    "clave": clave,
                    "valores": list(valores),
                    "creado_en": ahora,
                }
            },
            upsert=True,
        )

    # Esquemas por tipo (esperados/opcionales) + secciones avanzadas
    for tipo, esquema in ESQUEMAS_POR_TIPO.items():
        await db["esquemas_tipos"].update_one(
            {"tipo": tipo},
            {
                "$setOnInsert": {
                    "tipo": tipo,
                    "esperados": esquema["esperados"],
                    "opcionales": esquema["opcionales"],
                    "avanzadas": OPCIONES_AVANZADAS_POR_TIPO.get(tipo, []),
                    "creado_en": ahora,
                }
            },
            upsert=True,
        )
    await db["esquemas_tipos"].update_one(
        {"tipo": "__generico__"},
        {
            "$setOnInsert": {
                "tipo": "__generico__",
                "esperados": ESQUEMA_GENERICO["esperados"],
                "opcionales": ESQUEMA_GENERICO["opcionales"],
                "avanzadas": [],
                "creado_en": ahora,
            }
        },
        upsert=True,
    )

    # Documento unico de esquema base para referencia
    await db["esquemas_tipos"].update_one(
        {"tipo": "__base__"},
        {
            "$setOnInsert": {
                "tipo": "__base__",
                "campos_base": list(CAMPOS_BASE),
                "creado_en": ahora,
            }
        },
        upsert=True,
    )