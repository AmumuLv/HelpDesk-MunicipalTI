"""Esquemas de administracion: configuracion, permisos, equipo TI, KB, campanas y auditoria."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.domain.constants import ROLES
from app.schemas.common import Base, Id, IdOpcional


# ── Configuracion ────────────────────────────────────────────
class ReglaSLA(Base):
    prioridad: str
    horas_responder: float = Field(gt=0, le=2000, allow_inf_nan=False)
    horas_resolver: float = Field(gt=0, le=8000, allow_inf_nan=False)

    @model_validator(mode="after")
    def _plazos(self):
        if self.horas_resolver < self.horas_responder:
            raise ValueError("El plazo de resolución no puede ser menor que el de respuesta")
        return self

    @field_validator("prioridad")
    @classmethod
    def _p(cls, v: str) -> str:
        if v not in {"baja", "media", "alta", "critica"}:
            raise ValueError("Prioridad no valida")
        return v


class TramoHorario(Base):
    entrada: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    salida: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class CalendarioLaboral(Base):
    # Lunes a viernes, con el índice de `datetime.weekday()` (lunes = 0). El
    # default era `[1, 2, 3, 4, 5]`, que es martes a sábado.
    dias_laborables: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    # Jornada de 8 h con una hora de descanso: 08:00-13:00 y 14:00-17:00.
    tramos: list[TramoHorario] = Field(
        default_factory=lambda: [TramoHorario(entrada="08:00", salida="13:00"), TramoHorario(entrada="14:00", salida="17:00")]
    )
    incluir_feriados: bool = False
    feriados_extra: list[date] = Field(default_factory=list)

    @field_validator("dias_laborables")
    @classmethod
    def _dias(cls, v: list[int]) -> list[int]:
        if not v or any(d < 0 or d > 6 for d in v):
            raise ValueError("Dia de semana invalido")
        return sorted(set(v))

    @model_validator(mode="after")
    def _tramos(self):
        if not self.tramos or len(self.tramos) > 4:
            raise ValueError("Indica entre uno y cuatro tramos de atención")
        self.tramos.sort(key=lambda tramo: tramo.entrada)
        for indice, tramo in enumerate(self.tramos):
            if tramo.entrada >= tramo.salida or (indice and self.tramos[indice - 1].salida > tramo.entrada):
                raise ValueError("Los horarios deben tener una salida posterior a la entrada y no solaparse")
        return self


class ConfigSLA(Base):
    activo: bool = True
    pausa_fuera_de_horario: bool = True
    reglas: list[ReglaSLA] = Field(default_factory=list)
    calendario: CalendarioLaboral = Field(default_factory=CalendarioLaboral)

    @model_validator(mode="after")
    def _prioridades(self):
        if 'reglas' in self.model_fields_set and (len(self.reglas) != 4 or {r.prioridad for r in self.reglas} != {'baja', 'media', 'alta', 'critica'}):
            raise ValueError("Configura cada una de las cuatro prioridades una sola vez")
        return self


class ConfigIA(Base):
    global_activa: bool = True
    aprendizaje_activo: bool = True
    recomendaciones_activas: bool = True
    valor_por_defecto: bool = True
    confianza_minima: float = Field(default=0.55, ge=0, le=1)
    proveedor: str | None = None
    modelo: str | None = None


class ConfigNotificaciones(Base):
    email_activo: bool = False
    correo_destino: str | None = None
    avisar_al_afectado: bool = True
    avisar_al_reportante: bool = True


class ConfigGeneral(Base):
    institucion_nombre: str | None = Field(default=None, max_length=120)
    institucion_nombre_corto: str | None = Field(default=None, max_length=60)
    institucion_correo: str | None = Field(default=None, max_length=160)
    zona_horaria: str | None = None
    horario_inicio_global: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    horario_fin_global: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    aviso_global: str | None = None


class ConfigRespuesta(Base):
    negocio: dict[str, Any] = Field(default_factory=dict)
    sla: ConfigSLA | None = None
    ia: ConfigIA | None = None
    notificaciones: ConfigNotificaciones | None = None
    aviso_global: str | None = None


# ── Feriados ─────────────────────────────────────────────────
class Feriado(Base):
    fecha: date
    nombre: str = Field(min_length=2, max_length=120)
    tipo: str = "feriado"


class FeriadoActualizar(Feriado):
    pass


# ── Equipo TI y horarios ─────────────────────────────────────
class TramosTecnico(Base):
    tramos: list[TramoHorario] = Field(default_factory=list)
    libre: bool = False


class HorarioSemanal(Base):
    """Dia de semana (0=lunes segun el calendario interno) -> tramos."""

    dias: dict[int, TramosTecnico] = Field(default_factory=dict)


class TecnicoPerfilBase(Base):
    especialidades: list[str] = Field(default_factory=list)
    categorias: list[str] = Field(default_factory=list)
    zonas_pref: list[str] = Field(default_factory=list)
    capacidad_diaria: int = Field(default=8, ge=1, le=40)
    notas: str | None = Field(default=None, max_length=2000)


class TecnicoPerfilActualizar(TecnicoPerfilBase):
    horario: HorarioSemanal | None = None
    activo: bool | None = None


class AusenciaBase(Base):
    tipo: str = Field(default="Vacaciones", max_length=60)
    inicio: date
    fin: date
    motivo: str | None = Field(default=None, max_length=500)

    @field_validator("tipo")
    @classmethod
    def _tipo(cls, v: str) -> str:
        permitidos = {"Vacaciones", "Licencia", "Permiso", "Guardia", "Capacitacion", "Enfermedad", "Otros"}
        if v not in permitidos:
            raise ValueError("Tipo de ausencia no valido")
        return v


class AusenciaCrear(AusenciaBase):
    tecnico_id: Id


class Ausencia(Base):
    id: Id
    tecnico_id: Id
    tipo: str
    inicio: date
    fin: date
    motivo: str | None = None
    creado_por: str | None = None
    creado_en: datetime | None = None


class Disponibilidad(Base):
    tecnico_id: Id
    tecnico_nombre: str
    estado: str
    etiqueta: str
    ticket_actual_id: Id | None = None
    ticket_actual_codigo: str | None = None
    ticket_desde: datetime | None = None
    ticket_zona: str | None = None
    ticket_oficina: str | None = None
    carga_asignados: int = 0
    carga_espera: int = 0
    capacidad_diaria: int = 8
    porcentaje_carga: float = 0.0
    sla_mas_critico_min: int | None = None
    horario_hoy: list[TramoHorario] = Field(default_factory=list)
    ausencias: list[Ausencia] = Field(default_factory=list)
    dia_libre: bool = False
    fuera_de_horario: bool = False
    metricas: dict[str, Any] = Field(default_factory=dict)
    carga_ia: dict[str, Any] | None = None


class TecnicoDetalle(Base):
    id: Id
    nombre: str
    email: str | None = None
    telefono: str | None = None
    rol: str
    activo: bool
    zona_nombre: str | None = None
    oficina_nombre: str | None = None
    iniciales: str = ""
    perfil: dict[str, Any] = Field(default_factory=dict)
    horario: dict[str, Any] = Field(default_factory=dict)
    disponibilidad: Disponibilidad | None = None
    metricas: dict[str, Any] = Field(default_factory=dict)
    ausencias: list[Ausencia] = Field(default_factory=list)
    calendario: list[dict[str, Any]] = Field(default_factory=list)


# ── Permisos delegables ──────────────────────────────────────
class PermisoCambio(Base):
    clave: str
    valor: bool

    @field_validator("clave")
    @classmethod
    def _clave(cls, v: str) -> str:
        from app.domain.permissions import CLAVES_PERMISOS

        if v not in CLAVES_PERMISOS:
            raise ValueError("Permiso desconocido")
        return v


class PermisoAplicar(Base):
    cambios: list[PermisoCambio] = Field(min_length=1)


class MatrizPermisos(Base):
    grupo: str
    etiqueta: str
    descripcion: str
    permisos: list[dict[str, Any]] = Field(default_factory=list)


class PermisoTecnico(Base):
    usuario_id: Id
    nombre: str
    activo: bool = True
    permisos: dict[str, bool] = Field(default_factory=dict)


class AplicarPermisosTecnico(Base):
    cambios: dict[str, bool] = Field(default_factory=dict)


# ── Base de conocimiento ─────────────────────────────────────
class ArticuloBase(Base):
    visibilidad: Literal['todos', 'equipo_ti'] = 'todos'
    @field_validator("titulo", "categoria", "resumen", "cuerpo", mode="before")
    @classmethod
    def limpiar_texto(cls, valor):
        return valor.strip() if isinstance(valor, str) else valor

    titulo: str = Field(min_length=4, max_length=200)
    categoria: str = Field(max_length=120)
    resumen: str = Field(min_length=10, max_length=600)
    cuerpo: str = Field(min_length=10)
    pasos: list[str] = Field(default_factory=list)
    imagenes: list[str] = Field(default_factory=list)
    etiquetas: list[str] = Field(default_factory=list)
    relacionados: list[Id] = Field(default_factory=list)
    activo: bool = True


class ArticuloCrear(ArticuloBase):
    pass


class ArticuloActualizar(Base):
    visibilidad: Literal['todos', 'equipo_ti'] | None = None
    titulo: str | None = Field(default=None, min_length=4, max_length=200)
    categoria: str | None = Field(default=None, min_length=1, max_length=120)
    resumen: str | None = Field(default=None, min_length=10, max_length=600)
    cuerpo: str | None = Field(default=None, min_length=10)
    limpiar_texto = field_validator("titulo", "categoria", "resumen", "cuerpo", mode="before")(ArticuloBase.limpiar_texto.__func__)
    pasos: list[str] | None = None
    imagenes: list[str] | None = None
    etiquetas: list[str] | None = None
    relacionados: list[Id] | None = None
    activo: bool | None = None


class ArticuloResumen(Base):
    me_gusta: int = 0
    visibilidad: Literal['todos', 'equipo_ti'] = 'todos'
    id: Id
    titulo: str
    categoria: str
    resumen: str
    etiquetas: list[str] = Field(default_factory=list)
    pasos: list[str] = Field(default_factory=list)
    imagenes: list[str] = Field(default_factory=list)
    relacionados: list[Id] = Field(default_factory=list)
    popularidad: int = 0
    visualizaciones: int = 0
    valoracion_promedio: float | None = None
    valoraciones: int = 0
    actualizado_en: datetime | None = None
    activo: bool = True


class ArticuloDetalle(ArticuloResumen):
    mi_valoracion: bool | None = None
    cuerpo: str = ""
    creado_en: datetime | None = None
    creado_por: str | None = None


class ValorarArticulo(Base):
    util: bool
    comentario: str | None = Field(default=None, max_length=600)


class RespuestaRapida(Base):
    titulo: str = Field(min_length=2, max_length=120)
    cuerpo: str = Field(min_length=2, max_length=4000)
    categoria: str | None = Field(default=None, max_length=120)


# ── Campanas de inventario ───────────────────────────────────
class CampanaCrear(Base):
    nombre: str = Field(min_length=4, max_length=120)
    anio: int = Field(ge=2000, le=2100)
    alcance: str = Field(default="institucion")
    zona_ids: list[Id] = Field(default_factory=list)
    oficina_ids: list[Id] = Field(default_factory=list)
    fecha_inicio: date
    fecha_fin: date
    responsables: list[Id] = Field(default_factory=list)
    notas: str | None = Field(default=None, max_length=2000)
    generar_qr: bool = False

    @field_validator("alcance")
    @classmethod
    def _alcance(cls, v: str) -> str:
        if v not in {"institucion", "zonas", "oficinas"}:
            raise ValueError("Alcance no valido")
        return v


class CampanaActualizar(Base):
    nombre: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    notas: str | None = None
    generar_qr: bool | None = None


class CampanaResumen(Base):
    id: Id
    codigo: str
    nombre: str
    anio: int
    alcance: str
    estado: str
    fecha_inicio: date
    fecha_fin: date
    total_items: int = 0
    verificados: int = 0
    progreso: float = 0.0
    nuevos: int = 0
    modificados: int = 0
    sin_cambios: int = 0
    por_verificar: int = 0
    discrepancias: int = 0
    creado_en: datetime | None = None
    cerrado_en: datetime | None = None


class ItemVerificacion(Base):
    estado_item: str
    responsable_id: Id | None = None
    nuevo_activo_id: Id | None = None
    nuevo_oficina_id: Id | None = None
    observaciones: str | None = Field(default=None, max_length=1000)
    cambios: dict[str, Any] | None = None


class ActualizarItem(Base):
    estado_item: str
    responsable_id: Id | None = None
    observaciones: str | None = None
    cambios: dict[str, Any] | None = None

    @field_validator("estado_item")
    @classmethod
    def _estado(cls, v: str) -> str:
        permitidos = {
            "pendiente",
            "confirmado",
            "cambio_responsable",
            "cambio_estado",
            "cambio_oficina",
            "no_encontrado",
            "dado_de_baja",
            "nuevo",
        }
        if v not in permitidos:
            raise ValueError("Estado de verificacion no valido")
        return v


class ImportarCampana(Base):
    lote_id: str
    aceptar_todos: bool = False
    estados_aceptados: list[str] = Field(default_factory=list)
    # Rechazar es la otra mitad de la decisión: un equipo que se detectó pero no
    # es del municipio (pertenece a otro, está de paso, no se quiere registrar)
    # tiene que poder quedar fuera. Antes el servicio lo admitía y la ruta lo
    # descartaba: se aceptaba todo o nada.
    estados_rechazados: list[str] = Field(default_factory=list)


class ResultadoComparacion(Base):
    lote_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    nuevos: int = 0
    modificados: int = 0
    sin_cambios: int = 0
    ausentes: int = 0
    errores: int = 0


class ItemCampana(Base):
    id: Id
    activo_id: Id | None = None
    activo_nombre: str | None = None
    activo_codigo: str | None = None
    activo_tipo: str | None = None
    conjunto_nombre: str | None = None
    oficina_id: Id | None = None
    oficina_nombre: str | None = None
    zona_id: Id | None = None
    zona_nombre: str | None = None
    responsable_nombre: str | None = None
    estado_item: str = "pendiente"
    codigo_qr: str | None = None
    diferencias: list[dict[str, Any]] = Field(default_factory=list)
    observaciones: str | None = None
    verificado_por: str | None = None
    verificado_en: datetime | None = None


class CierreCampana(Base):
    aplicar_no_localizados: bool = True
    marcar_no_localizados: bool = True
    confirmacion: bool = True
    nota: str | None = None


# ── Auditoria ────────────────────────────────────────────────
class EntradaAuditoria(Base):
    id: Id
    fecha: datetime
    accion: str
    accion_texto: str
    usuario_nombre: str | None = None
    rol: str | None = None
    entidad: str | None = None
    entidad_id: str | None = None
    resultado: str | None = None
    resumen: str | None = None
    antes: Any = None
    despues: Any = None
    ip: str | None = None
    user_agent: str | None = None


# ── Analitica y asistente ────────────────────────────────────
class FiltrosAnalitica(Base):
    desde: date | None = None
    hasta: date | None = None
    periodo: str = "30d"
    zona_id: Id | None = None
    oficina_id: Id | None = None
    categoria: str | None = None
    tipo_activo: str | None = None
    tecnico_id: Id | None = None
    equipo_id: Id | None = None


class PreguntaIA(Base):
    pregunta: str = Field(min_length=2, max_length=1000)
    filtros: FiltrosAnalitica = Field(default_factory=FiltrosAnalitica)
    conversacion_id: Id | None = None

    @field_validator("pregunta", mode="before")
    @classmethod
    def _limpiar_pregunta(cls, valor: Any) -> Any:
        return valor.strip() if isinstance(valor, str) else valor


class MensajeIA(Base):
    rol: str
    texto: str
    created_at: str | None = None
    fuentes: list[str] = Field(default_factory=list)
    enlaces: list[dict[str, str]] | None = None
    periodo: str | None = None
    tabla: dict[str, Any] | None = None
    accion: dict[str, Any] | None = None
    confianza: float | None = None
    explicacion: str | None = None


class ConversacionIA(Base):
    id: Id
    titulo: str
    usuario_id: Id | None = None
    usuario_nombre: str | None = None
    mensajes: list[MensajeIA] = Field(default_factory=list)
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None


class PreguntasSugeridas(Base):
    preguntas: list[str] = Field(default_factory=list)


# ── Exportaciones ────────────────────────────────────────────
class ExportarSolicitud(Base):
    tipo: str = Field(description="tickets | ticket_individual | inventario | campana | calidad | analitica | auditoria")
    formato: str = Field(default="pdf", description="pdf | excel | csv")
    filtros: dict[str, Any] = Field(default_factory=dict)
    ids: list[Id] = Field(default_factory=list)
    incluir_notas_internas: bool = False
    titulo: str | None = None

    @field_validator("formato")
    @classmethod
    def _formato(cls, v: str) -> str:
        if v not in {"pdf", "excel", "csv"}:
            raise ValueError("Formato no valido")
        return v


class ExportacionEstado(Base):
    id: Id
    tipo: str
    formato: str
    estado: str
    nombre_archivo: str
    creado_en: datetime
    completado_en: datetime | None = None
    usuario_nombre: str | None = None
    tamano: int | None = None
    error: str | None = None
    descarga_url: str | None = None


# ── Notificaciones ───────────────────────────────────────────
class Notificacion(Base):
    id: Id
    titulo: str
    mensaje: str
    tipo: str = "info"
    enlace: str | None = None
    leida: bool = False
    creado_en: datetime
    ticket_id: Id | None = None


# ── Arranque guiado ──────────────────────────────────────────
class EstadoInstalacion(Base):
    configurado: bool = False
    hay_admin: bool = False
    hay_zonas: bool = False
    hay_oficinas: bool = False
    hay_usuarios: bool = False
    hay_tecnicos: bool = False
    hay_inventario: bool = False
    inventario_importado: bool = False
    horarios_completos: bool = False
    pasos_completados: list[str] = Field(default_factory=list)
    siguiente_paso: str = "crear_admin"
    institucion: str = ""


class Resumen(Base):
    """Panel TI: cifras de cabecera."""

    tickets_abiertos: int = 0
    tickets_sin_asignar: int = 0
    tickets_sla_riesgo: int = 0
    tickets_criticos: int = 0
    tickets_mios: int = 0
    tickets_resueltos_periodo: int = 0
    tiempo_medio_resolucion_min: float | None = None
    cumplimiento_sla: float | None = None
    satisfaccion_promedio: float | None = None
    total_activos: int = 0
    activos_con_datos_faltantes: int = 0
    completitud_inventario: float | None = None
    usuarios_activos: int = 0
    zonas: int = 0
    oficinas: int = 0
    equipo_disponible: int = 0
    equipo_total: int = 0
    tecnico_mas_carga: str | None = None
    top_oficinas: list[dict[str, Any]] = Field(default_factory=list)
    top_categorias: list[dict[str, Any]] = Field(default_factory=list)
    pendientes_calidad: list[dict[str, Any]] = Field(default_factory=list)
    campana_activa: dict[str, Any] | None = None
    ultimas_actualizaciones: datetime | None = None


ROL_VALIDOS = ROLES
