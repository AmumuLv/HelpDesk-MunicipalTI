# Análisis IA: lectura del servicio y consultas internas

El módulo tiene dos vistas: **Paneles**, para entender el servicio de un vistazo, y **Consultas de datos**, para preguntar sobre los registros. El chatbot TI externo conserva su función de orientación técnica general.

Las consultas tienen una interfaz de conversación, con historial lateral, búsqueda y selector de periodo en la cabecera. En móvil, el botón **Mostrar historial** abre la lista. Ambos temas usan verde moderado: fondos teñidos, bordes visibles y texto contrastado.

**Preguntas sugeridas** abre un panel sobre el área de mensajes, separado del campo de escritura. Conserva cuatro grupos: **Tickets**, **Equipos**, **Equipo TI** y **Entender**. Cada cuenta recibe únicamente las opciones autorizadas. El campo **Buscar preguntas** encuentra sugerencias de todos los grupos sin exigir tildes ni mayúsculas; **Limpiar** permite volver al listado. Las categorías distinguen la selección activa y el panel tiene desplazamiento propio; elegir una pregunta lo cierra. También puede cerrarse con Escape.

La pregunta se muestra durante la espera. La respuesta se escribe progresivamente y el desplazamiento acompaña su crecimiento; los gráficos y las fuentes aparecen al terminar el texto. Desplazarse manualmente hacia arriba interrumpe el seguimiento. Cargar o recuperar un historial no vuelve a animar sus respuestas. Con movimiento reducido, el texto se muestra completo sin animación.

## Controles del chat

- **Nueva conversación:** comienza un hilo separado, sin perder los anteriores.
- **Buscar, renombrar y eliminar:** administran únicamente las conversaciones de la cuenta activa. Eliminar requiere confirmación; la búsqueda abarca las 100 más recientes y avisa si existen más.
- **Enter:** envía; **Shift + Enter:** escribe otra línea. Se conserva la compatibilidad con Ctrl + Enter.
- **Copiar respuesta / Copiar código:** llevan el texto al portapapeles y muestran si hubo un problema.
- **Regenerar respuesta:** vuelve a leer los datos y reemplaza la última respuesta, conservando la pregunta.
- **Editar pregunta:** reemplaza desde la pregunta elegida cuando la nueva respuesta se guarda correctamente. Las respuestas posteriores se descartan; si falla, la rama anterior permanece intacta.
- **Detener escritura:** muestra de inmediato la respuesta completa ya recibida. Es un control de la animación; no cancela cálculos del servidor.
- **Ir al último mensaje:** vuelve al final después de revisar mensajes anteriores. La escritura deja de desplazar la vista cuando la persona lee arriba.
- **Descargar conversación:** genera un archivo Markdown con preguntas, respuestas, fuentes, ámbitos, tablas y enlaces disponibles a los registros relacionados. Los enlaces se convierten en direcciones completas de la instalación actual para poder abrirlos desde el archivo descargado; siguen requiriendo iniciar sesión y tener permiso.

El formato de las respuestas admite párrafos, énfasis, listas, tablas y bloques de código mediante elementos React seguros. No interpreta HTML, imágenes ni enlaces con protocolos ejecutables. No incorpora dependencias nuevas.

## Integridad de las conversaciones

Cada turno se publica en una sola escritura con control de versión. Si otra pestaña modificó la conversación, la interfaz recupera los mensajes actuales y conserva la pregunta para reintentar. Una solicitud UUID ligada a la cuenta y al contenido evita crear chats duplicados cuando se pierde la respuesta del primer envío. Estas operaciones modifican el historial del asistente; los tickets, equipos y usuarios siguen siendo de solo lectura para sus herramientas.

## Paneles

La primera sección resume los tickets creados en las fechas elegidas, los compara con el intervalo anterior de igual duración e indica los abiertos vencidos y los abiertos sin fecha límite. Después aparecen seis indicadores y siete gráficos o listados.

Cada indicador permite desplegar qué significa, cómo se calcula y qué límites tiene. Los gráficos también tienen una guía de lectura. Las tablas permiten revisar las cifras sin depender del color.

