"""Constantes de dominio: estados, prioridades, catalogos y esquemas por tipo.

Todo lo que la administracion puede cambiar despues vive en la coleccion
``catalogos``. Aqui solo estan los valores iniciales que se siembran en el primer
arranque y las listas cerradas que el negocio si necesita (estados de ticket,
prioridades, roles).
"""

from __future__ import annotations

# ── Roles ────────────────────────────────────────────────────
ROL_USUARIO = "usuario"
ROL_TECNICO = "tecnico"
ROL_ADMIN = "administrador"
ROLES = (ROL_USUARIO, ROL_TECNICO, ROL_ADMIN)

# ── Estados de ticket (regla institucional, no editable) ─────
ESTADO_NUEVO = "nuevo"
ESTADO_EN_PROGRESO = "en_progreso"
ESTADO_EN_ESPERA = "en_espera"
ESTADO_CERRADO = "cerrado"
# Existió hasta la versión 4. Un ticket ya concluido quedaba en «resuelto» a la
# espera de que alguien lo cerrara, y cerrar era un paso aparte. En una mesa de
# ayuda municipal no hay nadie esperando ese segundo paso: el técnico termina y
# el caso se archiva. Se conserva la constante solo para la migración que recoge
# los tickets que quedaran en ese estado; no forma parte del catálogo.
ESTADO_RESUELTO_LEGADO = "resuelto"
# Existió hasta la versión 5. Separaba «ya tiene técnico» de «el técnico lo está
# tocando», y resultó inútil en la práctica: asignar un ticket lo dejaba en
# «asignado» y pasar a «en progreso» exigía un segundo clic que nadie daba. Los
# tickets se quedaban ahí: 13 de 14 abiertos estaban en «asignado» y ni uno en
# «en progreso». Ninguna pantalla informaba de la diferencia —el contador que la
# medía no se mostraba en ninguna parte—, así que eran dos palabras para decir lo
# mismo. Se conserva la constante solo para la migración que recoge los que
# quedaran; no forma parte del catálogo.
ESTADO_ASIGNADO_LEGADO = "asignado"

ESTADOS_TICKET = (
    ESTADO_NUEVO,
    ESTADO_EN_PROGRESO,
    ESTADO_EN_ESPERA,
    ESTADO_CERRADO,
)
ESTADOS_ABIERTOS = (ESTADO_NUEVO, ESTADO_EN_PROGRESO, ESTADO_EN_ESPERA)
# Compatibilidad de lectura: los antiguos «resueltos» también están finalizados.
ESTADOS_CERRADOS = (ESTADO_CERRADO, ESTADO_RESUELTO_LEGADO)
# Transiciones permitidas (el backend las valida)
#
# De un estado abierto se va a «cerrado» directamente: se escribe la solución y
# se archiva en el mismo paso, sin un estado intermedio de espera. Cerrado sigue
# siendo reabrible, como antes, para cuando la solución no sirva.
#
# Asignar un técnico NO es un estado: es lo que hace que un «nuevo» pase
# directamente a «en progreso», en el mismo paso. Por eso no hay un estado
# «asignado» al que volver, y «nuevo» sigue siendo la forma de devolver un caso
# a la cola sin técnico.
TRANSICIONES = {
    ESTADO_NUEVO: {ESTADO_EN_PROGRESO, ESTADO_EN_ESPERA, ESTADO_CERRADO},
    ESTADO_EN_PROGRESO: {ESTADO_EN_ESPERA, ESTADO_CERRADO, ESTADO_NUEVO},
    ESTADO_EN_ESPERA: {ESTADO_EN_PROGRESO, ESTADO_CERRADO, ESTADO_NUEVO},
    ESTADO_CERRADO: {ESTADO_EN_PROGRESO},  # solo reapertura autorizada
}

