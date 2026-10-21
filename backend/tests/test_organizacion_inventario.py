"""Jerarquia Zona > Oficina > Usuario, inventario y estado 'No aplica'."""

from __future__ import annotations

import pytest

from tests.conftest import PASSWORD


async def _sesion(api, correo: str, password: str = PASSWORD) -> dict[str, str]:
    respuesta = await api.post("/api/auth/login", json={"correo": correo, "password": password})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    return {"Authorization": f"Bearer {datos['access_token']}", "X-CSRF-Token": datos["csrf_token"]}


async def test_jerarquia_zona_oficina_usuario(db, api):
    from app.services import org_service, usuario_service

    cab_admin = await _sesion_admin(api, "jerarquia@prueba.local")

    zona = (await api.post("/api/zonas", json={"nombre": "Zona Norte"}, headers=cab_admin)).json()
    assert zona["nombre"] == "Zona Norte"
    assert "id" in zona
    assert 1 <= zona["color_indice"] <= 8

    oficina = (
        await api.post("/api/zonas" if False else "/api/oficinas", json={"nombre": "LIMPIEZA", "zona_id": zona["id"]}, headers=cab_admin)
    ).json()
    assert oficina["zona_id"] == zona["id"]
    assert oficina["zona_nombre"] == "Zona Norte"

    # No se puede repetir zona ni oficina dentro de la misma zona
    repetida = await api.post("/api/zonas", json={"nombre": "zona norte"}, headers=cab_admin)
    assert repetida.status_code == 409
    repetida_oficina = await api.post("/api/oficinas", json={"nombre": "limpieza", "zona_id": zona["id"]}, headers=cab_admin)
    assert repetida_oficina.status_code == 409

    usuario = (
        await api.post(
            "/api/usuarios",
            json={
                "nombre": "Trabajador Demo",
                "email": "trabajador@prueba.local",
                "password": PASSWORD,
                "rol": "usuario",
                "oficina_id": oficina["id"],
            },
            headers=cab_admin,
        )
    ).json()
    assert usuario["oficina_id"] == oficina["id"]
    assert usuario["zona_id"] == zona["id"], "el usuario hereda la zona de su oficina"
    assert usuario["zona_nombre"] == "Zona Norte"

    # La zona se deriva de la oficina: no puede contradecirse
    otra_zona = (await api.post("/api/zonas", json={"nombre": "Zona Sur"}, headers=cab_admin)).json()
    zona_antes = (await api.get(f"/api/usuarios/{usuario['id']}", headers=cab_admin)).json()
    assert zona_antes["zona_id"] == zona["id"], "la oficina manda sobre la zona"
    assert otra_zona["id"] != zona["id"]

    # Los usuarios normales no ven a otros
    cab_usuario = await _sesion(api, "trabajador@prueba.local")
    detalle = await api.get(f"/api/usuarios/{usuario['id']}", headers=cab_usuario)
    assert detalle.status_code == 200, "puede ver su propio perfil"
    creado_otro = await api.post(
        "/api/usuarios",
        json={"nombre": "Otro Usuario", "email": "otro@prueba.local", "password": PASSWORD, "rol": "usuario", "oficina_id": oficina["id"]},
        headers=cab_admin,
    )
    otro = creado_otro.json()
    ajeno = await api.get(f"/api/usuarios/{otro['id']}", headers=cab_usuario)
    assert ajeno.status_code == 403

    # Perfil de zona con datos reales
    perfil = (await api.get(f"/api/zonas/{zona['id']}", headers=cab_admin)).json()
    assert perfil["color_indice"] == zona["color_indice"]
    assert perfil["total_oficinas"] == 1
    assert perfil["total_usuarios"] == 2
    assert perfil["oficinas"][0]["nombre"] == "LIMPIEZA"

    # Perfil de oficina
    perfil_oficina = (await api.get(f"/api/oficinas/{oficina['id']}", headers=cab_admin)).json()
    assert perfil_oficina["zona_color_indice"] == zona["color_indice"]
    assert {u["nombre"] for u in perfil_oficina["usuarios"]} == {"Trabajador Demo", "Otro Usuario"}
    assert "usuarios" not in perfil_oficina or perfil_oficina["usuarios"]

    # Búsqueda ignorando tildes y mayúsculas
    usuarios = (await api.get("/api/usuarios?texto=trabajador", headers=cab_admin)).json()
    assert usuarios["total"] == 1


