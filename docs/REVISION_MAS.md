# Revisión de Más y biblioteca

15/10/2026. Los tres apartados son Base de conocimiento, Auditoría y Configuración.

## Cambios

- Reportes: «Indicadores del servicio» pasa a «Resumen de atención de tickets», con una explicación de cantidad de tickets, resolución, plazos y satisfacción, y del alcance temporal.
- Biblioteca: icono de libro, propósito explícito, búsqueda literal segura, filtro de categoría y paginación de doce artículos. Categorías de tutoriales, software y recomendaciones junto a las existentes.
- Crear y editar artículos: validación de longitudes, categoría y pasos numerados. Lectura con enlaces HTTP/HTTPS y retirada con confirmación. La API valida sus respuestas de detalle y escritura. Los artículos retirados dejan de ser accesibles por su URL.
- Se corrigió la caché del lector: después de editar se invalidan tanto el detalle como las consultas compartidas. Los cambios de identificador no reutilizan el contenido de otro artículo como respuesta provisional.
- Respuestas rápidas: se explica su uso como plantillas redactadas por TI. Creación, edición y eliminación; selección desde la conversación de un ticket. La selección añade un borrador sin enviarlo automáticamente.
- Valoraciones del portal: el botón envía el campo que exige la API; cada cuenta aporta una valoración por artículo al cálculo, aunque vuelva a pulsarlo.
- Configuración: nombre de institución enviado con el contrato correcto, avisos editables y persistentes, confianza validada entre cero y uno. Las actualizaciones parciales preservan opciones no enviadas. Se actualiza el estado de IA tras guardar.
- Permisos: se corrigen el formato de envío y la representación de permisos; se pueden conceder y revocar sin perder otros. Los permisos del administrador se muestran bloqueados. Se elimina la repetición de esta sección dentro de IA.
- Auditoría: filtros y exportación revisados; diálogo de detalle del movimiento con valores anteriores y posteriores cuando están registrados. Se ocultan claves sensibles en su representación.

## Validación

Pruebas de API aisladas para creación, lectura, edición, retirada, búsqueda con caracteres especiales, valoración repetida, plantillas y conservación de configuración parcial. Regresiones de biblioteca, sugerencias y auditoría inmutable.

Pruebas de navegador sobre la compilación de producción en el entorno de demostración: artículos y plantillas completos, persistencia de avisos, concesión y revocación de permisos; inserción y envío de una plantilla en el chat. Revisión móvil de biblioteca y regresiones de reportes/auditoría.

Los datos y cambios de prueba se ejecutan fuera de la base principal. No se comprueba entrega externa de correo ni se modifican credenciales de proveedores.

## Ajustes de avisos, horario y editor

- Se aclara que los avisos son notificaciones dentro de la página. Las preferencias de afectado y reportante se aplican ahora al servicio de notificaciones, independientemente de la antigua bandera de correo; un destinatario que cumple ambos papeles recibe un solo aviso.
- El horario visible utiliza los tramos del calendario laboral: 08:00–13:00 y 14:00–17:00. La migración 019 corrige el cierre general inicial de 18:00 a 17:00.
- Tarjetas compactas en cuatro columnas de escritorio, doce artículos por página. Prueba de distribución con ocho tarjetas a 1440 × 900 y comprobación móvil.
- Editor ampliado y dividido entre ficha del artículo y desarrollo de la guía. Contenido de al menos 240 px de alto. Se corrige el componente Textarea para respetar sus filas, que antes quedaban anuladas por la altura fija de un campo de una línea.

## Lectura y paginación final

- Se ajusta la petición a cuatro artículos por página, presentados en dos columnas de escritorio. El servidor unifica títulos/categorías duplicados antes de contar y paginar; así no se pierden tarjetas después de recibir la página. La última página muestra los artículos restantes cuando el total no es múltiplo de cuatro.
- El lector presenta un resumen destacado, categoría y fecha, explicación y pasos en bloques numerados. Las acciones de edición quedan en el pie del diálogo.
- Auditoría muestra veinte movimientos por página y sustituye entidades técnicas por nombres legibles. El detalle compara campos cambiados, con valores anteriores y nuevos, sin mostrar JSON ni fechas internas de actualización.
- Las exportaciones exitosas se excluyen junto con la actividad cotidiana. Sus errores continúan visibles. No se eliminan registros históricos de la base.
- Guardar un artículo o una plantilla sin modificar datos ya no crea otra entrada. Las altas y ediciones de respuestas rápidas se identifican con su nombre correcto, también en reportes.
- Verificación ampliada: páginas completas con duplicados, ausencia de entradas por guardados idénticos, conservación de errores de exportación, navegación de páginas, lectura y detalle de auditoría, más regresiones de reportes.
- Se alinea el acceso de auditoría con su pantalla y sus exportaciones: solo administradores, incluso si un técnico tiene permiso para consultar otros reportes.
