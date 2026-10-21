"""Historial privado del chatbot TI. Cuota y exclusión mutua se imponen en MongoDB."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from pymongo import ReturnDocument

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import Conflicto, NoEncontrado, Validacion
from app.core.ids import id_requerido
from app.core.time import utcnow
from app.services import chatbot_service

COLECCION = 'chatbot_conversaciones'


def limite(usuario):
    # También acotar el tamaño máximo del documento de administradores.
    return max(1, min(100, settings.chatbot_limite_consultas_tecnico)) if usuario['rol'] == 'tecnico' else 100


def salida(doc, usuario, *, mensajes=True):
    return {'id': str(doc['_id']), 'titulo': doc['titulo'],
            'actualizado_en': doc['actualizado_en'].isoformat(),
            'consumo': doc.get('consumo', {'consultas': 0, 'tokens': 0, 'conTokens': 0}),
            'limite': limite(usuario),
            'en_curso': bool(doc.get('ocupado_hasta') and doc['ocupado_hasta'] > utcnow()),
            **({'mensajes': doc.get('mensajes', [])} if mensajes else {})}


async def crear(usuario, titulo='Nueva conversación'):
    chatbot_service.exigir_ti(usuario)
    coleccion = get_db()[COLECCION]
    if await coleccion.count_documents({'usuario_id': usuario['_id']}) >= 100:
        raise Validacion('Tienes 100 conversaciones guardadas. Elimina alguna para crear otra.')
    ahora = utcnow()
    doc = {'usuario_id': usuario['_id'], 'titulo': titulo[:80], 'mensajes': [],
           'consumo': {'consultas': 0, 'tokens': 0, 'conTokens': 0},
           'creado_en': ahora, 'actualizado_en': ahora}
    doc['_id'] = (await coleccion.insert_one(doc)).inserted_id
    return salida(doc, usuario)


async def listar(usuario):
    chatbot_service.exigir_ti(usuario)
    documentos = await get_db()[COLECCION].find({'usuario_id': usuario['_id']}, {'mensajes': 0}).sort('actualizado_en', -1).limit(100).to_list(100)
    return {'items': [salida(doc, usuario, mensajes=False) for doc in documentos]}


async def obtener(identificador, usuario):
    chatbot_service.exigir_ti(usuario)
    doc = await get_db()[COLECCION].find_one({'_id': id_requerido(identificador), 'usuario_id': usuario['_id']})
    if not doc:
        raise NoEncontrado('La conversación no existe o no pertenece a tu cuenta.')
    return salida(doc, usuario)


async def eliminar(identificador, usuario):
    chatbot_service.exigir_ti(usuario)
    resultado = await get_db()[COLECCION].delete_one({'_id': id_requerido(identificador), 'usuario_id': usuario['_id']})
    if not resultado.deleted_count:
        raise NoEncontrado('La conversación no existe o no pertenece a tu cuenta.')
    return {'eliminada': True}


async def consultar(datos, usuario):
    chatbot_service.exigir_ti(usuario)
    if not chatbot_service.estado(usuario)['configurado']:
        return await chatbot_service.responder(datos.pregunta, [], usuario)
    identificador = datos.conversacion_id
    if not identificador:
        identificador = (await crear(usuario, datos.pregunta))['id']
    consulta = {'_id': id_requerido(identificador), 'usuario_id': usuario['_id']}
    coleccion = get_db()[COLECCION]
    reserva = uuid4().hex
    ahora = utcnow()
    doc = await coleccion.find_one_and_update(
        {**consulta, 'consumo.consultas': {'$lt': limite(usuario)},
         '$or': [{'ocupado_hasta': {'$exists': False}}, {'ocupado_hasta': {'$lt': ahora}}]},
        {'$inc': {'consumo.consultas': 1}, '$set': {'reserva': reserva, 'ocupado_hasta': ahora + timedelta(minutes=3), 'actualizado_en': ahora}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        existente = await obtener(identificador, usuario)
        if existente['consumo']['consultas'] >= limite(usuario):
            raise Validacion(f'Esta conversación alcanzó el límite de {limite(usuario)} consultas. Puedes iniciar una nueva.', codigo='limite_chatbot')
        raise Conflicto('Hay una consulta en curso en esta conversación. Espera a que termine.')
    condicion = {**consulta, 'reserva': reserva}
    try:
        # Historial del servidor: el cliente no puede sustituir mensajes guardados.
        historial = [SimpleNamespace(rol=m['rol'], texto=m['texto']) for m in doc['mensajes'][-6:]]
        respuesta = await chatbot_service.responder(datos.pregunta, historial, usuario, pagina=datos.pagina, filtros_pagina=datos.filtros)
        uso = respuesta.get('uso') or {}
        incremento = {'consumo.tokens': int(uso.get('total') or 0), 'consumo.conTokens': 1 if uso else 0}
        cambio = {'$inc': incremento, '$set': {'actualizado_en': utcnow()}}
        if respuesta['disponible']:
            cambio['$push'] = {'mensajes': {'$each': [
                {'rol': 'user', 'texto': datos.pregunta},
                {'rol': 'assistant', 'texto': respuesta['texto'], 'fuentes': respuesta.get('fuentes', [])},
            ]}}
        guardada = await coleccion.find_one_and_update(condicion, cambio, return_document=ReturnDocument.AFTER)
        # Un borrado concurrente jamás recrea una conversación eliminada.
        if guardada:
            respuesta.update(conversacion_id=identificador, consumo=guardada['consumo'], limite=limite(usuario))
        return respuesta
    finally:
        await coleccion.update_one(condicion, {'$unset': {'reserva': '', 'ocupado_hasta': ''}})
