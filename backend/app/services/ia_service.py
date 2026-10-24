"""Recomendaciones de IA: clasificacion, asignacion, resumen y aprendizaje.

Reglas invariables:
1. La IA propone; la persona decide (Aplicar / Editar / Descartar).
2. Si una persona tiene las recomendaciones desactivadas, el backend NO devuelve
   sugerencias, pero sigue registrando la senal de aprendizaje en segundo plano.
3. Sin datos suficientes se dice "Datos insuficientes"; nunca se inventa.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bson import ObjectId

from app.core.audit import registrar
from app.core.db import get_db
from app.core.ids import a_id, clave as clave_texto
from app.core.time import utcnow
from app.domain.constants import (
    PRIORIDAD_ALTA,
    PRIORIDAD_BAJA,
    PRIORIDAD_CRITICA,
    PRIORIDAD_MEDIA,
    URGENCIA_A_PRIORIDAD,
)
from app.services import config_service, ia_provider, kb_service

# Los cuatro valores de prioridad que el resto del sistema reconoce. Sirve para
# que una prioridad escrita a mano no acabe guardando un valor que nadie más lee.
PRIORIDADES_VALIDAS = {PRIORIDAD_BAJA, PRIORIDAD_MEDIA, PRIORIDAD_ALTA, PRIORIDAD_CRITICA}


def _anterior_de(clave: str | None, anterior: dict[str, Any]) -> Any:
    """Valor previo del campo que se está decidiendo, para poder decir qué cambió."""
    if clave == "categoria":
        return anterior.get("categoria")
    if clave == "prioridad":
        return anterior.get("prioridad")
    if clave == "tecnico_sugerido_id":
        return anterior.get("tecnico_nombre") or anterior.get("tecnico_id")
    return None


async def _nombre_tecnico(db, tecnico_id: ObjectId) -> str | None:
    documento = await db["usuarios"].find_one({"_id": tecnico_id}, {"nombre": 1})
    return (documento or {}).get("nombre")

# Palabras que determinan categoria y prioridad sin depender del modelo
PALABRAS_CATEGORIA: dict[str, list[str]] = {
    "No enciende": ["no enciende", "no prende", "no arranca", "apagado", "murio", "se apago"],
    "Internet / Red": ["internet", "wifi", "wi-fi", "red", "conexion", "no navega", "sin internet", "red lenta", "se desconecta"],
    "Impresora": ["impresora", "imprimir", "impresion", "papel", "toner", "tinta", "scanner"],
    "Sistema / Programa": ["programa", "sistema", "aplicacion", "se traba", "error", "no abre", "office", "word", "excel", "power point", "powerpoint", "pdf", "pantalla azul", "crash"],
    "Correo / Cuenta": ["correo", "email", "contrasena", "clave", "cuenta", "password", "no puedo entrar", "bloqueado", "acceso"],
    "Hardware": ["teclado", "mouse", "monitor", "pantalla", "ram", "disco", "bateria", "cargador", "procesador", "hardware", "ventilador", "teclado"],
    "Software instalado": ["instalar", "instalar programa", "software", "licencia", "update", "actualizar"],
    "Accesos y permisos": ["permiso", "acceso", "permisos", "autorizacion", "no puedo ver", "carpeta"],
    "Equipo lento": ["lento", "lenta", "demora", "tarda", "cargando", "se traba mucho", "muy lento"],
}
PALABRAS_CRITICAS = ["incendio", "urgente", "emergencia", "paralizo", "no puedo trabajar", "bloquea", "servidor caido", "perdida de datos", "fuga", "virus"]
PALABRAS_ALTAS = ["urgente", "importante", "no puedo", "imposible", "se repitio", "varias veces", "no imprime", "no conecta"]

# Tipos de dispositivo que sugieren la categoria
TIPO_A_CATEGORIA = {
    "Impresora": "Impresora",
    "Router": "Internet / Red",
    "Switch": "Internet / Red",
    "UPS": "Hardware",
}

def _limitar_explicacion(texto: str | None) -> str | None:
    if texto is None:
        return None
    texto = " ".join(texto.split())
    if len(texto) <= 90:
        return texto
    corte = texto[:87].rsplit(" ", 1)[0].rstrip()
    return f"{corte or texto[:87]}..."


def _texto(ticket: dict[str, Any] | str) -> str:
    if isinstance(ticket, str):
        return ticket.lower()
    partes = [ticket.get("tipo_problema") or "", ticket.get("asunto") or "", ticket.get("descripcion") or ""]
    return " ".join(partes).lower()


async def _recomendaciones_activas(usuario: dict[str, Any]) -> bool:
    if not await config_service.recomendaciones_globales():
        return False
    return bool((usuario.get("preferencias") or {}).get("recomendaciones_ia", True))


async def _registrar_aprendizaje(
    evento: dict[str, Any], *, usuario: dict[str, Any] | None = None, ticket: dict[str, Any] | None = None
) -> None:
    """Registra la senal aunque la persona tenga las recomendaciones ocultas."""
    if not await config_service.aprendizaje_activado():
        return
    documento = {
        "tipo": evento.get("tipo"),
        "ticket_id": (ticket or {}).get("_id"),
        "ticket_codigo": (ticket or {}).get("codigo"),
        "usuario_id": (usuario or {}).get("_id"),
        "categoria_elegida": evento.get("categoria_elegida"),
        "prioridad_elegida": evento.get("prioridad_elegida"),
        "categoria_sugerida": evento.get("categoria_sugerida"),
        "prioridad_sugerida": evento.get("prioridad_sugerida"),
        "decision": evento.get("decision"),
        "recomendacion_visible": bool(evento.get("recomendacion_visible", True)),
        "confianza": evento.get("confianza"),
        "detalle": evento.get("detalle") or {},
        "creado_en": utcnow(),
    }
    await get_db()["ia_eventos"].insert_one(documento)


# ── Clasificacion de categoria y prioridad ───────────────────
def _menciona(texto: str, palabra: str) -> bool:
    return bool(re.search(r"\b" + re.escape(clave_texto(palabra).lower()) + r"\b", texto))


def _clasificar_por_palabras(texto: str, tipo_activo: str | None) -> tuple[str | None, float, str]:
    texto = clave_texto(texto).lower()
    mejor_categoria = None
    mejor_puntaje = 0
    for categoria, palabras in PALABRAS_CATEGORIA.items():
        puntaje = sum(1 for palabra in set(palabras) if _menciona(texto, palabra))
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_categoria = categoria
    if tipo_activo and tipo_activo in TIPO_A_CATEGORIA:
        if mejor_puntaje == 0:
            return TIPO_A_CATEGORIA[tipo_activo], 0.6, f"El equipo es de tipo {tipo_activo}."
        return mejor_categoria, min(0.55 + 0.1 * mejor_puntaje, 0.9), f"El texto menciona {mejor_categoria.lower()}."
    if mejor_categoria and mejor_puntaje:
        return mejor_categoria, min(0.5 + 0.12 * mejor_puntaje, 0.9), f"El texto menciona palabras de '{mejor_categoria}'."
    return None, 0.0, "El texto no da pistas suficientes."


def _prioridad_por_palabras(texto: str, urgencia: str | None, tipo_activo: str | None) -> tuple[str, float, str]:
    texto = clave_texto(texto).lower()
    base = URGENCIA_A_PRIORIDAD.get(urgencia or "", PRIORIDAD_MEDIA)
    confianza = 0.7
    explicacion = {
        PRIORIDAD_BAJA: "Indicaste que puede esperar.",
        PRIORIDAD_MEDIA: "Indicaste que te frena un poco.",
        PRIORIDAD_ALTA: "Indicaste que no puedes trabajar.",
        PRIORIDAD_CRITICA: "Indicaste que te detiene por completo.",
    }.get(base, "La urgencia indicada define la prioridad inicial.")
    if any(_menciona(texto, palabra) for palabra in PALABRAS_CRITICAS):
        if base != PRIORIDAD_CRITICA:
            explicacion = "El texto indica una situacion critica."
            return PRIORIDAD_CRITICA, 0.75, explicacion
    if any(_menciona(texto, palabra) for palabra in PALABRAS_ALTAS) and base == PRIORIDAD_BAJA:
        return PRIORIDAD_ALTA, 0.65, "El texto indica urgencia aunque indicaste que puede esperar."
    if tipo_activo == "Impresora" and base == PRIORIDAD_BAJA:
        return PRIORIDAD_MEDIA, 0.6, "Una impresora afecta a varias personas de la oficina."
    return base, confianza, explicacion


async def sugerir_clasificacion(ticket: dict[str, Any], usuario: dict[str, Any]) -> None:
    """Al crear un ticket se guarda la sugerencia en el ticket y en ia_eventos."""
    db = get_db()
    tipo_activo = None
    if ticket.get("activo_id"):
        activo = await db["activos"].find_one({"_id": ticket["activo_id"]}, {"tipo": 1})
        tipo_activo = (activo or {}).get("tipo")
    texto = _texto(ticket)
    categoria, confianza_cat, explicacion_cat = _clasificar_por_palabras(texto, tipo_activo)
    prioridad, confianza_prio, explicacion_prio = _prioridad_por_palabras(texto, ticket.get("urgencia"), tipo_activo)
    visible = await _recomendaciones_activas(usuario)
    confianza = min(confianza_cat if categoria else 0.0, 0.0) if not categoria else round((confianza_cat + confianza_prio) / 2, 2)

    if not categoria:
        return
    await db["tickets"].update_one(
        {"_id": ticket["_id"]},
        {
            "$set": {
                "ia_sugerencia": {
                    "categoria": categoria,
                    "prioridad": prioridad,
                    "confianza": confianza,
                    "explicacion": _limitar_explicacion(explicacion_cat),
                    "visible": visible,
                    "creada_en": utcnow(),
                    "decision": None,
                }
            }
        },
    )
    await _registrar_aprendizaje(
        {
            "tipo": "clasificacion",
            "categoria_sugerida": categoria,
            "prioridad_sugerida": prioridad,
            "confianza": confianza,
            "recomendacion_visible": visible,
        },
        usuario=usuario,
        ticket=ticket,
    )


async def sugerencias_ticket(ticket_id: ObjectId, *, usuario: dict[str, Any]) -> dict[str, Any]:
    """Bloque IA del detalle. Si el usuario las desactivo, no se devuelve nada."""
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        return {"disponible": False, "motivo_no_disponible": "Ticket no encontrado.", "activa": False}
    if not await config_service.recomendaciones_globales():
        return {"disponible": False, "motivo_no_disponible": "Las recomendaciones de IA estan desactivadas por la institucion.", "activa": False}
    if not await _recomendaciones_activas(usuario):
        return {"disponible": False, "motivo_no_disponible": "Tienes las recomendaciones de IA desactivadas.", "activa": False}

    texto = _texto(ticket)
    tipo_activo = None
    if ticket.get("activo_id"):
        activo = await db["activos"].find_one({"_id": ticket["activo_id"]}, {"tipo": 1})
        tipo_activo = (activo or {}).get("tipo")
    categoria, confianza_cat, explicacion_cat = _clasificar_por_palabras(texto, tipo_activo)
    if usuario.get('rol') in {'tecnico', 'administrador'}:
        from app.services.categorias_ticket_service import categorias_activas, categoria_del_catalogo
        categoria = categoria_del_catalogo(categoria, await categorias_activas())
        if not categoria:
            confianza_cat = 0.0
            explicacion_cat = 'No hay una categoria vigente suficientemente identificada. Revisa el catalogo.'
    prioridad, confianza_prio, explicacion_prio = _prioridad_por_palabras(texto, ticket.get("urgencia"), tipo_activo)
    articulos = await kb_service.sugerir_para_ticket(f"{ticket.get('tipo_problema') or ''} {texto}", ticket.get("categoria"), usuario=usuario)
    minimo = await config_service.confianza_minima()

    resumen = None
    causa_raiz = None
    respuesta_sugerida = None
    proveedor = ia_provider.obtener_proveedor()
    if await proveedor.disponible():
        generado = await _generar_texto_ticket(ticket, texto)
        resumen = generado.get("resumen")
        causa_raiz = generado.get("causa_raiz")
        respuesta_sugerida = generado.get("respuesta_sugerida")

    riesgo_sla = None
    if ticket.get("sla_resolver_en"):
        from app.core.time import utcnow as ahora_utc

        restante = (ticket["sla_resolver_en"] - ahora_utc()).total_seconds() / 60
        if restante <= 0:
            riesgo_sla = "vencido"
        elif restante <= 60:
            riesgo_sla = "critico"
        elif restante <= 240:
            riesgo_sla = "atencion"

    sugerida = await sugerir_asignacion(ticket, usuario=usuario)
    confianza = round((confianza_cat + confianza_prio) / 2, 2) if categoria else 0.0
    # Lo que ya se decidió sobre cada punto. Sin esto la interfaz recalculaba la
    # sugerencia y volvía a ofrecerla después de aplicarla o de descartarla.
    decisiones = (ticket.get("ia_sugerencia") or {}).get("decisiones") or {}
    return {
        "disponible": True,
        "decisiones": decisiones,
        "categoria": categoria,
        "prioridad": prioridad,
        "confianza": confianza,
        "confianza_suficiente": confianza >= minimo,
        "explicacion": _limitar_explicacion(explicacion_cat),
        "resumen": _limitar_explicacion(resumen),
        "causa_raiz": _limitar_explicacion(causa_raiz),
        "riesgo_sla": riesgo_sla,
        "articulos": articulos,
        "respuesta_sugerida": _limitar_explicacion(respuesta_sugerida),
        "tecnico_sugerido_id": sugerida.get("tecnico_id"),
        "tecnico_sugerido_nombre": sugerida.get("tecnico_nombre"),
        "explicacion_asignacion": _limitar_explicacion(sugerida.get("explicacion")),
        "activa": True,
        "llm_disponible": bool(resumen or respuesta_sugerida),
    }


async def _generar_texto_ticket(ticket: dict[str, Any], texto: str) -> dict[str, Any]:
    proveedor = ia_provider.obtener_proveedor()
    mensajes = [
        {
            "role": "system",
            "content": (
                "Eres un asistente de mesa de ayuda TI municipal. Responde SOLO con un objeto JSON con las claves "
                '"resumen" (una frase), "causa_raiz" (hipotesis tecnica corta) y "respuesta_sugerida" '
                "(mensaje breve y amable en espanol para la persona que reporto). "
                "No inventes datos que no esten en el texto. Si falta informacion, escribe 'Falta informacion'."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "codigo": ticket.get("codigo"),
                    "tipo_problema": ticket.get("tipo_problema"),
                    "asunto": ticket.get("asunto"),
                    "descripcion": (ticket.get("descripcion") or "")[:1200],
                    "categoria": ticket.get("categoria"),
                    "prioridad": ticket.get("prioridad"),
                    "equipo": ticket.get("activo_nombre"),
                },
                ensure_ascii=False,
            ),
        },
    ]
    respuesta = await proveedor.completar(mensajes, temperatura=0.1)
    if not respuesta.disponible or not respuesta.texto:
        return {}
    try:
        datos = json.loads(respuesta.texto)
        if not isinstance(datos, dict):
            return {}
        return {
            k: _limitar_explicacion(v)
            for k, v in datos.items()
            if k in {"resumen", "causa_raiz", "respuesta_sugerida"} and isinstance(v, str)
        }
    except (ValueError, TypeError):
        return {}


# ── Asignacion sugerida ──────────────────────────────────────
async def sugerir_asignacion(ticket: dict[str, Any], *, usuario: dict[str, Any]) -> dict[str, Any]:
    """Sugiere un tecnico considerando carga, horario, ausencias y especialidad."""
    from app.services import horario_service

    if not await config_service.recomendaciones_globales():
        return {"disponible": False}
    panel = await horario_service.panel_equipo()
    if not panel:
        return {"disponible": False, "motivo": "No hay tecnicos registrados."}
    elegibles = [t for t in panel if t["estado"] in {"disponible", "en_espera", "ocupado"}]
    if not elegibles:
        fuera = ", ".join(sorted({t["etiqueta"] for t in panel}))
        return {
            "disponible": True,
            "tecnico_id": None,
            "tecnico_nombre": None,
            "explicacion": _limitar_explicacion(f"Todos los tecnicos estan fuera de horario o ausentes ({fuera}). Asigna manualmente."),
            "requiere_confirmacion": True,
        }
    categoria = ticket.get("categoria")
    zona = ticket.get("zona_nombre")
    puntuaciones: list[tuple[float, dict[str, Any], str]] = []
    for tecnico in elegibles:
        from app.services import horario_service as hs

        perfil = await hs.obtener_perfil(tecnico["tecnico_id"])
        puntos = 100.0
        razones: list[str] = []
        if tecnico["estado"] == "disponible":
            puntos += 30
            razones.append("esta disponible ahora")
        elif tecnico["estado"] == "ocupado":
            puntos -= 25
            razones.append("esta ocupado con otro ticket")
        else:
            puntos += 10
            razones.append("tiene la cola en espera")
        carga = tecnico["porcentaje_carga"]
        if carga >= 100:
            puntos -= 30
            razones.append(f"ya tiene {carga:.0f}% de su carga")
        elif carga >= 60:
            puntos -= 12
        else:
            puntos += 12
            razones.append(f"carga baja ({carga:.0f}%)")
        if perfil.get("categorias") and categoria in perfil["categorias"]:
            puntos += 18
            razones.append(f"atiende la categoria '{categoria}'")
        if perfil.get("zonas_pref") and zona in perfil["zonas_pref"]:
            puntos += 10
            razones.append(f"trabaja en {zona}")
        if perfil.get("especialidades"):
            equipment = (ticket.get("activo_nombre") or "").lower()
            for especialidad in perfil["especialidades"]:
                if especialidad.lower() in equipment or equipment in especialidad.lower():
                    puntos += 10
                    razones.append(f"especialidad en {especialidad}")
                    break
        metricas = tecnico.get("metricas") or {}
        if metricas.get("cumplimiento_sla") is not None:
            puntos += max(min((metricas["cumplimiento_sla"] - 80) / 5, 10), -10)
        if metricas.get("satisfaccion") is not None:
            puntos += max(min((metricas["satisfaccion"] - 3.5) * 4, 8), -8)
        puntuaciones.append((puntos, tecnico, "; ".join(razones) or "sin datos adicionales"))
    puntuaciones.sort(key=lambda item: item[0], reverse=True)
    mejor_puntos, mejor, razon = puntuaciones[0]
    alternativas = [
        {"tecnico_id": t["tecnico_id"], "tecnico_nombre": t["tecnico_nombre"], "puntos": round(p, 1), "estado": t["etiqueta"]}
        for p, t, _ in puntuaciones[:4]
    ]
    confianza = 0.5
    if len(puntuaciones) > 1:
        separacion = puntuaciones[0][0] - puntuaciones[1][0]
        confianza = min(0.5 + separacion / 40, 0.9)
    return {
        "disponible": True,
        "tecnico_id": mejor["tecnico_id"],
        "tecnico_nombre": mejor["tecnico_nombre"],
        "explicacion": _limitar_explicacion(f"Sugerido porque {razon}."),
        "confianza": round(confianza, 2),
        "alternativas": alternativas,
        "estado_destino": mejor["etiqueta"],
        "requiere_confirmacion": True,
    }


async def aplicar_sugerencia(
    ticket_id: ObjectId,
    *,
    accion: str,
    clave: str | None = None,
    valor: str | None = None,
    categoria: str | None = None,
    prioridad: str | None = None,
    respuesta_sugerida: str | None = None,
    usuario: dict[str, Any],
) -> dict[str, Any]:
    """Registra Aplicar / Editar / Descartar y aplica el cambio si corresponde.

    Antes esta función solo anotaba la decisión: la interfaz mandaba `clave` y
    `valor` y el servicio leía `categoria` y `prioridad`, que llegaban vacías, así
    que «Aplicar» contestaba con éxito sin cambiar nada del ticket.
    """
    db = get_db()
    ticket = await db["tickets"].find_one({"_id": ticket_id})
    if ticket is None:
        return {"ok": False}

    # La clave dice QUÉ se decide; el valor dice CON QUÉ se queda.
    valor = valor or None
    tecnico_id: ObjectId | None = None
    if clave:
        if clave == "categoria":
            categoria = valor
        elif clave == "prioridad":
            prioridad = valor
        elif clave == "tecnico_sugerido_id":
            tecnico_id = a_id(valor)

    # Una prioridad escrita a mano que no exista no se aplica: se ignora en lugar
    # de guardar un valor que el resto del sistema no reconoce.
    if prioridad and prioridad not in PRIORIDADES_VALIDAS:
        prioridad = None

    sugerencia = ticket.get("ia_sugerencia") or {}
    anterior = {
        "categoria": ticket.get("categoria"),
        "prioridad": ticket.get("prioridad"),
        "tecnico_id": ticket.get("tecnico_id"),
    }
    anterior["tecnico_nombre"] = await _nombre_tecnico(db, anterior["tecnico_id"]) if anterior["tecnico_id"] else None

    cambios: dict[str, Any] = {}
    if accion == "aplicar":
        if categoria and categoria != anterior["categoria"]:
            cambios["categoria"] = categoria
            from app.services.vinculo_ticket_service import resolver
            cambios.update(await resolver(ticket, {'categoria': categoria}, usuario))
        if prioridad and prioridad != anterior["prioridad"]:
            from app.services import sla_service

            cambios["prioridad"] = prioridad
            cambios.update(await sla_service.recalcular_prioridad(ticket, prioridad))
        if clave == "tecnico_sugerido_id" and tecnico_id:
            nombre = await _nombre_tecnico(db, tecnico_id)
            if nombre:
                cambios["tecnico_id"] = tecnico_id
                cambios["tecnico_nombre"] = nombre
                if ticket.get("estado") == "nuevo":
                    cambios["estado"] = "en_progreso"

    # Se guarda por clave y no un único estado del ticket: la interfaz puede
    # aplicar la categoría y descartar la prioridad, y cada una necesita saber
    # cómo quedó para dejar de ofrecer lo que ya se decidió.
    actualizacion: dict[str, Any] = {
        "ia_sugerencia.decision": accion,
        "ia_sugerencia.decidida_por": usuario.get("nombre"),
        "ia_sugerencia.decidida_en": utcnow(),
        "ia_sugerencia.categoria_elegida": categoria,
        "ia_sugerencia.prioridad_elegida": prioridad,
    }
    if clave:
        actualizacion[f"ia_sugerencia.decisiones.{clave}"] = {
            "accion": accion,
            "elegido": valor,
            "anterior": _anterior_de(clave, anterior),
            "por": usuario.get("nombre"),
            "en": utcnow(),
        }
    actualizacion.update(cambios)
    await db["tickets"].update_one({"_id": ticket_id}, {"$set": actualizacion})

    await _registrar_aprendizaje(
        {
            "tipo": "decision",
            "decision": accion,
            "clave": clave,
            "valor_elegido": valor,
            "categoria_sugerida": sugerencia.get("categoria"),
            "prioridad_sugerida": sugerencia.get("prioridad"),
            "categoria_elegida": categoria,
            "prioridad_elegida": prioridad,
            "confianza": sugerencia.get("confianza"),
            "recomendacion_visible": await _recomendaciones_activas(usuario),
        },
        usuario=usuario,
        ticket=ticket,
    )
    await registrar(
        "ia.aplicar" if accion != "descartar" else "ia.descartar",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ticket",
        entidad_id=ticket_id,
        resumen=f"Sugerencia de IA {accion} en {ticket.get('codigo')}",
        antes={"clave": clave, "categoria": anterior["categoria"], "prioridad": anterior["prioridad"]},
        despues={"clave": clave, "elegido": valor, "decision": accion, **cambios},
    )
    return {"ok": True, "accion": accion, "clave": clave, "cambios": cambios, "anterior": anterior}


async def sugerencias_para_crear(
    *,
    tipo_problema: str | None,
    descripcion: str | None,
    urgencia: str | None,
    usuario: dict[str, Any],
    activo_tipo: str | None = None,
) -> dict[str, Any]:
    """Sugerencia discreta del paso 1 del reporte del usuario."""
    texto = f"{tipo_problema or ''} {descripcion or ''}".lower()
    if not await _recomendaciones_activas(usuario):
        # La persona decidio no ver sugerencias, pero la senal se sigue guardando
        # para que el sistema aprenda igual (sin mostrarsela nunca).
        await _registrar_aprendizaje(
            {
                "tipo": "consulta_sugerencia",
                "decision": "oculta",
                "categoria_elegida": None,
                "prioridad_elegida": None,
                "detalle": {"tipo_problema": tipo_problema, "urgencia": urgencia, "activo_tipo": activo_tipo},
                "recomendacion_visible": False,
            },
            usuario=usuario,
        )
        return {
            "disponible": False,
            "motivo_no_disponible": "Tienes las recomendaciones de IA desactivadas.",
            "aprendizaje_registrado": True,
        }
    categoria, confianza_cat, explicacion_cat = _clasificar_por_palabras(texto, activo_tipo)
    prioridad, _, explicacion_prio = _prioridad_por_palabras(texto, urgencia, activo_tipo)
    articulos = await kb_service.sugerir_para_ticket(texto, categoria, limite=3, usuario=usuario)
    if not categoria:
        return {"disponible": True, "categoria": None, "articulos": articulos, "explicacion": "Elige un tipo de problema para recibir ayuda."}
    return {
        "disponible": True,
        "categoria": categoria,
        "prioridad": prioridad,
        "confianza": confianza_cat,
        "explicacion": _limitar_explicacion(explicacion_cat),
        "articulos": articulos,
        "activa": True,
    }


async def registrar_feedback(
    *,
    usuario: dict[str, Any],
    ticket_id: ObjectId | None,
    correcto: bool,
    comentario: str | None = None,
    contexto: str = "clasificacion",
) -> dict[str, Any]:
    """Retroalimentacion explicita de los operadores."""
    await _registrar_aprendizaje(
        {
            "tipo": "retroalimentacion",
            "decision": "correcta" if correcto else "incorrecta",
            "detalle": {"comentario": comentario, "contexto": contexto},
        },
        usuario=usuario,
    )
    return {"ok": True}


async def estado_para_usuario(usuario: dict[str, Any]) -> dict[str, Any]:
    global_activa = await config_service.ia_activada()
    recomendaciones = await config_service.recomendaciones_globales()
    personales = bool((usuario.get("preferencias") or {}).get("recomendaciones_ia", True))
    proveedor = await ia_provider.estado()
    return {
        "ia_global_activa": global_activa,
        "recomendaciones_globales": recomendaciones,
        "recomendaciones_personales": personales,
        "recomendaciones_visibles": global_activa and recomendaciones and personales,
        "aprendizaje_activo": await config_service.aprendizaje_activado(),
        "proveedor_disponible": proveedor["disponible"],
        "modelo": proveedor.get("modelo"),
    }


async def registrar_consulta(pregunta: str, respuesta: str, *, usuario: dict[str, Any], fuentes: list[dict[str, Any]]) -> None:
    await get_db()["ia_eventos"].insert_one(
        {
            "tipo": "consulta",
            "pregunta": pregunta[:1000],
            "respuesta": respuesta[:2000],
            "fuentes": fuentes,
            "usuario_id": usuario.get("_id"),
            "usuario_nombre": usuario.get("nombre"),
            "rol": usuario.get("rol"),
            "creado_en": utcnow(),
        }
    )
    await registrar(
        "ia.consulta",
        usuario_id=usuario.get("_id"),
        usuario_nombre=usuario.get("nombre", ""),
        rol=usuario.get("rol", ""),
        entidad="ia_chat",
        resumen=pregunta[:160],
        contexto={"longitud_respuesta": len(respuesta)},
    )


def limpiar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()
