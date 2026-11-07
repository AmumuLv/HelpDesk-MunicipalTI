"""Un análisis incompleto nunca se presenta como cero vulnerabilidades."""
import json
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import auditar_imagenes


def _salida(contenido):
    return SimpleNamespace(returncode=0, stdout=contenido, stderr='')


class AuditoriaImagenesTest(unittest.TestCase):
    def test_limite_real_cierra_tambien_descendiente_con_tuberias_abiertas(self):
        codigo = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)']); "
            "time.sleep(10)"
        )
        inicio = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            auditar_imagenes._ejecutar([sys.executable, '-c', codigo], timeout=0.5)
        self.assertLess(time.monotonic() - inicio, 6)

    def _revisar(self, informe):
        with patch.object(auditar_imagenes, '_ejecutar', side_effect=[
            _salida('sha256:imagen-ficticia'), _salida(json.dumps(informe)),
        ]):
            return auditar_imagenes.revisar('imagen-de-prueba')

    def test_informe_sin_ejecuciones_es_desconocido(self):
        for informe in ({}, {'runs': []}, {'runs': [{}]}):
            with self.subTest(informe=informe):
                resultado = self._revisar(informe)
                self.assertTrue(resultado.get('sin_verificar'))
                self.assertNotIn('total', resultado)

    def test_json_invalido_no_da_error_sin_control_ni_resultado_limpio(self):
        with patch.object(auditar_imagenes, '_ejecutar', side_effect=[
            _salida('sha256:imagen-ficticia'), _salida('salida incompleta del analizador'),
        ]):
            self.assertTrue(auditar_imagenes.revisar('imagen-de-prueba').get('sin_verificar'))

    def test_analizador_sin_responder_termina_como_desconocido(self):
        with patch.object(auditar_imagenes, '_ejecutar', side_effect=[
            _salida('sha256:imagen-ficticia'), subprocess.TimeoutExpired('docker scout', 300),
        ]):
            self.assertTrue(auditar_imagenes.revisar('imagen-de-prueba').get('sin_verificar'))

    def test_docker_no_disponible_es_desconocido(self):
        with patch.object(auditar_imagenes, '_ejecutar', side_effect=FileNotFoundError):
            self.assertTrue(auditar_imagenes.revisar('imagen-de-prueba').get('sin_verificar'))

    def test_ejecucion_fallida_aunque_tenga_resultados_no_se_certifica(self):
        resultado = self._revisar({'runs': [{
            'tool': {'driver': {'name': 'Analizador'}}, 'results': [],
            'invocations': [{'executionSuccessful': False}],
        }]})
        self.assertTrue(resultado.get('sin_verificar'))

    def test_informe_valido_sin_avisos_si_tiene_cero(self):
        resultado = self._revisar({'runs': [{
            'tool': {'driver': {'name': 'Analizador'}}, 'results': [],
        }]})
        self.assertFalse(resultado.get('sin_verificar'))
        self.assertEqual(resultado['total'], 0)
        self.assertEqual(resultado['identificador'], 'sha256:imagen-ficticia')

    def test_avisos_de_paquetes_distintos_no_se_ocultan(self):
        resultado = self._revisar({'runs': [{
            'tool': {'driver': {'name': 'Analizador', 'rules': [{
                'id': 'CVE-FICTICIO', 'properties': {'cvssV3_severity': 'high'},
            }]}}, 'results': [{'ruleId': 'CVE-FICTICIO'}, {'ruleId': 'CVE-FICTICIO'}],
        }]})
        self.assertEqual(resultado['total'], 2)


if __name__ == '__main__':
    unittest.main()
