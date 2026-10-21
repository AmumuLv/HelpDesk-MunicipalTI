"""Permisos del directorio de usuarios.

La pantalla de Usuarios está detrás de `usuarios.ver`, pero el endpoint que la
alimenta **no exigía ningún permiso**: bastaba con estar conectado. Una persona con
cuenta de tipo `usuario` —la que reporta problemas— que llamara a `GET /api/usuarios`
recibía el directorio entero: nombre, correo, teléfono, rol y oficina de las 267
cuentas de la municipalidad.

También se fija que el buscador no sea una puerta trasera al mismo directorio.
"""

from __future__ import annotations

from tests.test_tickets_horarios import _mundo, _sesion


async def _mundo_con_companero(api, sufijo: str):
    """`_mundo` no trae sesión del compañero; aquí se abre."""
    mundo = await _mundo(api, sufijo)
    mundo["companero_headers"] = await _sesion(api, f"companero-{sufijo}@prueba.local")
    return mundo


async def test_el_directorio_exige_usuarios_ver(db, api):
    """Una persona con cuenta normal no puede listar el directorio."""
    mundo = await _mundo(api, "permisos-directorio")

    # El técnico sí: tiene `usuarios.ver`.
    como_tecnico = await api.get("/api/usuarios", headers=mundo["tecnico"])
    assert como_tecnico.status_code == 200, como_tecnico.text
    assert como_tecnico.json()["total"] > 0

    # La persona que reporta problemas no.
    como_usuario = await api.get("/api/usuarios", headers=mundo["usuario"])
    assert como_usuario.status_code == 403, (
        f"una cuenta de rol 'usuario' listingó el directorio: {como_usuario.text[:200]}"
    )


async def test_el_directorio_no_deja_ver_a_un_visitante(db, api):
    """Ni siquiera una cuenta de rol 'usuario' sin oficina: tampoco."""
    mundo = await _mundo(api, "permisos-directorio-sin-oficina")
    # Se le quita la oficina: el backend tiene una guarda para ese caso, pero la
    # pantalla debe estar cerrada igualmente y no por suerte de un dato.
    from bson import ObjectId

    await db["usuarios"].update_one(
        {"email": f"usuario-permisos-directorio-sin-oficina@prueba.local"}, {"$set": {"oficina_id": None}}
    )
    respuesta = await api.get("/api/usuarios", headers=mundo["usuario"])
    assert respuesta.status_code == 403, respuesta.text


async def test_el_buscador_no_es_una_puerta_al_directorio(db, api):
    """`/usuarios/buscar` con texto vacío no puede devolver el directorio entero.

    El buscador se usa desde el registro manual de tickets, al que llega la gente de
    la calle. Para un rol `usuario` ya estaba limitado a su zona; para técnico y
    administrador es global a propósito, pero **con texto vacío** no debe listarlo
    todo: un desplegable de 40 nombres sin escribir nada no es buscar, es volcar.
    """
    mundo = await _mundo(api, "permisos-buscador")

    vacio = await api.get("/api/usuarios/buscar", headers=mundo["tecnico"])
    assert vacio.status_code == 200, vacio.text
    assert vacio.json()["items"] == [], "sin texto no debe devolver nada"

    conTexto = await api.get("/api/usuarios/buscar?texto=CEMU", headers=mundo["tecnico"])
    assert conTexto.status_code == 200
    assert len(conTexto.json()["items"]) < 20, "con texto sí busca, pero acotado"

    # Y un rol `usuario` sigue viendo solo su zona.
    como_usuario = await api.get("/api/usuarios/buscar?texto=CEMU", headers=mundo["usuario"])
    assert como_usuario.status_code == 200, como_usuario.text
    assert len(como_usuario.json()["items"]) <= 40


