"""El preparador HTTPS respeta la jerarquía y se limita a la base ficticia."""
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from verificar_publicacion import PREPARAR_CUENTA_SEGURIDAD


class PreparadorSeguridadTest(unittest.TestCase):
    def preparar(self, respuestas, *, base='helpdesk_test_navegador'):
        usuarios = SimpleNamespace(find_one=AsyncMock(side_effect=respuestas))
        crear = AsyncMock()
        cerrar = AsyncMock()
        db = SimpleNamespace(name=base, usuarios=usuarios)
        modulos = {
            'app': ModuleType('app'), 'app.core': ModuleType('app.core'),
            'app.core.db': SimpleNamespace(get_db=lambda: db, close_connections=cerrar),
            'app.services': SimpleNamespace(usuario_service=SimpleNamespace(crear=crear)),
        }
        return usuarios, crear, cerrar, patch.dict('sys.modules', modulos)

    def test_usa_al_principal_real_para_el_alta(self):
        principal = {'_id': 'principal-ficticio', 'rol': 'administrador', 'administrador_principal': True}
        usuarios, crear, cerrar, modulos = self.preparar([None, principal])
        with modulos:
            exec(PREPARAR_CUENTA_SEGURIDAD, {})
        crear.assert_awaited_once()
        self.assertIs(crear.call_args.kwargs['usuario'], principal)
        self.assertEqual(usuarios.find_one.call_args.args[0], {
            'rol': 'administrador', 'administrador_principal': True,
            'activo': True, 'archivado': {'$ne': True},
        })
        cerrar.assert_awaited_once()

    def test_sin_principal_no_fabrica_autoridad(self):
        _, crear, cerrar, modulos = self.preparar([None, None])
        with modulos, self.assertRaisesRegex(RuntimeError, 'Falta el administrador principal'):
            exec(PREPARAR_CUENTA_SEGURIDAD, {})
        crear.assert_not_awaited()
        cerrar.assert_awaited_once()

    def test_repetir_no_duplica_la_cuenta(self):
        usuarios, crear, cerrar, modulos = self.preparar([{'email': 'seguridad.admin@demo.local'}])
        with modulos:
            exec(PREPARAR_CUENTA_SEGURIDAD, {})
        crear.assert_not_awaited()
        usuarios.find_one.assert_awaited_once()
        cerrar.assert_awaited_once()

    def test_otra_base_se_rechaza_antes_de_consultar_cuentas(self):
        usuarios, crear, cerrar, modulos = self.preparar([], base='mesa_ayuda')
        with modulos, self.assertRaises(AssertionError):
            exec(PREPARAR_CUENTA_SEGURIDAD, {})
        usuarios.find_one.assert_not_awaited()
        crear.assert_not_awaited()
        cerrar.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
