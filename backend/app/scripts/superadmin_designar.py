"""Designa al titular en instalaciones previas con varios administradores.

Requiere acceso a la consola del servidor. No permite sustituir un titular existente.
"""
import argparse
import asyncio

from pymongo.errors import DuplicateKeyError

from app.core.audit import registrar
from app.core.db import close_connections, get_db
from app.core.errors import Prohibido
from app.migrations import runner


async def designar(email: str):
    db = get_db()
    if await db['usuarios'].find_one({'superadministrador': True}):
        raise Prohibido('Ya existe un superadministrador. No se modifica su titularidad.')
    objetivo = await db['usuarios'].find_one({
        'email_normalizado': email.strip().lower(), 'rol': 'administrador', 'activo': True,
    })
    if objetivo is None:
        raise Prohibido('El correo debe corresponder a un administrador activo existente.')
    try:
        resultado = await db['usuarios'].update_one(
            {'_id': objetivo['_id'], 'rol': 'administrador', 'activo': True},
            {'$set': {'superadministrador': True}},
        )
    except DuplicateKeyError as exc:
        raise Prohibido('Ya se designó un superadministrador desde otra operación.') from exc
    if resultado.modified_count != 1:
        raise Prohibido('La cuenta cambió durante la operación. Revisa su estado.')
    await registrar(
        'usuario.superadministrador', usuario_nombre='Consola del servidor', rol='administrador',
        entidad='usuario', entidad_id=objetivo['_id'],
        resumen=f"Superadministrador designado: {objetivo['nombre']}",
        contexto={'origen': 'consola_servidor'},
    )


async def principal(email):
    try:
        await runner.ejecutar()
        await designar(email)
        print('Superadministrador designado. Vuelve a iniciar sesión.')
    finally:
        await close_connections()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    args = parser.parse_args()
    try:
        asyncio.run(principal(args.email))
    except Prohibido as exc:
        parser.exit(1, exc.mensaje + '\n')
