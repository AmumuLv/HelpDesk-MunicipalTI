"""Rasteriza muestras reales y comprueba orientación y límites del texto.

Uso: python tools/revisar_pdf_reportes.py docs/muestras-reportes
Dependencia de revisión: pymupdf (no forma parte de la aplicación).
"""
import json
import sys
from pathlib import Path

import pymupdf

carpeta = Path(sys.argv[1])
for archivo in sorted(carpeta.glob('*.pdf')):
    documento = pymupdf.open(archivo)
    fuera = []
    for numero, pagina in enumerate(documento, 1):
        if pagina.rect.width <= pagina.rect.height:
            raise ValueError(f'{archivo.name}: página {numero} no horizontal')
        if len(pagina.get_text('words')) < 20:
            raise ValueError(f'{archivo.name}: página {numero} casi vacía')
        for palabra in pagina.get_text('words'):
            x0, y0, x1, y1 = palabra[:4]
            if x0 < -1 or y0 < -1 or x1 > pagina.rect.width + 1 or y1 > pagina.rect.height + 1:
                fuera.append(numero)
    for indice in sorted({0, len(documento) - 1}):
        documento[indice].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6)).save(carpeta / f'{archivo.stem}-pagina-{indice + 1}.png')
    print(json.dumps({'archivo': archivo.name, 'paginas': len(documento), 'paginas_con_texto_fuera': sorted(set(fuera))}))
    if fuera:
        raise ValueError(f'{archivo.name}: hay texto fuera de los límites')