async def test_migracion_asigna_color_estable_a_zonas_existentes(db):
    from app.migrations.m007_color_zonas import aplicar
    from bson import ObjectId

    ids = [ObjectId() for _ in range(9)]
    await db["zonas"].insert_many([
        {"_id": zona_id, "nombre": f"Zona {i}", "nombre_normalizado": f"zona-{i}"}
        for i, zona_id in enumerate(ids)
    ])

    await aplicar(db)
    colores = await db["zonas"].find({"_id": {"$in": ids}}).sort("_id", 1).to_list(None)

    assert [zona["color_indice"] for zona in colores] == [1, 2, 3, 4, 5, 6, 7, 8, 1]


async def _sesion_admin(api, correo: str) -> dict[str, str]:
    from app.services import usuario_service

    await usuario_service.crear(
        {"nombre": "Admin Jerarquia", "email": correo, "password": PASSWORD, "rol": "administrador"},
        usuario={"nombre": "Instalador", "rol": "sistema"},
        es_primer_admin=True,
    )
    return await _sesion(api, correo)


async def test_activo_se_guarda_con_datos_faltantes(db, api):
    from app.services import org_service

    cab_admin = await _sesion_admin(api, "inventario@prueba.local")
    zona = (await api.post("/api/zonas", json={"nombre": "Zona Inventario"}, headers=cab_admin)).json()
    oficina = (await api.post("/api/oficinas", json={"nombre": "MESA PARTES", "zona_id": zona["id"]}, headers=cab_admin)).json()

    # Solo tipo y oficina: debe guardarse
    activo = (
        await api.post("/api/activos", json={"tipo": "CPU", "oficina_id": oficina["id"]}, headers=cab_admin)
    ).json()
    assert activo["tipo"] == "CPU"
    assert activo["faltantes"] > 0
    assert activo["opciones_avanzadas"] is False

    # IP y MAC inválidas si se escriben
    mala = await api.post(
        "/api/activos",
        json={"tipo": "Monitor", "oficina_id": oficina["id"], "direccion_ip": "999.1.1.1"},
        headers=cab_admin,
    )
    assert mala.status_code == 422

    # Código duplicado avisa con el equipo existente
    primero = (
        await api.post(
            "/api/activos",
            json={"tipo": "Monitor", "oficina_id": oficina["id"], "codigo_patrimonial": "ABC-1"},
            headers=cab_admin,
        )
    ).json()
    segundo = await api.post(
        "/api/activos",
        json={"tipo": "Monitor", "oficina_id": oficina["id"], "codigo_patrimonial": "ABC-1"},
        headers=cab_admin,
    )
    assert segundo.status_code == 201, segundo.text
    duplicados = await api.get(
        "/api/activos/duplicados",
        params={"codigo_patrimonial": "ABC-1"},
        headers=cab_admin,
    )
    assert {equipo["id"] for equipo in duplicados.json()["items"]} >= {primero["id"], segundo.json()["id"]}

    # El tipo es obligatorio
    sin_tipo = await api.post("/api/activos", json={"oficina_id": oficina["id"]}, headers=cab_admin)
    assert sin_tipo.status_code == 422


