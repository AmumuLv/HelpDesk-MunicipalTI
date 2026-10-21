import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import analitica_chat as servicio


class PresentacionAnalisisTest(unittest.IsolatedAsyncioTestCase):
    async def test_ayuda_funcional_no_consume_modelo_ni_consulta_registros(self):
        with patch.object(servicio.ia_provider, 'obtener_proveedor') as proveedor, patch.object(servicio, 'get_db') as db:
            respuesta = await servicio.responder('¿Para qué sirve este asistente?', usuario={'rol': 'tecnico'})
        self.assertIn('sin gastar tokens de Groq', respuesta['texto'])
        self.assertEqual(respuesta['fuentes'], ['guia_analisis'])
        self.assertIsNone(respuesta['periodo'])
        proveedor.assert_not_called()
        db.assert_not_called()

    def test_reconoce_explicaciones_y_no_intercepta_consultas_de_datos(self):
        from app.services.ayuda_analisis import responder_ayuda
        for pregunta in ['Hola', 'Gracias', '¿Qué es el SLA?', '¿Qué significa el porcentaje de datos faltantes?', '¿Usas tokens de Groq?', '¿Puedes eliminar equipos?']:
            self.assertTrue(responder_ayuda(pregunta), pregunta)
        self.assertIsNone(responder_ayuda('¿Qué oficina tiene más incidencias?'))
    def test_oficinas_destaca_resultado_fechas_y_tabla(self):
        texto, _, detalle = servicio._formatear('ranking_oficinas', {'periodo': {'desde': '2026-10-01', 'hasta': '2026-10-20'}, 'top': [{'oficina': 'Soporte TI', 'total': 30, 'por_equipo': 1.76, 'por_usuario': 2}, {'oficina': 'Caja', 'total': 1}]})
        self.assertTrue(texto.startswith('Soporte TI registra 30 tickets'))
        self.assertIn('01/10/2026', texto)
        self.assertNotIn('2026-10-', texto)
        self.assertEqual(len(detalle['tabla']['filas']), 2)

    def test_empates_no_inventan_un_lider_unico(self):
        texto, _, _ = servicio._formatear('ranking_oficinas', {'periodo': {'desde': '2026-10-01', 'hasta': '2026-10-20'}, 'top': [{'oficina': 'Caja', 'total': 5}, {'oficina': 'Archivo', 'total': 5}]})
        self.assertIn('comparten el primer lugar', texto)

    def test_zonas_incluye_comparacion_y_oficina_principal(self):
        texto, _, detalle = servicio._formatear('ranking_zonas', {'periodo': ['2026-10-01', '2026-10-20'], 'zonas': [{'zona': 'Palacio', 'total': 31, 'abiertos': 10, 'oficinas': [{'oficina': 'Soporte TI', 'total': 30}]}]})
        self.assertIn('Palacio concentra 31 tickets', texto)
        self.assertIn('Soporte TI', texto)
        self.assertEqual(detalle['tabla']['columnas'][1]['clave'], 'total')

    def test_familias_muestra_porcentaje_y_no_predice(self):
        texto, _, detalle = servicio._formatear('equipos_con_fallas', {'familias': [{'tipo': 'Monitor', 'tickets_12m': 10, 'activos': 2, 'tickets_por_equipo': 5, 'nivel': 'alto', 'suficiente_datos': False, 'tasa_falla': 0.5}]})
        self.assertIn('No es una predicción futura', texto)
        self.assertEqual(detalle['tabla']['filas'][0]['porcentaje_afectados'], 50)

    async def test_pregunta_reconocida_no_llama_proveedor_externo(self):
        proveedor = MagicMock()
        proveedor.disponible = AsyncMock()
        proveedor.completar = AsyncMock()
        with patch.object(servicio, 'get_db'), patch.object(servicio.ia_provider, 'obtener_proveedor', return_value=proveedor), patch.object(servicio, 'ejecutar_herramienta', new=AsyncMock(return_value={'periodo': {'desde': '2026-10-01', 'hasta': '2026-10-20'}, 'top': [{'oficina': 'Archivo', 'total': 2}]})), patch.object(servicio, 'ia_service_registrar', new=AsyncMock()):
            resultado = await servicio.responder('Qué oficina tiene más incidencias', usuario={'rol': 'administrador'})
        self.assertIn('Archivo', resultado['texto'])
        proveedor.disponible.assert_not_awaited()
        proveedor.completar.assert_not_awaited()
