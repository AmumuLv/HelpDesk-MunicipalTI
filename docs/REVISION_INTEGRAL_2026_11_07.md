# Revisión integral del sistema

Fecha: 07/11/2026. Revisión posterior al commit `49d2735`.

## Estado

Validación funcional local completada. Las correcciones se aplicaron a los
contenedores locales de API y worker; la interfaz compiló con las dependencias
corregidas. La revisión no acredita el servidor definitivo ni la ausencia de
cualquier vulnerabilidad o fallo futuro. Scout 1.29.0 ya analizó la API:
ocho avisos altos y ningún crítico dentro del filtro aplicado. El primer barrido
de siete imágenes detectó también avisos críticos de zlib en otros servicios.
Tras actualizar y volver a analizar, el consolidado vigente queda en **20 avisos
altos por imagen, nueve CVE distintos y cero críticos**, incluyendo backports y
discrepancias documentadas. Esto no declara el sistema libre de vulnerabilidades
ni acredita su despliegue público.

## Correcciones preparadas y reproducidas con pruebas

1. **Responsables de componentes.** Al asignar una PC a una persona, los
   componentes sin responsable recibían el nombre, pero no su intervalo de
   responsabilidad. Ahora se registra cada asignación, su actor y motivo, y se
   retira la marca de uso común. Se conservan los responsables particulares de
   otros componentes. Una repetición no duplica intervalos; una asignación que
   cambie mientras se lee la PC no se sobrescribe con la herencia.
2. **Vinculación a otra PC.** El responsable heredado al editar el conjunto de
   un componente podía cambiar sin cerrar su tramo anterior. Ahora se registra
   la transición. La edición admite un motivo opcional, limitado a 500
   caracteres. Los tickets anteriores conservan su autoría y persona afectada.
3. **Edición masiva.** Antes podía informar tres actualizaciones por un solo
   equipo al cambiar tres campos; un ID inexistente también podía generar un
   historial sin equipo. Ahora se validan todos los IDs antes de escribir, se
   eliminan IDs repetidos y se cuentan equipos distintos.
4. **Herramienta de seguridad.** Un SARIF vacío, inválido o fallido se informa
   como sin verificar, sin convertirlo en cero avisos. Se acotan los procesos
   de Docker y sus plugins descendientes: en Windows se reprodujo que Scout
   podía seguir vivo tras terminar su proceso padre y bloquear las tuberías.
   La corrección se comprueba con un proceso hijo real de prueba.
5. **Dependencia de desarrollo.** Se fija `minimatch` 11.0.1 únicamente dentro
   de `@typescript-eslint/typescript-estree`. La resolución anterior 10.2.6
   originaba siete avisos moderados propagados por el árbol de ESLint. La
   auditoría del nuevo lockfile devuelve cero avisos, también en producción.
   La compilación completa en Docker aprobó sin cambiar los archivos JS/CSS
   de producción. También se actualizó node_modules local: lint aprobó sin
   advertencias y las auditorías npm completa y de producción devolvieron cero.
6. **Consulta real del chatbot.** Groq rechazaba contar equipos activos: el
   esquema confundía la vigencia del inventario con los estados de tickets.
   Se reprodujo el error `tool_use_failed`, se distinguieron ambos conceptos
   y se verificó con el proveedor real una lectura de 31 equipos ficticios,
   coincidente con la base. Los estados operativos de equipos se filtran de
   forma literal; los estados inválidos de tickets y los filtros no admitidos
   se rechazan. No se desactivó la validación de herramientas ni de permisos.
   Un fallo de preparación de la consulta ya no pide cambiar una clave válida
   ni muestra el detalle privado del proveedor.

La corrección de minimatch sigue el [aviso del mantenedor](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249).
No se trata de siete vulnerabilidades independientes ni de siete avisos altos.

## Pruebas

