"""Historial por identidad del equipo, sin reescribir quién reportó cada caso."""
from app.core.db import get_db
from app.domain.equipos import componente_escritorio


async def tipos_oficina(oficina_id):
    if not oficina_id:
        return []
    from app.core.ids import clave, normalizar_texto
    tipos = await get_db().activos.distinct('tipo', {'oficina_id': oficina_id, 'responsable_id': None, 'activo': {'$ne': False}})
    unicos = {clave(t): normalizar_texto(t) for t in tipos if t and normalizar_texto(t)}
    return sorted(unicos.values(), key=clave)


async def consulta_conjunto(conjunto_id):
    equipos = await get_db().activos.distinct('_id', {'conjunto_id': conjunto_id})
    return {'$or': [{'conjunto_id': conjunto_id}, {'activo_id': {'$in': equipos}}]}


async def inventario_persona(usuario_id):
    db = get_db()
    equipos = await db.activos.find({'responsable_id': usuario_id, 'activo': {'$ne': False}}).to_list(None)
    conjuntos_ids = {e['conjunto_id'] for e in equipos if e.get('conjunto_id')}
    conjuntos = await db.conjuntos.find({'activo': {'$ne': False}, '$or': [
        {'responsable_id': usuario_id}, {'_id': {'$in': list(conjuntos_ids)}}]}).to_list(None)
    return equipos, conjuntos


async def opciones_ticket(ticket, *, corregir_origen=False):
    db = get_db()
    persona = ticket.get('afectado_id') or ticket.get('reportante_id')
    oficina = ticket.get('oficina_id')
    if not persona:
        return {'equipos': [], 'conjuntos': []}
    consulta = {'activo': {'$ne': False}, '$or': [{'responsable_id': persona}]}
    if oficina:
        consulta['$or'].append({'oficina_id': oficina, 'responsable_id': None})
    equipos = await db.activos.find(consulta).sort([('nombre_equipo', 1), ('_id', 1)]).to_list(None)
    if oficina:
        equipos = [e for e in equipos if e.get('oficina_id') == oficina]
    ids = {e['conjunto_id'] for e in equipos if e.get('conjunto_id') and componente_escritorio(e.get('tipo'))}
    conjuntos = await db.conjuntos.find({'activo': {'$ne': False}, '$or': [
        {'_id': {'$in': list(ids)}}, {'responsable_id': persona}]}).to_list(None)
    ajenos = set(await db.activos.distinct('conjunto_id', {
        'conjunto_id': {'$in': [c['_id'] for c in conjuntos]}, 'activo': {'$ne': False},
        'responsable_id': {'$nin': [None, persona]},
    }))
    permitidos = []
    for conjunto in conjuntos:
        if conjunto['_id'] not in ids:
            continue
        if oficina and conjunto.get('oficina_id') != oficina:
            continue
        if conjunto.get('responsable_id') not in (None, persona):
            continue
        if conjunto['_id'] not in ajenos:
            permitidos.append(conjunto)
    grupo_bloqueado = None if corregir_origen else ticket.get('vinculo_origen')
    if not corregir_origen and not grupo_bloqueado and (ticket.get('activo_id') or ticket.get('conjunto_id')):
        origen = await db.activos.find_one({'_id': ticket['activo_id']}) if ticket.get('activo_id') else await db.conjuntos.find_one({'_id': ticket.get('conjunto_id')})
        if origen:
            grupo_bloqueado = 'propios' if origen.get('responsable_id') == persona or any(e.get('conjunto_id') == origen['_id'] and e.get('responsable_id') == persona for e in equipos) else 'oficina'
    salida = {'equipos': [{'id': str(e['_id']), 'nombre': e.get('nombre_equipo') or e.get('tipo', 'Equipo'),
                         'tipo': e.get('tipo'), 'conjunto_id': str(e['conjunto_id']) if e.get('conjunto_id') and componente_escritorio(e.get('tipo')) else None,
                         'codigo': e.get('codigo_patrimonial'), 'grupo': 'propios' if e.get('responsable_id') == persona else 'oficina'} for e in equipos],
            'conjuntos': [{'id': str(c['_id']), 'nombre': c.get('nombre', 'Computadora'),
                           'grupo': 'propios' if c.get('responsable_id') == persona or any(e.get('conjunto_id') == c['_id'] and e.get('responsable_id') == persona for e in equipos) else 'oficina'} for c in permitidos], 'grupo_bloqueado': grupo_bloqueado}
    if grupo_bloqueado:
        for campo in ('equipos', 'conjuntos'):
            salida[campo] = [item for item in salida[campo] if item['grupo'] == grupo_bloqueado]
    return salida