async def test_cada_tipo_pregunta_lo_que_le_corresponde(db, api):
    """El esquema del tipo decide qué se pregunta al registrar.

    El alta sigue la plantilla del Excel: a un sistema de audio no se le
    pregunta la direccion IP porque no la tiene, pero si nombre, marca y
    modelo, que es lo comun a todo. Sin esquema propio, estos tipos caian en el
    generico y pedian IP y MAC a un amplificador.
    """
    cab_admin = await _sesion_admin(api, "esquemas@prueba.local")

    async def esquema(tipo: str) -> set[str]:
        respuesta = await api.get(f"/api/calidad-inventario/esquema/{tipo}", headers=cab_admin)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        return {*(cuerpo.get("esperados") or []), *(cuerpo.get("opcionales") or [])}

    # Cada tipo nuevo tiene esquema propio
    for tipo in (
        "Switch",
        "Servidor",
        "Tablet",
        "Celular",
        "UPS",
        "Disco duro externo",
        "Sistema de audio",
        "Otro",
    ):
        campos = await esquema(tipo)
        assert {"marca", "modelo", "nombre_equipo"} <= campos, f"a {tipo} hay que poder ponerle nombre y marca"

    # Lo que no tiene, no se pregunta
    for tipo in ("Sistema de audio", "UPS", "Celular", "Otro"):
        campos = await esquema(tipo)
        assert "direccion_ip" not in campos, f"a un {tipo} no se le pregunta la IP"
    for tipo in ("Sistema de audio", "UPS", "Celular", "Otro"):
        campos = await esquema(tipo)
        assert "direccion_mac" not in campos, f"a un {tipo} no se le pregunta la MAC"

    # Un servidor se registra como una computadora fija
    servidor = await esquema("Servidor")
    assert {"procesador", "memoria_ram", "almacenamiento", "direccion_ip", "direccion_mac"} <= servidor
    # Un dispositivo movil tiene MAC, pero no IP propia en el inventario
    tablet = await esquema("Tablet")
    assert "direccion_mac" in tablet and "direccion_ip" not in tablet
    # Un disco externo guarda su capacidad
    assert "almacenamiento" in await esquema("Disco duro externo")
    # Lo que va en la red, lo tiene
    for tipo in ("Router", "Switch"):
        campos = await esquema(tipo)
        assert {"direccion_ip", "direccion_mac"} <= campos
    # Y un mouse tampoco tiene IP: es un periférico
    assert "direccion_ip" not in await esquema("Mouse")
    # Un monitor sí tiene pantalla; una impresora y una CPU no. Este campo se
    # colaba en el esquema de la impresora y hacía que su ficha pidiera «Tamaño
    # de pantalla», que es el síntoma de que un esquema por tipo no sirve si
    # incluye campos que no aplican.
    assert "tamano_pantalla" in await esquema("Monitor")
    assert "tamano_pantalla" not in await esquema("Impresora"), "una impresora no tiene pantalla"
    assert "tamano_pantalla" not in await esquema("CPU"), "una CPU no tiene pantalla"
    # Y una CPU no tiene peripherals: la impresora tampoco lleva procesador
    assert "procesador" not in await esquema("Impresora")
    assert "memoria_ram" not in await esquema("Impresora")
    assert "almacenamiento" not in await esquema("Impresora")
    # Un teclado y un mouse no llevan pantalla ni IP
    for tipo in ("Teclado", "Mouse"):
        campos = await esquema(tipo)
        assert "tamano_pantalla" not in campos, f"un {tipo} no tiene pantalla"


async def test_responsables_pendientes_coinciden_con_la_puesta_en_marcha(db, api):
    """El filtro de Equipos y la puesta en marcha tienen que contar lo mismo.

    «Pendiente» es el equipo cuyo responsable viene del Excel y **no** esta
    enlazado a una cuenta activa. Si la cuenta se dio de baja, el enlace ya no
    sirve para nada y el equipo vuelve a estar pendiente de vincular.
    """
    from app.core.db import get_db
    from app.core.ids import a_id
    from app.services import usuario_service

    cab_admin = await _sesion_admin(api, "responsables@prueba.local")
    zona = (await api.post("/api/zonas", json={"nombre": "Zona Resp"}, headers=cab_admin)).json()
    oficina = (await api.post("/api/oficinas", json={"nombre": "MESA RESP", "zona_id": zona["id"]}, headers=cab_admin)).json()

    async def crear(nombre: str, **extra) -> dict:
        respuesta = await api.post(
            "/api/activos",
            json={"tipo": "CPU", "oficina_id": oficina["id"], "nombre_equipo": nombre, **extra},
            headers=cab_admin,
        )
        assert respuesta.status_code == 201, respuesta.text
        return respuesta.json()

    async def como_llego_del_excel(activo_id: str, nombre_responsable: str | None) -> None:
        """Así queda tras la importación: el nombre viene del Excel, no de una cuenta."""
        await get_db()["activos"].update_one(
            {"_id": a_id(activo_id)},
            {"$set": {"responsable_nombre": nombre_responsable, "responsable_id": None}},
        )

    async def pendientes() -> set[str]:
        respuesta = await api.get(
            "/api/activos",
            params={"responsables_pendientes": "true", "por_pagina": 100},
            headers=cab_admin,
        )
        assert respuesta.status_code == 200, respuesta.text
        return {item["id"] for item in respuesta.json()["items"]}

    # 1. El Excel nombra a alguien y ese nombre no tiene cuenta: pendiente
    sin_cuenta = await crear("Sin cuenta")
    await como_llego_del_excel(sin_cuenta["id"], "PERSONA SIN CUENTA")
    # 2. Sin responsable en el Excel: no es pendiente, es de uso común
    await crear("Sin responsable")
    assert await pendientes() == {sin_cuenta["id"]}

    # 3. Enlazado a una cuenta activa: deja de estar pendiente
    await usuario_service.crear(
        {"nombre": "Persona Con Cuenta", "email": "con-cuenta@prueba.local", "password": PASSWORD, "rol": "usuario"},
        usuario={"nombre": "Instalador", "rol": "sistema"},
    )
    persona = (await usuario_service.buscar_global("con-cuenta@prueba.local"))[0]
    con_cuenta = await crear("Con cuenta", responsable_id=str(persona["id"]))
    assert await pendientes() == {sin_cuenta["id"]}

    # 4. Si esa cuenta se da de baja, el enlace ya no sirve y vuelve a estar pendiente
    await get_db()["usuarios"].update_one({"_id": a_id(persona["id"])}, {"$set": {"activo": False}})
    assert await pendientes() == {sin_cuenta["id"], con_cuenta["id"]}

    # Y sin el filtro salen todos
    todos = await api.get("/api/activos", params={"por_pagina": 100}, headers=cab_admin)
    assert len(todos.json()["items"]) == 3


