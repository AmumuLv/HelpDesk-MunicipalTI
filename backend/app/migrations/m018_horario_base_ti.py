"""Corrige los horarios iniciales antiguos del personal TI sin alterar excepciones."""

DESCRIPCION = "Horario inicial TI de lunes a viernes, 08:00-13:00 y 14:00-17:00"


async def aplicar(db):
    from app.domain.horario import horario_base
    from app.core.time import utcnow

    antiguos = [
        [{"entrada": "08:00", "salida": "13:00"}, {"entrada": "15:00", "salida": "18:00"}],
        [{"entrada": "08:00", "salida": "13:00"}, {"entrada": "14:00", "salida": "17:00"}],
    ]
    ids = await db["usuarios"].distinct("_id", {"rol": {"$in": ["tecnico", "administrador"]}})
    for identificador in ids:
        await db["tecnicos_perfil"].update_one({"usuario_id": identificador}, {"$setOnInsert": {
            "usuario_id": identificador, "horario": horario_base(), "capacidad_diaria": 8,
            "especialidades": [], "categorias": [], "zonas_pref": [], "activo": True, "creado_en": utcnow(),
        }}, upsert=True)
    async for perfil in db["tecnicos_perfil"].find({"usuario_id": {"$in": ids}}):
        dias = (perfil.get("horario") or {}).get("dias") or {}
        laborables = {str(d): config for d, config in dias.items() if not config.get("libre") and config.get("tramos")}
        es_inicial = not dias or (
            set(laborables) in ({"0", "1", "2", "3", "4"}, {"1", "2", "3", "4", "5"})
            and all(config.get("tramos") in antiguos for config in laborables.values())
        )
        if es_inicial:
            await db["tecnicos_perfil"].update_one({"_id": perfil["_id"]}, {"$set": {
                "horario_previo_correccion_018": perfil.get("horario"),
                "horario": horario_base(), "actualizado_en": utcnow(),
            }})


async def revertir(db):
    async for perfil in db["tecnicos_perfil"].find({"horario_previo_correccion_018": {"$exists": True}}):
        await db["tecnicos_perfil"].update_one({"_id": perfil["_id"]}, {
            "$set": {"horario": perfil["horario_previo_correccion_018"]},
            "$unset": {"horario_previo_correccion_018": ""},
        })
