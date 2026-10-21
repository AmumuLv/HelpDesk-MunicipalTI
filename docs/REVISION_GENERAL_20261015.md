# Inventario anual, conexiones y recorridos del portal

El archivo anual admite una carga directa con año y Excel, sin crear previamente una campaña. Cada carga conserva una instantánea independiente del inventario operativo. Una carga repetida del mismo archivo y año devuelve la versión existente. Una hoja representa una zona; el CSV requiere indicar su zona.

Las comparaciones utilizan la revisión anual más reciente de cada año y muestran sus nombres de archivo. Identifican equipos por código patrimonial y separan incorporaciones, ausencias en el destino, traslados y cambios de datos. Sin patrimonio se utiliza nombre, tipo y ubicación, con advertencia de las limitaciones. Una ausencia en el archivo siguiente no da de baja el equipo operativo. Las campañas físicas anteriores permanecen en una pestaña separada.

Las conexiones se cuentan por sesiones autenticadas. Se permiten tres; el cuarto acceso cierra la más antigua. Renovar el token mantiene la identidad y fecha inicial de la conexión. El perfil muestra las conexiones vigentes y permite cerrarlas; los administradores pueden revisar las de otras cuentas. Cambiar contraseña invalida las sesiones y limpia el acceso en pantalla. La migración también limita las conexiones anteriores a este cambio.

El portal da prioridad al Botón de Pánico: elegir el problema y completar el detalle, con chat al terminar. La campana permite abrir el ticket correcto según el rol y marcar avisos propios como leídos; ofrece reintento ante errores.

Las fichas evitan repetir el nombre del equipo en título, ruta y tarjeta. La oficina ocupa el lugar principal en su propia tarjeta, con la zona como enlace secundario. El historial de la persona usa DataTable, estados y prioridades compartidos con la bandeja y añade filtro por estado. El responsable del inventario enlaza al perfil; los clics sobre enlaces dentro de una fila no activan la navegación de la fila.

Se añaden iconos con tonos semánticos, bordes amarillos al pasar el puntero por controles y filas, y mayor separación entre gráficos. Las pruebas se ejecutan con una base aislada, sin introducir inventarios o incidencias de prueba en la instalación principal.

Validación: pruebas de servidor en `test_redisenio_general.py`, inventario anual, usuarios y tickets/horarios; pruebas de navegador en `redisenio-general.spec.ts` y regresiones de usuarios, inventario, equipo TI, análisis, reportes, conocimiento y contraste. Los archivos Excel de prueba incluyen dos años con una incorporación, una ausencia y un traslado.
