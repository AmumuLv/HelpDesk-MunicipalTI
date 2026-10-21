DESCRIPCION = "Asignar un color estable a cada zona"


async def aplicar(db):
    zonas = await db["zonas"].find({}, {"_id": 1, "color_indice": 1}).sort("_id", 1).to_list(None)
    for posicion, zona in enumerate(zonas):
        if not isinstance(zona.get("color_indice"), int) or not 1 <= zona["color_indice"] <= 8:
            await db["zonas"].update_one(
                {"_id": zona["_id"]},
                {"$set": {"color_indice": posicion % 8 + 1}},
            )
