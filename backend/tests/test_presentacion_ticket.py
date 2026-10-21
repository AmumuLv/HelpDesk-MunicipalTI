import unittest

from app.services.presentacion_ticket import titulo_reporte


class PresentacionTicketTest(unittest.TestCase):
    def test_titulos_para_todas_las_opciones(self):
        casos = [
            ('Sistema/programa', 'Necesito instalar Office en mi equipo', 'Instalación de Office'),
            ('Sistema/programa', 'Necesito formatear la computadora', 'Solicitud de formateo del equipo'),
            ('SIGA/Casita/Servidor', 'No puedo entrar a SIGA desde ayer', 'No se puede acceder a SIGA'),
            ('Carpeta compartida', 'No abre la carpeta compartida', 'No se puede abrir la carpeta compartida'),
            ('Impresora', 'Se atascó la hoja al imprimir', 'Papel atascado en la impresora'),
            ('Huella dactilar', 'El lector no reconoce mi huella', 'El lector no reconoce la huella'),
            ('Internet/red', 'No hay internet en mi computadora', 'Sin conexión a internet'),
            ('No enciende', 'Mi computadora no prende desde ayer', 'El equipo no enciende'),
            ('Otro', 'Necesito cambiar mi contraseña de acceso', 'Solicitud de restablecimiento de contraseña'),
        ]
        for tipo, descripcion, titulo in casos:
            with self.subTest(tipo=tipo, descripcion=descripcion):
                self.assertEqual(titulo_reporte(tipo, descripcion), titulo)

    def test_descripciones_extensas_y_problemas_no_catalogados(self):
        descripcion = 'Buenos días a todos. ' + 'Información general de la oficina. ' * 25 + 'El sistema nuevo no permite guardar el expediente y muestra un error.'
        self.assertIn('guardar', titulo_reporte('Otro', descripcion))
        for tipo in ['Sistema/programa', 'SIGA/Casita/Servidor', 'Carpeta compartida', 'Impresora', 'Huella dactilar', 'Internet/red', 'No enciende', 'Otro', None]:
            with self.subTest(tipo=tipo):
                self.assertLessEqual(len(titulo_reporte(tipo, descripcion)), 70)


if __name__ == '__main__':
    unittest.main()
