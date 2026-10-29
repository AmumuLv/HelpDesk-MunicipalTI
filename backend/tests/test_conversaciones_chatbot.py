import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from bson import ObjectId

from app.core.config import settings
from app.core.db import close_connections, get_db
from app.core.errors import Conflicto, NoEncontrado, Validacion
from app.services import conversaciones_chatbot as chats


@unittest.skipUnless(os.environ.get('TEST_CHATBOT_MONGO'), 'Requiere MongoDB aislado para la prueba')
class ConversacionesChatbotTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await close_connections()
        self.db_nombre = 'revision_chatbot_' + uuid4().hex
        self.parches = [patch.object(settings, 'mongo_uri', os.environ['TEST_CHATBOT_MONGO']), patch.object(settings, 'mongo_db', self.db_nombre), patch.object(settings, 'chatbot_limite_consultas_tecnico', 15), patch.object(chats.chatbot_service, 'estado', return_value={'configurado': True})]
        for parche in self.parches:
            parche.start()
        self.usuario = {'_id': ObjectId(), 'rol': 'tecnico'}
        self.otro = {'_id': ObjectId(), 'rol': 'tecnico'}
        from app.migrations.m026_historial_chatbot import aplicar
        await aplicar(get_db())

    async def asyncTearDown(self):
        # Solo la base efímera creada arriba; nunca utilizar la base de producción.
        if not self.db_nombre.startswith('revision_chatbot_'):
            raise RuntimeError('Base de prueba fuera del ámbito previsto')
        await get_db().client.drop_database(self.db_nombre)
        await close_connections()
        for parche in reversed(self.parches):
            parche.stop()

    def pregunta(self, identificador=None):
        return SimpleNamespace(pregunta='Cómo reviso el inventario', historial=[], pagina='/panel/equipos', filtros={}, conversacion_id=identificador)

    async def test_persistencia_propiedad_borrado_y_limite_quince(self):
        with patch.object(chats.chatbot_service, 'responder', new=AsyncMock(return_value={'disponible': True, 'texto': 'Consulta el inventario.', 'fuentes': [], 'uso': {'total': 50}})) as modelo:
            primera = await chats.consultar(self.pregunta(), self.usuario)
            identificador = primera['conversacion_id']
            for _ in range(14):
                await chats.consultar(self.pregunta(identificador), self.usuario)
            with self.assertRaises(Validacion):
                await chats.consultar(self.pregunta(identificador), self.usuario)
            self.assertEqual(modelo.await_count, 15)
            self.assertEqual(len(modelo.call_args.args[1]), 6)
        await close_connections()
        guardado = await chats.obtener(identificador, self.usuario)
        self.assertEqual(len(guardado['mensajes']), 30)
        self.assertEqual(guardado['consumo'], {'consultas': 15, 'tokens': 750, 'conTokens': 15})
        self.assertEqual((await chats.listar(self.otro))['items'], [])
        with self.assertRaises(NoEncontrado):
            await chats.obtener(identificador, self.otro)
        with self.assertRaises(NoEncontrado):
            await chats.eliminar(identificador, self.otro)
        await chats.eliminar(identificador, self.usuario)
        self.assertEqual((await chats.listar(self.usuario))['items'], [])

    async def test_dos_pestanas_no_reservan_a_la_vez(self):
        identificador = (await chats.crear(self.usuario))['id']
        iniciada, terminar = asyncio.Event(), asyncio.Event()
        async def proveedor(*args, **kwargs):
            iniciada.set()
            await terminar.wait()
            return {'disponible': True, 'texto': 'Respuesta.', 'fuentes': []}
        with patch.object(chats.chatbot_service, 'responder', side_effect=proveedor):
            pendiente = asyncio.create_task(chats.consultar(self.pregunta(identificador), self.usuario))
            try:
                await asyncio.wait_for(iniciada.wait(), timeout=5)
                with self.assertRaises(Conflicto):
                    await chats.consultar(self.pregunta(identificador), self.usuario)
            finally:
                terminar.set()
                await pendiente
        self.assertEqual((await chats.obtener(identificador, self.usuario))['consumo']['consultas'], 1)

    async def test_tokens_confirmados_se_guardan_aunque_falle_la_respuesta_final(self):
        with patch.object(chats.chatbot_service, 'responder', new=AsyncMock(return_value={'disponible': False, 'texto': 'Cuota temporalmente agotada.', 'fuentes': [], 'uso': {'total': 120}})):
            fallida = await chats.consultar(self.pregunta(), self.usuario)
        identificador = fallida['conversacion_id']
        guardada = await chats.obtener(identificador, self.usuario)
        self.assertEqual(guardada['consumo'], {'consultas': 1, 'tokens': 120, 'conTokens': 1})
        self.assertEqual(guardada['mensajes'], [])
        with patch.object(chats.chatbot_service, 'responder', new=AsyncMock(return_value={'disponible': True, 'texto': 'Respuesta recuperada.', 'fuentes': [], 'uso': {'total': 30}})):
            await chats.consultar(self.pregunta(identificador), self.usuario)
        guardada = await chats.obtener(identificador, self.usuario)
        self.assertEqual(guardada['consumo'], {'consultas': 2, 'tokens': 150, 'conTokens': 2})
        self.assertEqual(len(guardada['mensajes']), 2)

    async def test_borrado_durante_respuesta_no_recrea_documento(self):
        identificador = (await chats.crear(self.usuario))['id']
        async def proveedor(*args, **kwargs):
            await chats.eliminar(identificador, self.usuario)
            return {'disponible': True, 'texto': 'Respuesta.', 'fuentes': []}
        with patch.object(chats.chatbot_service, 'responder', side_effect=proveedor):
            await chats.consultar(self.pregunta(identificador), self.usuario)
        self.assertEqual((await chats.listar(self.usuario))['items'], [])
