"""Asistente de importacion de inventario desde Excel/CSV (hoja = zona).

Flujo: subir -> detectar -> mapear columnas -> previsualizar con reglas visibles
-> confirmar las filas válidas -> deshacer los lotes que solo crearon equipos.

Principios: los campos vacios NUNCA son error de importacion (se importan como
"Pendiente"); los textos tipo "-" o "NO TIENE" se proponen como "No aplica"; la
importacion es idempotente usando el codigo patrimonial o, si no hay, la clave
compuesta (oficina + conjunto + dispositivo).
"""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Any

from bson import ObjectId

from app.core.audit import registrar
from app.domain.equipos import componente_escritorio
from app.core.db import get_db
from app.core.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from app.core.ids import (
    clave,
    clave_oscura,
    limpiar_codigo_patrimonial,
    mcp_ip,
    mcp_mac,
    normalizar_texto,
)
from app.core.time import utcnow
from app.domain.constants import (
    CAMPO_NO_APLICA,
    CAMPO_PENDIENTE,
    CAMPOS_BASE,
    PATRON_CONJUNTO,
    PATRON_CONJUNTO_SEP,
    SINONIMOS_BASE_CONJUNTO,
)
from app.domain.permissions import tiene_permiso
from app.services import catalogo_service, excel_service, inventario_service, org_service, usuario_service

# Claves logicas -> posibles cabeceras en el archivo
DETECCION_AUTOMATICA: dict[str, list[str]] = {
    "area": ["area", "oficina", "dependencia", "unidad", "direccion", "area o unidad"],
    "tipo_equipo": ["tipo de equipo", "tipo_equipo", "tipo equipo", "grupo", "conjunto", "equipo", "nombre de equipo"],
    "dispositivo": ["dispositivo", "componente", "tipo de dispositivo", "device", "elemento"],
    "codigo_patrimonial": ["codigo patrimonial", "codigo", "patrimonial", "codigo de activo", "cod pat"],
    "marca": ["marca", "brand", "fabricante"],
    "modelo": ["modelo", "model"],
    "tamano_pantalla": ["tamano pantalla", "tamano", "pulgadas", "size", "pantalla"],
    "nombre_equipo": ["nombre equipo", "nombre de equipo", "nombre", "hostname", "equipo"],
    "procesador": ["procesador", "cpu", "procesable"],
    "memoria_ram": ["memoria ram", "ram", "memoria"],
    "almacenamiento": ["almacenamiento", "disco", "disco duro", "ssd", "hd"],
    "direccion_ip": ["direccion ip", "ip", "direccion ip publica", "ip address"],
    "direccion_mac": ["direccion mac", "mac", "mac address"],
    "propiedad": ["propiedad", "tipo de propiedad"],
    "estado": ["estado", "situacion"],
    "responsable": ["responsable", "asignado a", "usuario", "empleado", "titular"],
}

CAMPOS_SENSIBLES_NO_APLICA = ("codigo_patrimonial", "direccion_mac", "direccion_ip", "tamano_pantalla")

ESTADOS = {"subido", "analizado", "previsualizado", "confirmado", "deshecho", "error"}


async def _cargar_grupos_responsables_excel() -> list[dict[str, Any]]:
    """Agrupa responsables importados por oficina y propone coincidencias seguras."""
    db = get_db()
    activos = await db["activos"].find(
        {
            "importacion_lote": {"$exists": True},
            "responsable_id": None,
            "responsable_nombre": {"$nin": [None, ""]},
            "oficina_id": {"$ne": None},
            "activo": {"$ne": False},
        },
        {
            "_id": 1,
            "oficina_id": 1,
            "oficina_nombre": 1,
            "zona_id": 1,
            "zona_nombre": 1,
            "responsable_nombre": 1,
            "responsable_nombre_excel": 1,
        },
    ).to_list(None)
    grupos: dict[tuple[ObjectId, str], dict[str, Any]] = {}
    for activo in activos:
        original = normalizar_texto(activo.get("responsable_nombre_excel") or activo.get("responsable_nombre"))
        nombre_clave = clave_oscura(original)
        if not original or not nombre_clave:
            continue
        clave_grupo = (activo["oficina_id"], nombre_clave)
        grupo = grupos.setdefault(
            clave_grupo,
            {
                "clave": f"{activo['oficina_id']}:{nombre_clave}",
                "oficina_id": activo["oficina_id"],
                "oficina_nombre": activo.get("oficina_nombre") or "Sin oficina",
                "zona_id": activo.get("zona_id"),
                "zona_nombre": activo.get("zona_nombre"),
                "nombre_original": original,
                "nombres_originales": set(),
                "activos": [],
            },
        )
        grupo["nombres_originales"].add(original)
        grupo["activos"].append(activo)

    ids_oficinas = list({oficina_id for oficina_id, _ in grupos})
    usuarios = await db["usuarios"].find(
        {"oficina_id": {"$in": ids_oficinas}, "activo": True},
        {"_id": 1, "nombre": 1, "oficina_id": 1},
    ).to_list(None) if ids_oficinas else []
    por_oficina: dict[ObjectId, list[dict[str, Any]]] = {}
    for persona in usuarios:
        por_oficina.setdefault(persona["oficina_id"], []).append(persona)

    resultado = []
    for grupo in grupos.values():
        objetivo = clave_oscura(grupo["nombre_original"])
        candidatos = []
        for persona in por_oficina.get(grupo["oficina_id"], []):
            nombre = persona.get("nombre", "")
            normalizado = clave_oscura(nombre)
            similitud = SequenceMatcher(None, objetivo, normalizado).ratio() if objetivo and normalizado else 0
            if normalizado == objetivo:
                coincidencia = "exacta"
            elif similitud >= 0.72:
                coincidencia = "parecida"
            else:
                continue
            candidatos.append(
                {"id": str(persona["_id"]), "nombre": nombre, "coincidencia": coincidencia, "similitud": round(similitud, 2)}
            )
        candidatos.sort(key=lambda persona: (persona["coincidencia"] != "exacta", -persona["similitud"], persona["nombre"]))
        resultado.append(
            {
                "clave": grupo["clave"],
                "oficina_id": str(grupo["oficina_id"]),
                "oficina_nombre": grupo["oficina_nombre"],
                "zona_id": str(grupo["zona_id"]) if grupo.get("zona_id") else None,
                "zona_nombre": grupo.get("zona_nombre"),
                "nombre_original": grupo["nombre_original"],
                "nombres_originales": sorted(grupo["nombres_originales"]),
                "equipos": len(grupo["activos"]),
                "candidatos": candidatos,
                "_activos": [activo["_id"] for activo in grupo["activos"]],
            }
        )
    resultado.sort(key=lambda grupo: (clave(grupo["oficina_nombre"]), clave_oscura(grupo["nombre_original"])))
    return resultado


async def listar_responsables_excel() -> list[dict[str, Any]]:
    return [
        {campo: valor for campo, valor in grupo.items() if campo != "_activos"}
        for grupo in await _cargar_grupos_responsables_excel()
    ]


async def _sincronizar_responsables_conjuntos(conjunto_ids, *, usuario: dict[str, Any]) -> None:
    """Una PC completa sigue al mismo responsable de sus componentes activos."""
    db = get_db()
    for conjunto_id in set(conjunto_ids):
        componentes = await db["activos"].find(
            {"conjunto_id": conjunto_id, "activo": {"$ne": False}}, {"responsable_id": 1}
        ).to_list(None)
        responsables = {componente.get("responsable_id") for componente in componentes}
        if len(responsables) != 1:
            continue
        responsable_id = next(iter(responsables))
        conjunto = await db["conjuntos"].find_one({"_id": conjunto_id})
        if conjunto and conjunto.get("responsable_id") != responsable_id:
            await inventario_service.cambiar_responsable(
                "conjunto", conjunto_id, responsable_id, usuario=usuario,
                motivo="Responsable común de los componentes confirmado desde el Excel",
            )


