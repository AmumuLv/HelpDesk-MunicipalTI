from PIL import Image
from io import BytesIO
import wave

from tests.test_tickets_horarios import _mundo, _sesion


async def test_fotos_audio_sin_texto_y_control_de_acceso(db, api):
    mundo = await _mundo(api, 'multimedia')
    usuario = mundo['usuario']
    nuevo = await api.post('/api/tickets', headers=usuario, json={'tipo_problema': 'No enciende', 'persona': {'es_para_mi': True}})
    assert nuevo.status_code == 201, nuevo.text
    ticket = nuevo.json()['ticket']['id']
    imagen = BytesIO()
    Image.new('RGB', (16, 16), 'green').save(imagen, format='PNG')
    png = imagen.getvalue()
    sonido = BytesIO()
    with wave.open(sonido, 'wb') as grabacion:
        grabacion.setnchannels(1)
        grabacion.setsampwidth(2)
        grabacion.setframerate(8000)
        grabacion.writeframes(b'\0\0' * 800)
    ids = []
    for nombre, contenido, mime in [('foto.png', png, 'image/png'), ('audio.wav', sonido.getvalue(), 'audio/wav')]:
        adjunto = await api.post('/api/adjuntos', headers=usuario, files={'archivo': (nombre, contenido, mime)})
        assert adjunto.status_code == 201, adjunto.text
        identificador = adjunto.json()['id']
        ids.append(identificador)
        assert (await api.get(f'/api/adjuntos/{identificador}', headers=mundo['tecnico'])).status_code == 403
    ajeno = await api.post(f'/api/tickets/{ticket}/mensajes', headers=mundo['tecnico'], json={'adjuntos': ids})
    assert ajeno.status_code == 403
    mensaje = await api.post(f'/api/tickets/{ticket}/mensajes', headers=usuario, json={'adjuntos': ids})
    assert mensaje.status_code == 201, mensaje.text
    assert (await api.get(f'/api/tickets/{ticket}/mensajes', headers=usuario)).json()['items'][0]['cuerpo'] == ''
    for identificador in ids:
        descargado = await api.get(f'/api/adjuntos/{identificador}', headers=mundo['tecnico'])
        assert descargado.status_code == 200
        assert descargado.content
    repetido = await api.post(f'/api/tickets/{ticket}/mensajes', headers=usuario, json={'adjuntos': ids})
    assert repetido.status_code == 403
    otra_persona = await _sesion(api, 'companero-multimedia@prueba.local')
    assert (await api.get(f'/api/adjuntos/{ids[0]}', headers=otra_persona)).status_code == 403
    assert (await api.post(f'/api/tickets/{ticket}/mensajes', headers=usuario, json={'cuerpo': '  '})).status_code == 422
    falso = await api.post('/api/adjuntos', headers=usuario, files={'archivo': ('audio.wav', png, 'audio/wav')})
    assert falso.status_code == 422
    assert (await api.get(f'/api/tickets/{ticket}/mensajes', headers=usuario)).json()['items'][0]['adjuntos'] == ids
