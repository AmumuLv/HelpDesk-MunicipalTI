"""Índice para consultar antecedentes por computadora sin recorrer todos los tickets."""
DESCRIPCION = 'Historial de tickets por conjunto'


async def aplicar(db):
    await db.tickets.create_index([('conjunto_id', 1), ('creado_en', -1)], name='ix_tickets_conjunto')
