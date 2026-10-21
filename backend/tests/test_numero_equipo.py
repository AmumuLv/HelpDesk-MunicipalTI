from bson import ObjectId
from tests.test_tickets_horarios import _mundo


async def test_tres_componentes_nuevo_cuarto_y_numero_en_ficha(db, api):
    mundo = await _mundo(api, 'numero-componente')
    cab = mundo['admin']
    grupo = (await api.post('/api/conjuntos', headers=cab, json={'oficina_id': mundo['oficina']['id'], 'nombre': 'Computadora N°1'})).json()
    creados = []
    for tipo in ['CPU', 'Teclado', 'Mouse']:
        r = await api.post('/api/activos', headers=cab, json={'tipo': tipo, 'oficina_id': mundo['oficina']['id'], 'conjunto_id': grupo['id']})
        assert r.status_code == 201, r.text
        creados.append(r.json())
    lista = (await api.get(f"/api/conjuntos?oficina_id={mundo['oficina']['id']}", headers=cab)).json()['items'][0]
    assert lista['total_activos'] == 3 and lista['siguiente_numero_equipo'] == 4
    assert [a['numero_equipo'] for a in creados] == [1, 2, 3]
    nuevo = await api.post('/api/activos', headers=cab, json={'tipo': 'Monitor', 'oficina_id': mundo['oficina']['id'], 'conjunto_id': grupo['id']})
    assert nuevo.status_code == 201 and nuevo.json()['numero_equipo'] == 4
    for _ in range(2):
        ficha = (await api.get(f"/api/activos/{nuevo.json()['id']}", headers=cab)).json()
        assert ficha['numero_equipo'] == 4
    # Editar el mismo conjunto no reasigna el número.
    cambio = await api.patch(f"/api/activos/{nuevo.json()['id']}", headers=cab, json={'conjunto_id': grupo['id'], 'modelo': 'Modelo actualizado'})
    assert cambio.status_code == 200 and cambio.json()['numero_equipo'] == 4


async def test_migracion_numera_existentes_y_reserva_concurrente_no_duplica(db, api):
    import asyncio
    from app.migrations.m023_numero_equipo import aplicar
    from app.services import inventario_service
    mundo = await _mundo(api, 'numero-migracion')
    grupo = (await api.post('/api/conjuntos', headers=mundo['admin'], json={'oficina_id': mundo['oficina']['id'], 'nombre': 'Computadora N°1'})).json()
    gid = ObjectId(grupo['id'])
    for tipo in ['CPU', 'Teclado', 'Mouse']:
        r = await api.post('/api/activos', headers=mundo['admin'], json={'tipo': tipo, 'conjunto_id': grupo['id'], 'oficina_id': mundo['oficina']['id']})
        assert r.status_code == 201, r.text
    await db['activos'].update_many({'conjunto_id': gid}, {'$unset': {'numero_equipo': ''}})
    await db['conjuntos'].update_one({'_id': gid}, {'$unset': {'ultimo_numero_equipo': ''}})
    await aplicar(db)
    numeros = [e['numero_equipo'] for e in await db['activos'].find({'conjunto_id': gid}).to_list(None)]
    assert sorted(numeros) == [1, 2, 3]
    await aplicar(db)
    asignados = await asyncio.gather(*(inventario_service.asignar_numero_equipo(gid) for _ in range(4)))
    assert sorted(asignados) == [4, 5, 6, 7]