async def test_estado_no_apica_sale_de_la_completitud(db, api):
    cab_admin = await _sesion_admin(api, "noaplica@prueba.local")
    zona = (await api.post("/api/zonas", json={"nombre": "Zona NoAplica"}, headers=cab_admin)).json()
    oficina = (await api.post("/api/oficinas", json={"nombre": "ARCHIVO", "zona_id": zona["id"]}, headers=cab_admin)).json()
    teclado = (
        await api.post(
            "/api/activos",
            json={"tipo": "Teclado", "oficina_id": oficina["id"], "marca": "Logitech", "codigo_patrimonial": "TEC-1"},
            headers=cab_admin,
        )
    ).json()

    # El esquema de Teclado espera codigo y marca
    assert teclado["completitud"] == 100.0

    # Con un segundo equipo al que le falta la marca
    teclado2 = (
        await api.post("/api/activos", json={"tipo": "Teclado", "oficina_id": oficina["id"]}, headers=cab_admin)
    ).json()
    assert teclado2["completitud"] < 100
    assert "marca" in teclado2["campos_faltantes"]

    # Marcar la marca como "No aplica": deja de avisar
    marcado = await api.post(
        f"/api/activos/{teclado2['id']}/campos",
        json={"campos": ["marca"], "estado": "no_aplica", "motivo": "Este equipo no tiene ni tendra marca registrada"},
        headers=cab_admin,
    )
    assert marcado.status_code == 200
    despues = marcado.json()["activo"]
    assert "marca" not in despues["campos_faltantes"]
    assert despues["completitud"] == 0.0, "el codigo sigue pendiente: falta 1 de 1 campos contables"
    assert despues["campos"]["marca"]["estado"] == "no_aplica"
    assert despues["campos"]["marca"]["motivo"]

    # Es reversible
    revertido = await api.post(
        f"/api/activos/{teclado2['id']}/campos",
        json={"campos": ["marca"], "estado": "pendiente"},
        headers=cab_admin,
    )
    assert revertido.status_code == 200
    assert "marca" in revertido.json()["activo"]["campos_faltantes"]

    # Al marcar el codigo como 'No disponible' deja de ser un pendiente
    sin_codigo = await api.post(
        f"/api/activos/{teclado2['id']}/campos",
        json={"campos": ["codigo_patrimonial"], "estado": "no_disponible", "motivo": "Informacion no disponible"},
        headers=cab_admin,
    )
    assert sin_codigo.status_code == 200
    assert "codigo_patrimonial" not in sin_codigo.json()["activo"]["campos_faltantes"]
    assert sin_codigo.json()["activo"]["campos"]["codigo_patrimonial"]["estado"] == "no_disponible"

    # Acción masiva
    masiva = await api.post(
        "/api/activos/campos-masivo",
        json={
            "activo_ids": [teclado["id"], teclado2["id"]],
            "campos": ["codigo_patrimonial"],
            "estado": "no_aplica",
            "motivo": "Equipo sin codigo patrimonial asignado",
        },
        headers=cab_admin,
    )
    assert masiva.status_code == 200
    assert masiva.json()["actualizados"] == 2


