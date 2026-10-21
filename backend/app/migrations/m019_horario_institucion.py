"""Alinea el rango general antiguo con la jornada laboral configurada."""

DESCRIPCION = "Corrige el cierre general inicial de 18:00 a 17:00"


async def aplicar(db):
    await db['configuracion'].update_one(
        {'_id': 'config', 'negocio.horario_inicio_global': '08:00', 'negocio.horario_fin_global': '18:00'},
        {'$set': {'negocio.horario_fin_global': '17:00'}},
    )
