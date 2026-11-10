"""Genera el Word independiente de publicación; no modifica el sistema operativo.

uv run --no-project --python 3.11 --with python-docx tools/generar_guia_publicacion.py
"""
from datetime import date
import hashlib
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

from generar_manuales import agregar_markdown, campo

RAIZ = Path(__file__).resolve().parents[1]
FUENTE = RAIZ / 'docs/GUIA_PUBLICAR_CON_DOMINIO.md'
DESTINO = RAIZ / 'docs/presentacion/Guia_publicar_HelpDesk_con_dominio.docx'


def main():
    documento = Document()
    seccion = documento.sections[0]
    seccion.page_width, seccion.page_height = Cm(21), Cm(29.7)
    seccion.top_margin = seccion.bottom_margin = Cm(1.8)
    seccion.left_margin = seccion.right_margin = Cm(2)
    normal = documento.styles['Normal']
    normal.font.name = 'Aptos'
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.08
    normal.paragraph_format.widow_control = True
    for nombre in ('Title', 'Heading 1', 'Heading 2', 'Heading 3'):
        estilo = documento.styles[nombre]
        estilo.font.name = 'Aptos Display'
        estilo.font.color.rgb = RGBColor.from_string('133D67')
        estilo.paragraph_format.keep_with_next = True
    cabecera = seccion.header.paragraphs[0]
    cabecera.add_run('HELPDESK MUNICIPAL TI  |  GUÍA DE PUBLICACIÓN').font.size = Pt(8)
    pie = seccion.footer.paragraphs[0]
    pie.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pie.add_run('07/11/2026  ·  Página ')
    campo(pie, 'PAGE', '1')
    documento.add_paragraph('MUNICIPALIDAD PROVINCIAL DE CASMA', style='Subtitle')
    documento.add_heading('Tu mesa de ayuda,\ndesde cualquier lugar', 0)
    documento.add_paragraph('Guía sencilla para publicar con dominio propio', style='Subtitle')
    documento.add_paragraph('Computadora municipal + Docker + Cloudflare Tunnel')
    documento.add_paragraph('Versión: ' + date(2026, 11, 7).strftime('%d/%m/%Y'))
    documento.add_paragraph('Para quien compra el dominio, prepara la computadora y coordina las pruebas de lanzamiento.')
    documento.add_heading('El camino de la publicación', 2)
    for texto in (
        '1. Comprar el dominio.',
        '2. Preparar la computadora y el sistema.',
        '3. Conectar Cloudflare Tunnel y activar HTTPS.',
        '4. Probar desde fuera y con todos los roles.',
        '5. Realizar un piloto y autorizar el lanzamiento.',
    ):
        documento.add_paragraph(texto)
    documento.add_paragraph('Ejemplos orientativos: el dominio aún debe elegirse y las pruebas públicas deben ejecutarse en el entorno definitivo.')
    documento.add_page_break()
    agregar_markdown(documento, FUENTE, 1)
    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    for run in parrafo.runs:
                        run.font.size = Pt(9)
    documento.core_properties.title = 'Guía para publicar HelpDesk-MunicipalTI con dominio propio'
    documento.core_properties.author = 'Equipo TI — Municipalidad Provincial de Casma'
    documento.core_properties.subject = 'Dominio, instalación, túnel, HTTPS, pruebas, piloto y operación'
    contenido = FUENTE.read_text(encoding='utf-8').replace('\r\n', '\n')
    documento.core_properties.comments = 'Fuente SHA-256: ' + hashlib.sha256(contenido.encode()).hexdigest()
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    documento.save(DESTINO)
    print(DESTINO)


if __name__ == '__main__':
    main()
