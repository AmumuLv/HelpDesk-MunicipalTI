# Expediente de entrega y puesta en marcha

HelpDesk-MunicipalTI · Municipalidad Provincial de Casma · cierre de revisión 07/11/2026.

Esta carpeta reúne el funcionamiento, la operación y la preparación técnica.
Documentar o probar en la laptop no configura el servidor definitivo ni autoriza
por sí solo la publicación institucional.

## Qué documento utilizar

| Necesidad | Guía |
| --- | --- |
| Reportar y seguir un problema | [Manual del usuario](manuales/USUARIO.md) |
| Identificar, atender y cerrar incidencias | [Manual del técnico](manuales/TECNICO.md) |
| Administrar cuentas, oficinas e inventario | [Manual del administrador](manuales/ADMINISTRADOR.md) |
| Gobernar administradores y proteger la cuenta titular | [Manual del principal / Super ADMIN](manuales/ADMINISTRADOR_PRINCIPAL.md) |
| Mantener código y probar cambios | [Manual del desarrollador](manuales/DESARROLLADOR.md) |
| Comprender colecciones, identidades, archivos y conservación | [Manual de base de datos](manuales/BASE_DE_DATOS.md) |
| Utilizar y evaluar la interfaz | [Guía de usabilidad](manuales/USABILIDAD.md) |
| Cambiar al trabajador sin duplicar sus equipos | [Relevo e importación](RELEVO_E_IMPORTACION.md) |
| Distinguir la IA interna del chatbot | [IA del sistema](IA_DEL_SISTEMA.md) |
| Evaluar crecimiento y comparar situación actual/propuesta | [Arquitectura y escalabilidad](ARQUITECTURA_Y_ESCALABILIDAD.md) |
| Solicitar, comprobar y entregar una mejora | [Gestión de cambios](GESTION_DE_CAMBIOS.md) y [registro](REGISTRO_DE_CAMBIOS.md) |
| Revisar protección, incidentes y preparación pública | [Ciberseguridad](CIBERSEGURIDAD.md) |
| Instalar desde cero | [Guía sencilla para otra PC](NUEVA_PC.md) |
| Configurar un servidor y el acceso público | [Referencia técnica](INSTALACION_TECNICA.md) |

La compilación de estas guías en un documento Word se genera con
`tools/generar_manuales.py`. Las fuentes Markdown son las que deben actualizarse
al cambiar una pantalla o una regla; después se vuelve a generar el documento.

[Abrir el documento Word completo](presentacion/Manuales_y_puesta_en_marcha_HelpDesk_MunicipalTI.docx).

## Decisiones de funcionamiento

**Identidad de personas y equipos.** Un reemplazo recibe otra identidad. La cuenta
anterior conserva sus antecedentes y se desactiva cuando corresponde. Un equipo
reconocido conserva su ID y cambia de responsable; los tickets anteriores no
se atribuyen al reemplazo. Los datos ambiguos se revisan antes de confirmar.

**Dos apoyos de IA.** El motor interno calcula y consulta los registros mediante
reglas y análisis. El chatbot conversa con un proveedor opcional y usa consultas
de lectura acotadas. Conservar ambas funciones no exige pagar dos proveedores.
La propuesta de arquitectura no retira módulos que ya utiliza el personal.

**Autoridad.** Hay tres roles operativos. El principal protegido responde al
concepto de Super ADMIN solicitado, manteniendo los permisos de los demás
administradores y los límites de técnicos autorizados.

**Arquitectura.** La base actual es una aplicación modular en Docker, preparada
para mejorar por etapas. Los diagramas separan componentes existentes de
propuestas. No se presenta un diseño futuro como si ya estuviera desplegado.

## Aceptación en el servidor definitivo

| Comprobación | Responsable de completarla |
| --- | --- |
| Código, regresiones del cambio, documentación y compilación | Desarrollo, con evidencia de cada ejecución. |
| Equipo anfitrión, memoria, disco, UPS, reinicio y disponibilidad | Operador del servidor con TI. |
| Dominio, DNS, HTTPS válido y entrada desde las redes previstas | Operador y responsable de red. |
| Puertos, firewall, administración de Docker y de la base | Operador con responsable de seguridad. |
| Primer principal, administradores autorizados y permisos mínimos | Responsable municipal del servicio. |
| Inventario inicial correcto y correspondencia física del relevo | Encargado de patrimonio / TI. |
| Tratamiento de datos, envío a proveedores y retención institucional | Responsable municipal con sus áreas competentes. |
| Recuperación autorizada y probada, con datos y adjuntos | Operador con responsable del servicio. |
| Usuarios reales completan tareas sin ayuda y aceptan el flujo | Representantes de trabajadores y equipo TI. |

Hasta contar con el servidor y dominio no corresponde dar por aprobado HTTPS
público, acceso desde casa, capacidad definitiva ni recuperación en esa máquina.
Los avisos de seguridad se revisan con las imágenes exactas; un recuento de una
fecha anterior no equivale a un análisis nuevo.

## Evidencia de esta entrega

La ronda posterior se documenta en la
[revisión integral del 07/11](REVISION_INTEGRAL_2026_11_07.md). Sustituye las
cifras anteriores de validación: 456 casos distintos del backend consolidados,
159 casos de navegador más tres de instalación inicial, 21 pruebas de
herramientas y cuatro consultas satisfactorias al proveedor real sobre una
base ficticia. La prueba de carga y restauración también concluyó; sus tiempos
y límites están en ese informe. La auditoría completa y de producción de npm
quedó en cero avisos tras corregir la dependencia afectada.

