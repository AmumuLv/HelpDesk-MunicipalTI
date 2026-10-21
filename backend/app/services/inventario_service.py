"""Inventario: conjuntos, activos, estado por campo, responsables y completitud.

Regla de oro del modulo: solo son obligatorios el TIPO y la OFICINA. Todo lo demas
puede quedar vacio (queda "Pendiente" y avisa), marcarse "No aplica" o "No disponible".
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.collation import Collation
from pymongo import ReturnDocument

from app.core.audit import registrar
from app.domain.equipos import componente_escritorio
from app.core.db import get_db
from app.core.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from app.core.ids import (
    clave,
    id_requerido,
    limpiar_codigo_patrimonial,
    mcp_ip,
    mcp_mac,
    normalizar_texto,
    siguiente_numero_conjunto,
)
from app.core.time import utcnow
from app.domain.constants import (
    CAMPO_ESTADO,
    CAMPO_NO_APLICA,
    CAMPO_NO_DISPONIBLE,
    CAMPO_PENDIENTE,
    CAMPOS_BASE,
    CAMPOS_CON_ESTADO,
)
from app.services import catalogo_service

PREFIJO_CLAVE = "activo"


async def recalcular_faltantes(consulta: dict[str, Any]) -> None:
    from pymongo import UpdateOne
    db = get_db()
    operaciones = []
    async for activo in db['activos'].find(consulta):
        faltantes = (await calcular_completitud(activo))['faltantes']
        operaciones.append(UpdateOne({'_id': activo['_id']}, {'$set': {'faltantes_count': faltantes}}))
        if len(operaciones) >= 250:
            await db['activos'].bulk_write(operaciones)
            operaciones = []
    if operaciones:
        await db['activos'].bulk_write(operaciones)


# ── Clave natural (idempotencia de la importacion) ──────────
def construir_clave_natural(oficina_id: ObjectId, conjunto_nombre: str | None, tipo: str, indice: int) -> str:
    """Clave estable para identificar un equipo sin codigo patrimonial.

    Usa el **nombre** del conjunto y no su identificador: asi la clave no depende
    de si el conjunto todavia no existe, y dos importaciones del mismo archivo
    generan exactamente la misma clave (idempotencia).
    """
    partes = [str(oficina_id), clave(conjunto_nombre) if conjunto_nombre else "-", clave(tipo)]
    if indice:
        partes.append(f"#{indice}")
    return "|".join(partes)


async def _contador_clave(oficina_id: ObjectId, conjunto_nombre: str | None, tipo: str) -> int:
    prefijo = construir_clave_natural(oficina_id, conjunto_nombre, tipo, 0)
    total = await get_db()["activos"].count_documents({"clave_natural": {"$regex": f"^{re.escape(prefijo)}"}})
    return total + 1


# ── Estado por campo ─────────────────────────────────────────
def _estado_campo(activo: dict[str, Any], campo: str) -> dict[str, Any]:
    return (activo.get("campos_estado") or {}).get(campo) or {"estado": CAMPO_PENDIENTE}


async def calcular_completitud(activo: dict[str, Any]) -> dict[str, Any]:
    """Calcula completitud segun el esquema del tipo.

    Un campo marcado "No aplica" o "No disponible" sale del denominador.
    """
    esquema = await catalogo_service.esquema(activo.get("tipo", ""))
    esperados = list(esquema["esperados"])
    campos_estado = activo.get("campos_estado") or {}
    detalle: dict[str, Any] = {}
    completos = 0
    contables = 0
    faltantes_lista: list[str] = []
    for campo in CAMPOS_BASE:
        info = _estado_campo(activo, campo)
        valor = activo.get(campo)
        hay_valor = bool(valor and str(valor).strip())
        esperado = campo in esperados
        excluido = info.get("estado") in (CAMPO_NO_APLICA, CAMPO_NO_DISPONIBLE)
        if excluido:
            contables += 0
            completo = True
        else:
            if esperado:
                contables += 1
            if esperado and not hay_valor:
                faltantes_lista.append(campo)
                completo = False
            elif esperado and hay_valor:
                completos += 1
                completo = True
            else:
                completo = True  # opcional: nunca resta
        detalle[campo] = {
            "estado": info.get("estado", CAMPO_PENDIENTE),
            "valor": valor,
            "motivo": info.get("motivo"),
            "nota": info.get("nota"),
            "esperado": esperado,
            "completo": completo,
            "usuario_nombre": info.get("usuario_nombre"),
            "fecha": info.get("fecha"),
        }
    porcentaje = round(100 * completos / contables, 1) if contables else 100.0
    return {
        "porcentaje": porcentaje,
        "completos": completos,
        "esperados": contables,
        "faltantes": len(faltantes_lista),
        "campos_faltantes": faltantes_lista,
        "campos": detalle,
        "derivados": _campos_derivados(activo),
    }


def _campos_derivados(activo: dict[str, Any]) -> list[str]:
    """Campos basicos alimentados por el detalle avanzado."""
    if not activo.get("opciones_avanzadas"):
        return []
    detalle = activo.get("detalle_avanzado") or {}
    derivados: list[str] = []
    if detalle.get("memoria_modulos"):
        derivados.append("memoria_ram")
    if detalle.get("almacenamiento_unidades"):
        derivados.append("almacenamiento")
    return derivados


def _conexion_impresora(datos: dict[str, Any], tipo: str, antes: dict[str, Any] | None = None) -> dict[str, Any]:
    if 'direccion_ip' not in datos:
        return datos
    entrada = normalizar_texto(datos.get('direccion_ip')).casefold()
    usb = entrada in {'usb', 'cable usb'}
    anterior_usb = ((antes or {}).get('campos_estado') or {}).get('direccion_ip', {}).get('motivo') == 'Cable USB'
    if not usb and not anterior_usb:
        return datos
    if usb and clave(tipo) != 'IMPRESORA':
        raise Validacion('Cable USB solo puede sustituir la IP en una impresora.')
    estados = dict(datos.get('campos_estado') or {})
    estados['direccion_ip'] = {'estado': CAMPO_NO_APLICA, 'motivo': 'Cable USB'} if usb else {'estado': CAMPO_PENDIENTE}
    return {**datos, 'direccion_ip': None if usb else datos.get('direccion_ip'), 'campos_estado': estados}


def _normalizar_campos(datos: dict[str, Any]) -> dict[str, Any]:
    salida: dict[str, Any] = {}
    for campo in CAMPOS_BASE:
        if campo not in datos:
            continue
        valor = datos.get(campo)
        if campo == "codigo_patrimonial":
            salida[campo] = limpiar_codigo_patrimonial(valor)
        elif campo == "direccion_ip":
            ip = mcp_ip(valor)
            if ip is None and normalizar_texto(valor):
                raise Validacion(f"'{valor}' no es una direccion IP valida.", detalles={"campo": campo})
            salida[campo] = ip
        elif campo == "direccion_mac":
            mac = mcp_mac(valor)
            if mac is None and normalizar_texto(valor):
                raise Validacion(f"'{valor}' no es una direccion MAC valida.", detalles={"campo": campo})
            salida[campo] = mac
        else:
            texto = normalizar_texto(valor)
            salida[campo] = texto or None
    return salida


# ── Conjuntos ────────────────────────────────────────────────
async def numeracion_sugerida(oficina_id: ObjectId, base: str = "Computadora") -> str:
    nombres = await (get_db()["conjuntos"].find({"oficina_id": oficina_id}, {"nombre": 1, "numero": 1}).to_list(None))
    ocupados = {n['numero'] for n in nombres if isinstance(n.get('numero'), int)}
    numero = siguiente_numero_conjunto(oficina_id, [n.get("nombre", "") for n in nombres])
    while numero in ocupados:
        numero += 1
    return f"{base} N°{numero}"


async def crear_conjunto(datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    oficina_id = id_requerido(datos.get("oficina_id"), "oficina")
    oficina = await db["oficinas"].find_one({"_id": oficina_id})
    if oficina is None:
        raise NoEncontrado("La oficina indicada no existe.")
    nombre = normalizar_texto(datos.get("nombre"))
    if len(nombre) < 2:
        raise Validacion("El nombre del conjunto es obligatorio.")

    numero = datos.get("numero")
    sufijo = re.search(r'(?:n[°º.]?\s*|[-_\s]+)(\d+)\s*$', nombre, re.IGNORECASE)
    if sufijo:
        numero_nombre = int(sufijo.group(1))
        if numero is not None and numero != numero_nombre:
            raise Validacion('El número del nombre y el número asignado deben coincidir.')
        numero = numero_nombre
    if numero is None:
        existentes = await (db["conjuntos"].find({"oficina_id": oficina_id}, {"numero": 1}).to_list(None))
        numeros = [e["numero"] for e in existentes if isinstance(e.get("numero"), int)]
        numero = (max(numeros) + 1) if numeros else 1
    else:
        numero = int(numero)
        if numero < 1:
            raise Validacion('El número del conjunto debe ser mayor que cero.')
        if await db["conjuntos"].find_one({"oficina_id": oficina_id, "numero": numero}):
            raise Conflicto(f"Ya existe '{nombre}' con el numero {numero} en esa oficina.")

    responsable_id = id_requerido(datos["responsable_id"], "responsable") if datos.get("responsable_id") else None
    responsable_nombre = None
    if responsable_id:
        from app.services import usuario_service

        persona = await usuario_service.obtener(responsable_id)
        if persona.get("oficina_id") and persona["oficina_id"] != oficina_id:
            raise Validacion(
                "El responsable pertenece a otra oficina. Confirma la transferencia o el prestamo.",
                detalles={"oficina_usuario": persona.get("oficina_nombre")},
            )
        responsable_nombre = persona.get("nombre")

    doc = {
        "nombre": nombre,
        "nombre_normalizado": clave(nombre),
        "numero": numero,
        "oficina_id": oficina_id,
        "oficina_nombre": oficina.get("nombre"),
        "zona_id": oficina.get("zona_id"),
        "zona_nombre": oficina.get("zona_nombre"),
        "responsable_id": responsable_id,
        "responsable_nombre": responsable_nombre,
        "uso_comun": bool(datos.get("uso_comun")) and not responsable_id,
        "estado": normalizar_texto(datos.get("estado")) or "Operativo",
        "notas": normalizar_texto(datos.get("notas")) or None,
        "activo": True,
        "creado_en": utcnow(),
        "creado_por": usuario.get("nombre", ""),
        "actualizado_en": utcnow(),
    }
    resultado = await db["conjuntos"].insert_one(doc)
    doc["_id"] = resultado.inserted_id
    if responsable_id:
        await _registrar_historial_responsable("conjunto", doc["_id"], responsable_id, responsable_nombre, None, "Asignacion inicial", usuario)
    await registrar(
        "conjunto.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="conjunto",
        entidad_id=doc["_id"],
        resumen=f"Conjunto creado: {nombre} en {oficina.get('nombre')}",
        despues={"nombre": nombre, "oficina": oficina.get("nombre"), "numero": numero},
    )
    return doc


async def actualizar_conjunto(conjunto_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    antes = await db["conjuntos"].find_one({"_id": conjunto_id})
    if antes is None:
        raise NoEncontrado("Conjunto no encontrado.")
    cambios: dict[str, Any] = {}
    if datos.get("nombre"):
        sufijo = re.search(r'(?:n[°º.]?\s*|[-_\s]+)(\d+)\s*$', normalizar_texto(datos['nombre']), re.IGNORECASE)
        if sufijo and int(sufijo.group(1)) != antes.get('numero'):
            numero = int(sufijo.group(1))
            if numero < 1:
                raise Validacion('El número del conjunto debe ser mayor que cero.')
            if await db['conjuntos'].find_one({'oficina_id': antes['oficina_id'], 'numero': numero, '_id': {'$ne': conjunto_id}}):
                raise Conflicto(f'El número {numero} ya está ocupado en esta oficina.')
            cambios['numero'] = numero
        cambios["nombre"] = normalizar_texto(datos["nombre"])
        cambios["nombre_normalizado"] = clave(datos["nombre"])
    if datos.get("estado"):
        cambios["estado"] = normalizar_texto(datos["estado"])
    if "notas" in datos:
        cambios["notas"] = normalizar_texto(datos.get("notas")) or None
    if "activo" in datos and datos["activo"] is not None:
        cambios["activo"] = bool(datos["activo"])
    if cambios:
        cambios["actualizado_en"] = utcnow()
        await db["conjuntos"].update_one({"_id": conjunto_id}, {"$set": cambios})
        if 'nombre' in cambios:
            await db['activos'].update_many({'conjunto_id': conjunto_id}, {'$set': {'conjunto_nombre': cambios['nombre']}})
    if "responsable_id" in datos:
        await cambiar_responsable(
            "conjunto", conjunto_id, datos.get("responsable_id"), usuario=usuario, motivo=datos.get("motivo")
        )
    despues = await db["conjuntos"].find_one({"_id": conjunto_id})
    await registrar(
        "conjunto.editar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="conjunto",
        entidad_id=conjunto_id,
        resumen=f"Conjunto actualizado: {despues.get('nombre')}",
        antes={k: antes.get(k) for k in cambios},
        despues={k: despues.get(k) for k in cambios},
    )
    return despues


async def listar_conjuntos(
    *, zona_id: ObjectId | None = None, oficina_id: ObjectId | None = None, texto: str | None = None, con_detalle: bool = True
) -> list[dict[str, Any]]:
    db = get_db()
    consulta: dict[str, Any] = {"activo": True}
    if zona_id:
        consulta["zona_id"] = zona_id
    if oficina_id:
        consulta["oficina_id"] = oficina_id
    if texto:
        consulta["nombre"] = {"$regex": re.escape(normalizar_texto(texto)), "$options": "i"}
    conjuntos = await (db["conjuntos"].find(consulta).sort([("oficina_nombre", 1), ("numero", 1)]).to_list(None))
    if not con_detalle:
        return conjuntos
    for conjunto in conjuntos:
        activos = await (db["activos"].find({"conjunto_id": conjunto["_id"]}).to_list(None))
        conjunto["total_activos"] = len(activos)
        conjunto['componentes'] = [{'id': str(a['_id']), 'tipo': a.get('tipo'), 'nombre': a.get('nombre_equipo'), 'numero_equipo': a.get('numero_equipo')} for a in activos]
        conjunto['siguiente_numero_equipo'] = max(conjunto.get('ultimo_numero_equipo', 0), max((a.get('numero_equipo') or 0 for a in activos), default=0)) + 1
        conjunto["activos_operativos"] = sum(1 for a in activos if (a.get("estado") or "") == "Operativo")
        conjunto["opciones_avanzadas"] = sum(1 for a in activos if a.get("opciones_avanzadas"))
        puntajes = [await calcular_completitud(a) for a in activos]
        conjunto["completitud"] = round(sum(p["porcentaje"] for p in puntajes) / len(puntajes), 1) if puntajes else 0.0
        conjunto["pendientes"] = sum(p["faltantes"] for p in puntajes)
    return conjuntos


# ── Activos ──────────────────────────────────────────────────
async def asignar_numero_equipo(conjunto_id: ObjectId) -> int:
    db = get_db()
    ultimo = await db['activos'].find_one({'conjunto_id': conjunto_id, 'numero_equipo': {'$type': 'number'}}, sort=[('numero_equipo', -1)])
    await db['conjuntos'].update_one({'_id': conjunto_id}, {'$max': {'ultimo_numero_equipo': (ultimo or {}).get('numero_equipo', 0)}})
    conjunto = await db['conjuntos'].find_one_and_update({'_id': conjunto_id}, {'$inc': {'ultimo_numero_equipo': 1}}, return_document=ReturnDocument.AFTER)
    if not conjunto:
        raise NoEncontrado('El conjunto indicado no existe.')
    return conjunto['ultimo_numero_equipo']


async def crear_activo(
    datos: dict[str, Any],
    *,
    usuario: dict[str, Any],
    registrar_sugerencias: bool = True,
    clave_natural: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    tipo = normalizar_texto(datos.get("tipo"))
    datos = _conexion_impresora(datos, tipo)
    if len(tipo) < 2:
        raise Validacion("Indica el tipo de equipo (por ejemplo: CPU, Laptop, Impresora).")
    oficina_id = id_requerido(datos.get("oficina_id"), "oficina")
    oficina = await db["oficinas"].find_one({"_id": oficina_id})
    if oficina is None:
        raise NoEncontrado("La oficina indicada no existe.")
    conjunto_id = id_requerido(datos["conjunto_id"], "conjunto") if datos.get("conjunto_id") else None
    conjunto = None
    if conjunto_id and not componente_escritorio(tipo):
        raise Validacion("Solo CPU, monitor, teclado y mouse pueden formar un conjunto de escritorio.")
    if conjunto_id:
        conjunto = await db["conjuntos"].find_one({"_id": conjunto_id})
        if conjunto is None:
            raise NoEncontrado("El conjunto indicado no existe.")
        if conjunto["oficina_id"] != oficina_id:
            raise Validacion("El conjunto pertenece a otra oficina.")

    campos = _normalizar_campos(datos)

    responsable_id = id_requerido(datos["responsable_id"], "responsable") if datos.get("responsable_id") else None
    if responsable_id is None and conjunto is not None:
        responsable_id = conjunto.get("responsable_id")
    responsable_nombre = None
    if responsable_id:
        from app.services import usuario_service

        persona = await usuario_service.obtener(responsable_id)
        responsable_nombre = persona.get("nombre")

    campos_estado = _construir_campos_estado(datos.get("campos_estado") or {}, usuario)
    nombre_conjunto = conjunto.get("nombre") if conjunto else None
    if clave_natural:
        prefijo = clave_natural
    else:
        prefijo = construir_clave_natural(oficina_id, nombre_conjunto, tipo, await _contador_clave(oficina_id, nombre_conjunto, tipo))
    doc: dict[str, Any] = {
        "tipo": tipo,
        "tipo_normalizado": clave(tipo),
        "oficina_id": oficina_id,
        "oficina_nombre": oficina.get("nombre"),
        "zona_id": oficina.get("zona_id"),
        "zona_nombre": oficina.get("zona_nombre"),
        "conjunto_id": conjunto_id,
        "conjunto_nombre": conjunto.get("nombre") if conjunto else None,
        "numero_equipo": await asignar_numero_equipo(conjunto_id) if conjunto_id else None,
        "responsable_id": responsable_id,
        "responsable_nombre": responsable_nombre,
        "uso_comun": bool(conjunto.get("uso_comun")) if conjunto else False,
        "campos_estado": campos_estado,
        "opciones_avanzadas": bool(datos.get("opciones_avanzadas", False)),
        "detalle_avanzado": datos.get("detalle_avanzado") if datos.get("opciones_avanzadas") else None,
        "clave_natural": prefijo,
        "version": 1,
        "creado_en": utcnow(),
        "creado_por": usuario.get("nombre", ""),
        "actualizado_en": utcnow(),
        "actualizado_por": usuario.get("nombre", ""),
    }
    doc.update({c: None for c in CAMPOS_BASE})
    doc.update(campos)
    if normalizar_texto(doc.get('propiedad')).casefold() == 'personal':
        doc['codigo_patrimonial'] = None
        campos_estado.update(_construir_campos_estado({
            'codigo_patrimonial': {'estado': CAMPO_NO_APLICA, 'motivo': 'Equipo de propiedad personal'},
        }, usuario))
    if not doc.get("nombre_equipo") and conjunto:
        doc["nombre_equipo"] = f"{conjunto['nombre']} - {tipo}"
    doc["estado"] = doc.get("estado") or "Operativo"
    if campos_estado.get(CAMPO_ESTADO, {}).get("estado") == CAMPO_PENDIENTE:
        campos_estado[CAMPO_ESTADO] = {
            "estado": CAMPO_PENDIENTE,
            "usuario_nombre": usuario.get("nombre"),
            "fecha": utcnow(),
        }

    doc['faltantes_count'] = (await calcular_completitud(doc))['faltantes']
    resultado = await db["activos"].insert_one(doc)
    doc["_id"] = resultado.inserted_id
    if responsable_id and not conjunto:
        await _registrar_historial_responsable(
            "activo", doc["_id"], responsable_id, responsable_nombre, None, "Asignacion inicial", usuario
        )
    if registrar_sugerencias:
        await _registrar_sugerencias(doc)
    await registrar(
        "activo.crear",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="activo",
        entidad_id=doc["_id"],
        resumen=f"Equipo creado: {tipo} en {oficina.get('nombre')}",
        despues={
            "tipo": tipo,
            "oficina": oficina.get("nombre"),
            "codigo_patrimonial": doc.get("codigo_patrimonial"),
            "nombre": doc.get("nombre_equipo"),
        },
    )
    return doc


def _construir_campos_estado(entrada: dict[str, Any], usuario: dict[str, Any]) -> dict[str, Any]:
    salida: dict[str, Any] = {}
    for campo, valor in (entrada or {}).items():
        if campo not in CAMPOS_CON_ESTADO:
            continue
        if isinstance(valor, str):
            estado, motivo, nota = valor, None, None
        else:
            estado = valor.get("estado", CAMPO_PENDIENTE)
            motivo = valor.get("motivo")
            nota = valor.get("nota")
        if estado not in (CAMPO_PENDIENTE, CAMPO_NO_APLICA, CAMPO_NO_DISPONIBLE):
            estado = CAMPO_PENDIENTE
        salida[campo] = {
            "estado": estado,
            "motivo": normalizar_texto(motivo) or None,
            "nota": normalizar_texto(nota) or None,
            "usuario_id": usuario.get("_id"),
            "usuario_nombre": usuario.get("nombre"),
            "fecha": utcnow(),
        }
    return salida


async def _registrar_sugerencias(activo: dict[str, Any]) -> None:
    valores = [
        (campo, activo.get(campo), activo.get("tipo"), activo.get("marca"))
        for campo in (
            "marca",
            "modelo",
            "procesador",
            "memoria_ram",
            "almacenamiento",
            "tamano_pantalla",
            "propiedad",
            "estado",
            "nombre_equipo",
        )
        if activo.get(campo)
    ]
    if valores:
        await catalogo_service.registrar_lote(valores)


async def actualizar_activo(activo_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    antes = await db["activos"].find_one({"_id": activo_id})
    if antes is None:
        raise NoEncontrado("Equipo no encontrado.")
    datos = _conexion_impresora(datos, datos.get('tipo') or antes.get('tipo') or '', antes)
    cambios = _normalizar_campos(datos)
    if "observaciones" in datos:
        cambios["observaciones"] = normalizar_texto(datos.get("observaciones")) or None
    if "tipo" in datos and datos["tipo"]:
        cambios["tipo"] = normalizar_texto(datos["tipo"])
        cambios["tipo_normalizado"] = clave(datos["tipo"])
    if "oficina_id" in datos and datos["oficina_id"]:
        oficina_id = id_requerido(datos["oficina_id"], "oficina")
        oficina = await db["oficinas"].find_one({"_id": oficina_id})
        if oficina is None:
            raise NoEncontrado("La oficina indicada no existe.")
        cambios.update(
            {
                "oficina_id": oficina_id,
                "oficina_nombre": oficina.get("nombre"),
                "zona_id": oficina.get("zona_id"),
                "zona_nombre": oficina.get("zona_nombre"),
            }
        )
    if datos.get("conjunto_id") and not componente_escritorio(cambios.get("tipo", antes.get("tipo"))):
        raise Validacion("Este dispositivo es independiente; selecciona Sin conjunto.")
    if "tipo" in cambios and not componente_escritorio(cambios["tipo"]) and "conjunto_id" not in datos:
        datos = {**datos, "conjunto_id": None}
    if "conjunto_id" in datos:
        conjunto_id = id_requerido(datos["conjunto_id"], "conjunto") if datos.get("conjunto_id") else None
        conjunto = await db["conjuntos"].find_one({"_id": conjunto_id}) if conjunto_id else None
        if conjunto_id and conjunto is None:
            raise NoEncontrado("El conjunto indicado no existe.")
        # El conjunto tiene que ser de la misma oficina que el equipo. Al crear ya
        # se comprobaba, pero al editar no, y desde la ficha se puede cambiar la
        # oficina y el conjunto en la misma llamada: un equipo podía quedar en
        # MERCADO con un conjunto de PALACIO. Se mira la oficina **resultante**,
        # que puede ser la que viene en este mismo cambio, no solo la anterior.
        oficina_del_equipo = cambios.get("oficina_id") or antes.get("oficina_id")
        if conjunto is not None and conjunto.get("oficina_id") != oficina_del_equipo:
            raise Validacion("El conjunto pertenece a otra oficina.")
        cambios["conjunto_id"] = conjunto_id
        cambios["conjunto_nombre"] = conjunto.get("nombre") if conjunto else None
        if conjunto_id != antes.get('conjunto_id'):
            cambios['numero_equipo'] = await asignar_numero_equipo(conjunto_id) if conjunto_id else None
        if conjunto:
            cambios["uso_comun"] = bool(conjunto.get("uso_comun"))
            if conjunto.get("responsable_id") and "responsable_id" not in datos:
                cambios["responsable_id"] = conjunto["responsable_id"]
                cambios["responsable_nombre"] = conjunto.get("responsable_nombre")
    await _aplicar_detalle_avanzado(activo_id, antes, datos, cambios, usuario)
    if "campos_estado" in datos and datos["campos_estado"] is not None:
        nuevos = _construir_campos_estado(datos["campos_estado"], usuario)
        campos_estado = dict(antes.get("campos_estado") or {})
        campos_estado.update(nuevos)
        cambios["campos_estado"] = campos_estado
    if cambios:
        cambios['faltantes_count'] = (await calcular_completitud({**antes, **cambios}))['faltantes']
        cambios["actualizado_en"] = utcnow()
        cambios["actualizado_por"] = usuario.get("nombre", "")
        cambios["version"] = int(antes.get("version", 1)) + 1
        await db["activos"].update_one({"_id": activo_id}, {"$set": cambios})
        await _registrar_sugerencias({**antes, **cambios})
    if "responsable_id" in datos:
        await cambiar_responsable(
            "activo", activo_id, datos.get("responsable_id"), usuario=usuario, motivo=datos.get("motivo")
        )
    despues = await db["activos"].find_one({"_id": activo_id})
    await registrar(
        "activo.editar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="activo",
        entidad_id=activo_id,
        resumen=f"Equipo actualizado: {despues.get('nombre_equipo') or despues.get('tipo')}",
        antes={k: antes.get(k) for k in cambios if k not in {"campos_estado", "detalle_avanzado"}},
        despues={k: despues.get(k) for k in cambios if k not in {"campos_estado", "detalle_avanzado"}},
    )
    return despues


async def _aplicar_detalle_avanzado(
    activo_id: ObjectId,
    antes: dict[str, Any],
    datos: dict[str, Any],
    cambios: dict[str, Any],
    usuario: dict[str, Any],
) -> None:
    """Sincroniza el interruptor, el detalle y los campos derivados."""
    if "opciones_avanzadas" in datos and datos["opciones_avanzadas"] is not None:
        activar = bool(datos["opciones_avanzadas"])
        cambios["opciones_avanzadas"] = activar
        if not activar and antes.get("detalle_avanzado"):
            # Desactivar oculta y avisa, pero NO borra el detalle.
            cambios["detalle_avanzado"] = antes.get("detalle_avanzado")
            cambios["aviso_detalle_oculto"] = True
        await registrar(
            "activo.opciones_avanzadas",
            usuario_id=usuario.get("_id"),
            usuario_nombre=usuario.get("nombre", ""),
            rol=usuario.get("rol", ""),
            entidad="activo",
            entidad_id=activo_id,
            resumen=f"Opciones avanzadas {'activadas' if activar else 'desactivadas'}",
            antes={"opciones_avanzadas": bool(antes.get("opciones_avanzadas"))},
            despues={"opciones_avanzadas": activar},
        )
    if "detalle_avanzado" in datos and datos["detalle_avanzado"] is not None:
        if not cambios.get("opciones_avanzadas", bool(antes.get("opciones_avanzadas"))):
            if datos.get("opciones_avanzadas") is False and datos.get("detalle_avanzado") is None:
                pass  # se conserva lo existente
            elif datos.get("opciones_avanzadas") is not True:
                raise Validacion("Activa las opciones avanzadas antes de registrar el detalle interno.")
        detalle_nuevo = datos["detalle_avanzado"]
        cambios["detalle_avanzado"] = (
            detalle_nuevo.model_dump(mode="json", exclude_none=True)
            if hasattr(detalle_nuevo, "model_dump")
            else dict(detalle_nuevo)
        )
        _sincronizar_derivados(cambios["detalle_avanzado"], cambios, marcar_derivados=True)
    await _registrar_cambios_componentes(activo_id, antes, cambios, usuario)


def _sincronizar_derivados(detalle: dict[str, Any], cambios: dict[str, Any], *, marcar_derivados: bool) -> None:
    """Memoria RAM y almacenamiento se muestran como valores derivados de los modulos."""
    if marcar_derivados:
        cambios["campos_derivados_calculados"] = True
    modulos = detalle.get("memoria_modulos") or []
    unidades = detalle.get("almacenamiento_unidades") or []
    if modulos:
        total = sum(float(m.get("capacidad_gb") or 0) for m in modulos)
        tipos = sorted({m.get("tipo") for m in modulos if m.get("tipo")})
        cambios["memoria_ram"] = " + ".join(
            parte for parte in [f"{total:g} GB", " / ".join(tipos)] if parte
        )
    if unidades:
        total_gb = sum(float(u.get("capacidad_gb") or 0) for u in unidades)
        tipos = sorted({u.get("tipo") for u in unidades if u.get("tipo")})
        cambios["almacenamiento"] = " + ".join(parte for parte in [f"{total_gb:g} GB", " / ".join(tipos)] if parte)


async def _registrar_cambios_componentes(
    activo_id: ObjectId, antes: dict[str, Any], cambios: dict[str, Any], usuario: dict[str, Any], ticket_id: ObjectId | None = None
) -> None:
    if "detalle_avanzado" not in cambios:
        return
    viejo = (antes.get("detalle_avanzado") or {})
    nuevo = cambios["detalle_avanzado"] or {}
    db = get_db()
    for seccion in ("memoria_modulos", "almacenamiento_unidades", "fuente_poder", "placa_madre", "sistema_operativo", "licencias"):
        anterior = json_seguro(viejo.get(seccion))
        posterior = json_seguro(nuevo.get(seccion))
        if anterior == posterior:
            continue
        await db["activos_cambios_componentes"].insert_one(
            {
                "activo_id": activo_id,
                "seccion": seccion,
                "antes": anterior,
                "despues": posterior,
                "resumen": _resumen_cambio(seccion, anterior, posterior),
                "fecha": utcnow(),
                "usuario_id": usuario.get("_id"),
                "usuario_nombre": usuario.get("nombre", ""),
                "ticket_id": ticket_id,
            }
        )


def json_seguro(valor: Any) -> Any:
    import json

    try:
        json.dumps(valor, default=str)
        return valor
    except Exception:  # pragma: no cover
        return str(valor)


def _resumen_cambio(seccion: str, antes: Any, despues: Any) -> str:
    def total(elementos: Any, campo: str) -> float:
        if not isinstance(elementos, list):
            return 0.0
        return sum(float(e.get(campo) or 0) for e in elementos if isinstance(e, dict))

    if seccion == "memoria_modulos":
        a, d = total(antes, "capacidad_gb"), total(despues, "capacidad_gb")
        modulos = len(despues) if isinstance(despues, list) else 0
        return f"Memoria RAM: {a:g} GB en {len(antes) if isinstance(antes, list) else 0} modulo(s) -> {d:g} GB en {modulos} modulo(s)"
    if seccion == "almacenamiento_unidades":
        a, d = total(antes, "capacidad_gb"), total(despues, "capacidad_gb")
        unidades = len(despues) if isinstance(despues, list) else 0
        return f"Almacenamiento: {a:g} GB -> {d:g} GB ({unidades} unidad(es))"
    return f"Seccion '{seccion}' modificada"


async def eliminar_activo(activo_id: ObjectId, *, usuario: dict[str, Any], motivo: str | None = None) -> None:
    db = get_db()
    activo = await db["activos"].find_one({"_id": activo_id})
    if activo is None:
        raise NoEncontrado("Equipo no encontrado.")
    if await db["tickets"].count_documents({"activo_id": activo_id, "estado": {"$nin": ["resuelto", "cerrado"]}}):
        raise Prohibido(
            "Este equipo tiene tickets abiertos. Resuelvelos antes de darlo de baja."
        )
    await db["activos"].update_one(
        {"_id": activo_id},
        {"$set": {"activo": False, "eliminado_en": utcnow(), "eliminado_por": usuario.get("nombre", "")}},
    )
    await registrar(
        "activo.eliminar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="activo",
        entidad_id=activo_id,
        resumen=f"Equipo dado de baja: {activo.get('nombre_equipo') or activo.get('tipo')}",
        antes={"tipo": activo.get("tipo"), "codigo": activo.get("codigo_patrimonial")},
        contexto={"motivo": motivo},
    )


async def obtener(activo_id: ObjectId) -> dict[str, Any]:
    activo = await get_db()["activos"].find_one({"_id": activo_id, "activo": {"$ne": False}})
    if activo is None:
        raise NoEncontrado("Equipo no encontrado.")
    return activo


async def exportar_excel(filtros: dict[str, Any] | None = None) -> tuple[bytes, int, str]:
    """
    El inventario registrado, en el Excel del municipio: **una hoja por zona**.

    Devuelve el archivo, cuántos equipos tiene y el nombre sugerido. Usa los mismos
    filtros que el listado —zona, oficina, tipo, estado, búsqueda— para que lo que se
    descarga sea exactamente lo que se está viendo en pantalla, no «todo» a propósito.

    El formato es el de ida y vuelta: las mismas columnas de la plantilla oficial, para
    que el archivo que sale se pueda volver a subir tal cual.
    """
    from app.services.excel_service import COLUMNAS_OFICIALES, exportar_inventario_por_zonas

    db = get_db()
    filtros = dict(filtros or {})
    consulta: dict[str, Any] = {"activo": {"$ne": False}}
    if filtros.get("zona_id"):
        consulta["zona_id"] = id_requerido(filtros["zona_id"], "zona")
    if filtros.get("oficina_id"):
        consulta["oficina_id"] = id_requerido(filtros["oficina_id"], "oficina")
    if filtros.get("tipo"):
        consulta["tipo_normalizado"] = clave(filtros["tipo"])
    if filtros.get("estado"):
        consulta["estado"] = filtros["estado"]
    if filtros.get("propiedad"):
        consulta["propiedad"] = filtros["propiedad"]
    if filtros.get("solo_faltantes"):
        consulta["faltantes_count"] = {"$gt": 0}
    if filtros.get("solo_uso_comun"):
        consulta["responsable_id"] = None
    if filtros.get("texto"):
        termino = re.escape(normalizar_texto(filtros["texto"]))
        consulta["$or"] = [
            {"codigo_patrimonial": {"$regex": termino, "$options": "i"}},
            {"nombre_equipo": {"$regex": termino, "$options": "i"}},
            {"marca": {"$regex": termino, "$options": "i"}},
            {"modelo": {"$regex": termino, "$options": "i"}},
            {"responsable_nombre": {"$regex": termino, "$options": "i"}},
            {"conjunto_nombre": {"$regex": termino, "$options": "i"}},
        ]

    documentos = await (
        db["activos"]
        .find(consulta)
        .sort([("zona_nombre", 1), ("oficina_nombre", 1), ("conjunto_nombre", 1), ("tipo", 1), ("_id", 1)])
        .to_list(None)
    )

    zonas: dict[str, list[dict[str, Any]]] = {}
    for activo in documentos:
        zona = normalizar_texto(activo.get("zona_nombre")) or "SIN ZONA"
        fila = {
            "AREA": activo.get("oficina_nombre"),
            "Tipo de equipo": activo.get("conjunto_nombre"),
            "Dispositivo": activo.get("nombre_equipo") or activo.get("modelo") or activo.get("tipo"),
            "Código patrimonial": activo.get("codigo_patrimonial"),
            "Marca": activo.get("marca"),
            "Modelo": activo.get("modelo"),
            "Tamaño Pantalla": activo.get("tamano_pantalla"),
            "Nombre Equipo": activo.get("nombre_equipo"),
            "Procesador": activo.get("procesador"),
            "Memoria RAM": activo.get("memoria_ram"),
            "Almacenamiento": activo.get("almacenamiento"),
            "Direccion IP": activo.get("direccion_ip"),
            "Direccion MAC": activo.get("direccion_mac"),
            "Propiedad": activo.get("propiedad"),
            "Estado": activo.get("estado"),
            "Responsable": activo.get("responsable_nombre"),
        }
        zonas.setdefault(zona, []).append({columna: fila.get(columna) or "" for columna in COLUMNAS_OFICIALES})

    contenido = exportar_inventario_por_zonas(zonas)
    partes = ["inventario"]
    if filtros.get("zona_id"):
        zona = await db["zonas"].find_one({"_id": id_requerido(filtros["zona_id"], "zona")})
        if zona:
            partes.append(normalizar_texto(zona["nombre"]).lower().replace(" ", "-"))
    elif filtros.get("oficina_id"):
        oficina = await db["oficinas"].find_one({"_id": id_requerido(filtros["oficina_id"], "oficina")})
        if oficina:
            partes.append(normalizar_texto(oficina["nombre"]).lower().replace(" ", "-"))
    return contenido, len(documentos), "-".join(partes)[:80]


async def listar(filtros: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    consulta: dict[str, Any] = {"activo": {"$ne": False}}
    if filtros.get("zona_id"):
        consulta["zona_id"] = filtros["zona_id"]
    if filtros.get("oficina_id"):
        consulta["oficina_id"] = filtros["oficina_id"]
    if filtros.get("tipo"):
        consulta["tipo_normalizado"] = clave(filtros["tipo"])
    if filtros.get("conjunto_id"):
        consulta["conjunto_id"] = filtros["conjunto_id"]
    if filtros.get("estado"):
        consulta["estado"] = filtros["estado"]
    if filtros.get("propiedad"):
        consulta["propiedad"] = filtros["propiedad"]
    if filtros.get("solo_uso_comun"):
        consulta["responsable_id"] = None
    if filtros.get('responsables_pendientes'):
        # «Pendiente» = el Excel nombra a alguien y ese nombre no esta enlazado a
        # una cuenta **activa**. Es la misma regla que usa la puesta en marcha
        # (`db/estado.py`): si la cuenta se dio de baja, el enlace ya no sirve y el
        # equipo vuelve a estar pendiente de vincular. Se resuelve con una lista
        # de ids en vez de un $lookup, que hacia el mismo trabajo mas caro.
        ids_activos = [u['_id'] async for u in db['usuarios'].find({'activo': True}, {'_id': 1})]
        consulta['responsable_nombre'] = {'$nin': [None, '']}
        consulta['responsable_id'] = {'$nin': ids_activos}
    if filtros.get('solo_faltantes'):
        consulta['faltantes_count'] = {'$gt': 0}
    if filtros.get("responsable_id"):
        consulta["responsable_id"] = filtros["responsable_id"]
    if filtros.get("solo_opciones_avanzadas"):
        consulta["opciones_avanzadas"] = True
    if filtros.get("texto"):
        termino = re.escape(normalizar_texto(filtros["texto"]))
        consulta["$or"] = [
            {"codigo_patrimonial": {"$regex": termino, "$options": "i"}},
            {"nombre_equipo": {"$regex": termino, "$options": "i"}},
            {"marca": {"$regex": termino, "$options": "i"}},
            {"modelo": {"$regex": termino, "$options": "i"}},
            {"direccion_ip": {"$regex": termino, "$options": "i"}},
            {"direccion_mac": {"$regex": termino.replace(":", ""), "$options": "i"}},
            {"responsable_nombre": {"$regex": termino, "$options": "i"}},
            {"conjunto_nombre": {"$regex": termino, "$options": "i"}},
        ]
    pagina = int(filtros.get('pagina', 1))
    por_pagina = int(filtros.get('por_pagina', 25))
    if pagina < 1 or not 1 <= por_pagina <= 100:
        raise Validacion('Página o tamaño de página no válido.')
    orden = filtros.get('orden') or 'creado_en'
    permitidos = {'ubicacion', 'nombre_equipo', 'tipo', 'marca', 'estado', 'actualizado_en', 'creado_en'}
    if orden not in permitidos:
        raise Validacion('Orden no válido.')
    campos_orden = ['zona_nombre', 'oficina_nombre', 'conjunto_nombre', 'tipo', '_id'] if orden == 'ubicacion' else [orden, '_id']
    pipeline = [{'$match': consulta}]
    pipeline += [{'$sort': {c: (-1 if orden == 'creado_en' else 1) for c in campos_orden}}, {'$facet': {
        'total': [{'$count': 'valor'}],
        'items': [{'$skip': (pagina - 1) * por_pagina}, {'$limit': por_pagina}, {'$project': {'clave_natural': 0}}],
    }}]
    resultado = (await (await db['activos'].aggregate(pipeline, collation=Collation(locale='es', numericOrdering=True))).to_list(None))[0]
    total = resultado['total'][0]['valor'] if resultado['total'] else 0
    documentos = resultado['items']
    import math

    items: list[dict[str, Any]] = []
    pendientes: list[dict[str, Any]] = []
    for activo in documentos:
        completeness = await calcular_completitud(activo)
        fila = _resumen_activo(activo, completeness)
        items.append(fila)
        if completeness["faltantes"]:
            pendientes.append(
                {
                    "id": fila["id"],
                    "nombre": fila["nombre_equipo"] or fila["tipo"],
                    "faltantes": completeness["faltantes"],
                }
            )
    return {
        "items": items,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": math.ceil(total / por_pagina) if por_pagina else 0,
        "pendientes": pendientes,
    }


def _resumen_activo(activo: dict[str, Any], completeness: dict[str, Any]) -> dict[str, Any]:
    return {
        **{campo: activo.get(campo) for campo in ("tamano_pantalla", "procesador", "memoria_ram", "almacenamiento", "direccion_ip", "direccion_mac", "observaciones")},
        "id": activo["_id"],
        "tipo": activo.get("tipo"),
        "nombre_equipo": activo.get("nombre_equipo"),
        "codigo_patrimonial": activo.get("codigo_patrimonial"),
        "marca": activo.get("marca"),
        "modelo": activo.get("modelo"),
        "estado": activo.get("estado"),
        "propiedad": activo.get("propiedad"),
        "oficina_id": activo.get("oficina_id"),
        "oficina_nombre": activo.get("oficina_nombre"),
        "zona_id": activo.get("zona_id"),
        "zona_nombre": activo.get("zona_nombre"),
        "conjunto_id": activo.get("conjunto_id"),
        "conjunto_nombre": activo.get("conjunto_nombre"),
        "numero_equipo": activo.get('numero_equipo'),
        "responsable_id": activo.get("responsable_id"),
        "responsable_nombre": activo.get("responsable_nombre"),
        "uso_comun": bool(activo.get("uso_comun")) or not activo.get("responsable_id"),
        "completitud": completeness["porcentaje"],
        "faltantes": completeness["faltantes"],
        "campos_faltantes": completeness["campos_faltantes"],
        "opciones_avanzadas": bool(activo.get("opciones_avanzadas")),
        "creado_en": activo.get("creado_en"),
    }


async def detalle(activo_id: ObjectId, *, usuario: dict[str, Any] | None = None) -> dict[str, Any]:
    db = get_db()
    activo = await db["activos"].find_one({"_id": activo_id, "activo": {"$ne": False}})
    if activo is None:
        raise NoEncontrado("Equipo no encontrado.")
    completeness = await calcular_completitud(activo)
    salida = _resumen_activo(activo, completeness)
    salida.update(
        {
            "tamano_pantalla": activo.get("tamano_pantalla"),
            "procesador": activo.get("procesador"),
            "memoria_ram": activo.get("memoria_ram"),
            "almacenamiento": activo.get("almacenamiento"),
            "direccion_ip": activo.get("direccion_ip"),
            "direccion_mac": activo.get("direccion_mac"),
            "propiedad": activo.get("propiedad"),
            "observaciones": activo.get("observaciones"),
            "campos": completeness["campos"],
            "campos_derivados": completeness["derivados"],
            "completitud_detalle": {
                "porcentaje": completeness["porcentaje"],
                "completos": completeness["completos"],
                "esperados": completeness["esperados"],
                "faltantes": completeness["faltantes"],
            },
            "historial_responsables": await db["historial_responsables"].find(
                {"activo_id": activo_id}, {"_id": 0}
            ).sort("fecha", -1).to_list(None),
            "historial_componentes": await _componentes_con_ticket(db, activo_id),
            "tickets": await db["tickets"]
            .find({"activo_id": activo_id}, {"codigo": 1, "asunto": 1, "estado": 1, "prioridad": 1, "creado_en": 1, "cerrado_en": 1, "tecnico_nombre": 1})
            .sort("creado_en", -1)
            .limit(25)
            .to_list(None),
            "creado_por": activo.get("creado_por"),
            "actualizado_en": activo.get("actualizado_en"),
            "version": activo.get("version", 1),
        }
    )
    if activo.get("opciones_avanzadas"):
        salida["detalle_avanzado"] = activo.get("detalle_avanzado") or {}
        salida["secciones_avanzadas"] = sorted(
            [k for k, v in (activo.get("detalle_avanzado") or {}).items() if v]
        )
        salida["calculos_avanzados"] = _calculos(activo.get("detalle_avanzado") or {})
    else:
        aviso = []
        if activo.get("detalle_avanzado"):
            aviso.append(
                {
                    "tipo": "avanzado_oculto",
                    "nivel": "info",
                    "mensaje": "Este equipo tiene detalle tecnico registrado que esta oculto por el interruptor.",
                }
            )
        if activo.get("aviso_detalle_oculto"):
            salida["aviso_detalle_oculto"] = True
            aviso.append(
                {
                    "tipo": "avanzado_oculto",
                    "nivel": "atencion",
                    "mensaje": "Las opciones avanzadas se desactivaron. El detalle guardado se conserva.",
                }
            )
        salida["alertas"] = aviso
    salida["alertas"] = salida.get("alertas", []) + await alertas(activo)
    from app.services.ml_service import predecir_falla

    salida["prediccion"] = await predecir_falla(activo)
    salida["campana_estado"] = await _estado_campana(activo_id)
    return salida


async def _estado_campana(activo_id: ObjectId) -> str | None:
    item = await get_db()["campana_items"].find_one(
        {"activo_id": activo_id}, {"estado_item": 1}, sort=[("verificado_en", -1)]
    )
    return item.get("estado_item") if item else None


async def _componentes_con_ticket(db, activo_id: ObjectId) -> list[dict[str, Any]]:
    documentos = await (
        db["activos_cambios_componentes"]
        .find({"activo_id": activo_id}, {"_id": 0})
        .sort("fecha", -1)
        .to_list(None)
    )
    ids = [d["ticket_id"] for d in documentos if d.get("ticket_id")]
    codigos: dict[str, str] = {}
    if ids:
        tickets = await (db["tickets"].find({"_id": {"$in": ids}}, {"codigo": 1}).to_list(None))
        codigos = {str(t["_id"]): t["codigo"] for t in tickets}
    for documento in documentos:
        if documento.get("ticket_id"):
            documento["ticket_codigo"] = codigos.get(str(documento["ticket_id"]))
    return documentos


def _calculos(detalle: dict[str, Any]) -> dict[str, Any]:
    modulos = detalle.get("memoria_modulos") or []
    unidades = detalle.get("almacenamiento_unidades") or []
    madre = detalle.get("placa_madre") or {}
    total_ranuras = madre.get("ranuras_ram_totales")
    ocupada = madre.get("ranuras_ram_ocupadas") or len(modulos)
    calculo: dict[str, Any] = {
        "modulos_memoria": len(modulos),
        "unidades_disco": len(unidades),
        "ram_instalada_gb": round(sum(float(m.get("capacidad_gb") or 0) for m in modulos), 2),
        "almacenamiento_total_gb": round(sum(float(u.get("capacidad_gb") or 0) for u in unidades), 2),
        "avisos": [],
    }
    if isinstance(total_ranuras, int) and isinstance(ocupada, int):
        calculo["ranuras_totales"] = total_ranuras
        calculo["ranuras_ocupadas"] = ocupada
        calculo["ranuras_libres"] = max(total_ranuras - ocupada, 0)
        if ocupada > total_ranuras:
            calculo["avisos"].append("Las ranuras de RAM ocupadas son mas que las totales.")
    maxima = madre.get("ram_maxima_soportada")
    if isinstance(maxima, (int, float)) and calculo["ram_instalada_gb"] > float(maxima):
        calculo["avisos"].append("La RAM instalada supera la capacidad maxima soportada por la placa.")
    return calculo


async def alertas(activo: dict[str, Any]) -> list[dict[str, Any]]:
    """Avisos tecnicos no bloqueantes."""
    alertas: list[dict[str, Any]] = []
    estado = (activo.get("estado") or "").lower()
    if estado in ("en reparación", "reparacion", "en reparacion"):
        alertas.append({"tipo": "estado", "nivel": "atencion", "mensaje": f"El equipo esta en estado '{activo.get('estado')}'."})
    if estado == "dado de baja":
        alertas.append({"tipo": "estado", "nivel": "critico", "mensaje": "El equipo esta dado de baja."})
    ip = activo.get("direccion_ip")
    mac = activo.get("direccion_mac")
    if ip:
        otros = await get_db()["activos"].find(
            {"direccion_ip": ip, "_id": {"$ne": activo["_id"]}, "activo": {"$ne": False}},
            {"nombre_equipo": 1, "tipo": 1},
        ).to_list(None)
        if otros:
            alertas.append(
                {
                    "tipo": "duplicado",
                    "nivel": "atencion",
                    "mensaje": f"La IP {ip} esta repetida en {len(otros) + 1} equipo(s).",
                }
            )
    if mac:
        otros = await get_db()["activos"].find(
            {"direccion_mac": mac, "_id": {"$ne": activo["_id"]}, "activo": {"$ne": False}},
            {"nombre_equipo": 1},
        ).to_list(None)
        if otros:
            alertas.append({"tipo": "duplicado", "nivel": "atencion", "mensaje": f"La MAC {mac} esta repetida."})
    codigo = activo.get("codigo_patrimonial")
    if codigo:
        otros = await get_db()["activos"].find(
            {"_id": {"$ne": activo["_id"]}, "activo": {"$ne": False}}, {"codigo_patrimonial": 1}
        ).to_list(None)
        for otro in otros:
            campos = (activo.get("marca"), activo.get("modelo"))
            if otro.get("codigo_patrimonial") == codigo and otro.get("marca") == campos[0]:
                alertas.append(
                    {
                        "tipo": "duplicado",
                        "nivel": "atencion",
                        "mensaje": "Existe otro equipo con el mismo codigo y marca. Revisa el codigo patrimonial.",
                    }
                )
                break
    garantia = ((activo.get("detalle_avanzado") or {}).get("compra_garantia") or {}) if activo.get("opciones_avanzadas") else {}
    vencimiento = garantia.get("vencimiento_garantia")
    if vencimiento and str(vencimiento) < utcnow().date().isoformat():
        alertas.append({"tipo": "garantia", "nivel": "info", "mensaje": "La garantia de este equipo ya vencio."})
    return alertas


# ── Estado de campo (masivo) ─────────────────────────────────
async def marcar_campos(
    activo_ids: list[ObjectId], campos: list[str], estado: str, *, usuario: dict[str, Any], motivo: str | None = None, nota: str | None = None
) -> dict[str, Any]:
    db = get_db()
    validos = [c for c in campos if c in CAMPOS_CON_ESTADO]
    if not validos:
        raise Validacion("Selecciona al menos un campo valido.")
    if estado not in (CAMPO_PENDIENTE, CAMPO_NO_APLICA, CAMPO_NO_DISPONIBLE):
        raise Validacion("Estado de campo no valido.")
    actualizados: list[str] = []
    for activo_id in activo_ids:
        activo = await db["activos"].find_one({"_id": activo_id})
        if activo is None:
            continue
        campos_estado = dict(activo.get("campos_estado") or {})
        for campo in validos:
            campos_estado[campo] = {
                "estado": estado,
                "motivo": normalizar_texto(motivo) or None,
                "nota": normalizar_texto(nota) or None,
                "usuario_id": usuario.get("_id"),
                "usuario_nombre": usuario.get("nombre", ""),
                "fecha": utcnow(),
            }
        await db["activos"].update_one(
            {"_id": activo_id},
            {"$set": {"campos_estado": campos_estado, 'faltantes_count': (await calcular_completitud({**activo, 'campos_estado': campos_estado}))['faltantes'], "actualizado_en": utcnow(), "actualizado_por": usuario.get("nombre", "")}},
        )
        actualizados.append(str(activo_id))
    await registrar(
        "activo.campo_estado",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="activo",
        resumen=f"Campos marcados como '{estado}' en {len(actualizados)} equipo(s)",
        despues={"campos": validos, "estado": estado, "motivo": motivo, "nota": nota, "activos": len(actualizados)},
    )
    return {"actualizados": len(actualizados), "campos": validos, "estado": estado}


async def activar_opciones_avanzadas(
    activo_ids: list[ObjectId], activar: bool, *, usuario: dict[str, Any]
) -> dict[str, Any]:
    db = get_db()
    resultado = await db["activos"].update_many(
        {"_id": {"$in": activo_ids}},
        {
            "$set": {
                "opciones_avanzadas": activar,
                "actualizado_en": utcnow(),
                "actualizado_por": usuario.get("nombre", ""),
            }
        },
    )
    await registrar(
        "activo.opciones_avanzadas",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="activo",
        resumen=f"Opciones avanzadas {'activadas' if activar else 'desactivadas'} en {resultado.modified_count} equipo(s)",
        despues={"activar": activar, "equipos": resultado.modified_count},
    )
    return {"actualizados": resultado.modified_count}


async def borrar_detalle_avanzado(activo_id: ObjectId, *, usuario: dict[str, Any]) -> None:
    db = get_db()
    activo = await db["activos"].find_one({"_id": activo_id})
    if activo is None:
        raise NoEncontrado("Equipo no encontrado.")
    if not activo.get("detalle_avanzado"):
        raise Validacion("Este equipo no tiene detalle avanzado registrado.")
    await db["activos"].update_one(
        {"_id": activo_id},
        {
            "$set": {
                "detalle_avanzado": None,
                "aviso_detalle_oculto": False,
                "campos_derivados_calculados": False,
                "actualizado_en": utcnow(),
            }
        },
    )
    await db["activos_cambios_componentes"].insert_one(
        {
            "activo_id": activo_id,
            "seccion": "__detalle__",
            "antes": {"secciones": sorted(k for k, v in (activo.get("detalle_avanzado") or {}).items() if v)},
            "despues": None,
            "resumen": "Detalle avanzado eliminado",
            "fecha": utcnow(),
            "usuario_id": usuario.get("_id"),
            "usuario_nombre": usuario.get("nombre", ""),
        }
    )
    await registrar(
        "activo.editar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="activo",
        entidad_id=activo_id,
        resumen="Detalle avanzado eliminado",
    )


async def registrar_componente(
    activo_id: ObjectId, seccion: str, despues: Any, *, usuario: dict[str, Any], resumen: str, ticket_id: ObjectId | None = None
) -> None:
    """Registro puntual desde la resolucion de un ticket (ofrecido, nunca imposed)."""
    db = get_db()
    activo = await db["activos"].find_one({"_id": activo_id})
    if activo is None:
        raise NoEncontrado("Equipo no encontrado.")
    detalle = dict(activo.get("detalle_avanzado") or {})
    anterior = detalle.get(seccion)
    detalle[seccion] = despues
    cambios = {"detalle_avanzado": detalle, "opciones_avanzadas": True}
    _sincronizar_derivados(detalle, cambios, marcar_derivados=True)
    cambios['faltantes_count'] = (await calcular_completitud({**activo, **cambios}))['faltantes']
    await db["activos"].update_one(
        {"_id": activo_id},
        {
            "$set": {
                **cambios,
                "actualizado_en": utcnow(),
                "actualizado_por": usuario.get("nombre", ""),
            }
        },
    )
    await db["activos_cambios_componentes"].insert_one(
        {
            "activo_id": activo_id,
            "seccion": seccion,
            "antes": anterior,
            "despues": despues,
            "resumen": resumen,
            "fecha": utcnow(),
            "usuario_id": usuario.get("_id"),
            "usuario_nombre": usuario.get("nombre", ""),
            "ticket_id": ticket_id,
        }
    )


# ── Responsables ─────────────────────────────────────────────
async def _registrar_historial_responsable(
    tipo: str,
    entidad_id: ObjectId,
    responsable_id: ObjectId | None,
    responsable_nombre: str | None,
    fin_anterior: datetime | None,
    motivo: str | None,
    usuario: dict[str, Any],
) -> None:
    db = get_db()
    filtro = {"activo_id": entidad_id} if tipo == "activo" else {"conjunto_id": entidad_id}
    if responsable_id:
        abierto = await db["historial_responsables"].find_one(filtro, sort=[("fecha", -1)])
        if abierto and abierto.get("responsable_id") == responsable_id and not abierto.get("fin"):
            return
        if abierto:
            await db["historial_responsables"].update_one({"_id": abierto["_id"]}, {"$set": {"fin": utcnow()}})
    documento = {
        **filtro,
        "responsable_id": responsable_id,
        "responsable_nombre": responsable_nombre,
        "inicio": utcnow(),
        "fin": None,
        "motivo": normalizar_texto(motivo) or None,
        "usuario_id": usuario.get("_id"),
        "usuario_nombre": usuario.get("nombre", ""),
        "fecha": utcnow(),
    }
    await db["historial_responsables"].insert_one(documento)


async def cambiar_responsable(
    tipo: str,
    entidad_id: ObjectId,
    responsable_id: ObjectId | None,
    *,
    usuario: dict[str, Any],
    motivo: str | None = None,
    confirmar_transferencia: bool = False,
) -> dict[str, Any]:
    db = get_db()
    coleccion = "activos" if tipo == "activo" else "conjuntos"
    entidad = await db[coleccion].find_one({"_id": entidad_id})
    if entidad is None:
        raise NoEncontrado("Equipo no encontrado." if tipo == "activo" else "Conjunto no encontrado.")
    nombre = None
    if responsable_id:
        from app.services import usuario_service

        persona = await usuario_service.obtener(responsable_id)
        if persona.get("oficina_id") and entidad.get("oficina_id") and persona["oficina_id"] != entidad["oficina_id"]:
            if not confirmar_transferencia:
                raise Validacion(
                    "El responsable pertenece a otra oficina. Confirma la transferencia o el prestamo.",
                    detalles={
                        "oficina_equipo": entidad.get("oficina_nombre"),
                        "oficina_usuario": persona.get("oficina_nombre"),
                        "requiere_confirmacion": True,
                    },
                )
            await registrar(
                "activo.responsable",
                usuario_id=usuario.get("_id"),
                usuario_nombre=usuario.get("nombre", ""),
                rol=usuario.get("rol", ""),
                entidad=coleccion,
                entidad_id=entidad_id,
                resumen="Transferencia o prestamo entre oficinas confirmado",
                contexto={
                    "de_oficina": entidad.get("oficina_nombre"),
                    "a_oficina": persona.get("oficina_nombre"),
                },
            )
        nombre = persona.get("nombre")
    await db[coleccion].update_one(
        {"_id": entidad_id},
        {
            "$set": {
                "responsable_id": responsable_id,
                "responsable_nombre": nombre,
                "uso_comun": bool(entidad_id and not responsable_id and tipo == "conjunto"),
                "actualizado_en": utcnow(),
                "actualizado_por": usuario.get("nombre", ""),
            }
        },
    )
    if tipo == "conjunto" and responsable_id:
        # Los activos sin responsable propio siguen al conjunto
        await db["activos"].update_many(
            {"conjunto_id": entidad_id, "responsable_id": None},
            {"$set": {"responsable_id": responsable_id, "responsable_nombre": nombre}},
        )
    await _registrar_historial_responsable(tipo, entidad_id, responsable_id, nombre, None, motivo, usuario)
    await registrar(
        "activo.responsable",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad=coleccion,
        entidad_id=entidad_id,
        resumen=(
            f"Responsable de '{entidad.get('nombre_equipo') or entidad.get('nombre')}' -> "
            f"{nombre or 'uso comun de la oficina'}"
        ),
        antes={"responsable": entidad.get("responsable_nombre")},
        despues={"responsable": nombre, "motivo": motivo},
    )
    return await db[coleccion].find_one({"_id": entidad_id})


# ── Consultas de apoyo ───────────────────────────────────────
async def equipos_de_usuario(usuario_id: ObjectId) -> dict[str, Any]:
    db = get_db()
    usuario = await db["usuarios"].find_one({"_id": usuario_id}) or {}
    activos = await (db["activos"].find({"responsable_id": usuario_id, "activo": {"$ne": False}}).to_list(None))
    grupos: dict[str, list[dict[str, Any]]] = {}
    for activo in activos:
        completeness = await calcular_completitud(activo)
        fila = _resumen_activo(activo, completeness)
        clave_grupo = (activo.get("conjunto_nombre") if componente_escritorio(activo.get("tipo")) else None) or "Equipos individuales"
        grupos.setdefault(clave_grupo, []).append(fila)
    uso_comun = (
        await db["activos"].find(
            {"oficina_id": usuario["oficina_id"], "responsable_id": None, "activo": {"$ne": False}}
        ).to_list(None)
        if usuario.get("oficina_id")
        # Sin oficina no se busca nada. La consulta se quedaba literal en
        # `{"oficina_id": null, "responsable_id": null}` —sin filtro de oficina—
        # así que en cuanto un equipo llegara al inventario sin oficina, todos los
        # equipos sin responsable pasarían a ser «de uso común» de cualquier
        # persona sin oficina. Son 875 de 876 los que no tienen responsable, así
        # que habría salido casi todo el inventario en la lista de quien reporta.
        else []
    )
    comunes: list[dict[str, Any]] = []
    for activo in uso_comun:
        completeness = await calcular_completitud(activo)
        comunes.append(_resumen_activo(activo, completeness))
    conjuntos = await db["conjuntos"].find(
        {"responsable_id": usuario_id, "activo": True}
    ).to_list(None)
    return {
        "por_conjunto": [{"conjunto": nombre, "equipos": filas} for nombre, filas in sorted(grupos.items())],
        "uso_comun_oficina": comunes,
        "conjuntos": [
            {"id": c["_id"], "nombre": c["nombre"], "oficina_nombre": c.get("oficina_nombre"), "numero": c.get("numero")}
            for c in conjuntos
        ],
    }


async def equipos_por_codigo(texto: str, *, limite: int = 20) -> list[dict[str, Any]]:
    termino = re.escape(normalizar_texto(texto))
    documentos = await (
        get_db()["activos"]
        .find(
            {"activo": {"$ne": False}, "$or": [{"codigo_patrimonial": {"$regex": termino, "$options": "i"}}, {"nombre_equipo": {"$regex": termino, "$options": "i"}}]},
            {"tipo": 1, "nombre_equipo": 1, "codigo_patrimonial": 1, "marca": 1, "modelo": 1, "oficina_nombre": 1, "conjunto_nombre": 1, "responsable_id": 1, "responsable_nombre": 1},
        )
        .limit(limite)
        .to_list(None)
    )
    return [
        {
            "id": d["_id"],
            "tipo": d.get("tipo"),
            "nombre": d.get("nombre_equipo") or d.get("modelo") or d.get("marca"),
            "codigo_patrimonial": d.get("codigo_patrimonial"),
            "marca": d.get("marca"),
            "modelo": d.get("modelo"),
            "oficina_nombre": d.get("oficina_nombre"),
            "conjunto_nombre": d.get("conjunto_nombre"),
            "responsable_id": d.get("responsable_id"),
            "responsable_nombre": d.get("responsable_nombre"),
        }
        for d in documentos
    ]


async def buscar(texto: str, *, limite: int = 25, zona_id: ObjectId | None = None) -> list[dict[str, Any]]:
    termino = re.escape(normalizar_texto(texto))
    if not termino:
        return []
    consulta: dict[str, Any] = {
        "activo": {"$ne": False},
        "$or": [
            {"codigo_patrimonial": {"$regex": termino, "$options": "i"}},
            {"nombre_equipo": {"$regex": termino, "$options": "i"}},
            {"marca": {"$regex": termino, "$options": "i"}},
            {"modelo": {"$regex": termino, "$options": "i"}},
            {"direccion_ip": {"$regex": termino, "$options": "i"}},
            {"direccion_mac": {"$regex": termino, "$options": "i"}},
            {"conjunto_nombre": {"$regex": termino, "$options": "i"}},
            {"responsable_nombre": {"$regex": termino, "$options": "i"}},
        ],
    }
    if zona_id:
        consulta["zona_id"] = zona_id
    documentos = await (get_db()["activos"].find(consulta).limit(limite).to_list(None))
    return [
        {
            "id": d["_id"],
            "tipo": d.get("tipo"),
            "nombre": d.get("nombre_equipo") or d.get("modelo") or d.get("marca"),
            "codigo_patrimonial": d.get("codigo_patrimonial"),
            "oficina_nombre": d.get("oficina_nombre"),
            "responsable_nombre": d.get("responsable_nombre"),
            "estado": d.get("estado"),
        }
        for d in documentos
    ]


async def buscar_duplicados(
    *,
    codigo_patrimonial: str | None = None,
    direccion_ip: str | None = None,
    direccion_mac: str | None = None,
    excluir_id: ObjectId | None = None,
) -> list[dict[str, Any]]:
    valores = {
        "codigo_patrimonial": (codigo_patrimonial or "").strip(),
        "direccion_ip": (direccion_ip or "").strip(),
        "direccion_mac": (direccion_mac or "").strip(),
    }
    condiciones: list[dict[str, Any]] = []
    for campo, valor in valores.items():
        if not valor:
            continue
        condiciones.append({campo: {"$regex": f"^{re.escape(valor)}$", "$options": "i"}})
    if not condiciones:
        return []
    consulta: dict[str, Any] = {
        "activo": {"$ne": False},
        "$or": condiciones,
    }
    if excluir_id:
        consulta["_id"] = {"$ne": excluir_id}
    documentos = await (
        get_db()["activos"]
        .find(
            consulta,
            {
                "tipo": 1,
                "nombre_equipo": 1,
                "codigo_patrimonial": 1,
                "direccion_ip": 1,
                "direccion_mac": 1,
                "oficina_nombre": 1,
                "zona_nombre": 1,
            },
        )
        .sort([("zona_nombre", 1), ("oficina_nombre", 1), ("_id", 1)])
        .limit(25)
        .to_list(None)
    )
    coincidencias = []
    for documento in documentos:
        coincidencias.append(
            {
                "id": documento["_id"],
                "nombre": documento.get("nombre_equipo") or documento.get("tipo") or "Equipo sin nombre",
                "tipo": documento.get("tipo"),
                "oficina_nombre": documento.get("oficina_nombre"),
                "zona_nombre": documento.get("zona_nombre"),
                "coincide_en": [
                    campo
                    for campo, valor in valores.items()
                    if valor
                    and (
                        str(documento.get(campo) or "").casefold() == valor.casefold()
                    )
                ],
            }
        )
    return coincidencias


async def cambio_masivo(datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    ids = datos.get("activo_ids") or []
    cambios: dict[str, Any] = {}
    if datos.get("estado"):
        cambios["estado"] = normalizar_texto(datos["estado"])
    if datos.get("propiedad"):
        cambios["propiedad"] = normalizar_texto(datos["propiedad"])
    if "observaciones" in datos and datos.get("observaciones"):
        cambios["observaciones"] = normalizar_texto(datos["observaciones"])
    nuevo_oficina = datos.get("oficina_id")
    nuevo_responsable = datos.get("responsable_id")
    actualizados = 0
    if cambios:
        cambios["actualizado_en"] = utcnow()
        cambios["actualizado_por"] = usuario.get("nombre", "")
        resultado = await db["activos"].update_many({"_id": {"$in": ids}}, {"$set": cambios})
        actualizados += resultado.modified_count
    if nuevo_oficina:
        oficina = await db["oficinas"].find_one({"_id": nuevo_oficina})
        if oficina is None:
            raise NoEncontrado("La oficina indicada no existe.")
        await db["activos"].update_many(
            {"_id": {"$in": ids}},
            {
                "$set": {
                    "oficina_id": oficina["_id"],
                    "oficina_nombre": oficina.get("nombre"),
                    "zona_id": oficina.get("zona_id"),
                    "zona_nombre": oficina.get("zona_nombre"),
                    "actualizado_en": utcnow(),
                }
            },
        )
        actualizados += len(ids)
    if "responsable_id" in datos:
        from app.services import usuario_service

        nombre = None
        if nuevo_responsable:
            persona = await usuario_service.obtener(nuevo_responsable)
            nombre = persona.get("nombre")
        await db["activos"].update_many(
            {"_id": {"$in": ids}},
            {"$set": {"responsable_id": nuevo_responsable, "responsable_nombre": nombre, "uso_comun": not nuevo_responsable}},
        )
        for activo_id in ids:
            await _registrar_historial_responsable(
                "activo", activo_id, nuevo_responsable, nombre, None, datos.get("motivo"), usuario
            )
        actualizados += len(ids)
    await recalcular_faltantes({'_id': {'$in': ids}})
    await registrar(
        "activo.masivo",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="activo",
        resumen=f"Cambio masivo en {len(ids)} equipo(s)",
        despues={"cambios": cambios, "oficina": str(nuevo_oficina or ""), "responsable": str(nuevo_responsable or ""), "motivo": datos.get("motivo")},
    )
    return {"actualizados": actualizados, "solicitados": len(ids)}
