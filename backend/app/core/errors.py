"""Errores de dominio y traduccion a respuestas HTTP uniformes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Error de negocio con codigo estable para el frontend."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    codigo: str = "error_general"

    def __init__(
        self,
        mensaje: str,
        *,
        detalles: Any = None,
        codigo: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles
        if codigo:
            self.codigo = codigo
        if status_code:
            self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"codigo": self.codigo, "mensaje": self.mensaje}
        if self.detalles is not None:
            body["detalles"] = self.detalles
        return body


class NoAutorizado(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    codigo = "no_autorizado"


class Prohibido(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    codigo = "sin_permiso"


class NoEncontrado(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    codigo = "no_encontrado"


class Conflicto(AppError):
    status_code = status.HTTP_409_CONFLICT
    codigo = "conflicto"


class Validacion(AppError):
    status_code = 422
    codigo = "validacion"


class DemasiadasPeticiones(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    codigo = "demasiadas_peticiones"


class DependenciaNoDisponible(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    codigo = "dependencia_no_disponible"


def _validacion_a_lista(err: RequestValidationError) -> list[dict[str, Any]]:
    campos: list[dict[str, Any]] = []
    for item in err.errors():
        loc = [str(part) for part in item.get("loc", []) if part not in ("body", "query")]
        campos.append(
            {
                "campo": ".".join(loc) or "general",
                "mensaje": item.get("msg", "valor invalido"),
                "tipo": item.get("type", "invalid"),
            }
        )
    return campos


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def _req_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        campos = _validacion_a_lista(exc)
        return JSONResponse(
            status_code=422,
            content={
                "codigo": "validacion",
                "mensaje": "Revisa los datos ingresados.",
                "detalles": campos,
            },
        )

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        logging.getLogger("app.errores").warning(
            "ValueError no controlado en %s %s: %s", request.method, request.url.path, exc, exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"codigo": "dato_invalido", "mensaje": str(exc)},
        )