# ── Prioridades ──────────────────────────────────────────────
PRIORIDAD_BAJA = "baja"
PRIORIDAD_MEDIA = "media"
PRIORIDAD_ALTA = "alta"
PRIORIDAD_CRITICA = "critica"
PRIORIDADES = (PRIORIDAD_BAJA, PRIORIDAD_MEDIA, PRIORIDAD_ALTA, PRIORIDAD_CRITICA)
PESO_PRIORIDAD = {PRIORIDAD_BAJA: 1, PRIORIDAD_MEDIA: 2, PRIORIDAD_ALTA: 3, PRIORIDAD_CRITICA: 4}
# Urgencia percibida por el usuario -> prioridad sugerida
URGENCIA_A_PRIORIDAD = {
    "puede_esperar": PRIORIDAD_BAJA,
    "me_frena": PRIORIDAD_MEDIA,
    "no_puedo_trabajar": PRIORIDAD_ALTA,
}

# ── Origen del ticket ────────────────────────────────────────
ORIGEN_USUARIO = "usuario"
ORIGEN_USUARIO_TERCERO = "usuario_por_companero"
ORIGEN_TECNICO = "tecnico"
ORIGEN_ADMIN = "administrador"
ORIGEN_AUTOMATICO = "automatico"
ORIGENES_TICKET = (
    ORIGEN_USUARIO,
    ORIGEN_USUARIO_TERCERO,
    ORIGEN_TECNICO,
    ORIGEN_ADMIN,
    ORIGEN_AUTOMATICO,
)
# Solo estos orígenes tienen chat entre usuario y TI (validado en el backend)
ORIGENES_CON_CHAT = (ORIGEN_USUARIO, ORIGEN_USUARIO_TERCERO)

# ── Estado de un campo de inventario ────────────────────────
CAMPO_PENDIENTE = "pendiente"
CAMPO_NO_APLICA = "no_aplica"
CAMPO_NO_DISPONIBLE = "no_disponible"
ESTADOS_CAMPO = (CAMPO_PENDIENTE, CAMPO_NO_APLICA, CAMPO_NO_DISPONIBLE)
MOTIVOS_ESTADO_CAMPO = {
    CAMPO_NO_APLICA: [
        "No aplica a este equipo",
        "Este equipo no tiene ni tendra ese dato",
        "No aplica a este tipo de equipo",
    ],
    CAMPO_NO_DISPONIBLE: [
        "Equipo en desuso",
        "Informacion no disponible",
        "No se pudo averiguar",
        "Documentacion perdida",
    ],
}

# ── Campos base de un activo ─────────────────────────────────
CAMPO_CODIGO = "codigo_patrimonial"
CAMPO_MARCA = "marca"
CAMPO_MODELO = "modelo"
CAMPO_TAMANO = "tamano_pantalla"
CAMPO_NOMBRE = "nombre_equipo"
CAMPO_PROCESADOR = "procesador"
CAMPO_RAM = "memoria_ram"
CAMPO_ALMACENAMIENTO = "almacenamiento"
CAMPO_IP = "direccion_ip"
CAMPO_MAC = "direccion_mac"
CAMPO_PROPIEDAD = "propiedad"
CAMPO_ESTADO = "estado"
CAMPO_OBSERVACIONES = "observaciones"

CAMPOS_BASE = (
    CAMPO_CODIGO,
    CAMPO_MARCA,
    CAMPO_MODELO,
    CAMPO_TAMANO,
    CAMPO_NOMBRE,
    CAMPO_PROCESADOR,
    CAMPO_RAM,
    CAMPO_ALMACENAMIENTO,
    CAMPO_IP,
    CAMPO_MAC,
    CAMPO_PROPIEDAD,
    CAMPO_ESTADO,
    CAMPO_OBSERVACIONES,
)
# Campos que pueden tener el estado "No aplica / No disponible"
CAMPOS_CON_ESTADO = CAMPOS_BASE

