"""Esquemas de inventario: conjuntos, activos, catalogos, calidad e importacion."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.core.ids import normalizar_texto
from app.domain.constants import (
    CAMPOS_CON_ESTADO,
    CAMPO_NO_APLICA,
    CAMPO_NO_DISPONIBLE,
    CAMPO_PENDIENTE,
    ESTADOS_CAMPO,
    ESTADOS_ACTIVO_INICIALES,
    PROPIEDADES_INICIALES,
    TIPOS_DISPOSITIVO_INICIALES,
)
from app.schemas.common import Base, Id, IdFiltro, IdOpcional


# ── Estado por campo ─────────────────────────────────────────
class EstadoCampo(Base):
    estado: str = CAMPO_PENDIENTE
    motivo: str | None = None
    nota: str | None = None
    usuario_id: IdOpcional = None
    usuario_nombre: str | None = None
    fecha: datetime | None = None

    @field_validator("estado")
    @classmethod
    def _valido(cls, v: str) -> str:
        if v not in ESTADOS_CAMPO:
            raise ValueError("Estado de campo no valido")
        return v


class CambioEstadoCampo(Base):
    campos: list[str] = Field(min_length=1)
    estado: str
    motivo: str | None = None
    nota: str | None = None

    @field_validator("estado")
    @classmethod
    def _valido(cls, v: str) -> str:
        if v not in ESTADOS_CAMPO:
            raise ValueError("Estado de campo no valido")
        return v

    @field_validator("campos")
    @classmethod
    def _campos(cls, v: list[str]) -> list[str]:
        for campo in v:
            if campo not in CAMPOS_CON_ESTADO:
                raise ValueError(f"Campo no admite estado: {campo}")
        return v


# ── Conjuntos ────────────────────────────────────────────────
class ConjuntoBase(Base):
    nombre: str = Field(min_length=2, max_length=120)
    oficina_id: Id
    responsable_id: IdOpcional = None
    uso_comun: bool = False
    estado: str = "Operativo"
    notas: str | None = Field(default=None, max_length=2000)
    componentes: list[str] = Field(default_factory=list)
    activo: bool = True


class ConjuntoCrear(ConjuntoBase):
    numero: int | None = None
    zona_id: Id | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        return normalizar_texto(v)


class ConjuntoActualizar(Base):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    responsable_id: IdOpcional = None
    uso_comun: bool | None = None
    estado: str | None = None
    notas: str | None = None
    activo: bool | None = None


class ConjuntoResumen(Base):
    id: Id
    nombre: str
    oficina_id: Id
    zona_id: Id | None = None
    zona_nombre: str | None = None
    oficina_nombre: str | None = None
    responsable_id: IdOpcional = None
    responsable_nombre: str | None = None
    uso_comun: bool = False
    estado: str = "Operativo"
    total_activos: int = 0
    activos_operativos: int = 0
    completitud: float = 0.0
    pendientes: int = 0
    opciones_avanzadas: int = 0


# ── Detalle avanzado ─────────────────────────────────────────
class ModuloMemoria(Base):
    ranura: str | None = None
    capacidad_gb: float | None = None
    tipo: str | None = None
    velocidad_mhz: int | None = None
    marca: str | None = None
    serie: str | None = None


class UnidadDisco(Base):
    tipo: str | None = None
    capacidad_gb: float | None = None
    marca: str | None = None
    modelo: str | None = None
    serie: str | None = None
    salud: str | None = None
    interfaz: str | None = None


class ComponenteInterno(Base):
    """Elemento repetible de la seccion avanzada."""

    tipo: str
    descripcion: str | None = None
    cantidad: int = 1
    datos: dict[str, Any] = Field(default_factory=dict)


class Licencia(Base):
    producto: str | None = None
    tipo: str | None = None
    clave_cifrada: str | None = None
    titular: str | None = None
    vence: date | None = None


class DetalleAvanzado(Base):
    """Secciones plegables, todas opcionales y solo si el interruptor esta activo."""

    placa_madre: dict[str, Any] | None = None
    procesador_detalle: dict[str, Any] | None = None
    memoria_modulos: list[ModuloMemoria] | None = None
    almacenamiento_unidades: list[UnidadDisco] | None = None
    fuente_poder: dict[str, Any] | None = None
    tarjeta_grafica: list[dict[str, Any]] | None = None
    red: list[dict[str, Any]] | None = None
    gabinete: dict[str, Any] | None = None
    bateria: dict[str, Any] | None = None
    cargador: dict[str, Any] | None = None
    pantalla: dict[str, Any] | None = None
    sistema_operativo: dict[str, Any] | None = None
    licencias: list[Licencia] | None = None
    compra_garantia: dict[str, Any] | None = None
    mantenimiento: dict[str, Any] | None = None
    tipo_impresora: dict[str, Any] | None = None
    conexion: dict[str, Any] | None = None
    consumibles: list[dict[str, Any]] | None = None
    contador_paginas: dict[str, Any] | None = None
    resolucion: dict[str, Any] | None = None
    puertos: list[str] | None = None

    def resumen(self) -> dict[str, Any]:
        """Datos derivados que alimentan los campos basicos."""
        modulos = self.memoria_modulos or []
        unidades = self.almacenamiento_unidades or []
        salida: dict[str, Any] = {}
        if modulos:
            total = sum(float(m.capacidad_gb or 0) for m in modulos)
            tipos = sorted({m.tipo for m in modulos if m.tipo})
            vel = sorted({m.velocidad_mhz for m in modulos if m.velocidad_mhz})
            salida["memoria_ram"] = " + ".join(
                part for part in [f"{total:g} GB", " / ".join(tipos), " / ".join(f"{v} MHz" for v in vel)] if part
            )
            salida["memoria_ram_total_gb"] = total
        if unidades:
            total_gb = sum(float(u.capacidad_gb or 0) for u in unidades)
            tipos = sorted({u.tipo for u in unidades if u.tipo})
            salida["almacenamiento"] = " + ".join(
                part for part in [f"{total_gb:g} GB", " / ".join(tipos)] if part
            )
            salida["almacenamiento_total_gb"] = total_gb
        return salida

    def calculos(self) -> dict[str, Any]:
        """Ranuras libres, capacidad instalada y avisos blandos."""
        modulos = self.memoria_modulos or []
        unidades = self.almacenamiento_unidades or []
        madre = self.placa_madre or {}
        total_ranuras = madre.get("ranuras_ram_totales")
        ocupada = len(modulos) or madre.get("ranuras_ram_ocupadas")
        maxima = madre.get("ram_maxima_soportada")
        instalada = round(sum(float(m.capacidad_gb or 0) for m in modulos), 2)
        calculo: dict[str, Any] = {
            "modulos_memoria": len(modulos),
            "unidades_disco": len(unidades),
            "ram_instalada_gb": instalada,
            "almacenamiento_total_gb": round(sum(float(u.capacidad_gb or 0) for u in unidades), 2),
        }
        avisos: list[str] = []
        if isinstance(total_ranuras, int) and isinstance(ocupada, int):
            libres = max(total_ranuras - ocupada, 0)
            calculo["ranuras_ram_libres"] = libres
            if ocupada > total_ranuras:
                avisos.append("Las ranuras de RAM ocupadas son mas que las totales.")
        if isinstance(maxima, (int, float)) and instalada > maxima:
            avisos.append("La RAM instalada supera la capacidad maxima soportada por la placa.")
        calculo["avisos"] = avisos
        return calculo


# ── Activos ──────────────────────────────────────────────────
class ActivoBase(Base):
    tipo: str = Field(min_length=2, max_length=80)
    oficina_id: Id
    conjunto_id: IdOpcional = None
    responsable_id: IdOpcional = None
    codigo_patrimonial: str | None = Field(default=None, max_length=60)
    marca: str | None = Field(default=None, max_length=120)
    modelo: str | None = Field(default=None, max_length=120)
    tamano_pantalla: str | None = Field(default=None, max_length=60)
    nombre_equipo: str | None = Field(default=None, max_length=160)
    procesador: str | None = Field(default=None, max_length=200)
    memoria_ram: str | None = Field(default=None, max_length=200)
    almacenamiento: str | None = Field(default=None, max_length=200)
    direccion_ip: str | None = Field(default=None, max_length=45)
    direccion_mac: str | None = Field(default=None, max_length=40)
    propiedad: str | None = Field(default=None, max_length=60)
    estado: str | None = Field(default=None, max_length=60)
    observaciones: str | None = Field(default=None, max_length=4000)
    opciones_avanzadas: bool = False
    detalle_avanzado: DetalleAvanzado | None = None

    @field_validator(
        "codigo_patrimonial",
        "marca",
        "modelo",
        "nombre_equipo",
        "estado",
        "propiedad",
        mode="before",
    )
    @classmethod
    def _limpiar(cls, v: Any) -> Any:
        if v is None:
            return None
        texto = normalizar_texto(v)
        return texto or None


class ActivoCrear(ActivoBase):
    campos_estado: dict[str, EstadoCampo] = Field(default_factory=dict)


class ActivoActualizar(Base):
    tipo: str | None = None
    oficina_id: Id | None = None
    conjunto_id: Id | None = None
    responsable_id: Id | None = None
    codigo_patrimonial: str | None = None
    marca: str | None = None
    modelo: str | None = None
    tamano_pantalla: str | None = None
    nombre_equipo: str | None = None
    procesador: str | None = None
    memoria_ram: str | None = None
    almacenamiento: str | None = None
    direccion_ip: str | None = None
    direccion_mac: str | None = None
    propiedad: str | None = None
    estado: str | None = None
    observaciones: str | None = None
    motivo: str | None = Field(default=None, max_length=500)
    opciones_avanzadas: bool | None = None
    detalle_avanzado: DetalleAvanzado | None = None


class EstadoCampoLectura(Base):
    estado: str
    valor: str | None = None
    motivo: str | None = None
    nota: str | None = None
    esperado: bool = False
    usuario_nombre: str | None = None
    fecha: datetime | None = None


class Completitud(Base):
    porcentaje: float = 0.0
    completos: int = 0
    esperados: int = 0
    faltantes: int = 0


class HistorialResponsable(Base):
    id: Id
    responsable_id: IdOpcional = None
    responsable_nombre: str | None = None
    inicio: datetime | None = None
    fin: datetime | None = None
    motivo: str | None = None
    usuario_id: IdOpcional = None
    usuario_nombre: str | None = None
    fecha: datetime | None = None


class CambioComponente(Base):
    id: Id
    seccion: str
    resumen: str
    antes: Any = None
    despues: Any = None
    fecha: datetime
    usuario_nombre: str | None = None
    ticket_id: IdOpcional = None
    ticket_codigo: str | None = None


class PrediccionFalla(Base):
    """Probabilidad con horizonte y confianza. Nunca se presenta como certeza."""

    probabilidad: float
    nivel: str = "baja"
    horizonte_dias: int = 90
    confianza: float = 0.0
    factores: list[str] = Field(default_factory=list)
    suficiente_datos: bool = True
    actualizado_en: datetime | None = None
    tickets_historia: int = 0
    dias_activo: int | None = None
    garantia_vigente: bool | None = None


class AlertaActivo(Base):
    tipo: str
    mensaje: str
    nivel: str = "atencion"


class ActivoResumen(Base):
    id: Id
    tipo: str
    nombre_equipo: str | None = None
    codigo_patrimonial: str | None = None
    marca: str | None = None
    modelo: str | None = None
    estado: str | None = None
    oficina_id: Id | None = None
    oficina_nombre: str | None = None
    zona_id: Id | None = None
    zona_nombre: str | None = None
    conjunto_id: IdOpcional = None
    conjunto_nombre: str | None = None
    responsable_id: IdOpcional = None
    responsable_nombre: str | None = None
    uso_comun: bool = False
    completitud: float = 0.0
    faltantes: int = 0
    opciones_avanzadas: bool = False
    creado_en: datetime | None = None


class ActivoDetalle(ActivoResumen):
    tamano_pantalla: str | None = None
    procesador: str | None = None
    memoria_ram: str | None = None
    almacenamiento: str | None = None
    direccion_ip: str | None = None
    direccion_mac: str | None = None
    propiedad: str | None = None
    observaciones: str | None = None
    campos: dict[str, EstadoCampoLectura] = Field(default_factory=dict)
    campos_derivados: list[str] = Field(default_factory=list)
    completitud_detalle: Completitud = Field(default_factory=Completitud)
    secciones_avanzadas: list[str] = Field(default_factory=list)
    detalle_avanzado: dict[str, Any] | None = None
    calculos_avanzados: dict[str, Any] = Field(default_factory=dict)
    historial_responsables: list[HistorialResponsable] = Field(default_factory=list)
    historial_componentes: list[CambioComponente] = Field(default_factory=list)
    tickets: list[dict[str, Any]] = Field(default_factory=list)
    alertas: list[AlertaActivo] = Field(default_factory=list)
    prediccion: PrediccionFalla | None = None
    campana_estado: str | None = None
    creado_por: str | None = None
    actualizado_en: datetime | None = None
    version: int = 1


class CambioResponsable(Base):
    responsable_id: IdOpcional = None
    motivo: str | None = Field(default=None, max_length=500)
    confirmar_transferencia: bool = False


class CambioMasivo(Base):
    activo_ids: list[Id] = Field(min_length=1, max_length=500)
    estado: str | None = None
    oficina_id: Id | None = None
    responsable_id: Id | None = None
    propiedad: str | None = None
    observaciones: str | None = None
    motivo: str | None = None


class CambioCamposMasivo(Base):
    """Marcar un campo como 'No aplica' / 'No disponible' en varios equipos."""

    activo_ids: list[Id] = Field(min_length=1, max_length=500)
    campos: list[str] = Field(min_length=1)
    estado: str
    motivo: str | None = None
    nota: str | None = None

    @field_validator("estado")
    @classmethod
    def _estado(cls, v: str) -> str:
        if v not in ESTADOS_CAMPO:
            raise ValueError("Estado de campo no valido")
        return v

    @field_validator("campos")
    @classmethod
    def _campos(cls, v: list[str]) -> list[str]:
        for campo in v:
            if campo not in CAMPOS_CON_ESTADO:
                raise ValueError(f"Campo no admite estado: {campo}")
        return v


class OpcionesAvanzadasMasivo(Base):
    activo_ids: list[Id] = Field(min_length=1, max_length=500)
    activar: bool = True


# ── Sugerencias de autocompletado ────────────────────────────
class Sugerencia(Base):
    valor: str
    frecuencia: int = 0
    marca: str | None = None
    frecuencia_marca: int = 0
    ejemplo_completo: dict[str, Any] | None = None


class SugerenciasCampo(Base):
    campo: str
    tipo: str | None = None
    marca: str | None = None
    valores: list[Sugerencia] = Field(default_factory=list)
    es_manual: bool = False


# ── Catalogos ────────────────────────────────────────────────
class CatalogoValor(Base):
    valor: str = Field(min_length=1, max_length=120)
    activo: bool = True
    orden: int = 0
    etiqueta: str | None = None


class CatalogoActualizar(Base):
    clave: str
    valores: list[CatalogoValor]
    aviso: bool = True

    @field_validator("clave")
    @classmethod
    def _clave(cls, v: str) -> str:
        permitidas = {
            "tipos_dispositivo",
            "estados_activo",
            "propiedades",
            "categorias",
            "motivos_no_aplica",
            "motivos_no_disponible",
            "sinonimos_dispositivo",
            "componentes_conjunto",
            "tipos_ausencia",
        }
        if v not in permitidas:
            raise ValueError("Catalogo no editable")
        return v


class EsquemaTipo(Base):
    tipo: str
    esperados: list[str] = Field(default_factory=list)
    opcionales: list[str] = Field(default_factory=list)
    avanzadas: list[str] = Field(default_factory=list)


class EsquemaTipoActualizar(Base):
    esperados: list[str] | None = None
    opcionales: list[str] | None = None
    avanzadas: list[str] | None = None


# ── Calidad del inventario ───────────────────────────────────
class FilaCalidad(Base):
    activo_id: Id
    nombre: str
    tipo: str
    codigo_patrimonial: str | None = None
    oficina_nombre: str | None = None
    zona_nombre: str | None = None
    responsable_nombre: str | None = None
    porcentaje: float = 0.0
    faltantes: int = 0
    campos_faltantes: list[str] = Field(default_factory=list)


class FilaCalidadOficina(Base):
    id: str | None = None
    nombre: str
    total: int = 0
    porcentaje: float = 0.0
    faltantes: int = 0
    equipos_incompletos: int = 0
    campos_faltantes: list[dict[str, Any]] = Field(default_factory=list)


class ResumenCalidad(Base):
    porcentaje_global: float = 0.0
    total_activos: int = 0
    con_datos_completos: int = 0
    faltantes_totales: int = 0
    por_zona: list[dict[str, Any]] = Field(default_factory=list)
    por_oficina: list[FilaCalidadOficina] = Field(default_factory=list)
    por_tipo: list[dict[str, Any]] = Field(default_factory=list)
    por_campo: list[dict[str, Any]] = Field(default_factory=list)


class FiltrosInventario(Base):
    # `IdFiltro` y no `Id`: estos vienen de la barra de direcciones. Con `Id`, una URL
    # guardada con un id que ya no existe —o alguien que edita el número a mano—
    # devolvía 422 y la pantalla se quedaba en blanco con dos errores en la consola.
    # Un filtro que no se puede aplicar se ignora: es lo que ya hace la pantalla, donde
    # ese filtro tampoco sale marcado.
    zona_id: IdFiltro = None
    oficina_id: IdFiltro = None
    tipo: str | None = None
    estado: str | None = None
    propiedad: str | None = None
    responsable_id: IdFiltro = None
    solo_uso_comun: bool | None = None
    responsables_pendientes: bool | None = None
    solo_faltantes: bool | None = None
    solo_opciones_avanzadas: bool | None = None
    conjunto_id: IdFiltro = None
    texto: str | None = None
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=25, ge=1, le=100)
    orden: Literal['ubicacion', 'nombre_equipo', 'tipo', 'marca', 'estado', 'actualizado_en', 'creado_en'] = 'creado_en'
    vista: str = "plana"


# ── Importacion ──────────────────────────────────────────────
class ColumnaDetectada(Base):
    clave: str
    etiqueta: str
    columna: str | None = None
    confianza: float = 0.0
    requerido: bool = False


class HojaDetectada(Base):
    nombre_hoja: str
    zona_nombre: str
    zona_id: IdOpcional = None
    zona_existe: bool = False
    fusionar_con: Id | None = None
    filas: int = 0
    oficinas: list[str] = Field(default_factory=list)
    oficinas_existentes: list[str] = Field(default_factory=list)
    oficinas_nuevas: list[str] = Field(default_factory=list)


class AnalisisArchivo(Base):
    nombre_archivo: str
    hojas: list[HojaDetectada] = Field(default_factory=list)
    columnas: dict[str, ColumnaDetectada] = Field(default_factory=dict)
    columnas_disponibles: list[str] = Field(default_factory=list)
    filas_totales: int = 0
    lote_id: str | None = None


class MapeoColumnas(Base):
    area: str | None = None
    tipo_equipo: str | None = None
    dispositivo: str | None = None
    codigo_patrimonial: str | None = None
    marca: str | None = None
    modelo: str | None = None
    tamano_pantalla: str | None = None
    nombre_equipo: str | None = None
    procesador: str | None = None
    memoria_ram: str | None = None
    almacenamiento: str | None = None
    direccion_ip: str | None = None
    direccion_mac: str | None = None
    propiedad: str | None = None
    estado: str | None = None
    responsable: str | None = None


class FilaPrevia(Base):
    numero: int
    zona_nombre: str
    oficina_nombre: str
    conjunto_nombre: str | None = None
    tipo_dispositivo: str
    marca: str | None = None
    modelo: str | None = None
    codigo_patrimonial: str | None = None
    responsable_nombre: str | None = None
    accion: str = "crear"
    advertencias: list[str] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)
    campos_no_aplica_sugeridos: list[str] = Field(default_factory=list)
    campos_estado: dict[str, str] = Field(default_factory=dict)
    valida: bool = True


class Previsualizacion(Base):
    lote_id: str
    filas: list[FilaPrevia] = Field(default_factory=list)
    total_filas: int = 0
    validas: int = 0
    con_error: int = 0
    con_advertencia: int = 0
    crearia: int = 0
    actualizaria: int = 0
    omitiria: int = 0
    reglas_aplicadas: list[str] = Field(default_factory=list)
    sin_responsable: list[str] = Field(default_factory=list)


class ImportarConfirmado(Base):
    lote_id: str
    filas_excluidas: list[int] = Field(default_factory=list)
    no_aplicar_confirmado: list[str] = Field(default_factory=list)
    crear_usuarios_faltantes: bool = False


class ResumenImportacion(Base):
    lote_id: str
    creados: int = 0
    actualizados: int = 0
    omitidos: int = 0
    errores: int = 0
    zonas_creadas: list[str] = Field(default_factory=list)
    oficinas_creadas: list[str] = Field(default_factory=list)
    conjuntos_creados: int = 0
    usuarios_creados: int = 0
    sin_codigo_advertencia: int = 0
    reversible: bool = True
    detalle: list[str] = Field(default_factory=list)


class EstadoImportacion(Base):
    id: Id
    nombre_archivo: str
    estado: str
    creado_en: datetime
    confirmado_en: datetime | None = None
    usuario_id: IdOpcional = None
    usuario_nombre: str | None = None
    resumen: dict[str, Any] = Field(default_factory=dict)
    reversible: bool = False
    observaciones: str | None = None


class NormalizacionTexto(Base):
    sinonimos: dict[str, str] = Field(default_factory=dict)
    valores_sin_dato: list[str] = Field(default_factory=list)
    fusionar_variantes: bool = True


class PlantillaRespuesta(Base):
    nombre_archivo: str
    contenido: bytes


CATALOGOS_INICIALES = {
    "tipos_dispositivo": TIPOS_DISPOSITIVO_INICIALES,
    "estados_activo": ESTADOS_ACTIVO_INICIALES,
    "propiedades": PROPIEDADES_INICIALES,
    "estados_campo": list(ESTADOS_CAMPO),
}
