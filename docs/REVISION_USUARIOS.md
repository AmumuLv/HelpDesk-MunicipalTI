# Revisión de Usuarios — 14 de octubre de 2026

El directorio, el perfil rápido y el perfil completo comparten las mismas reglas de cuenta. La búsqueda conserva su protección contra el autocompletado; abrir un diálogo bloquea temporalmente su edición.

## Cambios

- Creación: validación de nombre y correo, contraseña confirmada, mostrar/ocultar la clave nueva, teléfono y anexo separados, errores de correo duplicado junto al campo y bloqueo durante el envío. Solo un administrador puede crear otro administrador o asignar permisos delegables.
- Perfil completo: pestañas Resumen, Tickets, Equipos y Cuenta y edición. La edición se hace dentro de la página, con secciones para contacto, acceso, preferencias y ubicación. Las acciones de la cabecera se sitúan debajo del título en móvil.
- Tickets: `GET /api/usuarios/{id}/tickets`, con páginas de 10 y filtros por creador, afectado y técnico asignado. Incluye el historial completo, ordenado por fecha e identificador, sin duplicar tickets donde la persona cumple varias funciones. El endpoint exige permisos de tickets y de directorio para consultar otra cuenta.
- Equipos: el perfil rápido muestra hasta cinco; el perfil completo los pagina de diez en diez.
- Correo: se normaliza al guardar; los duplicados se rechazan sin modificar la cuenta. El formulario explica que la nueva dirección se utiliza para iniciar sesión.
- Contraseña: el operador puede revisar y confirmar la clave nueva antes de guardar. El restablecimiento revoca las sesiones anteriores y limpia los campos al terminar. Las contraseñas existentes se guardan como hashes y no se pueden mostrar ni recuperar.
- Estado: el administrador puede desactivar y reactivar desde el perfil con confirmación. No puede desactivar su propia cuenta; se conserva el historial y debe quedar un administrador activo.
- Protección de administradores: un técnico con permiso delegado de edición no puede cambiar el correo, los datos ni la contraseña de una cuenta administradora.
- Horario de nuevas cuentas TI: los días iniciales usan el criterio del calendario interno, 0 = lunes hasta 4 = viernes. Los horarios ya registrados no se modifican.
- Búsqueda: los caracteres especiales se buscan como texto literal, sin interpretarlos como expresiones regulares ni convertir un nombre normalizado vacío en una búsqueda de todas las cuentas.

## Verificación

Las pruebas de API usan una base aislada que se elimina al terminar. Las pruebas del navegador crean y desactivan cuentas de demostración en la API de pruebas del puerto 8100. La paginación de 23 tickets se verifica en la API con datos aislados y en el navegador con respuestas simuladas, sin crear incidencias en la base municipal.

- `backend/tests/test_usuarios_flujos.py`: correo y acceso, restablecimiento y revocación, páginas completas sin duplicados, filtros, permisos, búsqueda literal y horario inicial.
- `backend/tests/test_usuarios_permisos.py` y `test_usuarios_foto.py`: permisos, desactivación/reactivación, conservación de datos y fotos.
- `frontend/pruebas/usuarios-flujos.spec.ts`: creación, validación de correo, visibilidad y confirmación de contraseña, perfil completo, edición, rechazo de duplicados, nuevos accesos, paginación, diseño móvil y estado de cuenta.
- `frontend/pruebas/permisos-usuarios.spec.ts`: creación por administrador y restricciones de técnico.
- `frontend/pruebas/buscador-autocompletado.spec.ts`: rechaza distintos correos automáticos y conserva la búsqueda manual.

Capturas de prueba: [Cuenta](capturas/usuarios-perfil-cuenta.png), [Edición](capturas/usuarios-perfil-edicion.png), [Tickets en móvil](capturas/usuarios-perfil-tickets-movil.png).

Resultado: las 19 pruebas distintas de API de estos archivos y las cuatro pruebas de navegador pasaron en las ejecuciones de revisión. ESLint y la compilación de producción con TypeScript y Vite pasaron. Se reconstruyeron las imágenes y se actualizaron los servicios locales de API y web, tanto del entorno principal como del entorno de demostración.

## Ajustes visuales y fotos

- Las tres acciones del perfil rápido se encuentran en el pie del diálogo. El botón de contraseña abre su formulario y lo desplaza a la vista; el acceso al perfil completo sigue siendo la acción principal.
- Los equipos se presentan en tarjetas con icono, fondo y borde del color de su tipo, ubicación y estado. Los datos personales y de acceso usan tarjetas con iconos.
- Los tickets incluyen el equipo, tipo y código patrimonial, con enlace a su ficha según permisos. Se mantienen los nombres históricos y se consultan los datos actuales cuando el registro antiguo no guardó el nombre o el tipo.
- Se corrigió la invalidación de fotos en todos los avatares, incluidos reemplazos consecutivos. Las descargas evitan la caché HTTP y una respuesta antigua no puede sustituir una foto nueva.
- Se reprodujo el error 413 al enviar 1,2 MB por Nginx: el límite predeterminado de 1 MB contradice los 2 MB admitidos para fotos. El proxy ahora admite el cuerpo de subida; la API y el formulario conservan la validación de fotos de hasta 2 MB. Si un servidor rechaza una subida por tamaño, la aplicación muestra un mensaje específico.
- `npx playwright test -c playwright.servido.config.ts` permite comprobar los formularios y las subidas contra la web compilada del entorno de demostración, incluido Nginx.

Más capturas: [Equipos](capturas/usuarios-perfil-equipos.png), [Resumen](capturas/usuarios-perfil-resumen.png), [Perfil rápido](capturas/usuarios-perfil-rapido.png).

La comprobación contra Nginx pasó con dos subidas consecutivas de 1,2 MB desde la edición, cambio inmediato del avatar, eliminación y rechazo de una foto mayor de 2 MB sin perder la anterior. También pasó la consulta de equipos en los tickets y las ocho pruebas de fotos de la API. La compilación, ESLint y la configuración de Nginx se verificaron antes de actualizar el entorno principal.

## Densidad y colores del perfil

El encabezado muestra «Perfil de usuario» y la tarjeta de identidad muestra el nombre una sola vez. Cuando el nombre coincide con el rol, el subtítulo evita repetirlo. Los acentos de pestañas, enlaces y datos siguen la zona; las cuentas sin zona usan tonos neutros. Los colores de estado y prioridad conservan su significado.

Los tickets presentan el equipo en una línea secundaria con icono pequeño, sin otra tarjeta dentro de cada fila. Los equipos a cargo usan filas compactas con una etiqueta del tipo —por ejemplo, Monitor—, código patrimonial, ubicación y estado. La prueba del navegador comprueba la ausencia de nombres duplicados y el tamaño de las filas, además de los flujos anteriores.

El enlace de cada ticket conserva un acento dorado propio, independiente de la zona. En su línea de equipo se omite el tipo cuando ya aparece en el nombre y no se repite un conjunto idéntico. La comparación ignora mayúsculas, tildes y variantes Mouse/Mause/Ratón; se mantienen el patrimonio y los datos que aportan información distinta.