Scout actualizado completó el barrido inicial y la revisión posterior a las
actualizaciones de web, ClamAV, MongoDB y proxy: **cero críticos y 20 avisos
altos por imagen, nueve CVE distintos**, incluyendo repeticiones, backports y
discrepancias documentadas. MongoDB quedó sin altos/críticos. GCC conserva
seguimiento de aplicabilidad; no se declara la entrega libre de vulnerabilidades.
Los identificadores de imágenes y pruebas están en la revisión integral.
Los párrafos siguientes conservan el alcance histórico
de la primera ronda, no el estado final de la revisión ampliada.

Entre el 06 y el 07/11/2026 se verificaron **120 casos distintos del servidor**,
consolidados entre tandas, y **cinco recorridos de Chromium**. Las repeticiones
no se suman como casos nuevos. Se utilizaron bases, cuentas y equipos ficticios
separados de la instalación operativa; no se consultaron proveedores reales de IA.

| Grupo | Resultado y alcance |
| --- | --- |
| IA y gobernanza | 66 casos distintos: aplicación autorizada, rechazo de rutas alternativas, aprendizaje, respuestas y reportes. Tres aserciones iniciales sobre avisos se corrigieron al distinguir el aviso de creación del de asignación; los once casos nuevos aprobaron al repetirse. |
| Relevo e importación | 22 casos: nueve nuevos y trece existentes. Se comprobaron IDs, orden de filas, perfil único, autoría de tickets, historial, permisos y coincidencias ambiguas. La última tanda completa aprobó 22/22 después de corregir el historial inicial de componentes y el caso de identificador nuevo con nombre contradictorio. |
| Inventario y cruces de roles | 40 casos: permisos, bajas, historial, oficinas, consultas y contexto. Ocho son casos del relevo ya incluidos arriba; por eso el total distinto es 120. |
| Navegador | Cinco recorridos aprobados: atención entre cuentas sin recargar, permisos con formulario abierto, ascenso durante edición, asignación de IA con ID real y relevo mediante carga de Excel. Se repitieron tras un timeout inicial de ingreso bajo carga simultánea y corregir un selector de la prueba nueva. |
| Herramientas y contratos | 13 pruebas de herramientas aprobadas; 158 llamadas frontend contrastadas con las 151 rutas del OpenAPI. |
| Documentación | Dieciséis guías, comprobación de enlaces locales y huella del Word normalizada para Windows/Linux. No sustituye una revisión de contenido por quien opera el servicio. |

El nuevo código evita que la posición de una fila suplante al identificador del
equipo y conserva al reportante anterior. Una coincidencia ambigua se omite para
revisión. El perfil creado por Excel no tiene credenciales ni permisos de TI.
La aplicación de una sugerencia de técnico utiliza la misma autorización,
disponibilidad y asignación que la ficha normal.

La consulta del 07/11 sobre la imagen reconstruida revisó 61 paquetes Python sin
avisos conocidos. `npm audit --omit=dev` no encontró vulnerabilidades de producción. El
análisis completo de npm informó siete avisos moderados, sin altos ni críticos;
esa diferencia corresponde al entorno con dependencias de desarrollo. No se
forzaron actualizaciones mayores como si fueran una corrección sin impacto.
Es un alcance concreto: **la auditoría actual de imágenes está pendiente**.
Docker Scout solicitó autenticación; las alternativas Grype de Windows y Linux
agotaron el tiempo al preparar su base, antes de analizar las imágenes. Se
retiraron las cachés parciales propias. No se informa cero CVE ni se
recicla un número antiguo de alertas como resultado nuevo.

La ejecución de GitHub de `fc5de05` aprobó frontend y publicación; backend falló
antes de las pruebas al descargar FFmpeg desde `ffmpeg.org`. Se conservó la versión
9.0.2 y se preparó la descarga del archivo oficial de su etiqueta de GitHub con
un SHA-256 específico y reintentos acotados. Los controles de integridad siguen
activos. La construcción detectó además un cambio de formato en los parches
externos de Expat: GitHub amplió sus abreviaturas de blobs. Se recuperaron los
bytes que coinciden exactamente con los hashes originales y se fijaron cuatro
parches verificados de Expat/libxml2 en el repositorio, con procedencia y
licencias. No se deshabilitaron las comprobaciones ni se aceptó otro hash para
ocultar la discrepancia. Las reconstrucciones finales de API, worker y frontend
aprobaron; también las pruebas nativas de las bibliotecas y el verificador de
hashes, XML/DTD, Expat, zlib, PDF, Excel y ffprobe. Se fijó Python por versión y
digest para mantener coherencia con la extensión que se reconstruye.

La instalación local se actualizó con esas imágenes. Se comprobó la coincidencia
de los archivos de negocio de API/worker con el proyecto y la disponibilidad de
API, MongoDB, Redis y web a través del proxy. El recorrido de importación se
repitió con éxito tras la última corrección. Estos ensayos no cargan registros
ficticios en la instalación operativa.

Estos resultados verifican los escenarios ejecutados; no garantizan todas las
combinaciones, la capacidad del servidor definitivo ni la ausencia de fallos futuros.