- **Cerrados:** tickets creados en el periodo que actualmente están cerrados. No equivale a todos los cierres efectuados en esas fechas.
- **Tiempo medio:** promedio de los minutos de resolución informados; excluye los casos sin ese dato.
- **SLA:** proporción de cerrados sin incumplimiento registrado. Depende de la calidad de las marcas de plazo.
- **Satisfacción:** promedio de las valoraciones recibidas; no calificar no equivale a cero.
- **Precisión de clasificación:** proporción de evaluaciones correctas. Una categoría escrita no demuestra por sí sola que sea correcta.
- **Familias de equipos:** historial de los últimos doce meses, independiente del selector de tickets. No es un pronóstico.

Las ausencias de información se presentan como **Sin datos**. Más tickets no se interpreta automáticamente como peor atención.

## Preguntas disponibles

Además de oficinas, zonas, computadoras, causas, personas y disponibilidad TI, el asistente reconoce:

- «¿Puedes darme un resumen del servicio?»
- «¿Hay más tickets que en el periodo anterior?»
- «¿Cuántos tickets están abiertos y cerrados?»
- «¿Qué tickets tienen el plazo vencido?» (recuento por oficina, no listado individual).
- «¿Cómo evolucionan los tickets por día?»
- «¿Cuántos equipos tenemos registrados?»
- «¿Cuál es la satisfacción del servicio?», «¿Cuál es el tiempo promedio de resolución?» y «¿Cuál es el cumplimiento de SLA?».

Se pueden indicar fechas reconocidas, por ejemplo «hoy», «ayer», «el mes pasado» o un rango día/mes/año. Para filtrar consultas compatibles, usar **«en la oficina [nombre]»** o **«en la zona [nombre]»**. Los nombres ambiguos o desconocidos requieren precisión; no se sustituyen por un total global. Las consultas de familias, disponibilidad y personas no admiten estos filtros adicionales.

En una conversación puede continuarse con «¿y ayer?» o «¿y el mes pasado?», conservando la consulta y la ubicación. «Explícame eso» explica el resultado anterior. Las respuestas guardan fuentes, interpretación y contexto para retomarlas al recargar.

## Ampliación de consultas del 10/11/2026

El catálogo incorpora quince lecturas adicionales. Son consultas concretas sobre datos registrados; no convierten al asistente en un buscador libre de toda la base de datos. Las preguntas sugeridas permiten descubrirlas sin recordar su redacción.

| Grupo | Consulta disponible | Ejemplo de pregunta |
| --- | --- | --- |
| Tickets | Listados de pendientes, con códigos y enlaces | «Muéstrame los tickets vencidos», «Muéstrame los tickets más antiguos», «Muéstrame los tickets sin asignar», «Muéstrame los tickets sin equipo vinculado» o «Muéstrame los tickets con reaperturas». |
| Equipos | Calidad general del inventario | «¿Qué datos faltan en el inventario?» |
| Equipos | Dispositivos con campos pendientes | «¿Qué equipos tienen datos por completar?» o «¿Qué equipos no tienen código patrimonial?» |
| Equipos | Datos pendientes por oficina | «¿Qué oficinas tienen más datos pendientes?» |
| Equipos | Situación de los responsables | «¿Qué equipos están sin responsable?» |
| Equipos | Componentes de las PC de escritorio | «¿Qué PC de escritorio tienen componentes pendientes?» |
| Equipos | Archivos anuales disponibles | «¿Qué inventarios anuales están guardados?» |
| Equipos | Comparación de archivos anuales | «Compara los inventarios de 2025 y 2026». Si no se indican dos años distintos, solicita precisarlos. |
| Equipo TI | Carga y métricas por técnico | «¿Cómo está la carga del equipo TI?» o «¿Qué tiempos, valoraciones y reaperturas tiene cada técnico?» |
| Equipo TI | Programación de mañana | «¿Qué técnicos tienen horario mañana?» |
| Entender | Guías más consultadas | «¿Qué guías son las más consultadas?» |
| Entender | Guías mejor valoradas | «¿Qué guías están mejor valoradas?» |
| Entender | Categorías sin una guía visible | «¿Qué problemas frecuentes no tienen una guía?» |
| Entender | Movimientos conservados en auditoría | «¿Qué cambios se registraron en el periodo?» Solo para administradores. |
| Entender | Cambios de responsable de un equipo | «¿Quién cambió el responsable del equipo “CPU Tesorería”?» Solo para administradores; requiere identificar un equipo único. |

