# Limpieza previa a GitHub

**Nota histórica:** esta revisión se escribió antes de crear el repositorio
independiente. La raíz Git actual ya es esta carpeta. Para instalar o publicar,
consulta [la entrega actual](ENTREGA_GITHUB_PRIVADO.md) y
[la guía de traslado](INSTALAR_Y_TRASLADAR.md).

Se conserva la instalación principal `mesa-ayuda` y su base `mesa_ayuda`, con los datos
actuales de trabajo. Se eliminó la instalación descartable `mesa-ayuda-prueba`, incluidos
sus contenedores, bases de datos, adjuntos y volúmenes.

Las capturas, reportes y resultados generados se apartaron fuera de esta carpeta,
porque la protección automática del entorno bloqueó su eliminación. Las reglas de
Git los excluyen si se vuelven a generar.

Se conservan las pruebas automatizadas y sus fixtures sintéticos para depurar el código.
No contienen los registros operativos de MongoDB. La creación de datos demo es explícita;
no debe ejecutarse para preparar un despliegue real.
Playwright apunta por defecto a una API de pruebas separada en el puerto 8100
(`PRUEBA_API_URL`), en lugar de escribir sobre la API principal del puerto 8000.
Como se eliminó esa instalación descartable, habrá que preparar un entorno aislado
antes de volver a ejecutar pruebas que creen datos.
La prueba de humo rechaza ejecutarse en producción y los fixtures de pytest rechazan
borrar bases principales o bases cuyo nombre no las identifique como pruebas.

Los archivos `.env`, variantes locales, claves, respaldos, cargas y exportaciones quedan
excluidos de Git. Los documentos originales de `samples` permanecen locales; únicamente
`samples/inventario-muestra.xlsx`, utilizado como muestra sintética, sigue publicable.

## Antes de publicar

El repositorio Git detectado tiene como raíz el **Escritorio**, no esta carpeta. No se
debe publicar ese repositorio completo. Hay que preparar un repositorio independiente
que contenga únicamente `helpdesk-municipal`, respetando `.gitignore` y conservando el
historial anterior como respaldo local si se necesita.

La revisión realizada compara los secretos del entorno actual con los archivos que Git
considera publicables; no sustituye una revisión del historial del repositorio que vaya
a publicarse. No se ha creado un repositorio remoto ni se ha realizado ningún push.

Para usar un dominio de prueba, el siguiente paso es elegir el alojamiento y configurar
HTTPS, URL pública, cookies y proxy. Las notas de voz necesitan HTTPS fuera de localhost.
