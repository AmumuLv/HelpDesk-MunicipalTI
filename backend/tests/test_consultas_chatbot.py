import json
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from bson import ObjectId

from app.core.errors import Prohibido
from app.services import consultas_chatbot as consultas
from app.services import chatbot_service as chat


class ConsultasChatbotTest(unittest.IsolatedAsyncioTestCase):
    def test_total_equipos_usa_el_total_no_la_muestra_y_admite_cero(self):
        for total in (0, 1, 280):
            with self.subTest(total=total):
                texto = consultas.resumen_total_equipos({'recurso': 'equipos', 'total': total, 'items': [{'nombre': 'Muestra'}]}, 'Cuántos equipos activos hay registrados')
                self.assertIn(f'**{total} equipo', texto)

    def test_total_equipos_no_sustituye_listados_filtros_o_permisos(self):
        datos = {'recurso': 'equipos', 'total': 28}
        for pregunta in ('Cuántos equipos hay y cuáles son sus nombres', 'Cuántos equipos hay por oficina', 'Cuántos equipos hay con 8 GB de RAM', 'Cuántos equipos hay y cuántos usuarios', 'Cuántos equipos hay este mes', 'Cuántos equipos hay obsoletos', 'Cuántos equipos hay dados de baja', 'Cuántos equipos hay registrados en 2026', 'Cuántos equipos hay por sistema', 'Cuántos equipos hay no activos'):
            with self.subTest(pregunta=pregunta):
                self.assertIsNone(consultas.resumen_total_equipos(datos, pregunta))
        for variante in ({**datos, 'error': 'Acceso denegado'}, {**datos, 'recurso': 'usuarios'}, {**datos, 'total': True}, {**datos, 'total': -1}):
            self.assertIsNone(consultas.resumen_total_equipos(variante, 'Cuántos equipos hay'))
        self.assertIn('28 equipos', consultas.resumen_total_equipos(datos, 'Consulta el inventario actual y dime exactamente cuántos equipos activos hay registrados. Necesito el total real, no una estimación.'))

    async def test_conteo_simple_evita_segunda_llamada_groq_y_conserva_uso(self):
        primera = httpx.Response(200, json={
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
            'choices': [{'message': {'content': None, 'tool_calls': [{'id': 'lectura', 'type': 'function', 'function': {'name': 'consultar_sistema', 'arguments': json.dumps({'recurso': 'equipos'})}}]}}],
        }, request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions'))
        cliente = MagicMock()
        cliente.post = AsyncMock(return_value=primera)
        contexto = MagicMock()
        contexto.__aenter__ = AsyncMock(return_value=cliente)
        contexto.__aexit__ = AsyncMock(return_value=False)
        with patch.object(chat.settings, 'groq_model', 'openai/gpt-oss-20b'), patch.object(chat.settings, 'groq_api_key', 'clave-ficticia'), patch.object(chat.httpx, 'AsyncClient', return_value=contexto), patch.object(consultas, 'ejecutar_seguro', new=AsyncMock(return_value={'recurso': 'equipos', 'total': 280, 'items': []})):
            respuesta = await chat.responder_groq('Solo lectura', 'Cuántos equipos activos hay registrados', [], [], usuario={'rol': 'administrador'})
        self.assertTrue(respuesta['disponible'])
        self.assertIn('280 equipos', respuesta['texto'])
        self.assertEqual(respuesta['uso']['total'], 120)
        self.assertTrue(respuesta['fuentes'])
        cliente.post.assert_awaited_once()

    async def test_fallo_en_segunda_ronda_conserva_los_tokens_ya_confirmados(self):
        peticion = httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')
        primera = httpx.Response(200, json={
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
            'choices': [{'message': {'content': None, 'tool_calls': [{'id': 'lectura', 'type': 'function', 'function': {'name': 'consultar_sistema', 'arguments': json.dumps({'recurso': 'equipos'})}}]}}],
        }, request=peticion)
        for fallo in (httpx.Response(429, json={'error': 'detalle-privado'}, request=peticion), httpx.ConnectError('detalle-privado', request=peticion)):
            with self.subTest(fallo=type(fallo).__name__):
                cliente = MagicMock()
                cliente.post = AsyncMock(side_effect=[primera, fallo])
                contexto = MagicMock()
                contexto.__aenter__ = AsyncMock(return_value=cliente)
                contexto.__aexit__ = AsyncMock(return_value=False)
                with patch.object(chat.settings, 'groq_model', 'openai/gpt-oss-20b'), patch.object(chat.settings, 'groq_api_key', 'clave-ficticia'), patch.object(chat.httpx, 'AsyncClient', return_value=contexto), patch.object(consultas, 'ejecutar_seguro', new=AsyncMock(return_value={'recurso': 'equipos', 'total': 28, 'items': []})):
                    respuesta = await chat.responder_groq('Solo lectura', 'Lista los equipos y recomienda una mejora', [], [], usuario={'rol': 'administrador'})
                self.assertFalse(respuesta['disponible'])
                self.assertEqual(respuesta['uso']['total'], 120)
                self.assertNotIn('detalle-privado', respuesta['texto'])
                self.assertEqual(cliente.post.await_count, 2)

    def test_ranking_no_se_deduce_de_muestra_ni_inventa_estado(self):
        resultado = consultas.ajustar_intencion({'recurso': 'tickets', 'estado': 'cerrado'}, 'Qué equipo tuvo más incidencias entre el 15 y el 20 de octubre')
        self.assertEqual(resultado, {'recurso': 'ranking_equipos'})
        resultado = consultas.ajustar_intencion({'recurso': 'tickets', 'estado': 'cerrado'}, 'Cuántos tickets cerrados hay')
        self.assertEqual(resultado['estado'], 'cerrado')

    def test_resumen_ranking_conserva_cifras_y_casos_sin_vinculo(self):
        texto = consultas.resumen_ranking_equipos({'desde': date(2026, 10, 15), 'hasta': date(2026, 10, 20), 'total_tickets': 31, 'sin_vinculo': 26, 'items': [{'nombre': 'CPU prueba', 'total': 2}]})
        self.assertIn('15/10/2026', texto)
        self.assertIn('26 no tienen equipo', texto)
        self.assertIn('**2**', texto)
        self.assertNotIn('cerrado', texto)
    def base(self):
        coleccion = MagicMock()
        coleccion.count_documents = AsyncMock(return_value=12)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = cursor
        cursor.max_time_ms.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[])
        coleccion.find.return_value = cursor
        coleccion.aggregate = AsyncMock(return_value=cursor)
        db = MagicMock()
        db.__getitem__.return_value = coleccion
        return db, coleccion

    async def test_ranking_incluye_dias_completos_lima_y_excluye_eliminados(self):
        db, coleccion = self.base()
        with patch.object(consultas, 'get_db', return_value=db):
            resultado = await consultas.consultar({'recurso': 'ranking_equipos', 'desde': '2026-10-15', 'hasta': '2026-10-20'}, {'rol': 'administrador'})
        pipeline = coleccion.aggregate.call_args.args[0]
        filtro = pipeline[0]['$match']['$and'][0]
        self.assertEqual(filtro['eliminado'], {'$ne': True})
        self.assertEqual(filtro['creado_en']['$gte'], datetime(2026, 10, 15, 5, tzinfo=timezone.utc))
        self.assertEqual(filtro['creado_en']['$lte'].day, 21)
        self.assertEqual(filtro['creado_en']['$lte'].hour, 4)
        self.assertEqual(pipeline[1]['$group']['_id'], '$activo_id')
        self.assertEqual(resultado['total_tickets'], 12)
        self.assertIn('sin_vinculo', resultado)
        coleccion.insert_one.assert_not_called()
        coleccion.update_one.assert_not_called()

    async def test_rechaza_colecciones_arbitrarias_y_operadores(self):
        db, coleccion = self.base()
        with patch.object(consultas, 'get_db', return_value=db):
            for argumentos in [{'recurso': 'sesiones'}, {'recurso': 'usuarios', '$where': 'robar()'}, {'recurso': 'tickets', 'desde': '2026-10-20', 'hasta': '2026-10-15'}]:
                resultado = await consultas.ejecutar_seguro(argumentos, {'rol': 'administrador'})
                self.assertIn('error', resultado)
        coleccion.find.assert_not_called()

    async def test_proyeccion_personas_excluye_credenciales_y_datos_de_contacto(self):
        db, coleccion = self.base()
        with patch.object(consultas, 'get_db', return_value=db):
            await consultas.consultar({'recurso': 'usuarios', 'consulta': '.*'}, {'rol': 'administrador'})
        filtro, proyeccion = coleccion.find.call_args.args
        self.assertEqual(filtro['$or'][0]['nombre']['$regex'], r'\.\*')
        self.assertEqual(set(proyeccion), {'nombre', 'rol', 'cargo', 'oficina_nombre', 'zona_nombre'})

    async def test_permiso_denegado_no_consulta_registros(self):
        db, coleccion = self.base()
        with patch.object(consultas, 'get_db', return_value=db), patch.object(consultas, 'tiene_permiso', return_value=False):
            resultado = await consultas.ejecutar_seguro({'recurso': 'equipos'}, {'rol': 'tecnico'})
        self.assertIn('error', resultado)
        coleccion.find.assert_not_called()
        with self.assertRaises(Prohibido):
            await consultas.consultar({'recurso': 'tickets'}, {'rol': 'usuario'})

    async def test_hereda_fechas_visibles_y_pregunta_puede_anularlas(self):
        db, coleccion = self.base()
        pagina = {'desde': '2026-10-01', 'hasta': '2026-10-20', 'oficina_id': str(ObjectId())}
        with patch.object(consultas, 'get_db', return_value=db):
            resultado = await consultas.consultar({'recurso': 'tickets'}, {'rol': 'administrador'}, pagina)
            self.assertEqual(resultado['desde'], date(2026, 10, 1))
            self.assertIn('oficina_id', coleccion.find.call_args.args[0])
            resultado = await consultas.consultar({'recurso': 'tickets', 'desde': '2026-10-19', 'hasta': '2026-10-19', 'usar_filtros_pagina': False}, {'rol': 'administrador'}, pagina)
        self.assertEqual(resultado['desde'], date(2026, 10, 19))
        self.assertNotIn('oficina_id', coleccion.find.call_args.args[0])

    def test_fechas_y_entidades_visibles_conservan_codigo(self):
        self.assertEqual(chat.texto_presentable('Hoy 2026-10-20. &#x20;```\n2026-10-20\n```'), 'Hoy 20/10/2026.  ```\n2026-10-20\n```')
        self.assertNotIn('gsk_', consultas.datos_json({'nombre': 'gsk_01234567890123456789'}))

    async def test_tool_call_lee_datos_suma_tokens_y_no_ejecuta_escrituras(self):
        cliente = AsyncMock()
        cliente.post.side_effect = [
            httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'lectura1', 'type': 'function', 'function': {'name': 'consultar_sistema', 'arguments': json.dumps({'recurso': 'ranking_equipos', 'desde': '2026-10-15', 'hasta': '2026-10-20'})}}]}}], 'usage': {'total_tokens': 50}}),
            httpx.Response(200, json={'choices': [{'message': {'content': 'Del 2026-10-15 al 2026-10-20: Impresora, 5 tickets.'}}], 'usage': {'total_tokens': 30}}),
        ]
        contexto = MagicMock()
        contexto.__aenter__ = AsyncMock(return_value=cliente)
        contexto.__aexit__ = AsyncMock(return_value=False)
        with patch.object(chat.httpx, 'AsyncClient', return_value=contexto), patch.object(consultas, 'ejecutar_seguro', new=AsyncMock(return_value={'items': [{'nombre': 'Impresora', 'total': 5}]})) as lectura:
            respuesta = await chat.responder_groq('Solo lectura', 'Consulta un resumen del periodo', [], [], usuario={'rol': 'administrador'})
        lectura.assert_awaited_once()
        self.assertEqual(respuesta['uso']['total'], 80)
        self.assertIn('15/10/2026', respuesta['texto'])
        self.assertEqual(cliente.post.await_count, 2)
        self.assertEqual(cliente.post.call_args.kwargs['json']['messages'][-1]['role'], 'tool')