# ── Esquemas por tipo de dispositivo (valores iniciales) ─────
# "esperados" generan aviso si faltan; "opcionales" nunca avisan.
ESQUEMAS_POR_TIPO: dict[str, dict[str, list[str]]] = {
    "CPU": {
        "esperados": [
            CAMPO_CODIGO,
            CAMPO_MARCA,
            CAMPO_MODELO,
            CAMPO_NOMBRE,
            CAMPO_PROCESADOR,
            CAMPO_RAM,
            CAMPO_ALMACENAMIENTO,
            CAMPO_IP,
            CAMPO_MAC,
            CAMPO_ESTADO,
        ],
        "opcionales": [CAMPO_PROPIEDAD, CAMPO_OBSERVACIONES],
    },
    "Laptop": {
        "esperados": [
            CAMPO_CODIGO,
            CAMPO_MARCA,
            CAMPO_MODELO,
            CAMPO_NOMBRE,
            CAMPO_PROCESADOR,
            CAMPO_RAM,
            CAMPO_ALMACENAMIENTO,
            CAMPO_IP,
            CAMPO_MAC,
            CAMPO_ESTADO,
        ],
        "opcionales": [CAMPO_TAMANO, CAMPO_PROPIEDAD, CAMPO_OBSERVACIONES],
    },
    "Monitor": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO, CAMPO_TAMANO],
        "opcionales": [CAMPO_NOMBRE, CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
    },
    # Una impresora no tiene pantalla, así que ese campo no aparece en su ficha.
    # Antes figuraba entre los opcionales y el formulario pedía «Tamaño de
    # pantalla» para una impresora. Un esquema por tipo solo sirve si no incluye
    # campos que no aplican: es justo lo que hace que un formulario por tipo
    # parezca un formulario genérico con el nombre cambiado.
    "Impresora": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO],
        "opcionales": [
            CAMPO_NOMBRE,
            CAMPO_IP,
            CAMPO_MAC,
            CAMPO_PROPIEDAD,
            CAMPO_ESTADO,
            CAMPO_OBSERVACIONES,
        ],
    },
    "Teclado": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA],
        "opcionales": [
            CAMPO_MODELO,
            CAMPO_NOMBRE,
            CAMPO_PROPIEDAD,
            CAMPO_ESTADO,
            CAMPO_OBSERVACIONES,
        ],
    },
    "Mouse": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA],
        "opcionales": [
            CAMPO_MODELO,
            CAMPO_NOMBRE,
            CAMPO_PROPIEDAD,
            CAMPO_ESTADO,
            CAMPO_OBSERVACIONES,
        ],
    },
    "Router": {
        "esperados": [CAMPO_MARCA, CAMPO_MODELO],
        "opcionales": [
            CAMPO_CODIGO,
            CAMPO_NOMBRE,
            CAMPO_IP,
            CAMPO_MAC,
            CAMPO_PROPIEDAD,
            CAMPO_ESTADO,
            CAMPO_OBSERVACIONES,
        ],
    },
    # Red: lleva direccion IP y MAC porque es lo que se configura en el equipo.
    "Switch": {
        "esperados": [CAMPO_MARCA, CAMPO_MODELO],
        "opcionales": [
            CAMPO_CODIGO,
            CAMPO_NOMBRE,
            CAMPO_IP,
            CAMPO_MAC,
            CAMPO_PROPIEDAD,
            CAMPO_ESTADO,
            CAMPO_OBSERVACIONES,
        ],
    },
    # Un servidor es una computadora fija en un rack: se registra como CPU.
    "Servidor": {
        "esperados": [
            CAMPO_CODIGO,
            CAMPO_MARCA,
            CAMPO_MODELO,
            CAMPO_NOMBRE,
            CAMPO_PROCESADOR,
            CAMPO_RAM,
            CAMPO_ALMACENAMIENTO,
            CAMPO_IP,
            CAMPO_MAC,
            CAMPO_ESTADO,
        ],
        "opcionales": [CAMPO_PROPIEDAD, CAMPO_OBSERVACIONES],
    },
    # Dispositivos moviles: no hay IP propia en el inventario, solo la MAC.
    "Tablet": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO, CAMPO_NOMBRE],
        "opcionales": [CAMPO_TAMANO, CAMPO_MAC, CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
    },
    "Celular": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO, CAMPO_NOMBRE],
        "opcionales": [CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
    },
    # Perifericos y equipos sin red: solo los datos generales de la plantilla.
    "UPS": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO, CAMPO_NOMBRE],
        "opcionales": [CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
    },
    "Disco duro externo": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO, CAMPO_NOMBRE, CAMPO_ALMACENAMIENTO],
        "opcionales": [CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
    },
    "Sistema de audio": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO, CAMPO_NOMBRE],
        "opcionales": [CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
    },
    "Otro": {
        "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO, CAMPO_NOMBRE],
        "opcionales": [CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
    },
}
# Tipos sin esquema propio: se completan en Configuracion
ESQUEMA_GENERICO = {
    "esperados": [CAMPO_CODIGO, CAMPO_MARCA, CAMPO_MODELO],
    "opcionales": [CAMPO_NOMBRE, CAMPO_IP, CAMPO_MAC, CAMPO_PROPIEDAD, CAMPO_ESTADO, CAMPO_OBSERVACIONES],
}