| Grupo | Estado |
| --- | --- |
| Suite completa del backend | 451 casos y 44 subpruebas aprobados, en 3775,45 s |
| Chatbot después de la corrección de estados | 32 casos aprobados: 27 ya presentes en la suite y cinco regresiones adicionales; 456 casos de servidor distintos consolidados |
| Chromium, 159 casos de 28 archivos | 159 casos distintos aprobados entre la tanda completa y las repeticiones justificadas |
| Instalación vacía | Tres recorridos aprobados: primera laptop, CPU e impresora; primer administrador, zona y oficina |
| Herramientas | 21 casos aprobados, incluido límite real de procesos descendientes |
| Compilación de API y worker | Aprobada, con verificador nativo de integridad y regresiones |
| Compilación de la interfaz con dependencias actualizadas | Aprobada en Docker/Linux |
| Contratos de rutas | 158 llamadas contrastadas con 151 rutas, sin discrepancias |
| Paquetes Python de la imagen | 61 revisados, sin avisos en la fuente PyPI consultada |
| Proveedor generativo real | Cuatro casos aprobados: orientación, lectura exacta, rechazo de secretos y de eliminación; usuario normal rechazado |

Las cuatro respuestas generativas exitosas informaron 11693 tokens en total.
Los dos intentos iniciales con error 400 no informaron consumo; no se presume
que ese consumo sea cero. La clave se transfirió por entrada estándar y en
memoria al entorno aislado, sin guardarla en archivos ni mostrarla. Las
comprobaciones de permisos no generan consultas adicionales al proveedor.

La primera tanda Chromium terminó con 154 aprobados, tres fallos y dos casos
sin ejecutar. Un interceptor pendiente contaminaba el caso siguiente; ahora
se espera su cierre. Otra prueba esperaba el evento load en vez de comprobar
el DOM y los controles. El primer acceso a Vite, que compila el árbol de
desarrollo, tiene un margen de preparación acotado de 180 s; las navegaciones
posteriores conservan 60 s y no se retiraron aserciones funcionales. Se
repitieron los casos afectados y los dos no ejecutados. El envío y la
reproducción de audio aprobaron al repetirse, sin cambios en el código de
multimedia. Las repeticiones no aumentan el total de casos distintos.

Las pruebas de interfaz combinan llamadas a la API ficticia y respuestas
controladas según cada escenario. No se presentan todos los recorridos como
integraciones completas con servicios externos. Las bases de pruebas y los
índices Redis están separados de la instalación de trabajo.

## Recuperación, reportes y carga local

El ensayo aislado trabajó con **5031 equipos ficticios**, creó 100 tickets con
códigos distintos y completó 500 lecturas sin errores HTTP, repartidas entre
concurrencias de 5, 15 y 30 solicitudes. Se generaron y descargaron un PDF de
tickets y un Excel de inventario, comprobando que contenía al menos 5000 filas.

Se reiniciaron únicamente MongoDB, Redis y API de pruebas. Persistieron los
registros y la idempotencia: repetir el mismo envío no duplicó el ticket.
La copia ficticia se restauró en otra base y otro volumen; se comprobó el
inicio de sesión, el ticket, la idempotencia y la igualdad de bytes de la foto
y el adjunto. La copia temporal se retiró al terminar el ensayo.

| Concurrencia de lecturas | Solicitudes | Errores HTTP | p95 global |
| --- | --- | --- | --- |
| 5 | 50 | 0 | 495,04 ms |
| 15 | 150 | 0 | 2468,66 ms |
| 30 | 300 | 0 | 7534,73 ms |

La bandeja de tickets fue la ruta más lenta: p95 de 7785,28 ms con 30
solicitudes concurrentes; inventario obtuvo 1025,54 ms y usuarios 1135,70 ms.
No son 30 usuarios garantizados ni una certificación de capacidad: son
solicitudes de prueba sobre esta PC, que también ejecutaba otras tareas de
revisión. Hay que repetir la medición y fijar objetivos de respuesta en el
servidor definitivo.

## Seguridad y condiciones externas

Docker Scout 1.29.0 analizó la imagen de API
`sha256:fe7642e612e6f8e9f17c1b2dda7cf8e38e87bada38958d913f24e7e8a3c3dc9c`:
**ocho avisos altos y ningún crítico**, con filtro `critical,high`.
La copia temporal oficial se verificó por SHA-256 antes de usarla, sin
reemplazar el plugin de Docker Desktop. El barrido completo inicial figura abajo.
Un timeout se registra como `sin_verificar`, nunca como cero vulnerabilidades.

Avisos originales: CVE-2026-102010, CVE-2026-95619, CVE-2026-86140,
CVE-2026-117610, CVE-2026-118370, CVE-2026-76844, CVE-2026-85091 y
CVE-2026-74860. Deben contrastarse con los binarios y parches instalados;
no equivalen automáticamente a ocho fallos explotables.

