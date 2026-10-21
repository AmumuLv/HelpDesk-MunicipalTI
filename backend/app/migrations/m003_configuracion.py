"""Documento unico de configuracion: SLA, calendario laboral, IA y notificaciones."""

DESCRIPCION = "Configuracion inicial de SLA, calendario laboral, IA y notificaciones"

from app.core.config import settings
from app.core.time import utcnow

# Reglas base en horas laborables (el reloj se pausa fuera de horario y feriados)
SLA_BASE = [
    {"prioridad": "critica", "horas_responder": 1, "horas_resolver": 4},
    {"prioridad": "alta", "horas_responder": 4, "horas_resolver": 8},
    {"prioridad": "media", "horas_responder": 8, "horas_resolver": 24},
    {"prioridad": "baja", "horas_responder": 24, "horas_resolver": 72},
]

# Semana laboral por defecto: lunes a viernes, con el índice de `weekday()`
# (lunes = 0). El comentario decía lunes a viernes y el valor era [1, 2, 3, 4, 5],
# que es martes a sábado: el lunes no contaba como día de trabajo.
DIA_LABORABLE_POR_DEFECTO = [0, 1, 2, 3, 4]
# Jornada de 8 h con una hora de descanso: 08:00-13:00 (5 h) y 14:00-17:00 (3 h).
TRANSMOS_POR_DEFECTO = [{"entrada": "08:00", "salida": "13:00"}, {"entrada": "14:00", "salida": "17:00"}]

ID_CONFIG = "config"


async def aplicar(db) -> None:
    ahora = utcnow()
    await db["configuracion"].update_one(
        {"_id": ID_CONFIG},
        {
            "$setOnInsert": {
                "_id": ID_CONFIG,
                "institucion": {
                    "nombre": settings.institution_name,
                    "nombre_corto": settings.institution_short_name,
                    "correo": settings.contact_email,
                },
                "negocio": {
                    "zona_horaria": settings.business_timezone,
                    "horario_inicio_global": "08:00",
                    "horario_fin_global": "18:00",
                },
                "sla": {
                    "activo": True,
                    "pausa_fuera_de_horario": True,
                    "reglas": SLA_BASE,
                    "calendario": {
                        "dias_laborables": DIA_LABORABLE_POR_DEFECTO,
                        "tramos": TRANSMOS_POR_DEFECTO,
                        "incluir_feriados": False,
                        "feriados_extra": [],
                    },
                },
                "ia": {
                    "global_activa": settings.ai_global_enabled,
                    "aprendizaje_activo": settings.ai_learning_enabled,
                    "recomendaciones_activas": settings.ai_recommendations_enabled,
                    "valor_por_defecto": settings.ai_recommendations_default,
                    "confianza_minima": 0.55,
                    "proveedor": settings.ai_provider,
                    "modelo": settings.ai_model,
                },
                "notificaciones": {
                    "email_activo": False,
                    "correo_destino": settings.contact_email,
                    "avisar_al_afectado": True,
                    "avisar_al_reportante": True,
                },
                "inventario": {
                    "importacion_completada": False,
                    "plantilla_mapeo": None,
                },
                "sistema": {
                    "version": "1.0.0",
                    "creado_en": ahora,
                    "primer_arranque_completo": False,
                },
            }
        },
        upsert=True,
    )


async def revertir(db) -> None:
    await db["configuracion"].delete_one({"_id": ID_CONFIG})