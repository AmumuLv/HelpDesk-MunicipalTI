"""Validaciones previas al traslado; no escribe en el Docker operativo."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import trasladar
import zipfile


class TrasladoTest(unittest.TestCase):
    def test_inicio_genera_clave_y_no_sobrescribe_entorno(self):
        with tempfile.TemporaryDirectory() as carpeta, patch.object(trasladar, 'RAIZ', Path(carpeta)):
            raiz = Path(carpeta)
            (raiz / '.env.example').write_text('SECRET_KEY=ejemplo\nGROQ_API_KEY=\n', encoding='utf-8')
            trasladar.preparar_entorno()
            original = (raiz / '.env').read_text(encoding='utf-8')
            self.assertNotIn('SECRET_KEY=ejemplo', original)
            self.assertGreater(len(original.splitlines()[0].split('=', 1)[1]), 32)
            trasladar.preparar_entorno()
            self.assertEqual((raiz / '.env').read_text(encoding='utf-8'), original)

    def test_no_restaura_encima_de_registros_existentes(self):
        with patch.object(trasladar, 'identificadores', return_value=('api', 'mongo', {'db': 'prueba', 'uploads': '/data/uploads'})), patch.object(trasladar, 'ejecutar', return_value='1'), patch.object(trasladar, 'docker') as docker:
            with self.assertRaisesRegex(ValueError, 'ya contiene datos'):
                trasladar.restaurar('archivo-inexistente.zip')
            docker.assert_not_called()

    def test_reanuda_servicios_tras_un_fallo(self):
        with patch.object(trasladar, 'ejecutar') as ejecutar:
            ejecutar.side_effect = ['api\nworker\nmongo', '', '']
            with self.assertRaisesRegex(ValueError, 'fallo simulado'):
                with trasladar.sin_escrituras():
                    raise ValueError('fallo simulado')
            self.assertEqual(ejecutar.call_args.args, ('start', 'api', 'worker'))

    def test_intenta_reanudar_si_la_parada_falla_a_medias(self):
        with patch.object(trasladar, 'ejecutar') as ejecutar:
            ejecutar.side_effect = ['api\nworker\nmongo', ValueError('parada parcial'), '']
            with self.assertRaisesRegex(ValueError, 'parada parcial'):
                with trasladar.sin_escrituras():
                    self.fail('No debe copiar si la parada no terminó.')
            self.assertEqual(ejecutar.call_args.args, ('start', 'api', 'worker'))

    def test_respaldo_corrupto_no_modifica_el_destino(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'corrupto.zip'
            with zipfile.ZipFile(ruta, 'w') as archivo:
                archivo.writestr('manifiesto.json', json.dumps({'formato': 1, 'base': 'prueba', 'archivos': {'mongo.gz': '0' * 64}}))
                archivo.writestr('mongo.gz', b'contenido de prueba')
            with patch.object(trasladar, 'identificadores', return_value=('api', 'mongo', {'db': 'prueba', 'uploads': '/data/uploads'})), patch.object(trasladar, 'ejecutar', return_value='0'), patch.object(trasladar, 'docker') as docker:
                with self.assertRaisesRegex(ValueError, 'integridad'):
                    trasladar.restaurar(ruta)
                docker.assert_not_called()

    def test_ruta_fuera_del_temporal_se_rechaza(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'rutas.zip'
            with zipfile.ZipFile(ruta, 'w') as archivo:
                archivo.writestr('manifiesto.json', json.dumps({'formato': 1, 'base': 'prueba', 'archivos': {'../escapar': '', 'mongo.gz': ''}}))
            with patch.object(trasladar, 'identificadores', return_value=('api', 'mongo', {'db': 'prueba', 'uploads': '/data/uploads'})), patch.object(trasladar, 'ejecutar', return_value='0'), patch.object(trasladar, 'docker') as docker:
                with self.assertRaisesRegex(ValueError, 'ruta no permitida'):
                    trasladar.restaurar(ruta)
                docker.assert_not_called()


if __name__ == '__main__':
    unittest.main()