# ── Opciones avanzadas ───────────────────────────────────────
# Secciones disponibles por tipo (configurables por el administrador)
OPCIONES_AVANZADAS_POR_TIPO: dict[str, list[str]] = {
    "CPU": [
        "placa_madre",
        "procesador_detalle",
        "memoria_modulos",
        "almacenamiento_unidades",
        "fuente_poder",
        "tarjeta_grafica",
        "red",
        "gabinete",
        "sistema_operativo",
        "licencias",
        "compra_garantia",
        "mantenimiento",
    ],
    "Laptop": [
        "placa_madre",
        "procesador_detalle",
        "memoria_modulos",
        "almacenamiento_unidades",
        "bateria",
        "cargador",
        "pantalla",
        "red",
        "sistema_operativo",
        "licencias",
        "compra_garantia",
        "mantenimiento",
    ],
    "Impresora": ["tipo_impresora", "conexion", "consumibles", "contador_paginas"],
    "Monitor": ["resolucion", "puertos"],
    "Servidor": [
        "placa_madre",
        "procesador_detalle",
        "memoria_modulos",
        "almacenamiento_unidades",
        "tarjeta_grafica",
        "red",
        "sistema_operativo",
        "licencias",
        "compra_garantia",
        "mantenimiento",
    ],
    "Router": ["red", "conexion"],
    "Switch": ["red", "conexion", "puertos"],
    "UPS": ["bateria", "compra_garantia", "mantenimiento"],
    "Tablet": ["pantalla", "bateria", "cargador"],
    "Celular": ["bateria", "cargador"],
}
SECCIONES_AVANZADAS = {
    "placa_madre": [
        "marca",
        "modelo",
        "chipset",
        "socket",
        "factor_forma",
        "ranuras_ram_totales",
        "ranuras_ram_ocupadas",
        "ram_maxima_soportada",
        "ranuras_pcie",
        "conectores_m2",
        "conectores_sata",
    ],
    "procesador_detalle": ["modelo", "nucleos", "hilos", "frecuencia"],
    "memoria_modulos": ["modulos"],
    "almacenamiento_unidades": ["unidades"],
    "fuente_poder": ["marca", "potencia_w", "certificacion"],
    "tarjeta_grafica": ["tarjetas"],
    "red": ["tarjetas_red"],
    "gabinete": ["marca", "modelo", "tipo", "refrigeracion"],
    "bateria": ["estado", "ciclos", "capacidad"],
    "cargador": ["presente", "marca", "potencia_w"],
    "pantalla": ["tecnologia", "resolucion", "pulgadas", "tactil"],
    "sistema_operativo": ["sistema", "version", "arquitectura"],
    "licencias": ["licencias"],
    "compra_garantia": ["fecha_compra", "proveedor", "vencimiento_garantia"],
    "mantenimiento": ["ultimo_mantenimiento", "proximo_mantenimiento"],
    "tipo_impresora": ["subtipo", " multifuncion"],
    "conexion": ["tipo"],
    "consumibles": ["consumibles"],
    "contador_paginas": ["contador"],
    "resolucion": ["valor"],
    "puertos": ["puertos"],
}

