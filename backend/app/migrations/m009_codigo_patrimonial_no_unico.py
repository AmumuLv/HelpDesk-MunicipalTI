"""Permitir códigos patrimoniales repetidos y advertirlos en la interfaz."""

DESCRIPCION = "Permitir registrar códigos patrimoniales repetidos"


async def aplicar(db):
    indices = await db["activos"].index_information()
    if "uq_activos_codigo" in indices:
        await db["activos"].drop_index("uq_activos_codigo")
    await db["activos"].create_index(
        [("codigo_patrimonial", 1)],
        name="ix_activos_codigo",
    )


async def revertir(db):
    activos = db["activos"]
    duplicados = await activos.aggregate([
        {"$match": {"codigo_patrimonial": {"$type": "string"}}},
        {"$group": {"_id": "$codigo_patrimonial", "total": {"$sum": 1}}},
        {"$match": {"total": {"$gt": 1}}},
        {"$limit": 1},
    ]).to_list(length=1)
    if duplicados:
        raise RuntimeError(
            "No se puede restaurar el índice único: existen códigos repetidos."
        )

    indices = await activos.index_information()
    if "ix_activos_codigo" in indices:
        await activos.drop_index("ix_activos_codigo")
    await activos.create_index(
        [("codigo_patrimonial", 1)],
        name="uq_activos_codigo",
        unique=True,
        partialFilterExpression={"codigo_patrimonial": {"$type": "string"}},
    )
