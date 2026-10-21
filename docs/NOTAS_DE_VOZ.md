# Notas de voz

El navegador captura el micrófono en mono y solicita 64 000 bits/s. Elige AAC/M4A
si MediaRecorder lo admite, con alternativas Opus/WebM y Opus/Ogg según las
capacidades del navegador. No existe un único formato de grabación nativo disponible
en todas las versiones de todos los navegadores.

La grabación se detiene automáticamente a los dos minutos. Se rechazan archivos que
superen 5 MiB, tanto en la interfaz como en el servidor. El servidor comprueba la
duración de los audios adjuntados mediante ffprobe y rechaza más de 120 segundos
(con 250 ms de margen para el paquete final del codificador).

ffprobe solo inspecciona el contenedor y sus paquetes. El servidor no convierte,
no recodifica ni modifica los bytes del audio; guarda el original y registra su MIME,
tamaño, huella SHA-256 y duración. No se aplica la optimización WebP a los audios.
La reproducción se hace directamente en el chat mediante el control de audio nativo.

Se mantienen la selección de micrófono, medición de señal y rechazo de grabaciones
silenciosas. El micrófono requiere HTTPS o localhost y permiso del usuario.
