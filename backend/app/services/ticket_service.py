"""Tickets: creacion, bandeja, detalle, transiciones, chat condicionado, notas y SLA.

Regla central (validada en el backend): el chat entre usuario y TI solo existe si el
ticket fue reportado por un usuario. Si lo registro un tecnico o un administrador,
el ticket tiene linea de tiempo y notas internas, sin caja de respuesta para el usuario.
"""

from __future__ import annotations

import math
from copy import deepcopy
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.audit import registrar
from app.services.presentacion_ticket import titulo_reporte
from app.services.categorias_ticket_service import categoria_reporte, categorias_activas
from app.core.db import get_db
from app.core.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from app.core.ids import a_id, codigo_ticket, id_requerido, normalizar_texto, nuevo_id
from app.core.time import business_tz, local_date, utcnow
from app.domain.constants import (
    ESTADO_ASIGNADO_LEGADO,
    ESTADO_CERRADO,
    ESTADO_EN_ESPERA,
    ESTADO_EN_PROGRESO,
    ESTADO_NUEVO,
    ESTADO_RESUELTO_LEGADO,
    ESTADOS_ABIERTOS,
    ESTADOS_CERRADOS,
    ORIGEN_ADMIN,
    ORIGEN_AUTOMATICO,
    ORIGENES_CON_CHAT,
    ORIGEN_TECNICO,
    ORIGEN_USUARIO,
    ORIGEN_USUARIO_TERCERO,
    TRANSICIONES,
    URGENCIA_A_PRIORIDAD,
)
from app.domain.permissions import tiene_permiso
from app.domain.schemas_db import CONTADOR_TICKETS
from app.services import config_service, inventario_service, notificaciones_service, sla_service

CAMPOS_VISIBLES_USUARIO = {
    "codigo", "asunto", "descripcion", "estado", "prioridad", "categoria", "origen",
    "zona_nombre", "oficina_nombre", "activo_nombre", "activo_tipo", "conjunto_nombre", "creado_en",
    "actualizado_en", "resuelto_en", "cerrado_en", "nota_resolucion", "veces_reabierto",
    "confianza_ia", "afectado_nombre", "sla", "tiempo_resolucion_min",
}

DIAS_PERIODO = {"7d": 6, "30d": 29, "90d": 89, "mes": None, "anio": None}

# Intentos al asignar un codigo libre si el contador choca con el indice unico
MAX_REINTENTOS_CODIGO = 5


def _identidad_solicitud(datos, usuario, tipo):
    clave = datos.get('_solicitud_id')
    if not clave:
        return None
    identidad = hashlib.sha256(f"{usuario['_id']}:{tipo}:{clave}".encode()).hexdigest()
    contenido = {k: v for k, v in datos.items() if k != '_solicitud_id'}
    huella = hashlib.sha256(json.dumps(contenido, sort_keys=True, default=str).encode()).hexdigest()
    return ObjectId(identidad[:24]), huella


async def _repetido(datos, usuario, tipo):
    identidad = _identidad_solicitud(datos, usuario, tipo)
    if identidad is None:
        return None
    existente = await get_db().tickets.find_one({'_id': identidad[0]})
    if existente and existente.get('solicitud_huella') != identidad[1]:
        raise Conflicto('Este envío ya fue utilizado para otros datos. Inicia un reporte nuevo.')
    return existente


async def _insertar_solicitud(documento, datos, usuario, tipo):
    identidad = _identidad_solicitud(datos, usuario, tipo)
    if identidad:
        documento['_id'], documento['solicitud_huella'] = identidad
    try:
        resultado = await get_db().tickets.insert_one(documento)
        documento['_id'] = resultado.inserted_id
        return documento, True
    except DuplicateKeyError:
        repetido = await _repetido(datos, usuario, tipo)
        if repetido is None:
            raise
        return repetido, False


def rango_30d() -> tuple[Any, Any]:
    """Ultimos 30 dias en UTC, listo para comparar con ``creado_en``."""
    from app.services.horario_service import fin_utc, inicio_utc

    hoy = local_date()
    return inicio_utc(hoy - timedelta(days=29)), fin_utc(hoy)


def rango(periodo: str | None) -> tuple[Any, Any]:
    from app.core.ids import rango_fechas
    from app.services.horario_service import fin_utc, inicio_utc

    inicio, fin = rango_fechas(periodo, local_date())
    return inicio_utc(inicio), fin_utc(fin)


