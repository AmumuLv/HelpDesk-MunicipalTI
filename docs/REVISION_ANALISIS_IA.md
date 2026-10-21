# Revisión de Análisis IA

## Problemas corregidos

- El asistente esperaba `respuesta` y objetos en `fuentes`, pero la API devuelve `texto` y nombres de consultas. Las respuestas se mostraban vacías y las fuentes se perdían.
- El proveedor desactivado devolvía un booleano síncrono que otros servicios intentaban esperar con `await`. Ahora mantiene la misma interfaz asíncrona que el proveedor remoto.
- La interfaz no enviaba el periodo ni el identificador de conversación: cada pregunta iniciaba otra conversación. Ahora conserva ambos y permite abrir conversaciones recientes, iniciar una nueva y recargar la página sin perder el hilo.
- Los envíos simultáneos se bloquean; las preguntas fallidas conservan el borrador y muestran un error con posibilidad de reintento. Se validan longitud y contenido después de quitar espacios.
- Las sugerencias usan consultas soportadas, sin personas ficticias. Las consultas analíticas respetan el permiso `analitica.ver`; las de inventario y disponibilidad conservan sus permisos específicos. Cada conversación sigue siendo privada de su propietario.
- Los enlaces del asistente a oficinas apuntaban a rutas de zonas inexistentes. Se corrigen y se muestran las tablas, fuentes y explicación guardadas.
- Si el modelo no utiliza herramientas, se usa la consulta directa en lugar de presentar cifras sin respaldo. Si falla la segunda redacción, se conserva la respuesta construida con los datos obtenidos.
- El periodo `365d` caía en el valor por defecto de 30 días. Ahora representa 365 días y los rangos inválidos se rechazan.
- La serie diaria truncaba primero en UTC y luego convertía a Lima, desplazando tickets de día. Se agrupa directamente por fecha local; el último instante del día también se incluye.
- Los tickets eliminados se excluyen de indicadores, rankings, causas, carga y familias de equipos. Los tickets sin datos de ubicación no rompen los mapas de calor.
- Las causas se agrupan por categoría y problema, sin repetir una barra por cada equipo. Los filtros de tipo de equipo consultan el campo real `activo_tipo`.
- Los vencimientos se calculan con la fecha límite efectiva, sin depender de una marca que pudiera estar desactualizada. Los tickets sin plazo no provocan un error del panel.
- La precisión de clasificación se calcula con evaluaciones registradas. Tener categoría es cobertura, no precisión. Sin evaluaciones se informa que no hay datos.
- La división de tickets entre equipos podía superar uno y se presentaba como probabilidad futura. La sección muestra ahora la proporción histórica de equipos con incidencias, entre 0 y 100 %, con los tickets y equipos de cada familia. No se atribuye a un modelo entrenado que no se estaba utilizando en ese cálculo.
- La proyección de volumen no utiliza como historial observado los días anteriores al primer ticket y exige un mínimo de registros.

## Presentación y navegación

- Indicadores en una cuadrícula legible, con estados de carga, error y reintento.
- Periodo y pestaña en la URL. La sección de familias explica que su ventana es de doce meses e independiente del selector.
- Rankings compactos: ocho filas y listado completo en una tabla desplegable. Las filas abren su oficina o zona.
- Fechas cortas en el eje temporal; fechas completas en la tabla. Sin puntos superpuestos en series largas ni valores fraccionarios en el eje de tickets.
- Asistente con conversación desplazable, fuentes legibles, tablas opcionales, historial y atajo Ctrl + Enter. El desplazamiento automático se limita al registro de mensajes.

## Verificación

- API y servicios: límites de fecha local, 365 días, registros eliminados, vencimientos sin marca, tickets sin SLA, precisión con evaluaciones, proveedor desactivado, continuidad y privacidad de conversaciones, permisos delegados, sugerencias y fallo de redacción del modelo.
- Navegador con API real: periodo anual, tablas y enlaces de rankings, respuestas con fuentes, continuidad, recarga, historial, nueva conversación y presentación móvil.
- Fallos de red del navegador simulados explícitamente: error del asistente con recuperación y error del panel con reintento. Los demás pasos utilizan la API del despliegue de pruebas.
- Las conversaciones generadas por las pruebas se eliminan al terminar. Las pruebas de API utilizan una base independiente; no modifican los datos principales.

Capturas: `docs/capturas/analisis-panel.png`, `analisis-asistente.png`, `analisis-panel-movil.png` y `analisis-asistente-movil.png`.

Las pruebas del proveedor remoto utilizan un sustituto controlado para reproducir su fallo. No certifican la calidad lingüística de un modelo externo ni su disponibilidad futura.

Resultado: doce pruebas distintas de API/servicios aprobadas y cuatro pruebas de navegador aprobadas sobre la compilación servida por Nginx (dos de Análisis IA y las regresiones de Usuarios y Equipo TI). TypeScript, compilación de producción y ESLint de los archivos modificados finalizaron sin errores.