async def test_desactivar_y_reactivar_es_una_vuelta_completa(db, api):
    """Desactivar quita del listado; con `solo_activos=false` sigue estando; y se reactiva.

    El ciclo estaba a medio existir: el backend sabía apagar, y la pantalla no llamaba
    a ninguno de los dos caminos. Una cuenta desactivada desaparecía del directorio
    sin dejar rastro y sin forma de volver — el mismo callejón sin salida que se
    corrigió en Zonas y oficinas.
    """
    mundo = await _mundo_con_companero(api, "permisos-ciclo")
    objetivo = mundo["companero_id"]

    antes = (await api.get("/api/usuarios?por_pagina=200", headers=mundo["admin"])).json()
    activo_en_listado = any(u["id"] == objetivo for u in antes["items"])
    assert activo_en_listado, "antes de desactivar tiene que estar en la lista"

    apagado = await api.post(f"/api/usuarios/{objetivo}/desactivar", headers=mundo["admin"])
    assert apagado.status_code == 200, apagado.text
    assert apagado.json()["activo"] is False, apagado.json()

    # Desaparece del listado de las activas.
    solo_activos = (await api.get("/api/usuarios?por_pagina=200", headers=mundo["admin"])).json()
    assert not any(u["id"] == objetivo for u in solo_activos["items"]), "sigue saliendo en las activas"

    # Pero no se perdió: sale si se piden también las desactivadas, que es lo que hace
    # la casilla «Mostrar cuentas desactivadas».
    con_inactivas = (
        await api.get("/api/usuarios?solo_activos=false&por_pagina=200", headers=mundo["admin"])
    ).json()
    todavia = next((u for u in con_inactivas["items"] if u["id"] == objetivo), None)
    assert todavia is not None, "se perdió de la base"
    assert todavia["activo"] is False

    # Y se reactiva.
    reactivado = await api.patch(f"/api/usuarios/{objetivo}", json={"activo": True}, headers=mundo["admin"])
    assert reactivado.status_code == 200, reactivado.text
    assert reactivado.json()["activo"] is True, reactivado.json()

    de_nuevo = (await api.get("/api/usuarios?por_pagina=200", headers=mundo["admin"])).json()
    assert any(u["id"] == objetivo for u in de_nuevo["items"]), "no vuelve a la lista"


async def test_desactivar_no_borra_nada(db, api):
    """Desactivar apaga la entrada; no toca los tickets ni los equipos de esa persona."""
    mundo = await _mundo_con_companero(api, "permisos-desactivar-no-borra")
    objetivo = mundo["companero_id"]

    await api.post("/api/activos", json={"tipo": "CPU", "oficina_id": mundo["oficina"]["id"], "nombre_equipo": "PC DEL COMPAÑERO"}, headers=mundo["admin"])
    await db["activos"].update_many(
        {"oficina_id": __import__("bson").ObjectId(mundo["oficina"]["id"])},
        {"$set": {"responsable_id": __import__("bson").ObjectId(objetivo)}},
    )
    antes_equipos = await db["activos"].count_documents({"responsable_id": __import__("bson").ObjectId(objetivo)})
    assert antes_equipos == 1

    await api.post(f"/api/usuarios/{objetivo}/desactivar", headers=mundo["admin"])

    assert await db["usuarios"].count_documents({"_id": __import__("bson").ObjectId(objetivo)}) == 1, "no se borra la cuenta"
    assert await db["activos"].count_documents({"responsable_id": __import__("bson").ObjectId(objetivo)}) == 1, (
        "sus equipos siguen siendo suyos"
    )


async def test_un_usuario_no_se_desactiva_a_si_mismo(db, api):
    """Apagar la propia cuenta deja al operador fuera del sistema sin avisar."""
    mundo = await _mundo_con_companero(api, "permisos-autoinactivo")
    propio = (await api.get("/api/mi-perfil", headers=mundo["admin"])).json()

    apagado = await api.post(f"/api/usuarios/{propio['id']}/desactivar", headers=mundo["admin"])
    assert apagado.status_code in (400, 403), f"debería rechazar y devolvió {apagado.status_code}: {apagado.text[:160]}"

    sigue = (await api.get("/api/mi-perfil", headers=mundo["admin"])).json()
    assert sigue["activo"] is True, "el administrador se desactivó a sí mismo"


async def test_ver_otro_perfil_sigue_limitado(db, api):
    """Uno puede ver su propio perfil; el de otra persona, solo con `usuarios.ver`."""
    mundo = await _mundo_con_companero(api, "permisos-detalle")
    propio = await api.get("/api/mi-perfil", headers=mundo["usuario"])
    assert propio.status_code == 200, propio.text
    mio = propio.json()["id"]

    # Su propio perfil: sí.
    assert (await api.get(f"/api/usuarios/{mio}", headers=mundo["usuario"])).status_code == 200

    # El de otra persona, siendo ambos rol `usuario`: no.
    ajeno = await api.get(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo["companero_headers"])
    assert ajeno.status_code == 403, ajeno.text

    # El técnico, que sí tiene `usuarios.ver`: sí.
    assert (await api.get(f"/api/usuarios/{mundo['usuario_id']}", headers=mundo["tecnico"])).status_code == 200