### Cómo interpretar estas respuestas

- **Pendientes de tickets:** por defecto corresponden a tickets creados en el periodo elegido y que siguen abiertos al consultar. «Historial completo» permite quitar el límite de creación. El listado muestra hasta veinte resultados e indica el total encontrado. Los abiertos sin fecha límite no cuentan como vencidos. Los casos con reaperturas pueden estar cerrados actualmente. Después de un listado se puede continuar con «¿y sin equipo?» o «¿y vencidos?».
- **Calidad del inventario:** comprueba los campos esperados según el tipo de dispositivo. **No aplica** y **No disponible** se excluyen; un dato pendiente no significa una falla física. El porcentaje general usa los datos aplicables, mientras que cada fila de campo indica qué proporción de los equipos revisados tiene ese campo pendiente. Sin denominador se presenta **Sin datos**, no cero. Los listados muestran hasta veinte equipos u oficinas y distinguen las cifras totales de lo que se muestra.
- **Responsables y conjuntos:** distingue una cuenta activa, un responsable pendiente de vincular, el uso compartido confirmado y el uso por confirmar. No tener una persona vinculada no significa abandono. Una PC de escritorio se revisa por CPU, monitor, teclado y mouse activos registrados; las laptops e impresoras permanecen independientes. Un componente sin registrar no demuestra que falte físicamente.
- **Inventarios anuales:** compara instantáneas guardadas de dos años, no los tickets del periodo ni el estado operativo actual. Usa la versión de archivo anual más reciente y, si no existe, la última versión disponible de ese año. Puede mostrar incorporaciones, ausencias, cambios de ubicación, de responsable y de datos; un equipo puede figurar en varias diferencias. Sin un identificador estable, un traslado puede aparecer como salida y alta. La comparación no reasigna ni da de baja equipos. Estas consultas requieren permiso de inventario anual y rechazan filtros de oficina, zona, tipo, equipo o tickets que no pueden aplicar.
- **Equipo TI:** separa los pendientes actuales de todo el historial de los tickets creados en el periodo y atribuidos a su técnico **actual**. No reconstruye quién tuvo cada caso en una fecha anterior. Los tiempos y valoraciones muestran sus tamaños de muestra; sin registros no se presume un valor de cero. Las reaperturas son acumuladas en esos casos. Las horas son jornadas **programadas**, descontando ausencias y feriados registrados; no horas realmente trabajadas. La programación de mañana no garantiza que alguien esté libre ni revela motivos privados de ausencia.
- **Conocimiento:** consulta guías activas visibles para la cuenta sin aumentar sus lecturas. Las lecturas son acumuladas; las valoraciones toman la decisión más reciente de cada persona y muestran cuántos votos sustentan el porcentaje. Una guía sin votos no tiene utilidad cero. No existe una serie de lecturas por día para responder esos recuentos en un intervalo. Las brechas comparan categorías normalizadas de tickets del periodo con las categorías de guías visibles; no analizan el contenido ni confirman causas técnicas.
- **Auditoría:** solo los administradores pueden solicitar estas dos lecturas. Se limita a los **quince días conservados**, con un máximo de veinte movimientos por respuesta. Muestra actor, fecha, acción y clase de registro; no incluye contraseñas, valores privados del cambio, IP ni contenido completo de auditoría. Los cambios de responsable solo incluyen eventos registrados expresamente para el equipo identificado. No encontrar un movimiento antiguo no demuestra que nunca ocurriera.

Las fechas reconocidas incluyen «esta semana» y «la semana pasada», además de hoy, ayer, meses y rangos explícitos. Las consultas del periodo usan el calendario de Lima y los límites admitidos por el sistema. El inventario actual, los archivos anuales, las métricas acumuladas de guías y la programación de mañana identifican su propio alcance para no confundirse con el selector de tickets. Un filtro incompatible pide corregir la consulta; no se presenta un total global como si estuviera filtrado.

