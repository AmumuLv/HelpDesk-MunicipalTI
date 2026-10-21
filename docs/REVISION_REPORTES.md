# Revisión de reportes y auditoría

## Presentación

- Análisis IA muestra fechas en `dd/mm/aaaa`, también en las tablas y la ayuda del gráfico. El botón de actualización y el selector se alinean por su borde inferior.
- La resolución media se expresa en días, horas y minutos: `60 → 1 hora`, `90 → 1 hora 30 min`. Excel conserva además los minutos como número para poder calcular.
- Reportes explica el alcance de cada archivo. Inventario representa la situación actual y no muestra un filtro temporal que no se aplicaba. Zona y oficina están relacionadas; cambiar la zona limpia la oficina anterior.
- Se elimina el botón que imprimía la página web. La opción PDF descarga un documento generado en el servidor.

## PDF

- Los informes consolidados usan A4 horizontal, tablas compactas, filas alternadas, encabezados repetidos y páginas numeradas.
- Fecha de generación y responsable en el margen de cada página, evitando páginas finales dedicadas únicamente al pie. En el listado PDF de tickets se muestran fechas; Excel conserva las horas exactas.
- Los filtros identifican las ubicaciones por nombre y muestran las fechas de inicio y fin. No aparecen identificadores técnicos como sustituto del nombre de una zona.
- Tickets incluye código y asunto, tipo/nombre/patrimonio del equipo, ubicación, persona afectada, técnico, estado, fechas y resolución.
- Las notas internas, cuando se solicitan, se incluyen en una sección aparte y se identifican como información de trabajo TI.
- Cada zona del inventario empieza en una página nueva. La tabla conserva oficina, equipo, patrimonio, conjunto, marca/modelo, estado y responsable.
- El historial de familias de equipos del informe analítico se identifica como histórico de doce meses, no como una probabilidad futura de noventa días.

## Excel y CSV

- Se elimina el recorte de 500 tickets y se exportan todos los casos que cumplen el filtro, excluyendo los eliminados.
- Los tickets incluyen identificación del equipo incluso si el ticket antiguo solo conservaba el identificador del activo. La consulta del inventario se realiza en lote.
- El inventario usa una hoja por zona y recoge todas las páginas del listado. Las hojas tienen nombres válidos y únicos.
- Filas continuas, sin celdas combinadas ni separadores intermedios; encabezado fijo, filtro por columna y ancho adecuado al contenido.
- Las fechas de Excel son fechas reales con formato de día/mes/año. Los números siguen siendo numéricos, incluido el cero.
- CSV es una tabla UTF-8 separada por punto y coma. El reporte analítico ya no devuelve un XLSX bajo una extensión CSV.
- Los textos que comienzan como fórmulas se conservan como datos, sin ejecutarse al abrir el archivo.

## Auditoría

- Se registran cambios en cuentas, contraseñas y permisos; altas, ediciones y bajas del inventario; importaciones; asignaciones, cierres, reaperturas y eliminaciones de tickets; configuración, exportaciones y alertas de seguridad.
- Se dejan de duplicar accesos exitosos, cierres de sesión, mensajes, notas, adjuntos, valoraciones y consultas habituales de IA. El historial de los tickets permanece en su ficha.
- No se generan movimientos por una edición sin diferencias cuando el registro incluye el mismo antes y después.
- Los registros anteriores no se borran. La pantalla y sus exportaciones consultan el mismo criterio de movimientos relevantes, conservando las alertas.
- El filtro de acción de la pantalla ahora se envía a la API. La fecha final se aplica también en las exportaciones, incluyendo el último instante de ese día local.
- El enlace al reporte conserva las fechas y la acción seleccionadas. Las etiquetas de acción y el rol de la persona se muestran correctamente.

## Verificación

Pruebas API con MongoDB aislado: exportación de 505 tickets, identificación de equipo, notas opcionales, fechas y números de Excel, inventario de 102 equipos en varias zonas, PDF real en horizontal, límites de fechas de auditoría, exclusión de actividad cotidiana, tipos y formatos y validación de filtros. También se ejecutan las regresiones existentes de exportaciones y auditoría.

Las pruebas del navegador generan y descargan archivos reales, comprueban filtros, fechas legibles, alineación, conversión de duración, errores y presentación móvil. Las muestras de `docs/muestras-reportes` se generan exclusivamente con los datos del despliegue de demostración.

Resultado: doce pruebas distintas de API/servicios y siete del navegador aprobadas, incluidas las regresiones de Usuarios, Equipo TI y Análisis IA. Se repitieron las pruebas afectadas por los últimos ajustes de PDF y de alineación. La compilación de producción, TypeScript y ESLint finalizaron sin errores.

La revisión de las muestras PDF incluye rasterización e inspección visual, orientación horizontal, detección de páginas casi vacías y comprobación de texto fuera de los límites de página.
