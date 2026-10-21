"""Forma real de las respuestas de la API, observada en marcha.

El backend no declara `response_model`, asi que el OpenAPI publica todas las
respuestas como `{}` sin forma. La unica fuente veraz es lo que el servidor
responde de verdad, y eso es lo que recoge este script.

    python tools/formas_vivas.py

Escribe frontend/forma-api.json, y de ahi `frontend/tools/generar-tipos-respuesta.mjs`
genera los tipos de TypeScript. Se combinan todos los elementos de cada lista,
no solo el primero: un campo que aparece nulo en un elemento y con texto en otro
sale como texto opcional, que es lo que de verdad es.
"""

from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("VERIFICAR_API", "http://localhost:8000/api")
CORREO = os.environ.get("VERIFICAR_CORREO", "admin@demo.local")
PASSWORD = os.environ.get("VERIFICAR_PASSWORD", "Demo12345")
# El portal del usuario se consulta con su propia sesion: `/equipos/mis` solo
# tiene contenido si quien pregunta tiene oficina asignada.
CORREO_USUARIO = os.environ.get("VERIFICAR_CORREO_USUARIO", "usuario1@demo.local")

# Cuantos elementos de una lista se usan para deducir la forma.
MUESTRA = 40
# Cuantas claves se guardan por objeto (suficiente para la interfaz).
CLAVES = 60
# Cuanto se baja antes de rendirse en objetos anidados.
FONDO = 5


def pedir(metodo: str, ruta: str, cuerpo=None, cab: dict | None = None):
    url = f"{BASE}{ruta}"
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(url, data=datos, method=metodo)
    if datos:
        peticion.add_header("Content-Type", "application/json")
    for clave, valor in (cab or {}).items():
        peticion.add_header(clave, valor)
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:  # noqa: S310
            crudo = respuesta.read().decode("utf-8")
            if respuesta.headers.get("content-type", "").startswith("application/json"):
                return respuesta.status, json.loads(crudo)
            return respuesta.status, crudo[:200]
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")[:300]
    except Exception as error:  # noqa: BLE001
        return 0, str(error)[:200]


# ── Deducción de forma ───────────────────────────────────────
# Cada forma es un diccionario: {"tipo": ...} y, si hace falta, "nulo": true,
# "campos": {...} o "elemento": {...}. Así dos formas siempre se pueden fusionar.


def forma(valor, profundidad: int = 0) -> dict:
    """Deduce la forma de un valor JSON, combinando si es una lista."""
    if profundidad > FONDO:
        return {"tipo": "desconocido"}

    if valor is None:
        return {"tipo": "nulo"}

    if isinstance(valor, bool):
        return {"tipo": "booleano"}

    if isinstance(valor, int | float):
        return {"tipo": "numero"}

    if isinstance(valor, str):
        return {"tipo": "texto"}

    if isinstance(valor, list):
        if not valor:
            return {"tipo": "lista", "vacia": True}
        elementos = [forma(item, profundidad + 1) for item in valor[:MUESTRA]]
        fusionada = elementos[0]
        for otra in elementos[1:]:
            fusionada = fusionar(fusionada, otra)
        return {"tipo": "lista", "elemento": fusionada}

    if isinstance(valor, dict):
        if not valor:
            return {"tipo": "objeto", "vacio": True}
        claves = list(valor.keys())[:CLAVES]
        return {"tipo": "objeto", "campos": {clave: forma(valor[clave], profundidad + 1) for clave in claves}}

    return {"tipo": "desconocido"}


def fusionar(una: dict, otra: dict) -> dict:
    """Une dos formas del mismo campo en una que admita ambas."""
    # Un null se recuerda como "este campo puede faltar"
    if una["tipo"] == "nulo":
        return marcar_nulo(otra)
    if otra["tipo"] == "nulo":
        return marcar_nulo(una)

    if una["tipo"] != otra["tipo"]:
        # Tipos distintos: se declara el más general para no mentir
        if una["tipo"] in {"numero", "booleano"} and otra["tipo"] in {"numero", "booleano"}:
            return {"tipo": "numero|booleano"}
        return {"tipo": "desconocido"}

    if una["tipo"] == "objeto":
        campos = dict(una.get("campos", {}))
        for clave, subforma in otra.get("campos", {}).items():
            campos[clave] = fusionar(campos[clave], subforma) if clave in campos else subforma
        return {"tipo": "objeto", "campos": campos}

    if una["tipo"] == "lista":
        elemento = una.get("elemento")
        if elemento is None:
            return {"tipo": "lista", "vacia": True}
        if "elemento" not in otra:
            return una
        return {"tipo": "lista", "elemento": fusionar(elemento, otra["elemento"])}

    return una


def marcar_nulo(forma_base: dict) -> dict:
    """Marca una forma como opcional (el campo apareció nulo en algún elemento)."""
    if forma_base["tipo"] in {"nulo", "desconocido"}:
        return {"tipo": "desconocido"}
    resultado = dict(forma_base)
    resultado["nulo"] = True
    return resultado


