from io import BytesIO
from pathlib import Path
import hashlib
import subprocess
import wave

from bson import ObjectId
import pytest

from app.core.errors import Validacion
from app.services.audio_service import validar_audio
from tests.test_tickets_horarios import _mundo


def wav(segundos):
    salida = BytesIO()
    with wave.open(salida, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\x01\x01' * int(8000 * segundos))
    return salida.getvalue()


def test_limite_duracion_y_peso():
    assert validar_audio(wav(120)) == pytest.approx(120)
    with pytest.raises(Validacion, match='2 minutos'):
        validar_audio(wav(121))
    with pytest.raises(Validacion, match='5 MB'):
        validar_audio(wav(1) + bytes(5 * 1024 * 1024))
    with pytest.raises(Validacion, match='leer el audio'):
        validar_audio(b'audio roto')


async def test_formatos_nativos_se_guardan_sin_conversion_y_rechaza_excesos(db, api, tmp_path):
    mundo = await _mundo(api, 'audio-limites')
    formatos = [('webm', 'libopus', 'audio/webm'), ('ogg', 'libopus', 'audio/ogg'), ('m4a', 'aac', 'audio/mp4'), ('mp3', 'libmp3lame', 'audio/mpeg'), ('wav', 'pcm_s16le', 'audio/wav')]
    for ext, codec, mime in formatos:
        archivo = tmp_path / f'nota.{ext}'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.5', '-ac', '1', '-c:a', codec, '-b:a', '64k', str(archivo)], check=True)
        original = archivo.read_bytes()
        respuesta = await api.post('/api/adjuntos', headers=mundo['usuario'], files={'archivo': (archivo.name, original, mime)})
        assert respuesta.status_code == 201, respuesta.text
        info = respuesta.json()
        assert info['mime'] == mime and info['tamano'] == len(original)
        documento = await db.adjuntos.find_one({'_id': ObjectId(info['id'])})
        assert 0 < documento['duracion_segundos'] < 1
        assert documento['sha256'] == hashlib.sha256(original).hexdigest()
        assert Path(documento['ruta']).read_bytes() == original
        descarga = await api.get(f"/api/adjuntos/{info['id']}", headers=mundo['usuario'])
        assert descarga.status_code == 200 and descarga.content == original
    for contenido in [wav(121), wav(1) + bytes(5 * 1024 * 1024)]:
        respuesta = await api.post('/api/adjuntos', headers=mundo['usuario'], files={'archivo': ('grande.wav', contenido, 'audio/wav')})
        assert respuesta.status_code == 422, respuesta.text
    assert await db.adjuntos.count_documents({}) == len(formatos)
