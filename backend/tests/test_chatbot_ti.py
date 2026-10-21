import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core.errors import Prohibido
from app.services import chatbot_service as servicio


class ChatbotTITest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        proveedor = patch.object(servicio.settings, 'chatbot_provider', 'gemini')
        proveedor.start()
        self.addCleanup(proveedor.stop)
        permisos = patch.object(servicio, 'tiene_permiso', return_value=False)
        permisos.start()
        self.addCleanup(permisos.stop)

    async def test_usuario_no_accede_incluso_sin_clave(self):
        with self.assertRaises(Prohibido):
            servicio.estado({'rol': 'usuario'})
        with self.assertRaises(Prohibido):
            await servicio.responder('Hola', [], {'rol': 'usuario'})

    async def test_sin_clave_no_llama_proveedor(self):
        with patch.object(servicio.settings, 'gemini_api_key', ''), patch.object(servicio.httpx, 'AsyncClient') as cliente:
            respuesta = await servicio.responder('Hola', [], {'rol': 'tecnico'})
            self.assertFalse(respuesta['disponible'])
            cliente.assert_not_called()

    async def test_gemini_no_recibe_herramientas_ni_clave_en_url(self):
        cliente = AsyncMock()
        cliente.post.return_value = httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': 'Consulta la ficha del conjunto.'}]}}], 'usageMetadata': {'promptTokenCount': 20, 'candidatesTokenCount': 30, 'thoughtsTokenCount': 12, 'totalTokenCount': 62}})
        contexto = MagicMock()
        contexto.__aenter__ = AsyncMock(return_value=cliente)
        contexto.__aexit__ = AsyncMock(return_value=False)
        with patch.object(servicio.settings, 'gemini_api_key', 'clave-ficticia'), patch.object(servicio.httpx, 'AsyncClient', return_value=contexto), patch.object(servicio.analitica_chat, '_detectar_intencion', return_value=(None, {})):
            respuesta = await servicio.responder('Como veo un historial', [SimpleNamespace(rol='user', texto='Hola')], {'rol': 'tecnico', 'permisos': []})
        self.assertTrue(respuesta['disponible'])
        self.assertEqual(respuesta['uso'], {'entrada': 20, 'salida': 30, 'razonamiento': 12, 'total': 62})
        argumentos = cliente.post.call_args
        self.assertNotIn('clave-ficticia', argumentos.args[0])
        self.assertNotIn('tools', argumentos.kwargs['json'])
        self.assertEqual(argumentos.kwargs['headers']['x-goog-api-key'], 'clave-ficticia')
        self.assertEqual(argumentos.kwargs['json']['contents'][-1]['parts'][0]['text'], 'Como veo un historial')

    async def test_consulta_sin_permiso_no_obtiene_datos(self):
        with patch.object(servicio.settings, 'gemini_api_key', 'clave-ficticia'), patch.object(servicio.settings, 'gemini_model', 'modelo/invalido'), patch.object(servicio.analitica_chat, '_detectar_intencion', return_value=('ranking_oficinas', {})), patch.object(servicio.analitica_chat, '_permitida', return_value=False), patch.object(servicio.analitica_chat, 'ejecutar_herramienta', new=AsyncMock()) as consultar:
            respuesta = await servicio.responder('Que oficina tiene mas tickets', [], {'rol': 'tecnico', 'permisos': []})
            self.assertFalse(respuesta['disponible'])
            consultar.assert_not_called()

    async def test_error_cuota_no_revela_respuesta_del_proveedor(self):
        cliente = AsyncMock()
        cliente.post.return_value = httpx.Response(429, json={'error': {'message': 'detalle privado'}})
        contexto = MagicMock()
        contexto.__aenter__ = AsyncMock(return_value=cliente)
        contexto.__aexit__ = AsyncMock(return_value=False)
        with patch.object(servicio.settings, 'gemini_api_key', 'clave-ficticia'), patch.object(servicio.httpx, 'AsyncClient', return_value=contexto), patch.object(servicio.analitica_chat, '_detectar_intencion', return_value=(None, {})):
            respuesta = await servicio.responder('Como veo el historial', [], {'rol': 'tecnico', 'permisos': []})
        self.assertFalse(respuesta['disponible'])
        self.assertNotIn('detalle privado', respuesta['texto'])

    def test_tokens_ausentes_no_se_presentan_como_saldo(self):
        self.assertIsNone(servicio.uso_tokens({}))

    def test_contexto_acotado_conoce_calidad_y_conjuntos(self):
        from app.services.conocimiento_proyecto import contexto_proyecto
        texto = contexto_proyecto('Qué significa el porcentaje de calidad', [])
        self.assertIn('faltantes 0%', texto)
        self.assertIn('completitud 100%', texto)
        self.assertIn('dispositivos independientes', texto)
        self.assertIn('Ámbito exclusivo', texto)
        self.assertIn('Una portada oficial no verifica una norma', texto)
        self.assertNotIn('Mis asignaciones', texto)

    def test_contexto_recupera_tema_del_historial(self):
        from app.services.conocimiento_proyecto import contexto_proyecto
        texto = contexto_proyecto('Y cómo funciona eso', [SimpleNamespace(rol='user', texto='Consultar el SLA de tickets')])
        self.assertIn('SLA visible en la bandeja', texto)
        self.assertIn('descripción original', texto)

    async def test_normas_distinguen_referencias_de_contenido_verificado(self):
        with patch.object(servicio.settings, 'chatbot_provider', 'groq'), patch.object(servicio.settings, 'groq_api_key', 'ficticia'), patch.object(servicio.analitica_chat, '_detectar_intencion', return_value=(None, {})), patch('app.services.contexto_municipal_service.informacion_oficial', new=AsyncMock(return_value='')), patch.object(servicio, 'responder_groq', new=AsyncMock(return_value={'disponible': True})) as proveedor:
            await servicio.responder('Qué normativa municipal aplica en Perú', [], {'rol': 'tecnico'})
        instruccion, _, _, fuentes = proveedor.call_args.args
        self.assertIn('NO contenido de normas verificado', instruccion)
        self.assertIn('No fue posible verificar', instruccion)
        self.assertTrue(any('elperuano' in f['ruta'] for f in fuentes))

    async def test_groq_contexto_tokens_y_sin_herramientas(self):
        cliente = AsyncMock()
        cliente.post.return_value = httpx.Response(200, json={'choices': [{'message': {'content': 'Revisa el historial del conjunto.'}}], 'usage': {'prompt_tokens': 30, 'completion_tokens': 15, 'total_tokens': 45}})
        contexto = MagicMock()
        contexto.__aenter__ = AsyncMock(return_value=cliente)
        contexto.__aexit__ = AsyncMock(return_value=False)
        with patch.object(servicio.settings, 'chatbot_provider', 'groq'), patch.object(servicio.settings, 'groq_api_key', 'clave-ficticia'), patch.object(servicio.httpx, 'AsyncClient', return_value=contexto), patch.object(servicio.analitica_chat, '_detectar_intencion', return_value=(None, {})):
            respuesta = await servicio.responder('Como veo el historial', [SimpleNamespace(rol='user', texto='Hola')], {'rol': 'tecnico'})
        self.assertTrue(respuesta['disponible'])
        self.assertEqual(respuesta['uso']['total'], 45)
        llamada = cliente.post.call_args
        self.assertEqual(llamada.args[0], 'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(llamada.kwargs['headers']['Authorization'], 'Bearer clave-ficticia')
        cuerpo = llamada.kwargs['json']
        self.assertEqual(cuerpo['model'], 'openai/gpt-oss-20b')
        self.assertEqual(cuerpo['tools'][0]['function']['name'], 'consultar_sistema')
        self.assertFalse(cuerpo['include_reasoning'])
        self.assertIn('No puedes crear, editar, eliminar', cuerpo['messages'][0]['content'])

    async def test_groq_sin_clave_no_recurre_a_gemini(self):
        with patch.object(servicio.settings, 'chatbot_provider', 'groq'), patch.object(servicio.settings, 'groq_api_key', ''), patch.object(servicio.httpx, 'AsyncClient') as cliente:
            respuesta = await servicio.responder('Hola', [], {'rol': 'tecnico'})
            self.assertFalse(respuesta['disponible'])
            cliente.assert_not_called()

    async def test_groq_cuota_no_revela_detalles_privados(self):
        cliente = AsyncMock()
        cliente.post.return_value = httpx.Response(429, json={'error': {'message': 'secreto-del-proveedor'}})
        contexto = MagicMock()
        contexto.__aenter__ = AsyncMock(return_value=cliente)
        contexto.__aexit__ = AsyncMock(return_value=False)
        with patch.object(servicio.httpx, 'AsyncClient', return_value=contexto):
            respuesta = await servicio.responder_groq('Guía', 'Hola', [], [])
        self.assertFalse(respuesta['disponible'])
        self.assertNotIn('secreto-del-proveedor', respuesta['texto'])

    async def test_facturacion_y_saturacion_no_se_confunden_con_cuota(self):
        for codigo, esperado in [(402, 'facturación'), (429, 'solicitudes o tokens'), (503, 'saturado'), (500, 'fallo temporal')]:
            with self.subTest(codigo=codigo):
                cliente = AsyncMock()
                cliente.post.return_value = httpx.Response(codigo, json={'error': {'message': 'detalle privado del proveedor'}})
                contexto = MagicMock()
                contexto.__aenter__ = AsyncMock(return_value=cliente)
                contexto.__aexit__ = AsyncMock(return_value=False)
                with patch.object(servicio.settings, 'gemini_api_key', 'clave-ficticia'), patch.object(servicio.httpx, 'AsyncClient', return_value=contexto), patch.object(servicio.analitica_chat, '_detectar_intencion', return_value=(None, {})):
                    respuesta = await servicio.responder('Hola', [], {'rol': 'tecnico', 'permisos': []})
                self.assertFalse(respuesta['disponible'])
                self.assertIn(esperado, respuesta['texto'])
                self.assertNotIn('detalle privado', respuesta['texto'])
                if codigo == 402:
                    self.assertNotIn('límite', respuesta['texto'])

    def test_contexto_publico_no_incluye_scripts(self):
        from app.services.contexto_municipal_service import TextoPublico
        parser = TextoPublico()
        parser.feed('<h1>Municipalidad de Casma</h1><script>no incluir</script><p>Servicios municipales</p>')
        self.assertEqual(parser.textos, ['Municipalidad de Casma', 'Servicios municipales'])
