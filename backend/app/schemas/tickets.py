"""Esquemas de tickets, chat, notas y linea de tiempo."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.domain.constants import (
    ESTADOS_TICKET,
    ORIGENES_TICKET,
    PRIORIDADES,
    TRANSICIONES,
)
from app.schemas.common import Base, Id, IdOpcional


# ── Creacion por el usuario (2 pasos) ────────────────────────
class Paso1Usuario(Base):
    """¿Que pasa? Un tipo de problema o el detalle escrito a mano."""

    tipo_problema: str | None = Field(default=None, max_length=120)
    descripcion: str | None = Field(default=None, max_length=4000)


class PersonaAfectada(Base):
    """A quien afecta el problema."""

    es_para_mi: bool = True
    afectado_id: Id | None = None
    # Registrado por un tecnico: puede no existir todavia
    persona_no_registrada: dict[str, Any] | None = None


class Paso2Usuario(Base):
    persona: PersonaAfectada = Field(default_factory=PersonaAfectada)
    activo_id: Id | None = None
    conjunto_id: Id | None = None
    activo_no_identificado: str | None = Field(default=None, max_length=120)
    urgencia: str = "puede_esperar"
    descripcion: str | None = Field(default=None, max_length=4000)
    adjuntos: list[str] = Field(default_factory=list)
    aceptar_prioridad_ia: bool = True
    aceptar_categoria_ia: bool = True

    @field_validator("urgencia")
    @classmethod
    def _urgencia(cls, v: str) -> str:
        if v not in {"puede_esperar", "me_frena", "no_puedo_trabajar"}:
            raise ValueError("Urgencia no valida")
        return v


class TicketUsuarioCrear(Base):
    reporte_para: Literal['propio', 'companero', 'oficina'] | None = None
    sistema_afectado: str | None = Field(default=None, max_length=120)
    tipo_problema: str | None = None
    descripcion: str | None = Field(default=None, max_length=4000)
    persona: PersonaAfectada = Field(default_factory=PersonaAfectada)
    activo_id: Id | None = None
    conjunto_id: Id | None = None
    activo_no_identificado: str | None = None
    urgencia: str = "puede_esperar"
    adjuntos: list[str] = Field(default_factory=list)
    categoria: str | None = None
    prioridad: str | None = None
    aceptar_prioridad_ia: bool = True
    aceptar_categoria_ia: bool = True

    @field_validator("urgencia")
    @classmethod
    def _urgencia(cls, v: str) -> str:
        if v not in {"puede_esperar", "me_frena", "no_puedo_trabajar"}:
            raise ValueError("Urgencia no valida")
        return v


# ── Creacion por tecnico o administrador (2 pasos) ───────────
class PersonaBuscada(Base):
    afectado_id: Id | None = None
    persona_no_registrada: dict[str, Any] | None = None
    detectado_por_tec: bool = False

    @field_validator("detectado_por_tec")
    @classmethod
    def _bool(cls, v: Any) -> bool:
        return bool(v)


class TicketManualCrear(Base):
    sistema_afectado: str | None = Field(default=None, max_length=120)
    persona: PersonaBuscada = Field(default_factory=PersonaBuscada)
    asunto: str = Field(min_length=4, max_length=200)
    descripcion: str | None = Field(default=None, max_length=4000)
    activo_id: Id | None = None
    conjunto_id: Id | None = None
    activo_no_identificado: str | None = Field(default=None, max_length=120)
    # El tipo del equipo cuando **no** hay equipo enlazado: «es un CPU». Es
    # información útil para el triage y no inventa un equipo que no existe.
    activo_tipo: str | None = Field(default=None, max_length=60)
    categoria: str | None = Field(default=None, max_length=120)
    prioridad: str = "media"
    tecnico_id: Id | None = None
    adjuntos: list[str] = Field(default_factory=list)
    origen: str = "tecnico"

    @field_validator("prioridad")
    @classmethod
    def _prioridad(cls, v: str) -> str:
        if v not in PRIORIDADES:
            raise ValueError("Prioridad no valida")
        return v

    @field_validator("origen")
    @classmethod
    def _origen(cls, v: str) -> str:
        if v not in ORIGENES_TICKET:
            raise ValueError("Origen no valido")
        return v


# ── Lectura ──────────────────────────────────────────────────
class ActorResumen(Base):
    id: IdOpcional = None
    nombre: str
    rol: str = "sistema"
    iniciales: str = ""


class SLALectura(Base):
    activo: bool = True
    estado: str = "seguro"
    minutos_restantes: int | None = None
    minutos_transcurridos: int | None = None
    responder_en: datetime | None = None
    resolver_en: datetime | None = None
    pausado: bool = False
    progreso: float = 0.0


class TicketResumen(Base):
    id: Id
    codigo: str
    asunto: str
    descripcion: str | None = None
    estado: str
    prioridad: str
    origen: str
    categoria: str | None = None
    reportante_id: IdOpcional = None
    reportante_nombre: str | None = None
    afectado_id: IdOpcional = None
    afectado_nombre: str | None = None
    zona_id: IdOpcional = None
    zona_nombre: str | None = None
    oficina_id: IdOpcional = None
    oficina_nombre: str | None = None
    activo_id: IdOpcional = None
    activo_nombre: str | None = None
    conjunto_id: IdOpcional = None
    conjunto_nombre: str | None = None
    tecnico_id: IdOpcional = None
    tecnico_nombre: str | None = None
    creado_en: datetime
    actualizado_en: datetime
    sla: SLALectura = Field(default_factory=SLALectura)
    tiempo_resolucion_min: float | None = None
    confianza_ia: float | None = None
    mensajes_no_leidos: int = 0
    satisfaccion: int | None = None
    sla_incumplido: bool = False


class EventoTicket(Base):
    id: Id
    ticket_id: Id | None = None
    tipo: str
    fecha: datetime
    actor: ActorResumen = Field(default_factory=ActorResumen)
    resumen: str
    detalle: dict[str, Any] = Field(default_factory=dict)
    visible_usuario: bool = False
    origen_ia: bool = False


class MensajeTicket(Base):
    id: Id
    ticket_id: Id
    autor_id: IdOpcional = None
    autor_nombre: str
    autor_rol: str = "usuario"
    cuerpo: str
    creado_en: datetime
    leido_por_tecnico: bool = False
    adjuntos: list[dict[str, Any]] = Field(default_factory=list)
    es_ia: bool = False


class NotaInterna(Base):
    id: Id
    ticket_id: Id
    autor_id: IdOpcional = None
    autor_nombre: str
    cuerpo: str
    creado_en: datetime
    adjuntos: list[dict[str, Any]] = Field(default_factory=list)


class AdjuntoLectura(Base):
    id: Id
    nombre_original: str
    nombre_archivo: str
    mime: str
    tamano: int
    creado_en: datetime
    url: str


class SugerenciaIA(Base):
    categoria: str | None = None
    prioridad: str | None = None
    confianza: float = 0.0
    explicacion: str = ""
    resumen: str | None = None
    causa_raiz: str | None = None
    riesgo_sla: str | None = None
    articulos: list[dict[str, Any]] = Field(default_factory=list)
    respuesta_sugerida: str | None = None
    tecnico_sugerido_id: Id | None = None
    tecnico_sugerido_nombre: str | None = None
    activa: bool = False
    disponible: bool = True
    motivo_no_disponible: str | None = None


class TicketDetalle(TicketResumen):
    alcance_incidencia: Literal['equipo', 'conjunto', 'programa', 'servicio', 'pendiente'] | None = None
    sistema_afectado: str | None = None
    conversacion_id: Id | None = None
    tiene_chat: bool = False
    notas_internas: list[NotaInterna] = Field(default_factory=list)
    adjuntos: list[AdjuntoLectura] = Field(default_factory=list)
    eventos: list[EventoTicket] = Field(default_factory=list)
    sugerencias: SugerenciaIA | None = None
    resuelto_en: datetime | None = None
    cerrado_en: datetime | None = None
    nota_resolucion: str | None = None
    reabierto: int = 0
    primera_respuesta_min: float | None = None
    veces_reabierto: int = 0
    etiquetas: list[str] = Field(default_factory=list)
    # Lo que esta persona puede hacer con este ticket. El backend no expone
    # `response_model` en la ruta, así que la forma observada los recoge aparte;
    # aquí se declaran para que el contrato no dependa de eso.
    puede_operar: bool = False
    puede_cerrar: bool = False
    puede_reabrir: bool = False
    puede_eliminar: bool = False


class FiltrosTicket(Base):
    conjunto_id: Id | None = None
    estado: list[str] | None = None
    prioridad: list[str] | None = None
    categoria: list[str] | None = None
    zona_id: Id | None = None
    oficina_id: Id | None = None
    tecnico_id: Id | None = None
    activo_id: Id | None = None
    origen: list[str] | None = None
    sla: str | None = None
    texto: str | None = None
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    vista: str | None = None
    solo_mios: bool = False
    pagina: int = 1
    por_pagina: int = 25
    orden: str = "antiguedad"
    solo_abiertos: bool = False


class TicketActualizar(Base):
    alcance_incidencia: Literal['equipo', 'conjunto', 'programa', 'servicio', 'pendiente'] | None = None
    sistema_afectado: str | None = Field(default=None, max_length=120)
    asunto: str | None = Field(default=None, min_length=4, max_length=200)
    descripcion: str | None = Field(default=None, max_length=4000)
    categoria: str | None = Field(default=None, max_length=120)
    prioridad: str | None = None
    activo_id: Id | None = None
    conjunto_id: Id | None = None

    @field_validator("prioridad")
    @classmethod
    def _prioridad(cls, v: str | None) -> str | None:
        if v is not None and v not in PRIORIDADES:
            raise ValueError("Prioridad no valida")
        return v


class CambiarEstado(Base):
    estado: str
    nota_resolucion: str | None = Field(default=None, max_length=4000)
    pausa_motivo: str | None = Field(default=None, max_length=500)

    @field_validator("estado")
    @classmethod
    def _estado(cls, v: str) -> str:
        if v not in ESTADOS_TICKET:
            raise ValueError("Estado no valido")
        return v


class AsignarTicket(Base):
    tecnico_id: Id | None = None
    comentario: str | None = Field(default=None, max_length=500)
    confirmar_fuera_de_horario: bool = False


class MensajeCrear(Base):
    cuerpo: str = Field(default="", max_length=8000)
    adjuntos: list[str] = Field(default_factory=list, max_length=5)


class NotaCrear(Base):
    cuerpo: str = Field(min_length=1, max_length=8000)
    adjuntos: list[str] = Field(default_factory=list)


class AdjuntoCrear(Base):
    nombre_original: str = Field(max_length=255)
    nombre_archivo: str = Field(max_length=255)
    mime: str = Field(max_length=120)
    tamano: int = Field(ge=0)


class Valoracion(Base):
    puntuacion: int = Field(ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=1000)


class SugerenciaAplicar(Base):
    """Aplicar, editar o descartar una recomendacion de IA.

    `clave` es qué se decide (categoria, prioridad, tecnico_sugerido_id) y
    `valor` con qué se queda. Es el contrato que usa la interfaz; `categoria` y
    `prioridad` se aceptan sueltos para llamadas directas.
    """

    accion: str  # aplicar | editar | descartar
    clave: str | None = None
    valor: str | None = None
    categoria: str | None = None
    prioridad: str | None = None
    respuesta_sugerida: str | None = None

    @field_validator("accion")
    @classmethod
    def _accion(cls, v: str) -> str:
        if v not in {"aplicar", "editar", "descartar"}:
            raise ValueError("Accion no valida")
        return v


class VistasGuardadas(Base):
    nombre: str = Field(min_length=2, max_length=80)
    vista: str | None = None
    filtros: dict[str, Any] = Field(default_factory=dict)
    columnas: list[str] | None = None
    compartida: bool = False


class VistasGuardadasRespuesta(Base):
    id: Id
    nombre: str
    vista: str | None = None
    filtros: dict[str, Any] = Field(default_factory=dict)
    columnas: list[str] | None = None
    compartida: bool = False
    creada_por: str | None = None
    creado_en: datetime | None = None


def transicion_permitida(actual: str, nuevo: str) -> bool:
    return nuevo in TRANSICIONES.get(actual, set())
