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

## Estado tras la limpieza solicitada

La instalación local se vació conservando las cuatro cuentas de administrador
y sus contraseñas. Se retiraron sus fotos, ubicación y sesiones anteriores.
Se restablecieron los catálogos y la configuración inicial necesarios para
funcionar, junto con los perfiles TI básicos de esas cuentas.

Se eliminaron los demás usuarios, oficinas, zonas, equipos, tickets, artículos,
conversaciones, notificaciones, importaciones, historial y archivos cargados en
el almacenamiento del servidor, incluidos sus respaldos. No se generó un
respaldo de los datos eliminados.

Se retiraron también los respaldos locales, las muestras originales, las capturas,
los resultados de prueba, el clon temporal de validación y la documentación
histórica de la versión actual del proyecto. La plantilla de inventario se
genera vacía desde la web; no queda una copia de muestra en `docs/`.

Se conserva el código de pruebas automáticas con sus entradas ficticias; no
precarga datos en la instalación operativa. También se conservan el escudo, la
imagen de acceso, las fuentes y los iconos que forman parte de la aplicación.

La limpieza no elimina archivos de Descargas u otras carpetas ajenas al proyecto,
ni documentos almacenados en equipos externos. Git conserva versiones anteriores
de los archivos de código y documentación que estuvieron registrados; eliminar
un documento de la versión actual no reescribe el historial del repositorio.
