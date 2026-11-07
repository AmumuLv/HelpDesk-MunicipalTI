"""Comprueba que las guías del expediente existen y sus enlaces locales resuelven."""
import ast
import hashlib
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree

RAIZ = Path(__file__).resolve().parents[1]


def main():
    arbol = ast.parse((RAIZ / 'tools/generar_manuales.py').read_text(encoding='utf-8-sig'))
    fuentes = next(ast.literal_eval(n.value) for n in arbol.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'FUENTES' for t in n.targets))
    errores = []
    enlaces = 0
    for nombre in fuentes:
        ruta = RAIZ / nombre
        if not ruta.is_file():
            errores.append(f'{nombre}: falta la guía')
            continue
        texto = ruta.read_text(encoding='utf-8-sig')
        if not texto.startswith('# '):
            errores.append(f'{nombre}: falta un título principal')
        texto = re.sub(r'^```.*?^```', '', texto, flags=re.M | re.S)
        for destino in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', texto):
            url = urlsplit(destino)
            if url.scheme or not url.path:
                continue
            enlaces += 1
            objetivo = (ruta.parent / unquote(url.path)).resolve()
            if not objetivo.is_relative_to(RAIZ) or not objetivo.exists():
                errores.append(f'{nombre}: enlace local no encontrado: {destino}')
    word = RAIZ / 'docs/presentacion/Manuales_y_puesta_en_marcha_HelpDesk_MunicipalTI.docx'
    if not errores:
        huella = hashlib.sha256()
        for fuente in fuentes:
            texto_fuente = (RAIZ / fuente).read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
            huella.update(fuente.encode('utf-8') + b'\0' + texto_fuente.encode('utf-8'))
        texto_generador = (RAIZ / 'tools/generar_manuales.py').read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
        huella.update(texto_generador.encode('utf-8'))
        try:
            with ZipFile(word) as archivo:
                propiedades = ElementTree.fromstring(archivo.read('docProps/core.xml'))
                registrado = propiedades.findtext('{http://purl.org/dc/elements/1.1/}description')
            if registrado != 'Fuentes SHA-256: ' + huella.hexdigest():
                errores.append('El Word está desactualizado: ejecuta tools/generar_manuales.py.')
        except (OSError, BadZipFile, KeyError, ElementTree.ParseError):
            errores.append('Falta un Word válido; ejecuta tools/generar_manuales.py.')
    if errores:
        print('\n'.join(errores))
        return 1
    print(f'OK: {len(fuentes)} guías, {enlaces} enlaces locales y Word sincronizado. No verifica enlaces externos ni sustituye la revisión de contenido.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
