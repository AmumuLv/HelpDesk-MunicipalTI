"""Diagnóstico sin datos de prueba, mutaciones o exposición de secretos.

Se ejecuta con unittest sin arrancar servicios: HTTP se simula con MockTransport.
"""

from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

import httpx

from app.scripts.diagnostico import comprobar


class DiagnosticoTest(unittest.IsolatedAsyncioTestCase):
    async def diagnosticar(self, *, estado=200, cuerpo=None, contenido=None):
        peticiones = []

        def responder(peticion):
            peticiones.append(peticion)
            if contenido is not None:
                return httpx.Response(estado, content=contenido)
            return httpx.Response(estado, json=cuerpo)

        salida = StringIO()
        with redirect_stdout(salida), patch.dict("os.environ", {"API_PREFIX": "/api"}):
            resultado = await comprobar(transporte=httpx.MockTransport(responder))
        self.assertEqual(len(peticiones), 1)
        self.assertEqual(peticiones[0].method, "GET")
        self.assertEqual(str(peticiones[0].url), "http://localhost:8000/api/health")
        self.assertFalse(peticiones[0].content)
        self.assertNotIn("authorization", peticiones[0].headers)
        return resultado, salida.getvalue()

    async def test_instalacion_sana_no_necesita_cuentas_y_no_imprime_configuracion(self):
        resultado, salida = await self.diagnosticar(cuerpo={
            "estado": "ok", "mongo": True, "redis": True,
            "detalle": {"clave": "secreto-no-imprimir", "cuenta": "correo-privado"},
        })
        self.assertEqual(resultado, 0)
        self.assertIn("MongoDB responde", salida)
        self.assertIn("Redis responde", salida)
        self.assertNotIn("secreto-no-imprimir", salida)
        self.assertNotIn("correo-privado", salida)

    async def test_http_200_degradado_no_se_confunde_con_exito(self):
        for dependencia in ["mongo", "redis"]:
            with self.subTest(dependencia=dependencia):
                salud = {"estado": "degradado", "mongo": True, "redis": True}
                salud[dependencia] = False
                resultado, salida = await self.diagnosticar(cuerpo=salud)
                self.assertEqual(resultado, 1)
                self.assertIn("FALLA", salida)

    async def test_respuesta_erronea_o_malformada_falla_sin_imprimir_cuerpo(self):
        for parametros in [
            {"estado": 503, "contenido": b"secreto-interno"},
            {"contenido": b"secreto-interno"},
            {"cuerpo": []},
            {"cuerpo": {"estado": "ok"}},
            {"cuerpo": {"estado": "ok", "mongo": "true", "redis": True}},
        ]:
            with self.subTest(parametros=parametros):
                resultado, salida = await self.diagnosticar(**parametros)
                self.assertEqual(resultado, 1)
                self.assertNotIn("secreto-interno", salida)

    async def test_conexion_fallida_devuelve_error_sin_datos_de_la_url(self):
        def responder(peticion):
            raise httpx.ConnectError("detalle-secreto", request=peticion)

        salida = StringIO()
        with redirect_stdout(salida):
            resultado = await comprobar(transporte=httpx.MockTransport(responder))
        self.assertEqual(resultado, 1)
        self.assertIn("no se pudo conectar", salida.getvalue())
        self.assertNotIn("detalle-secreto", salida.getvalue())

    async def test_respeta_prefijo_de_api_configurado(self):
        peticiones = []

        def responder(peticion):
            peticiones.append(peticion)
            return httpx.Response(200, json={"estado": "ok", "mongo": True, "redis": True})

        with patch.dict("os.environ", {"API_PREFIX": "/servicio/"}), redirect_stdout(StringIO()):
            self.assertEqual(await comprobar(transporte=httpx.MockTransport(responder)), 0)
        self.assertEqual(peticiones[0].url.path, "/servicio/health")


if __name__ == "__main__":
    unittest.main()
