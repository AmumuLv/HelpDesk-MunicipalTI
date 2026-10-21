# Optimización de imágenes nuevas

El servidor convierte las nuevas subidas JPG/JPEG y PNG a WebP con calidad 80,
dimensión máxima de 1920 píxeles por lado y proporción original. Aplica la orientación
EXIF antes de redimensionar, conserva transparencia y no copia metadatos EXIF/GPS.
Las imágenes pequeñas no se amplían.

Se aplica en fotos de perfil y en el servicio común de adjuntos utilizado por tickets,
chat y cualquier pantalla que suba archivos a `/adjuntos`. Los bytes se guardan en el
servidor; MongoDB conserva la referencia, MIME, tamaño final y, para adjuntos, SHA-256.
La extensión y el nombre de descarga de las imágenes convertidas terminan en `.webp`.
El nombre original de subida queda en `nombre_subido`.

Las referencias anteriores no se migran: JPG/PNG existentes siguen sirviéndose con su
MIME y contenido original. WebP, GIF, audio, Excel, PDF y otros documentos mantienen su
contenido. La validación de tipo real y el antivirus opcional actúan antes de convertir.
Las imágenes corruptas se rechazan sin sustituir la foto de perfil vigente.

La entrada de fotos de perfil admite hasta 15 MB con la configuración predeterminada,
igual que los adjuntos. El servidor siempre respeta su límite `MAX_UPLOAD_MB`.
