import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import analisis_consultas as consultas, analitica_chat as chat


class LecturaAnalisisTest(unittest.IsolatedAsyncioTestCase):
    def test_intenciones_nuevas_sin_confundir_personas_o_definiciones(self):
        for pregunta, esperado in [
            ('¿Puedes darme un resumen del servicio?', 'metricas_generales'),
            ('¿Hay más tickets que en el periodo anterior?', 'comparacion_periodos'),
            ('¿Cuántos tickets están abiertos y cerrados?', 'estados_tickets'),
            ('¿Qué tickets tienen el plazo vencido?', 'plazos_atencion'),
            ('¿Cómo evolucionan los tickets por día?', 'evolucion_tickets'),
            ('¿Cuántos equipos tenemos registrados?', 'resumen_inventario'),
            ('Tickets de Ana Prueba', 'tickets_de_usuario'),
        ]:
            self.assertEqual(chat._detectar_intencion(pregunta)[0], esperado, pregunta)
        self.assertIsNone(consultas.detectar('¿Qué significa el tiempo promedio?'))

    def test_cero_anterior_no_inventa_porcentaje_y_fechas_son_legibles(self):
        datos = {'tickets_analizados': 5, 'tickets_periodo_anterior': 0, 'cerrados': 2,
                 'periodo': {'desde': '2026-10-01', 'hasta': '2026-10-03'},
                 'anterior': {'desde': '2026-09-28', 'hasta': '2026-09-30'}}
        texto, tabla = consultas.formatear('comparacion_periodos', datos)
        self.assertIn('No calculo una variación porcentual', texto)
        self.assertIn('28/09/2026', texto)
        self.assertEqual([f['total'] for f in tabla['filas']], [5, 0])

    def test_contexto_solo_guarda_argumentos_admitidos(self):
        fuente, argumentos = consultas.contexto_anterior([{'rol': 'assistant', 'contexto_consulta': {
            'herramienta': 'metricas_generales', 'argumentos': {'indicador': 'satisfaccion', '$where': 'no', 'nombre': {'$ne': None}},
        }}])
        self.assertEqual(fuente, 'metricas_generales')
        self.assertEqual(argumentos, {'indicador': 'satisfaccion'})
        self.assertTrue(consultas.es_continuacion('¿Y el mes pasado?'))
        self.assertFalse(consultas.es_continuacion('Elimina los tickets de ayer'))

    def test_ubicacion_imprecisa_no_se_convierte_en_total_global(self):
        from app.core.errors import Validacion
        with self.assertRaises(Validacion):
            consultas.exigir_ubicacion_explicita('Cuántos tickets hay en Tesorería')
        consultas.exigir_ubicacion_explicita('Cuántos tickets hay en la oficina Tesorería')
        consultas.exigir_ubicacion_explicita('Qué oficina tiene más incidencias en el periodo seleccionado')

    async def test_continuacion_reutiliza_consulta_sin_llamar_proveedor(self):
        proveedor = MagicMock()
        proveedor.disponible = AsyncMock()
        with patch.object(chat, 'get_db'), patch.object(chat.ia_provider, 'obtener_proveedor', return_value=proveedor), patch.object(chat, 'ejecutar_herramienta', new=AsyncMock(return_value={'items': []})) as ejecutar, patch.object(chat, 'ia_service_registrar', new=AsyncMock()):
            resultado = await chat.responder('¿Y el mes pasado?', usuario={'rol': 'administrador'}, historial=[{'rol': 'assistant', 'fuentes': ['estados_tickets']}])
        self.assertEqual(resultado['fuentes'], ['estados_tickets'])
        self.assertEqual(ejecutar.call_args.kwargs['filtros']['periodo'], 'mes_anterior')
        proveedor.disponible.assert_not_awaited()

    async def test_continuacion_no_evade_autorizacion(self):
        from app.core.errors import Prohibido
        with self.assertRaises(Prohibido):
            await chat.responder('¿Y ayer?', usuario={'rol': 'usuario'}, historial=[{'rol': 'assistant', 'fuentes': ['metricas_generales']}])

    async def test_no_presenta_familias_globales_como_datos_de_una_oficina(self):
        from app.core.errors import Validacion
        with patch.object(chat.analisis_consultas, 'resolver_ubicacion', new=AsyncMock(return_value=({'oficina_id': 'oficina'}, 'Oficina: Prueba'))), patch.object(chat, 'ejecutar_herramienta', new=AsyncMock()) as ejecutar:
            with self.assertRaises(Validacion):
                await chat.responder('Qué familias de equipos tienen más fallas en la oficina Prueba', usuario={'rol': 'administrador'})
            ejecutar.assert_not_awaited()

    def test_graficas_diarias_no_se_presentan_como_pronosticos_y_respetan_empates(self):
        texto, tabla = consultas.formatear('evolucion_tickets', {'total_periodo': 4, 'serie': [{'fecha': '2026-10-01', 'valor': 2}, {'fecha': '2026-10-02', 'valor': 2}]})
        self.assertIn('no hay un único día líder', texto)
        self.assertEqual(len(tabla['filas']), 2)
        self.assertIn('historial observado', consultas.lectura('evolucion_tickets')['limite'])