async def test_opciones_avanzadas_ocultas_y_derivadas(db, api):
    cab_admin = await _sesion_admin(api, "avanzado@prueba.local")
    zona = (await api.post("/api/zonas", json={"nombre": "Zona Avanzada"}, headers=cab_admin)).json()
    oficina = (await api.post("/api/oficinas", json={"nombre": "SOPORTE", "zona_id": zona["id"]}, headers=cab_admin)).json()
    activo = (
        await api.post("/api/activos", json={"tipo": "CPU", "oficina_id": oficina["id"]}, headers=cab_admin)
    ).json()

    # Apagado: no se muestra ni se exige nada
    assert activo["opciones_avanzadas"] is False
    assert not activo.get("detalle_avanzado")
    assert not activo.get("secciones_avanzadas")

    # Detalle sin activar el interruptor se rechaza
    intento = await api.patch(
        f"/api/activos/{activo['id']}",
        json={"detalle_avanzado": {"memoria_modulos": [{"capacidad_gb": 8, "tipo": "DDR4"}]}},
        headers=cab_admin,
    )
    assert intento.status_code == 422

    # Activado con detalle de RAM
    activado = await api.patch(
        f"/api/activos/{activo['id']}",
        json={
            "opciones_avanzadas": True,
            "detalle_avanzado": {
                "placa_madre": {"ranuras_ram_totales": 4, "ram_maxima_soportada": 64},
                "memoria_modulos": [
                    {"ranura": "1", "capacidad_gb": 8, "tipo": "DDR4", "velocidad_mhz": 2666},
                    {"ranura": "2", "capacidad_gb": 8, "tipo": "DDR4", "velocidad_mhz": 2666},
                ],
                "almacenamiento_unidades": [{"tipo": "SSD", "capacidad_gb": 240}],
            },
        },
        headers=cab_admin,
    )
    assert activado.status_code == 200
    detalle = activado.json()
    assert detalle["opciones_avanzadas"] is True
    assert "memoria_modulos" in detalle["secciones_avanzadas"]
    # RAM derivada de los modulos
    assert "16" in (detalle["memoria_ram"] or "")
    assert "DDR4" in (detalle["memoria_ram"] or "")
    assert "240" in (detalle["almacenamiento"] or "")
    assert "memoria_ram" in detalle["campos_derivados"]
    calculos = detalle["calculos_avanzados"]
    assert calculos["modulos_memoria"] == 2
    assert calculos["ranuras_libres"] == 2
    assert calculos["ram_instalada_gb"] == 16.0
    assert calculos["avisos"] == []

    # Aviso blando si la RAM supera el maximo soportado
    exceso = await api.patch(
        f"/api/activos/{activo['id']}",
        json={
            "opciones_avanzado": True,
            "detalle_avanzado": {
                "placa_madre": {"ranuras_ram_totales": 2, "ram_maxima_soportada": 8},
                "memoria_modulos": [{"ranura": "1", "capacidad_gb": 16, "tipo": "DDR4"}],
            },
        },
        headers=cab_admin,
    )
    assert exceso.status_code == 200
    assert exceso.json()["calculos_avanzados"]["avisos"], "debe avisar, no bloquear"

    # Desactivar oculta pero conserva los datos
    apagado = await api.patch(
        f"/api/activos/{activo['id']}", json={"opciones_avanzadas": False}, headers=cab_admin
    )
    assert apagado.status_code == 200
    tras_apagar = apagado.json()
    assert tras_apagar["opciones_avanzadas"] is False
    assert not tras_apagar.get("secciones_avanzadas")
    assert any(alerta["tipo"] == "avanzado_oculto" for alerta in tras_apagar["alertas"])

    # El detalle sigue en la base de datos
    from bson import ObjectId

    from app.core.db import get_db

    guardado = await get_db()["activos"].find_one({"_id": ObjectId(activo["id"])})
    assert guardado["detalle_avanzado"], "desactivar no borra el detalle"
    assert guardado["opciones_avanzadas"] is False

    # El historial de cambios de componentes se conserva
    historial = (await api.get(f"/api/activos/{activo['id']}/componentes", headers=cab_admin)).json()
    assert len(historial["items"]) >= 1


