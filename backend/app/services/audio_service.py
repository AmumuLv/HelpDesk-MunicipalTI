"""Comprueba tamaño y duración sin convertir ni recodificar audio."""

import json
import math
import subprocess
from tempfile import NamedTemporaryFile

from app.core.errors import DependenciaNoDisponible, Validacion

MAX_BYTES = 5 * 1024 * 1024
MAX_SEGUNDOS = 120


def validar_audio(contenido: bytes) -> float:
    if len(contenido) > MAX_BYTES:
        raise Validacion('Cada audio admite un máximo de 5 MB y 2 minutos.')
    try:
        with NamedTemporaryFile() as temporal:
            temporal.write(contenido)
            temporal.flush()
            # ffprobe solo lee el contenedor/paquetes; no decodifica ni convierte.
            resultado = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                 '-show_entries', 'format=duration:packet=pts_time,duration_time',
                 '-of', 'json', temporal.name],
                capture_output=True, timeout=10, check=True,
            )
        datos = json.loads(resultado.stdout)
        paquetes = datos.get('packets', [])
        if not paquetes:
            raise ValueError('No hay paquetes de audio')
        tiempos = [(float(p['pts_time']), float(p.get('duration_time', 0))) for p in paquetes if 'pts_time' in p]
        duracion = float(datos.get('format', {}).get('duration') or 0)
        if tiempos:
            duracion = max(duracion, max(t + max(0, d) for t, d in tiempos) - min(t for t, _ in tiempos))
        if not math.isfinite(duracion) or duracion <= 0:
            raise ValueError('Duración no disponible')
    except subprocess.TimeoutExpired as exc:
        raise DependenciaNoDisponible(
            'No pudimos comprobar el audio a tiempo. El servicio está ocupado; inténtalo nuevamente en un momento.',
            codigo='audio_no_disponible',
        ) from exc
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError) as exc:
        raise Validacion('No se pudo leer el audio. Vuelve a grabarlo o adjunta un audio válido.') from exc
    # Margen para el último paquete del codificador del navegador.
    if duracion > MAX_SEGUNDOS + 0.25:
        raise Validacion('El audio supera los 2 minutos. Envía una nota más corta.')
    return duracion