# ── Recorrido de la API ──────────────────────────────────────

RUTAS = [
    "/auth/sesion",
    "/mi-perfil",
    "/auth/preferencia-ia",
    "/publico/configuracion",
    "/instalacion",
    "/salud",
    # Tickets
    "/tickets",
    "/tickets/resumen",
    "/tickets/ajustes-crear",
    # Equipos del usuario (se consulta con su sesion, ver RUTAS_USUARIO)
    "/equipos/catalogos",
    "/equipos/buscar?texto=a",
    "/equipos/sugerencias?campo=marca",
    "/equipos/sugerencias?campo=marca&marca=HP",
    "/equipos/por-codigo?codigo=INEXISTENTE",
    # Organización
    "/zonas",
    "/oficinas",
    "/usuarios",
    "/usuarios/buscar?texto=a",
    "/usuarios/companeros",
    "/conjuntos",
    # Equipo TI
    "/equipo-ti/panel",
    "/equipo-ti/tecnicos",
    "/equipo-ti/calendario",
    "/equipo-ti/mi-horario/permiso",
    # Inventario
    "/calidad-inventario",
    "/calidad-inventario/estados-campo",
    "/calidad-inventario/esquemas",
    "/calidad-inventario/esquema/Monitor",
    "/importacion",
    "/campanas",
    "/campanas/versiones/historico",
    # Análisis e IA
    "/analitica/resumen",
    "/analitica/panel",
    "/analitica/equipos-prediccion",
    "/ia/asistente/preguntas",
    "/ia/asistente/conversaciones",
    "/ia/sugerencias-reporte?tipo_problema=x",
    # Contenido y administración
    "/kb/articulos",
    "/kb/categorias",
    "/kb/respuestas-rapidas",
    "/auditoria",
    "/exportaciones",
    "/permisos/matriz",
    "/permisos/tecnicos",
    "/vistas-guardadas",
    "/notificaciones",
    "/configuracion",
    "/configuracion/catalogos",
    "/configuracion/estado-ia",
    "/configuracion/feriados",
]

# Rutas con parámetro de id: se completan con ids reales de la demo.
RUTAS_CON_ID = [
    ("/usuarios/{usuario_id}", "usuario_id"),
    ("/oficinas/{oficina_id}", "oficina_id"),
    ("/zonas/{zona_id}", "zona_id"),
    ("/activos/{activo_id}", "activo_id"),
    ("/equipo-ti/{tecnico_id}", "tecnico_id"),
    ("/tickets/{ticket_id}", "ticket_id"),
    ("/tickets/{ticket_id}/mensajes", "ticket_id"),
    ("/tickets/{ticket_id}/notas", "ticket_id"),
    ("/tickets/{ticket_id}/ia", "ticket_id"),
    ("/kb/articulos/{articulo_id}", "articulo_id"),
    ("/campanas/{campana_id}", "campana_id"),
    ("/campanas/{campana_id}/items", "campana_id"),
]

# Rutas que solo tienen contenido con la sesion de un usuario normal
RUTAS_USUARIO = [
    "/equipos/mis",
    "/tickets?solo_mios=1",
    "/mi-perfil",
    "/auth/preferencia-ia",
    "/usuarios/companeros",
]

SUSTITUCIONES = {
    "{tipo}": "Monitor",
    "{lote_id}": "IMP-TEST",
    "{item_id}": "x",
    "{vista_id}": "x",
    "{feriado_id}": "x",
    "{exportacion_id}": "x",
    "{conversacion_id}": "x",
}