# ── Catalogos iniciales ──────────────────────────────────────
TIPOS_DISPOSITIVO_INICIALES = [
    "CPU",
    "Laptop",
    "Monitor",
    "Teclado",
    "Mouse",
    "Impresora",
    "Router",
    "Switch",
    "Tablet",
    "Celular",
    "Servidor",
    "UPS",
    "Disco duro externo",
    "Sistema de audio",
    "Otro",
]
ESTADOS_ACTIVO_INICIALES = [
    "Operativo",
    "En reparación",
    "Dado de baja",
    "En almacén",
    "Prestado",
    "No localizado",
]
PROPIEDADES_INICIALES = ["Institucional", "Personal", "Arrendado", "Donado"]
COMPONENTES_CONJUNTO_POR_DEFECTO = ["Monitor", "Teclado", "Mouse", "CPU"]

# ── Sincronismos de Excel ────────────────────────────────────
SINONIMOS_DISPOSITIVO: dict[str, str] = {
    "MAUSE": "Mouse",
    "RATON": "Mouse",
    "MOUSE ": "Mouse",
    "TECLADO": "Teclado",
    "TECLADO ": "Teclado",
    "KEYBOARD": "Teclado",
    "PC": "CPU",
    "CPU ": "CPU",
    "PROCESADOR": "CPU",
    "COMPUTADORA": "CPU",
    "MONITOR ": "Monitor",
    "PANTALLA": "Monitor",
    "IMPRESORA ": "Impresora",
    "IMPRESORA": "Impresora",
    "PRINTER": "Impresora",
    "LAPTOP ": "Laptop",
    "NOTEBOOK": "Laptop",
    "ROUTER ": "Router",
    "IMPRESORA N": "Impresora",
}
# Valores que el Excel usa para decir "no aplica"
VALORES_SIN_DATO = [
    "-",
    "--",
    "N/A",
    "NA",
    "S/N",
    "SN",
    "NO TIENE",
    "SIN CODIGO",
    "SIN CÓDIGO",
    "NINGUNO",
    "PENDIENTE",
    ".",
]
# Patron que detecta conjuntos: "COMPUTADORA N°1", "IMPRESORA N 2", "PC-03"
PATRON_CONJUNTO = r"^(?P<base>.+?)\s*n[°º.]?\s*(?P<numero>\d+)\s*$"
PATRON_CONJUNTO_SEP = r"^(?P<base>.+?)[\s\-_]+(?P<numero>\d+)$"
# Un grupo con mas de un dispositivo se convierte en conjunto
SINONIMOS_BASE_CONJUNTO = {
    "COMPUTADORA": "Computadora",
    "PC": "Computadora",
    "ESTACION": "Estacion",
    "ESTACIÓN": "Estacion",
    "IMPRESORA": "Impresora",
    "LAPTOP": "Laptop",
    "MONITOR": "Monitor",
    "CPU": "CPU",
    "ROUTER": "Router",
    "SERVIDOR": "Servidor",
}

# ── Disponibilidad tecnica ───────────────────────────────────
DISPONIBLE = "disponible"
OCUPADO = "ocupado"
EN_ESPERA = "en_espera"
FUERA_DE_HORARIO = "fuera_de_horario"
DIA_LIBRE = "dia_libre"
AUSENTE = "ausente"
DISPONIBILIDADES = (DISPONIBLE, OCUPADO, EN_ESPERA, FUERA_DE_HORARIO, DIA_LIBRE, AUSENTE)

# ── Notificaciones ───────────────────────────────────────────
CANAL_SISTEMA = "sistema"
CANAL_EMAIL = "email"
CANAL_WEB = "web"