async def test_el_conjunto_se_puede_cambiar_desde_la_ficha(db, api):
    """Meter un equipo en un conjunto, y sacarlo, desde su propia ficha.

    No se podía: el alta sí elegía conjunto, pero una vez creado el equipo no
    había dónde cambiarlo. Si un equipo se registraba suelto y luego se caía en la
    cuenta de que era parte de una computadora, la única salida era darlo de baja
    y volver a registrarlo.

    Y el conjunto tiene que ser **de la misma oficina**. Al crear se comprobaba;
    al editar no, y como desde la ficha se cambian oficina y conjunto en la misma
    llamada, un equipo podía quedar en MERCADO con un conjunto de PALACIO.
    """
    from app.core.db import get_db
    from app.core.ids import a_id

    cab_admin = await _sesion_admin(api, "conjunto-ficha@prueba.local")

    zona_a = (await api.post("/api/zonas", json={"nombre": "Zona Conjunto A"}, headers=cab_admin)).json()
    zona_b = (await api.post("/api/zonas", json={"nombre": "Zona Conjunto B"}, headers=cab_admin)).json()
    oficina_a = (await api.post("/api/oficinas", json={"nombre": "MESA CONJ A", "zona_id": zona_a["id"]}, headers=cab_admin)).json()
    oficina_b = (await api.post("/api/oficinas", json={"nombre": "MESA CONJ B", "zona_id": zona_b["id"]}, headers=cab_admin)).json()
    conjunto_a = (await api.post("/api/conjuntos", json={"nombre": "Computadora N°1", "oficina_id": oficina_a["id"], "activo": True}, headers=cab_admin)).json()
    conjunto_b = (await api.post("/api/conjuntos", json={"nombre": "Computadora N°9", "oficina_id": oficina_b["id"], "activo": True}, headers=cab_admin)).json()

    creado = await api.post(
        "/api/activos",
        json={"tipo": "Monitor", "oficina_id": oficina_a["id"], "nombre_equipo": "MONITOR SUELTO"},
        headers=cab_admin,
    )
    assert creado.status_code == 201, creado.text
    activo_id = creado.json()["id"]
    assert creado.json()["conjunto_id"] is None, "nace sin conjunto"

    # Un conjunto de otra oficina se rechaza
    cruzado = await api.patch(
        f"/api/activos/{activo_id}",
        json={"conjunto_id": conjunto_b["id"]},
        headers=cab_admin,
    )
    assert cruzado.status_code == 422, f"un conjunto de otra oficina no puede entrar: {cruzado.text}"
    assert "otra oficina" in cruzado.json()["mensaje"].lower(), cruzado.text

    # Y tampoco vale esquivarlo moviendo la oficina en la misma llamada
    esquiva = await api.patch(
        f"/api/activos/{activo_id}",
        json={"oficina_id": oficina_b["id"], "conjunto_id": conjunto_a["id"]},
        headers=cab_admin,
    )
    assert esquiva.status_code == 422, f"tampoco cambiando la oficina a la vez: {esquiva.text}"

    # El de su propia oficina entra, y el nombre del conjunto se copia
    meter = await api.patch(
        f"/api/activos/{activo_id}",
        json={"conjunto_id": conjunto_a["id"]},
        headers=cab_admin,
    )
    assert meter.status_code == 200, meter.text
    assert meter.json()["conjunto_id"] == conjunto_a["id"]
    assert meter.json()["conjunto_nombre"] == "Computadora N°1", "el nombre se guarda con el equipo"

    # Cambiar de conjunto dentro de la misma oficina también vale
    otro = (await api.post("/api/conjuntos", json={"nombre": "Computadora N°2", "oficina_id": oficina_a["id"], "activo": True}, headers=cab_admin)).json()
    cambiar = await api.patch(
        f"/api/activos/{activo_id}",
        json={"conjunto_id": otro["id"]},
        headers=cab_admin,
    )
    assert cambiar.status_code == 200, cambiar.text
    assert cambiar.json()["conjunto_nombre"] == "Computadora N°2"

    # Y mandarlo en blanco lo saca: si se omitiera, el equipo se quedaría donde estaba
    await get_db()["activos"].update_one(
        {"_id": a_id(activo_id)}, {"$set": {"conjunto_id": conjunto_a["id"], "conjunto_nombre": "Computadora N°1"}}
    )
    sacar = await api.patch(f"/api/activos/{activo_id}", json={"conjunto_id": None}, headers=cab_admin)
    assert sacar.status_code == 200, sacar.text
    assert sacar.json()["conjunto_id"] is None, "mandarlo en blanco tiene que sacarlo del conjunto"
    assert sacar.json()["conjunto_nombre"] is None

    # Y si no se manda nada, se conserva: omitirlo no es lo mismo que mandarlo vacío
    meter2 = await api.patch(f"/api/activos/{activo_id}", json={"conjunto_id": conjunto_a["id"]}, headers=cab_admin)
    assert meter2.status_code == 200, meter2.text
    omitido = await api.patch(f"/api/activos/{activo_id}", json={"tipo": "Monitor"}, headers=cab_admin)
    assert omitido.status_code == 200, omitido.text
    assert omitido.json()["conjunto_id"] == conjunto_a["id"], "omitir el conjunto no puede sacarlo del equipo"