El cambio oficial de zlib `df84af25dc1942490e1d1c899a07619152a46148`, ya
incluido en la compilación nativa, cubre CVE-2026-76844 y CVE-2026-85091 según
el [registro de Debian](https://security-tracker.debian.org/tracker/CVE-2026-76844).
El aviso de asignación alineada de `libstdc++` se contrastó después con el
parche oficial y una comprobación del binario, descrita abajo; la ausencia del
compilador por sí sola no basta para descartarlo.
[Referencia oficial](https://security-tracker.debian.org/tracker/CVE-2026-95619).
No se suprimen avisos para presentar un resultado artificialmente limpio.

El mismo análisis del worker devolvió los ocho avisos de API; no son dieciséis
CVE distintos. ClamAV
`sha256:08f9b2d2a30a035c2403600fbd3c2786ce6585d4a3005cdf075e5f56a93b6760`
presentó CVE-2026-86140 (alto, libxml2 con backport), CVE-2026-107891
(alto, musl 1.2.6-r3, corrección indicada 1.2.6-r6) y CVE-2026-4738
(crítico, zlib 1.3.2-r1, corrección indicada 1.4-r0).
Se inició una reconstrucción sin caché para obtener las actualizaciones;
no se considera corregido hasta verificar la nueva imagen. Por tanto, la
ausencia de críticos en API no se extiende a toda la instalación.

La comparación de musl requiere distinguir ramas: el
[registro oficial de Alpine](https://security.alpinelinux.org/vuln/CVE-2026-107891)
declara corregida `1.2.6-r3` en **3.24-main**, mientras que `1.2.6-r6`
corresponde a **edge-main**. La imagen analizada declara Alpine 3.24 y
musl 1.2.6-r3; ese aviso del analizador tiene una discrepancia de rama,
documentada sin eliminarlo del resultado original ni instalar paquetes edge.

### Barrido inicial completo, antes de actualizar las imágenes

| Imagen | Altos | Críticos | Observación |
| --- | ---: | ---: | --- |
| API | 8 | 0 | Requiere contrastar backports y libstdc++. |
| Worker | 8 | 0 | Mismos ocho CVE que API. |
| ClamAV | 2 | 1 | libxml2 con backport, discrepancia musl y zlib actualizable. |
| MongoDB | 3 | 0 | apt, x/net y klauspost/compress. |
| Web | 1 | 1 | Discrepancia musl y zlib actualizable. |
| Proxy | 3 | 1 | Discrepancia musl, x/net, compress y zlib. |
| Redis | 0 | 0 | Sin avisos altos/críticos en este barrido. |

Son 28 detecciones por imagen y **13 identificadores CVE distintos**,
incluyendo repetidos entre servicios y avisos cubiertos o discrepantes. Es
el resultado bruto inicial, no el recuento de fallos explotables ni el resultado
posterior a las actualizaciones.

MongoDB señaló CVE-2026-109518 (`apt` 2.8.3, corrección indicada
2.8.4ubuntu0.1), CVE-2026-78661 (`x/net` 0.60.0, corrección 0.62.0)
y CVE-2026-116591 (`klauspost/compress`, corrección 1.20.2). El proxy
repite los dos avisos de Go. Se prepararon las versiones mínimas corregidas
y se iniciaron reconstrucciones; este texto no las declara validadas todavía.

### Resultado posterior a las actualizaciones

Las cuatro reconstrucciones aprobaron. Se exigió zlib >= 1.4-r0 en web,
ClamAV y proxy; se actualizaron `x/net` a 0.62.0 y `compress` a 1.20.2 en
MongoDB y proxy, y apt a 2.8.4ubuntu0.1 en MongoDB. Se conservaron MongoDB
8.0.34, sus volúmenes, los backports, comprobaciones de hashes y pruebas nativas.

| Imagen final analizada | Altos | Críticos | Identificador SHA-256 |
| --- | ---: | ---: | --- |
| API, sin cambio de imagen | 8 | 0 | fe7642e612e6f8e9f17c1b2dda7cf8e38e87bada38958d913f24e7e8a3c3dc9c |
| Worker, sin cambio de imagen | 8 | 0 | d9fb04b1c7f736a90714b9d2ada2f21f14bcd118650c9d0cfe387c38b357bf32 |
| ClamAV | 2 | 0 | 3a247826f8bade7f263a9eb9147897e63712fdf8e62b1b6d99d9b79a0407668f |
| MongoDB | 0 | 0 | 26badfde8d71bcaa718924c26935c1197f45883a200c96de489fecb7f0a167ea |
| Web | 1 | 0 | 4c2e69ee745363698278627480305f4aad10ae12452ba6343b985fdad1fdc3ce |
| Proxy | 1 | 0 | 7635611c4faa742b39178cbf092c0855af7ca532e5c4443e5890392e9105f288 |
| Redis, sin cambio de imagen | 0 | 0 | 57e4255cc971b1c8d6f8a6ca283ac01bc3ecdd914273ef6bfaede87aaecd6541 |

Los avisos restantes de web y proxy son la discrepancia de musl. ClamAV
conserva esa discrepancia y el aviso de libxml2 con backport. API y worker
conservan los avisos iniciales por versiones de paquetes de distribución;
los binarios parcheados se validaron con sus hashes y pruebas de ejecución.
No se alteraron metadatos de paquetes ni se ocultaron CVE al analizador.

Para CVE-2026-95619, el [parche oficial de GCC](https://github.com/gcc-mirror/gcc/commit/200183d4ab5d57575f3dfebc6af3baf649910b9e)
explica que la implementación basada en `posix_memalign` evita el redondeo
afectado. `tools/verificar_libstdcxx.py` ejecutó los nueve pares tamaño/alineación
del caso oficial mediante la variante `nothrow`, en contenedores nuevos sin red
ni acceso a datos operativos: **9/9 en API y 9/9 en worker**, todos devolvieron
puntero nulo. No equivale a probar todas las rutas C++ ni elimina el aviso bruto.
El otro aviso de GCC, CVE-2026-102010, sigue sujeto a evaluación de aplicabilidad
y seguimiento del paquete; no se presenta como corregido únicamente porque
no estén instaladas las cabeceras C++.

Validación de las imágenes nuevas: Nginx y Caddy aprobaron su configuración;
MongoDB exportó y restauró un registro ficticio usando conexión zstd en un
contenedor aislado identificado por su SHA; ClamAV aceptó un contenido limpio
y detectó EICAR por streaming. La compilación XML aprobó sus pruebas nativas,
incluidos 3.806 casos de regresión, 49 de recursión, 324.154 comprobaciones de
API y 2.166 entradas de fuzz. La suite externa W3C no estaba incluida y ejecutó
cero casos: no se suma a los aprobados.

Las imágenes se aplicaron localmente. ClamAV excedió el primer límite de espera
de dos minutos mientras cargaba las firmas; después quedó saludable y aprobó
la prueba de detección. MongoDB quedó saludable, la API confirmó MongoDB y Redis
disponibles y el proxy respondió HTTP 200 en salud e inicio. Se retiraron los
contenedores y volúmenes del proyecto ficticio `helpdesk-verificacion`, sin
retirar volúmenes de la instalación operativa.

El servidor, dominio, HTTPS público, capacidad definitiva, política institucional
de retención y aceptación de usuarios reales requieren el entorno y las
decisiones de la municipalidad. Los ensayos locales no sustituyen esas pruebas.

La trazabilidad nueva se registra desde la operación corregida; no se inventan
intervalos para cubrir periodos históricos sin evidencia. La importación sigue
siendo parcial por fila y deshacer lotes que actualizaron equipos existentes
conserva sus límites documentados.

## Evidencias y reproducción

- Backend: `docker compose -p helpdesk-verificacion -f compose.pruebas.yml run --rm tests`
- Interfaz: `PRUEBA_API_URL=http://127.0.0.1:18100`,
  `PRUEBA_NAVEGADORES=chromium`, `COMPOSE_PROJECT_NAME=helpdesk-verificacion` y
  `npx playwright test --reporter=list` desde `frontend`.
- Herramientas: `python -m unittest discover -s tools -p 'test_*.py'`.
- Auditoría: `python tools/auditar_imagenes.py` seguido de los nombres de las
  imágenes locales; necesita Docker Scout operativo y autenticado.

Los logs temporales de esta ronda están fuera del repositorio, en la carpeta
`helpdesk-revision-integral-20261107` del directorio temporal del usuario.
No contienen la clave del proveedor; algunos diagnósticos del navegador
incluyen tokens de las cuentas ficticias, por lo que no se publican. Los datos operativos no se utilizan
para las altas, bajas, transferencias o pruebas de recuperación.
