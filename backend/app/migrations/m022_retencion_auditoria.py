"""Retención de movimientos del equipo TI durante quince días."""
from datetime import timedelta
from app.core.time import utcnow

DESCRIPCION = 'Auditoría de administradores y técnicos, retención de 15 días'

async def aplicar(db):
    await db['auditoria'].delete_many({'$or': [
        {'fecha': {'$lt': utcnow() - timedelta(days=15)}},
        {'rol': {'$nin': ['administrador', 'tecnico']}},
    ]})
    # Reemplaza un TTL anterior si lo hubiera, sin alterar los índices de consulta.
    for nombre, indice in (await db['auditoria'].index_information()).items():
        if indice.get('key') == [('fecha', 1)] and 'expireAfterSeconds' in indice:
            if indice['expireAfterSeconds'] == 15 * 86400:
                return
            await db['auditoria'].drop_index(nombre)
    await db['auditoria'].create_index('fecha', expireAfterSeconds=15 * 86400, name='auditoria_retencion_15d')