async def confirmar_responsables_excel(
    selecciones: list[dict[str, str]], *, usuario: dict[str, Any]
) -> dict[str, Any]:
    """Vincula en lote responsables del Excel o crea perfiles sin credenciales."""
    db = get_db()
    grupos = await _cargar_grupos_responsables_excel()
    por_clave = {grupo["clave"]: grupo for grupo in grupos}
    elegidas: dict[str, ObjectId | None] = {}
    for seleccion in selecciones:
        clave_grupo = seleccion.get("clave", "")
        if clave_grupo in elegidas or clave_grupo not in por_clave:
            raise Validacion("La selección de responsables del Excel no es válida o está repetida.")
        grupo = por_clave[clave_grupo]
        usuario_id = seleccion.get("usuario_id", "")
        if usuario_id == "crear":
            elegidas[clave_grupo] = None
            continue
        try:
            persona_id = ObjectId(usuario_id)
        except Exception as exc:
            raise Validacion("Selecciona una persona existente o crea un perfil sin cuenta.") from exc
        if not any(candidato["id"] == str(persona_id) for candidato in grupo["candidatos"]):
            raise Validacion("La persona seleccionada no coincide con las sugerencias de su oficina.")
        elegidas[clave_grupo] = persona_id
    if set(elegidas) != set(por_clave):
        raise Validacion("Confirma una opción para cada responsable antes de continuar.")

    vinculados = 0
    creados = 0
    # Uno por persona, para que la pantalla pueda decir **qué hizo con cada una**.
    # Antes solo volvían dos contadores: se sabía que se habían creado seis
    # personas, pero no cuáles ni en qué zona, y en la pantalla final no quedaba
    # rastro. Con la lista, lo hecho se puede revisar y corregir.
    detalle: list[dict[str, Any]] = []
    conjuntos_actualizados: set[ObjectId] = set()
    for clave_grupo, grupo in por_clave.items():
        responsable_id = elegidas[clave_grupo]
        if responsable_id is None:
            persona = await usuario_service.crear(
                {
                    "nombre": grupo["nombre_original"],
                    "oficina_id": grupo["oficina_id"],
                    "zona_id": grupo["zona_id"],
                    "rol": "usuario",
                },
                usuario=usuario,
            )
            responsable_id = persona["_id"]
            creados += 1
            accion = "creado"
            persona_nombre = persona.get("nombre")
            coincidencia = None
            similitud = None
        else:
            elegido = next((c for c in grupo["candidatos"] if c["id"] == str(responsable_id)), None)
            persona_nombre = (elegido or {}).get("nombre")
            coincidencia = (elegido or {}).get("coincidencia")
            similitud = (elegido or {}).get("similitud")
            accion = "vinculado"
        equipos_del_grupo = 0
        for activo_id in grupo["_activos"]:
            activo = await db["activos"].find_one({"_id": activo_id}, {"responsable_nombre": 1, "conjunto_id": 1})
            if activo is None:
                continue
            await db["activos"].update_one(
                {"_id": activo_id},
                {"$set": {"responsable_nombre_excel": activo.get("responsable_nombre_excel") or activo.get("responsable_nombre")}},
            )
            await inventario_service.cambiar_responsable(
                "activo", activo_id, responsable_id, usuario=usuario, motivo="Vinculado desde el Excel"
            )
            await db["activos"].update_one(
                {"_id": activo_id}, {"$set": {"responsable_vinculado": True}}
            )
            vinculados += 1
            equipos_del_grupo += 1
            if activo.get("conjunto_id"):
                conjuntos_actualizados.add(activo["conjunto_id"])
        detalle.append(
            {
                "clave": clave_grupo,
                "nombre_excel": grupo["nombre_original"],
                "nombre_asignado": persona_nombre,
                "usuario_id": str(responsable_id),
                "accion": accion,
                "oficina_nombre": grupo.get("oficina_nombre"),
                "zona_nombre": grupo.get("zona_nombre"),
                "coincidencia": coincidencia,
                "similitud": similitud,
                "equipos": equipos_del_grupo,
                # Sospechoso cuando el nombre del Excel es el mismo que el de la
                # oficina: en estos libros es habitual que la columna de
                # responsable venga con el nombre del área y no con el de alguien.
                "nombre_parece_oficina": bool(
                    grupo.get("oficina_nombre")
                    and clave_oscura(grupo["oficina_nombre"]) == clave_oscura(grupo["nombre_original"])
                ),
            }
        )
    await _sincronizar_responsables_conjuntos(conjuntos_actualizados, usuario=usuario)
    detalle.sort(key=lambda fila: (clave(fila["oficina_nombre"] or ""), clave(fila["nombre_excel"])))
    return {"personas_creadas": creados, "equipos_vinculados": vinculados, "detalle": detalle}


def _normalizar_cabecera(texto: str) -> str:
    return clave(texto).lower()


def _clave_canonica(texto: str) -> str:
    return clave(texto).lower().replace(" ", "")


def _coincide(cabecera: str, alias: str) -> float | None:
    """Cuanto encaja un alias con una cabecera (0 = nada, 1 = exacta).

    La comparacion respeta palabras completas: asi la columna "TIPO" no se
    confunde con el alias "IP" ni "CPU" con "ocupado".
    """
    if _clave_canonica(cabecera) == _clave_canonica(alias):
        return 1.0
    if len(_clave_canonica(alias)) <= 3:
        # Alias muy cortos (IP, MAC, SSD) solo valen si coinciden exactamente
        return None
    patron = r"(?:^|\s)" + re.escape(" ".join(str(alias).lower().split())) + r"(?:\s|$)"
    if re.search(patron, cabecera):
        return 0.75
    return None


def detectar_mapeo(cabeceras: list[str]) -> dict[str, dict[str, Any]]:
    """Detecta que columna del archivo corresponde a cada campo logico."""
    preparadas = [(indice, _normalizar_cabecera(c)) for indice, c in enumerate(cabeceras) if normalizar_texto(c)]
    mapeo: dict[str, dict[str, Any]] = {}
    usadas: set[int] = set()
    for campo, alias in DETECCION_AUTOMATICA.items():
        mejor: tuple[int, int, float] | None = None
        for indice, normalizada in preparadas:
            if indice in usadas:
                continue
            for posicion, alias_texto in enumerate(alias):
                base = _coincide(normalizada, alias_texto)
                if base is None:
                    continue
                # A igualdad de acierto gana el alias mas corto y exacto
                confianza = base - posicion * 0.01
                if mejor is None or confianza > mejor[2]:
                    mejor = (indice, posicion, confianza)
                if base == 1.0:
                    break
            if mejor is not None and mejor[0] == indice and mejor[2] >= 1.0:
                break
        if mejor:
            indice, posicion, confianza = mejor
            usadas.add(indice)
            mapeo[campo] = {
                "columna": cabeceras[indice],
                "indice": indice,
                "confianza": round(confianza, 2),
                "alias": alias[min(posicion, len(alias) - 1)],
                "requerido": campo in {"area", "dispositivo"},
            }
    return mapeo


