# Dónde se guardan los datos y archivos

Los archivos cargados en la web se guardan en el servidor que ejecuta Docker.
No se suben a GitHub ni se almacenan como archivos del código fuente.

## Ubicaciones actuales

Estas son las rutas predeterminadas de `docker-compose.yml`:

| Contenido | Ruta dentro de Docker | Volumen persistente |
| --- | --- | --- |
| Fotos de perfil | `/data/uploads/fotos/<id_usuario>.<extensión>` | `mesa-ayuda_api-data` |
| Adjuntos, imágenes y notas de voz | `/data/uploads/<id_usuario>/<AAAA-MM>/` | `mesa-ayuda_api-data` |
| Informes PDF, CSV y Excel generados como exportaciones | `/data/exports/` | `mesa-ayuda_api-data` |
| Respaldos locales que existan en el directorio de la API | `/data/backups/` | `mesa-ayuda_api-data` |
| Oficinas, usuarios, equipos, tickets, chats y datos de inventario importados | Base `mesa_ayuda`, MongoDB en `/data/db` | `mesa-ayuda_mongo-data` |
| Caché, colas y avisos temporales | Redis en `/data` | `mesa-ayuda_redis-data` |
| Firmas del antivirus | `/var/lib/clamav/` | `mesa-ayuda_clamav-data` |
| Respaldos del perfil opcional `backup` | `/data/backups/` del servicio `backup` | `mesa-ayuda_backup-data`, si se activa |
| Respaldos manuales de las herramientas de traslado | La ruta indicada al ejecutar el comando, normalmente `backups/` del proyecto | Carpeta del equipo anfitrión |

Los Excel y CSV importados se procesan y sus datos se almacenan en MongoDB.
El inventario anual conserva una instantánea de sus filas y los metadatos del
archivo; no se guarda como un Excel dentro del repositorio. Si un archivo se
envía como adjunto de un ticket, sí ocupa espacio en `uploads`.

Las rutas `UPLOAD_DIR` y `EXPORT_DIR` pueden personalizarse en `.env`.
Los nombres de los volúmenes cambian si se cambia el nombre del proyecto Compose.

## Consultar el espacio utilizado

```powershell
docker compose exec api du -sh /data/uploads /data/exports /data/backups
docker volume inspect mesa-ayuda_api-data
docker system df -v
```

En Windows con Docker Desktop, los volúmenes viven dentro del disco virtual de
Docker, no en una carpeta normal junto al proyecto. Docker Desktop muestra los
archivos desde **Volumes → mesa-ayuda_api-data**. Para copiarlos fuera de Docker
se puede utilizar `docker compose cp`; borrar la carpeta del código no borra los
volúmenes.

Los informes descargados al navegador también ocupan espacio en la carpeta
Descargas del equipo del usuario. Esa copia está fuera del almacenamiento del
servidor y no se elimina al borrar un registro en la web.

## Instalación nueva y conservación de datos

Una instalación con volúmenes vacíos no contiene las cuentas ni los registros de
otra PC. El primer arranque permite crear el administrador principal y conserva
los catálogos necesarios. Los datos ficticios de las pruebas no se cargan por
iniciar la instalación operativa.

Actualizar el código o recrear un contenedor conserva sus volúmenes. No indica
cuántas cuentas existen ni demuestra que la base esté vacía. Esta guía describe
rutas y funcionamiento; no es una fotografía del contenido actual del servidor.

Una limpieza de producción necesita alcance explícito y autorización. No borres
volúmenes para resolver una incidencia de la interfaz. Los archivos descargados
en otras computadoras y el historial de Git son independientes del almacenamiento
operativo: borrar un documento de la versión actual no reescribe ese historial.


## Revision de archivos al subirlos

Las fotos de perfil y los adjuntos se envían a ClamAV dentro de Docker antes
de guardarse. Si el antivirus detecta una amenaza o no puede comprobar el
archivo, la subida se rechaza. El contenido no se manda a un servicio externo.
El volumen `clamav-data` conserva firmas de amenazas, no fotos ni documentos de
los usuarios. Su base de firmas ocupa alrededor de 200 MB; el servicio consumió
aproximadamente 1 GB de RAM en esta instalación durante la comprobación.
Las importaciones Excel/CSV tienen sus propias validaciones; este control
antivirus se aplica a fotos y adjuntos, no equivale a revisar todo el disco.
