import asyncio
import contextlib
import json
import unittest

from bson import ObjectId
from app.services.sincronizacion_service import aviso_cambio, vigilar_cambios, CANAL


class AvisosSeguros(unittest.TestCase):
    def test_no_difunde_documentos_ni_cambios_de_lectura(self):
        cambio = {'ns': {'coll': 'usuarios'}, 'operationType': 'update', 'documentKey': {'_id': ObjectId()}, 'updateDescription': {'updatedFields': {'foto': {'nombre': 'privado.webp'}, 'email': 'privado'}, 'removedFields': []}, 'fullDocument': {'password_hash': 'secreto'}}
        dominio, foto = aviso_cambio(cambio)
        self.assertEqual(dominio, 'usuarios')
        self.assertEqual(foto, str(cambio['documentKey']['_id']))
        self.assertNotIn('privado', str((dominio, foto)))
        cambio['ns']['coll'] = 'articulos_kb'
        cambio['updateDescription']['updatedFields'] = {'lectores_ids.0': ObjectId(), 'visualizaciones': 2}
        self.assertIsNone(aviso_cambio(cambio))
        cambio['ns']['coll'] = 'sesiones'
        cambio['updateDescription']['updatedFields'] = {'ultimo_uso': 'ahora'}
        self.assertIsNone(aviso_cambio(cambio))


async def test_cambios_de_otro_cliente_se_publican_agrupados_sin_datos_privados(db, api):
    from app.core.db import get_redis
    from tests.test_tickets_horarios import _mundo
    mundo = await _mundo(api, 'sincronizacion')
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(CANAL)
    listo = asyncio.Event()
    tarea = asyncio.create_task(vigilar_cambios(listo))
    try:
        await asyncio.wait_for(listo.wait(), 10)
        r = await api.patch('/api/usuarios/' + mundo['usuario_id'], headers=mundo['admin'], json={'nombre': 'Nombre actualizado remotamente'})
        assert r.status_code == 200, r.text
        await db.usuarios.update_one({'_id': ObjectId(mundo['usuario_id'])}, {'$set': {'foto': {'nombre': 'privado.webp'}}})
        r = await api.post('/api/activos', headers=mundo['admin'], json={'tipo': 'Laptop', 'oficina_id': mundo['oficina']['id']})
        assert r.status_code == 201, r.text
        r = await api.post('/api/tickets', headers=mundo['usuario'], json={'tipo_problema': 'Otro', 'descripcion': 'Necesito ayuda en mi oficina'})
        assert r.status_code == 201, r.text
        dominios, fotos = set(), set()
        async with asyncio.timeout(10):
            while not {'usuarios', 'equipos', 'tickets'} <= dominios or mundo['usuario_id'] not in fotos:
                mensaje = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                if not mensaje:
                    continue
                datos = json.loads(mensaje['data'])
                if datos.get('tipo') != 'datos_actualizados':
                    continue
                assert set(datos) == {'tipo', 'dominios', 'fotos', 'fotos_todas'}
                assert 'privado' not in str(datos) and 'Nombre actualizado' not in str(datos)
                dominios.update(datos['dominios']); fotos.update(datos['fotos'])
    finally:
        tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarea
        await pubsub.aclose()
