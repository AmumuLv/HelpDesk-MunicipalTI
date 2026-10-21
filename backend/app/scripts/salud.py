"""Comprobacion rapida del sistema: Mongo, Redis, migraciones y estructura.

    python -m app.scripts.salud
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import settings
from app.core.db import close_connections, get_db, ping_mongo, ping_redis
from app.core.logging_config import configurar_logging
from app.domain.schemas_db import COLECCIONES, INDEXES


async def _principal() -> int:
    from app.migrations import runner

    mongo = await ping_mongo()
    redis = await ping_redis()
    print(f"Mesa de Ayuda TI  ({settings.app_env})")
    print(f"MongoDB ......... {'OK' if mongo else 'SIN RESPUESTA'}  {settings.mongo_db}")
    print(f"Redis ........... {'OK' if redis else 'SIN RESPUESTA'}")
    if mongo:
        db = get_db()
        existentes = set(await db.list_collection_names())
        faltantes = [c for c in COLECCIONES if c not in existentes]
        print(f"Colecciones ..... {len(existentes) - len(faltantes)}/{len(COLECCIONES)} creadas")
        if faltantes:
            print(f"  Faltan: {', '.join(faltantes)}")
        indices = 0
        faltantes_indices: list[str] = []
        for coleccion, nombre, _, _ in INDEXES:
            if coleccion not in existentes:
                continue
            lista = await db[coleccion].index_information()
            if nombre in lista:
                indices += 1
            else:
                faltantes_indices.append(f"{coleccion}.{nombre}")
        print(f"Indices ......... {indices}/{len(INDEXES)}")
        if faltantes_indices:
            print(f"  Faltan: {', '.join(faltantes_indices[:10])}")
        print("\nMigraciones:")
        for fila in await runner.estado():
            print(f"  {'OK ' if fila['aplicada'] else '-- '}{fila['version']}  {fila['descripcion']}")
        config = await db["configuracion"].find_one({"_id": "config"})
        if config:
            ia = config.get("ia", {})
            print(f"\nIA global ....... {'activa' if ia.get('global_activa') else 'desactivada'}")
            print(f"Aprendizaje ..... {'activo' if ia.get('aprendizaje_activo') else 'pausado'}")
        await db["auditoria"].count_documents({})
    print(f"\nZona horaria de negocio: {settings.business_timezone}")
    return 0 if mongo and redis else 1


def main() -> None:
    configurar_logging("ERROR")
    try:
        codigo = asyncio.run(_principal())
    finally:
        asyncio.run(close_connections())
    raise SystemExit(codigo)


if __name__ == "__main__":
    main()