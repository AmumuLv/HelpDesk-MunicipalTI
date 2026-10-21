# Portal del usuario

Inicio prioriza **Necesito ayuda** y los reportes en curso. La navegación principal es Inicio, Mis reportes y Mi cuenta. Mis equipos y Guías de ayuda siguen accesibles desde Inicio y Mi cuenta.

## Reportar

1. Elegir qué falla, con opciones familiares e iconos en color.
2. Describir el problema e indicar si puede seguir trabajando. Enviar abre el ticket y su conversación.

No se exige al usuario que conozca categorías técnicas. La opción elegida determina la categoría inicial; TI puede corregirla. El título se acorta automáticamente a un máximo de 70 caracteres para todas las opciones y problemas no catalogados. Si el proveedor está disponible, una tarea en segundo plano puede mejorarlo leyendo toda la descripción. Se respeta cualquier título editado por TI. No se genera ni muestra un párrafo adicional de resumen. La descripción original se conserva completa en la ficha.

El reporte para un compañero es opcional. Solo se ofrecen personas activas de la misma oficina; el servidor también rechaza destinatarios de otra oficina. Los equipos propios y los de uso común se muestran separados. Cambiar persona u origen limpia la selección del equipo.

Se bloquean envíos por doble clic. Si falla el envío se conserva lo escrito; si el ticket ya fue creado, una recarga fallida de listas no repite su creación.

## Seguimiento y mensajes

Los estados visibles son Recibido, En atención, En espera y Finalizado. Los antiguos registros resueltos se consultan también como finalizados. Mis reportes muestra 25 por página; cambiar filtros vuelve a la primera.

El cierre muestra **Resultado de la atención**, resaltado en ambos temas. Es el texto del técnico sobre qué ocurrió y qué se hizo. Se conservan valoración y reapertura.

El chat admite texto, fotos y notas de voz. Los estados, mensajes y avisos se actualizan mediante WebSocket autenticado; el portal mantiene consultas de respaldo cada 5 segundos con la pestaña visible. Los tickets registrados por TI que no tienen chat conservan su seguimiento sin habilitar una conversación inexistente.

Los mensajes del usuario notifican únicamente al técnico asignado. Sin técnico, se avisa a TI para evitar que el mensaje quede sin destinatario. Un mensaje en un ticket finalizado se distingue en ámbar y no reabre automáticamente el caso. Todas las cuentas pueden eliminar avisos propios o vaciar su bandeja; los tickets y mensajes se conservan.

## Equipo, conjunto y programa

En la ficha del ticket, **Editar** permite corregir título, categoría y vinculación:

- **Equipo concreto:** el ticket forma parte del historial de ese dispositivo y, si pertenece a un conjunto, también del historial del conjunto.
- **Conjunto completo:** se registra para la computadora como unidad sin atribuirlo a un componente al azar.
- **Programa o sistema / Servicio o cuenta:** se indica su nombre. Puede vincularse al equipo o conjunto donde ocurre, o quedar sin equipo si es una consulta general.
- **Por identificar:** TI todavía no confirmó el dispositivo o servicio afectado.

Los equipos y conjuntos deben pertenecer a la oficina del caso. La API valida identidad, oficina, existencia y permisos; no busca equipos por coincidencias aproximadas. Los cambios quedan en el historial y auditoría.

El ticket siempre permanece en el historial de sus personas participantes. Un problema de software vinculado a una PC también es parte del historial de esa PC: el historial incluye tanto hardware como trabajos realizados en ella. Los casos generales de programas o cuentas no se atribuyen a equipos ficticios. Pueden buscarse por nombre del programa en Tickets.

**Historial del conjunto**, disponible en la ficha del equipo y en el ticket vinculado, reúne los casos del conjunto y sus componentes, con diez por página y los mismos permisos de consulta de tickets.

## Cuenta y conocimiento

Los usuarios solicitan el restablecimiento de contraseña mediante un reporte al equipo TI. Solo el administrador puede realizarlo; se revocan las sesiones anteriores. Mi cuenta conserva dispositivos conectados, preferencias y cierre de sesión.

Los artículos pueden ser públicos o **Solo equipo TI**. La restricción se aplica en listados, búsqueda, lectura directa, categorías, valoraciones y recomendaciones. Los cambios de visibilidad quedan en auditoría.

El portal recomienda hasta tres guías públicas relacionadas cuando hay coincidencias y las recomendaciones están activadas. El chat del ticket es con soporte humano. Un futuro chatbot de consulta tendrá su propio canal y permisos; clasificación, aprendizaje y predicciones siguen separados.

## Verificación

`npx playwright test pruebas/portal-sencillo.spec.ts` intercepta API y WebSocket sin crear datos reales. Comprueba reporte, envío, errores, mensajes, accesibilidad, ambos temas, tamaños móviles y de escritorio, paginación, avisos, resultado y edición de vínculos.

Las pruebas de servidor usan MongoDB y Redis efímeros aislados. Los escenarios antiguos que requieren cuentas de integración no deben ejecutarse contra la base real.

## Calificación y cambios de IA en vivo

En un ticket finalizado, el reportante o la persona afectada puede guardar una calificación de 1 a 5 estrellas una sola vez. La selección se confirma después de guardarla, permanece al volver a abrir el reporte y se evita el doble envío tanto en navegador como con una actualización condicional en la base de datos. Un fallo permite reintentar. El técnico no puede calificar un ticket ajeno como si fuera la persona atendida.

Las preferencias personales y el interruptor global de IA emiten eventos autorizados. Las guías se ocultan al desactivar recomendaciones, aunque existan resultados anteriores en caché. La preferencia personal se sincroniza entre sesiones de la misma cuenta; los cambios globales solo difunden las banderas de disponibilidad, sin configuración privada. Se conserva una consulta de respaldo cada 15 segundos mientras la pestaña está visible.

## Lecturas y me gusta de las guías

Cada cuenta suma una sola lectura por artículo, aunque vuelva a abrirlo o use varios dispositivos. Los conteos anteriores se conservan porque no permiten identificar retroactivamente a cada lector.

El botón Me gusta conserva la selección y permite retirarla. La lista de personas muestra únicamente nombres, en páginas de 10, y respeta la visibilidad del artículo: las guías internas siguen reservadas para Equipo TI. Las reacciones y sus listas no generan nuevas lecturas.
