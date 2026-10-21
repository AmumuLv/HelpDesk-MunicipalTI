"""Tipos base de los esquemas Pydantic."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Generic, TypeVar

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """ObjectId que Pydantic v2 sabe validar y serializar a texto."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [core_schema.str_schema(), core_schema.no_info_plain_validator_function(cls.validar)]
                    ),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(str, when_used="json"),
        )

    @classmethod
    def validar(cls, valor: Any) -> ObjectId:
        if isinstance(valor, ObjectId):
            return valor
        try:
            return ObjectId(str(valor))
        except Exception as exc:  # pragma: no cover - validacion
            raise ValueError(f"Identificador no valido: {valor!r}") from exc


Id = PyObjectId
IdOpcional = PyObjectId | None


class PyIdFiltro(ObjectId):
    """
    Identificador de **filtro**: un id mal formado se ignora en vez de ser un error.

    Un filtro viene de la barra de direcciones y se puede guardar en un marcador, o
    quedar pegado cuando alguien edita la URL. Con `Id`, eso devolvía `422` y la
    pantalla se quedaba con «No hay equipos» más dos peticiones fallidas en la consola,
    sin explicar nada: el número de la URL no es un id, así que el filtro no se puede
    aplicar. Ignorarlo es lo correcto, y además es lo coherente con lo que la pantalla
    muestra, donde ese filtro tampoco aparece como seleccionado.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [core_schema.str_schema(), core_schema.no_info_plain_validator_function(cls.validar)]
                    ),
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(str, when_used="json"),
        )

    @classmethod
    def validar(cls, valor: Any) -> ObjectId | None:
        if isinstance(valor, ObjectId):
            return valor
        try:
            return ObjectId(str(valor))
        except Exception:
            return None


IdFiltro = PyIdFiltro | None

T = TypeVar("T")


class Base(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=False,
        populate_by_name=True,
        from_attributes=True,
    )


class BaseRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Paginado(BaseRespuesta, Generic[T]):
    items: list[T]
    total: int
    pagina: int = 1
    por_pagina: int = 25
    total_paginas: int = 0

    @classmethod
    def crear(cls, items: list[Any], total: int, pagina: int, por_pagina: int) -> "Paginado":
        import math

        total_paginas = math.ceil(total / por_pagina) if por_pagina else 0
        return cls(
            items=items,
            total=total,
            pagina=pagina,
            por_pagina=por_pagina,
            total_paginas=total_paginas,
        )


class RespuestaMensaje(BaseModel):
    mensaje: str
    codigo: str = "ok"
    detalles: Any | None = None


class Opcion(BaseModel):
    valor: str
    etiqueta: str
    activo: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class FiltroPeriodo(BaseModel):
    desde: date | None = None
    hasta: date | None = None
    periodo: str | None = "30d"


class FiltroPaginacion(BaseModel):
    pagina: int = Field(1, ge=1)
    por_pagina: int = Field(25, ge=1, le=200)
    orden: str | None = None
    direccion: str = "desc"

    @property
    def skip(self) -> int:
        return (self.pagina - 1) * self.por_pagina

    @property
    def limite(self) -> int:
        return self.por_pagina


class DateTimeAware(BaseModel):
    valor: datetime