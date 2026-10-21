"""Campanas de inventario anual: instantanea, comparacion con Excel, verificacion
fisica guiada, cierre e historial consultable por anios."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import re

from bson import ObjectId

from app.core.audit import registrar
from app.core.db import get_db
from app.core.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from app.core.ids import a_id, codigo_campana, clave, id_requerido, normalizar_texto
from app.core.time import a_fecha, business_tz, fecha_iso, utcnow
from app.domain.constants import CAMPO_PENDIENTE, CAMPOS_BASE
from app.domain.schemas_db import CONTADOR_CAMPANAS
from app.services import excel_service, import_service, inventario_service, org_service

ESTADOS_ITEM = {
    "pendiente",
    "confirmado",
    "cambio_responsable",
    "cambio_estado",
    "cambio_oficina",
    "no_encontrado",
    "dado_de_baja",
    "nuevo",
}
ESTADO_ITEM_NO_ENCONTRADO = "no_localizado"
ESTADOS_CAMPANA = {"abierta", "verificacion", "cerrada"}


async def _siguiente_codigo(anio: int) -> str:
    db = get_db()
    resultado = await db["contadores"].find_one_and_update(
        {"clave": f"{CONTADOR_CAMPANAS}:{anio}"},
        {"$inc": {"valor": 1}, "$setOnInsert": {"creado": utcnow()}},
        upsert=True,
        return_document=True,
    )
    return codigo_campana(anio, int(resultado["valor"]))
async def _a_utc(dia: date) -> datetime:
    return datetime.combine(dia, datetime.min.time(), tzinfo=business_tz()).astimezone(timezone.utc)


def zona_de_hoja(nombre_hoja: str) -> str:
    """
    El nombre de la hoja es el nombre de la zona.

    Es la convención que ya usa la importación del inventario —una hoja, una
    zona— y la que le da sentido a un equipo nuevo detectado en una hoja: sin
    ella no se sabe dónde crearlo.
    """
    return normalizar_texto(nombre_hoja).upper()


def _consulta_por_alcance(datos: dict[str, Any]) -> dict[str, Any]:
    """
    Traduce el alcance elegido a la consulta de equipos.

    Vive aparte porque lo usan dos sitios: crear la campaña y **preguntarle
    cuántos equipos habrá** antes de crearla. La pregunta que responde a «¿qué
    significa "solo algunas zonas"?» no es una descripción: es un número.
    """
    alcance = datos.get("alcance", "institucion")
    if alcance not in {"institucion", "zonas", "oficinas"}:
        raise Validacion("Elige un alcance válido: institución, zonas u oficinas.")
    consulta: dict[str, Any] = {"activo": {"$ne": False}}
    if alcance == "zonas":
        if not datos.get("zona_ids"):
            raise Validacion("Selecciona al menos una zona.")
        consulta["zona_id"] = {"$in": [id_requerido(z, "zona") for z in datos["zona_ids"]]}
    elif alcance == "oficinas":
        if not datos.get("oficina_ids"):
            raise Validacion("Selecciona al menos una oficina.")
        consulta["oficina_id"] = {"$in": [id_requerido(o, "oficina") for o in datos["oficina_ids"]]}
    return consulta


async def contar_por_alcance(datos: dict[str, Any]) -> int:
    """Cuántos equipos entran en la campaña, sin crearla. Solo lectura."""
    return await get_db()["activos"].count_documents(_consulta_por_alcance(datos))


async def crear(datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    """
    Crea la campaña **vacía**. Su contenido llega al subir el Excel de la sala.

    Antes congelaba aquí una instantánea con todo el inventario del alcance: 877
    equipos copiados en el momento de crearla. Al abrir la campaña se veía una
    lista idéntica a la del inventario —los mismos equipos que ya se habían
    subido—, sin que nadie hubiera subido nada todavía, y no había forma de
    entender qué faltaba descubrir. Para descubrir equipos nuevos lo único que
    importa es lo que hay en la sala, y eso se sabe con el archivo.

    El alcance sigue guardándose porque sigue sirviendo para una cosa: saber
    qué equipos registrados del alcance **no** aparecen en el archivo. Sin
    instantánea, ese grupo se calcula al comparar en vez de al crear, y es más
    útil: sale del archivo real, no de un supuesto.

    Por eso desaparece también el error «no hay equipos en el alcance»: que el
    inventario esté vacío ya no impide crear una campaña, porque la campaña se
    llena con lo que se suba.
    """
    db = get_db()
    fecha_inicio = a_fecha(datos["fecha_inicio"])
    fecha_fin = a_fecha(datos["fecha_fin"])
    if fecha_inicio is None or fecha_fin is None:
        raise Validacion("Las fechas de la campana no son validas.")
    if fecha_fin < fecha_inicio:
        raise Validacion("La fecha final no puede ser anterior a la inicial.")
    alcance = datos.get("alcance", "institucion")

    # El alcance se valida aunque la campaña nazca vacía: si se piden zonas u
    # oficinas concretas, tienen que existir. Que no haya equipos ya no impide
    # crear la campaña, porque se llena con lo que se suba.
    _consulta_por_alcance(datos)

    anio = int(datos["anio"])
    if fecha_inicio.year != anio:
        raise Validacion("El año de la campaña debe coincidir con la fecha de inicio.")
    codigo = await _siguiente_codigo(anio)
    campana = {
        "codigo": codigo,
        "nombre": normalizar_texto(datos["nombre"]),
        "anio": anio,
        "alcance": alcance,
        "zona_ids": [id_requerido(z, "zona") for z in (datos.get("zona_ids") or [])],
        "oficina_ids": [id_requerido(o, "oficina") for o in (datos.get("oficina_ids") or [])],
        # Fechas como texto ISO: BSON no admite datetime.date
        "fecha_inicio": fecha_iso(datos["fecha_inicio"]),
        "fecha_fin": fecha_iso(datos["fecha_fin"]),
        "responsables": [id_requerido(r, "usuario") for r in (datos.get("responsables") or [])],
        "responsables_nombre": [],
        "notas": normalizar_texto(datos.get("notas")) or None,
        "generar_qr": bool(datos.get("generar_qr")),
        "estado": "abierta",
        "creado_en": utcnow(),
        "creado_por": usuario.get("nombre", ""),
        "cerrado_en": None,
        "version_inventario": anio - 1,
    }
    if campana["responsables"]:
        nombres = await (db["usuarios"].find({"_id": {"$in": campana["responsables"]}}, {"nombre": 1}).to_list(None))
        campana["responsables_nombre"] = [n.get("nombre") for n in nombres]
    resultado = await db["campanas_inventario"].insert_one(campana)
    campana["_id"] = resultado.inserted_id

    # Sin instantánea: la campaña nace con cero equipos. Se llenan al comparar el
    # Excel de la sala, que es donde se sabe qué hay de verdad.
    campana["total_items"] = 0
    campana["total_previsto"] = await contar_por_alcance(datos)
    await db["campanas_inventario"].update_one(
        {"_id": campana["_id"]},
        {"$set": {"total_items": 0, "total_previsto": campana["total_previsto"]}},
    )
    await registrar(
        "campana.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="campana",
        entidad_id=campana["_id"],
        resumen=f"Campana creada: {codigo} (vacia; se llena con el Excel de la sala)",
        despues={
            "codigo": codigo,
            "anio": anio,
            "alcance": alcance,
            "items": 0,
            "registrados_en_alcance": campana["total_previsto"],
        },
    )
    return campana


async def listar(limite: int = 25) -> list[dict[str, Any]]:
    campanas = await (
        get_db()["campanas_inventario"].find({}, {"responsables": 0})
        .sort([("anio", -1), ("creado_en", -1), ("_id", -1)])
        .limit(limite)
        .to_list(None)
    )
    salida: list[dict[str, Any]] = []
    for campana in campanas:
        # El progreso se calcula por campaña y se mezcla con sus datos. Antes se
        # guardaba en `_resumen` y se borraba antes de leerlo, así que la lista
        # llegaba siempre con 0 verificados y 0 pendientes: verificar un equipo
        # no movía ningún indicador en pantalla.
        conteos = await progreso(campana["_id"])
        # `zona_ids` y `oficina_ids` **no se excluyen**. Antes sí, y por eso al
        # filtrar una campaña creada con dos zonas el desplegable ofrecía las
        # siete: la pantalla no tenía forma de saber qué alcance tenía.
        for campo in ("zona_ids", "oficina_ids"):
            campana[campo] = [str(x) for x in campana.get(campo) or []]
        salida.append({**campana, **_resumen(campana["_id"], conteos)})
    return salida


def _resumen(campana_id: ObjectId, conteos: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": campana_id,
        # El total **vivo** gana al guardado en el documento. `total_items` se
        # escribía al crear la campaña, y como ahora nace vacía se quedaba en 0 para
        # siempre: con 196 equipos ya subidos, la campaña seguía diciendo que tenía 0.
        # `{**campana, **_resumen(...)}` pone el resumen encima del documento, así que
        # aquí manda el número que se acaba de contar.
        "total_items": conteos.get("total_items", 0),
        "verificados": conteos.get("verificados", 0),
        "progreso": conteos.get("progreso", 0.0),
        "total_registrados": conteos.get("total_registrados", 0),
        "nuevos": conteos.get("nuevos", 0),
        "nuevos_aceptados": conteos.get("nuevos_aceptados", 0),
        "nuevos_descartados": conteos.get("nuevos_descartados", 0),
        "nuevos_sin_decidir": conteos.get("nuevos_sin_decidir", 0),
        "modificados": conteos.get("modificados", 0),
        "sin_cambios": conteos.get("sin_cambios", 0),
        "por_verificar": conteos.get("por_verificar", 0),
        "discrepancias": conteos.get("discrepancias", 0),
    }


# Estados que significa «alguien lo buscó en la sala y decidió». Un equipo nuevo
# marcado para registrarse **no** entra: no está en ninguna sala todavía, se
# acaba de descubrir en un archivo. Los equipos nuevos aceptados y los
# registrados pendientes se cuentan aparte, en sus propias cifras.
ESTADOS_VERIFICADOS = frozenset(
    {"confirmado", "no_encontrado", "dado_de_baja", "cambio_responsable", "cambio_oficina", "cambio_estado"}
)


async def progreso(campana_id: ObjectId) -> dict[str, Any]:
    """
    Las cuentas de la campaña, separadas por lo que cada una significa.

    Antes `verificados` era «todo lo que no estaba pendiente». Con los equipos
    nuevos eso mintió: al marcar dos equipos nuevos para registrarlos, la pantalla
    ponía «Verificados 2» y un 67 % de progreso siendo que **nadie había buscado
    esos equipos en ninguna sala**: se acababan de descubrir en un Excel. Un
    equipo que todavía no existe no puede estar verificado.

    Ahora cada grupo cuenta lo suyo:

    * `verificados`: equipos registrados a los que alguien los buscó en la sala.
    * `por_verificar`: equipos registrados que nadie llegó a mirar.
    * `nuevos_aceptados`: equipos de la sala ya marcados para registrarse.
    * `nuevos_sin_decidir`: equipos de la sala detectados y aún sin decidir.
    """
    db = get_db()
    total = await db["campana_items"].count_documents({"campana_id": campana_id})
    # Los equipos de verdad son los que tienen `activo_id`. Los nuevos nacen sin
    # él, porque aún no son un equipo.
    registrados = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "activo_id": {"$ne": None}, "origen": {"$ne": "excel_nuevo"}}
    )
    verificados = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "estado_item": {"$in": list(ESTADOS_VERIFICADOS)}, "activo_id": {"$ne": None}, "origen": {"$ne": "excel_nuevo"}}
    )
    nuevos = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "origen": "excel_nuevo", "estado_item": {"$ne": "nuevo"}}
    )
    # Los que ya se han marcado como «van a registrarse». `nuevos` cuenta también
    # los que nadie ha decidido todavía, así que sin esto el diálogo de cierre no
    # puede decir cuántos equipos van a aparecer en el inventario: no es lo mismo
    # lo detectado que lo aceptado.
    nuevos_aceptados = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "estado_item": "nuevo"}
    )
    nuevos_descartados = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "origen": "excel_rechazado"}
    )
    modificados = await db["campana_items"].count_documents({"campana_id": campana_id, "origen": "excel_modificado"})
    sin_cambios = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "origen": "excel_sin_cambio"}
    )
    por_verificar = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "estado_item": "pendiente", "activo_id": {"$ne": None}}
    )
    nuevos_sin_decidir = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "origen": "excel_nuevo", "estado_item": "pendiente"}
    )
    discrepancias = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "estado_item": {"$in": ["no_encontrado", "cambio_responsable", "cambio_oficina", "cambio_estado", "dado_de_baja"]}}
    )
    return {
        "total_items": total,
        "total_registrados": registrados,
        "verificados": verificados,
        # El progreso se mide sobre los equipos registrados: los nuevos no entran
        # en el denominador porque de ellos no se ha «verificado» nada.
        "progreso": round(100 * verificados / registrados, 1) if registrados else 0.0,
        "nuevos": nuevos,
        "nuevos_aceptados": nuevos_aceptados,
        "nuevos_descartados": nuevos_descartados,
        "nuevos_sin_decidir": nuevos_sin_decidir,
        "modificados": modificados,
        "sin_cambios": sin_cambios,
        "por_verificar": por_verificar,
        "discrepancias": discrepancias,
    }


async def obtener(campana_id: ObjectId, *, usuario: dict[str, Any]) -> dict[str, Any]:
    campana = await get_db()["campanas_inventario"].find_one({"_id": campana_id})
    if campana is None:
        raise NoEncontrado("Campana no encontrada.")
    campana["id"] = campana.pop("_id")
    campana["resumen"] = await progreso(campana_id)
    campana["responsables_nombre"] = campana.get("responsables_nombre") or []
    for campo in ("fecha_inicio", "fecha_fin"):
        if campo in campana:
            campana[campo] = a_fecha(campana[campo])
    return campana


async def actualizar(campana_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    campana = await db["campanas_inventario"].find_one({"_id": campana_id})
    if campana is None:
        raise NoEncontrado("Campana no encontrada.")
    if campana.get("estado") == "cerrada":
        raise Prohibido("La campana esta cerrada: crea una nueva para el siguiente ciclo.")
    cambios = {
        campo: datos[campo]
        for campo in ("nombre", "fecha_inicio", "fecha_fin", "notas", "generar_qr")
        if datos.get(campo) is not None
    }
    for campo in ("fecha_inicio", "fecha_fin"):
        if campo in cambios and not isinstance(cambios[campo], str):
            cambios[campo] = fecha_iso(cambios[campo])
    inicio = a_fecha(cambios.get("fecha_inicio", campana.get("fecha_inicio")))
    fin = a_fecha(cambios.get("fecha_fin", campana.get("fecha_fin")))
    if inicio is None or fin is None or fin < inicio:
        raise Validacion("La fecha final debe ser igual o posterior a la inicial.")
    if inicio.year != campana["anio"]:
        raise Validacion("La fecha de inicio debe pertenecer al año de la campaña.")
    if cambios:
        await db["campanas_inventario"].update_one({"_id": campana_id}, {"$set": cambios})
    await registrar(
        "campana.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="campana",
        entidad_id=campana_id,
        resumen=f"Campana {campana.get('codigo')} actualizada",
        antes={k: campana.get(k) for k in cambios},
        despues=cambios,
    )
    return await obtener(campana_id, usuario=usuario)


async def items(
    campana_id: ObjectId,
    *,
    zona_id: ObjectId | None = None,
    oficina_id: ObjectId | None = None,
    estado: str | None = None,
    solo_pendientes: bool = False,
    pagina: int = 1,
    por_pagina: int = 50,
    texto: str | None = None,
) -> dict[str, Any]:
    import math

    db = get_db()
    consulta: dict[str, Any] = {"campana_id": campana_id}
    if zona_id:
        consulta["zona_id"] = zona_id
    if oficina_id:
        consulta["oficina_id"] = oficina_id
    if estado:
        consulta["estado_item"] = estado
    if solo_pendientes:
        consulta["estado_item"] = "pendiente"
    if texto:
        # El texto tecleado se escapa antes de usarlo como expresión regular.
        # Sin esto, buscar `a*b` —un asterisco es perfectly normal al teclear un
        # código— deja la regex sin cerrar y Mongo devuelve 500. Es el mismo
        # criterio que ya se aplica en la búsqueda del inventario.
        patron = re.escape(normalizar_texto(texto))
        # Se busca también por **oficina y zona**, no solo por nombre y código del
        # equipo. En una sala lo que se sabe es dónde está el equipo, no cómo se
        # llama: buscando «PISCINA» salía cero resultados aunque la zona
        # PISCINA MUNICIPAL tuviera 36 equipos en la campaña.
        consulta["$or"] = [
            {"activo_nombre": {"$regex": patron, "$options": "i"}},
            {"activo_codigo": {"$regex": patron, "$options": "i"}},
            {"oficina_nombre": {"$regex": patron, "$options": "i"}},
            {"zona_nombre": {"$regex": patron, "$options": "i"}},
            {"responsable_nombre": {"$regex": patron, "$options": "i"}},
        ]
    total = await db["campana_items"].count_documents(consulta)
    documentos = await (
        db["campana_items"]
        .find(consulta)
        .sort([("zona_nombre", 1), ("oficina_nombre", 1), ("activo_nombre", 1), ("_id", 1)])
        .skip((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .to_list(None)
    )
    for documento in documentos:
        documento["id"] = documento.pop("_id")
    return {
        "items": documentos,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": math.ceil(total / por_pagina) if por_pagina else 0,
    }


async def verificar_item(
    campana_id: ObjectId, item_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]
) -> dict[str, Any]:
    """Verificacion fisica guiada. Nunca borra: los 'no encontrados' quedan para seguimiento."""
    db = get_db()
    campana = await db["campanas_inventario"].find_one({"_id": campana_id})
    if campana is None:
        raise NoEncontrado("Campaña no encontrada.")
    if campana.get("estado") == "cerrada":
        raise Prohibido("La campaña está cerrada; sus verificaciones son de solo lectura.")
    estado = datos.get("estado_item")
    if estado not in ESTADOS_ITEM:
        raise Validacion("Estado de verificacion no valido.")
    item = await db["campana_items"].find_one({"_id": item_id, "campana_id": campana_id})
    if item is None:
        raise NoEncontrado("Elemento no encontrado en esta campana.")
    if item.get("origen") == "excel_nuevo" and not item.get("activo_id") and estado == "confirmado":
        estado = "nuevo"
    cambios: dict[str, Any] = {
        "estado_item": estado,
        "observaciones": normalizar_texto(datos.get("observaciones")) or None,
        "verificado_por": usuario.get("nombre"),
        "verificado_en": utcnow(),
    }
    responsable_id = a_id(datos.get("responsable_id"))
    if responsable_id:
        cambios["responsable_id"] = responsable_id
        persona = await db["usuarios"].find_one({"_id": responsable_id}, {"nombre": 1})
        if persona is None:
            raise NoEncontrado("La persona responsable no existe.")
        cambios["responsable_nombre"] = (persona or {}).get("nombre")
    elif datos.get("responsable_id") is None and estado == "cambio_responsable":
        cambios["responsable_id"] = None
        cambios["responsable_nombre"] = None
    nuevo_oficina = a_id(datos.get("nuevo_oficina_id"))
    if estado == "cambio_oficina" and nuevo_oficina is None:
        raise Validacion("Selecciona la nueva oficina del equipo.")
    if nuevo_oficina:
        oficina = await db["oficinas"].find_one({"_id": nuevo_oficina})
        if oficina is None:
            raise NoEncontrado("La oficina indicada no existe.")
        cambios["nuevo_oficina_id"] = nuevo_oficina
        cambios["nuevo_oficina_nombre"] = oficina.get("nombre")
    if datos.get("cambios"):
        cambios["cambios"] = datos["cambios"]
        item_cambios = dict(item.get("actual") or {})
        for campo, valor in datos["cambios"].items():
            if campo in CAMPOS_BASE:
                item_cambios[campo] = valor
        cambios["actual"] = item_cambios
        cambios["diferencias"] = _calcular_diferencias(item.get("instantanea") or {}, item_cambios)
    await db["campana_items"].update_one({"_id": item_id}, {"$set": cambios})
    campana = await db["campanas_inventario"].find_one({"_id": campana_id}) or {}
    if campana.get("estado") == "abierta":
        await db["campanas_inventario"].update_one({"_id": campana_id}, {"$set": {"estado": "verificacion"}})
    await registrar(
        "campana.item",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="campana_item",
        entidad_id=item_id,
        resumen=f"{campana.get('codigo')}: {item.get('activo_nombre')} -> {estado}",
        antes={"estado": item.get("estado_item")},
        despues={"estado": estado, "observaciones": cambios.get("observaciones")},
    )
    return await db["campana_items"].find_one({"_id": item_id})


def _calcular_diferencias(instantanea: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    """Compara solo los campos que el archivo trae: una columna ausente no es un cambio."""
    diferencias: list[dict[str, Any]] = []
    for campo in CAMPOS_BASE:
        if campo not in actual:
            continue
        antes = instantanea.get(campo)
        despues = actual.get(campo)
        if (antes or None) != (despues or None):
            diferencias.append({"campo": campo, "antes": antes, "despues": despues})
    return diferencias


async def _crear_item_de_registrado(
    campana: dict[str, Any],
    activo: dict[str, Any],
    *,
    fila: dict[str, Any],
    hoja: str,
    numero: int | None,
) -> dict[str, Any]:
    """
    Crea el item de un equipo que **ya está en el inventario** y aparece en el Excel.

    Nace `pendiente`: aparecer en el archivo dice que alguien lo escribió, no que
    esté en la sala. La instantánea es la del inventario, no la del archivo: es
    contra ella contra la que se calculan después las diferencias.
    """
    instantanea = {campo: activo.get(campo) for campo in CAMPOS_BASE}
    instantanea.update(
        {
            "responsable_id": activo.get("responsable_id"),
            "responsable_nombre": activo.get("responsable_nombre"),
            "oficina_id": activo.get("oficina_id"),
            "oficina_nombre": activo.get("oficina_nombre"),
            "zona_id": activo.get("zona_id"),
            "zona_nombre": activo.get("zona_nombre"),
            "conjunto_id": activo.get("conjunto_id"),
            "conjunto_nombre": activo.get("conjunto_nombre"),
        }
    )
    documento = {
        "campana_id": campana["_id"],
        "activo_id": activo["_id"],
        "activo_nombre": activo.get("nombre_equipo") or activo.get("modelo") or activo.get("tipo"),
        "activo_codigo": activo.get("codigo_patrimonial"),
        "activo_tipo": activo.get("tipo"),
        "conjunto_nombre": activo.get("conjunto_nombre"),
        "oficina_id": activo.get("oficina_id"),
        "oficina_nombre": activo.get("oficina_nombre"),
        "zona_id": activo.get("zona_id"),
        "zona_nombre": activo.get("zona_nombre"),
        "responsable_id": activo.get("responsable_id"),
        "responsable_nombre": activo.get("responsable_nombre"),
        "instantanea": instantanea,
        "actual": instantanea,
        "diferencias": [],
        "estado_item": "pendiente",
        "origen": "excel_archivo",
        "hoja": hoja,
        "numero": numero,
        "observaciones": None,
        "verificado_por": None,
        "verificado_en": None,
        "codigo_qr": activo.get("codigo_patrimonial") if campana.get("generar_qr") else None,
        "creado_en": utcnow(),
    }
    resultado = await get_db()["campana_items"].insert_one(documento)
    documento["_id"] = resultado.inserted_id
    return documento


async def importar_excel(
    campana_id: ObjectId, contenido: bytes, nombre: str, *, usuario: dict[str, Any]
) -> dict[str, Any]:
    """Modo 'actualizar': compara el Excel del anio nuevo contra el inventario actual."""
    db = get_db()
    campana = await db["campanas_inventario"].find_one({"_id": campana_id})
    if campana is None:
        raise NoEncontrado("Campana no encontrada.")
    if campana.get("estado") == "cerrada":
        raise Prohibido("La campana esta cerrada.")
    if not nombre.lower().endswith((".xlsx", ".xlsm", ".csv")):
        raise Validacion("Sube un archivo .xlsx o .csv con la plantilla oficial.")

    hojas = excel_service.leer_archivo(contenido, nombre)
    oficinas_permitidas = []
    zonas_permitidas = []
    if campana.get("alcance") == "zonas":
        zonas_permitidas = await db["zonas"].find({"_id": {"$in": campana.get("zona_ids") or []}}).to_list(None)
    elif campana.get("alcance") == "oficinas":
        oficinas_permitidas = await db["oficinas"].find({"_id": {"$in": campana.get("oficina_ids") or []}}).to_list(None)
        zonas_permitidas = await db["zonas"].find({"_id": {"$in": [o["zona_id"] for o in oficinas_permitidas]}}).to_list(None)
    if nombre.lower().endswith(".csv") and len(zonas_permitidas) == 1:
        hojas = {zonas_permitidas[0]["nombre"]: next(iter(hojas.values()))}
    filas_planas: list[tuple[str, dict[str, Any]]] = []
    for nombre_hoja, filas in hojas.items():
        cabeceras, registros = excel_service.hoja_a_registros(filas)
        if not registros:
            continue
        mapeo = import_service.detectar_mapeo(cabeceras)
        for registro in registros:
            filas_planas.append((nombre_hoja, {"registro": registro, "mapeo": mapeo, "hoja": nombre_hoja}))

    if not filas_planas:
        raise Validacion("El archivo no contiene equipos para comparar. Revisa las cabeceras y las filas.")
    # Validar el libro completo antes de crear o modificar un solo elemento.
    if zonas_permitidas:
        nombres_zona = {clave(z["nombre"]) for z in zonas_permitidas}
        for hoja, bloque in filas_planas:
            if clave(hoja) not in nombres_zona and clave(hoja.replace("ZONA ", "")) not in nombres_zona:
                raise Validacion(f"La hoja «{hoja}» está fuera del alcance de esta campaña.")
            if oficinas_permitidas:
                columna = (bloque["mapeo"].get("area") or {}).get("columna")
                area = clave(bloque["registro"].get(columna, "")) if columna else ""
                if not any(clave(o["nombre"]) == area and any(z["_id"] == o["zona_id"] and clave(z["nombre"]) in {clave(hoja), clave(hoja.replace("ZONA ", ""))} for z in zonas_permitidas) for o in oficinas_permitidas):
                    raise Validacion("El archivo contiene una oficina fuera del alcance de la campaña.")

    items = await (db["campana_items"].find({"campana_id": campana_id}).to_list(None))

    # Los items de esta campaña —de una subida anterior del mismo archivo— y, además,
    # **el inventario registrado**. La campaña nace vacía, así que la primera vez no
    # hay ningún item: si solo se miraran los items, todas las filas saldrían como
    # equipo nuevo y los 877 equipos ya registrados aparecerían como nuevos. El
    # emparejamiento tiene que hacerse contra el registro, que es lo que responde a
    # «¿esto ya está dado de alta?».
    alcance = campana.get("alcance", "institucion")
    consulta_activos: dict[str, Any] = {"activo": {"$ne": False}}
    if alcance == "zonas" and campana.get("zona_ids"):
        consulta_activos["zona_id"] = {"$in": campana["zona_ids"]}
    elif alcance == "oficinas" and campana.get("oficina_ids"):
        consulta_activos["oficina_id"] = {"$in": campana["oficina_ids"]}

    registrados = await (db["activos"].find(consulta_activos).to_list(None))
    item_por_codigo = {i["activo_codigo"]: i for i in items if i.get("activo_codigo")}
    item_por_activo = {str(i["activo_id"]): i for i in items if i.get("activo_id")}
    item_por_nombre = {clave(i.get("activo_nombre") or ""): i for i in items if clave(i.get("activo_nombre") or "")}
    activo_por_codigo = {a["codigo_patrimonial"]: a for a in registrados if a.get("codigo_patrimonial")}

    resultados: list[dict[str, Any]] = []
    vistos: set[ObjectId] = set()
    # Items ya añadidos a `resultados` como ausentes. Sin esto, el equipo ausente se
    # reportaba dos veces en la segunda subida: una por el bucle de los registrados
    # del alcance y otra por el de los items que el archivo ya no menciona —el que
    # creó la primera subida ya estaba guardado—. El resumen grows en cada recarga
    # del mismo archivo.
    ya_reportados: set[ObjectId] = set()
    # Equipos registrados del alcance que van apareciendo en el archivo. Lo que quede
    # al final son los que no aparecen en ninguna fila, y se marcan como ausentes.
    registrados_vistos: set[str] = set()
    for nombre_hoja, bloque in filas_planas:
        registro = bloque["registro"]
        mapeo = bloque["mapeo"]
        # Solo se consideran los campos con columna mapeada y con valor: una celda
        # vacia significa "no informado", nunca "borrar el dato".
        fila = {}
        for campo in CAMPOS_BASE:
            columna = (mapeo.get(campo) or {}).get("columna")
            if not columna:
                continue
            valor = normalizar_texto(registro.get(columna, ""))
            if valor:
                fila[campo] = valor
        codigo = fila.get("codigo_patrimonial")
        clave_nombre = clave(fila.get("nombre_equipo") or "")
        # La columna AREA, la de tipo y la de dispositivo no son campos del
        # equipo (`CAMPOS_BASE` no las tiene): son las que dicen **dónde** está
        # y **qué** es. Sin ellas no se puede crear el equipo nuevo más adelante.
        columna_area = (mapeo.get("area") or {}).get("columna")
        oficina_nombre = normalizar_texto(registro.get(columna_area, "")) if columna_area else ""
        columna_tipo = (mapeo.get("tipo_equipo") or {}).get("columna")
        tipo_equipo = normalizar_texto(registro.get(columna_tipo, "")) if columna_tipo else ""
        columna_disp = (mapeo.get("dispositivo") or {}).get("columna")
        dispositivo = normalizar_texto(registro.get(columna_disp, "")) if columna_disp else ""
        # El tipo es «CPU», «Impresora»… El dispositivo es «PC NUEVA DE LA SALA»:
        # una descripción. Se usa el tipo; el dispositivo solo cuando no hay tipo,
        # porque un equipo sin tipo no se puede registrar.
        tipo = tipo_equipo or dispositivo
        advertencias: list[str] = []
        # 1) ¿Esta fila ya es un item de la campaña? Entonces es una recarga del
        #    mismo archivo y se actualiza en el sitio.
        item = item_por_codigo.get(codigo) if codigo else None
        # 2) Si no, ¿la fila corresponde a un equipo ya registrado? Es el caso normal
        #    de la primera subida: el equipo está en el inventario y hay que
        #    verificarlo, no darlo de alta.
        activo = activo_por_codigo.get(codigo) if codigo else None
        if item is None and activo is not None:
            item = await _crear_item_de_registrado(campana, activo, fila=fila, hoja=nombre_hoja, numero=registro.get("__fila__"))
            item_por_activo[str(activo["_id"])] = item
            if codigo:
                item_por_codigo[codigo] = item
            vistos.add(item["_id"])
            registrados_vistos.add(str(activo["_id"]))
        # 3) Sin código patrimonial se empareja por nombre, con aviso: dos equipos
        #    pueden llamarse igual y el emparejamiento por nombre es una suposición.
        if item is None and not codigo and clave_nombre:
            activo = next((a for a in registrados if clave(a.get("nombre_equipo") or "") == clave_nombre), None)
            if activo is not None:
                item = await _crear_item_de_registrado(campana, activo, fila=fila, hoja=nombre_hoja, numero=registro.get("__fila__"))
                item_por_activo[str(activo["_id"])] = item
                item_por_nombre[clave_nombre] = item
                vistos.add(item["_id"])
                registrados_vistos.add(str(activo["_id"]))
                advertencias.append("El equipo no tiene codigo patrimonial: se emparejo por nombre.")
        if item is None:
            resultados.append(
                {
                    "numero": registro.get("__fila__"),
                    "hoja": nombre_hoja,
                    "estado": "nuevo",
                    "descripcion": "Equipo que no existe en el inventario actual.",
                    # Mismos campos que el resto de grupos. Antes esta fila solo
                    # traía `datos` y ninguna pantalla podía mostrar el código ni
                    # el tipo sin desarmar el objeto a mano.
                    "activo_nombre": fila.get("nombre_equipo") or fila.get("modelo") or tipo,
                    "activo_codigo": fila.get("codigo_patrimonial"),
                    "activo_tipo": tipo,
                    "oficina_nombre": oficina_nombre,
                    "datos": fila,
                    "advertencias": advertencias,
                }
            )
            # Se guarda como item de la campaña, aunque todavía no exista como
            # equipo. Antes solo vivía en la respuesta de esta llamada: al
            # aceptar, `aceptar_cambios` buscaba el item por id, no lo encontraba
            # y lo **saltaba en silencio**, así que el equipo nuevo se perdía. Y
            # `cerrar` no los creaba. Es decir: se podian detectar los equipos
            # nuevos y no se podian registrar. Este es el hueco que cierra el
            # modo «actualizar».
            #
            # Nace `pendiente` a propósito: hasta que alguien lo acepta, no
            # cuenta como verificado ni se crea nada en el inventario.
            nuevo_id = await db["campana_items"].insert_one(
                {
                    "campana_id": campana_id,
                    "activo_id": None,
                    "activo_nombre": fila.get("nombre_equipo") or fila.get("modelo") or tipo,
                    "activo_codigo": fila.get("codigo_patrimonial"),
                    "activo_tipo": tipo,
                    "conjunto_nombre": fila.get("conjunto_nombre"),
                    "oficina_id": None,
                    "oficina_nombre": oficina_nombre,
                    "zona_id": None,
                    "zona_nombre": zona_de_hoja(nombre_hoja),
                    "responsable_id": None,
                    "responsable_nombre": fila.get("responsable_nombre"),
                    "instantanea": {},
                    "actual": fila,
                    "diferencias": [],
                    "estado_item": "pendiente",
                    "origen": "excel_nuevo",
                    "hoja": nombre_hoja,
                    "numero": registro.get("__fila__"),
                    "observaciones": None,
                    "verificado_por": None,
                    "verificado_en": None,
                    "codigo_qr": None,
                    "creado_en": utcnow(),
                }
            )
            nuevo_ids = resultados[-1]
            nuevo_ids["item_id"] = str(nuevo_id.inserted_id)
            continue
        vistos.add(item["_id"])
        # Un equipo que sigue **sin registrar**, ya detectado en una subida
        # anterior de este mismo archivo. Vuelve a salir como «nuevo» con el item
        # que ya tiene, para que siga a la vista hasta que se decida.
        #
        # Sin esto se comparaba contra una instantánea vacía —un equipo nuevo no
        # tiene datos previos— y salía como «con cambios»: en pantalla decía que
        # un equipo registrado había cambiado de datos, que es justo lo contrario
        # de lo que pasa: no está registrado. Recargar el mismo archivo tenía que
        # dar el mismo resultado que la primera vez.
        if item.get("activo_id") is None:
            # Se refrescan los datos del archivo. Antes solo se guardaba `actual`
            # y el resumen seguía mostrando los valores de la primera subida: si
            # se corregía el Excel y se volvía a subir, la pantalla seguía
            # enseñando el tipo y el nombre equivocados.
            await db["campana_items"].update_one(
                {"_id": item["_id"]},
                {
                    "$set": {
                        "actual": fila,
                        "oficina_nombre": oficina_nombre or item.get("oficina_nombre"),
                        "activo_nombre": fila.get("nombre_equipo") or fila.get("modelo") or tipo,
                        "activo_codigo": fila.get("codigo_patrimonial"),
                        "activo_tipo": tipo,
                    }
                },
            )
            resultados.append(
                {
                    "numero": registro.get("__fila__"),
                    "hoja": nombre_hoja,
                    "item_id": str(item["_id"]),
                    "activo_id": None,
                    "activo_nombre": item.get("activo_nombre"),
                    "activo_codigo": item.get("activo_codigo"),
                    "estado": "nuevo",
                    "descripcion": "Equipo que no existe en el inventario actual.",
                    "activo_nombre": fila.get("nombre_equipo") or fila.get("modelo") or tipo,
                    "activo_codigo": fila.get("codigo_patrimonial"),
                    "activo_tipo": tipo,
                    "oficina_nombre": oficina_nombre,
                    "diferencias": [],
                    "advertencias": advertencias,
                    "datos": fila,
                }
            )
            continue
        instantanea = item.get("instantanea") or {}
        diferencias = _calcular_diferencias(instantanea, fila)
        estado = "sin_cambio" if not diferencias else "modificado"
        resultados.append(
            {
                "numero": registro.get("__fila__"),
                "hoja": nombre_hoja,
                "item_id": str(item["_id"]),
                "activo_id": str(item["activo_id"]) if item.get("activo_id") else None,
                "activo_nombre": item.get("activo_nombre"),
                "activo_codigo": item.get("activo_codigo"),
                "activo_tipo": item.get("activo_tipo"),
                "oficina_nombre": item.get("oficina_nombre"),
                "estado": estado,
                "diferencias": diferencias,
                "advertencias": advertencias,
                "actual": fila,
            }
        )

    # Los que no aparecen en el archivo.
    #
    # Antes salían de recorrer los items de la campaña. Con la campaña vacía al
    # nacerse, eso no los detecta nadie: la lista de la sala puede tener 20 equipos y
    # el alcance tener 877 registrados, y los 857 que no aparecen en el archivo se
    # reportaban como «sin cambio» o quedaban mudos. Ahora se comparan los equipos
    # **registrados en el alcance** contra los que han salido en el archivo, y los que
    # sobran son los ausentes. Es la pregunta útil: ¿qué dice el registro que está en
    # esta zona y no aparece en lo que me pasaron?
    #
    # No se borran nunca: quedan como items pendientes para verificarlos a mano.
    for activo in registrados:
        if str(activo["_id"]) in registrados_vistos:
            continue
        item_existente = item_por_activo.get(str(activo["_id"]))
        if item_existente is None:
            item_existente = await _crear_item_de_registrado(campana, activo, fila={}, hoja="", numero=None)
            item_existente["origen"] = "excel_ausente"
            await db["campana_items"].update_one({"_id": item_existente["_id"]}, {"$set": {"origen": "excel_ausente"}})
            vistos.add(item_existente["_id"])
        resultados.append(
            {
                "item_id": str(item_existente["_id"]),
                "activo_id": str(activo["_id"]),
                "activo_nombre": activo.get("nombre_equipo") or activo.get("modelo") or activo.get("tipo"),
                "activo_codigo": activo.get("codigo_patrimonial"),
                "activo_tipo": activo.get("tipo"),
                "oficina_nombre": activo.get("oficina_nombre"),
                "estado": "ausente",
                "descripcion": "Está registrado pero no aparece en el archivo. No se borra: queda pendiente de verificar.",
                "diferencias": [],
                "advertencias": [],
            }
        )
        ya_reportados.add(item_existente["_id"])
    # Los items de subidas anteriores que el archivo ya no menciona también son
    # ausentes: si mañana se sube un archivo con menos filas, lo que sobra no se
    # queda pegado de una comparación vieja.
    for item in items:
        if item["_id"] in vistos or item["_id"] in ya_reportados:
            continue
        resultados.append(
            {
                "item_id": str(item["_id"]),
                "activo_id": str(item["activo_id"]) if item.get("activo_id") else None,
                "activo_nombre": item.get("activo_nombre"),
                "activo_codigo": item.get("activo_codigo"),
                "activo_tipo": item.get("activo_tipo"),
                "oficina_nombre": item.get("oficina_nombre"),
                "estado": "ausente",
                "descripcion": "Ya no aparece en el archivo. No se borra: queda pendiente de verificar.",
                "diferencias": [],
                "advertencias": [],
            }
        )
        ya_reportados.add(item["_id"])
    lote_id = f"CAMP-{campana.get('codigo')}-{utcnow().strftime('%Y%m%d%H%M%S')}"
    await db["campanas_inventario"].update_one(
        {"_id": campana_id},
        {"$set": {"excel_lote": lote_id, "excel_nombre": nombre, "excel_fecha": utcnow()}},
    )
    return {
        "campana_id": str(campana_id),
        "lote_id": lote_id,
        "resultados": resultados,
        "resumen": {
            "total": len(resultados),
            "nuevos": sum(1 for r in resultados if r["estado"] == "nuevo"),
            "modificados": sum(1 for r in resultados if r["estado"] == "modificado"),
            "sin_cambios": sum(1 for r in resultados if r["estado"] == "sin_cambio"),
            "ausentes": sum(1 for r in resultados if r["estado"] == "ausente"),
        },
    }


async def aceptar_cambios(
    campana_id: ObjectId,
    lote_id: str,
    *,
    acepta: list[str] | None = None,
    rechazar: list[str] | None = None,
    usuario: dict[str, Any],
) -> dict[str, Any]:
    """Acepta o rechaza diferencias por lote. Nunca borra equipos ausentes."""
    db = get_db()
    campana = await db["campanas_inventario"].find_one({"_id": campana_id})
    if campana is None:
        raise NoEncontrado("Campana no encontrada.")
    if campana.get("excel_lote") != lote_id:
        raise Validacion("Ese lote de comparacion ya no es el vigente.")
    if not acepta and not rechazar:
        raise Validacion("Indica que cambios aceptar o rechazar.")
    aceptados = set(acepta or [])
    rechazados = set(rechazar or [])
    if aceptados & rechazados:
        raise Validacion("Hay elementos en aceptar y rechazar a la vez.")
    items = await (db["campana_items"].find({"campana_id": campana_id}).to_list(None))
    por_id = {str(i["_id"]): i for i in items}
    if campana.get("estado") == "cerrada":
        raise Prohibido("La campaña está cerrada; no se pueden aceptar más cambios.")
    if (aceptados | rechazados) - por_id.keys():
        raise Validacion("Hay elementos que no pertenecen a esta campaña.")
    actualizados = 0
    nuevos_creados = 0
    por_verificar = 0
    for clave_item in aceptados:
        item = por_id.get(clave_item)
        if item is None:
            continue
        if item.get("origen") == "excel_nuevo":
            # Un equipo que no existía. Aceptarlo lo marca para que `cerrar` lo
            # cree en el inventario. Antes pasaba por aquí sin más: `nuevos_creados`
            # se contaba en cero y el equipo se perdía sin decir nada.
            await db["campana_items"].update_one(
                {"_id": item["_id"]},
                {"$set": {"estado_item": "nuevo", "actual": item.get("actual") or {}, "diferencias": [], "origen": "excel_nuevo", "verificado_en": utcnow()}},
            )
            nuevos_creados += 1
            continue
        await db["campana_items"].update_one(
            {"_id": item["_id"]},
            {"$set": {"actual": item.get("actual") or item.get("instantanea"), "diferencias": [], "origen": "excel_modificado", "estado_item": "confirmado"}},
        )
        actualizados += 1
    for clave_item in rechazados:
        item = por_id.get(clave_item)
        if item is None:
            continue
        # Rechazar un equipo nuevo lo deja como estaba: pendiente de verificar a
        # mano. No se crea nada.
        await db["campana_items"].update_one(
            {"_id": item["_id"]},
            {"$set": {"actual": item.get("instantanea"), "diferencias": [], "origen": "excel_rechazado", "estado_item": "pendiente"}},
        )
    # Los ausentes pasan a por verificar; jamas se borran
    resultado_ausentes = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "origen": {"$in": ["excel_ausente"]}}
    )
    por_verificar += resultado_ausentes
    await registrar(
        "campana.item",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="campana",
        entidad_id=campana_id,
        resumen=f"{campana.get('codigo')}: {actualizados} cambios aceptados, {nuevos_creados} equipos nuevos aceptados, {len(rechazados)} rechazados",
        despues={"aceptados": actualizados, "nuevos": nuevos_creados, "rechazados": len(rechazados)},
    )
    return {
        "aceptados": actualizados,
        "rechazados": len(rechazados),
        "nuevos_creados": nuevos_creados,
        "por_verificar": por_verificar,
        "resumen": await progreso(campana_id),
    }


async def _registrar_equipo_nuevo(item: dict[str, Any], campana: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    """
    Crea en el inventario un equipo que se encontró en la sala y no estaba.

    La zona sale del **nombre de la hoja** —una hoja, una zona, la misma convención
    que la importación del inventario— y la oficina del nombre de la columna ÁREA.
    Si la oficina no existe se crea, como hace la importación, para que un área
    nueva no bloquee la campaña entera.
    """
    db = get_db()
    datos = item.get("actual") or {}
    zona_nombre = item.get("zona_nombre") or zona_de_hoja(item.get("hoja") or "")
    zona = await db["zonas"].find_one({"nombre_normalizado": clave(zona_nombre)}) or await db["zonas"].find_one(
        {"nombre_normalizado": clave(zona_nombre.replace("ZONA ", ""))}
    )
    if zona is None:
        raise NoEncontrado(f"La zona de la hoja «{zona_nombre}» no está registrada.")
    oficina_nombre = normalizar_texto(item.get("oficina_nombre") or "")
    if not oficina_nombre:
        raise Validacion("La fila no dice a qué oficina pertenece el equipo.")
    zona_id = zona["_id"]
    oficina = await org_service.oficina_por_nombre(oficina_nombre, zona_id, crear=True, usuario=usuario)
    if oficina is None:
        raise NoEncontrado(f"No se pudo resolver la oficina «{oficina_nombre}».")

    tipo = normalizar_texto(item.get("activo_tipo") or datos.get("tipo") or "")
    if len(tipo) < 2:
        tipo = normalizar_texto(item.get("activo_nombre") or datos.get("nombre_equipo") or "")
    if len(tipo) < 2:
        raise Validacion("La fila no dice qué tipo de equipo es.")

    campos = {campo: datos.get(campo) for campo in CAMPOS_BASE if datos.get(campo)}
    return await inventario_service.crear_activo(
        {
            "tipo": tipo,
            "oficina_id": oficina["_id"],
            "nombre_equipo": normalizar_texto(datos.get("nombre_equipo") or item.get("activo_nombre") or "") or None,
            "codigo_patrimonial": normalizar_texto(datos.get("codigo_patrimonial") or item.get("activo_codigo") or "") or None,
            **campos,
        },
        usuario=usuario,
    )


async def cerrar(
    campana_id: ObjectId,
    *,
    marcar_no_localizados: bool = True,
    nota: str | None = None,
    usuario: dict[str, Any],
    confirmacion: bool = True,
) -> dict[str, Any]:
    """Cierre: aplica cambios aceptados y guarda la version historica consultable."""
    if usuario.get("rol") != "administrador":
        raise Prohibido("Solo un administrador puede cerrar una campana.")
    if not confirmacion:
        raise Validacion("El cierre requiere confirmacion explicita.")
    db = get_db()
    campana = await db["campanas_inventario"].find_one({"_id": campana_id})
    if campana is None:
        raise NoEncontrado("Campana no encontrada.")
    if campana.get("estado") == "cerrada":
        raise Conflicto("La campana ya esta cerrada.")

    items = await (db["campana_items"].find({"campana_id": campana_id}).to_list(None))
    aplicados = 0
    no_localizados = 0
    nuevos_registrados = 0
    nuevos_fallidos: list[dict[str, str]] = []
    for item in items:
        estado_item = item.get("estado_item")

        # Un equipo que se encontró en la sala y **no estaba en el inventario**.
        # Esto es lo que hace que la campaña sirva para algo: al cerrar, se
        # registra. Antes esta rama no existía y el equipo se perdía, aunque
        # estuviera aceptado y marcado en la lista.
        if estado_item == "nuevo" and item.get("origen") == "excel_nuevo":
            try:
                activo = await _registrar_equipo_nuevo(item, campana, usuario=usuario)
            except (Validacion, NoEncontrado) as exc:
                # Un equipo sin oficina o sin tipo no se puede crear. No se
                # rompe el cierre entero por una fila: se cuenta aparte y se
                # devuelve el motivo para que se pueda corregir.
                nuevos_fallidos.append(
                    {
                        "equipo": item.get("activo_nombre") or "(sin nombre)",
                        "hoja": item.get("hoja") or "",
                        "numero": str(item.get("numero") or ""),
                        "motivo": str(exc),
                    }
                )
                continue
            await db["campana_items"].update_one(
                {"_id": item["_id"]}, {"$set": {"activo_id": activo["_id"]}}
            )
            item["activo_id"] = activo["_id"]
            item["oficina_nombre"] = activo.get("oficina_nombre", item.get("oficina_nombre"))
            item["zona_nombre"] = activo.get("zona_nombre", item.get("zona_nombre"))
            nuevos_registrados += 1
            continue

        activo_id = item.get("activo_id")
        if activo_id is None:
            continue
        cambios: dict[str, Any] = {}
        if estado_item in {"no_encontrado", "dado_de_baja"} and marcar_no_localizados:
            cambios["estado"] = "Dado de baja" if estado_item == "dado_de_baja" else ESTADO_ITEM_NO_ENCONTRADO
            cambios["observaciones_campana"] = {
                "campana": campana.get("codigo"),
                "estado_item": estado_item,
                "observaciones": item.get("observaciones"),
                "fecha": utcnow().isoformat(),
            }
            no_localizados += 1
        elif item.get("actual") and estado_item in {"confirmado", "cambio_responsable", "cambio_estado", "cambio_oficina"}:
            for campo in CAMPOS_BASE:
                if campo in CAMPOS_BASE and (item.get("actual") or {}).get(campo) != (item.get("instantanea") or {}).get(campo):
                    cambios[campo] = (item.get("actual") or {}).get(campo)
            if item.get("nuevo_oficina_id"):
                oficina = await db["oficinas"].find_one({"_id": item["nuevo_oficina_id"]}) or {}
                cambios.update(
                    {
                        "oficina_id": item["nuevo_oficina_id"],
                        "oficina_nombre": oficina.get("nombre"),
                        "zona_id": oficina.get("zona_id"),
                        "zona_nombre": oficina.get("zona_nombre"),
                    }
                )
            if estado_item == "cambio_responsable" or item.get("responsable_id") is not None:
                cambios["responsable_id"] = item.get("responsable_id")
                cambios["responsable_nombre"] = item.get("responsable_nombre")
        if cambios:
            cambios["actualizado_en"] = utcnow()
            cambios["actualizado_por"] = usuario.get("nombre", "")
            await db["activos"].update_one({"_id": activo_id}, {"$set": cambios})
            item["actual"] = {**(item.get("actual") or item.get("instantanea") or {}), **{k: v for k, v in cambios.items() if k in CAMPOS_BASE}}
            item["oficina_nombre"] = cambios.get("oficina_nombre", item.get("oficina_nombre"))
            item["zona_nombre"] = cambios.get("zona_nombre", item.get("zona_nombre"))
            item["responsable_nombre"] = cambios.get("responsable_nombre", item.get("responsable_nombre"))
            aplicados += 1

    # Version historica consultable
    anio = int(campana["anio"])
    await db["inventario_versiones"].update_one(
        {"anio": anio, "campana_id": campana_id},
        {
            "$set": {
                "anio": anio,
                "campana_id": campana_id,
                "codigo_campana": campana.get("codigo"),
                "cerrado_en": utcnow(),
                "cerrado_por": usuario.get("nombre", ""),
                "nota": nota,
                "total_items": sum(1 for i in items if i.get("activo_id")),
                "total_revisados": len(items),
                "aplicados": aplicados,
                "no_localizados": no_localizados,
                "nuevos_registrados": nuevos_registrados,
                "nuevos_fallidos": nuevos_fallidos,
                "resumen": await progreso(campana_id),
                # La versión guarda los **datos completos** de cada equipo, no solo
                # su código y su nombre. Antes guardaba seis campos sueltos, y eso
                # impedía descargar el año: el Excel de 2026 necesita la marca, el
                # modelo, la RAM, la zona... que no estaban. Lo único que sí había
                # era el `activo_id`, así que reconstruir el año obligaba a leer el
                # inventario de hoy: al descargar 2026 salía 2027 con otro nombre.
                "instantanea": [
                    {
                        "activo_id": i.get("activo_id"),
                        "codigo": i.get("activo_codigo"),
                        "nombre": i.get("activo_nombre"),
                        "oficina": i.get("oficina_nombre"),
                        "responsable": i.get("responsable_nombre"),
                        "estado_item": i.get("estado_item"),
                        "tipo": i.get("activo_tipo"),
                        "conjunto_nombre": i.get("conjunto_nombre"),
                        "zona": i.get("zona_nombre"),
                        # `actual` es el estado en que quedó al cerrar; en un item sin
                        # resolver es la instantánea, que es el dato de partida.
                        "campos": {campo: ((i.get("actual") if i.get("estado_item") in ESTADOS_VERIFICADOS | {"nuevo"} else i.get("instantanea")) or i.get("instantanea") or {}).get(campo) for campo in CAMPOS_BASE},
                    }
                    for i in items if i.get("activo_id")
                ],
            }
        },
        upsert=True,
    )
    await db["campanas_inventario"].update_one(
        {"_id": campana_id},
        {"$set": {"estado": "cerrada", "cerrado_en": utcnow(), "cerrado_por": usuario.get("nombre", ""), "nota_cierre": nota}},
    )
    await registrar(
        "campana.cerrar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="campana",
        entidad_id=campana_id,
        resumen=f"Campana {campana.get('codigo')} cerrada: {nuevos_registrados} equipos nuevos registrados, {aplicados} cambios aplicados, {no_localizados} no localizados",
        despues={
            "nuevos_registrados": nuevos_registrados,
            "aplicados": aplicados,
            "no_localizados": no_localizados,
            "nuevos_fallidos": nuevos_fallidos,
            "nota": nota,
        },
    )
    return {
        "campana_id": str(campana_id),
        "codigo": campana.get("codigo"),
        "anio": anio,
        "estado": "cerrada",
        "aplicados": aplicados,
        "no_localizados": no_localizados,
        "nuevos_registrados": nuevos_registrados,
        "nuevos_fallidos": nuevos_fallidos,
        "mensaje": (
            f"Campana {campana.get('codigo')} cerrada. "
            + (
                f"Se registraron {nuevos_registrados} equipos nuevos. "
                if nuevos_registrados
                else ""
            )
            + f"Se aplicaron {aplicados} cambios y "
            f"{no_localizados} equipos quedaron como '{ESTADO_ITEM_NO_ENCONTRADO}' para seguimiento."
            + (f" {len(nuevos_fallidos)} equipos nuevos no se pudieron registrar." if nuevos_fallidos else "")
        ),
    }


async def versiones() -> list[dict[str, Any]]:
    documentos = await (
        get_db()["inventario_versiones"].find({}, {"instantanea": 0}).sort([("anio", -1), ("cerrado_en", -1), ("_id", -1)]).to_list(None)
    )
    for documento in documentos:
        documento["id"] = documento.pop("_id")
    return documentos


async def eliminar(campana_id: ObjectId, *, usuario: dict[str, Any]) -> dict[str, Any]:
    """
    Borra una campaña: sus equipos de la lista y su versión del histórico.

    **Nunca borra un equipo del inventario.** La campaña es un trabajo de revisión; lo
    que se registra en ella ya está en `activos` y no le pertenece. Como mucho, una
    campaña cerrada puede haber creado equipos al cerrarse, y esos se quedan: son
    inventario real y no se borran por Carpetón.

    Se borran también los equipos nuevos **pendientes** que la campaña detectó pero nadie
    aceptó: nunca llegaron a ser equipos, así que no queda ningún rastro de ellos y su
    historia sería una lista fantasma que volvería a salir en la próxima comparación.

    Una campaña cerrada con cambios ya aplicados se puede borrar, pero su versión del
    histórico se borra con ella: el histórico es la memoria de qué se cerró y cuándo, y
    dejarla sin versión sería un registro que promete un año que ya no se puede
    consultar ni descargar.
    """
    db = get_db()
    campana = await db["campanas_inventario"].find_one({"_id": campana_id})
    if campana is None:
        raise NoEncontrado("Campana no encontrada.")

    pendientes = await db["campana_items"].count_documents(
        {"campana_id": campana_id, "activo_id": None}
    )
    total_items = await db["campana_items"].count_documents({"campana_id": campana_id})
    borrados_items = (await db["campana_items"].delete_many({"campana_id": campana_id})).deleted_count
    borradas_versiones = (
        await db["inventario_versiones"].delete_many({"campana_id": campana_id})
    ).deleted_count
    await db["campanas_inventario"].delete_one({"_id": campana_id})
    await registrar(
        "campana.eliminar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="campana",
        entidad_id=campana_id,
        resumen=f"Campana eliminada: {campana.get('codigo')} ({total_items} equipos de la lista)",
        antes={"codigo": campana.get("codigo"), "nombre": campana.get("nombre"), "estado": campana.get("estado")},
        despues={
            "items_borrados": borrados_items,
            "versiones_borradas": borradas_versiones,
            "nuevos_pendientes_descartados": pendientes,
            "equipos_del_inventario_afectados": 0,
        },
    )
    return {
        "campana_id": str(campana_id),
        "codigo": campana.get("codigo"),
        "items_borrados": borrados_items,
        "versiones_borradas": borradas_versiones,
        "nuevos_pendientes_descartados": pendientes,
        "mensaje": (
            f"Se eliminó la campaña {campana.get('codigo')} y sus {borrados_items} equipos de la lista. "
            "El inventario no se ha tocado."
        ),
    }


async def exportar_version_excel(version_id: ObjectId) -> tuple[bytes, int, str]:
    """
    Descarga el inventario tal y como quedó en un año cerrado.

    Cada versión cerrada es un año del inventario que ya no existe en ninguna otra parte:
    `activos` va cambiando, así que el inventario de 2026 no se puede leer de ahí —solo
    se lee el de hoy—. Por eso la versión guarda los datos completos de cada equipo.

    Las versiones anteriores a eso guardaban solo seis campos y su `activo_id`. Esas se
    reconstruyen leyendo el inventario actual de los equipos que siguen existiendo, y se
    avisa de ello en la descarga: es lo mejor que hay, pero **no** es el estado de aquel
    año, y decirlo evita que alguien tome el archivo por un histórico fiel.
    """
    from app.services.excel_service import COLUMNAS_OFICIALES, exportar_inventario_por_zonas

    db = get_db()
    version = await db["inventario_versiones"].find_one({"_id": version_id})
    if version is None:
        raise NoEncontrado("No hay una versión cerrada con ese identificador.")

    instantanea = version.get("instantanea") or []
    filas_completas = [i for i in instantanea if i.get("campos") is not None]
    reconstruida = not filas_completas

    activos: dict[str, dict[str, Any]] = {}
    if reconstruida and instantanea:
        ids = [i["activo_id"] for i in instantanea if i.get("activo_id")]
        for activo in await db["activos"].find({"_id": {"$in": ids}}).to_list(None):
            activos[str(activo["_id"])] = activo

    zonas: dict[str, list[dict[str, Any]]] = {}
    omitidos = 0
    for entrada in instantanea:
        activo = activos.get(str(entrada.get("activo_id"))) if reconstruida else None
        campos = dict(entrada.get("campos") or {})
        if reconstruida:
            if activo is None:
                # El equipo ya no está en el inventario: se salió de baja o se borró.
                # No se inventa su ficha de aquel año.
                omitidos += 1
                continue
            campos = {campo: activo.get(campo) for campo in CAMPOS_BASE}
        zona = normalizar_texto(entrada.get("zona")) or normalizar_texto((activo or {}).get("zona_nombre")) or "SIN ZONA"
        fila = {
            "AREA": entrada.get("oficina") or (activo or {}).get("oficina_nombre"),
            "Tipo de equipo": campos.get("tipo_equipo") or entrada.get("conjunto_nombre") or (activo or {}).get("conjunto_nombre") or entrada.get("tipo"),
            "Dispositivo": campos.get("dispositivo") or entrada.get("nombre") or campos.get("nombre_equipo"),
            "Código patrimonial": entrada.get("codigo") or campos.get("codigo_patrimonial"),
            "Marca": campos.get("marca"),
            "Modelo": campos.get("modelo"),
            "Tamaño Pantalla": campos.get("tamano_pantalla"),
            "Nombre Equipo": campos.get("nombre_equipo") or entrada.get("nombre"),
            "Procesador": campos.get("procesador"),
            "Memoria RAM": campos.get("memoria_ram"),
            "Almacenamiento": campos.get("almacenamiento"),
            "Direccion IP": campos.get("direccion_ip"),
            "Direccion MAC": campos.get("direccion_mac"),
            "Propiedad": campos.get("propiedad"),
            "Estado": campos.get("estado"),
            "Responsable": entrada.get("responsable"),
        }
        zonas.setdefault(zona, []).append({columna: fila.get(columna) or "" for columna in COLUMNAS_OFICIALES})

    contenido = exportar_inventario_por_zonas(zonas)
    anio = version.get("anio")
    nombre = f"inventario-{anio}-{normalizar_texto(version.get('codigo_campana') or '').lower()}".strip("-")
    return contenido, len(instantanea), nombre


async def comparar_anios(anio_a: int, anio_b: int) -> dict[str, Any]:
    """Compara dos versiones historicas del inventario."""
    db = get_db()
    va = await db["inventario_versiones"].find_one({"anio": anio_a})
    vb = await db["inventario_versiones"].find_one({"anio": anio_b})
    if va is None or vb is None:
        return {
            "suficiente_datos": False,
            "mensaje": "Hacen falta las versiones cerradas de ambos anios para comparar.",
            "anios_disponibles": [d["anio"] for d in await (db["inventario_versiones"].find({}, {"anio": 1}).to_list(None))],
        }
    mapa_a = {i.get("codigo") or i.get("nombre"): i for i in va.get("instantanea", [])}
    mapa_b = {i.get("codigo") or i.get("nombre"): i for i in vb.get("instantanea", [])}
    altas = sorted(set(mapa_b) - set(mapa_a))
    bajas = sorted(set(mapa_a) - set(mapa_b))
    traslados = []
    cambios_responsable = []
    for clave_comun in set(mapa_a) & set(mapa_b):
        a, b = mapa_a[clave_comun], mapa_b[clave_comun]
        if a.get("oficina") != b.get("oficina"):
            traslados.append({"codigo": clave_comun, "nombre": b.get("nombre"), "de": a.get("oficina"), "a": b.get("oficina")})
        if a.get("responsable") != b.get("responsable"):
            cambios_responsable.append({"codigo": clave_comun, "nombre": b.get("nombre"), "de": a.get("responsable"), "a": b.get("responsable")})
    comun = len(set(mapa_a) & set(mapa_b))
    return {
        "suficiente_datos": True,
        "anios": [anio_a, anio_b],
        "totales": {str(anio_a): len(mapa_a), str(anio_b): len(mapa_b)},
        "altas": [{"codigo": c, "nombre": mapa_b[c].get("nombre")} for c in altas],
        "bajas": [{"codigo": c, "nombre": mapa_a[c].get("nombre")} for c in bajas],
        "traslados": traslados,
        "cambios_responsable": cambios_responsable,
        "porcentaje_cambio": round(100 * (len(altas) + len(bajas) + len(traslados)) / max(len(mapa_a), 1), 1),
        "comunes": comun,
    }


async def campana_activa() -> dict[str, Any] | None:
    """
    La campaña con la que se abre la pantalla.

    `find_one` sin orden devolvía **una al azar** entre las abiertas y las que ya
    están en verificación. En el municipio salía una campaña de 877 equipos en
    estado `verificacion` mientras la única `abierta` se quedaba sin verse, que es
    justo la que se está empezando.

    Ahora se escoge por criterio y no por azar: primero la que está `abierta` —es
    la que todavía se configura desde el principio— y, si no hay ninguna, la más
    reciente de las que ya están en verificación.
    """
    db = get_db()
    campana = await db["campanas_inventario"].find_one(
        {"estado": "abierta"}, sort=[("creado_en", -1)]
    ) or await db["campanas_inventario"].find_one(
        {"estado": "verificacion"}, sort=[("creado_en", -1)]
    )
    if campana is None:
        return None
    resumen = await progreso(campana["_id"])
    return {
        **_resumen(campana["_id"], resumen),
        # `total_items` faltaba aquí y sí viene en `listar()`. El frontend lo usa
        # para «Equipos en la campaña»; sin él tenía que recurrir a `por_verificar`
        # y el indicador mostraba los que faltaban con el nombre del total.
        "total_items": resumen["total_items"],
        "codigo": campana.get("codigo"),
        "nombre": campana.get("nombre"),
        "anio": campana.get("anio"),
        "estado": campana.get("estado"),
        "total_registrados": resumen["total_registrados"],
        "nuevos_sin_decidir": resumen["nuevos_sin_decidir"],
    }


async def validar_alcance(datos: dict[str, Any]) -> dict[str, Any]:
    """Comprueba que las zonas/oficinas indicadas existan antes de crear la campana."""
    db = get_db()
    for zona in datos.get("zona_ids") or []:
        if not await db["zonas"].find_one({"_id": id_requerido(zona, "zona")}):
            raise NoEncontrado("Una de las zonas indicadas no existe.")
    for oficina in datos.get("oficina_ids") or []:
        if not await db["oficinas"].find_one({"_id": id_requerido(oficina, "oficina")}):
            raise NoEncontrado("Una de las oficinas indicadas no existe.")
    return {"ok": True}


async def exportar_inventario_campana(campana_id: ObjectId) -> dict[str, Any]:
    """Filas para el Excel/PDF de la campana (misma estructura de la plantilla)."""
    db = get_db()
    items = await (db["campana_items"].find({"campana_id": campana_id}).to_list(None))
    filas: list[dict[str, Any]] = []
    from app.services.excel_service import COLUMNAS_OFICIALES, CAMPOS_A_COLUMNAS

    mapa_columna = {campo: columna for campo, columna in CAMPOS_A_COLUMNAS.items()}
    for item in sorted(items, key=lambda i: (i.get("zona_nombre") or "", i.get("oficina_nombre") or "", i.get("activo_nombre") or "")):
        fila = {
            "AREA": item.get("oficina_nombre"),
            "Tipo de equipo": item.get("conjunto_nombre"),
            "Dispositivo": item.get("activo_tipo"),
            "Código patrimonial": item.get("activo_codigo"),
            "Nombre Equipo": item.get("activo_nombre"),
            "Estado": (item.get("actual") or {}).get("estado"),
            "Responsable": item.get("responsable_nombre") or "",
            "_estado_verificacion": item.get("estado_item"),
            "_observaciones": item.get("observaciones"),
        }
        filas.append({columna: fila.get(columna, "") for columna in COLUMNAS_OFICIALES})
    return {"filas": filas, "columnas": COLUMNAS_OFICIALES, "total": len(filas)}


async def asegurar_pendientes(campana_id: ObjectId) -> int:
    return await get_db()["campana_items"].count_documents({"campana_id": campana_id, "estado_item": "pendiente"})
