"""Borrar una zona u oficina: el aviso dice lo mismo que va a hacer el borrado.

El diálogo de confirmación necesita saber qué hay detrás antes de preguntar. Antes
no había forma de saberlo sin intentarlo, y los contadores de la lista no servían:
el de equipos filtra los dados de baja y el borrado no, así que el aviso podía decir
«0 equipos» y el borrado responder «tiene 3».

Aquí se fija que `GET /{zonas|oficinas}/{id}/borrado` y el `DELETE` usan la **misma**
comprobación, y que el número del aviso es el que cuenta.
"""

from __future__ import annotations

from bson import ObjectId

from tests.test_tickets_horarios import _mundo


async def test_el_aviso_de_borrado_dice_lo_mismo_que_el_borrado(db, api):
    mundo = await _mundo(api, "borrado-zona")
    zona_id = mundo["zona"]["id"]

    # _mundo deja una oficina dentro, así que la zona no se puede borrar.
    aviso = (await api.get(f"/api/zonas/{zona_id}/borrado", headers=mundo["admin"])).json()
    assert aviso["puede_eliminar"] is False, "con una oficina dentro no se puede borrar"
    assert aviso["oficinas"] == 1, aviso
    assert aviso["motivo"] and "oficina" in aviso["motivo"], aviso["motivo"]
    # Una sola oficina: en singular, no «1 oficina(s)».
    assert "1 oficina registrada" in aviso["motivo"], aviso["motivo"]
    assert "oficina(s)" not in aviso["motivo"], "no se escribe «oficina(s)»"

    # Y el borrado se rechaza con exactamente ese motivo.
    borrado = await api.delete(f"/api/zonas/{zona_id}", headers=mundo["admin"])
    assert borrado.status_code == 403, borrado.text
    assert borrado.json()["mensaje"] == aviso["motivo"], "el aviso y el rechazo dicen cosas distintas"
    assert await db["zonas"].count_documents({"_id": ObjectId(zona_id)}) == 1, "no se borró"


async def test_el_aviso_de_una_zona_vacia_permite_borrar(db, api):
    mundo = await _mundo(api, "borrado-zona-vacia")
    zona = (
        await api.post("/api/zonas", json={"nombre": "ZONA HuerfANA"}, headers=mundo["admin"])
    ).json()

    aviso = (await api.get(f"/api/zonas/{zona['id']}/borrado", headers=mundo["admin"])).json()
    assert aviso["puede_eliminar"] is True, aviso
    assert aviso["motivo"] is None
    assert aviso["oficinas"] == 0 and aviso["equipos"] == 0

    borrado = await api.delete(f"/api/zonas/{zona['id']}", headers=mundo["admin"])
    assert borrado.status_code == 200, borrado.text
    assert await db["zonas"].count_documents({"_id": ObjectId(zona["id"])}) == 0


async def test_el_aviso_de_oficina_cuenta_los_equipos_dados_de_baja(db, api):
    """El equipo dado de baja **también** cuenta: el borrado los tiene en cuenta.

    Es justo el caso en el que el contador de la lista mentía. La lista dice
    «total_equipos» sin los dados de baja; el borrado cuenta todos. Si el aviso
    usara el de la lista, prometería un borrado que luego se rechaza.
    """
    mundo = await _mundo(api, "borrado-oficina")
    oficina_id = mundo["oficina"]["id"]

    creado = (
        await api.post(
            "/api/activos",
            json={"tipo": "CPU", "oficina_id": oficina_id, "nombre_equipo": "PC DADO DE BAJA", "estado": "Dado de baja"},
            headers=mundo["admin"],
        )
    ).json()
    await db["activos"].update_one({"_id": ObjectId(creado["id"])}, {"$set": {"estado": "Dado de baja"}})

    # El contador de la lista no lo ve…
    oficinas = (await api.get(f"/api/oficinas?zona_id={mundo['zona']['id']}&solo_activas=false", headers=mundo["admin"])).json()["items"]
    de_la_lista = next(o for o in oficinas if o["id"] == oficina_id)
    assert de_la_lista["total_equipos"] == 0, de_la_lista["total_equipos"]

    # …pero el aviso y el borrado sí.
    aviso = (await api.get(f"/api/oficinas/{oficina_id}/borrado", headers=mundo["admin"])).json()
    assert aviso["equipos"] == 1, aviso
    assert aviso["puede_eliminar"] is False, aviso
    assert "1 equipo registrado" in aviso["motivo"], aviso["motivo"]
    assert "equipo(s)" not in aviso["motivo"]

    borrado = await api.delete(f"/api/oficinas/{oficina_id}", headers=mundo["admin"])
    assert borrado.status_code == 403, borrado.text
    assert borrado.json()["mensaje"] == aviso["motivo"]


async def test_una_oficina_sin_equipos_se_puede_borrar(db, api):
    mundo = await _mundo(api, "borrado-oficina-limpia")
    oficina = (
        await api.post(
            "/api/oficinas", json={"nombre": "OFICINA VACIA", "zona_id": mundo["zona"]["id"]}, headers=mundo["admin"]
        )
    ).json()

    aviso = (await api.get(f"/api/oficinas/{oficina['id']}/borrado", headers=mundo["admin"])).json()
    assert aviso["puede_eliminar"] is True, "sin equipos sí se puede borrar aunque tenga personas"
    assert aviso["motivo"] is None
    assert aviso["personas"] == 0

    borrado = await api.delete(f"/api/oficinas/{oficina['id']}", headers=mundo["admin"])
    assert borrado.status_code == 200, borrado.text
    assert await db["oficinas"].count_documents({"_id": ObjectId(oficina["id"])}) == 0


async def test_borrar_no_se_lleva_los_equipos_de_otras_oficinas(db, api):
    """Borrar una zona vacía no toca nada fuera de ella."""
    mundo = await _mundo(api, "borrado-aislado")
    zona_vacia = (
        await api.post("/api/zonas", json={"nombre": "ZONA QUE SE VA"}, headers=mundo["admin"])
    ).json()

    await api.delete(f"/api/zonas/{zona_vacia['id']}", headers=mundo["admin"])

    assert await db["oficinas"].count_documents({"zona_id": ObjectId(mundo["zona"]["id"])}) == 1
    assert await db["usuarios"].count_documents({"zona_id": ObjectId(mundo["zona"]["id"])}) > 0
    assert await db["zonas"].count_documents({"_id": ObjectId(mundo["zona"]["id"])}) == 1