async def _siguiente_codigo() -> str:
    """Numero consecutivo atomico.

    El incremento se hace con ``find_one_and_update``, que es atomico en
    MongoDB, y si el indice unico detecta una colision (por ejemplo, porque se
    importo un historico con numeros ya usados) se reintenta con el siguiente.
    """
    db = get_db()
    anio = local_date().year
    for _ in range(MAX_REINTENTOS_CODIGO):
        resultado = await db["contadores"].find_one_and_update(
            {"clave": f"{CONTADOR_TICKETS}:{anio}"},
            {"$inc": {"valor": 1}, "$setOnInsert": {"creado": utcnow()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        codigo = codigo_ticket(anio, int(resultado["valor"]))
        if await db["tickets"].find_one({"codigo": codigo}, {"_id": 1}) is None:
            return codigo
    raise Conflicto(
        "No se pudo asignar un numero de ticket libre. Revisa el contador de la institucion.",
        codigo="codigo_ticket_agotado",
    )


def tiene_chat(ticket: dict[str, Any]) -> bool:
    """Unico lugar donde se decide si el chat existe.

    Existe si lo reporto un usuario (para si o para un companero) o si un usuario
    con cuenta lo confirmo despues, momento en el que queda habilitado.
    """
    if not ticket.get("conversacion_id"):
        return False
    if ticket.get("origen") in ORIGENES_CON_CHAT:
        return True
    return bool(ticket.get("origen_adopcion"))


async def _registrar_evento(
    ticket: dict[str, Any],
    tipo: str,
    resumen: str,
    *,
    actor: dict[str, Any] | None = None,
    detalle: dict[str, Any] | None = None,
    visible_usuario: bool = False,
    origen_ia: bool = False,
) -> None:
    await get_db()["ticket_eventos"].insert_one(
        {
            "ticket_id": ticket["_id"],
            "tipo": tipo,
            "fecha": utcnow(),
            "actor": {
                "id": (actor or {}).get("_id"),
                "nombre": (actor or {}).get("nombre", "Sistema"),
                "rol": (actor or {}).get("rol", "sistema"),
            },
            "resumen": resumen,
            "detalle": detalle or {},
            "visible_usuario": visible_usuario,
            "origen_ia": origen_ia,
        }
    )


# Cómo se escribe cada estado cuando se enseña en el historial.
#
# La base guarda valores con guion bajo —«en_progreso»— porque así se filtran, pero
# eso no es lo que se escribe para que lo lea alguien: se escribe «en progreso».
#
# Solo al mostrar. El registro guardado sigue diciendo exactamente lo que pasó.
TITULOS_ESTADO: dict[str, str] = {
    ESTADO_NUEVO: "nuevo",
    ESTADO_EN_PROGRESO: "en progreso",
    ESTADO_EN_ESPERA: "en espera",
    ESTADO_CERRADO: "cerrado",
}

# Los estados que se retiraron del catálogo siguen necesitando un nombre, pero no
# pueden llevar el de hoy sin mentir.
#
# Traducirlos funciona casi siempre: «Estado: asignado -> en_espera» se lee bien
# como «en progreso → en espera». Pero no siempre. El ticket TKT-2026-000092 tiene
# un evento «en_progreso -> asignado», y el estado al que entraba se llama igual
# que el de salida: al traducir se veía «Estado: en progreso → en progreso», que no
# es un cambio, es un error de pantalla. Peor que el estado viejo, porque el estado
# viejo al menos era verdad.
#
# Así que la traducción se comprueba. Si el estado de salida y el de entrada quedan
# con el mismo nombre, la traducción se descarta para esa línea: se deja el nombre
# de entonces y se marca que ya no está en el catálogo. Traducir casi siempre es
# mejor; traducir cuando el cambio desaparece es peor que no traducir.
NOMBRE_ACTUAL_RETIRADO: dict[str, str] = {
    # «asignado» era el paso previo a «en progreso».
    ESTADO_ASIGNADO_LEGADO: "en progreso",
    # «resuelto» ya no se distingue de «cerrado».
    ESTADO_RESUELTO_LEGADO: "cerrado",
}

MARCA_ESTADO_RETIRADO = " (estado antiguo)"


def _titulo_estado(valor: str) -> str:
    """Cómo se escribe un estado, esté en el catálogo o no."""
    return TITULOS_ESTADO.get(valor) or NOMBRE_ACTUAL_RETIRADO.get(valor, valor)


def _estado_mencionado(fragmento: str) -> str | None:
    """Qué estado nombra este trozo de texto, si nombra alguno.

    Se mira primero el estado más largo: en «Estado: en_progreso» está tanto
    «nuevo» —dentro de «en_progreso» no, pero sí dentro de otras palabras— como
    «en_progreso», y gana el que corresponde.
    """
    for valor in sorted((*TITULOS_ESTADO, *NOMBRE_ACTUAL_RETIRADO), key=len, reverse=True):
        if valor in fragmento:
            return valor
    return None


def _resumen_legible(resumen: str) -> str:
    """Pone los nombres de estado en palabras y con los de hoy.

    También unifica la flecha: las transiciones anteriores se escribieron como
    «->» y las nuevas como «→», y en la misma lista una cosa y la otra se leen como
    que salieron de sitios distintos. Que es lo que eran, pero no ayuda a leer.

    Un estado retirado se muestra con el nombre de hoy **salvo que eso borre el
    cambio**: si el estado del que se sale y al que se llega se llaman igual, la
    línea afirmaría que el ticket no cambió de estado cuando sí cambió. En ese caso
    se deja el nombre de entonces, que es lo que ocurrió, y se marca como antiguo.
    """
    if not resumen:
        return resumen
    resumen = resumen.replace("->", "→")
    antes, flecha, despues = resumen.partition("→")
    if not flecha:
        return _escribir_estados(antes)

    estado_antes = _estado_mencionado(antes)
    estado_despues = _estado_mencionado(despues)
    # Traducir a la letra dejaría «Estado: en progreso → en progreso»: el cambio se
    # vería como que no ocurrió. Se deshace solo en el lado que traía el estado
    # retirado, que es el único que puede haber producido el choque.
    choca = (
        estado_antes is not None
        and estado_despues is not None
        and estado_antes != estado_despues
        and _titulo_estado(estado_antes) == _titulo_estado(estado_despues)
    )
    izquierda = _escribir_estados(antes, conservar_retirado=choca and estado_antes in NOMBRE_ACTUAL_RETIRADO)
    derecha = _escribir_estados(despues, conservar_retirado=choca and estado_despues in NOMBRE_ACTUAL_RETIRADO)
    return f"{izquierda.strip()} → {derecha.strip()}"


def _escribir_estados(fragmento: str, *, conservar_retirado: bool = False) -> str:
    """Pone los estados de un trozo de texto en palabras.

    Con ``conservar_retirado`` se deja el nombre de un estado ya retirado tal como
    estaba y se le añade la marca de que es antiguo, para no perder el cambio.
    """
    texto = fragmento
    for valor, titulo in TITULOS_ESTADO.items():
        if valor in texto:
            texto = texto.replace(valor, titulo)
    for retirado, nombre_actual in NOMBRE_ACTUAL_RETIRADO.items():
        if retirado not in texto:
            continue
        texto = texto.replace(
            retirado,
            retirado + MARCA_ESTADO_RETIRADO if conservar_retirado else nombre_actual,
        )
    return texto


# ── Creacion ─────────────────────────────────────────────────
async def _verificar_adjuntos_propios(adjuntos: list[str] | None, usuario: dict[str, Any]) -> None:
    """Los adjuntos iniciales deben ser de quien crea el ticket y estar libres.

    Se comprueba antes de crear el ticket para que un id ajeno —o ya vinculado—
    se rechace sin dejar un ticket a medias. El `update_many` posterior repite
    el filtro: entre la comprobacion y el vinculo no puede colarse otro dueño.
    """
    ids = [a_id(a) for a in adjuntos or [] if a_id(a)]
    if not ids:
        return
    disponibles = {
        "_id": {"$in": ids},
        "ticket_id": None,
        "mensaje_id": None,
        "subido_por": usuario.get("_id"),
    }
    if await get_db()["adjuntos"].count_documents(disponibles) != len(ids):
        raise Prohibido("Algún adjunto no te pertenece o ya está vinculado a otro ticket.")


async def crear_desde_usuario(
    datos: dict[str, Any], *, usuario: dict[str, Any], ip: str | None = None
) -> dict[str, Any]:
    """Paso 1 + Paso 2 del reporte del usuario (2 pasos, lenguaje cotidiano)."""
    db = get_db()
    solicitud_original = deepcopy(datos)
    repetido = await _repetido(solicitud_original, usuario, 'portal')
    if repetido:
        return repetido
    persona = datos.get("persona") or {}
    reporte_para = datos.get('reporte_para') or ('propio' if persona.get('es_para_mi', True) else 'companero')
    if datos.get('reporte_para'):
        persona = {**persona, 'es_para_mi': reporte_para != 'companero'}
        datos = {**datos, 'persona': persona, 'activo_id': None, 'conjunto_id': None,
                 'activo_no_identificado': datos.get('activo_no_identificado') if reporte_para == 'oficina' else None}
    if reporte_para == 'oficina':
        if not usuario.get('oficina_id'):
            raise Validacion('Tu cuenta necesita una oficina asignada para reportar por la oficina.')
        from app.services.historial_inventario_service import tipos_oficina
        tipos = await tipos_oficina(usuario['oficina_id'])
        tipo_oficina = normalizar_texto(datos.get('activo_no_identificado'))
        if tipo_oficina and tipo_oficina not in tipos:
            raise Validacion('Selecciona un tipo de equipo de tu oficina o elige No lo sé.')
        persona = {**persona, 'es_para_mi': True, 'afectado_id': str(usuario['_id'])}
        datos = {**datos, 'persona': persona, 'activo_id': None, 'conjunto_id': None}
    es_para_mi = bool(persona.get("es_para_mi", True))
    afectado_id = a_id(persona.get("afectado_id"))
    solicitante_no_registrado: dict[str, Any] | None = None

    if es_para_mi:
        afectado = await db["usuarios"].find_one({"_id": usuario["_id"]})
        if afectado is None:
            raise NoEncontrado("No se encontro tu cuenta. Ingresa de nuevo.")
    elif afectado_id:
        afectado = await db["usuarios"].find_one({"_id": afectado_id, "activo": True})
        if afectado is None:
            raise NoEncontrado("La persona seleccionada ya no esta disponible.")
    else:
        datos_no_registrados = persona.get("persona_no_registrada") or {}
        nombre = normalizar_texto(datos_no_registrados.get("nombre"))
        if len(nombre) < 3:
            raise Validacion("Escribe el nombre de la persona afectada (minimo 3 caracteres).")
        afectado = None
        solicitante_no_registrado = {
            "nombre": nombre,
            "telefono": normalizar_texto(datos_no_registrados.get("telefono")) or None,
            "anexo": normalizar_texto(datos_no_registrados.get("anexo")) or None,
        }

    if usuario.get('rol') == 'usuario' and not es_para_mi:
        if not afectado or not usuario.get('oficina_id') or afectado.get('oficina_id') != usuario.get('oficina_id'):
            raise Prohibido('Solo puedes reportar para una persona de tu misma oficina.')

    zona_id = afectado.get("zona_id") if afectado else usuario.get("zona_id")
    zona_nombre = afectado.get("zona_nombre") if afectado else usuario.get("zona_nombre")
    oficina_id = afectado.get("oficina_id") if afectado else usuario.get("oficina_id")
    oficina_nombre = afectado.get("oficina_nombre") if afectado else usuario.get("oficina_nombre")

    activo = await _resolver_activo(datos, afectado=afectado, oficina_id=oficina_id, usuario=usuario)
    tipo_problema = normalizar_texto(datos.get("tipo_problema"))
    descripcion = normalizar_texto(datos.get("descripcion")) or None
    if not tipo_problema and not descripcion:
        raise Validacion("Elige un tipo de problema o describe brevemente que pasa.")

    origen = ORIGEN_USUARIO if es_para_mi else ORIGEN_USUARIO_TERCERO
    codigo = await _siguiente_codigo()
    ahora = utcnow()

    conversacion_id = nuevo_id()
    documento: dict[str, Any] = {
        "codigo": codigo,
        "asunto": titulo_reporte(tipo_problema, descripcion),
        "descripcion": descripcion,
        "tipo_problema": tipo_problema or None,
        "reporte_para": reporte_para,
        "estado": ESTADO_NUEVO,
        "prioridad": URGENCIA_A_PRIORIDAD.get(datos.get("urgencia", "puede_esperar"), "media"),
        "urgencia": datos.get("urgencia", "puede_esperar"),
        "origen": origen,
        "conversacion_id": conversacion_id,
        "reportante_id": usuario["_id"],
        "reportante_nombre": usuario.get("nombre"),
        "afectado_id": afectado["_id"] if afectado else None,
        "afectado_nombre": afectado.get("nombre") if afectado else solicitante_no_registrado["nombre"],
        "solicitante_no_registrado": solicitante_no_registrado,
        "zona_id": zona_id,
        "zona_nombre": zona_nombre,
        "oficina_id": oficina_id,
        "oficina_nombre": oficina_nombre,
        "activo_id": activo.get("_id") if activo else None,
        "activo_nombre": _nombre_activo(activo) if activo else normalizar_texto(datos.get("activo_no_identificado")) or None,
        "activo_no_identificado": normalizar_texto(datos.get("activo_no_identificado")) or None,
        "conjunto_id": activo.get("conjunto_id") if activo else a_id(datos.get("conjunto_id")),
        "conjunto_nombre": activo.get("conjunto_nombre") if activo else None,
        "activo_tipo": activo.get("tipo") if activo else None,
        "tecnico_id": None,
        "tecnico_nombre": None,
        "categoria": categoria_reporte(tipo_problema, descripcion or "", await categorias_activas()),
        "veces_reabierto": 0,
        "satisfaccion": None,
        "adjuntos_iniciales": list(datos.get("adjuntos") or []),
        "creado_en": ahora,
        "actualizado_en": ahora,
        "creado_por": usuario.get("nombre", ""),
        "detectado_por_tecnico": False,
    }
    from app.services.vinculo_ticket_service import resolver
    contexto = {**documento, 'activo_id': None, 'conjunto_id': None}
    documento.update(await resolver(contexto, {**datos, 'categoria': documento.get('categoria')}, usuario, creacion=True))
    documento.update(await sla_service.calcular_deadlines(documento["prioridad"], ahora))

    await _verificar_adjuntos_propios(datos.get("adjuntos"), usuario)
    documento, nuevo = await _insertar_solicitud(documento, solicitud_original, usuario, 'portal')
    if not nuevo:
        return documento
    documento["tiene_chat"] = True

    if datos.get("adjuntos"):
        ids = [a_id(a) for a in datos["adjuntos"] if a_id(a)]
        await db["adjuntos"].update_many(
            {
                "_id": {"$in": ids},
                "ticket_id": None,
                "mensaje_id": None,
                "subido_por": usuario.get("_id"),
            },
            {"$set": {"ticket_id": documento["_id"]}},
        )
    if documento.get("activo_id"):
        await db["activos"].update_one({"_id": documento["activo_id"]}, {"$inc": {"reportes": 1}})

    await _registrar_evento(
        documento,
        "creado",
        f"Ticket reportado por {usuario.get('nombre')}",
        actor=usuario,
        visible_usuario=True,
        detalle={
            "tipo_problema": tipo_problema,
            "urgencia": datos.get("urgencia"),
            "para_un_companero": not es_para_mi,
        },
    )
    await registrar(
        "ticket.crear",
        usuario_id=usuario["_id"],
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=documento["_id"],
        resumen=f"{codigo} creado por {usuario.get('nombre')}",
        despues={"codigo": codigo, "origen": origen, "prioridad": documento["prioridad"], "zona": zona_nombre},
        ip=ip,
    )
    from app.services import ia_service

    await ia_service.sugerir_clasificacion(documento, usuario)
    from app.services.resumen_ticket_service import encolar
    await encolar(str(documento['_id']))
    await _avisar_nuevo_ticket(documento)
    await notificaciones_service.publicar_ticket(documento["_id"], "ticket_creado", {"codigo": codigo})
    return documento


async def _avisar_nuevo_ticket(documento: dict[str, Any]) -> None:
    """Avisa a los técnicos de que hay trabajo nuevo.

    Antes, un ticket creado solo publicaba un evento en el canal del websocket y
    no dejaba rastro en ninguna bandeja: si nadie estaba mirando la lista en ese
    momento, el aviso se perdía. En un despliegue con un único administrador que
    crea y atiende todo, además nunca se le notificaba —porque es a la vez quien
    reporta y quien técnico— y la campana quedaba permanentemente vacía.

    Se avisa al técnico asignado si lo hay y, si no, a los técnicos y
    administradores activos, para que alguien lo recoja. A quien lo reportó se le
    excluye: ya sabe que lo ha creado.
    """
    reportante = documento.get("reportante_id")
    destinos: list[ObjectId] = []
    if documento.get("tecnico_id") and documento["tecnico_id"] != reportante:
        destinos.append(documento["tecnico_id"])
    else:
        equipo = await get_db()["usuarios"].find(
            {"_id": {"$ne": reportante}, "activo": {"$ne": False}, "rol": {"$in": ("tecnico", "administrador")}},
            {"_id": 1},
        ).to_list(None)
        destinos.extend(persona["_id"] for persona in equipo)

    asunto = documento.get("asunto") or documento.get("tipo_problema") or "Sin asunto"
    resumen = f"{documento.get('codigo')}: {asunto}"
    for usuario_id in dict.fromkeys(destinos):
        await notificaciones_service.crear(
            usuario_id,
            f"Ticket nuevo {documento.get('codigo')}",
            resumen[:200],
            tipo="asignacion",
            ticket_id=documento["_id"],
        )


async def _resolver_activo(
    datos: dict[str, Any], *, afectado: dict[str, Any] | None, oficina_id: Any, usuario: dict[str, Any]
) -> dict[str, Any] | None:
    db = get_db()
    activo_id = a_id(datos.get("activo_id"))
    if activo_id:
        activo = await db["activos"].find_one({"_id": activo_id, "activo": {"$ne": False}})
        if activo is None:
            raise NoEncontrado("El equipo seleccionado ya no esta disponible.")
        return activo
    conjunto_id = a_id(datos.get("conjunto_id"))
    if conjunto_id and afectado:
        activo = await db["activos"].find_one({"conjunto_id": conjunto_id, "responsable_id": afectado["_id"], "activo": {"$ne": False}})
        if activo:
            return activo
    texto = normalizar_texto(datos.get("activo_no_identificado"))
    if texto:
        # Texto libre: se queda como texto. No se busca en el inventario, porque
        # la coincidencia es sin anclar y un tipo como «CPU» se comería un equipo
        # cualquiera de entre los 6 que coinciden. Quien reporta elige de la lista
        # de sus equipos; si no está en el inventario, no hay equipo, hay un tipo.
        return None
    return None


def _nombre_activo(activo: dict[str, Any]) -> str:
    return (
        activo.get("nombre_equipo")
        or activo.get("conjunto_nombre")
        or " ".join(x for x in [activo.get("marca"), activo.get("modelo")] if x)
        or activo.get("tipo")
        or "Equipo"
    )


async def crear_manual(datos: dict[str, Any], *, usuario: dict[str, Any], ip: str | None = None) -> dict[str, Any]:
    """Registro manual por tecnico o administrador (2 pasos, sin chat)."""
    db = get_db()
    # El formulario actual selecciona personas registradas. Una petición heredada
    # no debe crear cuentas como efecto lateral de un ticket que puede rechazarse.
    if ((datos.get("persona") or {}).get("persona_no_registrada") or {}).get("crear_usuario"):
        if not tiene_permiso(usuario, "usuarios.editar"):
            raise Prohibido("No tienes permiso para crear cuentas de usuarios.")
        raise Validacion("Registra primero a la persona en Usuarios y selecciona su cuenta al crear el ticket.")
    solicitud_original = deepcopy(datos)
    repetido = await _repetido(solicitud_original, usuario, 'manual')
    if repetido:
        return repetido
    persona = datos.get("persona") or {}
    afectado_id = a_id(persona.get("afectado_id"))
    detectado_por_tecnico = bool(persona.get("detectado_por_tec"))
    solicitante_no_registrado: dict[str, Any] | None = None

    if afectado_id:
        afectado = await db["usuarios"].find_one({"_id": afectado_id, "activo": True})
        if afectado is None:
            raise NoEncontrado("El usuario seleccionado ya no esta disponible.")
    else:
        datos_no_registrados = persona.get("persona_no_registrada") or {}
        nombre = normalizar_texto(datos_no_registrados.get("nombre"))
        if len(nombre) < 3:
            raise Validacion("Escribe el nombre de la persona afectada (minimo 3 caracteres).")
        afectado = None
        solicitante_no_registrado = {
            "nombre": nombre,
            "telefono": normalizar_texto(datos_no_registrados.get("telefono")) or None,
            "anexo": normalizar_texto(datos_no_registrados.get("anexo")) or None,
        }
    zona_id = afectado.get("zona_id") if afectado else a_id((persona.get("persona_no_registrada") or {}).get("zona_id"))
    zona_nombre = afectado.get("zona_nombre") if afectado else None
    oficina_id = afectado.get("oficina_id") if afectado else a_id((persona.get("persona_no_registrada") or {}).get("oficina_id"))
    oficina_nombre = afectado.get("oficina_nombre") if afectado else None
    if (oficina_id or zona_id) and not zona_nombre:
        if oficina_id:
            oficina = await db["oficinas"].find_one({"_id": oficina_id})
            zona_nombre = (oficina or {}).get("zona_nombre")
            zona_id = (oficina or {}).get("zona_id")
        elif zona_id:
            zona = await db["zonas"].find_one({"_id": zona_id})
            zona_nombre = (zona or {}).get("nombre")

    activo = await _resolver_activo_manual(datos, afectado)
    origen = ORIGEN_ADMIN if usuario.get("rol") == "administrador" else ORIGEN_TECNICO
    if datos.get("origen") == ORIGEN_AUTOMATICO:
        origen = ORIGEN_AUTOMATICO
    codigo = await _siguiente_codigo()
    ahora = utcnow()

    tecnico_id = a_id(datos.get("tecnico_id")) or usuario["_id"]
    if tecnico_id == usuario["_id"] and usuario.get("rol") == "administrador":
        tecnico_id = usuario["_id"]
    tecnico = await db["usuarios"].find_one({"_id": tecnico_id}, {"nombre": 1}) or usuario

    documento: dict[str, Any] = {
        "codigo": codigo,
        "asunto": normalizar_texto(datos.get("asunto"))[:200],
        "descripcion": normalizar_texto(datos.get("descripcion")) or None,
        "tipo_problema": None,
        "estado": ESTADO_EN_PROGRESO if tecnico_id else ESTADO_NUEVO,
        "prioridad": datos.get("prioridad", "media"),
        "urgencia": None,
        "origen": origen,
        "conversacion_id": None,  # sin chat: lo registro el equipo TI
        "reportante_id": usuario["_id"],
        "reportante_nombre": usuario.get("nombre"),
        "afectado_id": afectado["_id"] if afectado else None,
        "afectado_nombre": afectado.get("nombre") if afectado else solicitante_no_registrado["nombre"],
        "solicitante_no_registrado": solicitante_no_registrado,
        "zona_id": zona_id,
        "zona_nombre": zona_nombre,
        "oficina_id": oficina_id,
        "oficina_nombre": oficina_nombre,
        "activo_id": activo.get("_id") if activo else None,
        "activo_nombre": _nombre_activo(activo) if activo else normalizar_texto(datos.get("activo_no_identificado")) or None,
        "activo_no_identificado": normalizar_texto(datos.get("activo_no_identificado")) or None,
        "conjunto_id": activo.get("conjunto_id") if activo else None,
        "conjunto_nombre": activo.get("conjunto_nombre") if activo else None,
        # El tipo se guarda aunque no haya equipo enlazado. «Es un CPU» es
        # información verdadera y sirve para el triage; inventar un equipo es
        # información falsa y además contaminaría el historial de ese equipo.
        "activo_tipo": (
            activo.get("tipo") if activo else normalizar_texto(datos.get("activo_tipo")) or None
        ),
        "tecnico_id": tecnico_id if tecnico_id else None,
        "tecnico_nombre": tecnico.get("nombre"),
        "categoria": normalizar_texto(datos.get("categoria")) or None,
        "veces_reabierto": 0,
        "satisfaccion": None,
        "adjuntos_iniciales": list(datos.get("adjuntos") or []),
        "creado_en": ahora,
        "actualizado_en": ahora,
        "creado_por": usuario.get("nombre", ""),
        "detectado_por_tecnico": detectado_por_tecnico,
    }
    from app.services.vinculo_ticket_service import resolver
    contexto = {**documento, 'activo_id': None, 'conjunto_id': None}
    documento.update(await resolver(contexto, {**datos, 'categoria': documento.get('categoria')}, usuario, creacion=True))
    documento.update(await sla_service.calcular_deadlines(documento["prioridad"], ahora))
    await _verificar_adjuntos_propios(datos.get("adjuntos"), usuario)
    documento, nuevo = await _insertar_solicitud(documento, solicitud_original, usuario, 'manual')
    if not nuevo:
        return documento
    documento["tiene_chat"] = False
    if datos.get("adjuntos"):
        ids = [a_id(a) for a in datos["adjuntos"] if a_id(a)]
        await db["adjuntos"].update_many(
            {
                "_id": {"$in": ids},
                "ticket_id": None,
                "mensaje_id": None,
                "subido_por": usuario.get("_id"),
            },
            {"$set": {"ticket_id": documento["_id"]}},
        )
    await _registrar_evento(
        documento,
        "creado",
        f"Ticket registrado por {usuario.get('nombre')}",
        actor=usuario,
        visible_usuario=True,
        detalle={
            "detectado_por_tecnico": detectado_por_tecnico,
            "sin_chat": True,
            "nota": "Registrado por el equipo TI: no hay chat, solo notas internas y nota de resolucion.",
        },
    )
    await registrar(
        "ticket.crear",
        usuario_id=usuario["_id"],
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=documento["_id"],
        resumen=f"{codigo} registrado manualmente por {usuario.get('nombre')}",
        despues={"codigo": codigo, "origen": origen, "detectado_por_tecnico": detectado_por_tecnico},
        ip=ip,
    )
    # El alta manual la hace el propio equipo TI: si el caso se le asigna a otra
    # persona, esa persona tiene que enterarse. Antes no se le avisaba.
    if tecnico_id and tecnico_id != usuario.get("_id"):
        await notificaciones_service.crear(
            tecnico_id,
            f"Nuevo ticket {documento.get('codigo')}",
            f"{usuario.get('nombre')} te ha asignado el ticket {documento.get('codigo')}: {documento.get('asunto')}",
            tipo="asignacion",
            ticket_id=documento["_id"],
        )
    await notificaciones_service.publicar_ticket(documento["_id"], "ticket_creado", {"codigo": codigo})
    return documento


async def _resolver_activo_manual(datos: dict[str, Any], afectado: dict[str, Any] | None) -> dict[str, Any] | None:
    """El equipo del alta manual, **solo si se eligió uno de una lista**.

    Antes, si no venía `activo_id`, se cogía el texto escrito y se buscaba en el
    inventario con una coincidencia **sin anclar**, quedándose con el primero que
    salía. Escribir «CPU» —que es un tipo, no un identificador— enganchaba un
    equipo cualquiera: en el inventario había 6 que coinciden, repartidos entre
    MERCADO, PALACIO, PISCINA, SEGURIDAD y COMPLEJO, y se quedaba con uno de
    PALACIO. El ticket pasaba a tener zona, conjunto e historial de fallos de un
    equipo que no era de nadie.

    Peor: los nombres se repiten. «COMPUTADORA N°01 - TECLADO» aparece **52 veces**
    en cinco zonas, así que ni escribiendo el nombre exacto se sabe cuál es. Solo
    el código patrimonial identifica uno —461 de 876 lo tienen, y **ninguno está
    repetido**—, y por eso el equipo se elige de una lista y no se escribe.

    Un equipo que no está en el inventario no es un equipo: es un tipo. Se anota el
    tipo y el caso queda sin equipo enlazado, que es la verdad.
    """
    db = get_db()
    activo_id = a_id(datos.get("activo_id"))
    if activo_id:
        return await db["activos"].find_one({"_id": activo_id, "activo": {"$ne": False}})
    # Sin equipo elegido no se adivina ninguno: ni por texto, ni «el primero de la
    # persona». Quien registra el caso no sabe cuál de los equipos de la persona
    # afectada es, y elegir uno al azar es peor que no elegir ninguno.
    return None


# ── Bandeja ──────────────────────────────────────────────────
def consulta_listado(filtros: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    consulta = _consulta_por_rol(filtros, usuario)
    # `eliminar` es lógico (deja rastro en auditoría), así que el borrado se
    # excluye aquí. Sin esta línea el ticket salía en la cola después de
    # eliminarlo y el mensaje «Ticket eliminado» no se correspondía con nada.
    consulta["eliminado"] = {"$ne": True}
    if filtros.get("estado"):
        estados = set(filtros['estado'])
        if ESTADO_CERRADO in estados:
            estados.update(ESTADOS_CERRADOS)
        consulta["estado"] = {"$in": list(estados)}
    elif filtros.get("solo_abiertos"):
        consulta["estado"] = {"$nin": list(ESTADOS_CERRADOS)}
    if filtros.get("prioridad"):
        consulta["prioridad"] = {"$in": list(filtros["prioridad"])}
    if filtros.get("categoria"):
        consulta["categoria"] = {"$in": list(filtros["categoria"])}
    if filtros.get("origen"):
        consulta["origen"] = {"$in": list(filtros["origen"])}
    if filtros.get("zona_id"):
        consulta["zona_id"] = filtros["zona_id"]
    if filtros.get("oficina_id"):
        consulta["oficina_id"] = filtros["oficina_id"]
    if filtros.get("tecnico_id"):
        consulta["tecnico_id"] = filtros["tecnico_id"]
    if filtros.get("activo_id"):
        consulta["activo_id"] = filtros["activo_id"]
    if filtros.get('conjunto_id'):
        consulta['conjunto_id'] = id_requerido(filtros['conjunto_id'], 'conjunto')
    if filtros.get("fecha_desde") or filtros.get("fecha_hasta"):
        rango: dict[str, Any] = {}
        if filtros.get("fecha_desde"):
            rango["$gte"] = horario_service_inicio(filtros["fecha_desde"])
        if filtros.get("fecha_hasta"):
            rango["$lte"] = horario_service_fin(filtros["fecha_hasta"])
        consulta["creado_en"] = rango
    if filtros.get("texto"):
        # Se escapa lo escrito. Antes lo que se tecleaba iba **tal cual** dentro
        # de `$regex`, así que un asterisco o una interrogación cambiaban lo que
        # se buscaba: `a*b` no busca la palabra «a*b», busca «cero o más a
        # seguido de b», y devolvió 17 tickets. Un corchete sin cerrar sí que
        # reventaba con «regular expression is invalid» y la búsqueda era un 500.
        # Y `PC (recepción)` con paréntesis balanceados no reventaba: los
        # paréntesis son un grupo de captura, así que buscaba «PC receptor» y
        # devolvía cero resultados en silencio. Con `re.escape` se busca lo que
        # se escribió.
        termino = re.escape(normalizar_texto(filtros["texto"]))
        busqueda = [
            {'sistema_afectado': {'$regex': termino, '$options': 'i'}},
            {"codigo": {"$regex": termino, "$options": "i"}},
            {"asunto": {"$regex": termino, "$options": "i"}},
            {"descripcion": {"$regex": termino, "$options": "i"}},
            {"reportante_nombre": {"$regex": termino, "$options": "i"}},
            {"afectado_nombre": {"$regex": termino, "$options": "i"}},
            {"tecnico_nombre": {"$regex": termino, "$options": "i"}},
            {"activo_nombre": {"$regex": termino, "$options": "i"}},
            # El tipo también se busca. Sin esto, un caso anotado como «Es un CPU»
            # —sin equipo enlazado, que es como se registra cuando el equipo no
            # está dado de alta— era invisible al buscador: `activo_nombre` está
            # vacío en esos casos y el tipo vive en `activo_tipo`.
            {"activo_tipo": {"$regex": termino, "$options": "i"}},
        ]
        consulta.setdefault("$and", []).append({"$or": busqueda})
    if filtros.get("sla") == "vencido":
        consulta["sla_resolver_en"] = {"$lt": utcnow()}
        consulta["estado"] = {"$nin": list(ESTADOS_CERRADOS)}
    elif filtros.get("sla") == "riesgo":
        consulta["estado"] = {"$nin": list(ESTADOS_CERRADOS)}
        consulta["sla_resolver_en"] = {"$gte": utcnow(), "$lte": _riesgo_horas()}
    elif filtros.get("sla") == "incumplido":
        consulta["sla_incumplido"] = True

    if filtros.get('vista') == 'criticos':
        consulta.setdefault('$and', []).append({'estado': {'$nin': list(ESTADOS_CERRADOS)}})
        consulta['$and'].append({'$or': [{'prioridad': 'critica'}, {'sla_resolver_en': {'$lt': utcnow()}}]})
    elif filtros.get('vista') == 'cerrados':
        consulta.setdefault('$and', []).append({'estado': {'$in': list(ESTADOS_CERRADOS)}})

    return consulta


async def listar(filtros: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    consulta = consulta_listado(filtros, usuario=usuario)
    if filtros.get('conjunto_id'):
        from app.services.historial_inventario_service import consulta_conjunto
        consulta.pop('conjunto_id', None)
        consulta.setdefault('$and', []).append(await consulta_conjunto(id_requerido(filtros['conjunto_id'], 'conjunto')))

    pagina = int(filtros.get("pagina") or 1)
    por_pagina = int(filtros.get("por_pagina") or 25)
    orden = filtros.get("orden") or "antiguedad"
    direccion = -1 if (filtros.get("direccion") or "desc") == "desc" else 1

    total = await db["tickets"].count_documents(consulta)
    if orden == "antiguedad":
        documentos = await (
            db["tickets"].find(consulta).sort([("creado_en", direccion), ("_id", direccion)]).skip((pagina - 1) * por_pagina).limit(por_pagina).to_list(None)
        )
    elif orden == "actualizacion":
        documentos = await (
            db["tickets"].find(consulta).sort("actualizado_en", direccion).skip((pagina - 1) * por_pagina).limit(por_pagina).to_list(None)
        )
    elif orden == "sla":
        documentos = await (
            db["tickets"].find(consulta).sort("sla_resolver_en", direccion).skip((pagina - 1) * por_pagina).limit(por_pagina).to_list(None)
        )
    else:  # urgencia: prioridad, luego SLA mas proximo
        documentos = await (
            db["tickets"]
            .find(consulta)
            .sort([("prioridad", -1), ("sla_resolver_en", 1), ("creado_en", -1)])
            .skip((pagina - 1) * por_pagina)
            .limit(por_pagina)
            .to_list(None)
        )

    with sla_service.lote_calculo():
        items = [await _resumen(documento) for documento in documentos]
    return {
        "items": items,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": math.ceil(total / por_pagina) if por_pagina else 0,
    }


def horario_service_inicio(dia) -> Any:
    from app.services.horario_service import inicio_utc

    return inicio_utc(_fecha_filtro(dia))


def horario_service_fin(dia) -> Any:
    from app.services.horario_service import fin_utc

    return fin_utc(_fecha_filtro(dia))


def _fecha_filtro(valor: Any) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor)
        except ValueError as exc:
            raise Validacion("La fecha del filtro debe tener formato AAAA-MM-DD.") from exc
    raise Validacion("La fecha del filtro no es válida.")


def _riesgo_horas() -> Any:
    return utcnow() + timedelta(hours=8)


riesgo_horas = _riesgo_horas


def _consulta_por_rol(filtros: dict[str, Any], usuario: dict[str, Any]) -> dict[str, Any]:
    """Un usuario normal solo ve lo suyo. La IA no ve nada sin permiso."""
    consulta: dict[str, Any] = {}
    if usuario.get("rol") == "usuario":
        consulta["$or"] = [{"reportante_id": usuario["_id"]}, {"afectado_id": usuario["_id"]}]
    elif filtros.get("vista") == "mis_tickets":
        consulta["$or"] = [{"tecnico_id": usuario["_id"]}, {"reportante_id": usuario["_id"]}]
    elif filtros.get("solo_mios"):
        consulta["$or"] = [{"tecnico_id": usuario["_id"]}, {"reportante_id": usuario["_id"]}]
    elif filtros.get("vista") == "sin_asignar":
        consulta["tecnico_id"] = None
        consulta["estado"] = {"$nin": list(ESTADOS_CERRADOS)}
    return consulta


async def _resumen(ticket: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    no_leidos = 0
    if tiene_chat(ticket):
        no_leidos = await db["ticket_mensajes"].count_documents(
            {"ticket_id": ticket["_id"], "autor_id": {"$ne": ticket.get("tecnico_id")}, "leido_por_tecnico": False}
        )
    sla = await sla_service.estado_sla(ticket)
    salida = {
        "id": ticket["_id"],
        "codigo": ticket.get("codigo"),
        "asunto": (
            titulo_reporte(ticket.get('tipo_problema'), ticket.get('descripcion') or ticket.get('asunto'))
            if len(ticket.get('asunto') or '') > 70
            and ticket.get('origen') in ORIGENES_CON_CHAT
            and not ticket.get('asunto_editado_ti')
            else ticket.get('asunto')
        ),
        "descripcion": (ticket.get("descripcion") or "")[:400] or None,
        "estado": ESTADO_CERRADO if ticket.get('estado') == ESTADO_RESUELTO_LEGADO else ticket.get('estado'),
        "prioridad": ticket.get("prioridad"),
        "origen": ticket.get("origen"),
        "categoria": ticket.get("categoria"),
        "reportante_id": ticket.get("reportante_id"),
        "reporte_para": ticket.get("reporte_para"),
        "reportante_nombre": ticket.get("reportante_nombre"),
        "afectado_id": ticket.get("afectado_id"),
        "afectado_nombre": ticket.get("afectado_nombre"),
        "zona_id": ticket.get("zona_id"),
        "zona_nombre": ticket.get("zona_nombre"),
        "oficina_id": ticket.get("oficina_id"),
        "oficina_nombre": ticket.get("oficina_nombre"),
        "activo_id": ticket.get("activo_id"),
        "activo_nombre": ticket.get("activo_nombre"),
        "activo_codigo_patrimonial": ticket.get("activo_codigo_patrimonial"),
        # Qué clase de equipo es. El nombre del equipo a veces lo lleva al final
        # («Computadora N°01 - CPU») y a veces no, y cuando la columna se estrecha
        # ese final es lo primero que se corta: sin el tipo aparte no se sabe si
        # es una CPU o una impresora.
        "activo_tipo": ticket.get("activo_tipo"),
        "conjunto_id": ticket.get("conjunto_id"),
        "conjunto_nombre": ticket.get("conjunto_nombre"),
        "tecnico_id": ticket.get("tecnico_id"),
        "tecnico_nombre": ticket.get("tecnico_nombre"),
        "creado_en": ticket.get("creado_en"),
        "actualizado_en": ticket.get("actualizado_en"),
        "sla": sla,
        "tiempo_resolucion_min": ticket.get("tiempo_resolucion_min"),
        "aceptacion": await _aceptacion_del_caso(ticket),
        "confianza_ia": ticket.get("confianza_ia"),
        "mensajes_no_leidos": no_leidos,
        "satisfaccion": ticket.get("satisfaccion"),
        "sla_incumplido": bool(ticket.get("sla_incumplido")) and ticket.get("estado") not in ESTADOS_CERRADOS,
    }
    if usuario_tecnico_ve_internos(ticket):
        salida["tiene_chat"] = tiene_chat(ticket)
        salida["detectado_por_tecnico"] = bool(ticket.get("detectado_por_tecnico"))
    return salida


def usuario_tecnico_ve_internos(ticket: dict[str, Any]) -> bool:
    """El chat siempre se indica como disponible o no; el endpoint lo valida igual."""
    return True


async def _aceptacion_del_caso(ticket: dict[str, Any]) -> dict[str, Any]:
    """Cuándo se Cogió el caso y cuánto se tardó, en minutos de trabajo.

    Responde a la pregunta que hace falta para medir la respuesta: **cuánto
    tardó el equipo TI en hacerse cargo**. Sin eso, un SLA que promete «responder
    en 4 h» no tiene con qué compararse.

    De dónde sale el momento, en este orden:

    1. ``primera_lectura_en``, que se escribe al aceptar el caso. Es lo fiel.
    2. Si no está —los casos anteriores a que eso se guardara—, el primer evento
       del historial que significa «alguien lo cogió»: la asignación o el cambio
       a «en progreso». Es una reconstrucción a partir del registro, no una
       suposición, y se marca como tal para que la interfaz pueda decirlo.
    3. Si tampoco hay evento, no se inventa nada: se dice que no consta.

    Los minutos son **laborables**, como todo el SLA: un caso aceptado un lunes a
    las 16:00 tardó 2 h de trabajo, no las que hubiera hasta la medianoche.
    """
    creado = ticket.get("creado_en")
    if not creado:
        return {"consta": False}
    momento = ticket.get("primera_lectura_en")
    reconstruido = False
    if not momento:
        evento = await get_db()["ticket_eventos"].find_one(
            {"ticket_id": ticket["_id"], "tipo": {"$in": ["asignado", "estado"]}},
            {"fecha": 1, "tipo": 1},
            sort=[("fecha", 1)],
        )
        if evento:
            momento = evento.get("fecha")
            reconstruido = True
    if not momento:
        return {"consta": False}

    minutos = int(await sla_service.minutos_laborables_entre(creado, momento))
    fecha_limite = ticket.get("sla_responder_en")
    cumplio = bool(fecha_limite and momento <= fecha_limite) if fecha_limite else None
    return {
        "consta": True,
        "en": momento,
        "minutos": minutos,
        "plazo_minutos": int(float(ticket.get("sla_horas_responder") or 0) * 60) or None,
        "cumplio": cumplio,
        "reconstruido": reconstruido,
    }


async def obtener(ticket_id: ObjectId, *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id, "eliminado": {"$ne": True}})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    _verificar_acceso(ticket, usuario)
    salida = await _resumen(ticket)
    salida['descripcion'] = ticket.get('descripcion')
    chat = tiene_chat(ticket)
    salida["tiene_chat"] = chat
    salida["conversacion_id"] = ticket.get("conversacion_id")
    salida["resuelto_en"] = ticket.get("resuelto_en")
    salida["cerrado_en"] = ticket.get("cerrado_en")
    salida["nota_resolucion"] = ticket.get("nota_resolucion")
    salida["veces_reabierto"] = ticket.get("veces_reabierto", 0)
    salida["detectado_por_tecnico"] = bool(ticket.get("detectado_por_tecnico"))
    salida["urgencia"] = ticket.get("urgencia")
    salida["tipo_problema"] = ticket.get("tipo_problema")
    salida['alcance_incidencia'] = ticket.get('alcance_incidencia') or ('equipo' if ticket.get('activo_id') else 'conjunto' if ticket.get('conjunto_id') else 'pendiente')
    salida['sistema_afectado'] = ticket.get('sistema_afectado')

    es_tecnico = usuario.get("rol") in ("tecnico", "administrador")
    if es_tecnico:
        notas = await (db["notas_internas"].find({"ticket_id": ticket_id}).sort("creado_en", -1).to_list(None))
        for nota in notas:
            nota["id"] = nota.pop("_id")
        salida["notas_internas"] = notas
        eventos = await (db["ticket_eventos"].find({"ticket_id": ticket_id}).sort("fecha", 1).to_list(None))
        for evento in eventos:
            evento["id"] = evento.pop("_id")
            if evento.get("actor", {}).get("id") and not evento["actor"].get("nombre"):
                evento["actor"]["nombre"] = "Sistema"
            evento["resumen"] = _resumen_legible(evento.get("resumen") or "")
        salida["eventos"] = eventos
        salida["puede_operar"] = _puede_operar(ticket, usuario)
        # Cerrar y reabrir tienen su propio permiso, delegable y apagado de
        # fábrica. La interfaz lo necesita para no ofrecer un botón que el
        # servidor va a rechazar con un 403.
        salida["puede_cerrar"] = _puede_cerrar(ticket, usuario)
        salida["puede_reabrir"] = _puede_cerrar(ticket, usuario)
        if tiene_permiso(usuario, "tickets.eliminar"):
            salida["puede_eliminar"] = True
    else:
        eventos = await db["ticket_eventos"].find(
            {"ticket_id": ticket_id, "visible_usuario": True}
        ).sort("fecha", 1).to_list(None)
        for evento in eventos:
            evento["id"] = evento.pop("_id")
            evento["resumen"] = _resumen_legible(evento.get("resumen") or "")
        salida["eventos"] = eventos
        if usuario.get("_id") == ticket.get("afectado_id") and usuario.get("_id") != ticket.get("reportante_id"):
            salida["solo_lectura"] = True

    from app.services import adjuntos_service

    salida["adjuntos"] = await adjuntos_service.listar_por_ticket(ticket_id)
    if ticket.get("reportante_id") and usuario.get("_id") != ticket.get("reportante_id") and es_tecnico:
        await db["ticket_mensajes"].update_many(
            {"ticket_id": ticket_id, "autor_id": {"$ne": usuario["_id"]}}, {"$set": {"leido_por_tecnico": True}}
        )
    if ticket.get("afectado_id") and es_tecnico:
        salida["afectado_equipos"] = await inventario_service.equipos_de_usuario(ticket["afectado_id"])
    return salida


def _verificar_acceso(ticket: dict[str, Any], usuario: dict[str, Any]) -> None:
    if usuario.get("rol") in ("tecnico", "administrador"):
        return
    if ticket.get("reportante_id") == usuario.get("_id") or ticket.get("afectado_id") == usuario.get("_id"):
        return
    raise Prohibido("No tienes acceso a este ticket.")


def _puede_operar(ticket: dict[str, Any], usuario: dict[str, Any]) -> bool:
    if usuario.get("rol") == "administrador":
        return True
    if ticket.get("tecnico_id") == usuario.get("_id"):
        return True
    if ticket.get("tecnico_id") is None:
        return tiene_permiso(usuario, "tickets.asignar_si_mismo")
    return False


def _puede_cerrar(ticket: dict[str, Any], usuario: dict[str, Any]) -> bool:
    """Misma regla que aplica `cambiar_estado` al cerrar o reabrir.

    El permiso `tickets.cerrar_reabrir` es delegable y arranca apagado, así que
    sin esto la interfaz ofrecía «Cerrar ticket» a quien el servidor iba a
    rechazar. Se expone el resultado para que el botón y el desplegable lo tengan
    en cuenta antes de ofrecerse.
    """
    if usuario.get("rol") == "administrador":
        return True
    if ticket.get("tecnico_id") == usuario.get("_id"):
        return True
    return tiene_permiso(usuario, "tickets.cerrar_reabrir")


# ── Operaciones ──────────────────────────────────────────────
async def actualizar(ticket_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    _verificar_acceso(ticket, usuario)
    es_tecnico = usuario.get("rol") in ("tecnico", "administrador")
    cambios: dict[str, Any] = {}
    if es_tecnico and datos.get('asunto') is not None:
        cambios['asunto_editado_ti'] = True
    for campo in ("asunto", "descripcion", "categoria"):
        if datos.get(campo) is not None:
            if not es_tecnico and campo == "categoria":
                raise Prohibido("La categoria la define el equipo de soporte.")
            cambios[campo] = normalizar_texto(datos[campo]) or None
    if datos.get("prioridad"):
        nueva = datos["prioridad"]
        if not es_tecnico and nueva != ticket.get("prioridad"):
            # El usuario puede subir la urgencia, nunca bajarla por debajo de la actual
            from app.domain.constants import PESO_PRIORIDAD

            actual = PESO_PRIORIDAD.get(ticket.get("prioridad", "media"), 2)
            if PESO_PRIORIDAD.get(nueva, 2) <= actual:
                raise Prohibido("Indica al equipo de soporte si necesitas mas urgencia.")
        cambios["prioridad"] = nueva
        cambios.update(await sla_service.recalcular_prioridad(ticket, nueva))
    from app.services.vinculo_ticket_service import resolver
    cambios.update(await resolver(ticket, datos, usuario))
    # La identificación de TI confirma el destino, sin alterar quién dio el aviso.
    # La categoría por sí sola nunca decide si un equipo es personal o compartido.
    if es_tecnico and cambios.get('vinculo_origen') and (datos.get('activo_id') or datos.get('conjunto_id')):
        if cambios['vinculo_origen'] == 'oficina':
            cambios['reporte_para'] = 'oficina'
        elif ticket.get('reporte_para') == 'oficina':
            cambios['reporte_para'] = 'propio' if ticket.get('reportante_id') == ticket.get('afectado_id') else 'companero'
    if not cambios:
        return await obtener(ticket_id, usuario=usuario)
    cambios["actualizado_en"] = utcnow()
    filtro = {'_id': ticket_id}
    if datos.get('version_esperada') is not None:
        filtro['actualizado_en'] = datos['version_esperada']
    resultado = await db["tickets"].update_one(filtro, {"$set": cambios})
    if not resultado.matched_count:
        raise Conflicto('Este ticket cambió mientras lo editabas. Revisa los datos actualizados antes de guardar.')
    await _registrar_evento(
        {**ticket, **cambios},
        "actualizado",
        f"{usuario.get('nombre')} actualizo: {', '.join(cambios.keys())}",
        actor=usuario,
        detalle={"campos": list(cambios.keys()), 'antes': {k: ticket.get(k) for k in cambios if k != 'actualizado_en'}, 'despues': {k: v for k, v in cambios.items() if k != 'actualizado_en'}},
        visible_usuario=True,
    )
    await registrar('ticket.actualizar', usuario_id=usuario.get('_id'), usuario_nombre=usuario.get('nombre', ''), rol=usuario.get('rol', ''), entidad='ticket', entidad_id=ticket_id, resumen=f"Datos de {ticket.get('codigo')} actualizados", antes={k: ticket.get(k) for k in cambios if k != 'actualizado_en'}, despues={k: v for k, v in cambios.items() if k != 'actualizado_en'})
    await notificaciones_service.publicar_ticket(ticket_id, "ticket_actualizado", {"campos": list(cambios.keys())})
    return await obtener(ticket_id, usuario=usuario)


async def asignar(ticket_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    from app.services import horario_service

    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    _verificar_acceso(ticket, usuario)
    if usuario.get("rol") == "usuario":
        raise Prohibido("La asignacion la realiza el equipo de soporte.")
    tecnico_id = a_id(datos.get("tecnico_id"))
    actual = ticket.get("tecnico_id")
    if tecnico_id != usuario.get("_id") and tecnico_id != actual and not tiene_permiso(usuario, "tickets.reasignar"):
        raise Prohibido("No tienes permiso para reasignar tickets a otra persona.")
    if usuario.get("rol") == "tecnico" and actual and actual != usuario.get("_id") and not tiene_permiso(usuario, "tickets.reasignar"):
        raise Prohibido("No puedes tomar un ticket asignado a otra persona.")

    advertencia: dict[str, Any] | None = None
    tecnico_nombre = None
    if tecnico_id:
        tecnico = await db["usuarios"].find_one({"_id": tecnico_id, "activo": True}, {"nombre": 1, "rol": 1})
        if tecnico is None:
            raise NoEncontrado("El tecnico seleccionado no esta disponible.")
        if tecnico.get("rol") not in ("tecnico", "administrador"):
            raise Validacion("El destino debe ser un tecnico de soporte.")
        tecnico_nombre = tecnico.get("nombre")
        disponibilidad = await horario_service.calcular_disponibilidad(tecnico_id)
        if disponibilidad["estado"] in ("fuera_de_horario", "dia_libre", "ausente"):
            advertencia = {
                "requiere_confirmacion": True,
                "estado": disponibilidad["estado"],
                "etiqueta": disponibilidad["etiqueta"],
                "mensaje": (
                    f"{tecnico_nombre} esta {disponibilidad['etiqueta'].lower()}. "
                    "Asignarle de todos modos?"
                ),
            }
            if not datos.get("confirmar_fuera_de_horario"):
                return {"requiere_confirmacion": True, "advertencia": advertencia}

    cambios: dict[str, Any] = {
        "tecnico_id": tecnico_id,
        "tecnico_nombre": tecnico_nombre,
        "actualizado_en": utcnow(),
    }
    # Asignar no es un estado: un ticket sin técnico pasa a «en progreso» en el
    # mismo paso, porque no hay una etapa intermedia que alguien mantenga a mano.
    #
    # Eso hace de la asignación **el momento en que alguien acepta el caso**, y
    # ese momento es el que responde a «¿cuánto tardarón en cogerlo?». Antes solo
    # se guardaba cuando alguien movía el estado a mano, así que de 26 tickets
    # había 6 con la fecha de aceptación y 20 sin ella: el dato que se pedía
    # para medir la respuesta no se estaba midiendo. Se guarda la primera vez
    # solamente, para que reasignar no la mueva.
    if tecnico_id and ticket.get("estado") in (ESTADO_NUEVO,):
        cambios["estado"] = ESTADO_EN_PROGRESO
        if not ticket.get("primera_lectura_en"):
            cambios["primera_lectura_en"] = cambios["actualizado_en"]
    resultado = await db["tickets"].update_one({'_id': ticket_id, 'tecnico_id': actual, 'estado': ticket.get('estado'), 'actualizado_en': ticket.get('actualizado_en')}, {"$set": cambios})
    if not resultado.matched_count:
        raise Conflicto('Otro integrante modificó o tomó este ticket. Actualiza la ficha antes de asignarlo.')
    await _registrar_evento(
        {**ticket, **cambios},
        "asignado",
        f"Asignado a {tecnico_nombre or 'sin asignar'}",
        actor=usuario,
        detalle={"tecnico": tecnico_nombre, "comentario": datos.get("comentario"), "advertencia": advertencia},
        visible_usuario=True,
    )
    await registrar(
        "ticket.asignar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resumen=f"{ticket.get('codigo')} asignado a {tecnico_nombre or 'sin asignar'}",
        antes={"tecnico": ticket.get("tecnico_nombre")},
        despues={"tecnico": tecnico_nombre},
    )
    if tecnico_id and tecnico_id != usuario.get("_id"):
        await notificaciones_service.crear(
            tecnico_id,
            f"Nuevo ticket {ticket.get('codigo')}",
            f"{usuario.get('nombre')} te asigno el ticket {ticket.get('codigo')}: {ticket.get('asunto')}",
            tipo="asignacion",
            ticket_id=ticket_id,
        )
    await notificaciones_service.publicar_ticket(ticket_id, "ticket_asignado", {"tecnico": tecnico_nombre})
    return await obtener(ticket_id, usuario=usuario)


async def cambiar_estado(ticket_id: ObjectId, datos: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    _verificar_acceso(ticket, usuario)
    es_tecnico = usuario.get("rol") in ("tecnico", "administrador")
    nuevo = datos["estado"]

    if not es_tecnico:
        # El usuario solo puede reabrir un ticket cerrado dentro de las reglas
        if nuevo == ESTADO_EN_PROGRESO and ticket.get("estado") == ESTADO_CERRADO:
            desde = ticket.get("cerrado_en") or ticket.get("resuelto_en") or ticket.get("creado_en")
            dias = (utcnow() - desde).days if desde else 99
            if dias > 15:
                raise Prohibido("Este ticket lleva mas de 15 dias cerrado. Contacta al soporte directamente.")
            return await _reabrir(ticket, usuario, motivo="Reapertura solicitada por el usuario")
        raise Prohibido("El estado del ticket lo gestiona el equipo de soporte.")

    if nuevo == ESTADO_CERRADO:
        if not tiene_permiso(usuario, "tickets.cerrar_reabrir") and ticket.get("tecnico_id") != usuario.get("_id"):
            raise Prohibido("No tienes permiso para cerrar tickets de otra persona.")
    actual = ticket.get("estado")
    if nuevo == actual:
        return await obtener(ticket_id, usuario=usuario)
    if nuevo not in TRANSICIONES.get(actual, set()):
        etiquetas_estado = {
            ESTADO_NUEVO: "Nuevo",
            ESTADO_EN_PROGRESO: "En progreso",
            ESTADO_EN_ESPERA: "En espera",
            ESTADO_CERRADO: "Cerrado",
        }
        raise Conflicto(
            f"El ticket está {etiquetas_estado.get(actual, 'en un estado no disponible')} y no se puede cambiar a {etiquetas_estado.get(nuevo, 'ese estado')}.",
            detalles={"estado_actual": actual, "estado_nuevo": nuevo, "permitidos": sorted(TRANSICIONES.get(actual, set()))},
        )

    ahora = utcnow()
    cambios: dict[str, Any] = {"estado": nuevo, "actualizado_en": ahora}
    descripcion_evento = ""
    if nuevo == ESTADO_EN_PROGRESO and not ticket.get("primera_lectura_en"):
        cambios["primera_lectura_en"] = ahora
    if nuevo == ESTADO_EN_ESPERA:
        cambios["pausa_motivo"] = normalizar_texto(datos.get("pausa_motivo")) or None
        cambios["pausado_en"] = ahora
    if nuevo == ESTADO_CERRADO:
        cambios["cerrado_en"] = ahora
        cambios["cerrado_por"] = usuario.get("nombre")
        descripcion_evento = f"Cerrado por {usuario.get('nombre')}"
        if actual in ESTADOS_ABIERTOS:
            # Cerrar desde un estado abierto es un solo paso: se escribe la
            # solución y se archiva a la vez. Antes pasaba por «resuelto» y luego
            # por «cerrado»: dos estados que significaban lo mismo, y obligaban al
            # técnico a volver sobre el caso solo para terminarlo.
            nota = normalizar_texto(datos.get("nota_resolucion"))
            if not nota:
                raise Validacion("Escribe qué solución se aplicó antes de cerrar el ticket.")
            cambios["nota_resolucion"] = nota
            # `resuelto_en` se sigue escribiendo aunque el estado ya no sea
            # «resuelto»: es la marca de cuándo se resolvió el caso, y de ahí
            # salen los tiempos de resolución, el cumplimiento de SLA y las
            # valoraciones. El nombre del campo es histórico; lo que cuenta es la
            # fecha.
            cambios["resuelto_en"] = ahora
            cambios["resuelto_por"] = usuario.get("nombre")
            if ticket.get("creado_en"):
                transcurrido = await sla_service.minutos_laborables_entre(ticket["creado_en"], ahora)
                cambios["tiempo_resolucion_min"] = round(transcurrido, 1)
    if nuevo in (ESTADO_EN_PROGRESO,) and ticket.get("estado") in ESTADOS_CERRADOS:
        cambios["veces_reabierto"] = int(ticket.get("veces_reabierto", 0)) + 1
        cambios["reabierto_en"] = ahora
        descripcion_evento = "Reabierto"

    resultado = await db["tickets"].update_one({'_id': ticket_id, 'estado': actual, 'tecnico_id': ticket.get('tecnico_id'), 'actualizado_en': ticket.get('actualizado_en')}, {"$set": cambios})
    if not resultado.matched_count:
        raise Conflicto('El estado o la asignación cambió en otra cuenta. Actualiza la ficha antes de continuar.')
    await _registrar_evento(
        {**ticket, **cambios},
        "estado",
        descripcion_evento or f"Estado: {TITULOS_ESTADO.get(actual, actual)} → {TITULOS_ESTADO.get(nuevo, nuevo)}",
        actor=usuario,
        detalle={"estado_anterior": actual, "estado_nuevo": nuevo, "nota": datos.get("nota_resolucion")},
        visible_usuario=True,
    )
    await registrar(
        "ticket.cerrar" if nuevo == ESTADO_CERRADO else "ticket.estado",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resumen=f"{ticket.get('codigo')}: {actual} -> {nuevo}",
        antes={"estado": actual},
        despues={"estado": nuevo},
    )
    if nuevo == ESTADO_CERRADO and actual in ESTADOS_ABIERTOS:
        await notificaciones_service.avisar_participantes(
            ticket,
            titulo=f"Problema resuelto: {ticket.get('codigo')}",
            mensaje=(datos.get("nota_resolucion") or "")[:300],
            excluir=usuario.get("_id"),
        )
    await notificaciones_service.publicar_ticket(ticket_id, "ticket_estado", {"estado": nuevo})
    return await obtener(ticket_id, usuario=usuario)


async def _reabrir(ticket: dict[str, Any], usuario: dict[str, Any], *, motivo: str) -> dict[str, Any]:
    db = get_db()
    ahora = utcnow()
    cambios = {
        "estado": ESTADO_EN_PROGRESO,
        "veces_reabierto": int(ticket.get("veces_reabierto", 0)) + 1,
        "reabierto_en": ahora,
        "actualizado_en": ahora,
        "ultima_reapertura": {"usuario": usuario.get("nombre"), "motivo": motivo, "fecha": ahora},
    }
    resultado = await db["tickets"].update_one({'_id': ticket['_id'], 'estado': ticket.get('estado'), 'actualizado_en': ticket.get('actualizado_en')}, {"$set": cambios})
    if not resultado.matched_count:
        raise Conflicto('El ticket cambió en otra cuenta. Actualiza la ficha antes de reabrirlo.')
    await _registrar_evento(
        {**ticket, **cambios},
        "reabierto",
        f"Reabierto por {usuario.get('nombre')}: {motivo}",
        actor=usuario,
        visible_usuario=True,
    )
    await registrar(
        "ticket.reabrir",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket["_id"],
        resumen=f"{ticket.get('codigo')} reabierto",
        antes={"estado": ticket.get("estado")},
        despues={"estado": ESTADO_EN_PROGRESO, "motivo": motivo},
    )
    await notificaciones_service.avisar_participantes(
        ticket,
        titulo=f"Ticket reabierto: {ticket.get('codigo')}",
        mensaje=motivo,
        excluir=usuario.get("_id"),
        tipo="alerta",
    )
    return await obtener(ticket["_id"], usuario=usuario)


async def eliminar(ticket_id: ObjectId, *, usuario: dict[str, Any], motivo: str | None = None) -> None:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    if not tiene_permiso(usuario, "tickets.eliminar"):
        raise Prohibido("No tienes permiso para eliminar tickets.")
    await db["tickets"].update_one(
        {"_id": ticket_id},
        {"$set": {"eliminado_en": utcnow(), "eliminado_por": usuario.get("nombre"), "eliminado": True}},
    )
    await registrar(
        "ticket.eliminar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resultado="eliminado",
        resumen=f"{ticket.get('codigo')} eliminado",
        antes={"codigo": ticket.get("codigo"), "estado": ticket.get("estado")},
        contexto={"motivo": motivo},
    )
    await notificaciones_service.publicar_ticket(ticket_id, "ticket_eliminado", {})


# ── Chat (solo tickets reportados por un usuario) ────────────
async def enviar_mensaje(ticket_id: ObjectId, cuerpo: str, adjuntos: list[str], *, usuario: dict[str, Any]) -> dict[str, Any]:
    """Endpoint de mensajes. Rechaza tickets sin chat en el backend."""
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id, "eliminado": {"$ne": True}})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    # Primero el acceso y despues el estado del chat: al reves, un trabajador
    # distinguia un ticket ajeno (que existe) de uno inventado por la respuesta.
    _verificar_acceso(ticket, usuario)
    if not tiene_chat(ticket):
        raise Prohibido(
            "Este ticket fue registrado por el equipo de soporte, asi que no tiene chat. "
            "La comunicacion queda registrada en la linea de tiempo y las notas internas.",
            codigo="sin_chat",
        )
    texto = normalizar_texto(cuerpo)
    if not texto and not adjuntos:
        raise Validacion("Escribe un mensaje o adjunta un archivo.")
    ids_adjuntos = [a_id(a) for a in adjuntos]
    if len(adjuntos) > 5 or any(a is None for a in ids_adjuntos) or len(set(ids_adjuntos)) != len(ids_adjuntos):
        raise Validacion("Selecciona hasta 5 archivos válidos y sin repetir.")
    mensaje_id = ObjectId()
    if ids_adjuntos:
        disponibles = {"_id": {"$in": ids_adjuntos}, "subido_por": usuario.get("_id"), "ambito": "ticket", "ticket_id": None, "mensaje_id": None}
        if await db["adjuntos"].count_documents(disponibles) != len(ids_adjuntos):
            raise Prohibido("Algún adjunto no te pertenece o ya está vinculado a otro mensaje.")
        vinculados = await db["adjuntos"].update_many(disponibles, {"$set": {"ticket_id": ticket_id, "mensaje_id": mensaje_id}})
        if vinculados.modified_count != len(ids_adjuntos):
            await db["adjuntos"].update_many({"mensaje_id": mensaje_id}, {"$set": {"ticket_id": None, "mensaje_id": None}})
            raise Validacion("Los adjuntos cambiaron. Vuelve a seleccionarlos.")
    documento = {
        "_id": mensaje_id,
        "ticket_id": ticket_id,
        "conversacion_id": ticket["conversacion_id"],
        "autor_id": usuario.get("_id"),
        "autor_nombre": usuario.get("nombre", ""),
        "autor_rol": usuario.get("rol", "usuario"),
        "cuerpo": texto,
        "adjuntos": list(adjuntos),
        "leido_por_tecnico": usuario.get("rol") in ("tecnico", "administrador"),
        "creado_en": utcnow(),
        "es_ia": False,
    }
    try:
        resultado = await db["ticket_mensajes"].insert_one(documento)
    except Exception:
        await db["adjuntos"].update_many({"mensaje_id": mensaje_id}, {"$set": {"ticket_id": None, "mensaje_id": None}})
        raise
    documento["id"] = resultado.inserted_id
    await db["tickets"].update_one({"_id": ticket_id}, {"$set": {"actualizado_en": utcnow()}})
    await _registrar_evento(
        ticket,
        "mensaje",
        f"{usuario.get('nombre')} escribio en el chat",
        actor=usuario,
        visible_usuario=True,
    )
    await registrar(
        "ticket.chat",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resumen=f"Mensaje en {ticket.get('codigo')}",
        contexto={"caracteres": len(texto)},
    )
    if usuario.get("rol") == "usuario":
        cerrado = ticket.get('estado') in ESTADOS_CERRADOS
        consulta_destinos = {'_id': ticket['tecnico_id'], 'activo': True} if ticket.get('tecnico_id') else {'rol': {'$in': ['tecnico', 'administrador']}, 'activo': True}
        async for destinatario in db.usuarios.find(consulta_destinos, {'_id': 1}):
            if destinatario['_id'] != usuario.get('_id'):
                await notificaciones_service.crear(destinatario['_id'], f"{'Mensaje en ticket finalizado' if cerrado else 'Nuevo mensaje'}: {ticket.get('codigo')}", texto[:120] or 'Se adjuntó un archivo', tipo='mensaje_cerrado' if cerrado else 'mensaje', ticket_id=ticket_id)
    else:
        await notificaciones_service.avisar_participantes(
            ticket,
            titulo=f"Respuesta de soporte: {ticket.get('codigo')}",
            mensaje=texto[:120] or "Se adjunto un archivo",
            excluir=usuario.get("_id"),
            tipo="mensaje",
        )
    await notificaciones_service.publicar_ticket(
        ticket_id,
        "mensaje",
        {
            "id": str(resultado.inserted_id),
            "cuerpo": texto,
            "autor_nombre": usuario.get("nombre"),
            "autor_rol": usuario.get("rol"),
            "creado_en": ahora_iso(),
        },
    )
    return documento


def ahora_iso() -> str:
    return utcnow().isoformat()


async def mensajes(ticket_id: ObjectId, *, usuario: dict[str, Any], desde: Any = None) -> list[dict[str, Any]]:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    # El acceso se comprueba antes de decir si hay chat; si no, la respuesta
    # vacia confirmaba la existencia de tickets ajenos.
    _verificar_acceso(ticket, usuario)
    if not tiene_chat(ticket):
        return []
    consulta: dict[str, Any] = {"ticket_id": ticket_id}
    if desde:
        consulta["creado_en"] = {"$gt": desde}
    documentos = await (db["ticket_mensajes"].find(consulta).sort("creado_en", 1).to_list(None))
    for documento in documentos:
        documento["id"] = documento.pop("_id")
    return documentos


# ── Notas internas ───────────────────────────────────────────
async def crear_nota(ticket_id: ObjectId, cuerpo: str, adjuntos: list[str], *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    if usuario.get("rol") == "usuario":
        raise Prohibido("Las notas internas son del equipo de soporte.")
    texto = normalizar_texto(cuerpo)
    if not texto and not adjuntos:
        raise Validacion("Escribe la nota o adjunta un archivo.")
    await _verificar_adjuntos_propios(adjuntos, usuario)
    documento = {
        "ticket_id": ticket_id,
        "autor_id": usuario.get("_id"),
        "autor_nombre": usuario.get("nombre", ""),
        "cuerpo": texto,
        "adjuntos": list(adjuntos),
        "creado_en": utcnow(),
    }
    resultado = await db["notas_internas"].insert_one(documento)
    documento["id"] = resultado.inserted_id
    if adjuntos:
        ids = [a_id(a) for a in adjuntos if a_id(a)]
        await db["adjuntos"].update_many(
            {
                "_id": {"$in": ids},
                "ticket_id": None,
                "mensaje_id": None,
                "subido_por": usuario.get("_id"),
            },
            {"$set": {"ticket_id": ticket_id, "nota_id": resultado.inserted_id}},
        )
    await db["tickets"].update_one({"_id": ticket_id}, {"$set": {"actualizado_en": utcnow()}})
    await _registrar_evento(
        ticket,
        "nota",
        f"{usuario.get('nombre')} agrego una nota interna",
        actor=usuario,
        visible_usuario=False,
    )
    await registrar(
        "ticket.nota",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resumen=f"Nota interna en {ticket.get('codigo')}",
    )
    await notificaciones_service.publicar_ticket(ticket_id, "nota", {"id": str(resultado.inserted_id)})
    return documento


async def eliminar_nota(nota_id, *, usuario: dict[str, Any]) -> None:
    db = get_db()
    if not tiene_permiso(usuario, "tickets.eliminar"):
        raise Prohibido("No tienes permiso para eliminar notas.")
    await db["notas_internas"].delete_one({"_id": nota_id})
    await registrar(
        "ticket.nota",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="nota_interna",
        entidad_id=nota_id,
        resultado="eliminado",
        resumen="Nota interna eliminada",
    )


# ── Valoracion ───────────────────────────────────────────────
async def valorar(ticket_id: ObjectId, puntuacion: int, comentario: str | None, *, usuario: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    _verificar_acceso(ticket, usuario)
    if ticket.get("estado") not in ESTADOS_CERRADOS:
        raise Prohibido("Puedes valorar cuando el ticket esté cerrado.")
    if usuario.get('_id') not in {ticket.get('reportante_id'), ticket.get('afectado_id')}:
        raise Prohibido('Solo quien reportó o la persona afectada puede valorar la atención.')
    if ticket.get("valorado_por") or ticket.get('satisfaccion') is not None:
        raise Conflicto("Este ticket ya fue valorado.")
    resultado = await db["tickets"].update_one(
        {"_id": ticket_id, 'estado': {'$in': list(ESTADOS_CERRADOS)}, 'valorado_por': None, 'satisfaccion': None},
        {"$set": {"satisfaccion": puntuacion, "valoracion_comentario": comentario, "valorado_por": usuario.get("_id"), "valorado_en": utcnow()}},
    )
    if not resultado.modified_count:
        raise Conflicto('El ticket ya fue valorado o cambió de estado. Actualiza el reporte.')
    await registrar(
        "ticket.encuesta",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resumen=f"{ticket.get('codigo')} valorado con {puntuacion}/5",
        despues={"puntuacion": puntuacion},
    )
    if ticket.get("tecnico_id") and ticket["tecnico_id"] != usuario.get("_id"):
        await notificaciones_service.crear(
            ticket["tecnico_id"],
            f"Valoracion de {ticket.get('codigo')}",
            f"{usuario.get('nombre')} valoró la atención con {puntuacion} de 5.",
            tipo="satisfaccion",
            ticket_id=ticket_id,
        )
    return {"satisfaccion": puntuacion}


# ── Habilitar chat cuando un usuario adopta un ticket ────────
async def adoptar_por_usuario(ticket_id, usuario: dict[str, Any]) -> dict[str, Any]:
    """Si un usuario con cuenta reporta/confirma un ticket creado por el equipo TI,
    el chat se habilita desde ese momento y se conserva la trazabilidad del cambio."""
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        raise NoEncontrado("Ticket no encontrado.")
    _verificar_acceso(ticket, usuario)
    if tiene_chat(ticket):
        return {"sin_cambios": True, "tiene_chat": True}
    ahora = utcnow()
    conversacion_id = nuevo_id()
    await db["tickets"].update_one(
        {"_id": ticket_id},
        {
            "$set": {
                "conversacion_id": conversacion_id,
                "origen_adopcion": {
                    "fecha": ahora,
                    "usuario": usuario.get("nombre"),
                    "origen_anterior": ticket.get("origen"),
                },
                "reportante_id": ticket.get("reportante_id"),
                "actualizado_en": ahora,
            }
        },
    )
    await _registrar_evento(
        ticket,
        "chat_habilitado",
        f"{usuario.get('nombre')} confirmo el problema desde su cuenta: el chat quedo habilitado",
        actor=usuario,
        visible_usuario=True,
        detalle={"origen_anterior": ticket.get("origen")},
    )
    await registrar(
        "ticket.actualizar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resumen=f"Chat habilitado en {ticket.get('codigo')} por confirmacion del usuario",
        antes={"origen": ticket.get("origen"), "tiene_chat": False},
        despues={"tiene_chat": True},
    )
    return {"tiene_chat": True}


async def registrar_intervencion_ia(ticket_id, resumen: str, tipo: str, detalle: dict[str, Any]) -> None:
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id}) or {"_id": ticket_id}
    await _registrar_evento(ticket, tipo, resumen, detalle=detalle, visible_usuario=False, origen_ia=True)
