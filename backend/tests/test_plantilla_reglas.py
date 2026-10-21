"""Reglas de archivo sin conexiones ni escrituras a bases de datos."""
from io import BytesIO
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from openpyxl import Workbook

from app.core.errors import Validacion
from app.core.ids import mcp_mac
from app.services import inventario_anual_service as anual, import_service


class ReglasPlantilla(IsolatedAsyncioTestCase):
    async def test_importacion_laptops_e_impresoras_son_independientes(self):
        documento = {'filas': {'PALACIO': [
            {'__fila__': n, 'AREA': 'SOPORTE', 'GRUPO': 'COMPUTADORA N°1', 'TIPO': tipo}
            for n, tipo in enumerate(['CPU', 'Monitor', 'Laptop', 'Impresora'], 2)
        ]}, 'mapeo': {'PALACIO': {'area': {'columna': 'AREA'}, 'tipo_equipo': {'columna': 'GRUPO'}, 'dispositivo': {'columna': 'TIPO'}}}}
        with patch.object(import_service, 'get_db', return_value={}), patch.object(import_service, '_resolucion_hoja', new=AsyncMock(return_value=({'_id': ObjectId(), 'nombre': 'PALACIO'}, False))), patch.object(import_service.catalogo_service, 'mapa_sinonimos', new=AsyncMock(return_value={})), patch.object(import_service.catalogo_service, 'tipos_existentes', new=AsyncMock(return_value=['CPU', 'Monitor', 'Laptop', 'Impresora'])):
            filas = (await import_service._preparar_filas(documento, usuario={}))['filas']
        self.assertEqual([f['es_conjunto'] for f in filas], [True, True, False, False])
        self.assertIsNone(filas[2]['conjunto_numero'])
        self.assertIsNone(filas[3]['conjunto_numero'])

    def archivo(self, filas):
        libro = Workbook()
        hoja = libro.active
        hoja.title = 'PALACIO'
        hoja.append(['AREA', 'Tipo de equipo', 'Dispositivo', 'Código patrimonial', 'Propiedad', 'Responsable', 'Direccion IP', 'Direccion MAC'])
        for fila in filas:
            hoja.append(fila)
        salida = BytesIO()
        libro.save(salida)
        return salida.getvalue()

    async def importar(self, filas):
        coleccion = AsyncMock()
        coleccion.find_one.return_value = None
        coleccion.insert_one.return_value = SimpleNamespace(inserted_id=ObjectId())
        with patch.object(anual, 'get_db', return_value={'inventario_versiones': coleccion}), patch.object(anual, 'registrar', new_callable=AsyncMock), patch.object(anual.catalogo_service, 'mapa_sinonimos', new=AsyncMock(return_value={'MAUSE': 'Mouse'})), patch.object(anual.catalogo_service, 'tipos_existentes', new=AsyncMock(return_value=['Mouse', 'CPU', 'Monitor', 'Teclado', 'Impresora', 'Laptop'])):
            await anual.importar(2026, self.archivo(filas), 'inventario.xlsx', None, {'_id': ObjectId()})
        return coleccion.insert_one.await_args.args[0]['instantanea']

    async def test_conjuntos_herencia_personal_y_oficina(self):
        filas = await self.importar([
            ['SOPORTE', 'COMPUTADORA N°01', 'CPU', '0001', 'MUNICIPALIDAD', 'Persona'],
            [None, None, 'MAUSE', None, 'MUNICIPALIDAD', 'Persona'],
            ['SOPORTE', 'COMPUTADORA N°02', 'Mouse', None, 'PERSONAL', None],
            ['OTRA OFICINA', 'COMPUTADORA N°01', 'Mouse', 'NO APLICA', 'PERSONAL', None],
        ])
        self.assertEqual(len(filas), 4)
        self.assertEqual(filas[1]['tipo'], 'Mouse')
        self.assertEqual(filas[1]['conjunto_nombre'], 'COMPUTADORA N°01')
        self.assertEqual(filas[1]['oficina'], 'SOPORTE')
        self.assertTrue(filas[2]['uso_comun'])
        self.assertIsNone(filas[3]['codigo'])
        self.assertNotEqual(anual.identidad(filas[1]), anual.identidad(filas[2]))

    async def test_personal_ignora_patrimonio_y_usb_no_es_ip(self):
        filas = await self.importar([
            ['SOPORTE', 'IMPRESORA N°1', 'Impresora', '123', 'PERSONAL', None, 'CABLE USB'],
            ['SOPORTE', 'IMPRESORA N°2', 'Impresora', None, 'PERSONAL', None, 'USB'],
        ])
        self.assertIsNone(filas[0]['codigo'])
        self.assertEqual(filas[1]['campos']['direccion_ip'], 'Cable USB')

    async def test_rechaza_ip_mac_repetidas_y_mal_escritas(self):
        for campo, valor in [(6, '192.168.0.5'), (7, 'AA:BB:CC:DD:EE:FF')]:
            filas = [['SOPORTE', f'LAPTOP N°{n}', 'Laptop', str(n), 'MUNICIPALIDAD', None, None, None] for n in (1, 2)]
            for fila in filas:
                fila[campo] = valor
            with self.assertRaisesRegex(Validacion, 'repetida'):
                await self.importar(filas)
        with self.assertRaisesRegex(Validacion, 'inválida'):
            await self.importar([['SOPORTE', 'LAPTOP N°1', 'Laptop', None, 'PERSONAL', None, '192.168.110', 'INVALIDA']])

    async def test_rechaza_duplicado_real(self):
        fila = ['SOPORTE', 'COMPUTADORA N°1', 'Mouse', None, 'MUNICIPALIDAD']
        with self.assertRaisesRegex(Validacion, 'equipo repetido'):
            await self.importar([fila, fila])

    async def test_identidad_equivalente_ceros_y_formatos_mac(self):
        a = {'zona': 'PALACIO', 'oficina': 'SOPORTE', 'tipo': 'Mouse', 'nombre': 'Mouse', 'conjunto_nombre': 'COMPUTADORA N°01'}
        b = {**a, 'conjunto_nombre': 'COMPUTADORA N°1'}
        self.assertEqual(anual.identidad(a), anual.identidad(b))
        for texto in ('aabb.ccdd.eeff', 'AA.BB.CC.DD.EE.FF', 'aa-bb-cc-dd-ee-ff'):
            self.assertEqual(mcp_mac(texto), 'AA:BB:CC:DD:EE:FF')

    async def test_previa_redes_repetidas_y_reimportacion(self):
        zona = str(ObjectId())
        def fila(numero, ip):
            return {'numero': numero, 'hoja': 'PALACIO', 'zona_nombre': 'PALACIO', 'zona_id': zona,
                    'oficina_nombre': 'SOPORTE', 'tipo': 'CPU', 'conjunto_nombre': f'Computadora N°{numero}',
                    'errores': [], 'excluida': False, 'advertencias': [], 'accion': 'crear',
                    'codigo_patrimonial': str(numero), 'es_conjunto': True, 'campos_no_aplica_sugeridos': [],
                    'responsable_nombre': None, 'responsable_estado': 'sin_responsable', 'propiedad': 'MUNICIPALIDAD', 'direccion_ip': ip}
        for repetida in (False, True):
            filas = [fila(2, '192.168.0.5'), fila(3, '192.168.0.5' if repetida else '192.168.0.6')]
            activos = AsyncMock()
            activos.find_one.return_value = None
            cambios = AsyncMock()
            with patch.object(import_service, 'obtener_lote', new=AsyncMock(return_value={})), patch.object(import_service, '_preparar_filas', new=AsyncMock(return_value={'filas': filas, 'reglas_aplicadas': []})), patch.object(import_service, 'get_db', return_value={'activos': activos, 'importaciones': cambios}):
                previa = await import_service.previsualizar('lote', usuario={})
            self.assertEqual(previa['con_error'], 2 if repetida else 0)