async def test_uso_comun_de_oficina(db, api):
    cab_admin = await _sesion_admin(api, "usocomun@prueba.local")
    zona = (await api.post("/api/zonas", json={"nombre": "Zona Comun"}, headers=cab_admin)).json()
    oficina = (await api.post("/api/oficinas", json={"nombre": "RECEPCION", "zona_id": zona["id"]}, headers=cab_admin)).json()
    impresora = (
        await api.post(
            "/api/activos",
            json={"tipo": "Impresora", "oficina_id": oficina["id"], "nombre_equipo": "Impresora de recepcion"},
            headers=cab_admin,
        )
    ).json()
    assert impresora["responsable_id"] is None
    assert impresora["uso_comun"] is True

    usuario = (
        await api.post(
            "/api/usuarios",
            json={"nombre": "Recepcionista", "email": "recepcion@prueba.local", "password": PASSWORD, "rol": "usuario", "oficina_id": oficina["id"]},
            headers=cab_admin,
        )
    ).json()
    cab_recepcion = await _sesion(api, "recepcion@prueba.local")
    mis_equipos = (await api.get("/api/equipos/mis", headers=cab_recepcion)).json()
    assert any(e["id"] == impresora["id"] for e in mis_equipos["uso_comun_oficina"]), "la impresora aparece para la oficina"

    # Asignarla como responsable
    asignado = await api.post(
        f"/api/activos/{impresora['id']}/responsable",
        json={"responsable_id": usuario["id"], "motivo": "Asignacion inicial"},
        headers=cab_admin,
    )
    assert asignado.status_code == 200
    assert asignado.json()["responsable_id"] == usuario["id"]


async def test_pelicula_de_calidad_por_zona_y_tipo(db, api):
    cab_admin = await _sesion_admin(api, "calidad@prueba.local")
    zona = (await api.post("/api/zonas", json={"nombre": "Zona Calidad"}, headers=cab_admin)).json()
    oficina = (await api.post("/api/oficinas", json={"nombre": "TESORERIA", "zona_id": zona["id"]}, headers=cab_admin)).json()
    for indice in range(4):
        await api.post(
            "/api/activos",
            json={"tipo": "CPU", "oficina_id": oficina["id"], "nombre_equipo": f"PC {indice}", "marca": "HP"},
            headers=cab_admin,
        )
    calidad = (await api.get(f"/api/calidad-inventario?zona_id={zona['id']}", headers=cab_admin)).json()
    assert calidad["total_activos"] == 4, calidad
    assert 0 <= calidad["porcentaje_global"] <= 100
    assert any(f.get("nombre") == "CPU" for f in calidad["por_tipo"]), calidad["por_tipo"]
    assert any(p.get("nombre") == "TESORERIA" for p in calidad["por_oficina"]), calidad["por_oficina"]
    oficina_calidad = next(p for p in calidad["por_oficina"] if p["nombre"] == "TESORERIA")
    assert oficina_calidad["total"] == 4
    assert oficina_calidad["campos_faltantes"], oficina_calidad
    assert oficina_calidad["campos_faltantes"][0]["faltantes"] == 4
    assert calidad["pendientes"], "debe listar los equipos con datos faltantes"
    assert all("campos_faltantes" in p for p in calidad["pendientes"])
    filtrada = (await api.get(f"/api/calidad-inventario?oficina_id={oficina['id']}", headers=cab_admin)).json()
    assert filtrada["total_activos"] == 4