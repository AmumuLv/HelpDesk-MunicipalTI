"""Ensamblado de todos los routers de la API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, auth, chatbot, importacion, inventario, org, tickets, tiempo_real

api = APIRouter()

api.include_router(auth.router)
api.include_router(chatbot.router)
api.include_router(org.router)
api.include_router(inventario.router)
api.include_router(importacion.router)
api.include_router(tickets.router)
api.include_router(tiempo_real.router)
api.include_router(admin.config_router)
api.include_router(admin.permisos_router)
api.include_router(admin.equipo_router)
api.include_router(admin.kb_router)
api.include_router(admin.campanas_router)
api.include_router(admin.analitica_router)
api.include_router(admin.ia_router)
api.include_router(admin.auditoria_router)
api.include_router(admin.export_router)

__all__ = ["api"]
