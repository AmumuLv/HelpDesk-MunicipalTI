"""Verify the production image's native backports without touching the database."""
import ctypes
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
import wave
import zlib

from openpyxl import Workbook, load_workbook
from weasyprint import HTML


def main():
    evidence = json.loads(Path('/usr/local/share/helpdesk/security-backports.json').read_text())
    for soname, item in evidence.items():
        path = Path(item['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], soname
        ctypes.CDLL(soname)
        assert str(path) in Path('/proc/self/maps').read_text(), soname
    # Verify the distribution library and CPython's rebuilt extension.
    import pyexpat
    module = evidence['libexpat.so.1']['python_module']
    assert Path(pyexpat.__file__).resolve() == Path(module['path'])
    assert hashlib.sha256(Path(module['path']).read_bytes()).hexdigest() == module['sha256']
    assert evidence['libexpat.so.1']['path'] in Path('/proc/self/maps').read_text()
    instrucciones = []
    parser = pyexpat.ParserCreate()
    parser.ProcessingInstructionHandler = lambda target, data: instrucciones.append((target, data))
    def entidad(context, base, system, public):
        child = parser.ExternalEntityParserCreate(context)
        child.Parse(b'', False)
        child.Parse(b'<?target data?>', True)
        return 1
    parser.ExternalEntityRefHandler = entidad
    parser.Parse(b'<!DOCTYPE root [<!ENTITY ext SYSTEM "external.dtd">]><root>&ext;</root>', True)
    assert instrucciones == [('target', 'data')], 'Expat empty non-final entity regression'
    # This CVE requires the separate libxml2 Python SAX bindings, never lxml.
    import importlib.util
    assert importlib.util.find_spec('libxml2') is None
    assert importlib.util.find_spec('libxml2mod') is None
    libxml = ctypes.CDLL('libxml2.so.2')
    libxml.xmlReadMemory.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    libxml.xmlReadMemory.restype = ctypes.c_void_p
    libxml.xmlFreeDoc.argtypes = [ctypes.c_void_p]
    xml = b'<!DOCTYPE equipo [<!ELEMENT equipo (#PCDATA)>]><equipo>Prueba</equipo>'
    document = libxml.xmlReadMemory(xml, len(xml), None, None, 16)
    assert document, 'Native XML with DTD validation failed'
    libxml.xmlFreeDoc(document)
    packages = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Status}', 'libcjson1'], capture_output=True, text=True)
    assert packages.stdout.strip() != 'installed', 'cJSON must not be installed in production'
    libz = ctypes.CDLL('libz.so.1')
    libz.zlibVersion.restype = ctypes.c_char_p
    assert libz.zlibVersion().startswith(b'1.3.2')
    data = b'Prueba de compresion sin datos reales' * 1000
    assert zlib.decompress(zlib.compress(data)) == data
    pdf = HTML(string='<h1>Informe TI</h1><p>Verificación de PDF: áéíóú.</p>').write_pdf()
    assert pdf.startswith(b'%PDF-') and len(pdf) > 1000
    workbook = Workbook()
    workbook.active.append(['Equipo', 'Oficina'])
    workbook.active.append(['Laptop ficticia', 'Pruebas'])
    excel = BytesIO()
    workbook.save(excel)
    excel.seek(0)
    assert load_workbook(excel).active['A2'].value == 'Laptop ficticia'
    with tempfile.TemporaryDirectory() as directory:
        audio = Path(directory) / 'audio.wav'
        with wave.open(str(audio), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b'\0\0' * 8000)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(audio)], capture_output=True, text=True, check=True)
        assert float(json.loads(probe.stdout)['format']['duration']) == 1.0
    print('PASS: hashes, loaded libraries, XML/DTD, patched Python Expat/entity regression, absent cJSON/Python SAX, zlib, PDF, Excel and ffprobe WAV')


if __name__ == '__main__':
    main()
