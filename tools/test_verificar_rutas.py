"""Regresiones del análisis estático de rutas, sin acceder a la base de datos."""
import unittest

from verificar_rutas import LLAMADA, alternativas, norm


class RutasTest(unittest.TestCase):
    def test_filtros_y_encadenamiento_opcional(self):
        self.assertEqual(norm('/tickets${consulta({ estado, pagina: 1 })}'), '/tickets')
        self.assertEqual(norm('/zonas/${borrando?.id}/borrado'), '/zonas/{x}/borrado')
        self.assertEqual(norm('/api/tickets/{ticket_id}?pagina=1'), '/tickets/{x}')

    def test_ambas_ramas_del_tipo_de_organizacion(self):
        llamada = "api.editar(`/${edicion.tipo === 'zona' ? 'zonas' : 'oficinas'}/${edicion.id}`, {})"
        helper, literal = LLAMADA.findall(llamada)[0]
        self.assertEqual(helper, 'editar')
        self.assertEqual([norm(r) for r in alternativas(literal[1:-1])], ['/zonas/{x}', '/oficinas/{x}'])

    def test_no_oculta_rutas_ni_verbos_distintos(self):
        self.assertNotEqual(norm('/no-existe/${id}'), norm('/tickets/${id}'))
        self.assertEqual(LLAMADA.findall("api.borrar('/tickets/abc')"), [('borrar', "'/tickets/abc'")])


if __name__ == '__main__':
    unittest.main()
