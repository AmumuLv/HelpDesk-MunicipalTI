"""Ficha de oficina: los equipos se agrupan por persona, no por su nombre.

En `GET /api/oficinas/{id}` los equipos con responsable se agrupaban por
`responsable_nombre`, que es un texto. Con eso:

* dos personas que se llamen igual caían en la misma fila y sus equipos se sumaban
  como si fueran de una sola persona;
* un nombre con un espacio de más o una tilde distinta partía el grupo en dos, y la
  parte que se quedaba fuera hacía que su dueño apareciera «sin equipo» teniendo los
  suyos.

El fallo es silencioso: nada sale mal, solo un número que no cuenta. Aquí se fija que
el cruce es por id, y que los grupos sin id siguen agrupándose —y avisando— para que no
se pierdan de vista.
"""

from __future__ import annotations

from bson import ObjectId

from tests.conftest import PASSWORD
from tests.test_tickets_horarios import _mundo


async def _activar_con_responsable(api, oficina_id: str, nombre: str, equipo: str, cabeceras, responsable_id=None):
    respuesta = await api.post(
        "/api/activos",
        json={
            "tipo": "CPU",
            "oficina_id": oficina_id,
            "nombre_equipo": equipo,
            "responsable_id": responsable_id,
            "responsable_nombre": nombre,
        },
        headers=cabeceras,
    )
    assert respuesta.status_code in (200, 201), respuesta.text
    return respuesta.json()


async def _crear_usuario(api, nombre: str, correo: str, oficina_id: str, cabeceras) -> dict:
    respuesta = await api.post(
        "/api/usuarios",
        json={"nombre": nombre, "email": correo, "password": PASSWORD, "rol": "usuario", "oficina_id": oficina_id},
        headers=cabeceras,
    )
    assert respuesta.status_code in (200, 201), respuesta.text
    return respuesta.json()


async def test_dos_personas_con_el_mismo_nombre_no_se_mezclan(db, api):
    mundo = await _mundo(api, "oficina-homonimos")
    oficina_id = mundo["oficina"]["id"]

    # Dos cuentas distintas con el mismo nombre escrito.
    uno = await _crear_usuario(api, "PERSONA REPETIDA", "gemelo-uno@prueba.local", oficina_id, mundo["admin"])
    dos = await _crear_usuario(api, "PERSONA REPETIDA", "gemelo-dos@prueba.local", oficina_id, mundo["admin"])
    assert uno["id"] != dos["id"], "las dos cuentas tienen que ser distintas para que la prueba signifique algo"

    await _activar_con_responsable(api, oficina_id, "PERSONA REPETIDA", "PC DEL UNO", mundo["admin"], uno["id"])
    await _activar_con_responsable(
        api, oficina_id, "PERSONA REPETIDA", "PC DEL OTRO", mundo["admin"], dos["id"]
    )

    detalle = (await api.get(f"/api/oficinas/{oficina_id}", headers=mundo["admin"])).json()
    grupos = detalle["equipos_por_usuario"]
    assert len(grupos) == 2, f"los homónimos tienen que salir en dos grupos, salieron {len(grupos)}"
    assert {g["responsable_id"] for g in grupos} == {uno["id"], dos["id"]}
    for grupo in grupos:
        assert len(grupo["equipos"]) == 1, "cada grupo lleva solo los equipos de su dueño"
    nombres = {e["nombre_equipo"] if "nombre_equipo" in e else e["nombre"] for g in grupos for e in g["equipos"]}
    assert nombres == {"PC DEL UNO", "PC DEL OTRO"}, f"se cruzaron los equipos: {nombres}"


async def test_un_nombre_con_espacios_no_deja_a_su_dueno_sin_equipo(db, api):
    """Si el equipo guarda el nombre con un espacio de más, su dueño sigue siendo él."""
    mundo = await _mundo(api, "oficina-espacios")
    oficina_id = mundo["oficina"]["id"]
    usuario = (await api.get("/api/usuarios?limite=200", headers=mundo["admin"])).json()["items"]
    dueño = next(u for u in usuario if u["oficina_id"] == oficina_id and u["rol"] == "usuario")

    await _activar_con_responsable(
        api, oficina_id, f"  {dueño['nombre']}  ", "PC CON ESPACIOS", mundo["admin"], dueño["id"]
    )

    detalle = (await api.get(f"/api/oficinas/{oficina_id}", headers=mundo["admin"])).json()
    grupos = detalle["equipos_por_usuario"]
    con_dueno = [g for g in grupos if g.get("responsable_id") == dueño["id"]]
    assert len(con_dueno) == 1, f"el equipo tiene que quedar en el grupo de su dueño: {grupos}"
    assert len(con_dueno[0]["equipos"]) == 1
    # Y no puede haberdlinguido en el de uso común, que es para lo que no tiene a nadie.
    ids_comunes = {e["id"] for e in detalle["equipos_uso_comun"]}
    assert con_dueno[0]["equipos"][0]["id"] not in ids_comunes


async def test_el_responsable_solo_con_nombre_no_se_pierde(db, api):
    """Equipo con nombre de responsable pero sin cuenta: se agrupa y se avisa, no se pierde.

    Ese estado no lo crea el formulario —ahí el nombre se deriva siempre de la cuenta—
    pero sí la importación del Excel: si el responsable escrito no aparece en el sistema
    y no se crean cuentas nuevas, el equipo queda con el nombre y sin id.
    """
    mundo = await _mundo(api, "oficina-sin-cuenta")
    oficina_id = mundo["oficina"]["id"]

    equipo = await api.post(
        "/api/activos",
        json={"tipo": "Radio", "oficina_id": oficina_id, "nombre_equipo": "RADIO GUARDIA"},
        headers=mundo["admin"],
    )
    equipo_id = equipo.json()["id"]
    await db["activos"].update_one(
        {"_id": ObjectId(equipo_id)},
        {"$set": {"responsable_nombre": "GUARDIA SIN CUENTA", "responsable_id": None}},
    )

    detalle = (await api.get(f"/api/oficinas/{oficina_id}", headers=mundo["admin"])).json()
    grupos = detalle["equipos_por_usuario"]
    assert len(grupos) == 1, f"no debe perderse el equipo: {grupos}"
    assert grupos[0]["responsable"] == "GUARDIA SIN CUENTA"
    assert grupos[0]["responsable_id"] is None, "sin cuenta no hay id con el que agrupar"
    assert len(grupos[0]["equipos"]) == 1
    # Sin cuenta tampoco es «de la oficina»: es de alguien concreto que aún no existe
    # como usuario, y ocultarlo entre los de uso común haría creer que no tiene dueño.
    assert detalle["equipos_uso_comun"] == []


async def test_el_uso_comun_sigue_siendo_lo_que_no_tiene_dueno(db, api):
    mundo = await _mundo(api, "oficia-uso-comun")
    oficina_id = mundo["oficina"]["id"]

    await api.post(
        "/api/activos",
        json={"tipo": "Impresora", "oficina_id": oficina_id, "nombre_equipo": "IMPRESORA COMPARTIDA"},
        headers=mundo["admin"],
    )

    detalle = (await api.get(f"/api/oficinas/{oficina_id}", headers=mundo["admin"])).json()
    assert len(detalle["equipos_uso_comun"]) == 1, "sin responsable va a uso común"
    assert detalle["equipos_uso_comun"][0]["nombre"] == "IMPRESORA COMPARTIDA"
    assert detalle["equipos_por_usuario"] == []
    assert detalle["total_equipos"] == 1