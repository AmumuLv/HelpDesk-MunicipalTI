"""Compila las guías mantenidas en Markdown en un manual Word de entrega.

Uso: uv run --no-project --python 3.11 --with python-docx tools/generar_manuales.py
No accede al entorno operativo, a Internet ni a la base de datos.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = [
    'docs/ENTREGA_Y_PUESTA_EN_MARCHA.md',
    'docs/manuales/USUARIO.md',
    'docs/manuales/TECNICO.md',
    'docs/manuales/ADMINISTRADOR.md',
    'docs/manuales/ADMINISTRADOR_PRINCIPAL.md',
    'docs/manuales/DESARROLLADOR.md',
    'docs/manuales/BASE_DE_DATOS.md',
    'docs/manuales/USABILIDAD.md',
    'docs/RELEVO_E_IMPORTACION.md',
    'docs/IA_DEL_SISTEMA.md',
    'docs/ARQUITECTURA_Y_ESCALABILIDAD.md',
    'docs/GESTION_DE_CAMBIOS.md',
    'docs/REGISTRO_DE_CAMBIOS.md',
    'docs/CIBERSEGURIDAD.md',
    'docs/NUEVA_PC.md',
    'docs/ALMACENAMIENTO.md',
]
AZUL = '123057'
GRIS = '526179'


def limpiar(texto: str) -> str:
    texto = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', texto)
    return texto.replace('**', '').replace('`', '')


def campo(parrafo, instruccion: str, valor: str = '') -> None:
    inicio = OxmlElement('w:fldChar')
    inicio.set(qn('w:fldCharType'), 'begin')
    codigo = OxmlElement('w:instrText')
    codigo.set(qn('xml:space'), 'preserve')
    codigo.text = ' ' + instruccion + ' '
    separador = OxmlElement('w:fldChar')
    separador.set(qn('w:fldCharType'), 'separate')
    final = OxmlElement('w:fldChar')
    final.set(qn('w:fldCharType'), 'end')
    for pieza in (inicio, codigo, separador):
        parrafo.add_run()._r.append(pieza)
    if valor:
        parrafo.add_run(valor)
    parrafo.add_run()._r.append(final)


def sombrear(celda, color: str) -> None:
    elemento = OxmlElement('w:shd')
    elemento.set(qn('w:fill'), color)
    celda._tc.get_or_add_tcPr().append(elemento)


def agregar_tabla(doc, filas: list[str]) -> None:
    datos = [[limpiar(c.strip()) for c in f.strip().strip('|').split('|')] for f in filas]
    datos = [f for f in datos if not all(re.fullmatch(r':?-{3,}:?', c) for c in f)]
    if not datos:
        return
    columnas = max(map(len, datos))
    tabla = doc.add_table(rows=0, cols=columnas)
    tabla.style = 'Table Grid'
    for i, fila in enumerate(datos):
        celdas = tabla.add_row().cells
        for j in range(columnas):
            celdas[j].text = fila[j] if j < len(fila) else ''
            for parrafo in celdas[j].paragraphs:
                parrafo.paragraph_format.space_after = Pt(4)
                for run in parrafo.runs:
                    run.font.size = Pt(9)
                    if i == 0:
                        run.bold = True
                        run.font.color.rgb = RGBColor.from_string('FFFFFF')
            if i == 0:
                sombrear(celdas[j], AZUL)
            elif i % 2:
                sombrear(celdas[j], 'F1F5FA')
        if i == 0:
            repetir = OxmlElement('w:tblHeader')
            tabla.rows[i]._tr.get_or_add_trPr().append(repetir)
    doc.add_paragraph()


def agregar_diagrama(doc, bloque: list[str]) -> None:
    """Representación tabular legible; el diagrama editable queda en Markdown."""
    nombres = dict(re.findall(r'(\w+)\[([^\]]+)\]', '\n'.join(bloque)))
    filas = ['| Origen | Relación | Destino |', '| --- | --- | --- |']
    patron = re.compile(r'^\s*(\w+)(?:\[[^\]]+\])?\s*(-->|-\..*?\.->)(?:\|([^|]+)\|)?\s*(\w+)(?:\[[^\]]+\])?\s*$')
    for linea in bloque:
        m = patron.match(linea)
        if m:
            origen, flecha, etiqueta, destino = m.groups()
            relacion = etiqueta or (flecha[2:-3].strip() if flecha.startswith('-.') else 'Conecta con')
            filas.append(f'| {nombres.get(origen, origen)} | {relacion} | {nombres.get(destino, destino)} |')
    doc.add_paragraph('Relaciones del diagrama. La versión gráfica editable se mantiene en la guía fuente.')
    agregar_tabla(doc, filas)


def agregar_markdown(doc, ruta: Path, numero: int) -> None:
    lineas = ruta.read_text(encoding='utf-8-sig').splitlines()
    titulo = next((l[2:].strip() for l in lineas if l.startswith('# ')), ruta.stem)
    doc.add_heading(f'{numero}. {titulo}', 1)
    origen = doc.add_paragraph(f'Fuente mantenida: {ruta.relative_to(RAIZ).as_posix()}')
    origen.style = 'Caption'
    parrafo: list[str] = []

    def vaciar():
        if parrafo:
            doc.add_paragraph(limpiar(' '.join(parrafo)))
            parrafo.clear()

    i = 0
    while i < len(lineas):
        linea = lineas[i].rstrip()
        if linea.startswith('# '):
            i += 1
            continue
        if linea.startswith('```'):
            vaciar()
            lenguaje = linea[3:].strip()
            bloque = []
            i += 1
            while i < len(lineas) and not lineas[i].startswith('```'):
                bloque.append(lineas[i])
                i += 1
            if lenguaje == 'mermaid':
                agregar_diagrama(doc, bloque)
            for codigo in ([] if lenguaje == 'mermaid' else bloque):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                run = p.add_run(codigo)
                run.font.name = 'Consolas'
                run.font.size = Pt(8)
            doc.add_paragraph()
        elif linea.startswith('|'):
            vaciar()
            filas = []
            while i < len(lineas) and lineas[i].startswith('|'):
                filas.append(lineas[i])
                i += 1
            agregar_tabla(doc, filas)
            continue
        elif linea.startswith('##'):
            vaciar()
            nivel = min(len(linea) - len(linea.lstrip('#')), 4)
            doc.add_heading(limpiar(linea.lstrip('#').strip()), nivel)
        elif re.match(r'^[-*] ', linea):
            vaciar()
            contenido = linea[2:]
            while i + 1 < len(lineas) and lineas[i + 1].startswith('  ') and not re.match(r'^\s+[-*\d]', lineas[i + 1]):
                i += 1
                contenido += ' ' + lineas[i].strip()
            doc.add_paragraph(limpiar(contenido), style='List Bullet')
        elif re.match(r'^\d+\. ', linea):
            vaciar()
            numero_paso = linea.split('.', 1)[0]
            contenido = re.sub(r'^\d+\. ', '', linea)
            while i + 1 < len(lineas) and lineas[i + 1].startswith('   '):
                i += 1
                contenido += ' ' + lineas[i].strip()
            # Conservar el número de la fuente evita que Word continúe una
            # única lista automática a través de todos los manuales.
            paso = doc.add_paragraph(f'{numero_paso}. {limpiar(contenido)}')
            paso.paragraph_format.left_indent = Cm(0.5)
            paso.paragraph_format.first_line_indent = Cm(-0.5)
        elif not linea.strip():
            vaciar()
        elif linea.strip() != '---':
            parrafo.append(linea.strip())
        i += 1
    vaciar()
    # Las fuentes externas quedan visibles también en Word, sin ocultar la URL.
    enlaces = sorted(set(re.findall(r'\]\((https?://[^)]+)\)', '\n'.join(lineas))))
    if enlaces:
        doc.add_heading('Referencias de esta sección', 3)
        for enlace in enlaces:
            doc.add_paragraph(enlace, style='Caption')


def generar(destino: Path, fecha: date) -> None:
    faltan = [f for f in FUENTES if not (RAIZ / f).is_file()]
    if faltan:
        raise ValueError('Faltan guías: ' + ', '.join(faltan))
    doc = Document()
    seccion = doc.sections[0]
    seccion.top_margin = seccion.bottom_margin = Cm(1.8)
    seccion.left_margin = seccion.right_margin = Cm(1.9)
    normal = doc.styles['Normal']
    normal.font.name = 'Aptos'
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    for nombre in ('Title', 'Heading 1', 'Heading 2', 'Heading 3', 'Heading 4'):
        doc.styles[nombre].font.color.rgb = RGBColor.from_string(AZUL)
    doc.styles['Heading 1'].paragraph_format.page_break_before = True
    cabecera = seccion.header.paragraphs[0]
    cabecera.add_run('HELPDESK MUNICIPAL TI  |  OPERACIÓN Y MANTENIMIENTO').font.size = Pt(8)
    cabecera.runs[0].font.color.rgb = RGBColor.from_string(GRIS)
    pie = seccion.footer.paragraphs[0]
    pie.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pie.add_run('Documento técnico · Página ')
    campo(pie, 'PAGE', '1')
    doc.add_paragraph('MUNICIPALIDAD PROVINCIAL DE CASMA', style='Subtitle')
    doc.add_heading('Manuales y expediente\nde puesta en marcha', 0)
    doc.add_paragraph('HelpDesk-MunicipalTI', style='Subtitle')
    doc.add_paragraph('Usuarios · Técnicos · Administración · Desarrollo · Datos · Seguridad')
    doc.add_paragraph('Versión documental: ' + fecha.strftime('%d/%m/%Y'))
    doc.add_paragraph('Las guías describen el sistema y sus límites. Los apartados de propuesta y preparación no significan que el servidor público ya esté desplegado.')
    doc.add_page_break()
    doc.add_heading('Contenido', 0)
    for n, fuente in enumerate(FUENTES, 1):
        contenido = (RAIZ / fuente).read_text(encoding='utf-8-sig')
        titulo = next(l[2:] for l in contenido.splitlines() if l.startswith('# '))
        doc.add_paragraph(f'{n}. {titulo}')
    doc.add_paragraph('Utiliza el panel de navegación de Word para ir a cada capítulo. Las guías Markdown mantienen los diagramas editables y los enlaces internos del proyecto.')
    for numero, fuente in enumerate(FUENTES, 1):
        agregar_markdown(doc, RAIZ / fuente, numero)
    doc.core_properties.title = 'Manuales y expediente de puesta en marcha — HelpDesk-MunicipalTI'
    doc.core_properties.author = 'Equipo TI — Municipalidad Provincial de Casma'
    doc.core_properties.subject = 'Operación, mantenimiento, inventario, IA, arquitectura y seguridad'
    doc.core_properties.created = datetime.now(timezone.utc)
    doc.core_properties.modified = doc.core_properties.created
    doc.core_properties.last_modified_by = 'Equipo TI — Municipalidad Provincial de Casma'
    huella = hashlib.sha256()
    for fuente in FUENTES:
        texto_fuente = (RAIZ / fuente).read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
        huella.update(fuente.encode('utf-8') + b'\0' + texto_fuente.encode('utf-8'))
    texto_generador = Path(__file__).read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    huella.update(texto_generador.encode('utf-8'))
    doc.core_properties.comments = 'Fuentes SHA-256: ' + huella.hexdigest()
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destino)
    print(f'Word generado con {len(FUENTES)} guías: {destino}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=RAIZ / 'docs/presentacion/Manuales_y_puesta_en_marcha_HelpDesk_MunicipalTI.docx')
    parser.add_argument('--fecha', type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    generar(args.salida, args.fecha)


if __name__ == '__main__':
    main()
