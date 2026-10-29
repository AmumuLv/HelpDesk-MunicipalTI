"""Destino real de una incidencia: componente y su PC, o solamente la PC."""
from app.core.db import get_db
from app.core.errors import NoEncontrado, Prohibido, Validacion
from app.core.ids import id_requerido, normalizar_texto, clave
from app.services.historial_inventario_service import opciones_ticket
from app.domain.equipos import componente_escritorio, equipo_informatico


def categoria_de_pc(categoria):
    texto = clave(categoria or '').lower()
    return any(p in texto for p in ('programa', 'sistema', 'software', 'correo', 'cuenta')) and 'formate' not in texto


async def resolver(ticket, datos, usuario, *, creacion=False):
    campos = {'activo_id', 'conjunto_id', 'alcance_incidencia', 'sistema_afectado', 'categoria'}
    if not campos.intersection(datos):
        return {}
    if not creacion and usuario.get('rol') not in {'tecnico', 'administrador'}:
        raise Prohibido('El equipo TI identifica el equipo afectado.')
    db = get_db()
    if not creacion and not (ticket.get('activo_id') or ticket.get('conjunto_id')) and not {'activo_id', 'conjunto_id'}.intersection(datos):
        return {'alcance_incidencia': 'pendiente',
                'sistema_afectado': normalizar_texto(datos.get('sistema_afectado', ticket.get('sistema_afectado'))) or None}
    if creacion and datos.get('reporte_para') == 'oficina':
        tipo = normalizar_texto(datos.get('activo_no_identificado')) or None
        return {'activo_id': None, 'conjunto_id': None, 'activo_nombre': tipo,
                'activo_tipo': tipo, 'conjunto_nombre': None, 'activo_no_identificado': tipo,
                'alcance_incidencia': 'pendiente', 'vinculo_origen': 'oficina'}
    if creacion and usuario.get('rol') == 'usuario' and (
        not (datos.get('persona') or {}).get('es_para_mi', True)
        or not (datos.get('activo_id') or datos.get('conjunto_id'))
    ):
        return {'activo_id': None, 'conjunto_id': None, 'activo_nombre': None, 'activo_tipo': None,
                'conjunto_nombre': None, 'activo_no_identificado': None, 'alcance_incidencia': 'pendiente',
                'sistema_afectado': normalizar_texto(datos.get('sistema_afectado')) or None,
                'vinculo_origen': None}
    corregir_origen = not creacion and datos.get('corregir_origen') is True
    opciones = await opciones_ticket(ticket, corregir_origen=corregir_origen)
    equipos = {e['id']: e for e in opciones['equipos']}
    conjuntos = {c['id']: c for c in opciones['conjuntos']}
    activo_id = datos.get('activo_id', ticket.get('activo_id'))
    conjunto_id = datos.get('conjunto_id', ticket.get('conjunto_id'))
    categoria = datos.get('categoria', ticket.get('categoria'))
    programa = categoria_de_pc(categoria)
    activo = None
    if activo_id:
        if str(activo_id) not in equipos:
            raise Validacion('Elige un equipo de la persona afectada. No puedes cambiar el origen seleccionado por un equipo compartido o ajeno.')
        activo = await db.activos.find_one({'_id': id_requerido(activo_id, 'equipo'), 'activo': {'$ne': False}})
        if not activo:
            raise NoEncontrado('El equipo ya no está disponible. Actualiza la lista.')
        if datos.get('activo_id') and datos.get('conjunto_id') and str(datos['conjunto_id']) != str(activo.get('conjunto_id')):
            raise Validacion('El componente y la computadora seleccionados no coinciden.')
        conjunto_id = activo.get('conjunto_id') if componente_escritorio(activo.get('tipo')) else None
    if programa:
        if activo and not conjunto_id and not equipo_informatico(activo.get('tipo')):
            raise Validacion('Selecciona la computadora de escritorio o laptop donde falla el programa.')
        if not conjunto_id and not activo:
            personales = [c for c in conjuntos.values() if c['grupo'] == 'propios']
            individuales = [e for e in equipos.values() if e['grupo'] == 'propios' and not e.get('conjunto_id') and equipo_informatico(e.get('tipo'))]
            if len(personales) + len(individuales) == 1 and personales:
                conjunto_id = personales[0]['id']
            elif len(personales) + len(individuales) == 1:
                activo = await db.activos.find_one({'_id': id_requerido(individuales[0]['id'], 'equipo'), 'activo': {'$ne': False}})
        if conjunto_id:
            activo = None
    if conjunto_id and str(conjunto_id) not in conjuntos:
        raise Validacion('Elige una computadora asignada a esta persona y conserva el origen del registro.')
    conjunto = await db.conjuntos.find_one({'_id': id_requerido(conjunto_id, 'conjunto')}) if conjunto_id else None
    if not activo and not conjunto:
        # El portal conserva la posibilidad de pedir ayuda sin inventar un equipo.
        # TI debe identificar el patrimonio antes de registrar o completar su ficha.
        if creacion and usuario.get('rol') == 'usuario':
            return {'activo_id': None, 'conjunto_id': None, 'activo_nombre': None, 'activo_tipo': None,
                    'conjunto_nombre': None, 'activo_no_identificado': None, 'alcance_incidencia': 'pendiente'}
        raise Validacion('Selecciona un equipo o una computadora real de la persona. Si no tiene ninguno, asígnalo primero en Inventario.')
    if categoria and 'formate' in clave(categoria).lower() and (not activo or clave(activo.get('tipo', '')).lower() not in {'cpu', 'laptop', 'computadora', 'pc'}):
        raise Validacion('Para un formateo selecciona el CPU o la laptop correspondiente.')
    grupo = opciones.get('grupo_bloqueado') or (equipos[str(activo['_id'])]['grupo'] if activo else conjuntos[str(conjunto['_id'])]['grupo'])
    return {'activo_id': activo['_id'] if activo else None,
            'activo_nombre': (activo.get('nombre_equipo') or activo.get('tipo')) if activo else None,
            'activo_tipo': activo.get('tipo') if activo else None, 'activo_no_identificado': None,
            'conjunto_id': conjunto['_id'] if conjunto else None,
            'conjunto_nombre': conjunto.get('nombre') if conjunto else None,
            'alcance_incidencia': 'programa' if programa else 'equipo' if activo else 'conjunto',
            'sistema_afectado': normalizar_texto(datos.get('sistema_afectado', ticket.get('sistema_afectado'))) or None,
            'vinculo_origen': grupo}