def main() -> None:
    estado, cuerpo = pedir("POST", "/auth/login", {"correo": CORREO, "password": PASSWORD})
    if estado != 200:
        print("No se pudo iniciar sesion:", cuerpo)
        raise SystemExit(1)

    cab = {
        "Authorization": f"Bearer {cuerpo['access_token']}",
        "X-CSRF-Token": cuerpo["csrf_token"] or "",
    }

    # ids reales para poder consultar las rutas con parametro
    ids: dict[str, str] = {}
    _, zonas = pedir("GET", "/zonas", cab=cab)
    if isinstance(zonas, dict) and zonas.get("items"):
        ids["zona_id"] = zonas["items"][0]["id"]
    _, oficinas = pedir("GET", "/oficinas", cab=cab)
    if isinstance(oficinas, dict) and oficinas.get("items"):
        ids["oficina_id"] = oficinas["items"][0]["id"]
    _, usuarios = pedir("GET", "/usuarios", cab=cab)
    if isinstance(usuarios, dict) and len(usuarios.get("items", [])) > 1:
        ids["usuario_id"] = usuarios["items"][1]["id"]
    _, activos = pedir("GET", "/activos", cab=cab)
    if isinstance(activos, dict) and activos.get("items"):
        ids["activo_id"] = activos["items"][0]["id"]
    _, tickets = pedir("GET", "/tickets", cab=cab)
    if isinstance(tickets, dict) and tickets.get("items"):
        ids["ticket_id"] = tickets["items"][0]["id"]
        # Las notas internas solo existen en algunos tickets: se busca uno que
        # las tenga para poder deducir su forma en vez de devolver una lista vacia
        for candidato in tickets["items"][:8]:
            _, prueba = pedir("GET", f"/tickets/{candidato['id']}/notas", cab=cab)
            if isinstance(prueba, dict) and prueba.get("items"):
                ids["ticket_id"] = candidato["id"]
                break
    _, campanas = pedir("GET", "/campanas", cab=cab)
    if isinstance(campanas, dict) and campanas.get("campana_activa"):
        ids["campana_id"] = campanas["campana_activa"]["id"]
    _, tecnicos = pedir("GET", "/equipo-ti/tecnicos", cab=cab)
    if isinstance(tecnicos, dict) and tecnicos.get("items"):
        ids["tecnico_id"] = tecnicos["items"][0]["id"]
        # Las ausencias se registran sobre técnicos concretos: se busca el
        # primero que tenga alguna, para deducir la forma con datos y no en vacío
        for candidato in tecnicos["items"]:
            _, prueba = pedir("GET", f"/ausencias?tecnico_id={candidato['id']}", cab=cab)
            if isinstance(prueba, dict) and prueba.get("items"):
                ids["tecnico_id"] = candidato["id"]
                break
    _, articulos = pedir("GET", "/kb/articulos", cab=cab)
    if isinstance(articulos, dict) and articulos.get("items"):
        ids["articulo_id"] = articulos["items"][0]["id"]

    # "siguiente-nombre" necesita oficina
    extra = []
    if "oficina_id" in ids:
        extra.append("/conjuntos/siguiente-nombre?oficina_id={oficina_id}")
    if "tecnico_id" in ids:
        extra.append("/ausencias?tecnico_id={tecnico_id}")
    if "campana_id" in ids:
        extra.append("/campanas/{campana_id}/items")
        extra.append("/campanas/{campana_id}/items?estado=verificado")
    extra.append(f"/calidad-inventario/esquema/{SUSTITUCIONES['{tipo}']}")

    rutas = [*RUTAS, *extra]
    # Se conservan las plantillas con {parametro}: el id real solo se usa para
    # consultar, nunca como clave, para que los tipos generados no cambien.
    for ruta, clave in RUTAS_CON_ID:
        if clave in ids:
            rutas.append(ruta)

    consultadas: dict[str, object] = {}
    sin_forma: list[str] = []

    def registrar(plantilla: str, real: str, cabeceras: dict[str, str], etiqueta: str) -> None:
        """Guarda la forma bajo la ruta con plantilla, no con el id real.

        Si la clave fuera la ruta concreta, los nombres de los tipos generados
        cambiarian en cada recarga de la demo y el archivo dejaria de compilar
        sin que nadie hubiera tocado nada.
        """
        estado, cuerpo = pedir("GET", real, cab=cabeceras)
        if estado == 200 and isinstance(cuerpo, dict | list):
            consultadas[f"{etiqueta}{plantilla}"] = forma(cuerpo)
        else:
            sin_forma.append(f"{real} -> {estado}")

    # Plantilla -> valor real, para consultar sin perder el nombre del recurso
    def resolver(plantilla: str) -> str:
        real = plantilla
        for clave, valor in ids.items():
            real = real.replace("{" + clave + "}", urllib.parse.quote(valor))
        for clave, valor in SUSTITUCIONES.items():
            real = real.replace(clave, urllib.parse.quote(valor))
        return real

    for ruta in rutas:
        registrar(ruta, resolver(ruta), cab, "")

    # El portal del usuario se consulta con su sesion: sin ella, /equipos/mis
    # viene vacio porque el administrador no tiene oficina asignada.
    estado_usuario, sesion_usuario = pedir("POST", "/auth/login", {"correo": CORREO_USUARIO, "password": PASSWORD})
    if estado_usuario == 200:
        cab_usuario = {
            "Authorization": f"Bearer {sesion_usuario['access_token']}",
            "X-CSRF-Token": sesion_usuario["csrf_token"] or "",
        }
        for ruta in RUTAS_USUARIO:
            registrar(ruta, ruta, cab_usuario, "usuario:")
    else:
        sin_forma.append(f"sesion de {CORREO_USUARIO} -> {estado_usuario}")

    salida = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "forma-api.json"
    salida.write_text(json.dumps(consultadas, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"ids de la demo: {', '.join(f'{k}={v[:8]}…' for k, v in ids.items())}")
    print(f"endpoints con forma: {len(consultadas)}")
    print(f"escrito en: {salida}")
    if sin_forma:
        print(f"\nSin forma ({len(sin_forma)}):")
        for nota in sin_forma:
            print(f"  {nota}")


if __name__ == "__main__":
    main()