Las respuestas pueden incluir enlaces a tickets, equipos, oficinas, guías, inventario anual, calidad, equipo TI o auditoría. La interfaz y la exportación admiten únicamente rutas locales reconocidas; abrirlas mantiene las comprobaciones de sesión y permisos de cada página. «De dónde sale esta respuesta» identifica las fuentes, y «Entender este resultado» resume su significado, qué revisar y sus límites.

## Funcionamiento y límites

Las consultas reconocidas usan reglas y agregaciones internas de solo lectura, sin tokens de Groq. Cada herramienta verifica los permisos vigentes; no habilita acciones de creación, edición o eliminación. Se conservan únicamente los argumentos de contexto admitidos, nunca operadores de base de datos aportados en el texto.

El asistente no acepta cualquier pregunta analítica arbitraria. Cuando no reconoce una petición, ofrece las consultas disponibles. El inventario describe dispositivos activos actuales; no reconstruye asignaciones históricas. Los conjuntos siguen siendo PC de escritorio y las laptops siguen siendo equipos individuales.

## Verificación del rediseño

Se comprueban consultas con MongoDB aislado y datos ficticios: periodos, exclusión de eliminados, estados, vencimientos, ausencia de plazos, inventario activo, valores ausentes, contexto, persistencia y permisos. Las pruebas de navegador verifican explicaciones, filtros, preguntas de seguimiento, escritura progresiva, recarga, accesibilidad y tamaños de pantalla en ambos temas. No se escriben tickets ni equipos en la base operativa para estas pruebas.

Verificación local del 07/11/2026: **28 pruebas de backend aprobadas**, **7 pruebas de navegador aprobadas** (4 de interfaz simulada y 3 contra API aislada), TypeScript y ESLint sin errores. La compilación Docker de API, worker y web terminó correctamente. Estas comprobaciones validan los escenarios cubiertos; no representan una garantía de ausencia de errores en cualquier consulta futura.

Revisión del chat del 08/11/2026: **54 pruebas distintas de backend y 15 subpruebas aprobadas**, más **17 escenarios de navegador** (13 con API simulada y 4 contra API y MongoDB aislados). Incluyen administración de historial, edición y regeneración, permisos/CSRF, control de concurrencia, reintentos sin duplicados, formato seguro, copia y descarga, recuperación de errores, teclado, desplazamiento, móvil y accesibilidad en ambos temas. TypeScript, ESLint y compilaciones Docker aprobados; no se agregaron paquetes.

Revisión de fluidez y conocimiento del 09/11/2026: **57 pruebas unitarias de backend** (34 nuevas y 23 de regresión), **14 escenarios de fluidez/contraste** y **22 escenarios de regresión de los chats** aprobados. Se comprobó texto parcial visible, un solo envío al proveedor simulado, lectura manual sin arrastre, gráficos y fuentes diferidos, recuperación de posición al reabrir, movimiento reducido y sugerencias en 320/1440 px. El conocimiento de importación y relevo se verificó con HTTP simulado, sin consumir cuota real. Los permisos y la lógica de importación no se modificaron.

Verificación adicional de botones, flujos y respuestas del 09/11/2026: **130 pruebas distintas de backend y 19 subpruebas**, más **53 escenarios de navegador**, aprobados. Incluyen 115 pruebas de las once suites de ambas IA, 15 nuevas regresiones de consultas, 36 escenarios existentes de interfaz, 12 casos adicionales y 5 recorridos con API/MongoDB aislados. Después de corregir el backend se repitieron las 26 pruebas afectadas contra el código definitivo. TypeScript y ESLint aprobados.

Se corrigieron tres detalles: Escape ahora cierra las sugerencias también desde el botón de apertura y devuelve el foco; las preguntas «en el sistema», «en la web» o «en la mesa de ayuda» no se confunden con ubicaciones imprecisas; el resumen de inventario respeta los filtros por tipo y equipo específico y rechaza los filtros de tickets que no puede aplicar. Se revisa cada mención de ubicación: «en el sistema en la oficina Tesorería» conserva el filtro y «en el sistema en Tesorería» pide precisión. Los argumentos adicionales de herramientas no reemplazan los filtros tipados de la API.

