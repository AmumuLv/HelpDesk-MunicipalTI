import unittest
from unittest.mock import AsyncMock, patch

from app.services.categorias_ticket_service import categoria_reporte, categorias_activas
from app.services.presentacion_ticket import CATEGORIA_POR_TIPO


class CategoriasReporteTest(unittest.IsolatedAsyncioTestCase):
    async def test_catalogo_excluye_inactivos(self):
        with patch('app.services.catalogo_service.listar_detallado', new=AsyncMock(return_value=[
            {'valor': 'Hardware', 'activo': True},
            {'valor': 'Impresora', 'activo': False},
        ])):
            self.assertEqual(await categorias_activas(), ['Hardware'])

    def test_botones_solo_asignan_categorias_del_catalogo(self):
        categorias = list(set(CATEGORIA_POR_TIPO.values())) + ['Formateo', 'Correo / Cuenta', 'Otros']
        for tipo, categoria in CATEGORIA_POR_TIPO.items():
            self.assertEqual(categoria_reporte(tipo, '', categorias), categoria)
            self.assertIsNone(categoria_reporte(tipo, '', []))
        self.assertEqual(categoria_reporte('Sistema/programa', 'Necesito formatear', categorias), 'Formateo')
        self.assertEqual(categoria_reporte('Otro', 'Mi correo no abre', categorias), 'Correo / Cuenta')
        self.assertIsNone(categoria_reporte('Sistema/programa', 'Formatear', ['Hardware']))
        self.assertEqual(categoria_reporte('Impresora', '', ['IMPRESORA']), 'IMPRESORA')
        self.assertEqual(categoria_reporte('Otro', 'Algo falla', categorias), 'Otros')
