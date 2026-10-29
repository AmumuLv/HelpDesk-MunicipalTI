"""Lectura y escritura de Excel/CSV (openpyxl) con la estructura de la plantilla oficial."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.core.errors import Validacion
from app.core.ids import clave, normalizar_texto

MAX_FILAS = 20000
MAX_COLUMNAS = 80

# Columnas oficiales de la plantilla. El orden importa: es el formato de ida y vuelta.
COLUMNAS_OFICIALES = [
    "AREA",
    "Tipo de equipo",
    "Dispositivo",
    "Código patrimonial",
    "Marca",
    "Modelo",
    "Tamaño Pantalla",
    "Nombre Equipo",
    "Procesador",
    "Memoria RAM",
    "Almacenamiento",
    "Direccion IP",
    "Direccion MAC",
    "Propiedad",
    "Estado",
    "Responsable",
]

# Claves internas -> cabeceras oficiales
MAPEO_INVIRSO = {clave(c): c for c in COLUMNAS_OFICIALES}

CAMPOS_A_COLUMNAS: dict[str, str] = {
    "area": "AREA",
    "tipo_equipo": "Tipo de equipo",
    "dispositivo": "Dispositivo",
    "codigo_patrimonial": "Código patrimonial",
    "marca": "Marca",
    "modelo": "Modelo",
    "tamano_pantalla": "Tamaño Pantalla",
    "nombre_equipo": "Nombre Equipo",
    "procesador": "Procesador",
    "memoria_ram": "Memoria RAM",
    "almacenamiento": "Almacenamiento",
    "direccion_ip": "Direccion IP",
    "direccion_mac": "Direccion MAC",
    "propiedad": "Propiedad",
    "estado": "Estado",
    "responsable": "Responsable",
}

ENCABEZADO_DETALLE = [
    "Código patrimonial",
    "Nombre Equipo",
    "Tipo",
    "Seccion",
    "Marca",
    "Modelo",
    "Capacidad",
    "Unidad",
    "Velocidad",
    "Serie",
    "Extra",
]

FILA_VACIA = PatternFill("solid", fgColor="FFF7E6")


def _a_texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, float):
        return str(valor).rstrip("0").rstrip(".")
    return normalizar_texto(str(valor))


def leer_archivo(contenido: bytes, nombre: str) -> dict[str, list[list[str]]]:
    """Devuelve {nombre_hoja: filas}. Acepta .xlsx y .csv."""
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension in {"csv", "txt"}:
        return _leer_csv(contenido)
    if extension not in {"xlsx", "xlsm"}:
        raise Validacion(
            "Formato no admitido. Sube un archivo .xlsx o .csv.",
            detalles={"extension": extension or "desconocida"},
        )
    try:
        libro = load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    except Exception as exc:
        raise Validacion("No se pudo abrir el archivo. Verifica que sea un .xlsx valido.") from exc
    hojas: dict[str, list[list[str]]] = {}
    for hoja in libro.worksheets:
        if clave(hoja.title) in {"INSTRUCCIONES", "INSTRUCTIONS"}:
            continue
        filas: list[list[str]] = []
        for indice, fila in enumerate(hoja.iter_rows(values_only=True)):
            if indice >= MAX_FILAS:
                break
            valores = [_a_texto(v) for v in list(fila)[:MAX_COLUMNAS]]
            while valores and valores[-1] == "":
                valores.pop()
            filas.append(valores)
        hojas[hoja.title] = filas
    libro.close()
    if not hojas:
        raise Validacion("El archivo no tiene hojas.")
    return hojas


def _leer_csv(contenido: bytes) -> dict[str, list[list[str]]]:
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1", "replace")
    muestra = texto[:5000]
    try:
        separador = csv.Sniffer().sniff(muestra, delimiters=",;\t|").delimiter
    except csv.Error:
        separador = ","
    filas = [linea for linea in csv.reader(io.StringIO(texto), delimiter=separador)][:MAX_FILAS]
    limpio = [[_a_texto(celda) for celda in fila] for fila in filas]
    return {"Hoja 1": limpio}


def detectar_encabezado(filas: list[list[str]]) -> int:
    """La cabecera es la primera fila que tiene al menos 3 textos no vacios."""
    for indice, fila in enumerate(filas[:10]):
        no_vacios = [c for c in fila if c]
        if len(no_vacios) >= 3:
            return indice
    return 0


def hoja_a_registros(filas: list[list[str]]) -> tuple[list[str], list[dict[str, Any]]]:
    """Devuelve (cabeceras, registros) usando la fila de cabecera detectada."""
    if not filas:
        return [], []
    indice = detectar_encabezado(filas)
    cabeceras = [c for c in filas[indice]]
    # Algunos libros OTIC omiten AREA en la primera celda de la cabecera.
    if cabeceras and not cabeceras[0] and any(clave(c) == "DISPOSITIVO" for c in cabeceras):
        cabeceras[0] = "AREA"
    registros: list[dict[str, Any]] = []
    for numero, fila in enumerate(filas[indice + 1 :], start=indice + 2):
        if not any(celda.strip() for celda in fila):
            continue
        registro = {cabeceras[i]: fila[i] if i < len(fila) else "" for i in range(len(cabeceras))}
        registro["__fila__"] = numero
        registros.append(registro)
    return cabeceras, registros


# ── Escritura ────────────────────────────────────────────────
def _encabezado(hoja: Worksheet, titulos: list[str]) -> None:
    relleno = PatternFill("solid", fgColor="EAF1FF")
    negrita = Font(bold=True)
    for indice, titulo in enumerate(titulos, start=1):
        celda = hoja.cell(row=1, column=indice, value=titulo)
        celda.font = negrita
        celda.fill = relleno
        celda.alignment = Alignment(vertical="center")
        hoja.column_dimensions[get_column_letter(indice)].width = max(14, min(len(titulo) + 4, 32))
    hoja.freeze_panes = "A2"


def plantilla_oficial() -> bytes:
    """Plantilla vacia con la estructura exacta que espera el asistente."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Inventario"
    _encabezado(hoja, COLUMNAS_OFICIALES)
    detalle = libro.create_sheet("Detalle avanzado")
    _encabezado(detalle, ENCABEZADO_DETALLE)
    notas = libro.create_sheet("Instrucciones")
    notas["A1"] = "Como usar esta plantilla"
    notas["A1"].font = Font(bold=True, size=13)
    instrucciones = [
        "1. Cada hoja de inventario es una ZONA. Renombra 'Inventario' con el nombre real de la zona.",
        "2. La columna AREA es la OFICINA. Repitela en cada fila o el sistema la rellena hacia abajo.",
        "3. 'Tipo de equipo' es el conjunto al que pertenece el dispositivo, si corresponde.",
        "   Recomendado: repitelo en cada componente (COMPUTADORA N°01). Si lo omites, se hereda dentro de la oficina.",
        "4. 'Dispositivo' es el componente: MONITOR, TECLADO, MOUSE, CPU, IMPRESORA, LAPTOP.",
        "5. Codigo patrimonial '-' o vacio significa que el equipo no tiene codigo asignado.",
        "6. Responsables: escribe el nombre de una persona registrada en esa oficina.",
        "   Si no hay responsable, el equipo queda como uso comun de la oficina.",
        "7. La hoja 'Detalle avanzado' es opcional y sirve para registrar RAM, discos y otros modulos.",
        "8. Los campos vacios no son errores: se importan como 'Pendiente' y aparecen en",
        "   Equipos > Calidad del inventario para completarlos despues.",
        "9. Propiedad PERSONAL: codigo patrimonial No aplica. No inventes codigos.",
        "10. IP y MAC no deben repetirse entre dispositivos. No copies la red del CPU al monitor, teclado o mouse.",
        "11. Impresora conectada por USB: escribe CABLE USB en Direccion IP y deja MAC vacia si no tiene red.",
        "12. Cada componente ocupa una fila. Computadora: CPU, MONITOR, TECLADO y MOUSE.",
        "13. Vacio significa Pendiente; No aplica significa que ese dato no corresponde al dispositivo.",
    ]
    for indice, linea in enumerate(instrucciones, start=3):
        notas.cell(row=indice, column=1, value=linea)
    notas.column_dimensions["A"].width = 110
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def exportar_inventario(filas: list[dict[str, Any]], *, destino_nombre: str = "inventario") -> bytes:
    """Exporta con la misma estructura de la plantilla (ida y vuelta)."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = destino_nombre[:31] or "inventario"
    _encabezado(hoja, COLUMNAS_OFICIALES)
    for fila in filas:
        hoja.append([fila.get(columna, "") or "" for columna in COLUMNAS_OFICIALES])
    if any(f.get("detalle") for f in filas):
        detalle = libro.create_sheet("Detalle avanzado")
        _encabezado(detalle, ENCABEZADO_DETALLE)
        for fila in filas:
            for modulo in fila.get("detalle") or []:
                detalle.append([modulo.get(columna, "") or "" for columna in ENCABEZADO_DETALLE])
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def exportar_inventario_por_zonas(
    zonas: dict[str, list[dict[str, Any]]], *, nombre_hoja_respaldo: str = "Inventario"
) -> bytes:
    """
    Exporta en el formato real del municipio: **una hoja por zona**.

    `exportar_inventario` mete todo en una sola hoja, que sirve para una previsualización
    corta pero no para el archivo del municipio: ese tiene cinco hojas, una por zona, y
    una hoja mezclada no se puede volver a subir ni comparar de un vistazo.

    Los nombres de hoja se limpian de lo que Excel no admite (`: \\ / ? * [ ]`) y se
    recortan a 31 caracteres, que es su límite. Si dos zonas se limpian al mismo nombre
    se añade un número, porque Excel no admite nombres repetidos y el archivo se
    rechazaría al abrirlo.
    """
    libro = Workbook()
    libro.remove(libro.active)
    usados: set[str] = set()
    for zona in zonas:
        filas = zonas[zona]
        limpio = "".join(caracter for caracter in zona if caracter not in ':\\/?*[]') or "Sin zona"
        limpio = limpio[:31]
        titulo = limpio
        numero = 2
        while titulo.casefold() in usados:
            sufijo = f" ({numero})"
            titulo = limpio[: 31 - len(sufijo)] + sufijo
            numero += 1
        usados.add(titulo.casefold())
        hoja = libro.create_sheet(titulo)
        _encabezado(hoja, COLUMNAS_OFICIALES)
        for fila in filas:
            hoja.append([fila.get(columna, "") or "" for columna in COLUMNAS_OFICIALES])
    if not zonas:
        # Un libro sin ninguna hoja no se puede abrir. Mejor un archivo vacío con la
        # estructura que un archivo corrupto.
        hoja = libro.create_sheet(nombre_hoja_respaldo[:31] or "Inventario")
        _encabezado(hoja, COLUMNAS_OFICIALES)
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def escribir_tablas(
    hojas: dict[str, list[dict[str, Any]]], titulos: dict[str, list[str]] | None = None
) -> bytes:
    """Crea un libro con varias hojas a partir de listas de diccionarios."""
    libro = Workbook()
    libro.remove(libro.active)
    usados: set[str] = set()
    for nombre, filas in hojas.items():
        columnas = (titulos or {}).get(nombre) or (list(filas[0].keys()) if filas else [])
        base = re.sub(r'[:\\/?*\[\]]', ' ', nombre).strip().strip("'")[:31] or 'Sin zona'
        titulo = base
        contador = 2
        while titulo.casefold() in usados:
            sufijo = f' ({contador})'
            titulo = base[:31 - len(sufijo)] + sufijo
            contador += 1
        usados.add(titulo.casefold())
        hoja = libro.create_sheet(titulo)
        _encabezado(hoja, columnas)
        for fila in filas:
            hoja.append([_valor_tabular(fila.get(columna)) for columna in columnas])
        hoja.auto_filter.ref = hoja.dimensions
        hoja.print_title_rows = '1:1'
        hoja.sheet_view.showGridLines = False
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
        hoja.page_setup.orientation = 'landscape'
        hoja.page_setup.paperSize = hoja.PAPERSIZE_A4
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0
        for celdas in hoja.iter_rows(min_row=2):
            for celda in celdas:
                celda.alignment = Alignment(vertical='top', wrap_text=True)
                if isinstance(celda.value, datetime):
                    celda.number_format = 'dd/mm/yyyy hh:mm'
                elif isinstance(celda.value, date):
                    celda.number_format = 'dd/mm/yyyy'
        for indice, columna in enumerate(columnas, 1):
            ancho = max([len(columna)] + [min(45, len(str(fila.get(columna) or ''))) for fila in filas[:200]]) + 2
            hoja.column_dimensions[get_column_letter(indice)].width = max(14, min(ancho, 45))
    if not hojas:
        libro.create_sheet("vacio")
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _valor_tabular(valor: Any) -> Any:
    if valor is None:
        return ''
    if isinstance(valor, (dict, list, tuple)):
        return json.dumps(valor, ensure_ascii=False, default=str)
    if isinstance(valor, str) and valor.startswith(('=', '+', '-', '@')):
        return "'" + valor
    return valor


def a_csv(filas: list[dict[str, Any]], columnas: list[str]) -> bytes:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\n")
    escritor.writerow(columnas)
    for fila in filas:
        escritor.writerow([_valor_tabular(fila.get(columna)) for columna in columnas])
    return buffer.getvalue().encode("utf-8-sig")
