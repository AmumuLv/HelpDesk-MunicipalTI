"""Zonas y oficinas: la puerta tiene que tener vuelta atrás.

La pantalla pedía solo lo activo (`solo_activas=True` por defecto) y solo ofrecía
«Desactivar». Desactivar una oficina la quitaba de la pantalla y no había ninguna forma
de recuperarla desde la aplicación: había que entrar a la base de datos. Eso no es una
pantalla de configuración, es una trampa.
"""

from __future__ import annotations

from bson import ObjectId

from tests.test_tickets_horarios import _mundo


async def test_lo_desactivado_se_ve_y_se_puede_reactivar(db, api):
    mundo = await _mundo(api, "org-desactivar")
    zona_id = mundo["zona"]["id"]
    oficina_id = mundo["oficina"]["id"]

    await api.post(
        "/api/activos",
        json={"tipo": "CPU", "oficina_id": oficina_id, "nombre_equipo": "PC UNO"},
        headers=mundo["admin"],
    )

    # Desactivar la oficina.
    desactivada = await api.patch(f"/api/oficinas/{oficina_id}", json={"activa": False}, headers=mundo["admin"])
    assert desactivada.status_code == 200, desactivada.text
    assert desactivada.json()["activa"] is False

    # Con `solo_activas` —el valor por defecto— ya no sale. Eso es lo que la
    # pantalla pedía antes, y por eso el elemento desaparecía.
    solo_activas = (await api.get("/api/oficinas", headers=mundo["admin"])).json()["items"]
    assert all(o["id"] != oficina_id for o in solo_activas), "el valor por defecto filtra las inactivas"

    # Pediendo también las inactivas, sigue ahí. Es lo que hace la pantalla ahora.
    con_inactivas = (
        await api.get("/api/oficinas?solo_activas=false", headers=mundo["admin"])
    ).json()["items"]
    inactiva = next(o for o in con_inactivas if o["id"] == oficina_id)
    assert inactiva["activa"] is False, "tiene que volver marcada como desactivada"

    # Y se puede reactivar, que es lo que no había.
    reactivada = await api.patch(f"/api/oficinas/{oficina_id}", json={"activa": True}, headers=mundo["admin"])
    assert reactivada.status_code == 200, reactivada.text
    assert reactivada.json()["activa"] is True
    vuelve = (await api.get("/api/oficinas", headers=mundo["admin"])).json()["items"]
    assert any(o["id"] == oficina_id for o in vuelve), "vuelve a ofrecerse"
    # Y el equipo sigue donde estaba: desactivar no mueve nada.
    assert await db["activos"].count_documents({"oficina_id": ObjectId(oficina_id)}) == 1


async def test_desactivar_no_saca_las_oficinas_de_su_zona(db, api):
    """
    Con `solo_activas=false` la zona cuenta sus oficinas **activas**.

    Si contara todas, una zona con doce oficinas de las que once están desactivadas
    pondría «Oficinas: 12» sin decir nada de ello. El contador tiene que decir
    cuántas se pueden usar.
    """
    mundo = await _mundo(api, "org-contador")
    zona_id = mundo["zona"]["id"]
    principal = mundo["oficina"]["id"]
    secundaria = (
        await api.post(
            "/api/oficinas", json={"nombre": "OFICINA SECUNDARIA", "zona_id": zona_id}, headers=mundo["admin"]
        )
    ).json()

    await api.patch(f"/api/oficinas/{secundaria['id']}", json={"activa": False}, headers=mundo["admin"])

    zonas = (await api.get("/api/zonas?solo_activas=false", headers=mundo["admin"])).json()["items"]
    zona = next(z for z in zonas if z["id"] == zona_id)
    assert zona["total_oficinas"] == 1, f"solo cuenta las activas: {zona['total_oficinas']}"


async def test_renombrar_una_zona_arrastra_su_nombre(db, api):
    """El nombre de la zona se guarda también en oficinas y personas."""
    mundo = await _mundo(api, "org-renombrar")
    zona_id = mundo["zona"]["id"]

    await api.patch(
        f"/api/zonas/{zona_id}", json={"nombre": "ZONA RENOMBRADA"}, headers=mundo["admin"]
    )

    oficina = await db["oficinas"].find_one({"_id": ObjectId(mundo["oficina"]["id"])})
    assert oficina["zona_nombre"] == "ZONA RENOMBRADA", oficina["zona_nombre"]
    usuario = await db["usuarios"].find_one({"zona_id": ObjectId(zona_id)})
    assert usuario["zona_nombre"] == "ZONA RENOMBRADA", usuario["zona_nombre"]


async def test_no_se_puede_crear_una_zona_con_nombre_repetido(db, api):
    mundo = await _mundo(api, "org-duplicado")
    repetida = await api.post("/api/zonas", json={"nombre": mundo["zona"]["nombre"]}, headers=mundo["admin"])
    assert repetida.status_code == 409, repetida.text