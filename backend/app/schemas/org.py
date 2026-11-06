"""Esquemas de zona, oficina y usuario."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.core.ids import normalizar_texto
from app.domain.constants import ROLES
from app.schemas.common import Base, Id, IdOpcional


# ── Zona ─────────────────────────────────────────────────────
class ZonaBase(Base):
    nombre: str = Field(min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    activa: bool = True


class ZonaCrear(ZonaBase):
    pass


class ZonaActualizar(Base):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    activa: bool | None = None


class ZonaResumen(Base):
    id: Id
    nombre: str
    descripcion: str | None = None
    activa: bool = True
    color_indice: int = Field(default=1, ge=1, le=8)


class ZonaDetalle(ZonaResumen):
    total_oficinas: int = 0
    total_usuarios: int = 0
    total_equipos: int = 0
    tickets_abiertos: int = 0
    tickets_periodo: int = 0
    tiempo_medio_resolucion_min: float | None = None
    categorias_frecuentes: list[dict[str, Any]] = Field(default_factory=list)
    oficinas_con_mas_fallas: list[dict[str, Any]] = Field(default_factory=list)
    completitud_inventario: float | None = None
    creado_en: datetime | None = None


# ── Oficina ──────────────────────────────────────────────────
class OficinaBase(Base):
    nombre: str = Field(min_length=2, max_length=120)
    zona_id: Id
    descripcion: str | None = Field(default=None, max_length=1000)
    activa: bool = True


class OficinaCrear(OficinaBase):
    pass


class OficinaActualizar(Base):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    zona_id: Id | None = None
    descripcion: str | None = Field(default=None, max_length=1000)
    activa: bool | None = None


class OficinaResumen(Base):
    id: Id
    nombre: str
    zona_id: Id | None = None
    zona_nombre: str | None = None
    descripcion: str | None = None
    activa: bool = True
    total_usuarios: int = 0
    total_equipos: int = 0
    tickets_abiertos: int = 0


class OficinaDetalle(OficinaResumen):
    usuarios: list["UsuarioResumen"] = Field(default_factory=list)
    equipos_uso_comun: list[dict[str, Any]] = Field(default_factory=list)
    equipos_por_usuario: list[dict[str, Any]] = Field(default_factory=list)
    pendientes_calidad: list[dict[str, Any]] = Field(default_factory=list)
    tickets_recientes: list[dict[str, Any]] = Field(default_factory=list)
    tendencia: list[dict[str, Any]] = Field(default_factory=list)
    incidencias_recurrentes: list[dict[str, Any]] = Field(default_factory=list)
    creado_en: datetime | None = None


# ── Usuario ──────────────────────────────────────────────────
class UsuarioBase(Base):
    nombre: str = Field(min_length=3, max_length=160)
    email: str | None = Field(default=None, max_length=160)
    telefono: str | None = Field(default=None, max_length=40)
    anexo: str | None = Field(default=None, max_length=40)
    cargo: str | None = Field(default=None, max_length=120)
    oficina_id: IdOpcional = None
    zona_id: IdOpcional = None
    rol: str = "usuario"
    activo: bool = True

    @field_validator("rol")
    @classmethod
    def _rol(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("Rol no valido")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        correo = normalizar_texto(v).lower()
        if not correo:
            return None
        if "@" not in correo or "." not in correo.split("@")[-1]:
            raise ValueError("Correo no valido")
        return correo

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        limpio = normalizar_texto(v)
        if len(limpio) < 3:
            raise ValueError("El nombre debe tener al menos 3 caracteres")
        return limpio


class UsuarioCrear(UsuarioBase):
    password: str | None = Field(default=None, min_length=8)
    recomendaciones_ia: bool | None = None
    permisos: dict[str, bool] = Field(default_factory=dict)


class UsuarioActualizar(Base):
    nombre: str | None = Field(default=None, min_length=3, max_length=160)
    email: str | None = None
    telefono: str | None = None
    anexo: str | None = None
    cargo: str | None = None
    oficina_id: IdOpcional = None
    zona_id: IdOpcional = None
    rol: str | None = None
    activo: bool | None = None
    recomendaciones_ia: bool | None = None
    permisos: dict[str, bool] | None = None

    @field_validator("rol")
    @classmethod
    def _rol(cls, v: str | None) -> str | None:
        if v is not None and v not in ROLES:
            raise ValueError("Rol no valido")
        return v


class UsuarioResumen(Base):
    archivado: bool = False
    desactivado_en: datetime | None = None
    archivado_en: datetime | None = None
    administrador_principal: bool = False
    id: Id
    nombre: str
    email: str | None = None
    telefono: str | None = None
    anexo: str | None = None
    cargo: str | None = None
    rol: str = "usuario"
    activo: bool = True
    zona_id: IdOpcional = None
    zona_nombre: str | None = None
    oficina_id: IdOpcional = None
    oficina_nombre: str | None = None
    iniciales: str = ""
    recomendaciones_ia: bool = True
    ultimo_acceso: datetime | None = None
    creado_en: datetime | None = None


class UsuarioDetalle(UsuarioResumen):
    equipos_responsable: list[dict[str, Any]] = Field(default_factory=list)
    historial_responsabilidad: list[dict[str, Any]] = Field(default_factory=list)
    tickets_creados: int = 0
    tickets_afectado: int = 0
    tickets_activos: int = 0
    satisfaccion_promedio: float | None = None
    especiales: list[str] = Field(default_factory=list)
    horario: dict[str, Any] | None = None
    carga_actual: int = 0


class UsuarioSesion(Base):
    """Lo que el frontend necesita saber de la cuenta con la que entra."""

    id: Id
    administrador_principal: bool = False
    nombre: str
    email: str | None = None
    rol: str
    zona_id: IdOpcional = None
    zona_nombre: str | None = None
    oficina_id: IdOpcional = None
    oficina_nombre: str | None = None
    iniciales: str = ""
    permisos: list[str] = Field(default_factory=list)
    recomendaciones_ia: bool = True
    csrf_token: str | None = None
    institucion: str = ""
    version_password: int | None = None


class CambioPassword(Base):
    password_actual: str
    password_nuevo: str = Field(min_length=8)


class RestablecerPassword(Base):
    password: str = Field(min_length=8, max_length=120)


class AdministradorInicial(Base):
    nombre: str = Field(min_length=3, max_length=160)
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=8, max_length=120)
    telefono: str | None = None


class PreferenciaIA(Base):
    recomendaciones_ia: bool


class PersonaNoRegistrada(Base):
    """Solicitante sin cuenta, registrado por el equipo TI."""

    nombre: str = Field(min_length=3, max_length=160)
    telefono: str | None = None
    anexo: str | None = None
    zona_id: Id | None = None
    oficina_id: Id | None = None
    zona_nombre: str | None = None
    oficina_nombre: str | None = None
    crear_usuario: bool = False


class SugerenciaPersona(Base):
    id: IdOpcional = None
    nombre: str
    iniciales: str = ""
    zona_nombre: str | None = None
    oficina_nombre: str | None = None
    es_registrado: bool = True
    activo: bool = True


OficinaDetalle.model_rebuild()
