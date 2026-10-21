"""Saca de la impresora el campo «Tamaño de pantalla».

El esquema de una impresora incluia ``tamano_pantalla`` entre sus opcionales, asi
que la ficha de una impresora pedia el tamano de una pantalla que no tiene. Como
el resto del esquema por tipo ya estaba bien, lo unico que hacia falta era quitar
ese campo de donde no aplica.

A diferencia de la migracion anterior, aqui si se corrige un esquema que ya
existe, porque no es una personalizacion del administrador sino un error. Solo se
toca la lista de campos de los tipos citados y solo si el campo estaba: cualquier
otra customization del administrador se respeta. Volver a anadirlo es una linea
en Configuracion.
"""

DESCRIPCION = "Quita el tamaño de pantalla del esquema de la impresora"

from app.core.time import utcnow

# tipo -> campos que no aplican a ese tipo
CAMPOS_QUITAR: dict[str, list[str]] = {
    "Impresora": ["tamano_pantalla"],
}


async def aplicar(db) -> None:
    ahora = utcnow()
    for tipo, campos in CAMPOS_QUITAR.items():
        documento = await db["esquemas_tipos"].find_one({"tipo": tipo})
        if documento is None:
            continue
        for clave in ("esperados", "opcionales", "avanzadas"):
            actuales = [c for c in (documento.get(clave) or []) if c not in campos]
            if len(actuales) != len(documento.get(clave) or []):
                await db["esquemas_tipos"].update_one(
                    {"tipo": tipo},
                    {"$set": {clave: actuales, "actualizado_en": ahora}},
                )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()


async def revertir(db) -> None:
    ahora = utcnow()
    for tipo, campos in CAMPOS_QUITAR.items():
        documento = await db["esquemas_tipos"].find_one({"tipo": tipo})
        if documento is None:
            continue
        for clave in ("esperados", "opcionales"):
            if clave == "esperados":
                continue
            actuales = list(documento.get(clave) or [])
            for campo in campos:
                if campo not in actuales:
                    actuales.append(campo)
            await db["esquemas_tipos"].update_one(
                {"tipo": tipo}, {"$set": {clave: actuales, "actualizado_en": ahora}}
            )
    from app.services.catalogo_service import invalidar_cache_esquemas

    invalidar_cache_esquemas()