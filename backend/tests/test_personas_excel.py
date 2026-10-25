from bson import ObjectId

from app.services import usuario_service
from tests.test_tickets_horarios import _mundo


async def test_crea_perfiles_sin_credenciales_y_vincula_en_lote(db, api):
    mundo = await _mundo(api, "personas_excel")
    oficina_id = ObjectId(mundo["oficina"]["id"])
    zona_id = ObjectId(mundo["zona"]["id"])
    actor = {"_id": ObjectId(), "nombre": "Admin de prueba", "rol": "administrador"}
    candidata = await usuario_service.crear(
        {"nombre": "Ana Lopez", "oficina_id": oficina_id, "rol": "usuario"},
        usuario=actor,
    )
    activos = [
        {"responsable_nombre": "Ana López", "responsable_id": None},
        {"responsable_nombre": "ANA  LOPEZ", "responsable_id": None},
        {"responsable_nombre": "Luis Ramos", "responsable_id": None},
    ]
    for activo in activos:
        await db["activos"].insert_one(
            {
                **activo,
                "responsable_nombre_excel": activo["responsable_nombre"],
                "oficina_id": oficina_id,
                "oficina_nombre": "COMUNA",
                "zona_id": zona_id,
                "zona_nombre": "Zona personas_excel",
                "activo": True,
                "importacion_lote": "lote-personas",
                "tipo": "CPU",
                "campos_estado": {},
                "clave_natural": str(ObjectId()),
                "actualizado_en": None,
            }
        )

    respuesta = await api.get("/api/importacion/responsables-excel", headers=mundo["admin"])
    assert respuesta.status_code == 200, respuesta.text
    grupos = respuesta.json()["items"]
    assert len(grupos) == 2
    assert all("_activos" not in grupo for grupo in grupos)
    grupo_ana = next(grupo for grupo in grupos if grupo["nombre_original"] == "Ana López")
    grupo_luis = next(grupo for grupo in grupos if grupo["nombre_original"] == "Luis Ramos")
    assert grupo_ana["equipos"] == 2
    assert grupo_ana["candidatos"][0]["id"] == str(candidata["_id"])
    assert grupo_ana["candidatos"][0]["coincidencia"] == "exacta"
    assert grupo_luis["candidatos"] == []

    confirmacion = await api.post(
        "/api/importacion/responsables-excel/confirmar",
        json={"selecciones": [
            {"clave": grupo_ana["clave"], "usuario_id": str(candidata["_id"])},
            {"clave": grupo_luis["clave"], "usuario_id": "crear"},
        ]},
        headers=mundo["admin"],
    )
    assert confirmacion.status_code == 200, confirmacion.text
    resultado = confirmacion.json()
    assert resultado["personas_creadas"] == 1
    assert resultado["equipos_vinculados"] == 3

    # El detalle: **qué se hizo con cada persona**, no solo cuántos.
    #
    # Con dos contadores se sabía que se había creado una persona, pero no cuál,
    # ni en qué zona, ni si lo que se hizo era lo que se quería. La pantalla
    # final no tenía nada que mostrar y no había forma de revisarlo.
    detalle = {fila["nombre_excel"]: fila for fila in resultado["detalle"]}
    assert set(detalle) == {"Ana López", "Luis Ramos"}

    ana = detalle["Ana López"]
    assert ana["accion"] == "vinculado"
    assert ana["nombre_asignado"] == "Ana Lopez"
    assert ana["usuario_id"] == str(candidata["_id"])
    assert ana["coincidencia"] == "exacta"
    assert ana["zona_nombre"] == "Zona personas_excel"
    assert ana["oficina_nombre"] == "COMUNA"
    assert ana["equipos"] == 2
    assert ana["nombre_parece_oficina"] is False

    luis = detalle["Luis Ramos"]
    assert luis["accion"] == "creado"
    assert luis["coincidencia"] is None
    assert luis["equipos"] == 1
    assert luis["nombre_parece_oficina"] is False, "el nombre es el de una persona, no el de la oficina"

    persona_creada = await db["usuarios"].find_one({"nombre": "Luis Ramos"})
    assert persona_creada is not None
    assert luis["usuario_id"] == str(persona_creada["_id"])
    assert persona_creada["email"] is None
    assert persona_creada["password_hash"] is None
    assert await db["usuarios"].count_documents({"nombre": "Luis Ramos"}) == 1
    activos_vinculados = await db["activos"].find({"importacion_lote": "lote-personas"}).to_list(None)
    assert {activo["responsable_id"] for activo in activos_vinculados} == {candidata["_id"], persona_creada["_id"]}
    assert {activo["responsable_nombre_excel"] for activo in activos_vinculados} == {
        "Ana López",
        "ANA  LOPEZ",
        "Luis Ramos",
    }
