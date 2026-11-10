# Registro de cambios y entregas

Este registro describe cambios preparados y entregados. La columna de estado
evita confundir un archivo editado con una publicación operativa autorizada.
Los commits contienen la diferencia exacta; las pruebas repetidas no se suman
como casos nuevos.

| Referencia | Alcance | Estado y evidencia |
| --- | --- | --- |
| `fc5de05` | Protección de cuentas y ubicaciones, archivo, importación por permisos, traslado y cruces de roles; corrección del historial al liberar y reasignar. | Publicado en GitHub privado en la ronda anterior. Comprobación local registrada: 60 casos de servidor, 3 recorridos de navegador y 13 de herramientas. El estado actual de Actions se consulta en GitHub; no se deduce de este texto. |
| `CAM-2026-001` | Relevo desde Excel, controles de aplicación de IA, documentación por rol, arquitectura, datos, seguridad y procedimiento de cambios. | Validado y aplicado localmente el 07/11/2026: 120 casos distintos de servidor, cinco recorridos de navegador y construcción de las tres imágenes aprobados. Evidencia y límites en [Entrega y puesta en marcha](ENTREGA_Y_PUESTA_EN_MARCHA.md). Aprobación institucional, auditoría actual de imágenes y despliegue definitivo pendientes. |
| `CAM-2026-002` | Trazabilidad de componentes, edición masiva, consulta real del chatbot y filtros, auditoría sin resultados falsamente limpios y dependencia de desarrollo corregida. | Validado y aplicado localmente el 07/11/2026. Suite completa de 451 casos y 44 subpruebas; 32 comprobaciones del chatbot posteriores (cinco nuevas); 159 casos de navegador consolidados y tres de instalación vacía. Carga, reinicio y restauración con datos ficticios aprobados. Detalles y límites en [Revisión integral](REVISION_INTEGRAL_2026_11_07.md). La auditoría completa de imágenes y el entorno definitivo siguen pendientes. |

## Seguimiento técnico e institucional

`CAM-2026-005` (10/11/2026): corrección de la columna Equipo de tickets abiertos
y cerrados. Una PC completa conserva `conjunto_id` y `conjunto_nombre`; la
bandeja solo comprobaba `activo_nombre` y mostraba «Sin equipo». Ahora reconoce
ambos vínculos, muestra la PC completa y mantiene el identificador de columna
para conservar las preferencias. No requiere migrar ni reasignar tickets.

Validación de entrega: **676 casos de backend y 44 subpruebas**, suite completa;
**77 escenarios funcionales de Chromium** consolidados y **tres pantallas HTTPS**.
Se comprobaron registro, cancelación, edición, recarga, asignación, cierre,
reapertura, permisos entre cuentas, laptops independientes y ambas IA. Una
prueba de navegación entre pestañas se sincronizó con su estado seleccionado
y aprobó tres repeticiones; esas repeticiones no aumentan el total de escenarios.
Datos exclusivamente ficticios. El contrato OpenAPI y sus tipos se actualizaron;
160 llamadas del frontend coinciden con 153 rutas documentadas. ESLint,
TypeScript, construcción de API/worker/web y controles nativos aprobados.

La comprobación HTTPS local aprobó cookies Secure/HttpOnly, CSRF, CSP, rechazo
de orígenes ajenos, archivos y documentación privados y revocación de sesión
HTTP/WebSocket. Los archivos publicables y el contenido XML de los Word se
revisaron sin encontrar credenciales del entorno. Se actualizan el manual y
los recorridos de CI. Docker local está saludable y sirve la bandeja corregida.
Entrega autorizada al repositorio privado; el commit y Actions acreditan el
estado remoto. El dominio, HTTPS público, aceptación institucional y seguimiento
de SEG-001 continúan pendientes; esta ronda no es un nuevo escaneo de CVE.

`CAM-2026-004` (10/11/2026): ampliación de Consultas de datos con quince
lecturas sobre pendientes de tickets, calidad y responsables del inventario,
PC de escritorio, archivos anuales, equipo TI, guías y auditoría. Añade búsqueda
en los cuatro grupos, enlaces seguros en conversación y Markdown y conocimiento
actualizado del módulo. Conserva permisos de solo lectura; auditoría exclusiva
de administradores. Validación local: 149 casos nuevos de backend y regresión
de 130 casos/19 subpruebas; 61 escenarios de Chromium en la ejecución completa,
ESLint, TypeScript y construcción de API, worker y web aprobados. Detalles y
límites en [Análisis IA](ANALISIS_IA.md). Aplicado en Docker local: los tres
servicios saludables y página, API y JavaScript actualizado con HTTP 200.
Entorno aislado y volúmenes ficticios retirados al terminar. Esta entrada no
acredita publicación de los cambios en GitHub ni despliegue público.

`CAM-2026-003` (07/11/2026): actualización de seguridad de las cuatro imágenes
indicadas en SEG-001, validada con reconstrucción, análisis y comprobaciones de
servicio. Aplicada localmente; el despliegue público y la aceptación institucional
siguen pendientes. La CI de las correcciones funcionales `a00459a` aprobó en
[GitHub Actions](https://github.com/AmumuLv/HelpDesk-MunicipalTI/actions/runs/42397004250).

| Referencia | Qué revisar | Situación |
| --- | --- | --- |
| `SEG-001` | Imágenes actuales, incluidos paquetes nativos y mitigaciones compiladas | Actualizadas y aplicadas web, ClamAV, MongoDB y proxy. Consolidado posterior de siete imágenes: 20 avisos altos por imagen, nueve CVE distintos y cero críticos, incluyendo backports y discrepancias de rama. MongoDB: cero altos/críticos. GCC conserva seguimiento y comprobaciones específicas; no se declara ausencia de vulnerabilidades. Ver revisión integral. |
| `OPE-001` | Servidor, dominio, TLS, exposición y recuperación | Requiere el entorno definitivo y la aceptación de TI. |
| `DAT-001` | Retención de auditoría y chats, tratamiento por proveedores externos | Definición institucional pendiente; los plazos actuales no se presentan como aprobación legal. |
| `DAT-002` | Herencia general de responsable desde una PC a componentes que no tenían dueño | Corregida y validada en CAM-2026-002: se registra cada componente heredado y el cambio implícito al vincular otra PC. Se respetan responsables particulares y no se reconstruyen periodos antiguos sin evidencia. |

## Qué completar en cada publicación operativa

Registra fecha, commit exacto, servidor, operador, autorización del responsable,
migraciones aplicadas, pruebas de aceptación, incidencias y decisión de continuar
o revertir. No incluyas contraseñas, tokens, archivos de inventario reales ni
datos personales innecesarios.