async def subir(contenido: bytes, nombre_archivo: str, *, usuario: dict[str, Any]) -> dict[str, Any]:
    """1. Subir. Devuelve el analisis inicial (hojas, zonas, oficinas, columnas)."""
    hojas = excel_service.leer_archivo(contenido, nombre_archivo)
    db = get_db()
    analisis_hojas: list[dict[str, Any]] = []
    total_filas = 0
    for nombre_hoja, filas in hojas.items():
        cabeceras, registros = excel_service.hoja_a_registros(filas)
        if not registros:
            analisis_hojas.append(
                {
                    "nombre_hoja": nombre_hoja,
                    "zona_nombre": normalizar_texto(nombre_hoja).upper(),
                    "filas": 0,
                    "oficinas": [],
                    "oficinas_existentes": [],
                    "oficinas_nuevas": [],
                    "advertencia": "La hoja no tiene filas de datos.",
                }
            )
            continue
        mapeo = detectar_mapeo(cabeceras)
        area_columna = mapeo.get("area", {}).get("columna")
        oficinas: list[str] = []
        anterior = ""
        for registro in registros:
            valor = normalizar_texto(registro.get(area_columna, "")) if area_columna else ""
            valor = _sin_dato(valor)
            if not valor:
                valor = anterior  # relleno hacia abajo tambien para AREA
            else:
                anterior = valor
            if valor and valor not in oficinas:
                oficinas.append(valor)
        zona_nombre = normalizar_texto(nombre_hoja).upper()
        zona = await db["zonas"].find_one({"nombre_normalizado": clave(zona_nombre)})
        existentes: list[str] = []
        nuevas: list[str] = []
        if zona:
            for oficina in oficinas:
                existe = await db["oficinas"].find_one(
                    {"zona_id": zona["_id"], "nombre_normalizado": clave(oficina)}
                )
                (existentes if existe else nuevas).append(oficina)
        else:
            nuevas = list(oficinas)
        total_filas += len(registros)
        analisis_hojas.append(
            {
                "nombre_hoja": nombre_hoja,
                "zona_nombre": zona_nombre,
                "zona_id": str(zona["_id"]) if zona else None,
                "zona_existe": bool(zona),
                "filas": len(registros),
                "oficinas": oficinas,
                "oficinas_existentes": existentes,
                "oficinas_nuevas": nuevas,
            }
        )
    if total_filas == 0:
        raise Validacion("El archivo no contiene filas de datos para importar.")

    # El sufijo aleatorio evita colisiones si se suben dos archivos en el mismo segundo
    lote_id = f"IMP-{utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"
    documento = {
        "lote_id": lote_id,
        "nombre_archivo": nombre_archivo,
        "estado": "analizado",
        "usuario_id": usuario.get("_id"),
        "usuario_nombre": usuario.get("nombre", ""),
        "creado_en": utcnow(),
        "analisis": {
            "nombre_archivo": nombre_archivo,
            "hojas": analisis_hojas,
            "filas_totales": total_filas,
            "columnas_por_hoja": {
                nombre_hoja: excel_service.hoja_a_registros(filas)[0]
                for nombre_hoja, filas in hojas.items()
            },
        },
        "mapeo": {nombre_hoja: detectar_mapeo(excel_service.hoja_a_registros(filas)[0]) for nombre_hoja, filas in hojas.items()},
        "ajustes": {},
        "filas": {
            nombre_hoja: excel_service.hoja_a_registros(filas)[1] for nombre_hoja, filas in hojas.items()
        },
        "resumen": {},
        "creados": [],
        "actualizados": [],
        "omtidos": [],
        "reversible": True,
    }
    await db["importaciones"].insert_one(documento)
    await registrar(
        "importacion.subir",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="importacion",
        entidad_id=lote_id,
        resumen=f"Archivo subido: {nombre_archivo} ({total_filas} filas)",
        despues={"lote": lote_id, "hojas": [h["nombre_hoja"] for h in analisis_hojas]},
    )
    columnas = excel_service.COLUMNAS_OFICIALES
    return {
        "lote_id": lote_id,
        "nombre_archivo": nombre_archivo,
        "hojas": analisis_hojas,
        "filas_totales": total_filas,
        "columnas_disponibles": columnas,
        "columnas_detectadas": list((next(iter(documento["mapeo"].values())) or {}).keys()),
    }


async def obtener_lote(lote_id: str) -> dict[str, Any]:
    documento = await get_db()["importaciones"].find_one({"lote_id": lote_id})
    if documento is None:
        raise NoEncontrado("No se encontro el lote de importacion. Vuelve a subir el archivo.")
    return documento


