"""Ambos asistentes explican el relevo verificado sin consumir proveedor ni tokens."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services import analitica_chat, chatbot_service
from app.services.ayuda_analisis import responder_ayuda
from app.services.conocimiento_proyecto import (
    GUIA_IMPORTACION_RELEVO,
    contexto_proyecto,
    trata_importacion_relevo,
)


@pytest.fixture(scope='session', autouse=True)
def mongo_replica_set():
    """Estas unitarias sustituyen el autouse de integración de conftest."""
    yield None


@pytest.fixture(autouse=True)
def sin_servicios_externos(monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError('Esta prueba no debe consultar Mongo ni un proveedor real')

    monkeypatch.setattr(chatbot_service, 'get_db', prohibido)
    monkeypatch.setattr(analitica_chat, 'get_db', prohibido)
    monkeypatch.setattr(analitica_chat.ia_provider, 'obtener_proveedor', prohibido)
    monkeypatch.setattr(httpx, 'AsyncClient', prohibido)


@pytest.mark.parametrize('pregunta', [
    '¿El Excel actualizado reasigna los equipos?',
    '¿Cómo funciona la importación?',
    '¿Qué pasa si importo sin crear perfiles?',
    '¿Cómo hago el relevo de trabajador?',
    '¿Cómo cambiar el responsable de una PC?',
    'Cambio del responsable de una laptop',
    '¿Cómo reemplazo a un trabajador?',
    '¿Puedo crear un usuario nuevo con sus equipos?',
    '¿El trabajador nuevo recibe el inventario anterior?',
    '¿Crear una cuenta nueva transfiere los equipos?',
])
def test_contexto_selecciona_flujo_verificado(pregunta):
    assert trata_importacion_relevo(pregunta)
    assert GUIA_IMPORTACION_RELEVO.strip() in contexto_proyecto(pregunta, [])


def test_contexto_recupera_relevo_del_historial_sin_seleccionarlo_por_defecto():
    historial = [SimpleNamespace(rol='user', texto='Voy a importar el Excel del reemplazo'),
                 SimpleNamespace(rol='assistant', texto='Revisa la vista previa.')]
    assert GUIA_IMPORTACION_RELEVO.strip() in contexto_proyecto('¿Y si no existe esa persona?', historial)
    assert GUIA_IMPORTACION_RELEVO.strip() not in contexto_proyecto('¿Qué significa el SLA?', [])
    assert not trata_importacion_relevo('¿Qué es lo importante del SLA?')


@pytest.mark.parametrize('pregunta', [
    '¿El Excel actualizado reasigna los mismos equipos al nuevo trabajador?',
    '¿Debo cambiar el responsable uno por uno después de importar?',
    '¿Cómo reasigno los equipos del usuario anterior al nuevo?',
    '¿Crear una cuenta nueva transfiere los equipos?',
])
def test_ayuda_explica_relevo_por_filas_validas_y_conserva_identidades(pregunta):
    respuesta = responder_ayuda(pregunta)
    assert 'Equipos → Importar' in respuesta
    assert 'No hace falta moverlos después uno por uno' in respuesta
    assert 'persona anterior → persona nueva' in respuesta
    assert 'usuarios.editar' in respuesta
    assert 'sin correo ni contraseña' in respuesta
    assert 'filas válidas' in respuesta and 'omitidas o ausentes' in respuesta
    assert 'historial' in respuesta and 'reportante y afectado originales' in respuesta
    assert 'por sí solos, no transfiere equipos' in respuesta


@pytest.mark.parametrize(('pregunta', 'esperados'), [
    ('¿Qué pasa si importo sin activar la creación de perfiles?',
     ('pendiente de vincular', 'personas del Excel', 'cuenta existente', 'no crea su correo ni su contraseña')),
    ('¿El Excel crea la contraseña para iniciar sesión del nuevo usuario?',
     ('usuarios.editar', 'no trae correo, contraseña ni privilegios administrativos', 'Usuarios')),
    ('¿El número de serie permite reconocer el equipo al importar?',
     ('código patrimonial', 'MAC real', 'coincidencia única', 'no es un identificador mapeado', 'se omite')),
    ('¿Importar en Inventario anual transfiere los equipos al reemplazo?',
     ('instantánea', 'no reasigna', 'Equipos → Importar', 'Se actualizará')),
    ('Importa el Excel y reasigna los equipos al nuevo trabajador',
     ('no cambiar usuarios ni equipos desde el chat', 'cuenta autorizada')),
])
def test_ayuda_distingue_limites_del_flujo(pregunta, esperados):
    respuesta = responder_ayuda(pregunta)
    assert respuesta
    for esperado in esperados:
        assert esperado in respuesta


@pytest.mark.parametrize('pregunta', [
    '¿Cuántos equipos se importaron?',
    '¿Puedes decirme cuántos equipos tiene el usuario nuevo?',
    '¿Cuál es el total de equipos importados?',
    '¿Puedes listar los equipos del trabajador nuevo?',
    'Muéstrame los equipos después del relevo',
    '¿Cuáles son los equipos del usuario nuevo?',
    '¿Qué equipos tiene el usuario nuevo?',
    'Equipos del nuevo trabajador',
    '¿Cómo están los equipos del usuario nuevo?',
])
def test_ayuda_no_sustituye_consultas_reales_por_guia(pregunta):
    assert responder_ayuda(pregunta) is None


def test_creacion_de_cuenta_sin_importacion_no_se_convierte_en_relevo():
    assert responder_ayuda('¿Cómo creo un usuario nuevo?') is None


@pytest.mark.parametrize('pregunta', [
    '¿Puedo importar el Excel y cambiar al responsable de los equipos?',
    '¿Qué pasa si importo sin activar crear perfiles faltantes?',
])
async def test_analisis_responde_orientacion_sin_base_ni_proveedor(pregunta):
    resultado = await analitica_chat.responder(pregunta, usuario={'rol': 'administrador'})
    assert resultado['texto'] == responder_ayuda(pregunta)
    assert resultado['fuentes'] == ['guia_analisis']
    assert resultado['herramientas'] == [] and resultado['tabla'] is None
    assert 'No representa un recuento' in resultado['explicacion']


@pytest.mark.parametrize('proveedor', ['groq', 'gemini'])
async def test_chatbot_envia_conocimiento_revisado_al_proveedor_configurado(monkeypatch, proveedor):
    monkeypatch.setattr(chatbot_service.settings, 'chatbot_provider', proveedor)
    monkeypatch.setattr(chatbot_service.settings, proveedor + '_api_key', 'ficticia-solo-prueba')
    monkeypatch.setattr(chatbot_service, 'tiene_permiso', lambda *args: False)
    monkeypatch.setattr(chatbot_service.analitica_chat, '_detectar_intencion', lambda *args: (None, {}))
    cliente = AsyncMock()
    datos = ({'choices': [{'message': {'content': 'Revisa la vista previa.'}}]} if proveedor == 'groq'
             else {'candidates': [{'content': {'parts': [{'text': 'Revisa la vista previa.'}]}}]})
    cliente.post.return_value = httpx.Response(200, json=datos)
    sesion = MagicMock()
    sesion.__aenter__ = AsyncMock(return_value=cliente)
    sesion.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: sesion)
    respuesta = await chatbot_service.responder(
        '¿Puedo importar el Excel y cambiar al responsable?', [], {'rol': 'tecnico'})
    assert respuesta['disponible']
    cuerpo = cliente.post.call_args.kwargs['json']
    instruccion = (cuerpo['messages'][0]['content'] if proveedor == 'groq'
                   else cuerpo['systemInstruction']['parts'][0]['text'])
    assert GUIA_IMPORTACION_RELEVO.strip() in instruccion
    assert 'sin moverlos despues uno por uno' in instruccion
    assert 'permiso de importacion y usuarios.editar' in instruccion
    assert 'no tiene Deshacer automático' in instruccion
    assert 'los equipos ausentes del Excel o en filas omitidas no se transfieren' in instruccion
