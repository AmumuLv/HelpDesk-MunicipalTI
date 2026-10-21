from datetime import timedelta

from bson import ObjectId

from app.core.time import utcnow
from tests.test_tickets_horarios import _mundo


async def test_listados_recientes_antes_de_paginar_y_edicion_no_sube_registro(db, api):
    mundo = await _mundo(api, 'orden-recientes')
    cab = mundo['admin']
    ahora = utcnow()
    antiguos = []
    nuevos = []
    for indice, nombre in enumerate(['AAA antiguo', 'ZZZ reciente']):
        usuario = await api.post('/api/usuarios', headers=cab, json={
            'nombre': nombre, 'email': f'orden-{indice}@prueba.local',
            'password': 'Prueba12345!', 'rol': 'tecnico', 'oficina_id': mundo['oficina']['id'],
        })
        assert usuario.status_code == 201, usuario.text
        persona = usuario.json()
        equipo = await api.post('/api/activos', headers=cab, json={
            'tipo': 'Monitor', 'nombre_equipo': nombre, 'oficina_id': mundo['oficina']['id'],
        })
        assert equipo.status_code == 201, equipo.text
        fecha = ahora - timedelta(days=1 - indice)
        for coleccion, entidad in [('usuarios', persona), ('activos', equipo.json())]:
            await db[coleccion].update_one({'_id': ObjectId(entidad['id'])}, {'$set': {'creado_en': fecha, 'actualizado_en': ahora + timedelta(days=5 if indice == 0 else 0)}})
        (antiguos if indice == 0 else nuevos).extend([persona['id'], equipo.json()['id']])

    for ruta, esperado in [('/api/usuarios?texto=reciente&por_pagina=1', nuevos[0]), ('/api/activos?por_pagina=1', nuevos[1])]:
        respuesta = await api.get(ruta, headers=cab)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()['items'][0]['id'] == esperado
    usuarios = (await api.get('/api/usuarios?por_pagina=1', headers=cab)).json()
    assert usuarios['items'][0]['id'] == nuevos[0]
    equipos = (await api.get('/api/activos?por_pagina=1&pagina=2', headers=cab)).json()
    assert equipos['items'][0]['id'] == antiguos[1]
    panel = (await api.get('/api/equipo-ti/panel', headers=cab))
    assert panel.status_code == 200, panel.text
    assert panel.json()['items'][0]['tecnico_id'] == nuevos[0]

    # Empates de fecha: el identificador de creación estabiliza la paginación.
    await db['activos'].update_many({}, {'$set': {'creado_en': ahora}})
    equipos = (await api.get('/api/activos?por_pagina=1', headers=cab)).json()
    assert equipos['items'][0]['id'] == nuevos[1]
    ubicacion = await api.get('/api/activos?orden=ubicacion', headers=cab)
    assert ubicacion.status_code == 200
    oficina = await api.post('/api/oficinas', headers=cab, json={'nombre': 'ZZZ oficina nueva', 'zona_id': mundo['zona']['id']})
    assert oficina.status_code == 201, oficina.text
    oficinas = (await api.get(f"/api/oficinas?zona_id={mundo['zona']['id']}", headers=cab)).json()['items']
    assert oficinas[0]['id'] == oficina.json()['id']