async def guardar_ajustes(lote_id: str, ajustes: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    """Ajustes manuales: renombrar zona, fusionar con zona existente, correccion de mapeo."""
    documento = await obtener_lote(lote_id)
    actual = dict(documento.get("ajustes") or {})
    for nombre_hoja, config in (ajustes or {}).items():
        actual[nombre_hoja] = {
            "zona_nombre": normalizar_texto(config.get("zona_nombre") or "") or None,
            "fusionar_con_zona": config.get("fusionar_con_zona"),
            "crear_zona": bool(config.get("crear_zona", True)),
            "mapeo": config.get("mapeo") or {},
            "excluir": bool(config.get("excluir", False)),
        }
    if ajustes and "mapeo_global" in (ajustes or {}):
        for nombre_hoja in documento.get("mapeo", {}):
            actual.setdefault(nombre_hoja, {})["mapeo"] = ajustes["mapeo_global"]
    await get_db()["importaciones"].update_one(
        {"lote_id": lote_id}, {"$set": {"ajustes": actual, "estado": "analizado", "actualizado_en": utcnow()}}
    )
    return {"lote_id": lote_id, "ajustes": actual}


async def guardar_mapeo_reutilizable(ajustes: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    """Guarda el mapeo de columnas como predeterminado para las proximas importaciones."""
    global_mapeo = (ajustes or {}).get("mapeo_global")
    if not global_mapeo:
        raise Validacion("Define primero el mapeo de columnas.")
    await get_db()["configuracion"].update_one(
        {"_id": "config"},
        {"$set": {"inventario.mapeo_columnas": global_mapeo, "inventario.mapeo_guardado_en": utcnow()}},
        upsert=True,
    )
    await registrar(
        "importacion.subir",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="configuracion",
        entidad_id="inventario.mapeo_columnas",
        resumen="Mapeo de columnas guardado para futuras importaciones",
        despues={"mapeo": global_mapeo},
    )
    return {"mapeo": global_mapeo}


async def _resolucion_hoja(
    nombre_hoja: str, documento: dict[str, Any], *, usuario: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Resuelve la zona destino de una hoja (crea si el administrador lo permite)."""
    db = get_db()
    ajustes = (documento.get("ajustes") or {}).get(nombre_hoja) or {}
    analisis = next((h for h in documento["analisis"]["hojas"] if h["nombre_hoja"] == nombre_hoja), {})
    zona_nombre = ajustes.get("zona_nombre") or analisis.get("zona_nombre") or normalizar_texto(nombre_hoja).upper()
    fusionar = ajustes.get("fusionar_con_zona")
    if fusionar:
        zona = await db["zonas"].find_one({"_id": ObjectId(str(fusionar))})
        if zona:
            return zona, ajustes
    zona = await db["zonas"].find_one({"nombre_normalizado": clave(zona_nombre)})
    if zona:
        return zona, ajustes
    if ajustes.get("crear_zona", True):
        nuevo = await org_service.crear_zona({"nombre": zona_nombre}, usuario=usuario)
        zona = await db["zonas"].find_one({"_id": nuevo})
        return zona, ajustes
    raise Prohibido(
        f"La zona '{zona_nombre}' no existe. Activa la creacion de zonas o elige una existente.",
        detalles={"hoja": nombre_hoja, "zona": zona_nombre},
    )


def _sin_dato(texto: str) -> str:
    """Devuelve '' si el texto significa 'no aplica'."""
    limpio = normalizar_texto(texto)
    if not limpio:
        return ""
    if re.fullmatch(r"[-–—/.]+", limpio):
        return ""
    if limpio.upper() in {"N/A", "NA", "S/N", "SN", "NO TIENE", "SIN CODIGO", "SIN CÓDIGO", "NINGUNO", "PENDIENTE", "-"}:
        return ""
    return limpio


async def _preparar_filas(
    documento: dict[str, Any], *, usuario: dict[str, Any], filas_excluidas: list[int] | None = None
) -> dict[str, Any]:
    """Aplica reglas de normalizacion y devuelve filas con advertencias/errores."""
    db = get_db()
    filas_excluidas = set(filas_excluidas or [])
    sinonimos = await catalogo_service.mapa_sinonimos()
    tipos_conocidos = {clave(t): t for t in await catalogo_service.tipos_existentes()}
    usuarios_por_oficina: dict[str, list[dict[str, Any]]] = {}
    filas: list[dict[str, Any]] = []
    reglas = [
        "Se recortan espacios sobrantes, incluidos los no separables.",
        "Se comparan textos sin tildes ni mayusculas para evitar duplicados (HP, Hp, hp).",
        "El nombre de cada hoja se toma como ZONA y la columna AREA como OFICINA.",
        "'Tipo de equipo' se rellena hacia abajo dentro de la misma oficina.",
        "Los sinonimos de dispositivo se corrigen con el diccionario editable (por ejemplo MAUSE -> Mouse).",
        "Los textos '-', 'N/A', 'S/N', 'NO TIENE' y 'SIN CODIGO' equivalen a 'No aplica'.",
        "Se reconoce primero el patrimonio o la MAC; la ubicación solo se usa si identifica un único equipo.",
        "Los equipos indistinguibles se dejan para revisión: no se emparejan por el orden de las filas.",
        "Las celdas vacias se importan como 'Pendiente': nunca son un error.",
        "Si no hay responsable, el equipo queda como uso comun de la oficina.",
    ]

    for nombre_hoja, registros in (documento.get("filas") or {}).items():
        ajustes = (documento.get("ajustes") or {}).get(nombre_hoja) or {}
        if ajustes.get("excluir"):
            continue
        zona, _ = await _resolucion_hoja(nombre_hoja, documento, usuario=usuario)
        mapeo = dict(documento.get("mapeo", {}).get(nombre_hoja) or {})
        mapeo.update(ajustes.get("mapeo") or {})
        area_columna = (mapeo.get("area") or {}).get("columna")

        oficina_anterior = ""
        grupo_anterior = ""
        grupo_oficina_anterior = None
        indice_tipo = 0

        for registro in registros:
            numero = int(registro.get("__fila__", 0))
            advertencias: list[str] = []
            errores: list[str] = []
            no_aplica_sugeridos: list[str] = []
            observaciones: list[str] = []

            def valor(campo: str) -> str:
                columna = (mapeo.get(campo) or {}).get("columna")
                if not columna:
                    return ""
                return normalizar_texto(registro.get(columna, ""))

            oficina = _sin_dato(valor("area")) or oficina_anterior
            if oficina:
                oficina_anterior = oficina
            if not oficina:
                errores.append("No se pudo determinar la oficina (columna AREA vacia).")

            grupo_crudo = _sin_dato(valor("tipo_equipo"))
            if grupo_crudo:
                grupo_anterior = grupo_crudo
                grupo_oficina_anterior = oficina
                indice_tipo = 0
            grupo = grupo_anterior
            if grupo and oficina != grupo_oficina_anterior:
                grupo = ""
            if not grupo:
                advertencias.append("La fila no indica 'Tipo de equipo': se importara como equipo individual.")

            dispositivo_crudo = valor("dispositivo")
            dispositivo = _sin_dato(dispositivo_crudo)
            tipo = _resolver_tipo(dispositivo, sinonimos, tipos_conocidos)
            if not dispositivo:
                tipo = "Por identificar"
                advertencias.append("La columna 'Dispositivo' esta vacia: se conserva como 'Por identificar'.")
            elif tipo not in tipos_conocidos.values():
                advertencias.append(f"Tipo '{dispositivo}' no esta en el catalogo; se creara como '{tipo}'.")

            conjunto_nombre, conjunto_numero = _resolver_conjunto(grupo)
            es_individual = not grupo or (dispositivo and grupo and _patron_conjunto(grupo) is None)
            if grupo and _patron_conjunto(grupo) is not None:
                indice_tipo += 1
            if grupo and _patron_conjunto(grupo) is not None:
                etiqueta_conjunto = conjunto_nombre
            else:
                etiqueta_conjunto = None

            codigo = limpiar_codigo_patrimonial(valor("codigo_patrimonial"))
            if valor("codigo_patrimonial") and not codigo:
                no_aplica_sugeridos.append("codigo_patrimonial")

            ip_crudo = valor("direccion_ip")
            conexion_usb = clave(tipo) == 'IMPRESORA' and clave(ip_crudo) in {'CABLE USB', 'USB'}
            ip = 'Cable USB' if conexion_usb else mcp_ip(ip_crudo) if ip_crudo else None
            if ip_crudo and not ip:
                if _es_texto_sin_dato(ip_crudo):
                    no_aplica_sugeridos.append("direccion_ip")
                    advertencias.append(f"La IP '{ip_crudo}' no es una direccion valida: se dejara como pendiente.")
                else:
                    advertencias.append(f"Direccion IP invalida: '{ip_crudo}': queda pendiente.")
                    observaciones.append(f"IP original del Excel: {ip_crudo}")

            mac_crudo = valor("direccion_mac")
            mac = mcp_mac(mac_crudo) if mac_crudo else None
            if mac_crudo and not mac:
                if _es_texto_sin_dato(mac_crudo):
                    no_aplica_sugeridos.append("direccion_mac")
                    advertencias.append(f"La MAC '{mac_crudo}' no tiene un formato valido: se dejara como pendiente.")
                else:
                    advertencias.append(f"Direccion MAC invalida: '{mac_crudo}': queda pendiente.")
                    observaciones.append(f"MAC original del Excel: {mac_crudo}")

            responsable_crudo = _sin_dato(valor("responsable"))
            estado_texto = _sin_dato(valor("estado")) or "Operativo"
            propiedad = _sin_dato(valor("propiedad"))
            if clave(propiedad or '') == 'PERSONAL':
                codigo = None
                if 'codigo_patrimonial' not in no_aplica_sugeridos:
                    no_aplica_sugeridos.append('codigo_patrimonial')
            if not propiedad:
                advertencias.append("Sin propiedad indicada: se usará 'Institucional'.")

            fila = {
                "numero": numero,
                "lote_id": documento.get("lote_id"),
                "hoja": nombre_hoja,
                "grupo_crudo": grupo,
                "zona_id": str(zona["_id"]),
                "zona_nombre": zona["nombre"],
                "oficina_nombre": oficina,
                "conjunto_nombre": etiqueta_conjunto,
                "conjunto_numero": conjunto_numero,
                "es_conjunto": bool(etiqueta_conjunto),
                "tipo": tipo or dispositivo,
                "dispositivo_original": dispositivo_crudo,
                "codigo_patrimonial": codigo,
                "marca": _sin_dato(valor("marca")) or None,
                "modelo": _sin_dato(valor("modelo")) or None,
                "tamano_pantalla": _sin_dato(valor("tamano_pantalla")) or None,
                "nombre_equipo": _sin_dato(valor("nombre_equipo")) or None,
                "nombre_equipo_original": _sin_dato(valor("nombre_equipo")) or None,
                "procesador": _sin_dato(valor("procesador")) or None,
                "memoria_ram": _sin_dato(valor("memoria_ram")) or None,
                "almacenamiento": _sin_dato(valor("almacenamiento")) or None,
                "direccion_ip": ip,
                "direccion_mac": mac,
                "propiedad": propiedad or "Institucional",
                "estado": estado_texto,
                "responsable_nombre": responsable_crudo or None,
                "responsable_nombre_original": responsable_crudo or None,
                "advertencias": advertencias,
                "errores": errores,
                "campos_no_aplica_sugeridos": no_aplica_sugeridos,
                "excluida": numero in filas_excluidas,
                "accion": "crear",
                "detalle": [],
                "observaciones": "; ".join(observaciones) or None,
            }

            filas.append(fila)

    # Un grupo con un solo dispositivo se importa como equipo individual
    tamanos: dict[tuple[str, str, str], int] = {}
    for fila in filas:
        if not fila["grupo_crudo"]:
            fila["es_conjunto"] = False
            continue
        clave_grupo = (fila["hoja"], fila["oficina_nombre"], fila["grupo_crudo"])
        tamanos[clave_grupo] = tamanos.get(clave_grupo, 0) + 1
    for fila in filas:
        if not fila["grupo_crudo"]:
            continue
        clave_grupo = (fila["hoja"], fila["oficina_nombre"], fila["grupo_crudo"])
        fila["es_conjunto"] = bool(fila["conjunto_nombre"]) and tamanos[clave_grupo] > 1 and componente_escritorio(fila["tipo"])
        if not fila["es_conjunto"]:
            fila["conjunto_numero"] = None
            # El equipo individual conserva el nombre del grupo como nombre propio
            fila["nombre_equipo"] = fila["nombre_equipo"] or fila["grupo_crudo"]

    # Responsables: coincidencia por nombre dentro de la oficina
    for fila in filas:
        if not fila["responsable_nombre"]:
            fila["responsable_id"] = None
            fila["responsable_estado"] = "uso_comun"
            continue

        oficina = await db["oficinas"].find_one(
            {"zona_id": ObjectId(fila["zona_id"]), "nombre_normalizado": clave(fila["oficina_nombre"])}
        )
        if oficina is None:
            fila["advertencias"].append(f"Se creara la oficina '{fila['oficina_nombre']}' en {fila['zona_nombre']}.")
            fila["responsable_id"] = None
            fila["responsable_estado"] = "no_encontrado"
            continue
        fila["oficina_id"] = str(oficina["_id"])

        candidatos = await db["usuarios"].find(
            {"oficina_id": oficina["_id"], "activo": True, "archivado": {"$ne": True}}, {"nombre": 1}
        ).to_list(None)
        if not candidatos:
            fila["responsable_id"] = None
            fila["responsable_estado"] = "no_encontrado"
            continue
        objetivo = clave_oscura(fila["responsable_nombre"])
        exactos = [c for c in candidatos if clave_oscura(c.get("nombre", "")) == objetivo]
        parciales = [c for c in candidatos if objetivo and objetivo in clave_oscura(c.get("nombre", ""))]
        elegido = exactos[0] if len(exactos) == 1 else None
        if elegido:
            fila["responsable_id"] = str(elegido["_id"])
            fila["responsable_nombre"] = elegido.get("nombre")
            fila["responsable_estado"] = "encontrado"
        elif parciales:
            fila["responsable_estado"] = "ambiguo"
            fila["responsable_candidatos"] = [c.get("nombre") for c in parciales]
            fila["advertencias"].append(
                f"Hay varias personas con un nombre parecido a '{fila['responsable_nombre']}': confirma cual es."
            )
        else:
            fila["responsable_estado"] = "no_encontrado"
            fila["advertencias"].append(
                f"No se encontro a '{fila['responsable_nombre']}' en {fila['oficina_nombre']}: el equipo quedara sin responsable."
            )

    return {"filas": filas, "reglas_aplicadas": reglas}


def _es_texto_sin_dato(texto: str) -> bool:
    limpio = normalizar_texto(texto).upper()
    return limpio in {"N/A", "NA", "S/N", "SN", "NO TIENE", "NO APLICA", "NO DISPONIBLE", "NINGUNO", "-", "--", "PENDIENTE"}


def _patron_conjunto(grupo: str) -> dict[str, str] | None:
    texto = normalizar_texto(grupo)
    for patron in (PATRON_CONJUNTO, PATRON_CONJUNTO_SEP):
        coincidencia = re.match(patron, texto, flags=re.IGNORECASE)
        if coincidencia:
            return {
                "base": SINONIMOS_BASE_CONJUNTO.get(clave(coincidencia.group("base")), coincidencia.group("base").title()),
                "numero": coincidencia.group("numero"),
            }
    return None


def _resolver_conjunto(grupo: str) -> tuple[str | None, int | None]:
    if not grupo:
        return None, None
    patron = _patron_conjunto(grupo)
    if patron:
        return f"{patron['base']} N°{patron['numero']}", int(patron["numero"])
    texto = normalizar_texto(grupo)
    return texto, None


def _resolver_tipo(dispositivo: str, sinonimos: dict[str, str], tipos_conocidos: dict[str, str]) -> str | None:
    if not dispositivo:
        return None
    clave_dispositivo = clave(dispositivo)
    if clave_dispositivo in sinonimos:
        dispositivo = sinonimos[clave_dispositivo]
        clave_dispositivo = clave(dispositivo)
    if clave_dispositivo in tipos_conocidos:
        return tipos_conocidos[clave_dispositivo]
    for clave_tipo, nombre in tipos_conocidos.items():
        if clave_tipo and clave_tipo in clave_dispositivo:
            return nombre
    return normalizar_texto(dispositivo)


async def _identificar_equipo(fila: dict[str, Any], repetidas: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resuelve patrimonio sin usar al trabajador ni el orden del archivo."""
    db = get_db()
    codigo, mac = fila.get("codigo_patrimonial"), fila.get("direccion_mac")
    por_codigo = await db.activos.find({"codigo_patrimonial": codigo}).limit(3).to_list(None) if codigo else []
    por_mac = await db.activos.find({"direccion_mac": mac}).limit(3).to_list(None) if mac else []
    existente = None
    if len(por_codigo) > 1:
        if len(por_mac) == 1 and por_mac[0]["_id"] in {c["_id"] for c in por_codigo}:
            existente = por_mac[0]
        else:
            fila["errores"].append("El patrimonio coincide con varios equipos. Corrige la identificación o añade su MAC única.")
            return None
    elif por_codigo:
        existente = por_codigo[0]
    if len(por_mac) > 1:
        fila["errores"].append("La MAC coincide con varios equipos. Revisa la identificación.")
        return None
    if por_mac:
        candidato = por_mac[0]
        if (existente and candidato["_id"] != existente["_id"]) or (
            codigo and candidato.get("codigo_patrimonial") not in (None, "", codigo)
        ):
            fila["errores"].append("El patrimonio y la MAC identifican equipos diferentes. Revisa la fila.")
            return None
        existente = candidato
    if existente:
        fila["identificado_por"] = "Código patrimonial" if codigo and por_codigo else "Dirección MAC"
        return existente

    # Un nombre explícito o la etiqueta del dispositivo individual distingue
    # equipos iguales. Para componentes de PC se usa el conjunto y el tipo.
    nombre = fila.get("nombre_equipo_original") or (fila.get("nombre_equipo") if not fila["es_conjunto"] else None)
    nombre_unico = bool(nombre) and sum(
        clave(f.get("nombre_equipo_original") or (f.get("nombre_equipo") if not f["es_conjunto"] else "") or "") == clave(nombre)
        for f in repetidas
    ) == 1
    if not codigo and not mac and len(repetidas) > 1 and not nombre_unico:
        fila["errores"].append("Hay varios dispositivos iguales sin identificación. Usa nombres únicos, patrimonio o MAC.")
        return None
    if nombre_unico:
        fila["clave_natural_preview"] = f"{fila['clave_natural_preview'].rsplit('#', 1)[0]}|nombre|{clave(nombre)}"

    oficina = await db.oficinas.find_one({
        "zona_id": ObjectId(fila["zona_id"]), "nombre_normalizado": clave(fila["oficina_nombre"]),
    })
    if not oficina:
        return None
    candidatos = await db.activos.find({
        "oficina_id": oficina["_id"],
        "$or": [{"tipo_normalizado": clave(fila["tipo"])}, {"tipo": fila["tipo"]}],
    }).to_list(None)
    grupo = clave(fila.get("conjunto_nombre") or "") if fila["es_conjunto"] else ""
    candidatos = [c for c in candidatos if clave(c.get("conjunto_nombre") or "") == grupo]
    # Un identificador nuevo no sustituye al patrimonio distinto de otro equipo.
    candidatos = [c for c in candidatos if
        (not codigo or not c.get("codigo_patrimonial") or c["codigo_patrimonial"] == codigo) and
        (not mac or not c.get("direccion_mac") or c["direccion_mac"] == mac)]
    por_nombre = [c for c in candidatos if nombre and clave(c.get("nombre_equipo") or "") == clave(nombre)]
    if nombre_unico and len(por_nombre) == 1:
        fila["identificado_por"] = "Nombre del equipo y ubicación"
        return por_nombre[0]
    if len(por_nombre) > 1 or len(candidatos) > 1:
        fila["errores"].append("La fila coincide con varios equipos existentes. Añade patrimonio o MAC para distinguirlos.")
        return None
    if candidatos and nombre and candidatos[0].get("nombre_equipo") and not por_nombre:
        fila["errores"].append("El nombre no coincide con el equipo existente. Confirma su identidad en la ficha antes de importar.")
        return None
    if candidatos and (len(repetidas) == 1 or nombre_unico and por_nombre):
        fila["identificado_por"] = "Ubicación y dispositivo únicos"
        return candidatos[0]
    if candidatos and not codigo and not mac:
        fila["errores"].append("No se puede distinguir el equipo existente. Revisa su nombre o identificación.")
    return None


async def previsualizar(
    lote_id: str, *, filas_excluidas: list[int] | None = None, no_aplicar_confirmado: list[str] | None = None, usuario: dict[str, Any]
) -> dict[str, Any]:
    """5. Vista previa + validacion + simulacion (dry-run)."""
    documento = await obtener_lote(lote_id)
    preparacion = await _preparar_filas(documento, usuario=usuario, filas_excluidas=filas_excluidas)
    filas = preparacion["filas"]
    db = get_db()
    confirmado = set(no_aplicar_confirmado or [])

    # El responsable no identifica el patrimonio. Dos filas sin identificador
    # tampoco se distinguen solamente por su posición al ordenar otro Excel.
    grupos: dict[str, list[dict[str, Any]]] = {}
    for fila in filas:
        if fila["excluida"]:
            continue
        base = f"{fila['zona_nombre']}|{fila['oficina_nombre']}|{fila['conjunto_nombre'] or '-'}|{clave(fila['tipo'])}"
        grupos.setdefault(base, []).append(fila)

    # El ordinal se conserva como clave inicial de una fila nueva. Nunca se
    # utiliza por sí solo para elegir un equipo entre varios existentes.
    contadores: dict[str, int] = {}
    for fila in filas:
        fila["valida"] = not fila["errores"] and not fila["excluida"]
        base = f"{fila['zona_nombre']}|{fila['oficina_nombre']}|{fila['conjunto_nombre'] or '-'}|{clave(fila['tipo'])}"
        contadores[base] = contadores.get(base, 0) + 1
        fila["clave_natural_preview"] = f"{base}#{contadores[base]}"
        fila["ordinal_grupo"] = contadores[base]
        if fila["excluida"]:
            fila["accion"] = "omitir"
            continue
        if fila["errores"]:
            fila["accion"] = "omitir"
            continue
        codigo = fila.get("codigo_patrimonial")
        existente = await _identificar_equipo(fila, grupos[base])
        if existente:
            fila["accion"] = "actualizar"
            fila["existente_id"] = str(existente["_id"])
            fila["clave_natural_preview"] = existente["clave_natural"]
            fila["responsable_anterior"] = existente.get("responsable_nombre")
            fila["cambia_responsable"] = clave_oscura(existente.get("responsable_nombre") or "") != clave_oscura(fila.get("responsable_nombre") or "")
            if not codigo and existente.get("codigo_patrimonial") and clave(fila.get("propiedad") or "") != "PERSONAL":
                fila["codigo_patrimonial"] = existente["codigo_patrimonial"]
                fila["advertencias"].append("Se conserva el patrimonio existente que no está escrito en el archivo.")
            if not fila.get("direccion_mac") and existente.get("direccion_mac"):
                fila["direccion_mac"] = existente["direccion_mac"]
                fila["advertencias"].append("Se conserva la MAC existente que no está escrita en el archivo.")
        else:
            fila.pop("existente_id", None)
            fila["accion"] = "crear"
            if codigo:
                fila["clave_natural_preview"] = f"patrimonio|{codigo}"
            elif fila.get("direccion_mac"):
                fila["clave_natural_preview"] = f"mac|{fila['direccion_mac']}"
        if fila["accion"] != "actualizar":
            if not fila["codigo_patrimonial"]:
                fila["advertencias"].append(
                    "Sin patrimonio: se usará su MAC o una coincidencia única de ubicación, dispositivo y nombre."
                )
        campos_estado = {}
        for campo in CAMPOS_BASE:
            if campo in confirmado and campo in fila["campos_no_aplica_sugeridos"]:
                campos_estado[campo] = CAMPO_NO_APLICA
            elif campo in fila["campos_no_aplica_sugeridos"]:
                campos_estado[campo] = CAMPO_PENDIENTE
            else:
                campos_estado[campo] = CAMPO_PENDIENTE
        if clave(fila['tipo']) == 'IMPRESORA' and fila.get('direccion_ip') == 'Cable USB':
            campos_estado['direccion_ip'] = CAMPO_NO_APLICA
        if clave(fila.get('propiedad') or '') == 'PERSONAL':
            campos_estado['codigo_patrimonial'] = CAMPO_NO_APLICA
        fila["campos_estado"] = campos_estado
        fila["valida"] = not fila["errores"]

    # Una misma identidad no se puede sobrescribir con dos filas del lote.
    codigos: dict[str, list[dict[str, Any]]] = {}
    for fila in filas:
        if fila.get("codigo_patrimonial") and not fila["excluida"]:
            codigos.setdefault(fila["codigo_patrimonial"], []).append(fila)
    for repetidas in codigos.values():
        if len(repetidas) > 1:
            for fila in repetidas:
                fila["errores"].append("El código patrimonial está repetido en el archivo. Revisa esas filas antes de importarlas.")
    destinos: dict[str, list[dict[str, Any]]] = {}
    for fila in filas:
        if fila.get("existente_id") and not fila["excluida"]:
            destinos.setdefault(fila["existente_id"], []).append(fila)
    for repetidas in destinos.values():
        if len(repetidas) > 1:
            for fila in repetidas:
                fila["errores"].append("Dos filas identifican el mismo equipo existente. Conserva solo una.")

    # No permitir asignar una IP o MAC a dos dispositivos distintos.
    redes: dict[tuple[str, str], list[dict]] = {}
    for fila in filas:
        if fila['excluida']:
            continue
        for campo in ('direccion_ip', 'direccion_mac'):
            valor_red = fila.get(campo)
            if not valor_red or valor_red == 'Cable USB':
                continue
            redes.setdefault((campo, valor_red), []).append(fila)
            consulta_red = {campo: valor_red, 'activo': {'$ne': False}}
            if fila.get('existente_id'):
                consulta_red['_id'] = {'$ne': ObjectId(fila['existente_id'])}
            if await db['activos'].find_one(consulta_red, {'_id': 1}):
                fila['errores'].append(f'{campo} ya pertenece a otro equipo: {valor_red}.')
    for (campo, valor_red), repetidas in redes.items():
        if len(repetidas) > 1:
            ubicaciones = ', '.join(f"{f['hoja']} fila {f['numero']}" for f in repetidas)
            for fila in repetidas:
                fila['errores'].append(f'{campo} repetida ({valor_red}): {ubicaciones}.')
    for fila in filas:
        if fila['errores']:
            fila['valida'] = False
            fila['accion'] = 'omitir'

    resumen = {
        "total_filas": len(filas),
        "validas": sum(1 for f in filas if f["valida"]),
        "con_error": sum(1 for f in filas if f["errores"]),
        "con_advertencia": sum(1 for f in filas if f["advertencias"] and not f["errores"]),
        "crearia": sum(1 for f in filas if f["accion"] == "crear"),
        "actualizaria": sum(1 for f in filas if f["accion"] == "actualizar"),
        "omitiria": sum(1 for f in filas if f["accion"] in {"omitir"}),
    }
    sin_responsable = sorted(
        {
            f["responsable_nombre"]
            for f in filas
            if f["responsable_nombre"] and f["responsable_estado"] in {"no_encontrado", "ambiguo"}
        }
    )
    zonas = sorted({f["zona_nombre"] for f in filas})
    await db["importaciones"].update_one(
        {"lote_id": lote_id},
        {
            "$set": {
                "estado": "previsualizado",
                "previsualizacion": {"resumen": resumen, "generada_en": utcnow()},
                "previsualizacion_filas": filas,
                "no_aplicar_confirmado": sorted(confirmado),
                "filas_excluidas": sorted(filas_excluidas or []),
            }
        },
    )
    return {
        "lote_id": lote_id,
        "filas": filas,
        **resumen,
        "reglas_aplicadas": preparacion["reglas_aplicadas"],
        "sin_responsable": sin_responsable,
        "zonas": zonas,
    }


async def _confirmar_lote(
    lote_id: str,
    *,
    filas_excluidas: list[int] | None = None,
    no_aplicar_confirmado: list[str] | None = None,
    crear_usuarios_faltantes: bool = False,
    usuario: dict[str, Any],
) -> dict[str, Any]:
    """8. Importar las filas válidas; los errores individuales se muestran al terminar."""
    db = get_db()
    documento = await obtener_lote(lote_id)
    if documento.get("estado") == "confirmado":
        raise Conflicto("Esta importacion ya fue confirmada. Usa 'Deshacer' si necesitas revertirla.")
    previsualizacion = await previsualizar(
        lote_id,
        filas_excluidas=filas_excluidas or documento.get("filas_excluidas") or [],
        no_aplicar_confirmado=no_aplicar_confirmado or documento.get("no_aplicar_confirmado") or [],
        usuario=usuario,
    )
    filas = previsualizacion["filas"]
    importables = [f for f in filas if f["accion"] in {"crear", "actualizar"} and f["valida"]]

    creados: list[str] = []
    actualizados: list[str] = []
    omitidos: list[str] = []
    errores: list[str] = []
    conjuntos_creados = 0
    usuarios_creados = 0
    zonas_nuevas: list[str] = []
    oficinas_nuevas: list[str] = []
    cache_conjuntos: dict[str, ObjectId] = {}
    cache_oficinas: dict[str, ObjectId] = {}
    cache_responsables: dict[tuple[ObjectId, str], ObjectId] = {}

    try:
        async with db.client.start_session() as sesion:  # type: ignore[attr-defined]
            async with await sesion.start_transaction():
                for fila in importables:
                    try:
                        resultado = await _importar_fila(
                            db,
                            fila,
                            usuario=usuario,
                            cache_conjuntos=cache_conjuntos,
                            cache_oficinas=cache_oficinas,
                            cache_responsables=cache_responsables,
                            crear_usuarios=crear_usuarios_faltantes,
                            contadores={"conjuntos_creados": 0, "usuarios_creados": 0, "zonas": zonas_nuevas, "oficinas": oficinas_nuevas},
                        )
                        if resultado["accion"] == "crear":
                            creados.append(resultado["id"])
                        else:
                            actualizados.append(resultado["id"])
                        if resultado.get("conjuntos_creados"):
                            conjuntos_creados += resultado["conjuntos_creados"]
                        if resultado.get("usuarios_creados"):
                            usuarios_creados += resultado["usuarios_creados"]
                    except Exception as exc:  # una fila no detiene el lote
                        omitidos.append(str(fila["numero"]))
                        errores.append(f"Fila {fila['numero']}: {exc}")
    except Exception as exc:
        raise Validacion(f"No se pudo confirmar la importacion: {exc}") from exc

    await _sincronizar_responsables_conjuntos(cache_conjuntos.values(), usuario=usuario)
    for fila in filas:
        if fila["accion"] == "omitir" or fila["excluida"]:
            omitidos.append(str(fila["numero"]))
    await db["importaciones"].update_one(
        {"lote_id": lote_id},
        {
            "$set": {
                "estado": "confirmado",
                "confirmado_en": utcnow(),
                "creados": creados,
                "actualizados": actualizados,
                "omtidos": omitidos,
                "resumen": {
                    "creados": len(creados),
                    "actualizados": len(actualizados),
                    "omitidos": len(omitidos),
                    "errores": len(errores),
                    "conjuntos_creados": conjuntos_creados,
                    "usuarios_creados": usuarios_creados,
                    "zonas_creadas": zonas_nuevas,
                    "oficinas_creadas": oficinas_nuevas,
                    "sin_codigo_advertencia": sum(
                        1 for f in importables if not f["codigo_patrimonial"]
                    ),
                    "detalle": errores[:200],
                    "reversible": not actualizados,
                },
                "reversible": not actualizados,
            }
        },
    )
    await db["configuracion"].update_one(
        {"_id": "config"}, {"$set": {"inventario.importacion_completada": True}}, upsert=True
    )
    await registrar(
        "importacion.confirmar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="importacion",
        entidad_id=lote_id,
        resumen=(
            f"{lote_id}: {len(creados)} creados, {len(actualizados)} actualizados, {len(omitidos)} omitidos"
        ),
        despues={
            "creados": len(creados),
            "actualizados": len(actualizados),
            "omitidos": len(omitidos),
            "errores": errores[:20],
        },
    )
    return {
        "lote_id": lote_id,
        "creados": len(creados),
        "actualizados": len(actualizados),
        "omitidos": len(omitidos),
        "errores": len(errores),
        "conjuntos_creados": conjuntos_creados,
        "usuarios_creados": usuarios_creados,
        "zonas_creadas": zonas_nuevas,
        "oficinas_creadas": oficinas_nuevas,
        "reversible": not actualizados,
        "detalle": errores[:200],
    }


async def _importar_fila(
    db,
    fila: dict[str, Any],
    *,
    usuario: dict[str, Any],
    cache_conjuntos: dict[str, ObjectId],
    cache_oficinas: dict[str, ObjectId],
    cache_responsables: dict[tuple[ObjectId, str], ObjectId],
    crear_usuarios: bool,
    contadores: dict[str, Any],
) -> dict[str, Any]:
    # No crear perfiles si el destino cambió después de la previsualización.
    clave_natural = fila["clave_natural_preview"]
    activo_existente = None
    if fila.get("existente_id"):
        activo_existente = await db["activos"].find_one({"_id": ObjectId(fila["existente_id"])})
        if activo_existente is None:
            raise Validacion("El equipo cambió después de la vista previa. Vuelve a revisar la importación.")
        clave_natural = activo_existente["clave_natural"]
    else:
        identidades = [{"clave_natural": clave_natural}]
        for campo in ("codigo_patrimonial", "direccion_mac"):
            if fila.get(campo):
                identidades.append({campo: fila[campo]})
        if await db["activos"].find_one({"$or": identidades}, {"_id": 1}):
            raise Conflicto("El inventario cambió después de la vista previa. Vuelve a revisar la importación.")
    zona_id = ObjectId(fila["zona_id"])
    clave_oficina = f"{fila['zona_id']}|{clave(fila['oficina_nombre'])}"
    if clave_oficina not in cache_oficinas:
        oficina = await org_service.oficina_por_nombre(
            fila["oficina_nombre"], zona_id, crear=True, usuario=usuario
        )
        if oficina is None:
            raise ValueError(f"no se pudo crear la oficina '{fila['oficina_nombre']}'")
        cache_oficinas[clave_oficina] = oficina["_id"]
        if not await db["oficinas"].find_one({"zona_id": zona_id, "nombre_normalizado": clave(fila["oficina_nombre"])}):
            contadores["oficinas"].append(fila["oficina_nombre"])
    oficina_id = cache_oficinas[clave_oficina]
    zona = await db["zonas"].find_one({"_id": zona_id})
    if zona is None:
        raise ValueError("la zona ya no existe")

    conjunto_id = None
    if fila["es_conjunto"] and fila["conjunto_nombre"]:
        clave_conjunto = f"{oficina_id}|{clave(fila['conjunto_nombre'])}"
        if clave_conjunto not in cache_conjuntos:
            existente = await db["conjuntos"].find_one(
                {"oficina_id": oficina_id, "nombre_normalizado": clave(fila["conjunto_nombre"])}
            )
            if existente:
                cache_conjuntos[clave_conjunto] = existente["_id"]
            else:
                numero = fila.get("conjunto_numero")
                if numero is not None and await db["conjuntos"].find_one({"oficina_id": oficina_id, "numero": numero}):
                    # El Excel numera computadoras e impresoras por separado.
                    # Conservamos su etiqueta; el ordinal interno debe ser unico.
                    numero = None
                documento = await inventario_service.crear_conjunto(
                    {
                        "nombre": fila["conjunto_nombre"],
                        "oficina_id": oficina_id,
                        "numero": numero,
                        "uso_comun": True,
                        "estado": "Operativo",
                    },
                    usuario=usuario,
                )
                cache_conjuntos[clave_conjunto] = documento["_id"]
                contadores["conjuntos_creados"] += 1
        conjunto_id = cache_conjuntos[clave_conjunto]

    usuarios_creados = 0
    responsable_id = ObjectId(fila["responsable_id"]) if fila.get("responsable_id") else None
    if not responsable_id and crear_usuarios and fila.get("responsable_nombre") and fila["responsable_estado"] == "no_encontrado":
        clave_persona = (oficina_id, clave_oscura(fila["responsable_nombre"]))
        if clave_persona not in cache_responsables:
            candidatos = await db["usuarios"].find(
                {"oficina_id": oficina_id, "activo": True, "archivado": {"$ne": True}}, {"nombre": 1}
            ).to_list(None)
            exactos = [c for c in candidatos if clave_oscura(c.get("nombre") or "") == clave_persona[1]]
            if len(exactos) > 1:
                raise Validacion("Hay varias personas con el mismo nombre. Vincula el responsable manualmente.")
            if exactos:
                cache_responsables[clave_persona] = exactos[0]["_id"]
            else:
                nuevo = await usuario_service.crear(
                    {"nombre": fila["responsable_nombre"], "oficina_id": oficina_id,
                     "zona_id": zona_id, "rol": "usuario"}, usuario=usuario,
                )
                cache_responsables[clave_persona] = nuevo["_id"]
                usuarios_creados = 1
        responsable_id = cache_responsables[clave_persona]
        fila["responsable_estado"] = "creado"

    campos = {campo: fila.get(campo) for campo in CAMPOS_BASE}
    campos["observaciones"] = fila.get("observaciones")
    campos["estado"] = campos.get("estado") or "Operativo"
    if fila.get("es_conjunto") and not fila.get("nombre_equipo"):
        campos["nombre_equipo"] = f"{fila['conjunto_nombre']} - {fila['tipo']}"
    elif not fila.get("es_conjunto") and fila.get("grupo_crudo") and not fila.get("nombre_equipo"):
        campos["nombre_equipo"] = fila["grupo_crudo"]
    campos_estado = {
        campo: (CAMPO_NO_APLICA if fila["campos_estado"].get(campo) == CAMPO_NO_APLICA else CAMPO_PENDIENTE)
        for campo in CAMPOS_BASE
        if fila["campos_estado"].get(campo) == CAMPO_NO_APLICA
    }

    if activo_existente is not None:
        await inventario_service.actualizar_activo(
            activo_existente["_id"],
            {**campos, "oficina_id": oficina_id, "conjunto_id": conjunto_id, "responsable_id": responsable_id},
            usuario=usuario,
        )
        await db["activos"].update_one(
            {"_id": activo_existente["_id"]},
            {"$set": {
                "clave_natural": clave_natural,
                "importacion_lote": fila.get("lote_id"),
                "responsable_nombre": fila.get("responsable_nombre"),
                "responsable_nombre_excel": fila.get("responsable_nombre_original"),
                "responsable_vinculado": bool(responsable_id),
            }},
        )
        return {"accion": "actualizar", "id": str(activo_existente["_id"]),
                "conjuntos_creados": contadores["conjuntos_creados"], "usuarios_creados": usuarios_creados}

    documento = await inventario_service.crear_activo(
        {
            "tipo": fila["tipo"],
            "oficina_id": oficina_id,
            "conjunto_id": conjunto_id,
            "responsable_id": responsable_id,
            **campos,
            "campos_estado": campos_estado,
            "uso_comun": not responsable_id,
        },
        usuario=usuario,
        registrar_sugerencias=False,
        clave_natural=clave_natural,
    )
    await db["activos"].update_one(
        {"_id": documento["_id"]},
        {"$set": {
            "importacion_lote": fila.get("lote_id"),
            "responsable_nombre": fila.get("responsable_nombre"),
            "responsable_nombre_excel": fila.get("responsable_nombre_original"),
            "responsable_vinculado": bool(responsable_id),
        }},
    )
    return {
        "accion": "crear",
        "id": str(documento["_id"]),
        "conjuntos_creados": contadores["conjuntos_creados"],
        "usuarios_creados": usuarios_creados,
    }


async def _deshacer_lote(lote_id: str, *, usuario: dict[str, Any]) -> dict[str, Any]:
    """10. Deshacer la ultima importacion mientras no se haya modificado lo importado."""
    db = get_db()
    documento = await obtener_lote(lote_id)
    if documento.get("estado") != "confirmado":
        raise Validacion("Solo se puede deshacer una importacion confirmada.")
    creados = [ObjectId(x) for x in documento.get("creados") or []]
    actualizados = [ObjectId(x) for x in documento.get("actualizados") or []]
    if actualizados:
        raise Prohibido("Este lote actualizo equipos existentes y no tiene una copia previa para restaurarlos.")
    if not creados and not actualizados:
        raise Validacion("No hay elementos importados que revertir.")

    modificados = await db["activos"].count_documents(
        {"_id": {"$in": creados}, "actualizado_en": {"$gt": documento.get("confirmado_en") or utcnow()}}
    )
    if modificados:
        raise Prohibido(
            f"{modificados} equipo(s) importados fueron modificados despues. Deshacer ya no es seguro.",
            detalles={"modificados": modificados},
        )
    if await db["tickets"].count_documents({"activo_id": {"$in": creados}}):
        raise Prohibido("Hay tickets asociados a equipos importados: ya no es seguro deshacer.")

    if creados:
        await db["activos"].delete_many({"_id": {"$in": creados}})
    await db["activos"].update_many(
        {"_id": {"$in": actualizados}}, {"$set": {"actualizado_en": utcnow()}}
    )
    await db["importaciones"].update_one(
        {"lote_id": lote_id}, {"$set": {"estado": "deshecho", "reversible": False, "deshecho_en": utcnow()}}
    )
    await registrar(
        "importacion.deshacer",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="importacion",
        entidad_id=lote_id,
        resultado="revertido",
        resumen=f"Importacion {lote_id} revertida",
        despues={"eliminados": len(creados), "restaurados": len(actualizados)},
    )
    return {"lote_id": lote_id, "eliminados": len(creados), "restaurados": len(actualizados)}


async def listar_importaciones(limite: int = 25) -> list[dict[str, Any]]:
    documentos = await (
        get_db()["importaciones"].find({}, {"filas": 0, "previsualizacion_filas": 0, "ajustes": 0})
        .sort("creado_en", -1)
        .limit(limite)
        .to_list(None)
    )
    for documento in documentos:
        documento["id"] = documento.pop("_id")
        documento["reversible"] = bool(documento.get("reversible")) and documento.get("estado") == "confirmado"
    return documentos


async def _ejecutar_operacion(lote_id: str, operacion, **opciones) -> dict:
    """Reserva el lote para evitar confirmaciones dobles o borrado durante su uso."""
    token = secrets.token_hex(12)
    ahora = utcnow()
    coleccion = get_db()['importaciones']
    reservado = await coleccion.find_one_and_update({
        'lote_id': lote_id, '$or': [{'operacion_en_curso': {'$ne': True}},
                                  {'operacion_inicio': {'$lt': ahora - timedelta(minutes=30)}}],
    }, {'$set': {'operacion_en_curso': True, 'operacion_inicio': ahora, 'operacion_token': token}})
    if reservado is None:
        await obtener_lote(lote_id)
        raise Conflicto('Esta importación está en proceso. Espera antes de volver a intentarlo.')
    try:
        return await operacion(lote_id, **opciones)
    finally:
        await coleccion.update_one({'lote_id': lote_id, 'operacion_token': token}, {'$unset': {
            'operacion_en_curso': '', 'operacion_inicio': '', 'operacion_token': '',
        }})


async def confirmar(lote_id: str, **opciones) -> dict:
    # La opción heredada de crear perfiles debe exigir el mismo permiso que
    # la confirmación de responsables del Excel, antes de reservar el lote.
    if opciones.get("crear_usuarios_faltantes") and not tiene_permiso(opciones.get("usuario") or {}, "usuarios.editar"):
        raise Prohibido("No tienes permiso para crear perfiles de usuarios desde el inventario.")
    return await _ejecutar_operacion(lote_id, _confirmar_lote, **opciones)


async def deshacer(lote_id: str, *, usuario: dict[str, Any]) -> dict:
    return await _ejecutar_operacion(lote_id, _deshacer_lote, usuario=usuario)


async def resultado(lote_id: str) -> dict[str, Any]:
    documento = await obtener_lote(lote_id)
    return {
        "lote_id": lote_id,
        "estado": documento.get("estado"),
        "nombre_archivo": documento.get("nombre_archivo"),
        "creado_en": documento.get("creado_en"),
        "confirmado_en": documento.get("confirmado_en"),
        "usuario_nombre": documento.get("usuario_nombre"),
        "reversible": bool(documento.get("reversible")) and documento.get("estado") == "confirmado",
        "resumen": documento.get("resumen") or {},
        "observaciones": documento.get("resumen", {}).get("detalle") or [],
    }
