# Revisión de Inventario anual

## Cambios

- Se retira del componente del escudo la base blanca, el borde y la sombra; el PNG ya tiene transparencia.
- Se presenta el recorrido en tres pasos: preparar, comparar/verificar y cerrar/conservar.
- Se validan el alcance, el año de inicio y el orden de fechas, incluida la edición de campañas. No se rechaza una campaña solo porque aún no tenga equipos registrados.
- Verificaciones y aceptación de cambios quedan bloqueadas en campañas cerradas. Los identificadores de elementos ajenos se rechazan antes de aplicar decisiones.
- Se rechazan archivos vacíos, dañados o con hojas/oficinas fuera del alcance seleccionado antes de modificar elementos. El CSV puede heredar la zona cuando el alcance determina una sola.
- Los equipos nuevos encontrados manualmente se marcan para registrarse al cerrar. No inflan el porcentaje de equipos previamente registrados verificados.
- La versión histórica incluye las identidades de equipos recién creados y los datos efectivos de oficina, responsable y estado. Los cambios pendientes no se presentan como aplicados. Se excluyen del inventario histórico las filas que no llegaron a registrarse.
- La pantalla muestra el resultado del cierre y los motivos de equipos nuevos que no se pudieron registrar. Mantiene seleccionada la campaña cerrada.
- Se manejan errores de verificación, se bloquean envíos simultáneos desde la pantalla y se impide cerrar mientras se guarda una verificación.
- Se reinician filtros al cambiar de campaña; cambiar zona limpia la oficina anterior. Se ofrecen todos los estados de verificación y nombres legibles.
- La consulta de elementos no utiliza datos provisionales de otra campaña; el orden de paginación es estable.
- Al crear, el diálogo se cierra después de refrescar y seleccionar la campaña nueva. Se evita que una subida inmediata termine en la campaña anterior.

## Verificación

Pruebas de API aisladas: detección/aceptación/alta, varios equipos nuevos, segunda subida del mismo archivo, descarte, campañas en verificación, cierre inmutable, fechas, alcance, archivos dañados/vacíos, histórico fiel y paginación de treinta equipos.

Prueba de navegador con datos propios de demostración: crear por zona, subir CSV, marcar novedades, verificar con error simulado y reintento, confirmar cierre, comprobar alta y descargar Excel. Se comprueba también el ancho móvil. Los datos principales del usuario no se usan para estas pruebas.
