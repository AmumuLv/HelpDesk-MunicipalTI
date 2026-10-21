"""Datos de demostracion. Se cargan SOLO con el comando explicito:

    docker compose exec api python -m app.scripts.demo

Todo lo que crea queda marcado con ``demo: True`` y puede eliminarse con
``eliminar_demo()``. Nunca se mezclan datos de ejemplo con datos reales.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from bson import ObjectId

from app.core.audit import registrar
from app.core.db import get_db
from app.core.errors import Conflicto, Validacion
from app.core.time import local_date, utcnow
from app.domain.constants import (
    ESTADO_CERRADO,
    ESTADO_EN_PROGRESO,
    ESTADO_NUEVO,
    ORIGEN_ADMIN,
    ORIGEN_TECNICO,
    ORIGEN_USUARIO,
    ORIGEN_USUARIO_TERCERO,
)
from app.domain.schemas_db import CONTADOR_TICKETS
from app.services import (
    campana_service,
    horario_service,
    inventario_service,
    kb_service,
    org_service,
    ticket_service,
    usuario_service,
)

ZONAS_DEMO = [
    {
        "nombre": "Zona Complejo",
        "descripcion": "Edificios del complejo municipal (demostracion)",
        "oficinas": [
            {"nombre": "COMUNA", "usuarios": 6},
            {"nombre": "ATM", "usuarios": 5},
        ],
    },
    {
        "nombre": "Zona Mercado",
        "descripcion": "Oficinas del mercado (demostracion)",
        "oficinas": [{"nombre": "ARCHIVO GENERAL", "usuarios": 4}],
    },
]

NOMBRES = [
    "Ana Quispe Mamani", "Luis Ramirez Torres", "Carmen Rojas Huaman", "Jorge Castillo Vera",
    "Rosa Gutierrez Ayala", "Pedro Sanchez Ruiz", "Maria Lopez Vargas", "Carlos Mendoza Paz",
    "Sofia Reyes Ccahuana", "Miguel Arana Flores", "Elena Tito Condori", "Diego Huaman Perez",
    "Patricia Chiroque", "Fernando Norena", "Gloria Winar", "Ricardo Banos",
]

CARGO_ADMIN = "Jefe de soporte"
CARGO_TECNICO = "Tecnico de soporte"
CARGO_USUARIO = "Trabajador municipal"

TECNICOS_DEMO = [
    ("Luis Ramirez Torres", "luis.ramirez@municipalidad.gob.pe", [1, 2, 3, 4, 5]),
    ("Carmen Rojas Huaman", "carmen.rojas@municipalidad.gob.pe", [1, 2, 3, 4]),
    ("Jorge Castillo Vera", "jorge.castillo@municipalidad.gob.pe", [2, 3, 4, 5, 6]),
    ("Rosa Gutierrez Ayala", "rosa.gutierrez@municipalidad.gob.pe", [1, 2, 3, 4, 5]),
]

EQUIPOS_POR_OFICINA = {
    "COMUNA": [
        ("COMPUTADORA N°1", ["MONITOR", "TECLADO", "MOUSE", "CPU"]),
        ("COMPUTADORA N°2", ["MONITOR", "TECLADO", "MOUSE", "CPU"]),
        ("IMPRESORA N°1", ["IMPRESORA"]),
        ("LAPTOP N°1", ["LAPTOP"]),
    ],
    "ATM": [
        ("COMPUTADORA N°1", ["MONITOR", "TECLADO", "MOUSE", "CPU"]),
        ("COMPUTADORA N°2", ["MONITOR", "TECLADO", "MOUSE", "CPU"]),
        ("IMPRESORA N°1", ["IMPRESORA"]),
        ("LAPTOP N°1", ["LAPTOP"]),
        ("ROUTER N°1", ["ROUTER"]),
    ],
    "ARCHIVO GENERAL": [
        ("COMPUTADORA N°1", ["MONITOR", "TECLADO", "MOUSE", "CPU"]),
        ("IMPRESORA N°1", ["IMPRESORA"]),
        ("IMPRESORA N°2", ["IMPRESORA"]),
        ("LAPTOP N°1", ["LAPTOP"]),
    ],
}

PROBLEMAS_DEMO = [
    ("No enciende", "La computadora no prende cuando la enciendo.", "no_puedo_trabajar", "Hardware"),
    ("Internet/red", "No me conecta el internet en la oficina.", "me_frena", "Internet / Red"),
    ("Impresora", "La impresora no imprime, se queda con luz roja.", "me_frena", "Impresora"),
    ("Sistema/programa", "El programa de planillas no abre, sale un error.", "me_frena", "Sistema / Programa"),
    ("Correo/cuenta", "No puedo entrar a mi correo, dice contrasena incorrecta.", "no_puedo_trabajar", "Correo / Cuenta"),
    ("Equipo lento", "El equipo esta muy lento, tarda mucho en abrir todo.", "puede_esperar", "Equipo lento"),
]

ARTICULOS_KB = [
    {
        "titulo": "La computadora no enciende",
        "categoria": "No enciende",
        "resumen": "Pasos sencillos cuando el equipo no prende, y cuando conviene avisar al soporte.",
        "cuerpo": "Revisa estos puntos antes de llamar al soporte. Si el problema sigue, envia un reporte.",
        "pasos": [
            "Revisa que el cable de corriente este bien conectado y que la luz del equipo se encienda.",
            "Si es una laptop, conecta su cargador y comprueba que el indicador de carga se encienda.",
            "Prueba otro enchufe: a veces el tomacorriente tiene la salida daniada.",
            "Si escuchas ventiladores pero no hay imagen, desconecta el monitor y revisa el cable de video.",
            "Si nada de esto funciona, reporta el problema indicando que el equipo no enciende.",
        ],
        "etiquetas": ["no enciende", "apagado", "power", "hardware"],
    },
    {
        "titulo": "El internet no funciona",
        "categoria": "Internet / Red",
        "resumen": "Como recuperar la conexion y cuando el problema es del cable de red.",
        "cuerpo": "Estos pasos resuelven la mayoria de los cortes de conexion.",
        "pasos": [
            "Apaga y enciende el router (el equipo de red) esperando 30 segundos.",
            "Revisa que el cable de red este bien conectado a la computadora.",
            "Si usas wifi, acercate al router o reinicia la computadora.",
            "Si el indicador del router parpadea en rojo o no enciende, reporta el problema.",
        ],
        "etiquetas": ["internet", "wifi", "red", "router"],
    },
    {
        "titulo": "La impresora no imprime",
        "categoria": "Impresora",
        "resumen": "Que revisar cuando la impresora no imprime, no tiene papel o muestra luces de error.",
        "cuerpo": "Revisa la impresora antes de reportar.",
        "pasos": [
            "Revisa que tenga papel y que la bandeja este cerrada.",
            "Abre la tapa y retira cualquier hoja atorada.",
            "Si muestra luz roja, apaga la impresora 30 segundos y vuelve a encenderla.",
            "Verifica que la computadora tenga seleccionada esa impresora.",
        ],
        "etiquetas": ["impresora", "papel", "toner", "imprimir"],
    },
    {
        "titulo": "Solicitar acceso a un sistema o carpeta",
        "categoria": "Accesos y permisos",
        "resumen": "Como pedir permisos para un sistema, correo compartido o carpeta de la institucion.",
        "cuerpo": "Indica exactamente a que necesitas acceso y quien lo autoriza.",
        "pasos": [
            "Escribe el nombre exacto del sistema o carpeta que necesitas.",
            "Indica quien en tu oficina autoriza el acceso.",
            "Envia el reporte y el soporte te respondera con el tiempo estimado.",
        ],
        "etiquetas": ["permisos", "acceso", "carpeta", "sistema"],
    },
]


async def hay_demo() -> bool:
    return await get_db()["usuarios"].count_documents({"demo": True}) > 0


async def _limpiar_huerfanos() -> None:
    """Borra zonas y oficinas de demostracion que una version anterior dejo sin marcar.

    Sin la marca `demo` el comando `eliminar` no las alcanzaba, de modo que la
    carga siguiente fallaba con «Ya existe una zona llamada ...». Solo toca
    nombres que define esta misma demo y oficinas sin usuarios.
    """
    db = get_db()
    zonas_demo = [zona["nombre"] for zona in ZONAS_DEMO]
    oficinas_demo = [oficina["nombre"] for zona in ZONAS_DEMO for oficina in zona["oficinas"]]
    await db["oficinas"].delete_many({"nombre": {"$in": oficinas_demo}, "demo": {"$ne": True}, "usuarios": 0})
    await db["zonas"].delete_many({"nombre": {"$in": zonas_demo}, "demo": {"$ne": True}})
    # Campañas antiguas que quedaron sin marcar: sus items son huerfanos
    campanas_huerfanas = [
        campana["_id"] async for campana in db["campanas_inventario"].find({"demo": {"$ne": True}}, {"_id": 1})
    ]
    if campanas_huerfanas:
        await db["campana_items"].delete_many({"campana_id": {"$in": campanas_huerfanas}})
        await db["inventario_versiones"].delete_many({"campana_id": {"$in": campanas_huerfanas}})
        await db["campanas_inventario"].delete_many({"_id": {"$in": campanas_huerfanas}})
    await db["campanas_inventario"].update_many({"anio": {"$gte": local_date().year - 1}}, {"$set": {"demo": True}})
    await db["inventario_versiones"].update_many(
        {"anio": {"$gte": local_date().year - 1}}, {"$set": {"demo": True}}
    )


async def cargar() -> dict[str, Any]:
    """Crea zonas, oficinas, usuarios, inventario, tickets y articulos de ejemplo."""
    if await hay_demo():
        raise Conflicto("Ya existen datos de demostracion. Eliminalos antes de volver a cargar.")
    await _limpiar_huerfanos()
    db = get_db()
    sistema = {"nombre": "Cargador de demostracion", "rol": "sistema", "_id": None}
    creado: dict[str, Any] = {
        "zonas": 0,
        "oficinas": 0,
        "usuarios": 0,
        "activos": 0,
        "tickets": 0,
        "articulos": 0,
        "campanas": 0,
        "ausencias": 0,
        "vistas_guardadas": 0,
        "notificaciones": 0,
    }

    # ── Zonas y oficinas ──
    mapa_oficinas: dict[str, ObjectId] = {}
    mapa_zonas: dict[str, ObjectId] = {}
    for zona_info in ZONAS_DEMO:
        zona_id = await org_service.crear_zona(
            {"nombre": zona_info["nombre"], "descripcion": zona_info["descripcion"]}, usuario=sistema
        )
        # Sin esta marca la zona sobrevive a `demo eliminar` y la segunda carga falla
        await db["zonas"].update_one({"_id": zona_id}, {"$set": {"demo": True}})
        creado["zonas"] += 1
        mapa_zonas[zona_info["nombre"]] = zona_id
        for oficina_info in zona_info["oficinas"]:
            oficina_id = await org_service.crear_oficina(
                {"nombre": oficina_info["nombre"], "zona_id": zona_id}, usuario=sistema
            )
            await db["oficinas"].update_one({"_id": oficina_id}, {"$set": {"demo": True}})
            creado["oficinas"] += 1
            mapa_oficinas[oficina_info["nombre"]] = oficina_id

    # ── Administrador y tecnicos ──
    admin = await usuario_service.crear(
        {
            "nombre": "Administrador Demo",
            "email": "admin@demo.local",
            "password": "Demo12345",
            "rol": "administrador",
            "cargo": CARGO_ADMIN,
        },
        usuario=sistema,
        es_primer_admin=True,
    )
    await db["usuarios"].update_one({"_id": admin["_id"]}, {"$set": {"demo": True, "debe_cambiar_password": False}})
    creado["usuarios"] += 1

    tecnicos: list[ObjectId] = []
    for indice, (nombre, correo, dias) in enumerate(TECNICOS_DEMO):
        zona_id = list(mapa_zonas.values())[indice % len(mapa_zonas)]
        oficina_id = list(mapa_oficinas.values())[indice % len(mapa_oficinas)]
        persona = await usuario_service.crear(
            {
                "nombre": nombre,
                "email": correo,
                "password": "Demo12345",
                "rol": "tecnico",
                "cargo": CARGO_TECNICO,
                "oficina_id": oficina_id,
            },
            usuario=sistema,
        )
        await db["usuarios"].update_one({"_id": persona["_id"]}, {"$set": {"demo": True}})
        await db["tecnicos_perfil"].update_one(
            {"usuario_id": persona["_id"]},
            {
                "$set": {
                    "especialidades": ["Hardware", "Red"] if indice % 2 == 0 else ["Impresoras", "Sistemas"],
                    "categorias": ["Hardware", "No enciende", "Impresora", "Internet / Red", "Sistema / Programa"],
                    "capacidad_diaria": 8 + indice,
                    "horario": {
                        "dias": {
                            str(dia): {"tramos": [{"entrada": "08:00", "salida": "13:00"}, {"entrada": "15:00", "salida": "18:00"}], "libre": dia not in dias}
                            for dia in range(7)
                        }
                    },
                }
            },
        )
        tecnicos.append(persona["_id"])
        creado["usuarios"] += 1

    # Ausencia de ejemplo para que se vea el estado "Ausente"
    await db["ausencias"].insert_one(
        {
            "tecnico_id": tecnicos[1],
            "tipo": "Vacaciones",
            "inicio": (local_date() - timedelta(days=1)).isoformat(),
            "fin": (local_date() + timedelta(days=3)).isoformat(),
            "motivo": "Datos de demostracion",
            "creado_por": "Cargador de demostracion",
            "creado_en": utcnow(),
            "demo": True,
        }
    )

    # ── Usuarios finales ──
    usuarios_por_oficina: dict[str, list[ObjectId]] = {}
    indice_nombre = 0
    for zona_nombre, zona_info in ((z["nombre"], z) for z in ZONAS_DEMO):
        for oficina_info in zona_info["oficinas"]:
            nombre_oficina = oficina_info["nombre"]
            lista: list[ObjectId] = []
            for _ in range(oficina_info["usuarios"]):
                nombre = NOMBRES[indice_nombre % len(NOMBRES)]
                indice_nombre += 1
                correo = f"usuario{indice_nombre}@demo.local"
                persona = await usuario_service.crear(
                    {
                        "nombre": nombre,
                        "email": correo,
                        "password": "Demo12345",
                        "rol": "usuario",
                        "cargo": CARGO_USUARIO,
                        "oficina_id": mapa_oficinas[nombre_oficina],
                    },
                    usuario=sistema,
                )
                await db["usuarios"].update_one({"_id": persona["_id"]}, {"$set": {"demo": True}})
                lista.append(persona["_id"])
                creado["usuarios"] += 1
            usuarios_por_oficina[nombre_oficina] = lista

    # ── Inventario ──
    from app.services import catalogo_service

    tipos = {t.lower(): t for t in await catalogo_service.tipos_existentes()}
    for nombre_oficina, equipos in EQUIPOS_POR_OFICINA.items():
        oficina_id = mapa_oficinas[nombre_oficina]
        responsables = usuarios_por_oficina.get(nombre_oficina) or []
        for indice_equipo, (nombre_equipo, componentes) in enumerate(equipos):
            responsable_id = responsables[indice_equipo % len(responsables)] if responsables and indice_equipo % 2 == 0 else None
            es_escritorio = 'CPU' in componentes
            conjunto = await inventario_service.crear_conjunto(
                {
                    "nombre": nombre_equipo,
                    "oficina_id": oficina_id,
                    "uso_comun": indice_equipo % 2 == 1,
                    "responsable_id": responsable_id,
                    "estado": "Operativo",
                },
                usuario=sistema,
            ) if es_escritorio else None
            for indice_componente, dispositivo in enumerate(componentes):
                tipo = tipos.get(dispositivo.lower(), dispositivo)
                datos: dict[str, Any] = {
                    "tipo": tipo,
                    "oficina_id": oficina_id,
                    "conjunto_id": conjunto["_id"] if conjunto else None,
                    "responsable_id": responsable_id,
                    "nombre_equipo": nombre_equipo,
                    "estado": "Operativo",
                    "propiedad": "Institucional",
                }
                if tipo in {"CPU", "Laptop"}:
                    datos.update(
                        {
                            "marca": "HP" if indice_componente % 2 == 0 else "Dell",
                            "modelo": "Desktop 400 G7" if tipo == "CPU" else "Latitude 5440",
                            "nombre_equipo": f"{nombre_equipo} - {tipo}",
                            "procesador": "Intel Core i5-12400",
                            "memoria_ram": "8 GB",
                            "almacenamiento": "SSD 240 GB",
                            "direccion_ip": f"192.168.10.{20 + creado['activos']}",
                        }
                    )
                elif tipo == "Monitor":
                    datos.update({"marca": "Samsung", "modelo": "S24R350", "tamano_pantalla": '24"'})
                elif tipo == "Impresora":
                    datos.update({"marca": "HP", "modelo": "LaserJet Pro M404", "direccion_ip": f"192.168.10.{180 + creado['activos']}"})
                activo = await inventario_service.crear_activo(datos, usuario=sistema)
                await db["activos"].update_one({"_id": activo["_id"]}, {"$set": {"demo": True}})
                creado["activos"] += 1

    # Un equipo con detalle avanzado (para ver RAM derivada de modulos)
    cpu = await db["activos"].find_one({"tipo": "CPU", "demo": True, "opciones_avanzadas": {"$ne": True}})
    if cpu:
        await inventario_service.actualizar_activo(
            cpu["_id"],
            {
                "opciones_avanzadas": True,
                "detalle_avanzado": {
                    "placa_madre": {"marca": "HP", "modelo": "Q370", "ranuras_ram_totales": 4, "ram_maxima_soportada": 64},
                    "procesador_detalle": {"modelo": "Intel Core i5-12400", "nucleos": 6, "hilos": 12, "frecuencia": "2.5 GHz"},
                    "memoria_modulos": [
                        {"ranura": "1", "capacidad_gb": 8, "tipo": "DDR4", "velocidad_mhz": 2666, "marca": "Kingston"},
                        {"ranura": "2", "capacidad_gb": 8, "tipo": "DDR4", "velocidad_mhz": 2666, "marca": "Kingston"},
                    ],
                    "almacenamiento_unidades": [{"tipo": "SSD", "capacidad_gb": 240, "marca": "Kingston", "interfaz": "SATA"}],
                    "compra_garantia": {"fecha_compra": "2023-05-10", "proveedor": "Proveedor demo", "vencimiento_garantia": "2026-05-10"},
                    "sistema_operativo": {"sistema": "Windows", "version": "11 Pro", "arquitectura": "64 bits"},
                },
            },
            usuario=sistema,
        )
    # Un equipo con campos marcados como "No aplica"
    teclado = await db["activos"].find_one({"tipo": "Teclado", "demo": True})
    if teclado:
        await inventario_service.marcar_campos(
            [teclado["_id"]],
            ["codigo_patrimonial", "direccion_ip", "direccion_mac"],
            "no_aplica",
            usuario=sistema,
            motivo="Este equipo no tiene ni tendra ese dato",
        )

    # ── Tickets ──
    ticket_ids = await _crear_tickets_demo(sistema, db, usuarios_por_oficina, tecnicos, admin)

    # ── Inventario anual: una campaña abierta con verificación pendiente ──
    creado["campanas"] = await _crear_campana_demo(sistema, db)

    # ── Ausencias del equipo TI ──
    creado["ausencias"] = await _crear_ausencias_demo(sistema, db, tecnicos)

    # ── Notas internas, para que el detalle de ticket tenga historial propio ──
    creado["notas_internas"] = await _crear_notas_demo(db, admin, ticket_ids)

    # ── Respuestas rápidas y feriados: catálogos que la configuración espera ──
    creado["respuestas_rapidas"] = await _crear_respuestas_rapidas_demo()
    creado["feriados"] = await _crear_feriados_demo(db)

    # ── Vistas guardadas de la bandeja ──
    creado["vistas_guardadas"] = await _crear_vistas_demo(db, admin)

    # ── Notificaciones de la campana ──
    creado["notificaciones"] = await _crear_notificaciones_demo(db, admin, tecnicos, ticket_ids)

    # ── Base de conocimiento ──
    for articulo in ARTICULOS_KB:
        await kb_service.crear(articulo, usuario=sistema)
        creado["articulos"] += 1

    await db["configuracion"].update_one(
        {"_id": "config"},
        {"$set": {"sistema.datos_demo": True, "sistema.demo_creado_en": utcnow()}},
        upsert=True,
    )
    await registrar(
        "demo.cargar",
        usuario_nombre="Cargador de demostracion",
        rol="sistema",
        entidad="sistema",
        resumen="Datos de demostracion cargados",
        despues=creado,
    )
    return {
        **creado,
        "credenciales_demo": {
            "administrador": {"correo": "admin@demo.local", "password": "Demo12345"},
            "tecnicos": [{"correo": correo, "password": "Demo12345"} for _, correo, _ in TECNICOS_DEMO],
            "usuarios": "usuario1@demo.local / Demo12345 (el resto sigue el mismo patron)",
        },
        "aviso": "Estos datos son de DEMOSTRACION. Eliminarlos con app.scripts.demo eliminar.",
    }


async def _crear_tickets_demo(
    sistema: dict[str, Any],
    db,
    usuarios_por_oficina: dict[str, list[ObjectId]],
    tecnicos: list[ObjectId],
    admin: dict[str, Any],
) -> list[ObjectId]:
    """Genera tickets historicos para que la analitica tenga datos reales de demostracion."""
    from app.core.ids import codigo_ticket
    from app.services import sla_service

    total = 0
    usuarios_planos = [u for lista in usuarios_por_oficina.values() for u in lista]
    activos = await (db["activos"].find({"demo": True}).to_list(None))
    if not activos or not usuarios_planos:
        return []
    ids: list[ObjectId] = []
    anio = local_date().year
    hoy = local_date()
    for indice in range(46):
        dias_atras = (indice * 3) % 75
        fecha = utcnow() - timedelta(days=dias_atras, hours=indice % 7)
        tipo_problema, descripcion, urgencia, categoria = PROBLEMAS_DEMO[indice % len(PROBLEMAS_DEMO)]
        afectado_id = usuarios_planos[indice % len(usuarios_planos)]
        afectado = await db["usuarios"].find_one({"_id": afectado_id}) or {}
        reportante_id = afectado_id
        origen = ORIGEN_USUARIO if indice % 3 else ORIGEN_USUARIO_TERCERO
        activo = activos[indice % len(activos)]
        estado = (
            ESTADO_CERRADO
            if dias_atras > 12
            else (ESTADO_EN_PROGRESO if indice % 3 == 0 else ESTADO_NUEVO)
        )
        prioridad = "alta" if urgencia == "no_puedo_trabajar" else ("media" if urgencia == "me_frena" else "baja")
        if indice % 11 == 0:
            prioridad = "critica"
        minutos = 45 + (indice * 37) % 400
        documento: dict[str, Any] = {
            "codigo": codigo_ticket(anio, indice + 1),
            "asunto": descripcion[:120],
            "descripcion": descripcion,
            "tipo_problema": tipo_problema,
            "estado": estado,
            "prioridad": prioridad,
            "urgencia": urgencia,
            "origen": origen,
            "conversacion_id": ObjectId(),
            "reportante_id": reportante_id,
            "reportante_nombre": afectado.get("nombre"),
            "afectado_id": afectado_id,
            "afectado_nombre": afectado.get("nombre"),
            "solicitante_no_registrado": None,
            "zona_id": activo.get("zona_id"),
            "zona_nombre": activo.get("zona_nombre"),
            "oficina_id": activo.get("oficina_id"),
            "oficina_nombre": activo.get("oficina_nombre"),
            "activo_id": activo["_id"],
            "activo_nombre": activo.get("nombre_equipo") or activo.get("tipo"),
            "conjunto_id": activo.get("conjunto_id"),
            "conjunto_nombre": activo.get("conjunto_nombre"),
            "tecnico_id": tecnicos[indice % len(tecnicos)],
            "tecnico_nombre": (await db["usuarios"].find_one({"_id": tecnicos[indice % len(tecnicos)]}, {"nombre": 1})).get("nombre"),
            "categoria": categoria,
            "veces_reabierto": 1 if indice % 13 == 0 else 0,
            "satisfaccion": (4 + indice % 2) if estado == ESTADO_CERRADO and indice % 3 else None,
            "demo": True,
            "creado_en": fecha,
            "actualizado_en": fecha + timedelta(hours=minutos // 60 or 1),
        }
        documento.update(await sla_service.calcular_deadlines(prioridad, fecha))
        if estado == ESTADO_CERRADO:
            documento["resuelto_en"] = fecha + timedelta(minutes=minutos)
            documento["cerrado_en"] = fecha + timedelta(minutes=minutos)
            documento["tiempo_resolucion_min"] = float(minutos)
            documento["nota_resolucion"] = f"Se resolvio el problema de {categoria.lower()} y se verifico con la persona afectada."
            documento["sla_incumplido"] = bool(indice % 7 == 0)
        else:
            documento["sla_incumplido"] = bool(indice % 5 == 0)
        resultado = await db["tickets"].insert_one(documento)
        documento["_id"] = resultado.inserted_id
        await db["ticket_eventos"].insert_one(
            {
                "ticket_id": documento["_id"],
                "tipo": "creado",
                "fecha": fecha,
                "actor": {"id": reportante_id, "nombre": afectado.get("nombre"), "rol": "usuario"},
                "resumen": "Ticket reportado (demostracion)",
                "detalle": {},
                "visible_usuario": True,
                "origen_ia": False,
                "demo": True,
            }
        )
        if estado == ESTADO_CERRADO:
            await db["ticket_mensajes"].insert_one(
                {
                    "ticket_id": documento["_id"],
                    "conversacion_id": documento["conversacion_id"],
                    "autor_id": documento["tecnico_id"],
                    "autor_nombre": documento["tecnico_nombre"],
                    "autor_rol": "tecnico",
                    "cuerpo": "Revisamos el equipo y quedó funcionando correctamente. Quedamos atentos.",
                    "adjuntos": [],
                    "leido_por_tecnico": True,
                    "creado_en": fecha + timedelta(minutes=max(minutos - 15, 5)),
                    "es_ia": False,
                    "demo": True,
                }
            )
        await db["activos"].update_one({"_id": activo["_id"]}, {"$inc": {"reportes": 1}})
        total += 1
        ids.append(resultado.inserted_id)
    await db["contadores"].update_one(
        {"clave": f"{CONTADOR_TICKETS}:{anio}"}, {"$set": {"valor": total + 1}}, upsert=True
    )
    # Dos tickets registrados por el equipo TI (sin chat) para ver la diferencia
    for indice, tipo in enumerate([("tecnico", ORIGEN_TECNICO), ("admin", ORIGEN_ADMIN)]):
        afectado = await db["usuarios"].find_one({"_id": usuarios_planos[indice]}) or {}
        activo = activos[indice]
        fecha = utcnow() - timedelta(days=5 + indice)
        documento = {
            "codigo": codigo_ticket(anio, total + 2 + indice),
            "asunto": "Revision detectada en el equipo",
            "descripcion": "Se detecto durante la supervision que el equipo presenta un funcionamiento irregular.",
            "tipo_problema": None,
            "estado": ESTADO_EN_PROGRESO,
            "prioridad": "media",
            "urgencia": None,
            "origen": ORIGEN_TECNICO if tipo == "tecnico" else ORIGEN_ADMIN,
            "conversacion_id": None,
            "reportante_id": admin["_id"],
            "reportante_nombre": admin.get("nombre"),
            "afectado_id": afectado.get("_id"),
            "afectado_nombre": afectado.get("nombre"),
            "solicitante_no_registrado": None,
            "zona_id": activo.get("zona_id"),
            "zona_nombre": activo.get("zona_nombre"),
            "oficina_id": activo.get("oficina_id"),
            "oficina_nombre": activo.get("oficina_nombre"),
            "activo_id": activo["_id"],
            "activo_nombre": activo.get("nombre_equipo") or activo.get("tipo"),
            "conjunto_id": activo.get("conjunto_id"),
            "conjunto_nombre": activo.get("conjunto_nombre"),
            "tecnico_id": tecnicos[indice],
            "tecnico_nombre": (await db["usuarios"].find_one({"_id": tecnicos[indice]}, {"nombre": 1})).get("nombre"),
            "categoria": "Hardware",
            "veces_reabierto": 0,
            "satisfaccion": None,
            "demo": True,
            "creado_en": fecha,
            "actualizado_en": fecha,
        }
        documento.update(await sla_service.calcular_deadlines("media", fecha))
        resultado = await db["tickets"].insert_one(documento)
        await db["ticket_eventos"].insert_one(
            {
                "ticket_id": resultado.inserted_id,
                "tipo": "creado",
                "fecha": fecha,
                "actor": {"id": admin["_id"], "nombre": admin.get("nombre"), "rol": tipo},
                "resumen": "Registrado por el equipo TI (sin chat)",
                "detalle": {"detectado_por_tecnico": True},
                "visible_usuario": True,
                "origen_ia": False,
                "demo": True,
            }
        )
        total += 1
        ids.append(resultado.inserted_id)
    return ids


async def _crear_campana_demo(sistema: dict[str, Any], db) -> int:
    """Campaña de inventario anual abierta, con parte de los equipos ya verificados.

    Sin esto el módulo de inventario anual no tiene nada que mostrar ni con lo
    que probar la verificación física ni la comparación entre años.
    """
    anio = local_date().year
    try:
        campana = await campana_service.crear(
            {
                "nombre": f"Inventario fisico {anio}",
                "anio": anio,
                "alcance": "todas",
                "fecha_inicio": (local_date() - timedelta(days=20)).isoformat(),
                "fecha_fin": (local_date() + timedelta(days=40)).isoformat(),
                "responsables": [],
                "notas": "Campana de demostracion: verificacion fisica de todo el inventario.",
                "generar_qr": True,
            },
            usuario=sistema,
        )
    except Validacion:
        # Ya habia una campaña de ese anio: se reutiliza
        campana = await db["campanas_inventario"].find_one({"anio": anio})
        if not campana:
            return 0
    campana_id = campana["_id"] if isinstance(campana.get("_id"), ObjectId) else ObjectId(campana["id"])
    await db["campanas_inventario"].update_one({"_id": campana_id}, {"$set": {"demo": True, "estado": "abierta"}})

    pendientes = await campana_service.asegurar_pendientes(campana_id)
    await db["campana_items"].update_many({"campana_id": campana_id}, {"$set": {"demo": True}})

    # Una parte ya verificada, para que se vea el avance sin esperar a nadie
    items = (
        await db["campana_items"]
        .find({"campana_id": campana_id, "estado_item": "pendiente"})
        .limit(4)
        .to_list(None)
    )
    for indice, item in enumerate(items):
        await db["campana_items"].update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "estado_item": "verificado",
                    "verificado_por": sistema.get("nombre"),
                    "verificado_en": utcnow(),
                    "observaciones": "Equipo encontrado y etiquetado correctamente." if indice % 2 == 0 else "",
                    "demo": True,
                }
            },
        )
    # Campaña del año anterior ya cerrada: sin ella el histórico de versiones
    # y la comparación entre años no tienen nada que mostrar
    await _crear_campana_anterior_demo(sistema, db, anio)
    return 1 if campana else 0


async def _crear_campana_anterior_demo(sistema: dict[str, Any], db, anio: int) -> int:
    """Campaña del año pasado, cerrada, con su items verificados."""
    if await db["campanas_inventario"].count_documents({"anio": anio - 1}) > 0:
        return 0
    try:
        campana = await campana_service.crear(
            {
                "nombre": f"Inventario fisico {anio - 1}",
                "anio": anio - 1,
                "alcance": "todas",
                "fecha_inicio": f"{anio - 1}-03-01",
                "fecha_fin": f"{anio - 1}-05-31",
                "responsables": [],
                "notas": "Campana cerrada de demostracion.",
                "generar_qr": False,
            },
            usuario=sistema,
        )
    except (Validacion, Conflicto):
        return 0
    campana_id = campana["_id"] if isinstance(campana.get("_id"), ObjectId) else ObjectId(campana["id"])
    await campana_service.asegurar_pendientes(campana_id)
    await db["campana_items"].update_many(
        {"campana_id": campana_id, "estado_item": "pendiente"},
        {
            "$set": {
                "estado_item": "verificado",
                "verificado_por": sistema.get("nombre"),
                "verificado_en": utcnow(),
                "demo": True,
            }
        },
    )
    # El cierre es lo que guarda la version historica consultable: si se
    # marcara el estado a mano, el historico y la comparacion entre anos
    # seguirian vacios aunque la campana existiera
    await campana_service.cerrar(
        campana_id,
        marcar_no_localizados=False,
        nota="Cierre de demostracion",
        usuario={**sistema, "rol": "administrador"},
    )
    await db["campanas_inventario"].update_one({"_id": campana_id}, {"$set": {"demo": True}})
    await db["inventario_versiones"].update_many({"campana_id": campana_id}, {"$set": {"demo": True}})
    return 1


async def _crear_ausencias_demo(sistema: dict[str, Any], db, tecnicos: list[ObjectId]) -> int:
    """Dos ausencias del equipo TI: una futura y otra en curso.

    El panel muestra el estado de cada técnico según horario y ausencias; sin
    ausencias el calendario y los estados nunca ejercitan esa rama.
    """
    total = 0
    hoy = local_date()
    casos = [
        {
            "tecnico_id": tecnicos[0] if tecnicos else None,
            "tipo": "vacaciones",
            "inicio": (hoy + timedelta(days=10)).isoformat(),
            "fin": (hoy + timedelta(days=24)).isoformat(),
            "motivo": "Vacaciones programadas",
        },
        {
            "tecnico_id": tecnicos[1] if len(tecnicos) > 1 else (tecnicos[0] if tecnicos else None),
            "tipo": "capacitacion",
            "inicio": hoy.isoformat(),
            "fin": hoy.isoformat(),
            "motivo": "Capacitacion en seguridad de la informacion",
        },
        {
            "tecnico_id": tecnicos[2 % len(tecnicos)] if tecnicos else None,
            "tipo": "permiso",
            "inicio": (hoy - timedelta(days=3)).isoformat(),
            "fin": (hoy - timedelta(days=1)).isoformat(),
            "motivo": "Permiso por tramite municipal",
        },
    ]
    for caso in casos:
        if not caso["tecnico_id"]:
            continue
        try:
            # El servicio espera fechas como date; la API las convierte al validar
            await horario_service.crear_ausencia(
                {
                    **caso,
                    "inicio": date.fromisoformat(caso["inicio"]),
                    "fin": date.fromisoformat(caso["fin"]),
                },
                usuario=sistema,
            )
        except (Validacion, Conflicto):
            continue
        await db["ausencias"].update_one(
            {"tecnico_id": caso["tecnico_id"], "motivo": caso["motivo"]}, {"$set": {"demo": True}}
        )
        total += 1
    return total


async def _crear_vistas_demo(db, admin: dict[str, Any]) -> int:
    """Vistas guardadas de la bandeja: las que el panel ofrece al abrirse."""
    vistas = [
        {
            "nombre": "Sin asignar",
            "descripcion": "Tickets nuevos que todavia no tienen tecnico",
            "filtros": {"estado": "nuevo", "tecnico_id": ""},
            "sistema": False,
            "orden": 1,
        },
        {
            "nombre": "Criticos y vencidos",
            "descripcion": "Prioridad critica o SLA incumplido",
            "filtros": {"prioridad": "critica", "sla": "incumplido"},
            "sistema": False,
            "orden": 2,
        },
        {
            "nombre": "Zona Complejo",
            "descripcion": "Todo lo reportado en la zona del complejo municipal",
            "filtros": {"zona_id": "", "solo_abiertos": True},
            "sistema": False,
            "orden": 3,
        },
    ]
    total = 0
    # La zona del complejo se resuelve por nombre para que el filtro de la vista sirva
    zona = await db["zonas"].find_one({"nombre": "Zona Complejo"})
    for vista in vistas:
        if await db["vistas_guardadas"].count_documents({"nombre": vista["nombre"]}) > 0:
            continue
        filtros = dict(vista["filtros"])
        if vista["nombre"] == "Zona Complejo" and zona:
            filtros["zona_id"] = str(zona["_id"])
        # Se guardan con la misma forma que usa la API: `creada_por` es el id
        # del autor y `compartida` decide si la ven los demás técnicos
        await db["vistas_guardadas"].insert_one(
            {
                "nombre": vista["nombre"],
                "vista": "",
                "filtros": filtros,
                "columnas": [],
                "compartida": True,
                "creada_por": admin["_id"],
                "creada_por_nombre": admin.get("nombre"),
                "creado_en": utcnow(),
                "demo": True,
            }
        )
        total += 1
    return total


async def _crear_notificaciones_demo(db, admin: dict[str, Any], tecnicos: list[ObjectId], ticket_ids: list[ObjectId]) -> int:
    """Notificaciones de ejemplo para el administrador y los tecnicos.

    La campana de la cabecera muestra el contador de no leidas; sin datos nunca
    se veria ese estado.
    """
    from app.services import notificaciones_service

    total = 0
    tickets = await db["tickets"].find({"demo": True}).limit(3).to_list(None)
    destinos: list[tuple[ObjectId, str]] = [(admin["_id"], "Administrador Demo")]
    for indice, tecnico_id in enumerate(tecnicos[:2]):
        nombre = (await db["usuarios"].find_one({"_id": tecnico_id}, {"nombre": 1})) or {}
        destinos.append((tecnico_id, nombre.get("nombre") or "Tecnico"))

    for ticket in tickets:
        for indice, (destino_id, _) in enumerate(destinos):
            await notificaciones_service.crear(
                destino_id,
                f"Ticket {ticket.get('codigo')} asignado",
                f"{ticket.get('asunto')} fue asignado para atencion.",
                tipo="info",
                enlace=f"/tickets/{ticket['_id']}",
                ticket_id=ticket["_id"],
            )
            total += 1
        break  # basta con un ticket para que haya notificaciones

    await db["notificaciones"].update_many({"demo": True}, {"$set": {"demo": True}})
    # La primera de cada persona queda sin leer: el contador debe verse
    for destino_id, _ in destinos:
        await db["notificaciones"].update_one(
            {"usuario_id": destino_id},
            {"$set": {"leida": False, "demo": True}},
        )
    await db["notificaciones"].update_many({"usuario_id": {"$in": [d[0] for d in destinos]}}, {"$set": {"demo": True}})
    return total


async def _crear_notas_demo(db, admin: dict[str, Any], ticket_ids: list[ObjectId]) -> int:
    """Notas internas en algunos tickets.

    Las notas internas no las ve el usuario: son el canal del equipo TI. Sin
    ellas el detalle nunca muestra esa zona ni su regla de visibilidad.
    """
    if not ticket_ids:
        return 0
    notas = [
        (
            "Se contacto al proveedor del monitor: la unidad de repuesto llega el miercoles.",
            "Llamada registrada con el proveedor",
        ),
        (
            "El usuario tiene Windows 10, que dejo de recibir actualizaciones. Se debe planificar el reemplazo.",
            "Riesgo de seguridad",
        ),
        (
            "Revisar si el caso se puede resolver con cambio de equipo prestrado en lugar de compra.",
            "Posible economia",
        ),
    ]
    total = 0
    # Se anotan los tickets mas recientes: son los que el equipo tiene abiertos
    recientes = await db["tickets"].find({"demo": True}).sort("creado_en", -1).limit(3).to_list(None)
    for indice, ticket in enumerate(recientes):
        cuerpo, motivo = notas[indice % len(notas)]
        if await db["notas_internas"].count_documents({"ticket_id": ticket["_id"]}) > 0:
            continue
        await db["notas_internas"].insert_one(
            {
                "ticket_id": ticket["_id"],
                "autor_id": admin["_id"],
                "autor_nombre": admin.get("nombre"),
                "cuerpo": cuerpo,
                "motivo": motivo,
                "visible_usuario": False,
                "creado_en": utcnow(),
                "demo": True,
            }
        )
        total += 1
    return total


async def _crear_respuestas_rapidas_demo() -> int:
    """Respuestas rápidas de la base de conocimiento.

    Son plantillas que el técnico inserta en el chat sin volver a escribir lo
    mismo: sin ellas el módulo de respuestas rapidas aparece siempre vacio.
    """
    plantillas = [
        ("Como reponer un teclado o mouse", "Hola, para reponer tu teclado o mouse comunicate a soporteti con el codigo de tu ticket."),
        ("Solicitar un equipo nuevo", "Hola, para solicitar un equipo nuevo necesitamos justificar la necesidad y pasar por la oficina de soporte TI."),
        ("Conectarse a la red de la municipalidad", "Hola, para conectarte a la red institucional usa el portal de captacion con tu codigo de servidor."),
        ("Acceso al sistema de Tramites", "Tu usuario es el mismo correo institucional. Si pide cambio de contrasena, seguimos el procedimiento de la entidad."),
    ]
    db = get_db()
    total = 0
    for titulo, cuerpo in plantillas:
        if await db["respuestas_rapidas"].count_documents({"titulo": titulo}) > 0:
            continue
        await db["respuestas_rapidas"].insert_one(
            {
                "titulo": titulo,
                "cuerpo": cuerpo,
                "categoria": "Atencion al usuario",
                "activo": True,
                "orden": total + 1,
                "creado_en": utcnow(),
                "demo": True,
            }
        )
        total += 1
    return total


async def _crear_feriados_demo(db) -> int:
    """Feriados del ano: sin ellos el calendario de TI no tiene dias libres fijos."""
    anio = local_date().year
    casos = [
        (date(anio, 1, 1), "Anio Nuevo", "nacional"),
        (date(anio, 5, 1), "Dia del Trabajo", "nacional"),
        (date(anio, 6, 29), "San Pedro y San Pablo", "municipal"),
        (date(anio, 12, 25), "Navidad", "nacional"),
    ]
    total = 0
    for fecha, nombre, tipo in casos:
        if await db["feriados"].count_documents({"fecha": fecha.isoformat(), "nombre": nombre}) > 0:
            continue
        await db["feriados"].insert_one(
            {"fecha": fecha.isoformat(), "nombre": nombre, "tipo": tipo, "creado_en": utcnow(), "demo": True}
        )
        total += 1
    return total


async def eliminar() -> dict[str, Any]:
    """Elimina todo lo marcado como demo. No toca datos reales."""
    if not await hay_demo():
        return {"mensaje": "No hay datos de demostracion cargados."}
    db = get_db()
    ticket_ids = [t["_id"] async for t in db["tickets"].find({"demo": True}, {"_id": 1})]
    activo_ids = [a["_id"] async for a in db["activos"].find({"demo": True}, {"_id": 1})]
    usuario_ids = [u["_id"] async for u in db["usuarios"].find({"demo": True}, {"_id": 1})]
    await db["ticket_mensajes"].delete_many({"ticket_id": {"$in": ticket_ids}})
    await db["ticket_eventos"].delete_many({"ticket_id": {"$in": ticket_ids}})
    await db["notas_internas"].delete_many({"ticket_id": {"$in": ticket_ids}})
    await db["adjuntos"].delete_many({"ticket_id": {"$in": ticket_ids}})
    await db["tickets"].delete_many({"demo": True})
    await db["activos"].delete_many({"demo": True})
    await db["conjuntos"].delete_many({"demo": True})
    await db["historial_responsables"].delete_many({"demo": True})
    await db["notificaciones"].delete_many({"usuario_id": {"$in": usuario_ids}})
    await db["sesiones"].delete_many({"usuario_id": {"$in": usuario_ids}})
    await db["ausencias"].delete_many({"demo": True})
    await db["tecnicos_perfil"].delete_many({"usuario_id": {"$in": usuario_ids}})
    await db["usuarios"].delete_many({"demo": True})
    await db["articulos_kb"].delete_many({"demo": True})
    await db["campana_items"].delete_many({"demo": True})
    await db["inventario_versiones"].delete_many({"demo": True})
    await db["campanas_inventario"].delete_many({"demo": True})
    await db["vistas_guardadas"].delete_many({"demo": True})
    await db["respuestas_rapidas"].delete_many({"demo": True})
    await db["feriados"].delete_many({"demo": True})
    await db["oficinas"].delete_many({"demo": True})
    await db["zonas"].delete_many({"demo": True})
    await db["configuracion"].update_one({"_id": "config"}, {"$unset": {"sistema.datos_demo": "", "sistema.demo_creado_en": ""}})
    await _limpiar_huerfanos()
    await registrar(
        "demo.cargar",
        usuario_nombre="Cargador de demostracion",
        rol="sistema",
        entidad="sistema",
        resultado="revertido",
        resumen="Datos de demostracion eliminados",
        despues={"tickets": len(ticket_ids), "activos": len(activo_ids), "usuarios": len(usuario_ids)},
    )
    return {
        "mensaje": "Datos de demostracion eliminados.",
        "tickets": len(ticket_ids),
        "activos": len(activo_ids),
        "usuarios": len(usuario_ids),
    }
