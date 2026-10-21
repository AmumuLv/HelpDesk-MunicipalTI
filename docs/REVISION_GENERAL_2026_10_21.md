# Revisión general del sistema

**Actualización posterior:** los pendientes de esta revisión se cerraron en la
[preparación para GitHub](ENTREGA_GITHUB_PRIVADO.md). Este informe conserva los
resultados de la ejecución inicial; consulta el documento de entrega para el estado actual.

## Resultado y límites

Se ejecutó la suite completa del backend y una selección amplia de pruebas de navegador. Se corrigieron fallos comprobados, se recompilaron API y web y se actualizaron los servicios Docker. **Esta revisión no certifica que todas las funciones estén libres de errores.** Hay pruebas antiguas pendientes de adaptar y un flujo largo de usuarios que terminó por tiempo excedido.

Las operaciones de prueba se realizaron con MongoDB, Redis y API independientes, datos ficticios y directorios temporales. No se usaron credenciales reales ni se hicieron altas o bajas de prueba en la base operativa. Las llamadas a modelos externos en las pruebas del chatbot fueron simuladas.

## Correcciones

1. **Asistente interno:** las preguntas sobre incidencias «en el periodo seleccionado» podían activar la explicación del filtro. Ahora la explicación requiere una pregunta explícita sobre cómo usar o interpretar el periodo; las consultas de datos conservan su recorrido normal. Se añadieron regresiones.
2. **Historial de una persona:** el código patrimonial se obtenía del equipo, pero se perdía al construir el resumen del ticket. Ahora se devuelve `activo_codigo_patrimonial`. La prueba de historial paginado pasó tras corregirlo.
3. **Datos de demostración:** se intentaban crear impresoras y laptops como conjuntos, provocando conflictos de numeración. Solo las PC de escritorio crean conjuntos; los otros dispositivos se registran independientes, con su responsable. También se evitaron IP repetidas de la muestra y se corrigió una instrucción incorrecta sobre conectar una laptop sin cargador. La carga de demostración terminó correctamente en la instalación aislada.
4. **Lint:** se corrigieron tres errores: conversión booleana redundante, captura que solo relanzaba el mismo error y un tipo `any` en una prueba. El lint termina sin errores; conserva 16 advertencias, principalmente de dependencias de efectos y exportaciones para recarga de desarrollo.
5. **Verificador de rutas:** se actualizó el OpenAPI guardado y se corrigió el reconocimiento de filtros, ternarios y encadenamiento opcional. Las 158 llamadas detectadas coinciden con las 150 rutas documentadas. Se añadieron tres pruebas del verificador. Esta comprobación estática no sustituye la validación de cada formulario.
6. **Pruebas de navegador:** se retiraron direcciones fijas de puertos antiguos en varias suites y se corrigió la selección de la tabla de tendencia. La prueba de respuestas rápidas y la de fechas de gráficos pasaron después de estos ajustes. También se ajustaron las expectativas del número de tarjetas y el error persistente simulado del panel.

## Evidencia

| Comprobación | Resultado |
| --- | --- |
| Suite completa inicial del servidor | 243 aprobadas, 25 fallidas, 3 omitidas; además 22 subpruebas aprobadas. |
| Confirmación del servidor tras las correcciones | 59 aprobadas y 4 subpruebas aprobadas. Incluye análisis, ayuda, historial de usuarios, chatbot, persistencia de conversaciones, destinos reales e inventario anual. |
| Portal, sincronización y asistentes en navegador | 57 aprobadas, incluyendo los tres roles, estrellas, reacciones, notificaciones, temas y tamaños de pantalla. |
| Auditoría anual con API real | 4 aprobadas: validación, reintento, doble envío, plantilla, paginación, búsqueda, versiones, comparación y recuperación de CSV. |
| Otros flujos con API real | 9 aprobados en la ejecución amplia: SLA, permisos, avisos, biblioteca, auditoría, configuración y exportaciones. |
| Confirmación de dos pruebas de navegador corregidas | 2 aprobadas: insertar y enviar respuesta rápida; fechas locales y tabla de tendencia. |
| Confirmación del panel de análisis | 2 aprobadas: distribución de siete tarjetas en escritorio/móvil y recuperación tras error persistente de la API. |
| TypeScript, textos de IA y clases CSS | Aprobados. |
| Verificador de rutas y sus regresiones | Aprobados. |
| Compilación de producción de API y web | Aprobada en Docker. |

Los resultados de confirmación se superponen con los de la ejecución inicial; no deben sumarse como si fueran pruebas diferentes.

## Pendientes que impiden afirmar «todo funciona»

De los 25 fallos iniciales del servidor, dos corresponden a las correcciones del asistente y del historial, verificadas nuevamente. Los otros 23 siguen pendientes de actualización o verificación. Se concentran en expectativas anteriores:

- Creación manual de tickets sin seleccionar equipo real, equipos ajenos o personas no registradas, frente a las reglas actuales de vinculación.
- Reportar por una persona externa a la oficina, cuando el portal actual exige un compañero registrado de la misma oficina.
- Cambio de contraseña por el propio usuario, cuando el flujo actual lo deriva al administrador.
- Orden del primer evento WebSocket: ahora existe un aviso inicial de sincronización.
- Lista de destinos antes de que TI identifique el equipo, que ahora también puede ofrecer equipos compartidos disponibles.

No se debilitaron estas reglas para hacer pasar pruebas antiguas. Los fallos de exportación y analítica de esa ejecución se producen en su preparación, al intentar crear tickets con datos que hoy se rechazan; otras pruebas actuales de exportaciones sí pasaron.

En navegador, el flujo largo de crear/editar/restablecer/desactivar un usuario agotó el tiempo y no quedó certificado de extremo a extremo. La prueba antigua de conversación completa de Análisis también requiere completar su actualización a la interfaz actual y volver a ejecutarse; las otras dos pruebas de esa suite pasaron tras actualizarse. No se ocultaron ni deshabilitaron estas pruebas.

Las advertencias de lint siguen pendientes de revisión; no se añadieron silenciamientos globales. El entorno de pruebas también mostró una advertencia de escape en una docstring de Excel y otra de compatibilidad futura de WeasyPrint.

**Eliminar una versión anual sigue siendo una función no implementada.** No hay botón ni endpoint dedicado; no se considera una operación probada ni disponible. Eliminar una campaña es otra operación y no sustituye el borrado de un archivo anual independiente.

## Reproducción

- `npm run lint`, `npm run typecheck`, `npm run verify:ai-texts`, `npm run verify:clases`, desde `frontend`.
- `python tools/verificar_rutas.py` y `python -m unittest discover -s tools -p test_verificar_rutas.py`.
- `python -m pytest -ra --tb=short`, desde `backend`, **solo con MongoDB/Redis y base de pruebas aislados**. Los fixtures borran su base de pruebas.
- Playwright utiliza `PRUEBA_API_URL` para dirigir el proxy a la API aislada. La suite del portal simula las respuestas; las suites de flujos con API real requieren usuarios de demostración.
- Para incluir las pruebas de persistencia del chatbot, definir `TEST_CHATBOT_MONGO` con la URI del MongoDB de pruebas.

API, worker y web quedaron saludables después de la actualización; `/api/health` devolvió HTTP 200. Al terminar se retiraron los contenedores e imagen temporales utilizados en esta revisión.