Las nuevas comprobaciones cubren fallos al editar/regenerar sin perder la rama guardada, reintentos, doble Enter, portapapeles denegado, selección por grupos, cierre del chatbot con respuesta pendiente, respuesta interna vacía, renombrado concurrente y acceso de técnicos con/sin permiso de análisis. Una prueba de navegador compara la suma de dispositivos de la respuesta interna con el total del inventario real de prueba y comprueba que la consulta no cambie ese total. El conocimiento de relevo se contrasta con la importación de equipos y la conservación de identidades e historial.

Los registros utilizados son ficticios y pertenecen a `helpdesk-verificacion`; las cuentas y los registros operativos no se modificaron. Groq/Gemini se simularon por HTTP: se verificaron contexto, contratos, herramientas, límites y manejo de errores, sin consumir cuota. Esta revisión no evalúa una respuesta generada por el proveedor real ni garantiza ausencia de errores fuera de los escenarios cubiertos.

Cierre del despliegue local: imágenes de API, worker y web compiladas y servicios recreados con estado saludable. La página de Análisis, la API de salud y el recurso JavaScript actualizado respondieron HTTP 200. Se comprobó la interpretación de ubicaciones dentro del contenedor definitivo sin consultar registros ni al proveedor. El proyecto aislado y sus volúmenes ficticios se eliminaron al terminar.

### Verificación de la ampliación del 10/11/2026

Las cinco suites de las lecturas ampliadas aprobaron **149 pruebas de backend** contra el código final, con MongoDB aislado cuando corresponde. Cubren todas las preguntas nuevas por API, conservación de respuestas, filtros, permisos, auditoría reservada a administradores, identificación de equipos, calidad, comparaciones anuales, programación, conocimiento y rechazo de argumentos no autorizados. Se compararon los registros operativos ficticios antes y después de consultar: las herramientas no cambiaron tickets, equipos, conjuntos, guías, versiones anuales ni perfiles TI.

La regresión previa de esta misma ampliación aprobó **130 casos distintos y 19 subpruebas** de las doce suites del asistente, chatbot y relevo de inventario. El consolidado es de **279 casos de backend y 19 subpruebas**, sin sumar de nuevo las repeticiones focalizadas.

En navegador Chromium aprobaron **61 escenarios** en una ejecución completa: 41 con respuestas simuladas, siete contra API/MongoDB aislados y trece de regresión del portal y los chats. Incluyen botones, permisos entre roles, búsqueda por grupos y tildes, recarga, edición y regeneración, fuentes, enlaces al ticket, descarga Markdown, manejo de errores, un solo envío, escritura progresiva, accesibilidad y pantallas de 320/1440 px en ambos temas. El chatbot TI conserva el azul y las consultas internas el verde.

Se corrigieron la continuidad de fechas explícitas en los listados operativos, la búsqueda de «patrimonio»/«patrimonial» y el nombre accesible del buscador. Los gráficos priorizan los datos pendientes y el nombre del dispositivo cuando corresponde; las descargas incluyen enlaces completos y autorizados a los registros. ESLint completo, TypeScript y compilación de API, worker y web aprobados. Las comprobaciones nativas del backend también aprobaron durante la construcción; esto no sustituye un análisis nuevo de vulnerabilidades.

Estas pruebas utilizan datos ficticios y proveedores simulados: no consumen cuota de Groq/Gemini ni verifican respuestas de un proveedor real. Las cifras indican los escenarios cubiertos, no una garantía de ausencia de cualquier error futuro.

Despliegue local del 10/11/2026: API, worker y web recreados y saludables. La página de Análisis, la API de salud, el JavaScript principal y el módulo actualizado devolvieron HTTP 200. Dentro de la API definitiva se verificaron las treinta herramientas, las quince lecturas nuevas y las veintiuna sugerencias nuevas sin consultar registros ni proveedores. Se retiraron el entorno aislado y sus volúmenes de datos ficticios; los volúmenes operativos se conservaron.
