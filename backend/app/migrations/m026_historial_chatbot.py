"""Índice del historial privado del chatbot TI."""
DESCRIPCION = 'Conversaciones del chatbot ordenadas por cuenta y actualización'


async def aplicar(db):
    await db['chatbot_conversaciones'].create_index(
        [('usuario_id', 1), ('actualizado_en', -1)], name='ix_chatbot_usuario_fecha')
