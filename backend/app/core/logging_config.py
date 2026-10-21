"""Configuracion de logging estructurado y simple."""

from __future__ import annotations

import logging
import sys

_CONFIGURADO = False


def configurar_logging(nivel: str = "INFO") -> None:
    global _CONFIGURADO
    if _CONFIGURADO:
        return
    raiz = logging.getLogger()
    raiz.setLevel(getattr(logging, nivel.upper(), logging.INFO))
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    raiz.addHandler(manejador)
    # Access log de uvicorn duplicado
    logging.getLogger("uvicorn.access").handlers.clear()
    _CONFIGURADO = True


def obtener_logger(nombre: str) -> logging.Logger:
    return logging.getLogger(nombre)