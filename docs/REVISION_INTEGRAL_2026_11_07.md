# Revisión integral del sistema

Fecha: 07/11/2026. Revisión posterior al commit `49d2735`.

## Estado

Validación funcional local completada. Las correcciones se aplicaron a los
contenedores locales de API y worker; la interfaz compiló con las dependencias
corregidas. La revisión no acredita el servidor definitivo ni la ausencia de
cualquier vulnerabilidad o fallo futuro. Scout 1.29.0 ya analizó la API:
ocho avisos altos y ningún crítico dentro del filtro aplicado. Las demás
imágenes siguen en revisión; no se presenta una cifra global cerrada.

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
reemplazar el plugin de Docker Desktop. Las otras imágenes siguen en revisión.
Un timeout se registra como `sin_verificar`, nunca como cero vulnerabilidades.

Avisos originales: CVE-2026-102010, CVE-2026-95619, CVE-2026-86140,
CVE-2026-117610, CVE-2026-118370, CVE-2026-76844, CVE-2026-85091 y
CVE-2026-74860. Deben contrastarse con los binarios y parches instalados;
no equivalen automáticamente a ocho fallos explotables.

El cambio oficial de zlib `df84af25dc1942490e1d1c899a07619152a46148`, ya
incluido en la compilación nativa, cubre CVE-2026-76844 y CVE-2026-85091 según
el [registro de Debian](https://security-tracker.debian.org/tracker/CVE-2026-76844).
El aviso de asignación alineada de `libstdc++` sigue pendiente de mitigación
confirmada; la ausencia del compilador no basta para descartarlo.
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
