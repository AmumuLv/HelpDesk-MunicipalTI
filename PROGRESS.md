# PROGRESS

Sistema de Mesa de Ayuda TI con IA para municipalidades.

## Fase 1 — Andamiaje, datos, autenticación y permisos

**Estado: COMPLETADA**

- `docker-compose.yml` con `mongo` (réplica set de un nodo inicializado por
  `mongo-init`), `redis`, `api`, `worker` (ARQ), `web` y `proxy` (Caddy).
  Servicios opcionales por perfil: `backup` y `antivirus` (ClamAV).
- `.env.example` completo, sin secretos versionados. Zona horaria de negocio
  configurable (por defecto `America/Lima`); todo se almacena en UTC.
- 35 colecciones declaradas en `app/domain/schemas_db.py` con validadores
  `$jsonSchema` en las críticas e índices compuestos, de texto, único parcial y
  de contadores.
- Migraciones versionadas (`m001`…`m009`) con registro en `_migraciones`.
- Autenticación: argon2id, JWT de vida corta, refresco con rotación en cookie
  `httpOnly`, protección CSRF de doble envío, rate limiting y bloqueo por
  intentos fallidos.
- Autorización: permisos base por rol + matriz delegable (20 permisos, todos
  desactivados por defecto) validada **siempre en el backend**.

**Verificado**: `docker compose up -d` levanta sin pasos manuales; `GET
/api/health` responde con Mongo y Redis conectados; migraciones aplicadas al
arrancar; `app.scripts.salud` comprueba colecciones, índices y migraciones.

## Fase 2 — Sistema de tokens, componentes base y layout

**Estado: COMPLETADA**

- Tokens semánticos en OKLCH (`estilos/tokens.css`) para una paleta clara
  institucional: ningún componente escribe hexadecimales.
- Tipografía Atkinson Hyperlegible servida desde el propio servidor (tres
  archivos woff2 en `frontend/public/fuentes/`), sin CDN.
- Componentes reutilizables documentados en `docs/COMPONENTES.md`: `Boton`,
  `Campo`, `Panel`, `Insignia`, `Tabla`, `Modal`, `Selector`, `Migas`,
  `Grafico`, avisos y proveedor de sesión.
- Iconos de Lucide con nombre en español, centralizados; sin emojis.
- Marco de la aplicación con menú por rol, barra inferior en móvil y
  navegación por teclado.
- Base de la API configurable, siempre por rutas relativas: la web y la API se
  sirven en el mismo origen.

**Verificado**: `tsc -b` sin errores; `npm run build` genera el paquete de
producción; la web responde por el proxy y por su propio puerto.

## Fase 3 — Zonas, oficinas, directorio de usuarios y perfiles

**Estado: COMPLETADA**

- CRUD de zonas y oficinas con la jerarquía Zona › Oficina › Usuario y campos
  desnormalizados (`zona_id`, `zona_nombre`, `oficina_id`, `oficina_nombre`) para
  agregaciones rápidas.
- Directorio con búsqueda por nombre, correo, teléfono y anexo; alta, edición y
  desactivación (nunca borrado físico). Perfiles de zona, oficina y usuario.
- Un usuario normal solo se ve a sí mismo: el backend lo rechaza con 403.

**Verificado**: creación en cascada, zona deducida de la oficina, nombres
repetidos rechazados con 409 y aislamiento entre usuarios.

## Fase 4 — Equipos e inventario

**Estado: COMPLETADA**

- Conjuntos y activos en colecciones separadas, con `clave_natural` estable
  basada en oficina, nombre del conjunto, tipo y ordinal (no en el identificador
  del conjunto, para que la clave exista antes de que el conjunto se cree).
- Estado por campo: **Pendiente / No aplica / No disponible**, con motivo, nota,
  autor y fecha. Los campos excluidos salen del denominador de completitud.
- Esquemas por tipo (esperados y opcionales) configurables y cacheados.
- Panel de calidad del inventario con porcentaje global, por zona, oficina, tipo
  y campo, lista de pendientes y exportación.
- Responsables opcionales (persona o uso común de la oficina) con historial y
  confirmación explícita en transferencias entre oficinas.
- Opciones avanzadas **apagadas por defecto**; al desactivar se ocultan y avisan,
  nunca se borran. La memoria RAM se deriva de los módulos instalados.
- Sugerencias de autocompletado ordenadas por la frecuencia real del inventario.

**Verificado**: activo guardado solo con tipo y oficina; interruptor de opciones
avanzadas apagado de fábrica; marcar un campo como "No aplica" lo saca de los
pendientes y eleva la completitud; el detalle avanzado sigue guardado tras
desactivarlo.

## Fase 5 — Importación desde Excel (hoja = zona)

**Estado: COMPLETADA**

- Asistente automático: subir → previsualizar excepciones → confirmar →
  deshacer. No exige una pantalla de mapeo manual.
- Detección automática de columnas por palabra completa, para que "TIPO" no se
  confunda con el alias "IP".
- Reglas visibles: recorte, mayúsculas, diccionario de sinónimos, relleno hacia
  abajo del conjunto, `-` = sin código, validación de IP/MAC.
- Los campos vacíos **nunca** son error: se importan como Pendiente.
- Confirmación en transacción por lote, resumen descargable y reversión mientras
  no se modifique lo importado.
- Un grupo con un solo dispositivo se importa como equipo individual; con varios,
  como conjunto con sus componentes.

**Verificado**: con el Excel de muestra (2 zonas, 3 oficinas, 39 filas) se crean
39 equipos, 0 errores; la reimportación del mismo archivo no crea nada nuevo.

## Fase 6 — Tickets: 2 pasos del usuario y del equipo TI

**Estado: COMPLETADA**

- Usuario: paso 1 (tipo de problema con botones grandes e icono) y paso 2 (es
  para mí / es para un compañero con lista de la oficina, buscador, "otra
  persona" sin cuenta, equipos propios y de uso común, urgencia en tres opciones).
- Técnico y administrador: registro compacto con persona afectada, solicitante no
  registrado y "lo detecté yo".
- Se guardan por separado **quién reporta** y **a quién afecta**.
- Confirmación con código, tiempo esperado en palabras simples y enlace de
  seguimiento.

**Verificado**: ticket de usuario "para un compañero" con chat activo y tiempo
esperado legible; ticket manual del técnico sin chat, con nota interna y nota de
resolución de una sola vía.

## Fase 7 — Bandeja, detalle, notas, adjuntos y SLA

**Estado: COMPLETADA**

- **Regla del chat validada en el backend**: el endpoint de mensajes devuelve
  403 con `sin_chat` en tickets creados por el equipo TI. La interfaz recibe
  `tiene_chat`.
- Línea de tiempo única con todos los eventos; notas internas siempre separadas
  del chat.
- Reanudar chat cuando un usuario con cuenta adopta un ticket del equipo TI,
  conservando la trazabilidad del cambio de origen.
- SLA con calendario laboral: días laborables, tramos, feriados y pausas; el
  reloj se detiene fuera de horario y en ausencias.
- Número de ticket consecutivo asignado con incremento atómico, con reintento si
  el índice único detecta una colisión.
- Adjuntos con validación de firma real, tamaño, nombre saneado y ClamAV
  opcional.

**Verificado**: el backend rechaza el chat en ticket sin chat; notas internas y
resolución funcionan en ticket sin chat; dos tickets seguidos no repiten código.

## Fase 8 — Perfil del técnico, horarios y panel de equipo TI

**Estado: COMPLETADA**

- Horario semanal por tramos y días libres; ausencias (vacaciones, licencia,
  permiso, guardia).
- Disponibilidad calculada: Disponible, Ocupado, En espera, Fuera de horario, Día
  libre, Ausente.
- Calendario del equipo, métricas normalizadas por horas laborables reales y carga
  frente a capacidad. Al asignar fuera de horario se pide confirmación.

**Verificado**: panel con estados calculados según horario y ausencias; el
calendario combina días libres, feriados y ausencias.

## Fase 9 — Configuración, permisos delegables y preferencias de IA

**Estado: COMPLETADA**

- Configuración por secciones (General, SLA y calendario, catálogos, IA,
  notificaciones, feriados).
- Matriz de permisos delegables agrupada, aplicada en el backend, con auditoría
  de cada cambio (antes y después) y reversión inmediata.
- Preferencia de IA individual y persistente; el backend no devuelve sugerencias
  a quien las apagó, pero sigue registrando la señal de aprendizaje en
  `ia_eventos` con la marca `recomendacion_visible: false`.

**Verificado**: la matriz llega con 20 permisos y ninguno activo; un técnico sin
`equipos.crear` recibe 403 y con el permiso activado puede; desactivar la IA
devuelve el aviso honesto y la señal de aprendizaje sigue guardándose.

## Fase 10 — Tickets cerrados y exportación

**Estado: COMPLETADA**

- Filtros por periodo, zona, oficina, técnico, categoría, prioridad, equipo,
  origen, SLA y satisfacción.
- Exportación PDF (WeasyPrint) y Excel/CSV (openpyxl): tickets, inventario,
  pendientes de calidad, campañas, analítica, auditoría y equipo.
- Registro de cada exportación con estado y descarga por ruta relativa a la API.

**Verificado**: informe PDF consolidado generado y descargado; el archivo empieza
por `%PDF` y el Excel por `PK`.

## Fase 11 — Campañas de inventario anual

**Estado: COMPLETADA**

- Instantánea congelada al crear la campaña, comparación con Excel (nuevo /
  modificado con diferencia / sin cambios / ausente, nunca borrado), verificación
  física guiada, progreso por zona y oficina, cierre con versión histórica
  consultable y comparación entre años.
- El cierre exige confirmación explícita y no se puede repetir.

**Verificado**: campaña con 3 equipos; comparación que reporta 1 ausente y 0
borrados; cierre que deja el equipo como "no localizado" y guarda el histórico.

## Fase 12 — Análisis con IA y asistente conversacional

**Estado: COMPLETADA**

- 13 bloques de análisis y KPIs sobre agregaciones reales de MongoDB, con
  comparación contra el periodo anterior.
- Proyección con banda de confianza; si no hay datos suficientes se declara el
  mínimo en cada bloque.
- Predicción de fallas por familia que declara su método (`modelo_entrenado` o
  `regla_heuristica`), su explicación, la confianza y la fecha.
- Asistente con 10 herramientas de solo lectura, permisos y horarios. Sin modelo
  de lenguaje responde con consultas directas, lo dice y declara sus fuentes.

**Verificado**: `/api/analitica/panel` devuelve los 13 bloques; el asistente
responde con `explicacion` y `fuentes`; la predicción declara el método.

## Fase 13 — Reportes, auditoría y base de conocimiento

**Estado: COMPLETADA**

- Auditoría append-only con filtros, resultado y detalle antes/después.
- Base de conocimiento con artículos, pasos, valoración, populares y sugerencias
  por ticket; la valoración se guarda en su propia colección y recalcula el
  promedio con agregación real.
- Catálogos editables (tipos, estados, propiedades, categorías, sinónimos de
  dispositivo, motivos de "No aplica") y esquemas por tipo configurables.

**Verificado**: la valoración de un artículo se guarda y el promedio refleja el
total de votos; la auditoría no tiene ningún endpoint de borrado.

## Fase 14 — Verificación final

**Estado: COMPLETADA**

- [x] `docker compose up -d` levanta Mongo (réplica set), Redis, API, worker,
      interfaz y proxy sin pasos ocultos, desde un volumen vacío.
- [x] Script de humo: 40 comprobaciones contra el sistema desplegado, todas en
      verde.
- [x] Verificación de la interfaz: web y API en el mismo origen, tipografía
      local, cabeceras de seguridad y ciclo completo de una persona (entrar,
      reportar, escribir en el chat, registro del equipo TI).
- [x] Verificación de contratos: la interfaz solo lee campos que la API envía.
- [x] Suite de pruebas: 31 pruebas sobre Docker real.
- [x] Interfaz completa: 16 pantallas, responsive y con tema claro institucional.
- [x] TypeScript sin errores y compilación de producción en Docker.
- [x] `README.md`, `DECISIONS.md`, `PROGRESS.md` y `docs/COMPONENTES.md`.
- [x] Datos de demostración en un comando aparte, marcados y eliminables.
- [ ] Respaldo y restauración probados sobre un volumen real (el script existe y
      está documentado; falta la ensayo con datos en producción).

---

## Verificaciones y cómo repetirlas

| Qué | Comando | Resultado |
|---|---|---|
| Backend de extremo a extremo | `docker compose exec -T api python -m app.scripts.humo` | Solo en un despliegue temporal; crea datos de prueba |
| Interfaz y API juntas | `docker run --rm --add-host host.docker.internal:host-gateway -e VERIFICAR_HOST=host.docker.internal mesa-ayuda-api python -m app.scripts.verificar_web` | Todo funciona de extremo a extremo; ejecutarlo contra API temporal |
| Contratos API ↔ interfaz | `docker run --rm --add-host host.docker.internal:host-gateway mesa-ayuda-api python -m app.scripts.verificar_contratos` | Los contratos coinciden |
| Pruebas automáticas | `docker run --rm --network mesa-ayuda_red -e TEST_MONGO_URI="mongodb://mongo:27017/?replicaSet=rs0" -e TEST_REDIS_URL="redis://redis:6379/14" -e MONGO_URI="mongodb://mongo:27017/?replicaSet=rs0" -e APP_ENV=test -e SECRET_KEY="clave-de-pruebas" mesa-ayuda-api-dev python -m pytest` | 48 pruebas en verde |
| Tipos de la interfaz | `cd frontend && npx tsc -b` | Sin errores |
| Clases de Tailwind (`cn()`) | `cd frontend && npm run verify:clases` | Pruebas de `cn()` y revisión de sus llamadas |
| Compilación de la interfaz | `cd frontend && npm run build` | Paquete generado |

**Seguridad de datos:** `humo` y `verificar_web` hacen escrituras persistentes en
la API destino. Antes de ejecutarlos, usa un despliegue de prueba con su propia
base y verifica que `VERIFICAR_API` apunte a esa API; no los dirijas al inventario
municipal. `verificar_web` también necesita `VERIFICAR_HOST=host.docker.internal`
al ejecutarse desde un contenedor.

### Qué cubre cada prueba

- `test_importacion_excel.py`: la importación del Excel real, la idempotencia, la
  reversión y la plantilla oficial.
- `test_organizacion_inventario.py`: jerarquía, aislamiento entre personas,
  guardado con datos faltantes, "No aplica", acciones masivas, opciones
  avanzadas, uso común de oficina y calidad del inventario.
- `test_tickets_horarios.py`: los dos pasos del reporte, el chat condicionado al
  origen, la adopción de un ticket, la privacidad entre usuarios, la
  disponibilidad con horario y ausencias y la asignación fuera de horario.
- `test_gobernanza_y_reportes.py`: permisos delegables, auditoría, preferencia de
  IA, asistente honesto, predicción con método declarado, campañas, exportaciones
  PDF y Excel, analítica, base de conocimiento, arranque guiado, configuración y
  catálogos.

## Ajustes finales A1–F5

### A1 — Validación de formularios

**Estado: COMPLETADA** — commit `a308e850`.

- Los formularios muestran los errores 422 en el campo correspondiente.
- Exportación, artículos y tipos de ausencia envían valores aceptados por la API.
- Pruebas de regresión para usuario, ausencia y artículo.

### B1–B9 — Tickets, cuentas, exportación, campañas y conocimiento

**Estado: COMPLETADA**

- Cierre con nota de solución, transiciones válidas y reapertura confirmada;
  el historial consulta tanto tickets resueltos como cerrados.
- Administración puede restablecer contraseña; la acción revoca sesiones y
  queda separada de la edición normal del perfil.
- Fechas ISO de exportación se convierten correctamente; formulario de usuario
  incluye teléfono, cargo y zona.
- Campañas usan el contrato de la API para alcance y verificación, y piden
  confirmar el cierre.
- Artículos abren contenido completo, cargan el cuerpo al editar, sugieren
  categorías existentes y no repiten entradas con igual título y categoría.
- La asignación muestra el nombre del técnico y enlaza a su perfil; el tipo
  inicial de ausencia es `Vacaciones`.
- Las listas de estados se envían como parámetros repetidos, no como un único
  texto separado por comas.

**Verificado:** 48 pruebas backend; TypeScript; ESLint (sin errores, 7 avisos
preexistentes); colores; build frontend; humo; web; contratos. La base municipal
se dejó con sus 875 activos originales y sin los registros temporales de humo.

### C1–C10 — Inventario y calidad

**Estado: COMPLETADA**

- El registro y la ficha muestran características según el esquema real del
  tipo; CPU ya no pide tamaño de pantalla.
- Códigos, IP y MAC repetidos generan advertencias con enlace a la ficha, pero
  no bloquean el alta o la edición. La migración `m009` reemplaza el índice
  único del código por uno no único; se conserva la clave natural de los activos.
- Las gráficas de calidad filtran por zona/oficina, navegan al inventario
  filtrado y presentan los campos que faltan más en cada oficina.
- Las columnas del inventario se recuerdan por usuario, se pueden restablecer y
  la lista mantiene ubicación/color visibles y desplazamiento horizontal.
- La plantilla oficial no incluye equipos de ejemplo; la hoja de instrucciones
  se excluye del análisis. La vista previa es automática, cuenta zonas/oficinas
  y bloquea la aplicación si no cuadra el número de filas.

**Verificado:** TypeScript, ESLint (sin errores; 7 avisos preexistentes),
colores, build y `docker compose config -q`. 48 pruebas backend pasan usando
Mongo/Redis temporales aislados; se excluyó la prueba PDF porque la instalación
Windows no tiene `libgobject-2.0-0`. No se ejecutaron `humo` ni
`verificar_web`: el Compose actualmente activo está conectado al inventario
municipal y esos scripts escriben tickets/cuentas. No se hizo `docker compose
up` para no reiniciar servicios que usan esos datos.

### D1–D5 — Organización, perfiles y calendarios

**Estado: COMPLETADA**

- Las rutas de perfiles de zona y oficina, la administración de nombres y
  desactivación, los enlaces de ubicación y los filtros del directorio por rol,
  zona y oficina ya están integrados en el flujo del panel.
- El perfil del técnico reúne disponibilidad, ticket actual, cola, métricas,
  horario y ausencias.
- El listado de ausencias permite filtrar por técnico o ver al equipo según
  `horarios.ver_todos`. La API limita la edición a `horarios.editar_propio` para
  ausencias propias y `horarios.editar_todos` para las de otras personas.

**Verificado:** TypeScript y ESLint del componente modificado. Las pruebas de
integración dirigidas se omitieron porque el fixture no pudo iniciar MongoDB
de prueba mediante Docker; no se ejecutaron escrituras contra el despliegue
municipal activo.

### E1–E6 — Análisis, permisos y textos de IA

**Estado: COMPLETADA**

- Se conservaron los indicadores y reportes basados en datos reales, los
  perfiles y la base de conocimiento con autorización aplicada en la API.
- El resumen de tickets para usuarios cuenta los estados sobre todos sus
  registros, sin limitarse a los cinco más recientes.
- Los textos explicativos de IA del portal y del panel se centralizaron y se
  simplificaron; las explicaciones generadas se limitan a 90 caracteres,
  también cuando son una sola palabra larga.
- Se agregó `npm run verify:ai-texts`, que falla si un texto del catálogo supera
  100 caracteres.

**Verificado:** TypeScript, ESLint (sin errores; 7 avisos preexistentes),
tokens de color, verificador de textos IA y comprobación directa de la
explicación con frases largas y sin espacios. Pasaron las 3 pruebas puras de IA
con `pytest --noconftest`; las pruebas de integración se omitieron porque Docker
no pudo iniciar el MongoDB aislado. El contador y los permisos tienen pruebas
de integración que requieren ese fixture.

### F1–F5 — Diseño, navegación y portal

**Estado: COMPLETADA**

- El panel mantiene nueve grupos principales con pestañas para Tickets y
  Equipos. La bandeja muestra seis columnas; Usuarios, cuatro; Equipos, seis
  columnas iniciales y el resto queda en «Columnas».
- El inventario conserva el orden por zona/oficina/conjunto, selección por
  oficina o zona y la franja de color de zona y enlace de oficina en cada fila.
- El portal ofrece el acceso destacado para reportar, seis atajos frecuentes,
  la elección «Para mí / Para un compañero», equipos de la persona y la barra
  Recibido → Asignado → Revisando → Listo. La navegación usa «Mis avisos».
- ZonaBadge, IconoTipoEquipo, BarraProgreso y TarjetaPerfil usan tokens
  semánticos. Se retiraron el selector y las variables del tema oscuro; queda
  una paleta clara institucional.

**Verificado:** `npx tsc -b --noEmit`, ESLint (0 errores; 6 avisos),
`verificar-colores`, textos de IA, build frontend y `docker compose config -q`.
No se inició Compose ni se generaron capturas o imágenes; las pruebas backend
de integración requieren servicios aislados y no se ejecutaron en este bloque.

### G1–G3 — Regresiones de Usuarios, formularios y campañas

**Estado: COMPLETADA**

- **Usuarios.** El formulario «Nuevo usuario» sí abría, pero el pie del diálogo
  quedaba fuera de la pantalla: `max-h-[90vh]` con `flex-1` no encoge el cuerpo
  cuando la altura del contenedor es automática, así que en un formulario largo
  el botón «Crear usuario» no se podía pulsar. El cuerpo del diálogo tiene ahora
  su propio tope (`max-h-[65vh]`) y desplaza. Además, la detección de
  administrador en `estado/Sesion.tsx` normaliza el rol (mayúsculas, espacios,
  «admin») y acepta el comodín `*` de los permisos, que es el que envía el
  backend: antes una diferencia de escritura en el rol dejaba al administrador
  sin los botones de gestión aunque la API lo autorizara. El backend sigue
  exigiendo `usuarios.editar`: un técnico sin ese permiso recibe 403.
- **Formularios.** Nuevo componente `PantallaFormulario` en `Estructura.tsx`
  (columna centrada, `mx-auto w-full max-w-[1100px]`, `min-w-0`, espaciado
  uniforme) aplicado a Registrar ticket, Inventario anual, Importar inventario,
  Zonas y oficinas, Configuración, Reportar y Mi perfil. El encabezado de página
  declara `flex-wrap` y sus acciones envuelven en vez de salirse.
- **Campañas.** Dos causas reales: `campana_service.listar()` borraba el resumen
  antes de leerlo, así que la lista llegaba siempre con 0 verificados y verificar
  un equipo no movía ningún indicador; y el formulario solo mostraba el fallo en
  un aviso emergente. Ahora el progreso se calcula por campaña y, si el alcance
  no tiene equipos, el motivo se lee dentro del formulario («No hay equipos en
  ese alcance. Importa el inventario o elige otro alcance») con el alcance
  elegible (institución, zonas u oficinas). La campaña elegida gobierna
  indicadores, lista y cierre, y la recién creada queda seleccionada.

**Verificado:** 54 pruebas backend en verde (`pytest` sobre el despliegue
aislado con datos de demostración), `npx tsc -b --noEmit`, ESLint (0 errores;
6 avisos) y 9 pruebas de interfaz nuevas en tres archivos:
`permisos-usuarios.spec.ts` (el administrador ve «Nuevo usuario» y crea la
cuenta; un técnico sin permiso no ve el botón y la API le responde 403),
`responsivo-formularios.spec.ts` (390, 820 y 1440 px: sin desbordamiento, sin
recortes a la derecha, contenedor centrado de 1100 px como máximo y encabezado
que envuelve) y `campanas-inventario.spec.ts` (motivo en pantalla y flujo
crear → verificar → cerrar con versión histórica). Capturas en
`docs/capturas/`.

### H1–H5 — Cuadros de resumen, relieve y el interruptor de tema

**Estado: COMPLETADA**

- **Los tamaños de los cuadros de resumen.** La causa no era el diseño sino
  `frontend/src/lib/cn.ts`: agrupaba clases por prefijo de Tailwind, así que
  `text-2xl` (tamaño) y `text-foreground` (color) caían en el mismo grupo y el
  color eliminaba el tamaño. Un indicador de tono neutro se quedaba con la cifra
  al tamaño del texto y uno con tono de color salía grande: por eso «Abiertos» y
  «SLA en riesgo» se veían distintos de «Sin asignar» y «Cerrados». Ahora `cn()`
  agrupa por la propiedad CSS que cada clase escribe, con listas cerradas para
  tamaño de fuente, grosor de fuente y grosor de borde; la variante se conserva
  porque `hover:bg-muted` y `bg-surface` deben convivir. Las seis cifras miden lo
  mismo (36 px) y las seis tarjetas la misma altura (104 px).
- **Relieve en toda la web.** En el tema claro la caja blanca se separaba del
  fondo solo con el borde, y los bordes dominaban la pantalla. Se añadió
  `--sombra-tarjeta` (dos niveles, para indicadores y fichas) y se reforzaron
  `--sombra-md` y `--sombra-lg`; `--shadow-panel` pasó a usar `--sombra-md`, así
  que los paneles ya existentes también quedan elevados. El borde de las cajas
  decorativas bajó a `--t-borde` (#CBD5E4) y los campos de formulario pasaron a
  `--t-input`, más firme, porque su contorno es la única señal de que se puede
  escribir ahí.
- **El interruptor de tema.** Dos motivos distintos, ambos reales. Uno: el
  contenedor `web` servía un build anterior, sin el script de arranque del tema y
  sin el botón; el código fuente sí estaba bien. Otro: `BotonTema` se pintaba con
  `bg-surface`, o sea un cuadrado blanco sobre la barra azul institucional, y casi
  invisible en oscuro — por eso parecía un control roto. Ahora usa tokens `nav-*`
  como el botón de notificaciones que tiene al lado.
- **`color-scheme` inválido.** `aplicarTema` escribía «claro»/«oscuro» en
  `<meta name="color-scheme">`, valores que el navegador descarta: los controles
  nativos quedaban con el aspecto del tema contrario. Ahora escribe
  `light`/`dark`, en el script de `index.html` y en `estado/tema.ts`.
- **Contraste del botón primario.** `--t-accion` bajó a #2A61F2 y el texto que va
  encima pasó a su propio token `--t-accion-texto` (blanco en claro, oscuro en
  oscuro, porque el azul cambia de luminosidad). Antes el texto blanco sobre el
  azul quedaba en 4.46:1 en claro y 3.18:1 en oscuro.
- **Lint.** `usoActivo` en `ShellPanel.tsx` llama a `useLocation`, así que es un
  hook con nombre inválido para `react-hooks/rules-of-hooks`. Renombrada a
  `useActivo`.

**Verificado:** sobre el despliegue reconstruido (`docker compose build web` y
`up -d --no-deps web`), con Chromium y axe: el interruptor cambia
`data-tema` y el color de fondo, **persiste tras recargar** y muestra el icono y
la etiqueta del tema al que va a llevar; los seis indicadores miden 104 px de
alto, 16 px de relleno, sombra presente y cifras de 36 px; axe sobre
`/panel`, `/panel/tickets`, `/panel/equipos`, `/panel/equipos/calidad` y
`/panel/analisis` en los dos temas, **0 violaciones graves** (antes 1 por ruta en
`/panel/tickets` y `/panel/equipos`). `npx tsc -b --noEmit` sin errores, ESLint
0 errores y 6 avisos preexistentes, `verificar-colores` y `verify:ai-texts` en
verde, sin errores de consola. No se escribieron datos: solo se reconstruyó el
contenedor `web`, que no toca MongoDB.

### I1–I6 — Bandeja de tickets: filtros, fechas, colores y centrado

**Estado: COMPLETADA**

- **Las pestañas y los indicadores del resumen no filtraban.** `?vista=` se
  escribía en la URL pero `filtrosGuardados` nunca leía ese parámetro, así que
  «Todos / Sin asignar / Críticos / Cerrados» cambiaban el enlace sin cambiar una
  sola fila. Además `aria-selected` comparaba contra `vistaInicial`, que en la
  bandeja general siempre vale `todos`: la pestaña activa tampoco se movía. Ahora
  la URL manda, `vistaActiva` sale de ella y `VISTAS_RAPIDAS` declara los filtros
  reales de cada vista. Se añadió la vista «Abiertos», que es a la que ya
  enlazaba el indicador homónimo del resumen.
- **`/panel/criticos` no existía.** El indicador «Críticos» del resumen y su
  enlace «Ver todos» apuntaban a una ruta sin registrar, que caía en la redirección
  a `/`. Ahora van a `/panel/tickets?vista=criticos`. «Cerrados» apunta a
  `/panel/cerrados?tab=cerrados`, que es la pestaña correcta de esa pantalla.
- **El desplegable de SLA ofrecía valores que la API ignora.** La lista era `ok`,
  `por_vencer` y `en_pausa`; `ticket_service.listar` solo entiende `riesgo`,
  `vencido` e `incumplido`, así que tres de cuatro opciones devolvían la cola
  completa sin avisar. Se dejaron solo las que el servidor filtra.
- **Filtro por fecha.** El backend ya aceptaba `fecha_desde` y `fecha_hasta` desde
  el principio y en el tipo generado, así que no hizo falta tocar el contrato
  para escribirlos. Se añadieron dos campos de fecha en el panel de filtros, con
  `min`/`max` cruzados para que el rango no se pueda invertir, y entran en la URL
  como el resto de filtros.
- **Insignias de SLA sin color.** `estados.ts` declaraba los estados
  `ok, por_vencer, en_riesgo, incumplido, en_pausa` y `sla_service.estado_sla`
  emite `seguro, atencion, critico, vencido, cumplido, sin_configuracion`: no
  coincidía ni uno, así que `slaDe` caía siempre en «SLA sin dato». La tabla se
  reescribió con los valores reales y su color: verde en tiempo o cumplido, ámbar
  cuando queda poco, rojo a punto de vencer o vencido.
- **Colores de estado en la cola.** `DataTable` acepta ahora `tonoFila`, que
  pinta una franja lateral de 3 px en la fila de escritorio y el mismo borde en
  la tarjeta de móvil. `tonoUrgenciaTicket` en `estados.ts` es el único lugar que
  decide el color: rojo si el SLA venció o está por vencer, o si la prioridad es
  crítica; ámbar si queda poco, si la prioridad es alta o si no hay técnico; verde
  si está resuelto o cerrado. Encima va una leyenda que dice qué significa cada
  color, porque el color nunca sustituye al texto: la insignia de estado y la de
  SLA siguen nombrando el caso.
- **Espaciado y centrado.** El estado vacío de la captura del usuario salía
  descentrado (icono a la izquierda, textos escalonados, botón al centro) por el
  bug de `cn()` descrito más abajo, no por el componente. En la tabla, la columna
  «Afectado» apilaba nombre, oficina y zona en tres líneas mientras las demás
  tenían una, y el SLA se partía en tres renglones: oficina y zona van ahora en la
  misma línea y la celda del SLA no envuelve.

**Verificado:** sobre el despliegue reconstruido (`web` y `api`), con Chromium y
axe: las seis vistas devuelven filas distintas (5 / 2 / 2 / 0 / 0 / 3) con su
pestaña marcada, tanto por URL como por clic; el rango de fechas aparece en la URL
y un rango amplio devuelve la cola completa mientras uno futuro deja el estado
vacío, que ahora mide `display: flex` con los tres hijos centrados; las franjas
salen con los valores de los tokens (`rgb(23,138,85)` verde,
`rgb(200,121,0)` ámbar, `rgb(196,61,75)` rojo); axe sobre `/panel/tickets`,
`/panel/cerrados` y `/panel/mis-asignaciones` en los dos temas, **0 violaciones
graves**; sin errores de consola. Se comprobó el ciclo crear → eliminar: el
ticket aparece, se elimina y desaparece de la lista y su detalle responde 404.
`npx tsc -b --noEmit` sin errores, ESLint 0 errores y 6 avisos preexistentes,
`verificar-colores` en verde y **55 pruebas backend** en verde. El inventario
quedó con sus 875 activos y sin rastro de los tickets de prueba.

**Nota sobre las pruebas de interfaz:** `playwright.config.ts` usaba el puerto
4317 con `reuseExistingServer: true`, y ese puerto lo tenía ocupado un despliegue
de pruebas (`mesa-ayuda-prueba-*`) con su propia base de datos, así que las
pruebas se ejecutaban contra un contenedor viejo y no contra el código del
proyecto. Ahora el puerto es 4321 y `reuseExistingServer` es `false`. Con el
despliegue real, `accesos-arranque.spec.ts` pasa; `verificacion-visual.spec.ts` y
`responsivo-formularios.spec.ts` requieren las cuentas de demostración que
declara `pruebas/utilidades.ts` (`jorge.castillo@municipalidad.gob.pe` y
`usuario1@demo.local`), que esta base municipal no tiene: solo existen
`admin@demo.local` y una cuenta de usuario. Necesitan los datos de demostración
cargados o un despliegue de pruebas.

### J1–J5 — Sugerencias de IA, historial del ticket y vistas guardadas

**Estado: COMPLETADA**

- **«Aplicar» no aplicaba nada.** El frontend mandaba `{clave, accion, valor}` y
  `aplicar_sugerencia` leía `categoria` y `prioridad`, que llegaban vacías: el
  servicio registraba la decisión, anotaba el aprendizaje y devolvía «ok», sin
  tocar el ticket. El botón además no enviaba el valor ni siquiera, así que
  tampoco con el contrato arreglado se aplicaba. Ahora `SugerenciaAplicar` acepta
  `clave` y `valor`, el servicio traduce la clave al campo que corresponda y
  **aplica de verdad**: la categoría, la prioridad (recalculando el SLA) y el
  técnico sugerido. Una prioridad escrita a mano que no exista se ignora en vez
  de guardarse. El botón «Aplicar» del técnico sugerido ya no es un no-op.
- **La sugerencia volvía a aparecer para siempre.** `sugerencias_ticket` recalcula
  la clasificación desde cero y nunca miraba la decisión guardada, así que tras
  aplicar o descartar se volvía a ofrecer igual. Ahora cada decisión se guarda
  **por clave** en `ia_sugerencia.decisiones` (con el valor anterior, quién y
  cuándo) y la API la devuelve en `decisiones`. Hace falta por clave y no un
  único estado porque se puede aplicar la categoría y descartar la prioridad.
- **Aplicada: desaparece y dice qué cambió.** La tarjeta se sustituye por una
  línea: «Categoría aplicada: No enciende», y si el valor era distinto añade
  «(antes: …)». **Descartada: más discreta**, en letra pequeña y apagada —
  «Prioridad: sugerencia descartada, se mantuvo «baja»» — porque rechazar una
  recomendación no es un evento que merezca ocupar espacio. Ninguna de las dos
  vuelve a offering botones.
- **El riesgo de SLA dejó de tener botones.** Es un dato calculado, no una
  decisión: aparecía con «Aplicar / Editar / Descartar» y ninguno hacía nada.
  Ahora se muestra sin acciones.
- **Refresco doble al decidir.** `alAplicar` solo refrescaba el detalle del
  ticket, así que la sugerencia resuelta seguía en pantalla hasta recargar.
- **La línea de tiempo nunca se vio.** `Timeline` pedía
  `GET /tickets/{id}/eventos`, una ruta que el backend nunca tuvo: era un 404 en
  cada apertura de ticket y la caja se ocultaba. Los eventos ya venían dentro de
  `GET /tickets/{id}`, filtrados por rol, así que el componente usa `useTicket` y
  no hace una segunda petición a una ruta inexistente.
- **«Guardar vista» no decía qué guardaba y guardaba la mitad.** El diálogo
  anunciaba «los filtros y las columnas» pero solo mandaba filtros: `columnas`
  iba siempre como lista vacía y ni la búsqueda de texto se guardaba. Ahora
  enumera **qué se guarda con su valor actual** («Vista: Sin asignar», «Prioridad:
  Alta», «Creado desde: 1 ene 2020»), dice cuántas columnas van a la vista,
  aclara que la página no se guarda y si la vista será compartida. Guarda
  filtros, búsqueda y columnas; `DataTable` acepta `columnasForzadas` para
  restaurarlas al abrir la vista, y dejan de mandar en cuanto se toca un filtro
  a mano.

**Verificado:** sobre el despliegue reconstruido (`api` y `web`), con Chromium:
aplicar la categoría pasó el ticket de `categoria: null` a `"No enciende"` y la
línea «Categoría aplicada: No enciende» sustituyó a los botones de inmediato;
descartar la prioridad dejó «Prioridad: sugerencia descartada, se mantuvo «baja»»
en 12 px frente a los 14 px de la aplicada; tras recargar ninguna de las dos
volvió a ofrecerse y no quedó ni un botón; `GET /tickets/{id}/eventos` desapareció
de la consola, sin errores. La vista guardada devuelve
`{vista: sin_asignar, prioridad: alta, fecha_desde: 2020-01-01}` más las seis
columnas, y al pulsarla se restauran la URL y la pestaña. **56 pruebas backend**
en verde, incluida una de regresión nueva que cubre los dos fallos de la IA
(aplicar de verdad, dejar de ofrecerse, descartar sin tocar el ticket e ignorar
una prioridad inventada). `npx tsc -b --noEmit` sin errores, ESLint 0 errores y 6
avisos preexistentes, sin errores de consola. El inventario quedó con sus 875
activos, 5 tickets y sin rastros de prueba.

### K1–K5 — Cerrar tickets: permiso, solución obligatoria, historial y reapertura

**Estado: COMPLETADA**

- **El botón «Cerrar ticket» se ofrecía sin permiso.** El servidor exige, para
  cerrar o reabrir, ser el técnico asignado **o** tener `tickets.cerrar_reabrir`,
  que es delegable y **arranca apagado**. La interfaz no comprobaba nada, así que
  cualquier técnico que no fuera el asignado veía el botón, rellenaba el
  formulario y recibía un `403` sin explicación. Ahora `obtener` devuelve
  `puede_cerrar` y `puede_reabrir` con la misma regla que aplica el servidor; sin
  ellos, el botón no aparece y en su lugar se lee por qué («no eres su técnico
  asignado; se necesita el permiso «Cerrar y reabrir tickets», que concede el
  administrador»). El desplegable tampoco ofrece «Cerrado» a quien no puede.
- **Resolver sin escribir la solución daba un error del servidor.** El campo de
  nota era opcional en la interfaz y obligatorio en el API, así que el diálogo se
  abría, se confirmaba y la respuesta era un `422`. Ahora la nota es obligatoria,
  se comprueba antes de enviar y el aviso va **en el campo**, con el diálogo
  cerrado; el mensaje dice qué falta.
- **La bandeja no mostraba el equipo.** En «Historial cerrado» no aparecía qué
  equipo se había reparado, que es justo lo que se busca al revisar casos ya
  terminados. Se añadió la columna «Equipo» con el nombre del activo y su
  conjunto.
- **Un ticket resuelto seguía en la lista de activos.** La vista por defecto se
  llamaba «Todos» y no filtraba nada, así que un ticket recién resuelto se
  quedaba en la cola de trabajo hasta que alguien lo cerraba de verdad. Ahora la
  primera vista es «Abiertos» (`solo_abiertos`), que es la cola real; lo
  terminado vive en «Cerrados». `?vista=todos` sigue funcionando como alias.
- **Reapertura con confirmación.** El botón «Reabrir ticket» abre un diálogo que
  nombra el ticket y dice a qué estado vuelve, y solo entonces cambia. Se
  comprueba además que el dropdown no ofrezca la reapertura por la puerta
  trasera.

**Verificado:** sobre el despliegue reconstruido (`api` y `web`): resolver sin
nota ya no abre el diálogo y muestra el error en el campo; escribiendo la nota el
ticket pasa a `resuelto` con `resuelto_en` y nota guardada; `solo_abiertos`
devuelve `{enAbiertos: false, enHistorico: true}`; las cabeceras de la bandeja
son `["Ticket","Afectado","Estado y prioridad","SLA","Equipo","Técnico",
"Actualizado"]`; reabrir muestra la confirmación y deja el ticket en
`en_progreso`. **60 pruebas backend** en verde, con un archivo nuevo
`tests/test_cierre_y_reapertura.py` (4 pruebas) que fija el comportamiento:
`puede_cerrar` del asignado frente al de otro técnico, `403 sin_permiso` al
intentar cerrar el ticket de otro, la solución obligatoria, que el cierre pasa por
`resuelto` dejando las dos fechas, la reapertura con contador `veces_reabierto`, y
que un ticket resuelto sale de la cola activa. `npx tsc -b --noEmit` sin errores,
sin errores de consola. El inventario quedó con 875 activos y sin rastros de
prueba.

**Nota sobre el proveedor de IA:** los logs de la API muestran `401 Unauthorized`
contra `api.deepseek.com`. La clave configurada ya no es válida, así que las
funciones de lenguaje (resumen, causa raíz, respuesta sugerida) están cayendo al
modo de reglas y el sistema lo dice, pero conviene revisarla.

### L1–L4 — Menú de la cuenta, notificaciones y el botón «Limpiar»

**Estado: COMPLETADA**

- **El menú de la cuenta no llevaba a ninguna parte.** Se desplegaba bien, pero
  dentro solo había «Cerrar sesión»: ni perfil, ni configuración, ni el
  directorio de usuarios. Abrirlo no servía para nada. Ahora lista **Mi perfil**,
  **Mis tickets**, **Configuración** (si hay permiso) y **Usuarios** (si hay
  permiso), y al pulsar una opción el menú se cierra y navega.
- **«Mi perfil» sacaba del panel.** La ruta `/perfil` usa el cascarón del portal,
  así que desde el panel esa opción cambiaba a otra interfaz sin barra lateral y
  se perdía el contexto. Se añadió `/panel/perfil`, que muestra la misma pantalla
  dentro del panel; `/perfil` sigue siendo la de quien entra por el portal.
- **El aviso de la campana no llevaba a ninguna parte.** El backend guarda un
  `enlace` con la forma `/tickets/{id}`, que no corresponde a ninguna ruta: el
  panel usa `/panel/tickets/{id}` y el portal `/mis-tickets/{id}`. Al pulsar un
  aviso se caía a la ruta `*` y volvía al inicio. Ahora la ruta la arma el
  componente con `ticket_id` según el rol (y entiende la forma antigua si algún
  registro no lo trae), y al abrir un aviso se marca como leído: antes solo
  existía «Marcar todas», así que la lista no bajaba nunca.
- **La campana no existía en el portal.** Es justo donde está quien reporta el
  problema y recibe el aviso de que se resolvió, y era el único sitio sin forma
  de verlo. Se extrajo a `componentes/dominio/CampanaNotificaciones.tsx` y ahora
  está en los dos cascarones, con un texto que explica cuándo aparece algo en vez
  de un «No tienes notificaciones» seco. Sin lista, `useNotificaciones` consulta
  cada 30 s: el aviso en vivo por WebSocket no está conectado, así que el
  contador se quedaba con el número de la última visita.
- **El botón «Limpiar» salía sin recuadro.** Usaba la variante `fantasma`
  (transparente, sin borde) y se leía como texto suelto junto a «Filtros» y
  «Guardar vista», que sí tienen marco. Ahora usa `secundario` y lleva una ✕.

**Verificado:** sobre el despliegue reconstruido (`web`): el menú de la cuenta
muestra `["Mi perfil","Mis tickets","Configuración","Usuarios","Cerrar
sesión"]`; «Mi perfil» deja la ruta en `/panel/perfil` conservando la barra
lateral y cierra el popover; la campana aparece en el panel y en `/mis-tickets`,
y con lista vacía explica el motivo; «Limpiar» se ve con fondo blanco y borde
`1px solid rgb(203,213,228)`, alto 40 px; el menú también se ve bien en modo
oscuro. **61 pruebas backend** en verde, con una prueba nueva en
`tests/test_cierre_y_reapertura.py` que fija el contrato del aviso: al resolver un
caso, quien lo reportó recibe una notificación con `ticket_id` y el código del
ticket en el título, y `POST /notificaciones/leer?ids=…` marca solo esa y baja el
contador en uno. `npx tsc -b --noEmit` sin errores y ESLint sin errores, sin
errores de consola.

**Nota sobre notificaciones:** en la base municipal hay 8 avisos, pero son de la
persona usuaria (`jurasicpar.muertesegura@gmail.com`), no del administrador de
demostración; por eso la campana del panel aparece vacía y es correcto. El aviso
en vivo por WebSocket (`/api/ws/notificaciones`) sigue sin conectarse en la
interfaz: mientras tanto la campana refresca cada 30 s.

### M1–M4 — Vistas guardadas que sí filtran y ventanas centradas

**Estado: COMPLETADA**

- **Las ventanas emergentes estaban descentradas en toda la página.** No era un
  problema de cada pantalla: `DialogModal` se centra con `top-1/2 left-1/2` más
  `-translate-x-1/2 -translate-y-1/2`, y `cn()` veía las dos medias traslaciones
  como la misma clave, así que se quedaba **solo la última**. El diálogo se
  colocaba en el punto medio de la pantalla y se corría media anchura hacia la
  derecha. Afectaba a todos los diálogos del panel: guardar vista, nuevo usuario,
  nueva zona, nueva campaña, cerrar ticket, reabrir, eliminar.
- **Un acceso rápido guardado no filtraba ni actualizaba.** Al abrir una vista
  guardada se perdían tres cosas:
  1. **La vista rápida de la que se guardó.** Se guardaba en el campo `vista` del
     registro y al abrirla no se leía: una vista creada sobre «Cerrados» volvía
     a la cola de abiertos.
  2. **Las listas de valores.** La vista «Cerrados» guarda `estado:
     ['resuelto','cerrado']` y al volcarlo con `String(...)` quedaba
     `estado=resuelto,cerrado`, que no corresponde a ningún estado: la tabla se
     quedaba vacía. La API espera el parámetro repetido.
  3. **El texto buscado**, que se quedaba solo en el registro.
  Además, si el filtro resultante era el mismo que ya se estaba viendo, la
  consulta no se volvía a lanzar y la tabla no se movía. Ahora la URL que se
  escribe es `?vista=cerrados&estado=resuelto&estado=cerrado&pagina=1`, se
  invalidan los tickets y sale un aviso con el nombre de la vista aplicada.
- **`solo_abiertos` no se reconocía a la vuelta.** Se leía solo como `1`, y la
  vista guardada lo dejaba como `true`: al abrirla el filtro no coincidía con nada
  y se perdía en silencio. Los filtros que viajan por la URL ahora están en una
  tabla única (`FILTROS_URL`) con cómo se escriben y cómo se leen, para que
  guardar y aplicar no puedan separarse otra vez.
- **El botón «Limpiar» ya tiene recuadro** (ronda anterior) y **las pruebas de
  `cn()` ahora son permanentes**: `tools/verificar-clases.mjs` carga la función
  real, la somete a 37 casos y revisa las llamadas de `cn()` de los 78 archivos
  del proyecto avisando de pares de ejes que se pisan. Es la forma de que esto no
  vuelva a pasar en silencio.

**Verificado:** sobre el despliegue reconstruido (`web`), midiendo el centro del
diálogo contra el ancho real de maquetación: desviación `0 px / 0 px` en «Guardar
esta vista», «Nuevo usuario», «Nueva zona», «Nueva campaña de inventario» y
«Cerrar ticket». Ida y vuelta de una vista guardada: se crea sobre «Cerrados»
(4 tickets cerrados), se vuelve a «Abiertos» (3 abiertos) y al pulsarla la tabla
pasa a los 4 cerrados con la URL `?vista=cerrados&estado=resuelto&estado=cerrado`;
la vista de prueba se borró y no quedó rastro. `?estado=resuelto&estado=cerrado`
devuelve 4 filas y `?estado=resuelto,cerrado` devuelve 0, que es exactamente la
diferencia entre lo que se escribía y lo que el servidor entiende. `npm run
verify:clases` en verde, `npx tsc -b --noEmit` sin errores, ESLint sin errores,
sin errores de consola. **61 pruebas backend** en verde.

**Limpieza del entorno de pruebas:** `conftest.py` creaba una base
`mesa_ayuda_test_<aleatorio>` por corrida y no la borraba al terminar; había 37
acumuladas (unos 90 MB) en el Mongo del despliegue. Ahora la borra en el
`finally` de la fixture `db`, y se borraron las que quedaban. La base municipal
sigue con 875 activos, 7 tickets vivos y 2 usuarios.

### M5 — La vista guardada que está filtrando se ve marcada

**Estado: COMPLETADA**

- **No se distinguía la vista aplicada.** Los accesos rápidos se pintaban todos
  igual, así que no había forma de saber por qué la tabla mostraba lo que
  mostraba: podía ser la vista guardada, un filtro puesto a mano o la vista por
  defecto. Ahora la que coincide con lo que hay en pantalla se marca con el
  color de la institución (el mismo ámbar de las pestañas rápidas), con borde
  marcado y el texto en negrita; las demás quedan en blanco.
- **La marca se apaga sola en cuanto se toca algo.** Se compara la «huella» de
  los filtros de pantalla con la de cada vista guardada, así que al poner un
  filtro a mano deja de coincidir y se desmarca. No es un estado que se active al
  pulsar y se olvide: si recargas la página o compartes el enlace, la marca se
  conserva.
- **Al guardar, la vista nueva queda marcada al instante**, porque el registro
  que se acaba de crear es, por definición, lo que se está viendo.
- **La comparación no depende del orden.** `estado=resuelto&estado=cerrado` y
  `estado=cerrado&estado=resuelto` son la misma vista; la huella ordena las claves
  y los valores antes de compararlos.
- De paso, **guardar ya no copia los valores derivados**: se guardan los filtros
  que hay en la URL, no el objeto que pasa por la tabla (que incluía la página y
  el tamaño).

**Verificado:** sobre el despliegue reconstruido (`web`). Viendo «Abiertos», que
es justo lo que guarda la vista existente: fondo `rgb(251,241,210)`, texto
`rgb(107,79,0)`, grosor 600, marcada. Sobre «Cerrados» o con un filtro a mano:
fondo `rgb(255,255,255)`, texto `rgb(22,32,51)`, grosor 500, sin marcar. En modo
oscuro: fondo `rgb(58,47,16)`, texto `rgb(242,210,122)`, marcada. `npx tsc -b
--noEmit` sin errores, ESLint sin errores, `verify:clases` en verde, sin errores
de consola.

### N1–N5 — Tipos de equipo nuevos, búsqueda de Equipos y barra de filtros

**Estado: COMPLETADA**

- **Router, switch, tablet, celular, servidor, UPS, disco duro externo, sistema de
  audio y «otro» se registraban con los campos de una computadora.** Estos tipos
  estaban en el catálogo pero sin esquema propio, así que caían en el esquema
  genérico y el formulario preguntaba dirección IP y MAC a un amplificador. Ahora
  cada tipo tiene su esquema, tomado de las columnas de la plantilla del Excel:

  | Tipo | Pregunta además de marca, modelo, nombre y código |
  |---|---|
  | CPU, Laptop, **Servidor** | procesador, memoria RAM, almacenamiento, IP, MAC, estado |
  | **Router, Switch** | IP, MAC, estado |
  | **Tablet** | tamaño de pantalla, MAC, estado |
  | **Celular, UPS, Sistema de audio, Otro** | solo estado |
  | **Disco duro externo** | almacenamiento, estado |

  Se aplicó con la migración `010_esquemas_tipos_nuevos`, que **solo inserta** los
  tipos que no existían: los que ya estaban no se tocan, para no perder lo que el
  administrador haya ajustado en Configuración.
- **Todo se daba de alta como parte de un conjunto.** La casilla venía marcada
  para cualquier tipo, así que un router o un sistema de audio acababan dentro de
  «Computadora N°01». Ahora el punto de partida depende del tipo: marcado para CPU,
  Laptop, Monitor, Teclado, Mouse e Impresora; sin marcar para el resto, y el texto
  explica por qué.
- **No se podía registrar ningún equipo.** El botón «Continuar» del primer paso
  pedía tipo **y** oficina, pero la oficina se elige en el segundo paso: el
  asistente se quedaba bloqueado. Ahora el primer paso solo pide el tipo.
- **La barra de filtros mezclaba dos formas.** El buscador y la casilla entraban en
  la fila de los controles sin rótulo, junto a campos que sí lo tenían, y se leía
  como desalineada. Las seis celdas tienen ahora la misma estructura —rótulo arriba,
  control abajo—: Buscar equipos, Zona, Oficina, Tipo, Agrupar por y Responsable
  del Excel. Comprobado a 1600, 1280, 1000 y 780 px: los rótulos de cada fila
  comparten coordenada.
- **La búsqueda no decía qué se escribe ni qué encuentra.** El texto de ayuda
  underneath del buscador ahora lo dice —código patrimonial, nombre, marca,
  modelo, IP, MAC, conjunto y responsable— y el panel de coincidencias lleva
  encabezado con el número de resultados, botón para cerrarlo y alto máximo con
  barra de desplazamiento: antes las 25 coincidencias empujaban la tabla entera.
  Además las consultas van con 300 ms de retardo, porque antes salía una petición
  por tecla y las respuestas podían llegar desordenadas.

**Verificado:** sobre el despliegue reconstruido (`api` y `web`). Recorriendo el
asistente para cada tipo, sin guardar nada: CPU y Servidor piden procesador, RAM,
almacenamiento, IP, MAC y estado; Router y Switch piden IP, MAC y estado; Tablet
pide tamaño, MAC y estado; UPS, Sistema de audio y Otro piden solo estado; Disco
duro externo pide almacenamiento. Ninguno de los perifericos pide IP. La casilla
de conjunto sale marcada solo para CPU y desmarcada para el resto. El resumen del
paso «Confirmar» muestra exactamente los mismos campos. `npx tsc -b --noEmit` sin
errores, ESLint sin errores, `verify:clases` en verde, sin errores de consola.
**63 pruebas backend** en verde, con dos pruebas nuevas en
`tests/test_organizacion_inventario.py`: una fija qué campos pide cada tipo y que
un periférico no pregunte IP ni MAC; la otra fija que el filtro de responsables
pendientes coincida con lo que cuenta la puesta en marcha. Inventario sin tocar:
875 activos, 7 tickets, 2 usuarios, ninguna base de prueba.

**Lo que no pude reproducir:** el error al pulsar un resultado de la búsqueda.
Probé 15 resultados distintos (`comp`, `EPSON`, `teclado`, `impresora`,
`desktop`), filas de la tabla con la búsqueda activa, equipos sin oficina y equipos
dados de baja: en todos los casos navega bien a `/panel/equipos/:id` sin errores de
consola ni mensajes en pantalla. Lo que sí estaba roto ya está corregido: el panel de
coincidencias está acotado y con encabezado propio, y ahora limpia la búsqueda al
abrir un equipo para que no vuelvas con la tabla ya filtrada. Si te vuelve a
pasar, dime **qué mensaje sale** (o una captura) y lo busco con eso.

### O1–O4 — Fila del equipo, color de zona, columnas y estados

**Estado: COMPLETADA**

- **La fila decía unas cosas y otras.** El Excel nombra los equipos como quiere:
  las computadoras traen el nombre en la red («PULL-D-GV53JNV3») y los monitores,
  mouses y teclados traen «Computadora N°03 - Monitor». Con el tipo en la tercera
  línea, unas filas se leían como nombres y otras como tipos. Ahora la fila es:

  ```
  PULL-D-GV53JNV3                              ← el nombre, o el tipo si no hay
  CPU · TEROS TEROS · 740895000230             ← el TIPO siempre, en negrita
  [💻 Computadora N°03]                        ← el conjunto como distintivo corto
  ```

  Da igual cómo se llame cada equipo: el tipo está siempre a la vista, y el
  conjunto ya no ocupa una línea entera.
- **Las zonas no tenían color.** No era que se vieran parecidas: **el punto de
  color era invisible**. Las variables `--zona-1`…`--zona-8` estaban declaradas
  dentro de `@theme`, y Tailwind v4 solo emite las que alguna clase utiliza; como
  solo se leen desde un `style` en línea, nunca llegaron al navegador y
  `var(--zona-4)` no resolvía. Las paletas de zonas e iconos se movieron a
  `:root`, que sí se emite siempre. Además el fondo y el borde de la pastilla se
  tiñen con el color de la zona, no solo el punto.
- **Los estados se confundían entre sí.** «Operativo» y «Dado de baja» se
  distinguían solo por un matiz del fondo. Los estados del equipo ahora se pintan
  **rellenos**: verde oscuro, rojo oscuro, ámbar… cada uno una mancha distinta que
  se ve de un vistazo. Se usa el token `-fuerte` de cada color como fondo y
  `primary-foreground` como texto, que es el mismo par que ya se usó y se probó
  en los botones; así el contraste funciona en los dos temas sin seis pares de
  tokens nuevos.
- **38 equipos salían como «Sin estado».** El Excel usa `OPERATIVO`,
  `INOPERATIVO`, `INOPERATIVA` y `Dado de baja`, y el catálogo usa otros nombres:
  lo que no coincidía caía en el estado desconocido, que es indistinguible de un
  dato corrupto. Se añadieron `inoperativo` e `inoperativa` al mapa, con icono de
  apagado.
- **Columnas: «Restablecer» y guardado.** Los dos ya existían y funcionaban —
  comprobado marcando «Tipo» y «Conjunto», que sobreviven a cambiar de página y a
  recargar, y «Restablecer» vuelve al estado por defecto y también se guarda. Lo
  que sí sobraba era una casilla **«menu»** en la lista: era la columna del botón
  de acciones, que se podía desmarcar y dejaba la fila sin forma de abrirse. Ahora
  esa columna no se ofrece.

**Verificado:** sobre el despliegue reconstruido (`web`). Fila: las ocho primeras
filas muestran el tipo antes de la marca («Impresora · EPSON L6270 · 742223580169»,
«CPU · CYBERLINK CASE · 740899500012», «Monitor · LG FALTRON1955 · …») y el
conjunto como distintivo. Zona COMPLEJO: fondo `color(srgb .76 .44 .24 / .18)` y
borde `/ .55`; las cinco zonas tienen índices distintos (COMPLEJO 4, MERCADO 3,
PALACIO 1, PISCINA 5, SEGURIDAD 2). Estados: Operativo `rgb(14,92,55)` sobre
blanco, Inoperativo y Dado de baja `rgb(142,40,51)` sobre blanco, cada uno con su
icono. Columnas: la lista va de «Equipo» a «Observaciones», sin «menu». Marcado y
guardado confirmado con `localStorage`; «Restablecer» confirmado tras recarga.
`npx tsc -b --noEmit` sin errores, ESLint sin errores, `verify:clases` en verde, sin
errores de consola. **El inventario tiene ahora 876 equipos, no 875**: el
extra lo registró la persona usuaria probando el asistente con un **Celular**
(`LeyvaPrueba1`, Xiaomi TR3, PALACIO/ALCALDÍA, creado por «Administrador» el 9 de
octubre a las 21:58), es decir, que el alta de los tipos nuevos funciona de
verdad. Las comprobaciones de esta ronda no escribieron nada.

### P1–P2 — La columna «Datos» y una paleta de zonas que se distinga

**Estado: COMPLETADA**

- **«Completo» y «50%» no decían nada de la forma de la columna.** Eran dos
  pastillas con un número, y con dos tonos: un inventario al 90 % se veía igual
  que uno al 50 %. Ahora la celda es una **barra con la cifra al lado**, y la
  escala tiene cuatro pasos: 100 % verde, 70-99 % azul, 30-69 % ámbar, menos de
  30 % rojo. De un vistazo se ve cuántos equipos están completos, cuántos van por
  la mitad y cuántos están casi vacíos, sin leer un solo número. El texto
  «Completo» se mantiene en el 100 % porque se lee mejor que «100%».
- **Las zonas seguían sin distinguirse entre sí.** COMPLEJO y MERCADO eran los
  dos naranjas, PALACIO y PISCINA los dos azules: había que leer el nombre para
  saber cuál era cuál. Se rehízo la paleta repartiendo los ocho tonos cada 45°
  en la rueda de color, alternando claridad: azul, verde azulado, verde, ocre,
  naranja, granate, violeta y fucsia. Ninguna pareja queda cerca. Además el
  **texto** de la pastilla lleva el color de la zona mezclado con el del tema —en
  claro se oscurece y en oscuro se aclara—, así que el tono se lee sin depender
  del punto ni del fondo.

**Verificado:** sobre el despliegue reconstruido (`web`), con las cinco zonas de
la municipalidad pintadas una junto a otra en los dos temas. COMPLEJO ocre,
MERCADO verde, PALACIO azul, PISCINA naranja y SEGURIDAD CIUDADANA verde azulado:
las cinco se distinguen de un vistazo. La columna «Datos» muestra la barra con
relleno sólido sobre pista neutra (`rgb(139,214,176)` al 100 %, `rgb(242,210,122)`
al 50 % en tema oscuro) y la cifra al lado. `npx tsc -b --noEmit` sin errores,
ESLint sin errores, `verify:clases` en verde, sin errores de consola. No se tocó
la base: el índice de cada zona (`color_indice`) es el de siempre, solo cambia el
color al que apunta.

### Q1–Q3 — La tabla se lee mejor y la barra horizontal siempre está a mano

**Estado: COMPLETADA**

- **La barra horizontal solo estaba al final.** Con todas las columnas a la vista
  la tabla mide 2.186 px en 1.079 px visibles: su barra quedaba **mil píxeles más
  abajo**, así que había que bajar hasta el final de la tabla para poder moverla,
  y al principio no se podía. Ahora hay una segunda barra `sticky bottom-1` que
  está siempre en pantalla y se va sola cuando la tabla queda fuera de vista.
- **El tirador se pinta a mano.** En algunos navegadores la barra es superpuesta y
  no se ve hasta que pasas el ratón por encima, que es justo lo que se quería
  quitar. La pista es una línea fina con borde y su tirador una cápsula que se
  arrastra; al pulsar en la pista salta a ese punto, como en cualquier barra. El
  ancho del tirador es la parte visible de la tabla y su desplazamiento, la parte
  recorrida del hueco.
- **La tabla se amontonaba.** Las celdas de datos se quedan en una línea y lo que
  no cabe se recorta, en vez de partirse en tres y estirar la fila. Se acortaron
  cinco rótulos —«Tamaño de pantalla» → «Pantalla», «Memoria RAM» → «RAM»,
  «Dirección IP» → «IP», «Dirección MAC» → «MAC»— y el ancho máximo de celda bajó
  de 14 a 11 rem. Con eso **las columnas por defecto ya no necesitan scroll**: la
  tabla ocupa exactamente lo que hay (1.079 de 1.079). El borde del contenedor
  hacía que `w-full` se pasara 38 px y apareciera una barra que no hacía falta;
  ahora la tabla usa `min-w-full`.

**Verificado:** sobre el despliegue reconstruido (`web`). Con las columnas por
defecto no hay desborde ni barra. Con las 16 columnas: barra visible, tirador de
569 px sobre una pista de 1.081, y al arrastrar 300 px el `scrollLeft` de la tabla
pasa de 0 a 947 (el desborde completo) —comprobado con el ratón, no solo que se
vea—. La barra se mantiene en `y=764` con la página bajada 1.100 px. `npx tsc -b
--noEmit` sin errores, ESLint sin errores, `verify:clases` en verde, sin errores de
consola, **63 pruebas backend** en verde.

### R1–R6 — La tabla se lee mejor de un vistazo

**Estado: COMPLETADA**

- **El encabezado era una lista de palabras sueltas.** Eran títulos del color de la
  tinta apagada sobre el mismo blanco de las filas, sin fondo ni borde que los
  separara: no se leían como una cabecera. Ahora la fila entera lleva un fondo
  suave (`bg-surface-2`), borde propio y más aire (16 px a los lados, 14 px arriba
  y abajo, 49 px de alto frente a 41), con los títulos en `text-foreground/70` y
  peso 700. **Las mayúsculas se quedan**: se probaron en minúsculas y la fila
  perdía el golpe visual que hace que «Equipo», «Ubicación» y «Responsable» se
  distinguan de un vistazo. Lo que le faltaba no eran las mayúsculas sino que no
  había nada detrás.
- **COMPLEJO salía de color arena.** El motivo era concreto: su tono era un ocre
  apagado (`#a16207`), el único terroso de la lista, y al mezclarlo con blanco para
  pintar la pastilla quedaba como un tono neutro por error. Además MERCADO y
  COMPLEJO eran los dos naranjas y PALACIO y PISCINA los dos azules, así que había
  que leer el nombre. La paleta se rehízo: los seis índices en uso están a 32° o
  más de separación en la rueda de color y **ninguno es terroso**. COMPLEJO es
  violeta. Los dos tonos terrosos que quedaban libres van a los índices 7 y 8,
  que nadie usa. El tinte de la pastilla subió del 22 % al 26 %.
- **La columna Ubicación tenía dos rayas de color.** La celda pintaba un
  `border-l-4` y `EnlaceOficina` pintaba el suyo: la zona salía con dos barras
  paralelas separadas por un hueco, que parecía un carácter mal escrito. Se quitó
  la de la celda y se deja solo la del enlace.
- **«Operativo» y «Dado de baja» eran la misma pastilla.** Ahora los estados
  críticos —toda baja, inoperativo, no localizado— llevan **otra forma**: son
  rectángulos con el texto en versalitas, no cápsulas. Se separan por la silueta
  antes de leer una palabra, que es lo único que sigue funcionando cuando la
  columna está a media pantalla.
- **La franja roja de la fila salía a medias.** Se derivaba comparando el texto
  del estado con una lista escrita a mano, y el teclado marcado como «Dado de
  baja» traía otra clave desde la API: la insignia lo pintaba bien y la fila se
  quedaba sin franja. Ahora la franja se saca de `disponibilidadDe`, el mismo
  lugar del que sale el color de la insignia, así que no pueden contradecirse.
  Se comprobó fila por fila en las tres primeras páginas: 139 «Operativo» sin
  franja, 10 «Inoperativo» y 1 «Dado de baja» **con** franja.
- **Los guiones llenaban media tabla.** En las columnas técnicas —RAM, IP, MAC,
  Almacenamiento— un mouse no tiene RAM y una impresora no tiene MAC, así que
  media pantalla era una columna de rayas que competía con los datos de verdad.
  Ahora es `CeldaVacia`: un punto al 40 % de opacidad. Cero guiones viejos, 104
  puntos discretos. El `title` sigue diciendo qué significa cada uno.

De paso se bajó el tono del nombre de la oficina, que iba en el color de marca y
era **el texto más fuerte de la fila, por encima del nombre del equipo**. Con la
jerarquía al revés, lo que identifica el equipo no destacaba.

**Verificado:** sobre el despliegue reconstruido (`web`), en los dos temas.
Encabezado con fondo `rgb(244,247,251)` y borde `rgb(203,213,228)`, 49 px de alto,
títulos de 14 px en versalitas. Las cinco zonas con equipos pintadas una junto a
otra y cada una con su color: COMPLEJO `rgb(124,58,237)`, MERCADO `rgb(22,163,74)`,
PALACIO `rgb(37,99,235)`, PISCINA `rgb(13,148,136)`, SEGURIDAD `rgb(234,88,12)`.
«Operativo» cápsula de 3,4 × 10⁷ px de radio, «DADO DE BAJA» rectángulo de 6 px y
en versalitas. En oscuro: fondo de cabecera `rgb(30,42,59)`, zonas y estados siguen
distinguibles. Recorrido por resumen, tickets, cerrados, equipos, equipo TI, zonas
y oficinas, galería y mis equipos: **sin errores de consola**. En móvil la vista
sigue siendo de tarjetas. `npx tsc -b --noEmit` sin errores, ESLint sin errores,
`verify:clases` en verde, **63 pruebas backend** en verde. Datos intactos: 876
equipos, 20 tickets, 2 usuarios, 6 zonas.

### T1–T4 — Ajustes de jerarquía después de ver el resultado

**Estado: COMPLETADA**

La primera versión de R salió demasiado discreta en tres cosas. Se corrigieron:

- **La columna Equipo vuelve a su aspecto anterior.** Se había puesto el nombre en
  negrita, el tipo en versalita pequeña y el conjunto en un distintivo gris neutro.
  En una tabla de quince filas eso es justo lo que no se ve de un vistazo. Ahora:
  nombre en peso medio, **tipo en negrita** dentro de la línea de detalle, y el
  conjunto otra vez en el color de marca, que es lo que llenaba la columna de
  manchas ámbar y hacía que se reconociera a qué equipo pertenece cada fila.
- **Las mayúsculas vuelven al encabezado.** Ver R1. La discreción se queda para el
  fondo y el aire, no para las letras.
- **La oficina vuelve a resaltar**, en el color de marca y con peso medio. Se había
  bajado a tinta normal con el argumento de que era el texto más fuerte de la
  fila; en la práctica lo que falla es que el nombre del equipo no va en negrita,
  y esa es la fila que manda.
- **El responsable va en peso medio**, para que la columna se lea sin tener que
  descender a la línea de detalle de cada equipo.

**Verificado:** sobre el despliegue reconstruido (`web`). Títulos de columna en
`text-transform: uppercase`; nombre del equipo en peso 500, tipo en 600; oficina en
peso 500 y color de marca `rgb(107,79,0)`; responsable en peso 500. Sin errores de
consola, `tsc` y ESLint sin errores, `verify:clases` en verde.

### U1–U4 — La ficha pide solo lo que corresponde a ese equipo

**Estado: COMPLETADA**

El filtrado por esquema **ya existía** en `FichaEquipo`: los campos visibles salen
de `esperados + opcionales` del tipo. Lo que estaba mal era el contenido del
esquema.

- **La impresora pedía «Tamaño de pantalla».** Su esquema llevaba
  `tamano_pantalla` entre los opcionales, así que la ficha de una impresora
  mostraba un campo para el tamaño de una pantalla que no tiene. Quitado de
  `ESQUEMAS_POR_TIPO` y de la base con la migración `011_esquema_impresora_sin_pantalla`,
  que —a diferencia de la `010`— sí corrige un esquema existente: no es una
  personalización del administrador sino un error, y solo toca la lista de campos.
- **Comprobado tipo por tipo**, no solo la impresora: la CPU no muestra pantalla
  (nunca la tuvo), ni procesador ni RAM una impresora, ni pantalla un teclado o un
  mouse. Monitor y Laptop sí la muestran, porque sí tienen.
- **Aviso de datos repetidos, sin obligar a nada.** En «Disponibilidad de los
  datos» ahora se avisa, campo a campo, cuando el código patrimonial, la IP o la
  MAC ya están en otro equipo: una pastilla «Repetido en 2» junto al nombre del
  campo, la lista de los equipos con enlace a su ficha y un aviso arriba que lo
  resume todo. Es **información, no un bloqueo**: el inventario viene de un Excel
  de años donde muchos equipos no tienen código ni IP, y hay Claim de repuestos
  que comparten propósito. Se lee «No es obligatorio» en el propio aviso.
  Se busca **sobre lo que hay en el formulario**, con 600 ms de retardo, así que
  avisa también mientras se escribe y no solo al guardar —antes el aviso salía
  únicamente después de pulsar «Guardar», cuando ya se había escrito la ficha
  entera—.
- **Diseño.** La cabecera de la ficha mezclaba el color de marca —un ámbar— con la
  franja del color de zona —violeta—, así que salía una cabecera mitad y mitad que
  no significaba nada. Ahora ambos usan el color de la zona y la ficha se lee como
  «este equipo es de COMPLEJO» de un vistazo. Los encabezados de panel llevan
  fondo suave para separar el título del contenido, con el mismo criterio que la
  cabecera de las tablas.

**Verificado:** sobre el despliegue reconstruido (`api` y `web`). Ficha de una
impresora: 9 campos, ninguno de CPU y ninguno de pantalla. Ficha de una CPU: 12
campos, sin pantalla. Con una IP repetida de verdad (`192.168.3.80`, dos CPU):
«Repetido en 1 · También en DESKTOP-LE9RKNN. No es obligatorio». Al escribir una
IP que está en tres equipos: «Repetido en 3» con los tres nombres. Al escribir una
libre: el aviso desaparece. Cabecera de la CPU de PISCINA teñida de turquesa y de
la impresora de COMPLEJO de violeta, cada una con su franja. **63 pruebas backend**
en verde, incluida la que ahora fija que la impresora no lleva pantalla ni
procesador. `tsc` y ESLint sin errores, `verify:clases` en verde. Datos intactos:
876 equipos, 20 tickets, 2 usuarios, 6 zonas, 11 migraciones.

### V1–V3 — El enlace de tickets y dónde va la zona

**Estado: COMPLETADA**

- **«Ver los tickets de este equipo» no decía nada y a veces no llevaba a
  ninguna parte.** El filtro sí existía —el backend acepta `activo_id` y la
  bandeja lo lee—, pero tenía dos fallos. El primero es que no decía cuántos son.
  El segundo es peor: contaba **todos** los tickets y enlazaba a la bandeja de
  **abiertos**. Un equipo cuyo único ticket ya está cerrado prometía «1 ticket» y
  al seguir el enlace se veía una lista vacía: eso es justo lo que hace que un
  enlace parezca roto.
  Ahora se cuentan por separado los abiertos y los cerrados, y **cada número
  lleva a la lista donde ese número es cierto**: los abiertos a la bandeja, los
  cerrados al historial. El enlace de cerrados necesita además `?vista=cerrados`,
  porque esa página abre en la pestaña «Casos críticos» y, sin ese parámetro, un
  ticket cerrado que no es crítico tampoco salía.
- **Cuando no hay tickets, se dice y se explica** que es lo normal, sin ofrecer un
  enlace a «abrir un ticket»: el alta manual admite solo escribir un texto, no
  elegir un equipo del inventario, así que el enlace llevaría a un formulario en
  blanco y sería otra promesa que no se cumple.
- **La zona estaba suelta en una casilla de la retícula**, debajo del tipo de
  equipo y al lado del responsable, dejando un hueco que desalineaba la fila. Va
  ahora debajo de su propio selector, con la etiqueta «Zona:», que es de donde se
  deduce: acompaña a la oficina.

**Verificado:** sobre el despliegue reconstruido (`web`). Con la impresora que
tiene un ticket cerrado: «No tiene tickets abiertos.» y «1 ticket en el historial
cerrado»; al seguirlo, una fila —`TKT-2026-000077`— y la petición
`?estado=resuelto&estado=cerrado&activo_id=…`. Con la impresora que no tiene
ninguno: el texto explicativo, sin enlace. La zona queda dentro de la casilla de
«Oficina y zona» y por debajo del selector. Sin errores de consola, `tsc` y ESLint
sin errores, `verify:clases` en verde.

### W1–W3 — El desplegable de oficinas, agrupado por zona

**Estado: COMPLETADA**

- **No se veía dónde acababa la oficina y empezaba la zona.** El desplegable eran
  59 líneas de «OFICINA · ZONA», las dos en mayúsculas y con el mismo punto de
  separación: un muro de nombres largos donde no había por dónde agarrarse.
- **Ahora va agrupado por zona**, con `<optgroup>`: la zona es un encabezado y
  debajo solo los nombres de oficina, que es lo que se busca al elegir. El
  encabezado lleva el color de la zona —el mismo que la pastilla del resto de la
  aplicación—, así que el grupo se reconoce antes de leer. Para eso `Select` acepta
  ahora `grupos`; los selectores que no los usan no cambian.
  Quedan cinco grupos con su color: PALACIO `rgb(37,99,235)` con 27 oficinas,
  COMPLEJO `rgb(124,58,237)` con 12, MERCADO `rgb(22,163,74)` con 11,
  SEGURIDAD CIUDADANA `rgb(234,88,12)` con 5 y PISCINA MUNICIPAL `rgb(13,148,136)`
  con 4. Suman las 59.
- **La pastilla de zona sigue a la oficina elegida**, no a la que está guardada.
  Antes, al cambiar a una oficina de otra zona, la pastilla seguía diciendo la
  zona antigua mientras el selector decía otra cosa: dos verdades distintas en la
  misma fila. Comprobado: eligiendo ALMACEN, que es de PALACIO, la pastilla pasa
  a PALACIO sin guardar nada.

**Verificado:** sobre el despliegue reconstruido (`web`). Cinco grupos con su
color, 59 oficinas en total, valor seleccionado «ASISTENCIA SOCIAL» —sin el
sufijo `· COMPLEJO`, que ahora es la pastilla de al lado—. Al cambiar de oficina el
valor se actualiza y la zona acompaña. Sin errores de consola, `tsc` y ESLint sin
errores, `verify:clases` en verde, **63 pruebas backend** en verde.

### X1–X6 — Las seis zonas marcadas: explicadas y arregladas

**Estado: COMPLETADA**

Sobre la captura de la bandeja:

- **X1. «Estado y prioridad»:** son dos cosas en la misma casilla. El **estado**
  dice en qué situación está el caso —nuevo, asignado, en progreso, en espera,
  atendido, cerrado— y la **prioridad** cuánta urgencia tiene. Ahora la cabecera
  lo dice al pasar el ratón y cada pastilla se explica sola.
  Y se cambió el nombre: **«Resuelto» pasa a decir «Atendido»**. El motivo es el que
  se señaló: «Resuelto» y «Cerrado» son dos finales casi iguales y no queda claro si
  un ticket cerrado está «resuelto» o no —la respuesta es que las dos cosas—.
  «Atendido» dice lo que quiere decir, que hubo una solución, sin parecer un
  final. **La clave interna sigue siendo `resuelto`**: los 20 tickets guardados la
  usan y los estados de la base no se renombran.
- **X2. «Exportaciones (8) no sirve»:** era un bug real. El botón «Descargar» era
  un `<a href>` a la ruta de la API, y la API autentica con la cabecera
  `Authorization`, que un enlace normal no manda: la petición salía sin token y
  recibía un **401**. El botón se pulsaba y no bajaba nada, sin ningún aviso. Ahora
  la descarga pasa por el cliente de la API —con token—, con estado de
  «Descargando…» y un aviso si algo falla. Arreglado en los tres sitios donde
  pasaba: Reportes, Cerrados y la plantilla del importador.
- **X3. «Responsable del Excel»:** el rótulo «Solo los que no tienen cuenta» se
  podía leer como «las cuentas que no tienen cuenta». Ahora dice «El responsable no
  tiene cuenta» y el texto de debajo explica qué filtra, para qué sirve —localizar
  a quién hay que crearle un acceso— y que los equipos de «Uso común» no entran.
- **X4. Resalte de la fila:** el tinte era del 50 % y no se veía de qué fila era.
  Ahora la fila se apaga del resto al pasar por encima, aparece una franja de color
  en el canto izquierdo y al pulsar se hunde un poco más, para que el clic se
  sienta como un clic. **La franja de urgencia tiene prioridad**: una fila ya
  marcada por SLA o estado crítico no cambia de franja al pasar el ratón.
- **X5. «Carga del equipo»:** el «163 %» no decía de qué era ese 100. La cifra
  ahora se llama «de capacidad», lleva el desglose al pasar el ratón y, cuando está
  sobrecargado, aparece la frase con los números: «Tiene 5 tickets más de los que
  puede resolver en un día. Reparta o póngalo en espera».
- **X6. Los medidores de SLA:** «Transcurrido 100 %» no dice de qué. El rótulo pasa
  a «del tiempo permitido, ya usado»: es el gastado, que es lo que la barra dibuja;
  lo que queda ya estaba en la línea de arriba («Vencido hace 24 h»).

**Verificado:** sobre el despliegue reconstruido (`web`). La descarga se probó de
verdad: `tickets-20261009-073525.xlsx`, 6.319 bytes en disco. En el historial salen
«Atendido» y «Cerrado», sin «Resuelto» en ninguna parte. La fila pasa de fondo
transparente a teñido al pasar el ratón. El SLA se lee «del tiempo permitido, ya
usado 100 %». En la carga del equipo: «15 asignados, 1 en espera, 188 % de
capacidad», con la frase «Tiene 7 tickets más de los que puede resolver en un
día». Sin errores de consola, `tsc` y ESLint sin errores, `verify:clases` en
verde, **63 pruebas backend** en verde.

### Y1–Y4 — Un solo estado final: «cerrado»

**Estado: COMPLETADA**

«Cerrado» y «Resuelto» no cumplían funciones distintas: los dos decían «el
problema está solucionado», los dos eran finales y los dos se podían reabrir.
Eran dos nombres para lo mismo y dos pasos donde bastaba uno. En la cola real
«resuelto» se quedaba semanas sin que nadie lo cerrara, que es justo lo que hace
inútil un estado que nadie usa. **Se retira «resuelto».**

- **Quedan cinco estados**: cuatro abiertos —nuevo, asignado, en progreso y en
  espera— y **uno final, «cerrado»**. Cerrado no significa «no se vuelve a tocar»:
  se puede reabrir, igual que antes, para cuando la solución no sirva. La
  descripción de la insignia lo dice: «El problema está solucionado y el caso
  archivado; se puede reabrir si vuelve a fallar».
- **Cerrar es un paso, no dos.** El backend pasaba por dentro de «resuelto» para
  validar la nota y avisar a quien reportó; ahora hace las dos cosas y pasa
  directamente a «cerrado». En la interfaz queda un botón y una nota.
- **Las dos fechas se siguen escribiendo.** `resuelto_en` —cuándo se resolvió— y
  `cerrado_en` —cuándo se archivó— no son el estado, son marcas de tiempo, y de
  ellas salen los tiempos de resolución, el cumplimiento de SLA, las valoraciones y
  las estadísticas. Quitar el estado no toca ninguna de esas medidas.
- **Los tickets ya guardados se trayeron.** La migración
  `012_un_solo_estado_final` pasa los que estaban en «resuelto» a «cerrado»,
  rellena `cerrado_en` con `resuelto_en` —o con `reabierto_en` en los que volvieron
  a la cola— y actualiza las vistas guardadas que filtraban por el estado
  retirado, que si no se habrían quedado vacías sin avisar.

**Verificado:** sobre el despliegue reconstruido (`api` y `web`) y contra los datos
reales. 12 migraciones aplicadas. Los estados que quedan en la base: 12 asignados,
8 cerrados, 1 en progreso, 1 en espera. **Cero tickets en «resuelto»** y cero
cerrados sin fecha. En la ficha de un ticket abierto, el selector ofrece «En
progreso», «Cerrado» y «Asignado»: ni «Resuelto» ni «Atendido» aparecen en ninguna
parte de la pantalla. El diálogo de cierre dice «El ticket queda cerrado y sale de
la cola. Se puede reabrir si el problema vuelve» y exige la nota de solución.
**64 pruebas backend** en verde, incluida una nueva que fija que el estado
retirado no vuelve al catálogo y que la API lo rechaza con 422. `tsc` y ESLint sin
errores, `verify:clases` en verde. Datos intactos: 876 equipos, 22 tickets, 2
usuarios, 6 zonas.

### Z1–Z4 — Exportaciones, tarjetas del resumen y carga del equipo

**Estado: COMPLETADA**

- **Por qué «Exportaciones (8)» parecía no servir.** El botón **ya descargaba bien**
  —comprobado: el archivo llega con 6.319 bytes y es un xlsx válido—, pero no
  hacía lo que el rótulo prometía: solo **abría una lista** de archivos ya
  generados. Quien lo leía como «bajar la lista de esos 8 tickets» pulsaba y no
  pasaba nada. El problema no era que el botón estuviera roto, sino que el nombre
  no decía la verdad. Ahora:
  - El botón pasó primero a «Archivos exportados (8)» y luego, al ver que tampoco se
    entendía, a **«Descargas (8)»**. Un nombre nuevo no arregla un concepto confuso:
    «exportados» describe el pasado, no lo que hace el botón. «Descargas» dice las
    dos cosas sin que haga falta saber nada.
  - El panel se titula **«Archivos que puedes volver a bajar»** y su subtítulo dice,
    sin rodeos, **«No genera nada nuevo: son archivos que ya creaste en Reportes»**.
    Esa frase es la que faltaba y la que contesta la pregunta de golpe.
  - En Reportes el panel se llama igual **«Descargas»**, para que las dos pantallas
    usen el mismo nombre y no haya dos palabras para lo mismo.
  - El panel explica **de dónde sale uno nuevo**: en Reportes se elige rango, zona
    y formato. Es la pregunta que siempre salía después.
  - Hay un botón **«Descargar todos»** que baja los 5 archivos listos, de uno en
    uno con una pausa entre ellos —en paralelo, el navegador pregunta y los
    bloquea todos—.
- **El texto del filtro de responsables, más corto.** Se quedó en lo pedido:
  «Sirve para localizar a quién hay que crearle un acceso. Los equipos de «Uso
  común» no entran». La primera frase sobraba: repetía lo que ya decía el rótulo
  de la casilla.
- **Las tarjetas del Resumen no reaccionaban al ratón, y había un motivo exacto.**
  La tarjeta llevaba `group-hover:shadow-panel` **en sí misma**, y eso nunca puede
  funcionar: `group-hover` solo se aplica a elementos que cuelgan de un ancestro
  marcado `group`, y la tarjeta no colgaba de ninguno. Seis tarjetas iguales sin
  ninguna señal de dónde estaba el puntero. Ahora la tarjeta se levanta, toma
  borde de color y la etiqueta y el icono cambian de tinta.
- **«Carga del equipo» rediseñada.** Antes eran cuatro bloques para decir una sola
  cosa: tres cifras en cajas, una barra suelta y un párrafo entero debajo. Ahora
  es una fila con la barra, el porcentaje a su derecha y una frase debajo que dice
  qué hacer. La tarjeta entera toma el tono de la carga —borde rojo si está
  sobrecargado, ámbar si se acerca— para que el problema se vea sin leer. Y el
  «14 de 8 del día» aparece junto al nombre, que es la comparación que faltaba.

**Verificado:** sobre el despliegue reconstruido (`web`). «Descargar todos» baja
los 5 archivos (`tickets-20261009-073525.xlsx`, `tickets-20261009-073431.xlsx`,
`tickets-20261008-235240.pdf`, …). El resalte de las tarjetas se midió con el ratón
encima: el borde pasa de `rgb(203,213,228)` a un tinte de marca, la etiqueta de
`rgb(77,91,112)` a `rgb(22,32,51)` y el icono a `rgb(226,178,60)`. «Carga del
equipo» se lee ahora «Puede resolver 8 al día · 14 de 8 del día · 175 % · 6
tickets por encima de lo que puede resolver en un día». Sin errores de consola,
`tsc` y ESLint sin errores, `verify:clases` en verde.

### AA1–AA4 — Enlace al ticket en curso, cierre separado y notificaciones

**Estado: COMPLETADA**

- **«Atendiendo TKT-…» ahora es un enlace** al ticket que tiene el técnico
  abierto. Ver «qué está haciendo» y abrir ese caso son el mismo gesto, y quien
  mira la carga del equipo casi siempre lo que quiere es ir a ese ticket. El
  backend ya mandaba el `ticket_actual_id`; solo faltaba usarlo.
- **Cerrar sale del desplegable de estados.** El modelo propuesto era el correcto
  y así quedó:
  - El desplegable se llama **«Mover en el flujo»** y ofrece solo los pasos del
    trabajo: *Elegir paso siguiente · En progreso · Asignado*. **«Cerrado» ya no
    aparece**, aunque el backend lo permita, porque no es un paso más del flujo.
  - El cierre vive aparte, en un bloque con su propio rótulo —«Terminar el
    caso»— que explica qué pasa: *«Al cerrar hay que escribir qué se hizo. La
    persona que lo reportó lo lee, y el caso sale de la cola.»* Después, el botón
    «Cerrar ticket» abre su diálogo con la nota de solución.
  - El botón pasa de «destructivo» rojo a primario: cerrar un caso es un trabajo
    terminado, no un error.
  - Se quitó la duplicación: antes el desplegable pedía la nota de solución y el
    botón la pedía otra vez, en dos sitios distintos.
- **Las insignias de cabecera, ordenadas.** Antes iban sueltas y pegadas, cada una
  con su altura: dos cápsulas, un reloj con su línea de tiempo debajo y un texto
  suelto al final, todo en la misma línea. Se leía como una frase rota. Ahora hay
  cuatro bloques separados por una filete, cada uno con su etiqueta encima —
  **ESTADO · PRIORIDAD · TIEMPO ACORDADO · ORIGEN**— y su valor debajo, para
  recorrerlos de izquierda a derecha sin adivinar a qué corresponde cada trozo.
- **Las notificaciones no notificaban, y la causa era de fondo.** La campana
  consultaba cada 30 s correctamente; el problema es que **no se creaba ningún
  aviso para el administrador**. En la base había 9 notificaciones, las 9 para
  Maicol, la persona que reportaba, y ninguna para el técnico. Las dos causas:
  - Al **crear** un ticket solo se publicaba un evento por websocket, sin dejar
    rastro en ninguna bandeja: si nadie estaba mirando la lista en ese momento,
    el aviso se perdía.
  - Al **asignar** sí se notificaba, pero solo si el técnico era distinto de quien
    asigna. Con un único administrador que crea y atiende todo, nunca había nadie
    a quien avisar: era él mismo.
  Ahora, al crear un ticket se avisa al técnico asignado y, si no hay, a los
  técnicos y administradores activos para que alguien lo recoja. A quien lo
  reporta se le excluye: ya sabe que lo ha creado. Y en el alta manual se avisa
  al técnico al que se le asigne.

**Verificado:** sobre el despliegue reconstruido (`api` y `web`). El enlace del
ticket en curso apunta a `/panel/tickets/6ac88e9e…`. El desplegable se titula
«Mover en el flujo» y sus opciones son *Elegir paso siguiente · En progreso ·
Asignado*: «Cerrado» no aparece, y el botón «Cerrar ticket» está aparte. La
cabecera muestra los cuatro bloques rotulados. Las notificaciones se comprueban
con una prueba que crea un ticket desde el portal y verifica que llega a la campana
del técnico con su código, y que **no** se envía a quien lo reportó. **65 pruebas
backend** en verde, `tsc` y ESLint sin errores, `verify:clases` en verde.

### AB1–AB4 — «Asignado» desaparece y el enlace roto del panel

**Estado: COMPLETADA**

- **El enlace «Atendiendo TKT-…» daba un 404.** La causa era real y no era del
  enlace: **TKT-2026-000091 estaba borrado** (`eliminado: true`) y el panel de carga
  del equipo lo leía como si siguiera vivo. El borrado es lógico, y esa consulta no
  filtraba los eliminados. Pasaban tres cosas a la vez: el técnico aparecía
  «Ocupado» por un caso que ya no existe, su carga iba inflada y el enlace llevaba a
  un ticket borrado. Ahora los borrados no cuentan para nada de eso, y el «caso en
  curso» es el más movido recientemente en lugar del primero que devuelva Mongo.
  Comprobado pulsando el enlace: TKT-2026-000091 ya no aparece; el que sale abre
  su ficha sin error.
- **«Asignado» y «En progreso» eran la misma cosa, y los datos lo decían.** La
  pregunta era si de verdad hacían lo mismo. Los datos contestaron que sí, y de
  forma bastante tajante: **13 tickets estaban parados en «asignado» y ni uno solo
  había llegado a «en progreso»**. El estado no describía nada; era el sitio donde
  los casos se quedaban. Tres razones por las que no se notaba:
  - Asignar un técnico dejaba el ticket en «asignado», y pasarlo a «en progreso»
    exigía un **segundo clic** en otro control. Ese segundo clic no lo daba nadie.
  - El único contador que medía la diferencia —los pendientes sin responder— **no
    se mostraba en ninguna pantalla**.
  - En los informes, «asignado» y «en progreso» se contaban igual.
  Así que **quitar el estado**: asignar un técnico pone el caso «en progreso» en el
  mismo paso. Quedan cuatro estados, que se leen de un vistazo:

  | Estado | Qué quiere decir |
  |---|---|
  | **Nuevo** | se acaba de reportar y nadie lo ha tomado |
  | **En progreso** | hay un técnico con el caso |
  | **En espera** | está parado, esperando un repuesto o una respuesta |
  | **Cerrado** | terminado, con su solución escrita |

  El desplegable «Mover en el flujo» queda en *Elegir paso siguiente · En espera ·
  Nuevo*: ni «Cerrado» ni «Asignado». Volver a la cola sin técnico se hace con
  «Nuevo», que es lo que significa.
- **Cambios en el modelo y en las pantallas**: `ESTADOS_TICKET`, `TRANSICIONES` y
  el esquema de la colección; el alta manual y la asignación; el resumen de la
  bandeja; la analítica; el PDF del ticket; y en la web, la ficha, los filtros y el
  progreso del portal del ciudadano, que pasa de cuatro pasos —*Recibido, Asignado,
  Revisando, Listo*— a tres —*Recibido, En revisión, Listo*—. Al ciudadano «le
  asignaron» y «lo están revisando» le suenan igual: por dentro es un solo paso.
- **Migración `013_asignar_es_trabajar`**: los tickets que estaban en «asignado»
  pasan a «en progreso», que es donde estaban de hecho. Si alguno no tuviera
  técnico vuelve a «nuevo», porque «en progreso» mentiría. También recoge las
  vistas guardadas que filtraban por el estado retirado, que se habrían quedado
  vacías sin avisar.

**Verificado:** 67 pruebas backend en verde —dos nuevas: una que exige que asignar
deje el caso en «en progreso» y que el estado retirado no se pueda pedir por la
API, y otra que comprueba que un ticket borrado no carga trabajo, no marca al
técnico como ocupado y no ofrece su enlace—. Migración aplicada sobre el despliegue
(`13 migraciones`): ya no queda ningún ticket en «asignado», 15 en «en progreso`. La
carga del administrador bajó de 6 a 5, que era el borrado que se estaba contando.
En el navegador: el enlace abre la ficha sin error, el desplegable ofrece *En espera*
y *Nuevo*, y no aparece ni «Cerrado» ni «Asignado». `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola.

### AC1–AC2 — La franja de la bandeja y los tickets sin zona

**Estado: COMPLETADA**

- **El título mentía.** Decía «Abiertos» *siempre*: salía de la vista inicial, que
  no cambia al pulsar un botón. Al abrir «Críticos» o «Sin asignar» ponía
  «Abiertos» encima de una tabla que no era esa. Ahora el encabezado sigue a la
  vista activa. Comprobado en las cuatro: abiertos, sin asignar, críticos y
  cerrados, el título coincide con la pestaña marcada.
- **Las pastillas se veían apiñadas porque medían menos que todo lo demás:** 34 px
  frente a los 40 px de los botones de «Filtros», «Limpiar» y del campo de
  búsqueda. Dos alturas distintas en la misma franja se leen como una fila torcida,
  aunque el hueco estuviera bien. Ahora las cinco vistas miden 40 px, como el resto
  de controles, el espacio entre ellas pasa de 6 a 8 px y se abre un poco más el
  aire antes de la fila y antes de la leyenda. La separación entre bloques ya era
  correcta —16 px en todos— y no se tocó.

**Consulta sobre los tickets sin zona ni oficina, y lo que se comprobó:**

| Pregunta | Respuesta, comprobada en el código y con datos reales |
|---|---|
| ¿Desaparecen de la base? | **No.** Se guardan enteros; el borrado es la única vía para que dejen de estar. |
| ¿Se omiten en el informe? | **No.** Salen en el CSV, en el Excel y en el PDF, en el mismo formato que los demás. |
| ¿Bajo otro formato? | **No.** Mismas columnas y mismo formato; lo único que cambia es que las columnas de zona y oficina **decían qué les falta**. |

Cómo funciona: la zona y la oficina llegan solas del usuario registrado. Cuando quien
reporta no está en el sistema, el caso se registra con su nombre, teléfono y anexo
en `solicitante_no_registrado`, y con la zona y la oficina en blanco. En la base
real hay **10 casos vivos sin zona ni oficina, los 10 presentes en el informe**.

Dos huecos reales que salió al mirar:

- **En la lista de tickets nunca se exige zona ni oficina**, así que estos casos no
  se esconden en ninguna vista. Se comprobó en el código del listado.
- **Los rankings por zona y por oficina tampoco se filtran.** En el archivo exportado no: la celda salía vacía. En una hoja de cálculo una celda
  vacía no distingue «no tiene zona» de «se borró el dato», y encima no se puede
  filtrar por ella. Ahora el CSV, el Excel y el PDF escriben **«Sin zona»** y **«Sin
  oficina»**, igual que el ranking. En el despliegue real, las diez filas salen con
  esos dos textos.

**Verificado:** 68 pruebas backend en verde. La nueva crea un caso con una persona
no registrada, comprueba que guarda su nombre, que sale en el informe y que las
columnas vacías dicen qué les falta. En el navegador: el título coincide con la
pestaña activa en las cuatro vistas, y las pastillas miden 40 px como el resto de
los controles. `tsc` y ESLint sin errores, `verify:clases` en verde, sin errores de
consola.

### AD1–AD2 — Vistas recortadas en Cerrados y pastillas más pequeñas

**Estado: COMPLETADA**

- **En «Historial y casos críticos» solo se ofrecen las dos vistas de esa página.**
  Tenían razón: la fila completa era una segunda navegación encima de una pantalla
  que ya trae sus propias pestañas. Ofrecía **«Abiertos», «Sin asignar» y «SLA en
  riesgo»**, que son atajos de la cola abierta: botones que te sacan de la página en
  la que estás. Ahora esa fila es **«Críticos · Cerrados»**, y las dos pestañas de
  arriba siguen igual. La bandeja general conserva las cinco: allí sí son un atajo
  útil. `Bandeja` acepta ahora un prop `vistas` con las claves que esa pantalla
  ofrece; si la URL trae una vista que no está en esa lista, se cae en la inicial de
  la página en vez de dejar la fila coja. Comprobado con
  `?vista=sin_asignar`: no rompe nada y muestra el historial.
- **Las pastillas bajan a 36 px.** Se habían puesto a 40 px para igualarlas con los
  botones de «Filtros» y «Limpiar», y el resultado fue una fila que pesaba más que la
  tabla de abajo: son navegación, no acciones. Ahora miden 36 px, con `px-3.5` y el
  texto en peso medio salvo la activa, que lo mantiene en negrita. Se distinguen por
  el borde y el relleno, no por el tamaño.

**Verificado:** sobre el despliegue reconstruido. La bandeja general sigue con las
cinco vistas; en «Historial y casos críticos» aparecen solo *Críticos · Cerrados* y
la activa cambia bien al pulsar cada pestaña. La pastilla mide 36 px en las dos
pantallas. `tsc` y ESLint sin errores, `verify:clases` en verde, sin errores de
consola.

### AE1–AE4 — Tipo de equipo, texto del SLA, plazo de 2 días y el error de «SLA en riesgo»

**Estado: COMPLETADA**

- **El error de «SLA en riesgo» era mío, de la ronda anterior.** Al tocar el clic de
  las vistas escribí la condición al revés: comprobaba si la vista traía `vista` o
  `estado` en sus filtros, y «SLA en riesgo» no trae ninguna de las dos —filtra por
  `sla`—, así que se quedaba sin filtro y saltaba a «Abiertos». Ahora se decide por
  la clave, que es lo único fiable. **Comprobado una por una**: *Abiertos* → sin
  filtro; *Sin asignar*, *SLA en riesgo*, *Críticos* y *Cerrados* → cada una a su
  URL y con su pestaña activa.
- **La columna «Equipo» decía lo mismo dos veces.** Arriba el nombre, abajo el
  conjunto al que pertenece. En el inventario importado el conjunto es el prefijo
  del nombre —«Computadora N°01 - CPU» dentro de «Computadora N°01»— así que la
  segunda línea repetía lo de arriba; y como la columna es estrecha, **el «- CPU» era
  justo lo que se cutraba**, que es lo que hacía imposible saber si lo que se veía
  era una CPU o una impresora. Ahora:
  - arriba el nombre sin el sufijo redundante —«Computadora N°01»—,
  - debajo **el tipo** —«CPU»—,
  - y el conjunto solo cuando no es el prefijo del nombre, porque entonces sí
    aporta algo.
  Para poder hacerlo, el ticket guarda ahora `activo_tipo`: es un dato que ya
  estaba en el inventario, pero en otra colección, y pedirlo por fila sería una
  consulta por fila. **Migración `015`**, que solo rellena ese campo en los tickets
  que ya existían y no toca nombre ni conjunto ni nada del equipo.
- **El texto del SLA ya cabe.** Decía «69 h 32 min restantes» y «116 h 5 min
  restantes»: cuatro cifras y media palabra, y se cortaba. Ahora cuenta en la unidad
  más grande que quepa —**«Quedan 2 días y 17 h»**, «Quedan 3 h», «Vencido hace 1
  día»— porque un plazo se habla en días, no en horas de reloj. El rótulo de la
  barra («Parte del tiempo permitido ya usada») pasa al título emergente: escrito
  encima se comía media celda. Queda **«18 % del plazo»** y la barra.
- **El plazo máximo del SLA son 2 días.** Antes, la prioridad «baja» daba **72 horas
  laborables: nueve días**, así que un ticket sin prisa podía pasar más de una
  semana y media sin que nadie lo tocara sin que el sistema marcara nada —el
  contador compara el retraso contra ese mismo plazo, y el plazo lo consentía—. Y
  como las horas son laborables, al traducirlas a tiempo de calendario salían
  números imposibles de leer. La escalera nueva, con la jornada de 8 horas:

  | Prioridad | Responder | Resolver | Días laborables |
  |---|---|---|---|
  | crítica | 1 h | 2 h | ¼ |
  | alta | 2 h | 4 h | ½ |
  | media | 4 h | 8 h | 1 |
  | baja | 8 h | **16 h** | **2** |

  **Migración `014`**: cambia las reglas guardadas y recalcula el plazo de los
  tickets **abiertos**. Los ya cerrados conservan el plazo con el que se resolvieron,
  porque su plazo se fijó cuando se creó y reescribirlo sería falsear lo ocurrido.
  Los plazos siguen siendo configurables desde Configuración.

**Verificado:** 68 pruebas backend en verde. En el despliegue: las cinco vistas van
a su sitio; la columna muestra *Computadora N°01* sobre *CPU*; el SLA dice *Quedan 2
días y 17 h · 18 % del plazo*; y en la base, la regla de «baja» queda en 16 h. Los
tickets ya cerrados mantienen su fecha original. `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola.

### AF1–AF2 — Las insignias se partían por la mitad

**Estado: COMPLETADA**

- **La causa estaba medida, no supuesta.** Las celdas de datos llevan
  `truncate whitespace-nowrap`, y eso corta con `overflow: hidden`. Funciona con
  texto, que es de lo que se esperaba: sale con puntos suspensivos. Pero una
  **insignia no puede encogerse** —es un `inline-flex` con su propio relleno— y
  como la columna se estrecha por debajo de su contenido, la pastilla se partía a
  media palabra, con el borde redondeado cortado por el lado derecho. La celda de
  «Afectado» tenía lo mismo dentro con las insignias de zona y de oficina.
- **`DataTable` acepta `meta.celdaLibre`**: la celda sale del recorte automático y
  lo que no cabe pasa a la línea siguiente. Se declara en el módulo de TanStack
  para que `columnDef.meta` lo reconozca, en vez de andar con conversiones.
- **Estado y prioridad** la piden, y las dos insignias ahora van **apiladas**: una
  debajo de otra. Antes iban en línea y solo se apilaban cuando la columna ya era
  estrecha, así que el ancho de la columna cambiaba según el ancho de la ventana.
  Con la pila fija la columna mide lo mismo siempre.
- **Afectado** también la pide: el nombre largo sí se recorta con puntos
  suspensivos —que es lo único que funciona con texto—, y las insignias de zona
  y de oficina se leen enteras.

**Lo que sigue igual, y conviene decir:** la tabla necesita 912 px y por debajo de
1280 de ancho el hueco es menor, así que **la última columna se ve cortada por el
borde del contenedor** y hay que desplazar en horizontal. Eso es inherent a una
tabla de siete columnas con el menú lateral abierto, y la barra fija del pie está
para eso. Lo que ya no pasa es que una columna se parta **por dentro**, que es lo
que parecía un error.

**Verificado:** en el despliegue, la columna «Estado y prioridad» muestra *Cerrado*
sobre *Media* y *Cerrado* sobre *Baja*, completas; «Afectado» muestra *Maicol*,
*Sin oficina* y la insignia *Sin zona* entera. Barrido de anchos de 1440 a 1024:
**ninguna celda queda cortada por dentro** en ninguno. `tsc` y ESLint sin errores,
`verify:clases` en verde.

### AG1 — El recorte se arregla en la tabla, no columna por columna

**Estado: COMPLETADA**

Puesto que el recorte de la celda era el problema de fondo, se corrige **en
`DataTable`**, que usan Bandeja, Equipos, Usuarios, Auditoría y Galería. Todas
quedan cubiertas de una vez y no solo las detectadas a ojo.

- **El recorte baja del `<td>` a un envoltorio.** Antes `truncate whitespace-nowrap`
  iba en la celda, y `truncate` corta con `overflow: hidden`: correcto para texto,
  que sale con puntos suspensivos, y **`overflow: hidden` no distingue entre texto y
  otra cosa**. Una insignia es un `inline-flex` con relleno y borde; no puede
  encogerse por debajo de su contenido, así que se partía a media palabra con el
  borde redondeado cortado. Puesto en un envoltorio, cada celda recorta su propio
  contenido y **una columna con `meta.celdaLibre` no recorta nada**, dejando que lo
  que no cabe baje a la línea siguiente.
- **Marcadas las columnas con insignias**, en todas las pantallas:
  - Bandeja: «Afectado» y «Estado y prioridad».
  - Equipos: «Ubicación», «Estado» y «Datos».
  - Usuarios: «Ubicación» y «Estado».
- **Lo que no cambia:** los textos largos **siguen recortándose con puntos
  suspensivos**, dentro de la celda. Comprobado en Equipos con nombres largos:
  «THALIA CABALLERO CHINCHAY» sale con puntos y `text-overflow: ellipsis`.

**Verificado con un escaneo automático, no a ojo:** se recorren **ocho pantallas** —
bandeja con sus cuatro vistas, cerrados, equipos, usuarios, organización, equipo TI
y auditoría— a **seis anchos** de 1600 a 1024, buscando en cada una cualquier
elemento que se salga de su ancestro con `overflow: hidden` y tenga forma propia.
Resultado: **0 recortes**. En Equipos y Usuarios se ve además que los nombres largos
conservan sus puntos suspensivos y que las insignias —«COMPLEJO», «Operativo»,
«Sin zona», «Activo»— se leen enteras. `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola.

### AH1 — Zona y oficina con la misma forma en todas las vistas

**Estado: COMPLETADA**

Las dos capturas eran de «Abiertos» y «Sin asignar», y la celda se veía distinta de
como se veía en «Cerrados». Medido, no supuesto: en «Abiertos» la columna de estado
es más ancha —«En progreso» ocupa 103 px frente a los 79 de «Cerrado»—, la de
afectado crecía con ella, y la pastilla «Sin zona» **saltaba a una tercera línea**.
La misma celda se leía de dos maneras según la vista.

- **Nuevo componente `Ubicacion`**, con estructura fija que no depende del ancho:
  zona arriba, oficina debajo. Se usa en la columna «Afectado» de Bandeja y en
  «Ubicación» de Usuarios, para que las dos se lean igual.
- **«Sin oficina» desaparece cuando no hay zona.** Eran dos formas de decir lo
  mismo —no sabemos dónde está esta persona— y juntas llenaban la celda de avisos.
  Con la zona ya escrita, la oficina solo aparece cuando existe.
- **Sin zona no hay pastilla, hay una línea de texto.** La pastilla con su punto de
  color sirve para distinguir una zona de otra; sin zona no hay color que
  distinguir y quedaba una etiqueta con la misma forma que las de verdad, que hace
  creer que hay un dato donde no lo hay.
- **La raya de color de `EnlaceOficina` solo se pinta cuando hay un color que
  rayar.** Antes el borde se dibujaba siempre y, sin zona, `borderColor` se
  quedaba sin valor: heredaba el color del texto y salía una raya gris junto a «Sin
  oficina». Una raya que no significa nada parece un fallo de pantalla. Con zona
  sigue pintándose con su color —en Equipos, COMPLEJO la muestra violeta—.

**Verificado:** en «Abiertos» y en «Cerrados» la celda es exactamente la misma, dos
líneas —*Maicol* / *Sin zona*—, y la columna bajó de 170 a 134 px en «Abiertos» al
desaparecer el texto y la pastilla de la zona. Con datos de verdad, Equipos sigue
mostrando la oficina con la raya de su zona y la pastilla de COMPLEJO. Escaneo
automático de nueve pantallas a seis anchos: **0 recortes**, sin errores de consola.
`tsc` y ESLint sin errores, `verify:clases` en verde.

### AI1 — La descripción de la ficha

**Estado: COMPLETADA**

- **La descripción es el contenido del panel, no un campo más.** Antes salía como
  un párrafo suelto con la misma pinta que los datos de debajo, y no se distinguía
  de ellos. Ahora va en su propio bloque, con una raya de color a la izquierda como
  una cita y con interlineado más abierto para que un texto largo se lea.
- **Si no hay descripción, se dice.** Antes salía un párrafo vacío; ahora: *«Quien
  reportó el problema no escribió una descripción.»*
- **Los seis datos de abajo se ven iguales.** Antes tres rótulos iban en mayúsculas
  y otros dos no, y zona y oficina se montaban a mano aparte de los demás: se notaba
  que eran campos hechos en momentos distintos. `Campo` ahora acepta un contenido
  propio además de un texto —porque la zona es una pastilla con su color y la
  oficina lleva su raya— y los seis usan la misma etiqueta, el mismo peso y la
  misma separación. Debajo del bloque va una filete que separa la descripción de
  sus metadatos.

**Verificado** sobre el despliegue, con una descripción corta y otra larga: el bloque
con su raya se ve igual en las dos, y los seis rótulos —REPORTÓ, AFECTA A, CATEGORÍA,
ZONA, OFICINA, EQUIPO— salen con la misma forma. `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola.

### AI2 — El recuadro, no lo que escribió la gente

**Estado: COMPLETADA**

Entendido: el encargo era el recuadro, no el texto. Se retira el bloque con fondo y
raya que se había añadido —era un añadido, no lo pedido— y se trabaja el marco.

- **El recuadro de «Descripción» lleva ahora un canto de color de 3 px** en el lado
  izquierdo. Es el texto del caso, lo primero que hay que leer al abrir un ticket, y
  hasta ahora era un recuadro gris más entre los de al lado: el borde lo identifica
  de un vistazo. Se aplica con `className` sobre el `Panel`, que es compartido, así
  que los demás recuadros de la aplicación no cambian.
- **La descripción respira y no se estira.** Interlineado más abierto y ancho de
  lectura acotado —68 caracteres— para que un texto largo se lea en lugar de
  recorrer toda la pantalla.
- **Separación más marcada** entre la descripción y sus metadatos: filete y aire por
  encima y por debajo.
- **Se conserva** lo del punto anterior: si no hay descripción se dice que no la
  hay, y los seis datos de abajo salen con la misma forma —tres rótulos en
  mayúsculas y tres sin ellas, y dos montados a mano aparte, era lo que se veía en
  la captura—.

**Verificado** sobre tres tickets distintos: el recuadro mide lo mismo en los tres y
el canto de color se pinta en los tres. `tsc` y ESLint sin errores, `verify:clases` en
verde, sin errores de consola.

### AJ1–AJ4 — La ficha del ticket, de arriba abajo

**Estado: COMPLETADA**

Revisada la página entera con una captura y medidos los bloques. Salieron cuatro
cosas, tres de ellas no eran diseño:

- **El historial mostraba estados que ya no existen.** Al retirar «asignado» y
  «resuelto», los eventos antiguos se quedaron con su nombre viejo: en pantalla se
  leía «Estado: asignado -> en_espera» y «resuelto -> cerrado», con estados que no
  existen en el catálogo. Ahora **cada estado se muestra con el nombre de hoy** —
  «Estado: en progreso → en espera»— y sin el guion bajo del valor interno, que no
  es lo que se escribe para que lo lea alguien. **El registro guardado no se
  reescribe**: dice exactamente lo que pasó; solo se traduce al mostrar, porque leer
  «asignado» en una pantalla donde no hay estado «asignado» obliga a buscar a qué
  corresponde. También se unifica la flecha: las transiciones viejas usaban «->» y
  las nuevas «→», y en la misma lista eso se lee como que salieron de sitios
  distintos.
- **El historial repetía el nombre del rol.** Con el administrador de la
  municipalidad cada línea decía «Administrador · administrador»: el mismo texto
  dos veces. El rol ahora solo aparece cuando el nombre no empieza por él —«Juan
  Pérez · técnico»— porque ahí sí distingue a una persona de otra.
- **Las sugerencias de la IA mostraban cuatro líneas idénticas.** No era la IA: la
  base de conocimiento tenía **siete copias de cada artículo** —28 documentos para
  4 títulos—, así que la lista de cuatro salía con el mismo título repetido.
  `sugerir_para_ticket` **deduplica por título** y trae más candidatos por si hay
  repetidos. Los 28 documentos **no se tocan**: son datos de la municipalidad y
  borrarlos es cosa suya.
- **El aviso «este ticket no tiene conversación» era lo más llamativo de la página**
  y es lo menos importante: un bloque ancho con el color del tema, en medio de la
  columna. Ahora es una línea discreta con su icono. La página bajó de 1494 a 1444
  px solo con eso.

**Verificado:** 70 pruebas backend en verde. Dos nuevas: una comprueba que el
historial no enseña estados retirados, que los muestra con los nombres de hoy y que
**el documento guardado no cambia**; otra que las sugerencias no repiten título. En
el navegador, el historial dice «Estado: en progreso → en espera», el autor aparece
como «Administrador» a secas y el panel de IA muestra una sola línea de artículos.
`tsc` y ESLint sin errores, `verify:clases` en verde, sin errores de consola.

### AK1–AK2 — La pantalla de registrar ticket

**Estado: COMPLETADA**

Revisada con captura y medidas, como la ficha. Salieron dos cosas, y son las mismas
que se corrigieron allí:

- **El porqué «Por qué no hay chat» era el bloque más llamativo de la pantalla**, y es
  un porqué, no un aviso: nada está mal, es una explicación de por qué este tipo de
  alta no abre conversación. Salía con el color del tema —que en el tema activo es el
  mismo que el de aviso— y ocupaba media columna lateral en una pantalla cuya función
  es que escribas un caso. Va ahora como una línea discreta, **igual que en la
  ficha**, para que las dos pantallas hablen el mismo idioma.
- **«Qué pasa» lleva el mismo canto de color que «Descripción»** en la ficha del
  ticket. Son la misma tarea en las dos pantallas —el texto libre del caso— y ahora
  se reconocen igual a un vistazo.

**Un intento que se deshizo y no quedó:** acotar el ancho de lectura del panel a 68
caracteres, como en la ficha. En un texto que envuelve no hay problema, pero en un
formulario deja una franja vacía a la derecha del recuadro que parece un error de
maquetación. Se quitó; los campos van a lo ancho del panel.

**Verificado** sobre el despliegue: el panel ocupa todo su ancho, la nota es una
línea, el canto de color se pinta, y el formulario sigue sin errores de consola. No
se tocó la lógica: es la misma pantalla con otra forma. `tsc` y ESLint sin errores,
`verify:clases` en verde.

### AL1–AL3 — Lo que encontró mirar las dos pantallas juntas

**Estado: COMPLETADA**

Puestas una al lado de la otra, el mismo criterio se ve en las dos —canto de 3 px en
«Qué pasa» y en «Descripción», misma nota discreta— y queda una cosa que solo se ve
mirando el historial real, no el código.

- **El historial decía «Estado: en progreso → en progreso».** Una transición a sí
  mismo, que no es un cambio: es un error de pantalla. Venía de traducir el evento
  antiguo `en_progreso → asignado`, y como «asignado» pasó a llamarse «en progreso»,
  los dos extremos quedaron igual. **Peor que el estado retirado**: el estado viejo
  al menos era verdad.
- **El arreglo comprueba antes de traducir.** Si el estado de salida y el de entrada
  se llaman igual al traducirlos, **no se traduce**: se deja el nombre de entonces y
  se marca «(estado antiguo)». Así el ticket TKT-2026-000092 dice ahora «Estado: en
  progreso → asignado (estado antiguo)», que es exactamente lo que pasó.
- **El registro guardado sigue intacto.** Como antes: se traduce al mostrar, nunca al
  guardar.

**Verificado:** 70 pruebas backend en verde. La prueba del historial ahora fija los
tres casos a la vez —el que se traduce bien, el que se marca por choque de nombres y
el que no puede pasar— y comprueba además que el documento guardado no cambia. En el
navegador, el historial real de TKT-2026-000092 ya no tiene ninguna línea que diga
que el ticket no cambió de estado. `tsc` y ESLint sin errores, `verify:clases` en
verde, sin errores de consola.

### AM1–AM3 — Las tres vistas de tickets: SLA, columnas y cerrado

**Estado: COMPLETADA**

Medidas las tres vistas —Abiertos, Mis asignaciones e Historial cerrado— a 1440,
1280 y 1100 px. No había ni un recorte ni un desbordado. Salieron tres cosas:

- **El SLA se medía con dos relojes a la vez.** El reparto del plazo salía de
  `sumar_minutos_laborables` —que respeta fines de semana— y el tiempo restante de
  `resolver_en - ahora`, que no. Los tickets TKT-2026-000093/94/95 se crearon el
  sábado y mostraban **«Quedan 2 días y 4 h» con la barra en 0 %**. Ahora las dos
  cifras salen del reloj de trabajo: el plazo máximo sigue siendo **16 h de trabajo**
  (2 días de 8) y queda garantizado que `lo que queda + lo gastado = el plazo`, que
  es lo que impide que el texto y la barra se contradigan. Un caso que vence el
  viernes ya no se muere el sábado.
- **Las columnas cambiaban de proporción entre vistas**, aunque son las mismas y las
  tres usan el mismo componente: la del ticket medía 205 px en Abiertos y 192 en
  Cerrados, la fila pasaba de 96 a 92 px y «Estado y prioridad» se partía en dos
  líneas en una vista y en una en la otra. Cada columna declara su proporción y la
  tabla usa `table-fixed`: **las siete ahora miden lo mismo en las tres vistas y en
  los tres anchos**.
- **En el historial cerrado, «Vencido» en rojo con la barra llena.** El caso está
  cerrado: no está vencido, se cerró tarde, y ahí no hay nada que resolver. Ahora
  sale **«Cerrado a tiempo»** o **«Cerrado con retraso»**, con la línea de debajo
  diciendo cuánto tardó y la barra en gris. **Misma estética**: misma insignia,
  misma línea pequeña, misma barra.

**Un precio que hay que saber:** con ventana de 1280 hay que desplazar la tabla 149 px
a la derecha. Es la consecuencia de que las columnas midan lo mismo en todas las
vistas **y** de que no se recorte nunca el texto. Se midió la otra opción —columnas
que encogen sin límite— y a 1280 «Cerrado con retraso» se cortaba 16 px y a 1100,
47 px, con filas de 112 px unas y 96 otras. Desplazar se prefirió a cortar.

**Verificado:** 74 pruebas backend en verde, **cuatro nuevas** en un archivo propio
que no existía: el invariante de los dos relojes, que el fin de semana no corra el
plazo, que un cerrado no diga «vencido», y un guardarraíl que comprueba que las fechas
de la prueba caen en el día de la semana que dicen. Esa última existe porque el
reparto del plazo depende del día: una prueba con `utcnow()` puede pasar un sábado y
romperse el lunes, y en las pruebas nuevas la zona se le pregunta a la app en vez de
suponerla. En el navegador: SLA coherente («Quedan 6 h 33 min» = 82 % de 8 h, que es
justo el 18 % de la barra), columnas idénticas en las tres vistas a los tres anchos,
filas de 96 px en las tres y cero recortes. `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola.

### AN1–AN3 — El calendario laboral, que era martes a sábado

**Estado: COMPLETADA**

Al preguntar cuánto era el plazo en total salió el problema de fondo: **las 16 h
estaban bien, el calendario contra el que se contaban no**.

- **El lunes no era día laborable.** Los días guardados eran `[1, 2, 3, 4, 5]` y el
  índice es el de `datetime.weekday()`, donde el lunes es 0. Lo que había era
  **martes a sábado**. Dos efectos: las 16 h ocupaban lunes, martes y miércoles en
  vez de dos días, y una prioridad crítica de 2 h abierta el lunes a las 08:00 no
  vencía hasta el **martes a las 18:00** — un día entero de margen que nadie pidió.
- **La tarde estaba corrida una hora.** Los tramos eran 08:00-13:00 y **15:00-18:00**;
  la jornada entra a las 14:00 y sale a las 17:00. Las dos sumaban 8 h, así que el
  día laboral era correcto y **el error no se veía en ninguna cifra**, solo en las
  horas: en qué momento empezaba la tarde.
- **Estaba en cuatro sitios**: `config_service.DEFAULTS`, el esquema de la API, la
  migración 003 y el respaldo de `sla_service`. Que fuera cuatro veces no es un
  detalle: el comentario de la 003 ya decía «lunes a viernes» y el valor al lado era
  martes a sábado, y eso sobrevive porque el comentario miente en la dirección que
  uno espera.

Corregido en los cuatro, y con la **migración 016** para lo que ya estaba guardado.
Los plazos de los casos **abiertos se recalcularon**; los cerrados conservan el suyo,
como en la 014, porque ese plazo se fijó cuando se creó el caso.

**Verificado:** 76 pruebas backend en verde, dos nuevas. Una comprueba **de forma
literal** que el calendario por defecto es lunes a viernes y que la jornada dura 8 h,
escrita en la prueba a propósito: si mañana el valor cambia solo en `DEFAULTS`, la
prueba tiene que avisar en vez de darlo por bueno. La otra comprueba lo que se pidió
al principio —**que 16 h caigan el segundo día laborable**—, que era justo lo que
nadie había escrito y lo que fallaba. En la app real, con tu configuración puesta:
un caso de prioridad baja abierto el lunes 08:00 **vence el martes a las 17:00** —el
día acaba a las 17:00, no a las 18:00— y uno de prioridad media ese mismo lunes vence
**el lunes a las 17:00**. Los cuatro plazos medidos desde el lunes: crítica 2 h → el
lunes, alta 4 h → el lunes, media 8 h → el lunes, baja 16 h → **día 2 de labor**.

**Un detalle que salió al mirar la pantalla:** los casos vencidos mostraban «0 min»
debajo de la insignia. Cero minutos de retraso de verdad —el plazo pasó en fin de
semana y el fin de semana no cuenta—, pero «0 min» es cierto y no significa nada.
Ahora dice **«Plazo agotado»**.

### AO1–AO3 — Los dos plazos del SLA: responder y resolver

**Estado: COMPLETADA**

Pedido: que el medidor sea dinámico. Sin tomar, el de **responder**; en cuanto alguien
coge el caso, el de **resolver**, en el mismo sitio. Y en los casos cerrados, un
apartado con lo que se tardó en cogerlos.

**1. El SLA cambia de plazo según el estado.** `estado_sla` devuelve ahora `modo`
—`responder` mientras el caso está en «nuevo», `resolver` en cuanto lo está— y toda
la cuenta se hace contra ese: el tiempo que queda, el estado y el progreso de la
barra. Comprobado sobre el mismo caso, en los dos estados:

```
nuevo            modo=responder   queda 240 min   (4 h de responder)
en progreso      modo=resolver   queda 480 min   (8 h de resolver)
```

Los dos plazos se devuelven igual en sus propios campos
(`minutos_responder_restantes`, `minutos_resolver_restantes`) para el que necesite el
que no está corriendo. La insignia dice **«Para cogerlo: …»** mientras está sin tomar,
porque si no «Quedan 4 h» no dice si es para cogerlo o para arreglarlo. En la ficha el
rótulo cambia de «Tiempo acordado» a «Tiempo para cogerlo».

**2. Faltaba el dato de «cuándo se cogió», y era el importante.** El plazo de
responder se calculaba y se guardaba, pero **la fecha en que alguien se hizo cargo no
se guardaba al asignar**: solo cuando alguien movía el estado a mano. De los 26
tickets de la base, **6 tenían la fecha y 20 no la tenían**. Es decir, el SLA que
promete «responder en 4 h» no tenía con qué compararse en cuatro casos de cada cinco.
Ahora asignar un caso «nuevo» guarda `primera_lectura_en`, y solo la primera vez, para
que reasignar no la mueva.

**3. El bloque «Cuándo se cogió», en los casos cerrados.** Tres datos: cuánto se tardó
—en **minutos de trabajo**, no de reloj—, si se quedó dentro del plazo y qué día fue.
Para los casos anteriores a que la fecha se guardara, el momento se **reconstruye del
historial** —el primer evento de asignación o de cambio de estado— y la interfaz lo
dice: «Sacado del historial del caso». No es un adorno: avisa de que la cifra sale del
registro y no de un campo del documento. Si no hay nada de eso, se dice que no consta.

**Lo que no se pudo ver en pantalla:** **no hay ningún ticket en estado «Nuevo»**; los
15 abiertos están todos en progreso porque se asignan nada más crearse. La parte de
«nuevo» está comprobada en la prueba y contra la API con el caso copiado y el estado
cambiado en memoria, **sin escribir en la base**. Para verla de verdad hay que dejar un
caso sin asignar.

**Verificado:** 76 pruebas backend en verde. Las dos del SLA ahora cubren **los dos
modos**: el invariante de los dos relojes se comprueba en «nuevo» —y el mismo caso se
comprueba ya en «en progreso» con el otro plazo—, y la del fin de semana cuenta contra
el plazo de responder. `tsc` y ESLint sin errores, `verify:clases` en verde, sin
errores de consola.

### S1 — Una prueba que solo pasaba de lunes a viernes

**Estado: COMPLETADA**

`test_disponibilidad_con_horario_y_ausencias` fallaba y no era culpa de este
trabajo: venía de `HEAD` y fijaba un horario de lunes a viernes. Un técnico con el
sábado libre sale «dia_libre», no «fuera_de_horario», que es lo que pedía la
aserción. Como hoy es sábado, la mitad de las ejecuciones de esa prueba eran un
falso negativo.

El arreglo no es relajar la comprobación sino quitarle la dependencia del día: el
horario de prueba ahora cubre los siete días, y el día libre explícito se marca
sobre **hoy**, sea el que sea. Además se añadió el paso intermedio que faltaba —
comprobar que quitar el día libre devuelve al técnico a disponible o fuera de
horario—, que antes no existía porque en un día laborable la prueba nunca llegaba
hasta ahí.

**Verificado:** 63 pruebas en verde un sábado.

**Aviso sobre la vista guardada que había:** durante la verificación del bloque
M1–M4, un script de comprobación borró por error la vista «sin asignar esta
semana». Se recreó con el mismo nombre, la misma vista rápida, los mismos filtros
(`solo_abiertos`) y las mismas 7 columnas, con la diferencia de que ahora registra
además `vista: 'abiertos'`. **Después la persona usuaria la eliminó ella misma**
desde `/panel/mis-asignaciones` (registro `DELETE /api/vistas-guardadas/6ac8e7ec…`
en el log del servidor), así que a día de hoy no hay ninguna vista guardada. Los
scripts de comprobación ya solo leen: no crean ni borran nada en la municipalidad.
Cuando quieras volver a tener una, guárdala estando sobre la pestaña que quieras —
a partir de ahora sí guarda esa vista y las columnas con las que la estás
mirando— y aparecerá marcada en el color de la institución mientras siga
filtrando.
### AP1–AP4 — El equipo del ticket: de la lista, o solo el tipo

**Estado: COMPLETADA**

Al registrar un caso, escribir el nombre del equipo en un cuadro de texto enganchaba
un equipo **del edificio entero**. Medido en los datos:

* «CPU» coincide con **6 equipos de 5 zonas**; el sistema se quedaba con uno de
  PALACIO sin preguntar;
* «COMPUTADORA N°01 - TECLADO» aparece **52 veces** en cinco zonas;
* solo el código patrimonial identifica uno —461 de 876 lo tienen, **ninguno
  repetido**—, así que ni con el nombre exacto se sabe cuál es.

No era un equipo equivocado: era **un enlace a una máquina ajena**, con su zona, su
conjunto y su historial de fallos.

- **El equipo se elige de una lista.** El panel ofrece los equipos de la persona
  afectada, cada uno con su zona al lado, mediante el componente nuevo
  `SelectorEquipo`. Si no tiene ninguno, lo dice con palabras —*«Maicol no tiene
  equipos registrados a su nombre»*— y se puede registrar el caso igual: que falten
  equipos en el inventario no es motivo para no registrar nada.
- **El texto libre ya no decide nada.** Los dos caminos que lo hacían —el alta manual
  y el del portal— dejaron de buscar por texto. También se quitó el «coge el primer
  equipo de la persona», que era lo mismo por otro lado.
- **El tipo se guarda sin equipo.** Se anota «Es un CPU» con un desplegable de los 16
  tipos. Es información verdadera y sirve para el triage, a diferencia del enlace
  inventado. Nueva propiedad `activo_tipo` en el alta manual.
- **Endpoint nuevo** `GET /equipos/de-persona/{id}` para ver los equipos de otra
  persona, con permiso `equipos.ver`. El portal tenía el suyo pero solo servía para
  quien pregunta.

**Corrección de algo que dije antes:** afirmé que Maicol no tenía equipos a su cargo.
**Es falso**: tiene uno, `Mause17` (Mouse), en PALACIO, en el conjunto «Computadora
N°2». Se vio al montar el selector, que la devolvió en la lista. Lo que sí es cierto
es que **ni ella ni el administrador tienen zona ni oficina en su ficha**, y por eso
sus tickets salen «Sin zona» aunque su equipo esté en PALACIO.

Y de ahí sale lo que hace el fallo más grande de lo que parecía.

**Verificado:** 78 pruebas backend en verde, **dos nuevas**. Una comprueba que un tipo
no enlaza ningún equipo y que el texto libre tampoco, con dos equipos en la base cuyo
nombre contiene lo mismo — que es lo que hace que el texto no pueda decidir. La otra
comprueba el camino bueno: elegido de la lista, ese equipo queda enlazado con su
nombre y su tipo, porque quitar el enlace sin comprobar que lo bueno sigue
funcionando sería arreglar el fallo borrando la función. `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola.

**Lo que no se hizo, y por qué:** buscar un equipo por código patrimonial dentro del
formulario. El hook que hay para eso está mal tipado y usa un endpoint que **también
busca por nombre**, así que reintroduciría justo la ambigüedad que se quita. Para
enlazar un equipo que no es de la persona se hace desde la ficha del caso.

### AP5-AP8 — El tipo se ve, y «equipos a cargo» rediseñado

**Estado: COMPLETADA**

Al registrar «Es un CPU» y guardar, la bandeja decía **«Sin equipo»**. El tipo sí
estaba guardado —`activo_tipo: "CPU"` en `TKT-2026-000101`— pero no se enseñaba, y
eso se lee como que al registrar el caso se perdió algo.

- **El tipo sale cuando no hay equipo enlazado.** La celda pone el tipo en la
  primera línea y **«Sin identificar»** en la segunda. Con nombre de equipo sigue
  como estaba: nombre arriba, tipo y conjunto debajo. En la ficha del caso, lo
  mismo: *«CPU · sin identificar»* en vez de *«No indicado»*.
- **La columna EQUIPO pasó de 13 % a 15 %** —se lo quitó a Afectado, de 14 % a
  12 %—. «Computadora N°01» no cabía en 13 % y se partía en dos líneas, lo que
  descuadraba el alto de todas las filas. Medido: las 7 columnas miden igual en
  las 3 vistas y **todas las filas quedan en 96 px**.
- **`truncate` y no `line-clamp-1` en la celda.** Antes se eligió `line-clamp-1`
  porque `truncate` dejaba que el navegador ensanchara la columna; eso ya no pasa
  con `table-fixed` y el `<colgroup>`, donde manda el ancho declarado. Y
  `line-clamp-1` **no estaba recortando**: «Mouse · Computadora N°2» salía
  partido en dos líneas. Ahora se corta con puntos y el texto entero queda en el
  `title`.

**Diseño de «equipos a cargo»:**

- **Rótulo «Equipo de Maicol»** sobre la lista. Sin él no se sabía que esas filas
  se podían tocar: del título del panel a un texto en mayúsculas que parecía
  encabezado de tabla, sin ningún sitio donde diga que es una elección.
- **Agrupado por conjunto**, que es como están de verdad: una persona con una
  computadora tiene un conjunto con varias piezas, y en lista plana no se ve
  cuáles forman parte de la misma máquina. El agrupado lo da la API.
- **El nombre del conjunto perdió el negrita.** Con él, el conjunto pesaba más que
  el nombre del equipo, que es justo al revés de lo que se está eligiendo: el
  conjunto es contexto, el equipo es la decisión.
- **El icono sale del tipo, no es una imagen fija.** Había un disco duro en todas
  las filas y al lado de «Mause17 — Mouse» afirmaba algo falso: el mismo error que
  motiva el componente, en pequeño. Doce tipos con su icono, y disco duro solo como
  último recurso. Se compara sin acentos ni mayúsculas.
- **Ayuda más corta**: de dos líneas a una.

**Un agujero tapado de paso, que no estaba fallando:** la lista de *uso común de la
oficina* se pedía con `{"oficina_id": usuario.oficina_id}` y, si la persona **no
tiene oficina**, la consulta se quedaba literal sin filtro de oficina: habría
devuelto **todos** los equipos sin responsable. Como 875 de 876 equipos no tienen
responsable, habría salido casi todo el inventario en la lista de quien reporta.
Ahora no se busca nada si no hay oficina. **No puede llegar a pasar hoy** —el
esquema de la base exige que `oficina_id` sea un ObjectId, así que ningún equipo
puede tenerlo nulo—, pero la consulta estaba a un cambio de esquema de fallar.

**Verificado:** 78 pruebas backend en verde, `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola. En pantalla: las 7 columnas
miden igual en las 3 vistas, filas de 96 px, la ficha del tipo sin equipo dice
«CPU · sin identificar», y elegir un equipo **oculta** el desplegable de tipo
porque con equipo el tipo sale de él.

### AQ1-AQ5 — Alta de equipo: zona, conjuntos a la vista, y que no se cierre sola

**Estado: COMPLETADA**

Cuatro cosas del alta de equipo y una del buscador.

- **Pide zona antes que oficina, y la zona filtra las oficinas.** Antes salían las
  **59 oficinas** en un desplegable sin más, y no había forma de saber en qué zona
  iba a quedar el equipo. Ahora: primero la zona, con su número de oficinas al lado
  —«PALACIO · 27 oficinas»— y después solo las oficinas de esa zona. La oficina
  queda bloqueada hasta elegir zona. Al cambiar de zona se sueltan oficina y
  conjunto, que si no el backend responde «el conjunto pertenece a otra oficina».

  La zona **no se manda al backend**: `crear_activo` la copia de la oficina
  (`zona_id`/`zona_nombre` salen de `oficina`). Se pide en el formulario para poder
  filtrar y para no registrar en una zona sin querer, y sale en el paso de
  revisión.

  Las zonas que salen son las activas: **LEYVA no aparece** porque está desactivada
  y no tiene ninguna oficina.

- **Los conjuntos existentes se ven, con su número de equipos.** Antes había un
  cuadro de texto en blanco y, al lado, la sugerencia del sistema: «Computadora N°3».
  No había forma de saber que conjuntos había, y el estado `conjuntoId` existía en
  el componente pero **nada lo rellenaba**: estaba muerto. Ahora hay un desplegable
  con los conjuntos de esa oficina y su recuento —«Computadora N°01 · 4 equipos»— y
  el campo de nombre nuevo solo sale si eliges «Crear uno nuevo». El backend ya
  traía `total_activos` y no se usaba.

  Se ve el problema que evita: en ALCALDIA hay **`Computadora N°02 · 4 equipos`** y
  **`Computadora N°2 · 1 equipo`**, que es la misma computadora con dos nombres. Sin
  la lista a la vista, el nombre nuevo sale casi siempre.

- **La consulta de conjuntos espera a que haya oficina.** Sin ella salían los **261**
  conjuntos del municipio, y `listar_conjuntos` hace una consulta al inventario
  **por conjunto** para contar sus equipos y calcular su completitud. `useConjuntos`
  acepta ahora un `habilitado`.

- **El panel ya no se cierra al pulsar fuera.** En un formulario de tres pasos se
  perdía todo lo escrito por un clic perdido. `Sheet` tiene `cerrarFuera`, que
  viene activated; el alta de equipo lo apaga. **La X y Escape siguen cerrando.**
  Verificado en pantalla: tras un clic fuera sigue abierto, conserva lo escrito, y
  la X cierra.

- **El buscador busca también por tipo de equipo.** Ya lo había propuesto la ronda anterior y ya está. Buscar
  «CPU» devuelve **11** tickets, **2** de ellos de equipo sin identificar, que antes
  no aparecían porque `activo_nombre` está vacío y el tipo vive en `activo_tipo`.

  De paso se corrigió algo que **no era lo que dije**: afirmé que buscar
  `PC (recepción)` daba un error 500. **Es falso.** Con los paréntesis balanceados la
  expresión es válida —un grupo de captura— y devolvía cero resultados en silencio.
  Lo que sí pasaba, comprobado contra la base:

  | lo tecleado | antes | |
  |---|---|---|
  | `a*b` | **17 tickets** | `a*b` es «cero o más a seguido de b», no la palabra |
  | `a[bc` | error 500 | expresión inválida |
  | `COMPUTADORA N.1` | **9 equipos** | el `.` casaba con el `°` de «N°1» |

  Con `re.escape` se busca lo que se escribió.

**Verificado:** 78 pruebas backend en verde, `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola. En pantalla: zona con 5 opciones
activas, oficinas bloqueadas hasta elegir zona (27 al elegir PALACIO), 3 conjuntos en
ALCALDIA con su recuento, el panel sobrevive al clic fuera y el buscador encuentra
los casos por tipo.

### AR1-AR4 — El diálogo de guardar vista, más corto; y la campana, verificada

**Estado: COMPLETADA**

**El diálogo.** Bajó de unas 90 palabras a **47**, y de cuatro párrafos sueltos a
tres líneas. Se quitó la frase «Un atajo con lo que estás viendo ahora. Al pulsarlo
se recupera todo esto de golpe», que no decía qué hacer, y la ayuda del campo de
nombre, que repetía lo mismo. Ahora:

- «Ponle un nombre y aparecerá como un botón para volver aquí con un clic.»
- El campo se llama **«Nombre»**, no «Nombre de la vista».
- «Qué se va a guardar» → **«Se guarda»**.
- Las notas de abajo son tres líneas sueltas: las columnas, la primera página, y
  quién la verá.

**Un texto era falso y sigue siendo falso por dentro.** Se dice «las 7 columnas que
ves ahora, **pero no su orden**». Se comprobó: `guardarVista` manda `columnas:
columnasVisibles`, que es un array, así que el orden se guarda… pero `DataTable`
hace `setVisibles(Object.fromEntries(columnas.map(...)))`, y eso construye el mapa
**en el orden de la definición de columnas**, no en el del array. El orden se
pierde al aplicarlo. El texto dice la verdad.

**La campana, verificada de punta a punta:**

| | |
|---|---|
| Sin avisos | «No tienes notificaciones» + para qué sirve. Sin errores. |
| Con 2 sin leer | insignia «2» y etiqueta accesible «Notificaciones: 2 sin leer» |
| La lista | título, mensaje y tiempo; sin leer con fondo y punto |
| «Marcar todas» | solo aparece si hay algo sin leer |
| Al pulsar | va a `/panel/tickets/{id}` y marca ese aviso como leído |

Las dos cosas que no se pudieron comprobar con datos de verdad, y por qué:

- **El administrador no tiene ni un aviso.** Los 10 de la base son de Maicol. Para
  ver la lista con contenido se interceptó la respuesta en el navegador con avisos
  de ejemplo, y **las peticiones que escriben se cortaron**: no se escribió nada en
  la base municipal.
- **No se pudo entrar como Maicol** para verlo desde el portal. Su correo es un
  Gmail real y no se conoce la clave; no se intentó restablecerla.

**Un hallazgo de paso: hay avisos duplicados.** Cuatro tickets tienen **dos** avisos
de «Problema resuelto» cada uno. En dos de ellos con **40 y 17 segundos** de
diferencia, y el ticket cerrado **una sola vez**: `cerrado_en` coincide con el
primer aviso y el segundo no cambió nada. Eso no es cerrar, reabrir y cerrar —eso
dejaría una reapertura en la línea de tiempo—.

La prueba que cubría esto decía `no_leidas >= 1`, así que **el duplicado pasaba
inadvertido**. Se cambió a exigir la cantidad exacta, y **pasa**: un cierre, un
aviso, y volver a cerrar no añade otro. Es decir, **el fallo era del código antiguo**
—los avisos son del 7 al 9 de octubre, de antes de unificar los estados— y **hoy no
se reproduce**. Los avisos viejos siguen en la base; borrarlos es cosa tuya.

**Verificado:** 79 pruebas backend en verde, **una nueva**. `tsc` y ESLint sin
errores, `verify:clases` en verde, sin errores de consola.

### AS1-AS3 — Desmarcar «es parte de un conjunto» lo suelta todo

**Estado: COMPLETADA**

Al desmarcar la casilla, la pantalla de confirmación seguía diciendo que el equipo
pertenecía a un conjunto. Reproducido: marcaba la casilla, el sistema rellenaba el
nombre solo con «Computadora N°2», se desmarcaba, y la confirmación seguía
poniendo **Conjunto = «Computadora N°2»**.

- **Desmarcar suelta las dos cosas**, no solo el interruptor. `conjuntoId` no se
  limpiaba, y es justo lo que se manda primero: `guardar` hace
  `conjuntoId || crearConjunto()`. Con un conjunto elegido y la casilla desmarcada,
  el equipo se guardaba **enlazado a ese conjunto**, que es lo contrario de lo que
  se había marcado. Ahora desmarcar vacía también el nombre.

- **La confirmación no puede contradecir lo de arriba.** Si la casilla está
  desmarcada, sale «No aplica» sin mirar nada más. Antes se miraba el nombre
  guardado, y por eso mentía.

- **Marcar la casilla obliga a decir cuál es.** Se puede guardar con la casilla
  marcada solo si se eligió un conjunto existente o se escribió un nombre. Antes se
  guardaba un equipo suelto con la casilla puesta. En la revisión sale «Sin elegir».
  El caso normal no se ve afectado porque la sugerencia del sistema rellena el
  nombre solo.

**Verificado en pantalla**, en los tres caminos:

| | antes | ahora |
|---|---|---|
| Marcar y desmarcar | confirmación decía «Computadora N°2» | «No aplica» |
| Elegir un conjunto y desmarcar | se quedaba enlazado a ese conjunto | el desplegable vuelve a «Crear uno nuevo», o sea que se soltó |
| Marcar sin elegir ni escribir | se guardaba sin conjunto | «Sin elegir» y botón bloqueado; al escribir el nombre, se desbloquea |

**79 pruebas backend en verde**, `tsc` y ESLint sin errores, `verify:clases` en
verde, sin errores de consola. Sin cambios en el backend esta ronda.

### AT1-AT3 — Auditoría del inventario: dos alturas de fila y dos estados vacíos

**Estado: COMPLETADA**

Recorrido completo de `/panel/equipos` midiendo, no solo mirando.

**1. Las filas tenían dos alturas: 68 px y 87 px.** El distintivo del conjunto iba
en una tercera línea, y solo aparece cuando el equipo pertenece a uno. Medido en
la primera página: **5 filas de 68 px y 20 de 87 px**. En pantalla se veía el
salto, unas filas muy juntas y otras con un hueco debajo.

- El distintivo pasó a la **primera línea**, junto al nombre. Todas las filas miden
  **68 px** y la tabla ocupa 1.700 px en vez de 2.175 con 25 filas.
- **Solo sale cuando aporta algo.** Con estos datos casi nunca lo hace: el equipo
  se llama «Computadora N°01 - Monitor» y su conjunto es «Computadora N°01», o sea
  que el distintivo repetía el nombre. Es la misma regla que ya usaba la columna
  EQUIPO de la bandeja: si el nombre empieza por el del conjunto, el conjunto ya
  está dicho.

**Un intento se tiró abajo por el camino.** Poner el distintivo al final de la
**segunda** línea daba filas iguales, pero el distintivo se comía el espacio y el
**código patrimonial se cortaba**: «CPU · CYBERLINK CASE…» en vez de «CPU ·
CYBERLINK CASE · 740899500012». El código identifica el equipo —461 de 876 lo
tienen y **ninguno está repetido**— y el conjunto lo tiene **1 de 876**. No pueden
competir por el mismo hueco. Por eso acabó en la primera línea, y solo cuando
añade algo.

**2. Dos estados vacíos a la vez, y uno mandaba la instrucción equivocada.** Al
buscar «zzzznoexiste» salían la franja de «0 coincidencias» y, debajo, un cartel
que decía *«Prueba con otros filtros, o **registra el primer equipo si el
inventario está vacío**»*. El inventario tiene **876 equipos**.

No se preguntaba si el inventario estaba vacío o si eran los filtros, que es
justo lo que distingue las dos cosas. Ahora:

- con filtros puestos: «**Ningún equipo sale con estos filtros** / Prueba a quitar
  alguno, o cambia la búsqueda»;
- sin filtros y cero equipos: «**El inventario está vacío** / Registra el primer
  equipo», con el botón.

**Lo que se miró y está bien, y no se tocó:**

- **Las columnas no se pueden ordenar, y es a propósito.** El orden de TanStack es
  del cliente: con 876 equipos y 36 páginas, ordenar solo reordenaría las 25 de la
  página actual, que es peor que no ordenar. Ordenar de verdad es una función
  nueva: que el backend acepte el criterio.
- **La casilla «El responsable no tiene cuenta»** se announced sin nombre en una
  primera medición, pero es un falso positivo: el `<label>` la **envuelve**, así que
  el nombre accesible sí es «El responsable no tiene cuenta» y se activa con el
  espacio. No hay nada que arreglar.
- Los cuatro filtros (Zona, Oficina, Tipo, Agrupar por) tienen etiqueta asociada y
  se anuncian bien.

**Pendiente que no se arregla aquí:** dos nombres de oficina se cortan con puntos
—«COMPROMISO 1 PADRON DOMINAL» y «GERENCIA DE DESARROLLO SOCIAL»— en la columna
UBICACIÓN, que es de 176 px. Se ven enteros en la ficha del equipo y con el
agrupado por zona ocupan la misma; es cuestión de ancho, no de texto.

**Verificado:** 79 pruebas backend en verde, `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola ni peticiones con error.

### AU1-AU5 — Ficha del equipo: una sola alarma de repetido, y conjunto editable

**Estado: COMPLETADA**

Recorridas fichas de Impresora, CPU y Laptop. El comportamiento de campos por tipo
funciona bien: un Monitor no pregunta procesador ni RAM, una Laptop sí, y la
disponibilidad de cada campo cambia con el tipo.

**1. La alarma de repetido eran tres avisos en dos sitios.** En la ficha de un CPU
con la IP repetida:

- arriba del panel, un recuadro grande «Hay datos que ya están en otro equipo» con
  la lista de cada coincidencia y un párrafo de explicación;
- junto al campo, una etiqueta «Repetido en 1» que solo daba el **número**;
- debajo del campo, otra línea «También en DESKTOP-LCFMHER. No es obligatorio.»

Una misma información, tres veces y en dos formatos. Ahora **solo queda la alarma**,
que dice **cuál** se repite, con enlace a su ficha, y todo lo demás en la
explicación al pasar el ratón.

**2. Ya no se sale de su sitio.** Medido: la columna del panel mide **327 px** y el
desplegable de disponibilidad se come 130. Con la etiqueta al lado del desplegable
el nombre del otro equipo se cortaba en «Computador…», que es justo lo que había
que evitar. Por eso la alarma va **en su línea propia**, con el ancho acotado y
recorte con puntos: con nombres largos no empuja nada.

Comprobado en la CPU con la IP `192.168.0.46` repetida: la alarma dice
**«Repetido en Computadora N°01 - CPU»** entera, dentro del panel, y ningún
elemento se sale de su columna.

**3. El recuadro grande de «equipos con el mismo código o dirección»** del formulario
también se quitó y se sustituir por una línea con la misma alarma. Ese aviso
**no se puede borrar sin más**: avisa de lo que se acaba de escribir, que todavía
no está guardado, y sin él se guardaría a ciegas.

**4. Ya se puede cambiar el conjunto desde la ficha.** No se podía: el alta sí
elegía conjunto, pero una vez creado el equipo no había dónde cambiarlo. Si se
registraba suelto y luego se caía en la cuenta de que era parte de una
computadora, la única salida era darlo de baja y volver a registrarlo. Ahora hay
un desplegable junto al responsable, con los conjuntos **de esa oficina** y su
número de equipos. Al cambiar de oficina se suelta el conjunto, igual que el
responsable.

**5. Un agujero del backend que solo se ve al abrir esta puerta.** Al **crear** un
equipo se comprobaba que el conjunto fuera de la misma oficina; al **editar** no.
Y como desde la ficha se cambian oficina y conjunto en la misma llamada, un equipo
podía quedar en MERCADO con un conjunto de PALACIO. Ahora se comprueba contra la
oficina **resultante**, que puede ser la que viene en ese mismo cambio, y no solo
la anterior.

**Prueba nueva**, con cinco cosas fijadas: conjunto de otra oficina rechazado;
rechazado también al cambiar la oficina en la misma llamada; entrar, cambiar de
conjunto dentro de la misma oficina; **mandarlo en blanco lo saca** y **omitirlo lo
conserva**, que no es lo mismo y es la diferencia entre quitar y no tocar.

**Lo que se miró y no se tocó:** el desplegable de Responsable sale vacío en estas
oficinas porque en toda la municipalidad hay **2 usuarios**. Es falta de cuentas,
no un fallo de la pantalla.

**Verificado:** 80 pruebas backend en verde, una nueva. `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola.

### AV1-AV4 — Cerrar un ticket se quedaba «abierto», y dos etiquetas que no cuadtaban

**Estado: COMPLETADA**

**1. El fallo de verdad: cerrar un ticket y que siguiera saliendo abierto.**

Las cuatro acciones de la ficha del caso —asignar, cambiar de estado, cerrar y
reabrir— recarga**ban la ficha y nada más**. Y el cliente de datos está montado a
propósito con `staleTime` de 30 s y `refetchOnWindowFocus: false`, para que la
bandeja no parpadee al saltar entre pantallas.

Medido: al abrir la bandeja se hacen **3 peticiones**; al entrar en un ticket y
volver, **0**. La lista se sirve de caché y no se vuelve a pedir. Así que un
ticket recién cerrado se quedaba en la cola de «Abiertos» con el estado viejo,
el resumen no bajaba el contador, la campana no se actualizaba y la ficha del
equipo seguía diciendo que tenía un ticket abierto.

Ahora las cuatro acciones invalidan lo que el cambio deja anticuado: las listas de
tickets (el prefijo `['tickets']` cubre también el resumen), la ficha, los conteos
por equipo (`['activos-tickets']`, que tenían **60 s** de caché), la analítica, la
campana y las notificaciones.

**2. Una etiqueta que se contradecía a sí misma.** En el bloque «Cuándo se cogió»,
un ticket cerrado ponía:

> DENTRO DEL PLAZO DE 4 H
> 50 min tarde

Las dos cosas a la vez en la misma casilla: la etiqueta afirmaba que se cumplió el
plazo mientras el número decía que no. La etiqueta era fija y el valor variable.
Ahora la etiqueta dice **qué se midió** —«Plazo de respuesta: 4 h»— y el veredicto
lo lleva el valor: «Cumplido» o «50 min tarde». Antes el valor de «cumplido» era un
«Sí» que, al lado de la etiqueta, sonaba a que se había cumplido.

**3. El bloque de tickets del equipo, rediseñado.** En la ficha de un equipo con
9 tickets:

- antes: «Ver los 1 tickets abiertos de este equipo» y «1 ticket en el historial
  cerrado», **las dos con el mismo peso**, aunque una es lo pendiente y la otra ya
  pasó. Y el plural salía mal: «los 1 tickets»;
- ahora: una fila marcada **«⚠ 9 tickets abiertos · Ver»** para lo pendiente, y
  debajo, discreto, «1 caso cerrado en el historial».

Cuando no hay abiertos, se dice con palabras y con un visto bueno —«✓ Sin tickets
abiertos»— en vez de dejar una línea al lado de un enlace.

**Verificado:** 80 pruebas backend en verde, `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola. Los dos estados del bloque de
tickets comprobados en pantalla: el equipo con 9 abiertos y el que solo tiene uno
cerrado.

### AW1-AW5 — La pestaña Calidad: un ranking sin nombres, y sumas que no significan nada

**Estado: COMPLETADA**

Analizada la pestaña `/panel/equipos/calidad` de punta a punta.

**1. El panel «Por tipo de equipo» no decía de qué equipos hablaba.** Mostraba las
barras con su porcentaje y **la etiqueta en blanco**: quince filas de «0%», «0%»,
«63%»… sin ninguna palabra. Inútil de principio a fin.

El motivo: el panel leía `fila.tipo`, y `_agrupar` devuelve **siempre** la etiqueta
en `nombre`. Se estaba leyendo una propiedad que la API no devuelve, así que salía
la cadena vacía. Además el panel no era pulsable, al contrario que zona y oficina.

**2. Una columna de 1.300 px de espacio vacío.** La rejilla de dos columnas ponía
juntos «Por zona» —6 entradas— y «Por oficina» —59—. La columna izquierda se
acababa a los 770 px y el hueco seguía hasta el pie de la página.

Ahora los dos cortos van juntos arriba y los dos largos debajo a todo el ancho:
«Por tipo» entero y «Por oficina» repartido en dos columnas, que es lo único que
hacía falta para que 59 entradas no fueran una escalera.

**3. Sumas que no significaban nada.** Al pie de cada panel ponía «Suma: …»:

- en los de porcentajes: «Suma: **1.096 %**» y «Suma: 83 %». Los porcentajes de
  zonas u oficinas distintas **no se suman entre sí**; 1.096 % no iba con nada;
- en el de los datos que faltan: «Suma: **2.028 equipos**». Son 2.028 **datos**, y
  además contados con repetición: un equipo al que le falten tres campos aparece en
  tres barras, así que la suma nunca son equipos distintos.

Ahora los paneles de porcentaje dicen que cada barra lleva su porcentaje al lado, y
el de campos explica el número y por qué no se suman los equipos.

**4. El filtro por tipo no leía la URL, así que sus enlaces no filtraban.** El
inventario arrancaba siempre con el tipo vacío y no lo escribía nunca: un enlace
como `/panel/equipos?tipo=Monitor` —el que debería llevar este mismo ranking— llega
al inventario **sin filtrar**. Un control que parece funcionar y no hace nada. Ahora
el tipo vive en la URL como los demás, y comprobado: al pulsar «Monitor» el
inventario sale con Tipo = Monitor y las filas son monitores.

**5. La mitad del ranking por tipo no son tipos.** Al arreglar las etiquetas se vio
qué había detrás: **8 de las 15 filas no son tipos de equipo**, y son 33 equipos.

| Lo que pone en «tipo» | Equipos | Qué es en realidad |
|---|---|---|
| Por identificar | 8 | un marcador de la importación |
| INOPERATIVO | 5 | un **estado** |
| PERONAL | 5 | un cargo, y sin la erre |
| SIN CONEXCION | 5 | un **estado** |
| LAPTO | 4 | «Laptop» cortado |
| FALTASTES | 4 | basura |
| FALTAN | 1 | un aviso del Excel |
| 7422235800 | 1 | un **código de patrimonio** |

El Excel traía más columnas que el tipo de equipo yacabaron en ese campo: el equipo
«Computadora N°02 - INOPERATIVO» tiene de tipo «INOPERATIVO».

**No se ha corregido ni un equipo**, porque son datos de la municipalidad y decidir
qué es cada máquina es criterio de quien conoce el inventario. Lo que sí se ha hecho
es **marcar esas filas** con «no está en el catálogo de tipos», para que el panel
deje de ser ruido y sea una lista de trabajo.

**Verificado:** 80 pruebas backend en verde, `tsc` y ESLint sin errores,
`verify:clases` en verde, sin errores de consola ni peticiones con error.

### AX1-AX6 — Calidad rediseñada: cada gráfico dice qué mide, y los filtros van a la URL

**Estado: COMPLETADA**

Rediseño de la pestaña Calidad y otra pasada de errores, siguiendo el flujo paso a
paso: entrar, filtrar por zona, filtrar por oficina, quitar el filtro y pulsar una
barra.

**1. Qué mide el porcentaje, dicho una vez y arriba.** Los gráficos decían «19 %»
y «0 %» sin más. Un «Monitor · 0 %» parece decir que no hay monitores con datos,
cuando lo que dice es que **ninguno de los 181 monitores tiene todos sus campos
escritos**: la diferencia entre una cifra tranquila y una alarmista. Ahora hay una
nota al principio que lo explica, y no se repite en los cinco gráficos.

**2. Cada gráfico, con su título y su explicación.** No basta con «Por zona»: hay
que saber qué mide y qué se puede hacer con él.

- **Qué datos faltan más** — cuántos equipos no tienen escrito cada dato; un equipo
  puede salir en varias barras.
- **Por zona** — equipos con todos sus datos, por zona; pulsa una para abrir su
  inventario.
- **Por tipo de equipo** — ídem por tipo; los que no están en el catálogo necesitan
  corregirse.
- **Por oficina** — ídem por oficina, con los tres datos que más faltan en cada una.

**3. Los filtros van a la URL.** Se guardaban solo en el estado del componente: la
barra de direcciones no cambiaba nunca, el botón «Atrás» no deshacía el filtro y la
vista filtrada no se podía compartir. Ahora la URL es `?zona_id=…`.

**4. Al filtrar se ve el alcance y se puede volver atrás.** Al elegir una zona
decía el 0 % sin más: el mismo 19 % significa muy distinto con 36 equipos que con
511. Ahora pone «36 equipos en este filtro» y aparece un botón **Quitar filtros**
que solo existe cuando hay algo puesto.

**5. «Por zona» desaparece cuando estás filtrando por zona.** Con una zona
elegida, ese gráfico se queda con **una fila: la zona que acabas de elegir**. No es
un resumen, es el mismo dato que ya dice el filtro de arriba, en un gráfico entero.
Se oculta y no se pone nada en su lugar: el de los datos que faltan ya está al lado
y dice exactamente lo mismo.

**6. Los nombres largos ya no se cortan en nada.** Las oficinas salían como
«SUB. GERENCIA D…» y «GERENCIA DE AD…», que no dicen nada. `BarrasCampos` acepta
ahora el ancho de la columna de etiquetas: las oficinas van a 208 px y los tipos a
160, y los nombres se leen.

**Un intento que se tiró abajo:** en lugar de «Por zona» iba a poner un panel
«Cómo está esa zona» con los datos que faltan. Al verlo salían **dos paneles con las
mismas barras**, uno al lado del otro. Se quitó; con filtro basta con el que ya hay.

**Verificado recorriendo el flujo:** los cuatro gráficos con título y explicación,
el filtro reflectedo en la URL, el alcance visible, el botón que aparece y desaparece,
zona → oficina encadenadas, sin errores de consola ni peticiones con error.
80 pruebas backend en verde, `tsc` y ESLint sin errores, `verify:clases` en verde.

### AY1-AY6 — El «0 %» era verdad y mentía a la vez: dos porcentajes, filtro de pendientes y oficinas recortadas

**Estado: COMPLETADA**

El usuario preguntó por qué PISCINA MUNICIPAL salía a 0 %, pidió que al pulsar una barra
se filtraran solo los equipos con datos faltantes, dijo que los gráficos no se entendían
y que las listas se desbordaban en dos filas.

**El 0 % no era un error de cálculo.** El porcentaje que se mostraba era *la parte de
equipos a los que no les falta ningún campo*, y en PISCINA MUNICIPAL hay 36 equipos y
**ninguno** completo: 96 datos que faltan repartidos. La cifra era correcta y aun así
decía «no tiene nada escrito», que no era verdad. El problema no era el número, era que
solo había uno y era el menos intuitivo de los dos.

**1. Se calculan los dos porcentajes y las barras usan el que se entiende de un
vistazo.** `calidad_service._analizar` ya sumaba `esperados` por equipo (línea 59) pero
`_agrupar` lo tiraba: no había forma de decir «de 3.000 casillas hay 2.500».
Ahora la API devuelve `porcentaje_datos`, `esperados`, `completos` y `esperados_totales`,
y `porcentaje` se queda con su significado original.

- **La barra** = datos escritos. «De 3.000 casillas hay 2.500», que es lo que se lee sin
  explicación.
- **El detalle de la fila** = equipos, datos sin escribir y equipos completos. Los tres
  números, para que el denominador esté siempre a la vista.

**Medido después del cambio:**

| Antes | Después |
| --- | --- |
| PISCINA MUNICIPAL · 0 % | PISCINA MUNICIPAL · 36 equipos · 96 datos sin escribir · 0 completos · **36 %** |
| Zonas a 0 %: 4 de 5 | Zonas a 0 %: **0 de 5** |
| Oficinas a 0 %: casi todas | Oficinas a 0 %: **0 de 14** |
| PALACIO · 19 % | PALACIO · **51 %** |
| Monitor · 0 % | Monitor · **70 %** |
| CPU · 0 % | CPU · **38 %** |
| Teclado · 0 % | Teclado · **81 %** |

Quedan **5 tipos a 0 %** de 15, y son legítimos: «Por identificar», «INOPERATIVO» y
demás, donde de 1 a 8 equipos no hay prácticamente nada escrito. Ahí el 0 % sí es la
información útil.

**2. Al pulsar una barra se filtran solo los equipos incompletos.** El backend ya tenía
el filtro `solo_faltantes` (`inventario_service.listar`, línea 707, junto a
`responsables_pendientes`) y el esquema lo aceptaba: **lo que faltaba era que la pantalla
lo ofreciera**. Los tres enlaces de los gráficos —zona, tipo y oficina— llevan ahora
`&solo_faltantes=1`.

Comprobado con una oficina: la URL queda
`/panel/equipos?oficina_id=…&solo_faltantes=1`, el subtítulo lo explica y **las 20 filas
que salen tienen datos pendientes: 20 de 20**.

**3. El filtro también se puede poner y quitar a mano.** El inventario tiene un
interruptor «Solo los que tienen algún dato sin escribir», en el mismo grupo que el de
responsables pendientes. Si el enlace llega con el filtro puesto, la casilla aparece
marcada y se puede quitar; sin el filtro, la casilla está libre y no estorba. Vive en la
URL como los demás.

**4. Las oficinas ya no son una escalera.** Eran 59 filas en dos columnas, dos pantallas
de alto, y **ordenadas por cantidad de equipos**, no por calidad: la lista empezaba por
las oficinas más grandes, que no son las peores. Ahora:

- van **de peor a mejor** (más datos sin escribir primero), que es el orden en el que se
  va a trabajar;
- se muestran **las 12 con más pendientes**, y el resto está a un botón
  («Ver las 59 oficinas» / «Ver solo las peores») que solo aparece si hay más de 12.

**5. La nota de arriba ya no mintió.** Decía «cada porcentaje es la parte de equipos que
tienen todos sus datos escritos», lo cual dejó de ser cierto en cuanto las barras
midieron otra cosa. Ahora explica los dos números, dice cuál usa cada sitio y por qué
salía a 0 %.

**6. El indicador grande cambió de métrica.** Decía «Completitud global · 19 %» —el
estricto— al lado de zonas al 51 %, lo que parecía una contradicción. Ahora es
«Datos escritos · 50 %» con el detalle «2.028 de 4.049 casillas esperadas», y el
estricto vive en «Equipos sin pendientes · 168». Los dos números, cada uno en su sitio.

**Verificado en el navegador:** ninguna fila a 0 % en zonas ni oficinas, los cuatro
gráficos con cifras que se entienden, el enlace con `solo_faltantes=1` trae solo
incompletos (20 de 20), el interruptor aparece y desaparece, el botón de oficinas cambia
de texto, sin errores de consola ni peticiones fallidas.
80 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores (6 warnings
preexistentes), `verify:clases` en verde.

### AZ1-AZ5 — El 0 % por fin significa una cosa sola, una sola barra y el ratón se ve

**Estado: COMPLETADA**

El usuario volvió a(libros): «0 % debería ser que faltan todos los datos y 100 % que están
todos escritos; dime que una parte sale 0 % pero tiene datos y no me cuadra». Y dos cosas
más: dos barras horizontales en el inventario y que no se nota dónde está el ratón.

**1. El porcentaje ahora tiene una sola definición, y un 0 % no puede significar otra
cosa.** Se quitó de cada fila el recuento de «equipos completos». Antes una fila decía
«PISCINA MUNICIPAL · 36 equipos · 96 sin escribir · **0 completos** · 36 %»: dos ceros y
un 36 %, y no era cuál era el bueno. Ahora cada fila dice **escritos de esperados**:

```
PISCINA MUNICIPAL | 36 equipos · 54 de 150 datos escritos | 36 %
SIN CONEXCION    | 5 equipos · 0 de 15 datos escritos     | 0 %
```

Con eso el 0 % se demuestra solo: **0 de 15 escritos** no se lee como «algo escrito».
Y los que siguen a 0 % son cinco tipos basura vacíos de verdad —INOPERATIVO, PERONAL,
SIN CONEXCION, FALTASTES y FALTAN, con 0 de 15, 0 de 15, 0 de 15, 0 de 12 y 0 de 3— que
antes era imposible distinguir de un error de cálculo.

**2. La barra a 0 % ya no dibuja nada.** Estaba `Math.max(2, …)`: un mínimo de 2 px para
que «se notase», que es justo lo que hace que un 0 % parezca «hay algo». Ahora el 0 % es
una pista vacía. El mínimo solo se aplica al tope del 100 %, para que una barra al 99 %
no se salga.

**3. La nota de arriba se rescribió.** Decía «hay dos porcentajes y no son lo mismo», que
tras el punto 1 ya no era cierto y además era la fuente de la confusión. Ahora dice una
cosa: **0 % es que no hay ningún dato escrito; 100 % es que no falta ninguno**.

**4. El inventario tenía dos barras horizontales —y eran dos para lo mismo.** `DataTable`
pone debajo de la tabla su propio tirador (la pista redondeada con el pulgar), y por encima
aparecía también la del navegador: en la imagen se veían la gris con flechitas y la otra
debajo. El culpable era una línea:

```tsx
!mostrarDesplazamiento && 'sin-barra'
```

`sin-barra` **no oculta la barra del navegador: la adelgaza a 8 px**. Y en el inventario
`mostrarDesplazamiento` venía activado, así que ni siquiera se aplicaba. En las tablas
cortas tampoco se notaba porque el desborde no llegaba a aparecer.

Solución: clase nueva `barra-oculta` (`scrollbar-width: none`), que oculta la del
navegador sin tocar `sin-barra`, que se sigue usando en otros sitios donde sí se quiere
una barra fina. Se quita `mostrarDesplazamiento`, que ya no decidía nada. Comprobado a
1280 px —donde la tabla desborda 105 px—: `scrollbar-width=none`, tirador propio
presente, y arrastrándolo el desplazamiento va de 0 a 105.

**5. El ratón ahora se ve.** El hover de las barras pulsables era `hover:bg-muted/60`, un
gris tan parecido al de la pista que no se notaba: había cinco zonas pulsables y ninguna
decía cuál. Ahora la fila que está bajo el ratón se pinta de crema, gana una marca dorada
a la izquierda y le sale una flecha a la derecha —que es lo que dice «esto se abre»—. Las
filas que no hacen nada se quedan como estaban, y así se distinguen de un vistazo.

**Verificado:** 0 filas a 0 % que no digan «0 de N datos escritos»; fondo del hover
`rgba(0,0,0,0)` → `rgb(251,241,210)` con marca `rgb(226,178,60)` y flecha a opacidad 1;
una sola barra horizontal en el inventario y el arrastre funciona; sin errores de consola
ni peticiones fallidas. 80 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores
(6 warnings preexistentes), `verify:clases` en verde.

### BA1-BA7 — Importar: la acción de cada fila se ve, los avisos se agrupan y el lote pide permiso

**Estado: COMPLETADA**

Revisión completa de la pestaña Importar: errores, datos, funciones, pruebas, funcionalidad
y diseño. Recorrido real con el Excel de muestra de las pruebas, que va a una base de datos
aparte (`mesa_ayuda_test_<random>`) y no toca el inventario municipal.

**Lo que funcionaba:** sin errores de consola ni peticiones fallidas en todo el recorrido;
la plantilla oficial se descarga y es un `.xlsx` válido; un archivo que no es Excel responde
422 con «No se pudo abrir el archivo. Verifica que sea un .xlsx válido.» y la pantalla vuelve
al paso 1; el conteo de zonas, oficinas, filas y accuraciones es correcto; elDesplazamiento
por hoja del Excel filtra.

**1. La columna «Acción» era la última de veinte y no se veía nunca.** Medido: la tabla
medía 1.744 px en un hueco de 1.066, y **10 de 20 columnas quedaban fuera**, entre ellas
«Acción» —que es justo la pregunta de esa pantalla: qué va a pasar con esta fila—. Había
que arrastrar hasta el final para verla, y funcionaba como si no existiera.

Ahora «Acción» va **de primera y pegada al canto izquierdo**, con la fila entera
coloreada según lo que vaya a pasar («Se creará» / «Se actualizará» / «Se omitirá»), y se
queda ahí al desplazar. De paso, hoja y número se fundieron en una columna: «ZONA COMPLEJO»
estaba escrito tres veces seguidas en cada fila.

Quedan 7 columnas fuera de vista —procesador, RAM, IP, MAC…—, que son datos de detalle y
no la decisión. El encabezado ahora queda fijo al bajar, así que las 100 filas que se pintan
no se leen a ciegas.

**2. 58 tarjetas de aviso para decir dos frases.** El bloque de «advertencias y errores»
hacía una tarjeta por fila: con el archivo de muestra eran **58 tarjetas para 2 mensajes
distintos** —39 veces «sin propiedad indicada» y 36 veces «sin código patrimonial»—. El
segundo mensaje quedaba debajo del primero y no se veía.

Ahora los avisos se **agrupan por texto**, y cada línea dice el mensaje, **cuántas filas lo
tienen y cuáles son**, para poder ir a buscarlas al Excel:

```
Aviso · Sin propiedad indicada: se usará 'Institucional'.
       En 39 filas · filas 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 y 27 más
Aviso · El equipo no tiene código patrimonial: se identificará por oficina + conjunto + dispositivo.
       En 36 filas · filas 3, 4, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 y 24 más
```

Un error sigue mandando sobre un aviso, y si hay filas con error se dice explícitamente que
**no se importan**.

**3. «Filas contadas: 39 / 39» era un número que no podía ser otro.** El backend arma
`total_filas` con `len(filas)`, así que la comparación siempre salía cierta. Encima de eso
había dos cosas que parecían una red de seguridad y no lo eran:

- un aviso en rojo que decía «el desglose de filas no coincide con el total; no apliques la
  importación», **imposible que saliera**;
- el botón «Aplicar la importación» que comparaba esos mismos dos números, o sea que nunca
  se apagaba por eso.

Peor aún: si algún día el backend pasara a devolver una muestra en vez de todas las filas
—que es lo que habría que hacer con los 877 equipos—, ese guardia no avisaría de nada,
dejaría el botón apagado sin explicación y nadie sabría por qué no se podía importar. Se
quitaron los tres y la cifra ahora es «Filas en el archivo: 39».

**4. «1 oficinas».** Corregido con un ayudante de plural: «1 oficina», «2 oficinas».

**5. Falta de permisos al leer un lote.** `GET /importacion/{lote_id}` solo exigía estar
conectado, mientras que su hermana `GET /importacion/{lote_id}/resumen` sí pedía
`equipos.importar`: **dos puertas al mismo dato, una con llave y otra sin ella**. Cualquier
cuenta de la aplicación —una persona que solo reporta tickets— podía abrir el análisis del
archivo importado por el municipio: su nombre, sus hojas y la estructura de sus columnas.
Ahora exige el permiso, y hay **prueba nueva** (`test_ver_un_lote_exige_permiso_de_importar`)
que demuestra que la ficha se abre con permiso, da 403 sin él y que tampoco se puede
aplicar la importación saltándose el paso anterior.

**6. Tildes que faltaban en los avisos.** El backend escribía «se usara», «codigo
patrimonial», «se identificara». Toda la aplicación las usa; estas tres no. Corregidas.

**7. El `useMemo` de los avisos no guardaba nada.** `filasVisibles` era un array nuevo en
cada render, así que la agrupación se rehacía entera en cada tecla: con el archivo de
muestra no se nota, con los 877 equipos y sus avisos sí. Ahora `filasVisibles` va memorizado
también (ESLint lo señaló).

**Un hallazgo que se retiró:** parecía que la barra fija de abajo **tapaba cuatro filas** de
la tabla. Se comprobó desplazándose hasta el final del todo: **no tapa ninguna** —las cuatro
«tapadas» son solo las que quedan detrás mientras te mueves, que es lo que hace una barra
fija—. Era un artefacto de la captura de página entera, no un fallo. No se cambió nada por
ello.

**Verificado en el navegador:** acción visible y pegada en la primera columna, encabezado
fijo, 39 de 39 filas pintadas, 7 columnas de detalle fuera de vista, 2 avisos agrupados con
sus cifras, «1 oficina» en singular, sin errores de consola ni peticiones fallidas.
**81 pruebas backend en verde** (eran 80), `tsc` 0 errores, ESLint 0 errores (6 warnings
preexistentes), `verify:clases` en verde.

### Lo que queda pendiente en Importar

- `filas_excluidas` y `no_aplicar_confirmado` los acepta el backend y **la pantalla no los
  usa nunca**: no hay forma de quitar una fila concreta antes de importar.
- `GET /importacion/regolas` devuelve las ocho reglas de normalización —la mejor explicación
  de cómo funciona la importación— y no se llama desde ningún sitio.
- El backend devuelve **todas** las filas de la previsualización en el JSON (877 filas
  enteras por respuesta) y la pantalla solo pinta 100.
- `/importacion/{lote_id}/ajustes` y `/importacion/mapeo-guardable` no tienen contraparte en
  la pantalla.

Ninguno se ha tocado: son cambios de alcance y no lo que se pidió en esta ronda.

### BB1-BB6 — Importar: se ven las 875 filas, se explica por qué empiezan en la 3, y el resultado dice qué pasó

**Estado: COMPLETADA**

Tres cosas del usuario: que solo se veían 100 de 875 filas y no se podían verificar
las demás, por qué la lista empezaba en la fila 3, y una revisión del panel de resultado.

**1. La lista se cortaba en 100 y no había manera de seguir.** La ronda anterior subió el
tope de 30 a 100 y lo Pengelolaó como «Muestra de 100 de 875», lo cual es exactamente el
problema: una revisión que llega al 11 % no es una revisión. Ahora hay **paginación de 100**
con Primera, Anterior, Siguiente y Última, y el encabezado dice dónde estás:

```
Página 1 de 9 · 875 filas
Mostrando 1–100 de 875 filas.
```

Al cambiar de hoja se vuelve a la primera página, porque si no se aterriza en una página
que puede no existir. El paginador va **fuera** del contenedor con desplazamiento
horizontal: dentro, la barra del contenedor se lleva los botones al borde y a los lados
salen de la pantalla.

**2. Que empiece en la 3 es correcto, pero la pantalla no lo decía.** El número es **la
fila real del Excel**, no la posición en la lista —el backend lo calcula con
`enumerate(filas[indice + 1:], start=indice + 2)`. Leyendo el archivo municipal se
confirma:

| Fila | Contenido |
| --- | --- |
| 1 | `EQUIPOS INFORMATICOS` (título de la hoja) |
| 2 | `AREA · Tipo de equipo · Dispositivo · Código patrimonial…` (encabezado) |
| 3 | Primer equipo |

Es a propósito —con ese número se abre el Excel y se cae en la fila exacta—, pero sin
decirlo parece que faltan dos filas del principio, y esas dos filas no son datos. El
pie de la tabla lo explica ahora en una frase.

**3. El resultado decía «Inventario importado» con «Se crearon 0 equipos».** Eso parece un
fallo: un 0 en «creados» se lee como «no se hizo nada», cuando lo que pasó es lo normal en
una reimportación —los 875 equipos ya estaban y se refrescaron sus datos—. Ahora el titular
lleva lo que pasó y por qué:

- «Se actualizaron 875 equipos que ya estaban», con la explicación de que **actualizar no
  es duplicar**;
- o «Se crearon 39 equipos nuevos», según el caso.

**4. El backend creaba zonas, oficinas y conjuntos y no se decía.** `confirmar` devuelve
`zonas_creadas`, `oficinas_creadas` y `conjuntos_creados`, y la pantalla no los mostraba:
si el archivo traía una zona que no existía, se creaba en silencio. Ahora se dice, con
singular y plural correctos: «Además se creó 1 zona nueva, 4 oficinas nuevas y 12 conjuntos
nuevos».

**5. Los errores del resultado eran una lista plana de hasta 200 renglones.** Se agrupan
por texto igual que los avisos, cada uno con cuántas veces ocurrió, y se añade lo que no
decía ninguno: **qué hacer con ellos** — que el resto del archivo sí entró, que al volver a
subirlo los que ya entraron se actualizan y no se duplican.

**6. El bloque de personas era una pila de desplegables idénticos.** Ahora dice cuántos
quedan de entrada («Quedan 3 personas por decidir»), la lista tiene altura fija con su
propio desplazamiento —así no empuja los botones de deshacer y de importar otro archivo
fuera de la pantalla— y cada línea se lee «oficina · persona · N equipos». Cuando el
nombre de la persona es el mismo que el de la oficina, antes ponía
«ADMINISTRACION · ADMINISTRACION · 1 equipos»: dos veces el mismo dato y en plural
incorrecto. Ahora pone «ADMINISTRACION · 1 equipo».

**Dos detalles que aparecieron al probar:**

- Escribí `**texto**` dentro de un `<p>` de JSX esperando que se pusiera en negrita. En
  JSX los asteriscos salen **tal cual**: se leían «equipo \*\*ya estaba en el
  inventario\*\*» en pantalla. Corregido a `<strong>`.
- El aviso flotante salía **verde con un visto bueno** al lado de un bloque rojo de fallos.
  Ahora, si hubo errores, sale en amarillo.

**Verificado con 875 filas simuladas en el navegador** (sin tocar la base de datos: la
respuesta del servidor se intercepta, no se aplica ninguna importación): página 1 de 9,
«Última» lleva a 801–875 con las 75 últimas, cambiar de hoja vuelve a la 1, titular con
los dos números, «1 zona nueva, 4 oficinas nuevas y 12 conjuntos nuevos», «1 equipo» en
singular, «Confirmar 3 personas», cero asteriscos sueltos y cero «1 equipos». Sin errores de
consola ni peticiones fallidas.
81 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores (6 warnings preexistentes),
`verify:clases` en verde.

### BC1-BC5 — Importar: volver atrás, y seguir sin vincular a los responsables uno por uno

**Estado: COMPLETADA**

Petición del usuario: un botón al final para volver atrás, y uno para avanzar sin confirmar
a las personas del Excel, de forma global y no una por una.

**1. Faltaba la salida evidente del bloque de responsables.** Solo había dos caminos:
elegir cada nombre de una lista —con el Excel municipal salen decenas— o cerrar la página
y perder el resultado. Se añadieron dos acciones:

- **Vincular todas como nuevas**: resuelve de golpe los nombres que tienen más de una
  coincidencia posible, que son los únicos que salen en blanco. Medido con 6 casos: 4 ya
  venían marcados y 2 en blanco; tras el botón, los 6 quedan resueltos y el botón de
  confirmar se enciende.
- **Continuar sin vincular**: deja los equipos como estaban, y **dice dónde resolverlo más
  tarde** —Equipos → Inventario, con el filtro «El responsable no tiene cuenta»—, porque si
  el bloque simplemente desaparece parece que el paso se resolvió solo.

Las tres acciones están **encima** de la lista, no debajo: la lista ocupa casi una pantalla
y quien solo quería continuar tenía que bajar hasta el final para encontrar el botón.

**2. «Volver a revisar el archivo».** Al final del resultado, junto a «Deshacer» y a
«Importar otro archivo». Vuelve al paso 2 con la lista y los avisos a mano, sin tener que
subir el archivo otra vez. El botón dice que **no deshace nada**: los datos ya están en el
inventario.

**3. Un fallo que metí yo: volver atrás era una trampa.** Al activar el Stepper para poder
retroceder, el paso «Resultado» **quedaba deshabilitado**, porque el componente marca como
hechos solo los pasos que están por detrás del actual. Es decir: se podía volver al
archivo y no se podía volver al resultado. Se añadió la prop `alcanzado` al `Stepper`: un
paso cuenta como hecho si está por detrás **o** si se sabe que se llegó a él. Ahora
retroceder y volver a avanzar funciona en los dos sentidos.

El campo `hecho` que ya tenía el tipo `Paso` estaba declarado y **nunca se usó**; la
propiedad nueva deja claro cuál de las dos manda.

**4. Cuando no se puede deshacer, se dice por qué.** El botón «Deshacer» solo aparece si la
importación se puede deshacer, y en el caso del usuario —875 actualizaciones— no aparece.
Pero el silencio no explica nada: ahora hay una línea que dice que no se puede deshacer
porque la importación actualizó equipos que ya existían, y que para corregir algo se abre
la ficha del equipo.

**5. La nota de personas ya no dice «se crearon 0 perfiles».** Con el Excel municipal casi
todo se empareja con cuentas que ya existen, así que se creaban cero personas y la frase
quedaba con un número muerto. Ahora el texto se arma con lo que pasó: o «se crearon N
perfiles nuevos sin correo ni contraseña», o «no hizo falta crear ninguna persona».

**Dos cosas que parecían fallos y no lo eran — corregí mi propia afirmación:**

- Escribí que «el botón de confirmar permanece apagado hasta que eliges todos». Al probarlo
  con 6 casos reales vi que **los que no tienen ninguna coincidencia ya venían
  preseleccionados como «crear»**: solo quedan en blanco los que tienen más de una
  posibilidad. La afirmación era demasiado amplia; la nota y el texto del botón ahora dicen
  exactamente eso.
- La nota salió sin números y el aviso flotante con «undefined equipos actualizados». Al
  revisar el backend, `confirmar_responsables_excel` devuelve bien
  `{personas_creadas, equipos_vinculados}`: **era mi script de prueba**, que registraba una
  ruta genérica `*/confirmar` después de la específica y se comía la respuesta de personas
  (Playwright prueba las rutas en orden inverso al registro). Corregido el script y
  comprobado: «Se crearon 4 perfiles nuevos…» y ningún `undefined`.

**Verificado en el navegador con 875 filas simuladas y respuestas interceptadas** (no llega
nada a la base de datos): 4 desplegables ya marcados y 2 en blanco con el botón apagado;
«Vincular todas como nuevas» deja los 6 en «crear» y enciende el botón; la confirmación
muestra los números; «Continuar sin vincular» deja 0 desplegables y el aviso de dónde
resolverlo; «Volver a revisar el archivo» lleva al paso 2 con la tabla y el paginador
«Página 1 de 9»; y el paso «Resultado» del Stepper vuelve a ser pulsable. Sin errores de
consola ni peticiones fallidas.
81 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores (6 warnings preexistentes),
`verify:clases` en verde.

### BD1-BD6 — Tres botones reducidos a dos, y nada se crea sin que alguien lo pida

**Estado: COMPLETADA**

Petición del usuario: resumir los tres botones del bloque de responsables a dos con recuadro,
porque «Confirmar 263 personas» y «Vincular todas como nuevas» hacen lo mismo; poder seguir
cuando has cambiado una coincidencia a mano; y saber qué es «crear perfil sin credenciales» y
qué pasa si no se quiere crear ninguno.

**1. Eran tres botones y dos hacían lo mismo.** Con todo marcado en «crear» —que era lo que
pasaba—, «Confirmar 263 personas» y «Vincular todas como nuevas» acababan en el mismo sitio.
Quedan **dos, con recuadro**, y cada uno se distingue por lo que **no** hace:

| Botón | Qué hace | Qué no hace |
| --- | --- | --- |
| **Continuar sin vincular** | nada | no crea ninguna cuenta |
| **Confirmar y crear N perfiles nuevos** | respeta lo elegido a mano y crea el resto | no pisa ninguna decisión tuya |

**2. El botón global borraba las coincidencias que habías elegido a mano.** Este fue el
fallo real que reportó el usuario: elegías «es esta persona» en cuatro nombres, pulsabas el
botón para resolver los que quedaban en blanco, y los cuatro volvían a «crear». Ahora solo
rellena los que siguen **vacíos**.

Comprobado mirando lo que se manda al backend: se prepararon 22 casos (20 sin coincidencia,
1 con coincidencia exacta, 1 con dos parecidas), se escogió a mano una de las parecidas y al
confirmar se envió `{"crear": 20, "u1": 1, "u2": 1}` — la elegida a mano sobrevivió.

**3. Ya nada viene preseleccionado como «crear».** Antes, todo nombre que no estuviera en
ninguna cuenta salía marcado como «crear perfil»: con el Excel municipal eso eran **263
personas decididas de antemano**, y el botón de confirmar solo formalizaba una decisión ya
tomada. Medido: de 22 casos, **0 preseleccionados como «crear»** (antes 21 de 23).

Lo único que se deja marcado son las **coincidencias exactas**, que no crean nada: solo
apuntan a una cuenta que ya existe.

**4. Se explica qué es «crear un perfil sin credenciales»**, que es lo que hacía que el botón
diera miedo sin motivo claro: añade a la persona a Usuarios con su nombre y su oficina para
que sus equipos dejen de estar sin dueño, pero **no puede entrar al sistema** —sin correo ni
contraseña— y solo sirve como responsable hasta que alguien le asigne una cuenta.

**5. El bloque cabe en una pantalla.** Antes era una pila de 263 desplegables que empujaba
los botones fuera de la vista. Ahora:

- una línea con el resumen: «El archivo nombra a 22 personas en 42 equipos. 2 se parecen a
  alguien que ya tiene cuenta. 20 no aparecen en ninguna cuenta»;
- el recuadro de qué significa crear un perfil;
- **«Revisar uno por uno (22)»** plegado, que solo se abre si quieres ajustar algo;
- los dos botones con recuadro debajo, que son la decisión y la lista es el detalle.

**6. La explicación de por qué la lista empieza en la fila 3 estaba escondida.** Estaba en
el pie de una tabla de veinte columnas, al final de la pantalla. Es lo primero que se ve al
mirar y lo primero que se pregunta —se preguntó dos veces—, así que ahora está **junto al
selector de hoja**, antes de la tabla.

**Verificado en el navegador con 875 filas y respuestas interceptadas** (nada llega a la base
de datos): la explicación del número 3 visible sin buscar, resumen con los tres números,
recuadro de qué es crear un perfil, lista plegada, dos botones con recuadro distinguidos por
color, 0 preseleccionados como «crear», y la coincidencia elegida a mano respetada al
confirmar. Sin errores de consola ni peticiones fallidas.
81 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores (6 warnings preexistentes),
`verify:clases` en verde.

### BE1-BE7 — Inventario anual: se llega a los 875 equipos y no se verifica lo que ya no sirve

**Estado: COMPLETADA**

Revisión completa de Inventario anual: flujo, secciones, estado real, errores y diseño.
Todo lo que cambia datos se probó con respuestas interceptadas; lo que solo lee se probó
contra la base real.

**El estado real que había:** una campaña, «OTIC», **cerrada** el 8 de octubre de 2026, con
**875 equipos y ninguno verificado**. Los 875 siguen en «pendiente».

**1. Al entrar, la pantalla no enseñaba nada.** Se elegía automáticamente la campaña
**abierta**; como la única estaba cerrada, `seleccionada` quedaba nula y no se pintaban ni
los indicadores ni la lista: solo el chip y el histórico. Sin una palabra explicando por qué,
parecía una pantalla rota. Ahora, si no hay ninguna abierta, se elige la primera de la lista
y se ve de entrada que está cerrada y por eso no se puede seguir.

**2. De 875 equipos se veían 25, sin paginador.** `por_pagina: 25` y ningún control para
moverse: la campaña entera era inalcanzable y el trabajo de sala se paraba en el equipo 26.
Ahora hay paginación de 25 con Primera, Anterior, Siguiente y Última:
«Equipos 1–25 de 875 · 1 / 35», y «Última» lleva a 851–875.

**3. Se podía verificar en una campaña cerrada, y el trabajo se perdía en silencio.** El
backend acepta el cambio y lo guarda, pero `cerrar` **ya se había ejecutado**: nadie volvería
a volcar esos cambios al inventario. Los indicadores subirían a «875 verificados» en una
campaña archivada. Ahora los botones no se pintan —solo la palabra «Verificación cerrada»— y
arriba hay un aviso que explica el porqué.

**4. El diálogo de cierre prometía marcar los no localizados y no lo hace.** Decía «los
equipos que no se localizaron quedarán marcados para seguimiento», pero `cerrar` solo marca
los que alguien marcó como ausente: **los que nunca se llegaron a mirar no se marcan**,
porque no se puede afirmar que no estén allí si nadie los buscó. Con esta campaña, 875
pendientes y cero ausentes: se cerró y los 875 se quedaron «pendiente» para siempre.

El diálogo ahora enseña **Verificados 300 · Sin verificar 575** y dice las dos cosas: los
ausentes pasan a «Dado de baja», y los pendientes se quedan como están.

**5. El buscador no encontraba por oficina ni por zona.** Solo miraba el nombre y el código
del equipo. En una sala lo que se sabe es **dónde** está el equipo: buscando «PISCINA» salía
cero resultados aunque la zona PISCINA MUNICIPAL tuviera 36 equipos en la campaña. Ahora
busca por nombre, código, **oficina, zona y responsable**. Medido: «PISCINA» → 36 equipos;
COMPLEJO por zona → 111; DEMUNA → 18; una oficina concreta → 9.

**6. Un asterisco rompía la búsqueda.** El texto tecleado se usaba tal cual como expresión
regular: buscar `a*b` dejaba la regex sin cerrar. Ahora se escapa con `re.escape`, el mismo
criterio que ya se aplicaba en la búsqueda del inventario. Comprobado: `a*b` devuelve el
estado vacío y **no hay error 500**.

**7. Filtros que el backend ya tenía y no se ofrecían.** `zona_id`, `oficina_id` y `texto`
existían en `campana_service.items` y no había ningún control para usarlos. Ahora hay buscador
por equipo, selector de zona (7) y de oficina (59), y todos vuelven a la página 1 al cambiar.
El estado vacío distingue «no hay equipos» de «el filtro no deja pasar nada», con su botón
**Quitar el filtro**.

**8. El indicador «Equipos en la campaña» podía marcar el número equivocado.** Usaba
`elegida?.total_items ?? seleccionada.por_verificar ?? 0`: al llegar sin pulsar ningún chip,
`elegida` era nula y caía al **pendiente**, no al total. Con 500 por verificar de 875 habría
dicho «Equipos en la campaña: 500». El total sale ahora de un solo sitio, y el backend devuelve
`total_items` también en `campana_activa`, que faltaba.

**9. Detalle menor:** `total_items` no venía en `campana_activa`, `lista` se recreaba en cada
render y hacía que el efecto de selección se disparara sin parar (ESLint lo señaló), y el botón
«Cerrar campaña» aparecía en campañas ya cerradas —el backend respondía «La campaña ya está
cerrada»—, así que solo servía para producir un error.

**Prueba nueva** `test_la_campana_se_busca_por_oficina_y_no_revienta_con_un_asterisco`:
comprueba que se encuentra por zona, por oficina y por código, y que un asterisco se busca
literal sin romper nada.

**Verificado en el navegador:** entrada con indicadores y lista sin tocar nada, paginador a la
última página (851–875), búsqueda por zona, por oficina y por código, estado vacío con su
botón, diálogo de cierre con los números delante, y diálogo de nueva campaña. Sin errores de
consola ni peticiones fallidas.
**82 pruebas backend en verde** (eran 81), `tsc` 0 errores, ESLint 0 errores (6 warnings
preexistentes), `verify:clases` en verde.

### BF1-BF5 — Importar: se ve lo que se creó, y la decisión son dos casillas y un «Continuar»

**Estado: COMPLETADA**

Petición del usuario: un indicador de que se ha continuado con el usuario creado, que el registro
aparezca en la pantalla final, cambiar los dos botones por **casillas excluyentes** con un solo
botón «Continuar», y un resumen de qué pasó, con qué personas, sus zonas y qué datos podrían
haber quedado mal.

**1. No había forma de confirmar nada.** El backend devolvía solo dos contadores
(`personas_creadas`, `equipos_vinculados`) y la pantalla, tras confirmar, cambiaba el bloque por
«No quedan responsables del Excel sin vincular». Se sabía **cuántas** personas se habían
creado, pero no **quiénes**, ni en qué zona, ni si lo hecho era lo que se quería. Con el
archivo municipal son cientos: un número no es un comprobante.

`confirmar_responsables_excel` ahora devuelve un **`detalle` por persona**: nombre del Excel,
nombre asignado, si se creó o se vinculó, oficina, zona, tipo de coincidencia con su
similitud, cuántos equipos y si el nombre parece el de la oficina.

**2. Los dos botones pasan a ser dos casillas excluyentes y un botón «Continuar».** Se
mantiene la función de código de cada uno, pero la decisión se toma marcando y el botón solo
aplica:

| Casilla | Qué hace al pulsar «Continuar» |
| --- | --- |
| **Crear un perfil para las que faltan** | crea los que faltan respetando lo elegido a mano |
| **No vincular a nadie de momento** | no crea ninguna cuenta y no vincula a nadie |
| *ninguna marcada* | avanza solo con lo que se haya elegido en la lista |

La tercera es la que pedía el usuario: si decides hacerlo a mano y no marcas nada, no se crea
**ninguna** cuenta por sorpresa. Si no hay nada elegido, es como la segunda.

La casilla marcada **inhabilita la otra**, que es lo que se pidió para evitar tener las dos.
Esa exclusividad tiene un coste —no se puede pasar de una a otra sin desmarcar—, así que la
casilla inhabilitada lo dice: *«Desmarca la de arriba para poder elegir esta»*. Sin esa frase
parece un fallo de la pantalla.

**3. La pantalla final muestra qué se hizo con cada persona.** Un bloque «Qué se hizo con cada
persona» con la lista completa: nombre, si se creó o a quién se vinculó, **zona · oficina ·
nº de equipos**, y una nota de dónde corregirlo.

**4. Y resalta lo que podría haber quedado mal.** Tres casos, ninguno un error comprobado:
se señalan para que una mirada rápida decida:

- **el nombre del Excel es el de la oficina** («ADMINISTRACION · ADMINISTRACION»): en estos
  libros la columna de responsable a veces trae el nombre del área y no el de alguien;
- **coincidencia parecida**: «Se vinculó a “Julio Ramírez” porque se le parece (78 %)». Es lo
  más fácil de equivocar sin enterarse, y ahora se dice con el porcentaje;
- **perfil creado sin cuenta**: no está mal, pero conviene saberlo.

Las coincidencias **exactas** no se señalan: no hay nada que revisar.

**Prueba nueva** en `test_personas_excel.py`: comprueba el detalle de las dos personas —la
vinculada con coincidencia exacta y la creada—, que la zona y la oficina llegan, que los
equipos están contados y que `nombre_parece_oficina` es `False` en ambos casos. Antes la
prueba comparaba el diccionario entero contra `{"personas_creadas": 1, "equipos_vinculados":
3}`, lo que además ataba la prueba a la forma de la respuesta.

**Verificado en el navegador** con respuestas interceptadas: las dos casillas nacen vacías,
marcar una marca la otra como deshabilitada en los dos sentidos, el texto inferior cambia
según lo marcado («se vincularán solo las 1 persona que hayas elegido y no se creará ninguna
cuenta nueva»), y la pantalla final muestra el resumen, los tres casos señalados con su motivo
y la lista completa con zonas. Sin errores de consola ni peticiones fallidas.
82 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores (6 warnings preexistentes),
`verify:clases` en verde.

### BG1-BG5 — Inventario anual: calendario, alcance que se entiende, filtros acotados y marcas que se pueden deshacer

**Estado: COMPLETADA**

Cinco cosas del usuario: no había calendario al crear la campaña, no se entendía qué
significaba «solo algunas zonas / solo algunas oficinas», el diseño del diálogo era pésimo,
el filtro ofrecía zonas que no estaban en la campaña, y **una vez marcado un equipo no se
podía volver a «Pendiente»**.

**1. No había calendario, y el año iba por separado.** Las fechas se mandaban fijas —del 1 de
enero al 31 de diciembre del año escrito— y no había dónde tocarlas, aunque el backend guarda
`fecha_inicio` y `fecha_fin` y el histórico los muestra. Ahora hay dos campos de fecha con
calendario, y **el campo «Año» desaparece**: sale del año de la fecha de inicio.

Quitarlo no es cosmético: con los dos campos se podía escribir año 2026 y fechas de 2025 sin
que nada lo impidiera, y la campaña se archivaba bajo un año que no era el suyo. Ahora no se
pueden contradecir.

**2. «Solo algunas zonas» no significaba nada, ahora significa un número.** Eran tres opciones
en un desplegable, sin explicación, y el efecto —cuántas máquinas hay que ir a mirar en la
sala— solo se descubría **después de crearla**, cuando salía el error de alcance vacío.

Ahora cada opción explica qué incluye y hay un endpoint nuevo (`POST /campanas/previa`, solo
lectura) que cuenta los equipos del alcance elegido: el pie del diálogo dice **«Esta campaña
tendrá 877 equipos»** y se actualiza al marcar y desmarcar zonas. Si el alcance está vacío,
lo avisa antes de escribir nada.

**3. El diálogo era demasiado estrecho.** Era de 448 px (`sm`), y el selector de zonas u
oficinas se metía en un hueco pequeño: había que desplazarse para llegar al botón. Ahora es
de 896 px (`lg`) con dos columnas —datos a la izquierda, alcance a la derecha—.

**4. El selector de zonas y oficinas se rehace.** Era un `max-h-48` con una casilla por fila,
sin buscador. Con 59 oficinas había que recorrer un scroll corto para encontrar una. Ahora
tiene buscador, botones «Todas» y «Ninguna», y el recuento «Zonas — 7 de 7 marcadas».

**5. El filtro ofrecía zonas que no estaban en la campaña.** El origen estaba en el backend:
`campana_service.listar()` **excluía** `zona_ids` y `oficina_ids` de la proyección, así que la
pantalla no tenía forma de saber el alcance. Al filtrar una campaña creada con dos zonas
salían las siete, y elegir una tercera devolvía cero resultados sin explicar por qué.

Ahora la lista sale del alcance guardado, y el panel lo dice: *«Esta campaña solo cubre 1
zona: los filtros solo ofrecen lo que está dentro»*. Medido con una campaña de una zona:
**1 zona y 1 oficina** ofrecidas, antes 7 y 59.

**6. Las marcas eran irreversibles.** Solo había dos botones, «Encontrado» y «Ausente», y los
dos llevaban a un estado definitivo. Marcar por error un equipo como ausente no tenía vuelta
atrás: la fila se quedaba así hasta que la campaña se cerrara. El backend ya aceptaba
`pendiente`; solo faltaba el botón.

Ahora una fila marcada ofrece **«Pendiente»** primero, para deshacer. En una sala, donde se va
marcando con el dedo, uno se equivoca; eso tiene que ser reversible.

**7. Se explica qué es una campaña al abrir el diálogo:** *«Se crea una copia congelada del
inventario de hoy, del alcance que elijas. Esa copia es la lista que habrá que verificar
máquina por máquina en la sala; el inventario sigue como está hasta que cierres la campaña.»*
Es lo que responde a «¿por qué me importa el inventario que ya tengo?» —porque una
verificación física necesita una foto del momento en que empieza—.

**Verificado en el navegador** con una campaña de alcance acotado simulada: filtros con 1
zona y 1 oficina, panel explicando el alcance, botón «Pendiente» en las filas ya marcadas y
no en las pendientes, diálogo de 896×485 con los dos calendarios, sin campo «Año», con las
tres opciones de alcance explicadas, buscador de zonas, «Todas» / «Ninguna» y el conteo en
vivo. Sin errores de consola ni peticiones fallidas.
82 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores (6 warnings preexistentes),
`verify:clases` en verde.

### BH1-BH4 — Tablas que ocupan el 100 %, y la barra de Importar al alcance de la vista

**Estado: COMPLETADA**

Dos peticiones: que la tabla del inventario se estire para llenar el espacio cuando se ocultan
columnas, y una barra horizontal en Importar que permita moverse de izquierda a derecha sin
tener que bajar hasta el final.

**1. La tabla no ocupaba el hueco, y al ocultar columnas el hueco era enorme.** Medido en
Inventario antes del arreglo:

| | contenedor | tabla | hueco |
| --- | --- | --- | --- |
| Todas las columnas visibles | 1.181 px | 1.028 px | **153 px** |
| Con columnas ocultas | 1.181 px | 67 px | **1.114 px** |

La causa estaba en `DataTable`: `w-full` estaba **dentro** de `conAnchosFijos && 'table-fixed
w-full min-w-[1110px]'`, y esa condición exige que **todas** las columnas visibles declaren
`ancho`. La columna «Menú» de Equipos no lo declaraba, así que la tabla entera pasaba a
reparto automático y se encogía al contenido: medido, la clase real era
`border-collapse text-sm text-foreground`, sin `w-full` ni `table-fixed`.

Arreglo en las dos partes: `w-full` va **siempre**, y «Menú» declara `meta: { ancho:
'68px' }` —el botón cabe de sobra— para que la vista vuelva al reparto fijo.

Después: **2 px** de hueco en los dos casos (el borde), con las columnas repartiéndose
proporcionalmente, y `table-fixed` activo con columnas ocultas.

**2. La barra horizontal de Importar quedaba al final de las 100 filas.** El contenedor de
la previsualización solo tenía desplazamiento horizontal, así que para usarla había que bajar
hasta el final de la lista —justo lo contrario de lo que se pedía—.

Ahora el contenedor tiene **altura acotada** (`min(60vh, 620px)`) y se desplaza dentro en los
dos ejes: las dos barras están siempre a la vista sin importar cuántas filas haya. De rebote,
el encabezado, que ya era `sticky`, acompaña al desplazamiento vertical: al ir por la fila 700
se siguen viendo los nombres de las columnas.

Medido: recuadro de 570 px que termina en el 794 de una ventana de 950 — **a la vista sin
desplazar la página**—, desborde horizontal de 1.619 px que se recorre con la rueda
(`scrollLeft` 0 → 600) y también arrastrando, y el encabezado sigue fijo arriba.

**3. Un cruce de capas que tapaba el encabezado.** Al acotar la altura apareció un defecto: la
celda fija de la primera columna («Se creará») se pintaba **encima** del encabezado, y la
columna parecía llamarse «Se creará» en vez de «Acción». El `<thead>` y la `<td>` fija tenían
el mismo `z`, así que ganaba la que llegaba después en el documento. Se separaron las capas:
`thead` a `z-20` y la celda de cabecera a `z-30`, por encima de las `z-10` de los datos.

**Verificado en el navegador:** hueco de la tabla del inventario con todas las columnas y con
varias ocultas (2 px en ambos, antes 153 y 1.114), barra horizontal de Importar a la vista
sin bajar, desplazamiento en los dos ejes con la rueda y con arrastre, y encabezado legible y
fijo mientras se baja. Sin errores de consola ni peticiones fallidas.
82 pruebas backend en verde, `tsc` 0 errores, ESLint 0 errores (6 warnings preexistentes),
`verify:clases` en verde.

---

## BI — Inventario anual: que sirva para lo que se le pide (descubrir lo que no está registrado)

**Lo que se reportó:** el inventario anual «está todo vacío», no hace la función de registrar un
inventario, no cumple su función ni una sola, ni siquiera registrar un inventario nuevo para
mantenerlo registrado, ni siquiera el de elegir por zonas. Que el 2026 es el que hay ahora, y que
este sirve para comprobar si hay datos nuevos en un registro nuevo y **mantener el 2026
registrado**.

**Lo que había.** El backend tenía la función, documentada como _«modo actualizar: compara el Excel
del año nuevo contra el inventario actual»_, con sus rutas `POST /campanas/{id}/excel` y
`/excel/aceptar`. La pantalla **no la mencionaba en ningún sitio**. Y el recorrido estaba roto en las
tres piezas que importaban:

| Pieza | Qué hacía en realidad |
|---|---|
| `importar_excel` | comparaba y detectaba los equipos nuevos — funcionaba |
| `aceptar_cambios` | **los tiraba en silencio**: buscaba el item por id, no lo encontraba (los nuevos no eran items) y hacía `continue` |
| `cerrar` | **no los creaba**: no existía rama para un equipo sin `activo_id` |

Se podían **detectar** equipos nuevos y no se podían **registrar**. `nuevos_creados` se inicializaba
a cero y nunca se incrementaba: la firma de una función sin terminar.

### Lo que se hizo

**1. El backend registra los equipos nuevos de principio a fin.**
- `importar_excel` guarda cada equipo nuevo como item de la campaña con `origen: excel_nuevo` y
  `activo_id: null`. Nace `pendiente` a propósito: hasta que alguien lo acepta, no cuenta como
  verificado ni se crea nada.
- `aceptar_cambios` los marca (`estado_item: nuevo`) y cuenta en `nuevos_creados`.
- `cerrar` los **crea en el inventario** con `_registrar_equipo_nuevo`: la zona sale del nombre de la
  hoja —una hoja, una zona, la convención de la importación— y la oficina del nombre de la columna
  ÁREA; si la oficina no existe se crea, como hace la importación, para que un área nueva no bloquee
  la campaña entera. Un equipo sin zona o sin oficina **no rompe el cierre**: se cuenta en
  `nuevos_fallidos` con su motivo.
- Devuelve `nuevos_registrados` y `nuevos_fallidos`, y ambos quedan en el histórico y en la auditoría.

**2. La pantalla sube el Excel y deja decidir.** Panel «Comparar con el inventario»: un botón de
subir, los cuatro grupos con número (**No registrados** / **Con cambios** / **Iguales** / **No
aparecen**), la lista de equipos nuevos con código, tipo, marca, modelo, oficina y hoja —lo que se
mira de cerca en la sala para decidir si el equipo es ese—, y botones «Marcar los N» y «Descartar».
El botón dice **Marcar**, no Crear: aceptar no crea nada todavía, lo crea el cierre.

**3. El rechazo existe de verdad.** `estados_rechazados` estaba en el servicio pero **no en el
esquema ni en la ruta**: se aceptaba todo o nada. Ahora la casilla lo declara y el rechazo deja el
equipo pendiente de verificar a mano, sin borrarlo y sin crearlo.

**4. Los indicadores ya no mezclan lo verificado con lo descubierto.** `verificados` contaba «todo
lo que no estaba pendiente», así que marcar dos equipos nuevos ponía «Verificados 2» y 67 % de
progreso sin que nadie hubiera buscado nada: esos equipos no estaban en ninguna sala. Ahora
`verificados` son los equipos **registrados** que alguien buscó; los nuevos van en
`nuevos_aceptados` / `nuevos_sin_decidir` y quedan fuera del numerador y del denominador. El diálogo
de cierre dice cuántos se van a registrar y cuántos se quedan sin decidir.

**5. Solo `cerrada` está cerrada.** Este era el motivo de que la pantalla «no cumpliera su función»:
`verificacion` es el estado que el backend pone **sola** al marcar el primer equipo, y la pantalla
trataba cualquier estado distinto de `abierta` como cerrado. Marcar un equipo dejaba la campaña
entera inservible —sin botones de verificar, sin cerrar, sin subir el Excel— y salía el aviso de que
«verificar ahora no cambiaría nada», que era falso. En el municipio había **dos campañas de 877
equipos bloqueadas** por tener un único equipo confirmado.

**6. `campana_activa` elige por criterio.** Era un `find_one` sin orden sobre
`{abierta, verificacion}`: salía la que tocara por orden natural, y abría una campaña ya empezada en
vez de la única `abierta`. Ahora primero la `abierta` más reciente, si no la `verificacion` más
reciente.

**7. El texto de la página.** Decía _«Campañas de verificación física: confirmar que cada equipo está
donde dice estar»_, o sea, la mitad de la función. Ahora dice lo que hace: subir el Excel de la sala,
descubrir lo que no está registrado y registrarlo al cerrar.

### Cuatro fallos que solo aparecieron midiendo en el navegador

1. **500 al subir el archivo.** El índice único `uq_item_campana_activo` sobre
   `(campana_id, activo_id)` trata `null` **como un valor**, así que todos los equipos nuevos
   compartían clave y **el segundo reventaba la subida entera** con `E11000 duplicate key`. La
   función solo registraría un equipo nuevo por campaña. La primera prueba de backend tenía uno solo
   y pasaba de largo: el fallo solo aparece con dos. Corregido con índice **parcial** (migración
   `017`) y con una prueba de tres equipos nuevos.
2. **Recargar el mismo archivo cambiaba el resultado.** El item se emparejaba y se comparaba contra
   una instantánea vacía —un equipo nuevo no tiene datos previos—, así que salía como «con cambios»:
   la pantalla decía que un equipo registrado había cambiado de datos, siendo que no estaba
   registrado. Ahora sigue saliendo como nuevo, y **refresca** tipo, nombre, código y oficina con los
   del archivo.
3. **El tipo salía de la columna equivocada.** Se leía `dispositivo` porque `tipo` no está en
   `CAMPOS_BASE` ni en `mapeo`: el equipo se iba a registrar con «PC NUEVA DE LA SALA» como tipo en
   vez de «CPU». El tipo sale ahora de la columna mapeada como `tipo_equipo`.
4. **Los resultados de «nuevo» no traían código ni tipo**, a diferencia de los otros grupos: ninguna
   pantalla podía mostrarlos sin desarmar el objeto a mano. La forma de la respuesta es ahora la misma
   en los cuatro grupos.

### Verificación

Recorrido completo medido en el navegador contra una **base aislada** (`mesa_ayuda_ui_prueba`, un
API aparte en el puerto 8111 con su propia base), **sin tocar el inventario municipal**: subir el
Excel de una sala → detección de 2 equipos nuevos y 1 ausente → listado con código, tipo y marca →
marcar → el diálogo de cierre dice «Se registrarán 2 equipos nuevos» → confirmar el cierre → los dos
equipos aparecen en Inventario con su código buscados uno a uno, en la oficina y zona de su hoja.

En la instalación real, con los datos del municipio: al abrir sale la campaña `abierta`, el panel de
comparación está visible y el botón de subir disponible; una campaña en `verificacion` también es
usable (botones de encontrado, cerrar campaña y panel visibles, sin el aviso falso). Sin errores de
consola ni peticiones fallidas.

Base municipal comprobada después de aplicar la migración 017: las cinco campañas siguen igual
(OTIC 2026 cerrada con 875 pendientes) y el índice ya es parcial. No se ha creado ni modificado
ningún equipo.

**Pruebas backend: 87 en verde** (`test_inventario_anual.py` con 5: detectar-aceptar-registrar,
varios nuevos a la vez, rechazo no registra, recargar da el mismo resultado, una campaña en
verificación sigue admitiendo nuevos). `tsc` 0 errores, ESLint 0 errores (6 warnings preexistentes),
`verify:clases` en verde. Migración `017` aplicada.
---

## BJ — Campaña vacía, descargar el inventario y eliminar campañas

**Lo que se reportó:** dos cosas.

1. *«aún me sigue dejando con los datos que ya subí cuando creo uno nuevo, es decir con los mismos
   datos del inventario anterior»*. Al crear una campaña aparecían los 877 equipos del inventario.
2. *«elimíname todo lo que creé en esa pestaña que eran simples pruebas»*, y después: *«inclúyele un
   botón de descarga con el formato que tenemos de Excel… si está registrado 2026 y 2027 los dos se
   deberían descargar»*.

### Lo borrado (con aprobación explícita)

Se leyeron las seis campañas que había y se borraron cinco, conservando **OTIC** (INV-2026-009, la del
7 de octubre): `Inventario fisico 2026` (cerrada), `Inventario 2027`, `prueba`, `Inventario Fisico
2026` y `hgg2056`. En transacción: **5 campañas, 4130 equipos de lista y 1 versión del histórico**.
Después: 1 campaña, 875 equipos de lista, 1 versión, **0 huérfanos** y el inventario **intacto en
877 equipos**. Ninguna de las seis tenía un Excel subido ni un solo equipo creado
(`origen: excel_nuevo` = 0 en todo el municipio), así que no había nada que revertir en `activos`.

### 1. La campaña nace vacía

Crear una campaña ya no congela una instantánea del inventario: se crea con cero equipos y se llena al
subir el Excel de la sala. Antes salía una lista idéntica a la del inventario sin que nadie hubiera
subido nada, y eso era justo lo que hacía imposible «ver qué falta descubrir».

Lo que cambia con ese ajuste:

* Desaparece el error «no hay equipos en el alcance elegido». Que el inventario esté vacío ya no
  impide crear una campaña. El alcance se sigue validando y guardando.
* Los equipos de la campaña son los que salen del archivo, más los registrados del alcance que **no**
  aparecen en él (antes ese grupo salía de recorrer los items, y con la campaña vacía no habría
  detectado ninguno).
* El emparejamiento de cada fila se hace contra **`activos`**. Si solo se miraran los items de la
  campaña —vacíos al empezar— las 877 filas saldrían como equipo nuevo.
* Se arregló un fallo que solo apareció al medir: en la **segunda** subida del mismo archivo, cada
  equipo ausente se reportaba dos veces (una por el bucle de los registrados del alcance y otra por el
  de los items que el archivo ya no mencionaba). El resumen crecía en cada recarga.

**Efecto secundario que conviene saber:** una campaña ya no puede «borrarse» cerrándola sin querer.
Al no haber items, cerrar una campaña recién creada no aplica nada y no marca nada como dado de
baja —que era lo que pasaba con la campaña «prueba» de 622 equipos que quedó cerrada por accidente—.

### 2. La comparación no sobrevive a cambiar de campaña

El resultado de la última subida se quedaba pegado al cambiar de chip o al crear una campaña: seguían
viéndose los equipos nuevos, modificados y ausentes **del archivo de la campaña anterior**, con su
nombre arriba. Ahora comparación, archivo y errores se borran al cambiar de campaña.

### 3. Descargar el inventario

* **`GET /activos/excel`** — el inventario registrado en el Excel del municipio, **una hoja por zona**,
  con las 16 columnas de la plantilla oficial. Acepta los mismos filtros que el listado (zona, oficina,
  tipo, estado, búsqueda, solo faltantes): lo que descargas es lo que estás viendo, no «todo» por
  sorpresa. Botón **Descargar Excel** en Equipos, junto a «Registrar equipo».
* **`GET /campanas/versiones/{id}/excel`** — el inventario de un año cerrado, mismo formato. Botón
  **Descargar Excel** en cada año del histórico, así que 2026 y 2027 se descargan los dos por separado.

Medido sobre el inventario real: **5 hojas** (COMPLEJO 111, MERCADO 142, PALACIO 511, PISCINA
MUNICIPAL 36, SEGURIDAD CIUDADANA 77), **877 equipos**, 16 columnas de la plantilla, sin nombres de
hoja repetidos ni caracteres que Excel rechace. Filtrando por zona el archivo se llama
`inventario-complejo.xlsx`, con lo que hay filtrado. El año 2026 descarga
`inventario-2026-INV-2026-009.xlsx` con 82 KB.

**Un arreglo de fondo que hacía falta:** la versión de cada campaña cerrada guardaba solo seis campos
sueltos (código, nombre, oficina, responsable, estado). Con eso no se puede reconstruir un Excel —
falta la marca, el modelo, la RAM, la zona— y lo único que quedaba era el `activo_id`, o sea que
descargar 2026 obligaba a leer el inventario de hoy: **salía 2027 con otro nombre**. Ahora la versión
guarda los datos completos. Las versiones anteriores se reconstruyen con lo que siga existiendo en el
inventario, y el archivo lo dice.

### 4. Eliminar campañas

`DELETE /campanas/{id}`. Borra la campaña, su lista de equipos y su versión del histórico. **Nunca
borra un equipo del inventario**: lo que se registró al cerrar una campaña es inventario real y no le
pertenece a la campaña. Sí se borran los equipos nuevos pendientes que la campaña detectó y nadie
aceptó, porque nunca llegaron a ser equipos y su lista volvería a salir en la próxima comparación.

La papelera va **fuera** del botón que selecciona la campaña: un botón dentro de un botón no existe en
HTML, y si se hubiera construido encima con un `div`, el clic para elegir la campaña habría acabado
borrándola. El diálogo enumera qué se borra y dice en negrita que los equipos del inventario no se
tocan, porque en una pantalla de inventario «eliminar» sin explicación se lee como «va a borrar
equipos» y nadie lo va a pulsar.

### Verificación

**93 pruebas backend en verde** (8 nuevas en `test_descarga_y_borrado.py`: el Excel sale con una hoja
por zona, respeta los filtros, el año se descarga con los datos de aquel año y no con los de hoy,
eliminar no toca el inventario, eliminar una cerrada deja el histórico coherente, y eliminar lo que no
existe da 404). Cinco pruebas de gobernanza y de inventario anual adaptadas al cambio de «nace vacía».

Medido en el navegador contra la instalación real: descarga del inventario (82 KB, Excel válido),
descarga con filtro de zona, descarga del año 2026, diálogo de nueva campaña diciendo que empieza
vacía, y papelera con su diálogo. Cancelar el diálogo **no** borra nada. Sin errores de consola ni
peticiones fallidas. `tsc` y ESLint sin errores, `verify:clases` en verde.

Base municipal comprobada: sigue con **877 equipos** y la campaña OTIC con sus 875 items.
---

## BK — La redirección que no debía, el aviso que faltaba y los cuatro flujos

**Lo que se reportó:** al importar se redirige a la pestaña de Importar, lo que puede generar
errores porque **puede actualizar los equipos que se están manejando en el momento**. Y pide revisar
el diseño, las posiciones, los errores y el flujo de cada parte: filtros, importaciones, histórico e
historiales anuales.

### 1. La redirección: era un error mío de la ronda anterior

El único botón que llevaba a Importar estaba en el estado vacío de Inventario anual, y **lo dejé
there cuando las campañas pasaron a nacer vacías**. Consecuencias, todas medidas:

* Con la campaña vacía salía ese mensaje **en todas las campañas nuevas**.
* Envía a la pantalla de importación del inventario, que **actualiza los equipos que ya existen** —
  el riesgo que señalaste — y **no llena la campaña**: la campaña se llena con el Excel de la sala.
* El resultado es un callejón sin salida: el usuario llega a una pantalla que refresca 877 equipos
  sin avisar y de la que no es dueño.

Ahora el botón dice **Subir el Excel de la sala** y abre el selector de archivo del panel de
arriba, que es lo único que hace falta. Medido: en una campaña vacía aparece el botón nuevo y el de
«Importar inventario» **no aparece**.

### 2. El riesgo de la importación: ahora se avisa antes, no después

El backend siempre contó cuántas filas iban a **actualizar** un equipo existente, y la pantalla lo
enseñaba con la etiqueta «Actualizaciones», que se lee como «habrá novedades». No lo es: importar
**reescribe** los datos de los equipos que ya están —marca, modelo, el responsable que alguien
escribió a mano—.

La explicación buena estaba en el paso de resultado, que llega cuando ya no hay nada que hacer.
Ahora la previsualización avisa antes, con el número delante, y dice qué se pierde. Si **todas** las
filas válidas actualizan, dice que esto es una reimportación y no un alta.

### 3. Cuatro flujos recorridos en el navegador

Recorridos con Playwright contra la instalación real, mirando peticiones fallidas y errores de
consola. Lo que salió:

| Flujo | Qué se encontró |
|---|---|
| **Filtros** | Filtran bien, la búsqueda encuentra equipos reales y avisa cuando no hay ninguno. **Pero** una URL con `?zona_id=x` —un marcador guardado, una URL editada— devolvía **422 en dos endpoints**: la pantalla se quedaba a medias con dos errores en la consola. |
| **Importación** | **No había historial en pantalla**, con 29 importaciones guardadas en la base. El endpoint y el hook existían desde el principio y no los llamaba nadie. |
| **Histórico** | Enlace a comparar años presente. Sin años cerrados, la lista está vacía: correcto. |
| **Anuales** | Dos campañas con **196 equipos ya subidos** que seguían diciendo `total_items: 0`. El total se guardaba al crear la campaña y, como ahora nacen vacías, se quedaba en cero para siempre. |

### Lo que se corrigió

1. **El filtro mal formado ya no da error** (decisión 196). Un id que no es un id se ignora; uno
   válido que no existe filtra a cero, que es lo normal. Los ids de ruta y de cuerpo siguen
   validándose. Medido: de 2 peticiones fallidas a **0**.
2. **El historial de importaciones** ahora está en la pantalla: archivo, si se aplicó o fue solo
   vista previa, cuántos equipos creó, cuántos actualizó y cuándo.
3. **`total_items` se cuenta** en vez de guardarse al crear (decisión 197).
4. **El año de la campaña se ve** en el chip, y si el nombre dice un año y las fechas dicen otro,
   el diálogo lo avisa con los dos números y cuál manda.

Sobre el 4º, un hallazgo de tus datos que conviene que sepas: tienes **dos campañas, «Inventario
2026» y «inventario 2027», y las dos están archivadas como 2026**. El año sale de la fecha de inicio
y el calendario viene precargado con el año en curso, así que la segunda quedó como 2026 sin que nada
lo dijera. Ahora se ve en el chip, pero **esa campaña hay que recrearla** con las fechas de 2027 si
la quieres como año 2027; no se puede cambiar el año de una campaña ya creada.

### Verificación

**94 pruebas backend en verde** (una nueva: un filtro mal formado en `activos` y en `oficinas`
devuelve 200 con el filtro ignorado, y uno válido que no existe devuelve cero). Recorrido de los
cuatro flujos en el navegador: **0 peticiones fallidas, 0 errores de consola**. `tsc` y ESLint sin
errores, `verify:clases` en verde.
---

## BL — Zonas y oficinas: desactivar era una puerta sin vuelta atrás

**Lo que se pidió:** ir a oficinas y zonas, analizar el diseño, probar cada paso y comprobar que todo
esté bien.

### El hallazgo grave: desactivar quitaba cosas para siempre

El backend sirve solo lo activo por defecto (`solo_activas=True`), y la pantalla pedía eso y solo
ofrecía **Desactivar**. Medido: **al desactivar una oficina desaparecía de la pantalla sin dejar
rastro, y no había forma de recuperarla desde la aplicación** — había que entrar a la base de datos.

En el municipio ya había **cuatro elementos desactivados** que nadie podía volver a activar sin
escribir SQL. Esos son datos tuyos y **no los toqué**: solo se comprobó que ahora su menú ofrece
«Reactivar», sin pulsarlo.

### Lo corregido

1. **Desactivar es una puerta y tiene vuelta atrás** (decisión 199). La pantalla pide también lo
   desactivado, lo marca con una etiqueta y con su explicación, y ofrece Reactivar junto a Desactivar.
   Verificado en el navegador: las 4 desactivadas muestran «Renombrar · Reactivar».

2. **El diálogo de desactivar decía la mitad de la verdad** (decisión 200). Decía «los registros
   históricos se conservarán», que era lo que no importa. Lo que importa es lo que **deja de
   funcionar**: deja de ofrecerse al elegir zona, oficina o responsable en todo el sistema, y sus
   equipos se quedan sin oficina a la que asignarse. Ahora dice las tres cosas, incluido que es
   reversible desde ahí mismo.

3. **Ciento dieciocho botones para tres acciones** (decisión 201). Cada una de las 59 oficinas tenía
   Renombrar y Desactivar sueltos. Medido: **66 botones «Renombrar» sueltos → 0**, y 43 menús de tres
   puntos, igual que en Inventario.

4. **Con 59 oficinas, buscar no era opcional** (decisión 202). Buscador de zona **y** de oficina: buscar
   el nombre de una oficina trae la zona que la contiene. Verificado: buscando «PALACIO» queda solo
   PALACIO; buscando algo que no existe avisa y ofrece limpiar.

5. **PALACIO tenía 27 oficinas y hacía la página un muro** (decisión 203). Se listan 8 por zona con
   «Ver las N más», y **una zona desplegada a la vez**. Medido: la página pasó de 80 filas a 53, con
   3 zonas con lista larga.

6. Cosas menores: la zona sin oficinas muestra «Esta zona todavía no tiene oficinas» con un botón
   **Agregar la primera** en vez de un texto muerto; el diálogo de nueva oficina dice en qué zona se va
   a crear; el de renombrar zona avisa de que el nombre también se reemplaza en oficinas, personas y
   tickets; y el contador de oficinas de una zona cuenta solo las **activas**, que es lo que se puede
   usar.

### Dos errores míos en el camino

- Volví a escribir `**todo**` en JSX, que sale **con asteriscos literales** en pantalla. Salió en una
  captura y estaba en el diálogo de desactivar. Corregido, y ahora el recorrido comprueba que en ese
  diálogo no queden asteriscos.
- El diálogo de desactivar decía «Sus 0 oficinas siguen existiendo». Con cero ahora dice «No tiene
  oficinas».

### Verificación

**98 pruebas backend en verde** (4 nuevas: lo desactivado se ve con `solo_activas=false` y se puede
reactivar; desactivar no saca las oficinas de su zona ni mueve los equipos; renombrar una zona
arrastra el nombre a oficinas y personas; el nombre duplicado se rechaza).

Recorrido de **12 pasos** en el navegador contra la instalación real: contadores, menú de fila,
diálogo de desactivar, buscador con y sin coincidencias, validación de crear zona, crear oficina con
su zona, renombrar con su aviso, que una desactivada ofrece Reactivar, y el desplegar de listas
largas. **0 peticiones fallidas, 0 errores de consola.** `tsc` y ESLint sin errores,
`verify:clases` en verde.

**No se escribió nada en tu base**: los pasos que guardan se cancelaron siempre con «Cancelar».
---

## BM — Zonas y oficinas: diez por página

**Lo que se pidió:** límite de 10 oficinas por zona y dividirlas en páginas.

### Lo que se hizo

Se cambió el corte de 8 a **10** y el botón «Ver las N más» se sustituyó por **paginación real**,
reutilizando el mismo paginador de Inventario (`Paginacion`), para que el control sea el mismo en
toda la aplicación.

Medido sobre tus datos: **3 zonas con lista larga** — COMPLEJO 13 oficinas, MERCADO 11, PALACIO 27 —
y cada una con su propio paginador («Mostrando 1 a 10 de 13 · Anterior 1 2 Siguiente»).

Tres cosas que solo aparecieron al implementarlo y que se dejaron resueltas:

1. **Cada zona lleva su página, no una común.** Si el estado fuera compartido, al paginar PALACIO
   cambiaría MERCADO, que está justo al lado. Medido: paginar la primera deja la segunda intacta.

2. **La página se acota a las que existen.** Al buscar, o al dejar de mostrar las desactivadas, una
   zona puede quedarse con menos oficinas; sin acotar se quedaba en «página 3 de 2» y la lista salía
   **en blanco sin explicar nada**.

3. **Buscando se ven todas las oficinas de la zona, sin paginación.** El buscador es para encontrar
   una en concreto; esconder el resto detrás de un «Siguiente» devolvía el problema que el buscador
   resolvió. Verificado: con la búsqueda activa no queda ningún paginador.

La última página **acaba justo en el total**: COMPLEJO muestra «11 a 13 de 13», sin repetir filas y
sin huecos.

### Verificación

**7 pasos** en el navegador: los paginadores existen, muestran 10 y no 8, «Siguiente» avanza y marca la
página 2, «Anterior» vuelve, la última acaba en el total, cada zona va por su cuenta, y la búsqueda
deja la zona entera a la vista. **0 peticiones fallidas, 0 errores de consola.** `tsc` y ESLint sin
errores, `verify:clases` en verde. **98 pruebas backend en verde.**

No se escribió nada en tu base: la paginación es de lectura.

---

## BN — La ficha de oficina, oficina por oficina

**Lo que se pidió:** entrar a cada oficina y ver si está bien o mal —diseño, estética, contraste,
color, tamaños, iconos—, mirar cómo se muestran los **equipos de uso común** y el **personal con
equipos responsables en su espacio**, y que **«mostrar desactivados» se recuerde** al volver a entrar.

### «Mostrar desactivados» se recuerda

Era una casilla que solo vivía mientras la pantalla estuviera abierta: al salir de Zonas y oficinas y
volver, los desactivados volvían a aparecer solos, y había que desmarcarlos otra vez. Es una
decisión de quien mira, no un estado de la pantalla.

Se guarda en `localStorage` bajo `org.ver-desactivados`, **leída fuera de `useState`** para que no
haya un parpadeo: si no, el guardado se aplicaría después del primer dibujado y la pantalla
aparecería un instante con los desactivados y luego los quitaría. Si el valor guardado viene
corrupto, lo que no sea «false» se trata como marcado. Verificado: desmarcado → 0 · tras recargar →
0 · tras venir de otra pantalla → 0, y restaurado a 4.

### La ficha de oficina, que era un esqueleto

Medido antes de tocarla: el nombre de la oficina salía **tres veces** (migas, título y tarjeta), el
estado del equipo era **texto suelto** —«· OPERATIVO»— mientras que en Inventario es una insignia con
su color, y el mismo texto **«No hay registros para mostrar»** aparecía en tres bloques distintos.
Los tamaños de encabezado medidos eran **16 px el título y 16 px el cuerpo**: no había jerarquía.

Lo corregido:

1. **Contenedor y jerarquía.** La ficha va en `PantallaFormulario`, como el resto. Medido después:
   **título 24 px, encabezados de panel 20 px**, cuerpo 14 px. Antes el título era del mismo tamaño
   que el texto que lo describía.

2. **El nombre ya no sale tres veces.** La tarjeta grande se queda con lo que aporta —la zona, su
   color y los números— en vez de repetir el título.

3. **El estado del equipo es una insignia**, la misma de Inventario, con su color y su icono.

4. **Cada vacío dice qué falta.** «No hay tickets abiertos en esta oficina» es una buena noticia y se
   lee en verde con su marca; «Todos los equipos de esta oficina tienen responsable asignado»;
   «Ninguna categoría se repite en esta oficina».

5. **Responder «quién tiene equipos» sin cruzar dos listas.** Ahora cada persona dice cuántos equipos
   tiene, o **«Sin equipo»**. Antes la respuesta obligaba a comparar mentalmente «Personas» con
   «Equipos por responsable».

6. **Los equipos de uso común se distinguen.** Un equipo sin responsable no es un equipo de nadie: es
   **de la oficina**. Lleva su panel propio y la insignia «USO COMÚN», y un aviso corto explica que se
   puede corregir asignándole un responsable.

7. **Iconos de un solo tamaño** (18 px). Antes se medían 16, 18, 22 y 26 mezclados, y uno **de tamaño
   0**, invisible.

8. **Los paneles ya no se estiran.** Con dos columnas, el panel corto quedaba con un bloque de
   blanco debajo que parecía contenido que no cargó. Ahora cada uno mide lo que mide.

### El número que no contaba nada

El rótulo de «Personas» decía **«0 sin equipos asignados»** en una oficina donde las tres personas
tenían uno. Se calculaba restando `total_usuarios - usuarios.length`, que da siempre 0 cuando la lista
está completa: no miraba a nadie. Ahora cuenta las personas de la lista sin equipo, y el recorrido
comprueba que el rótulo y la lista **digan lo mismo**.

### El agrupamiento por nombre, que mezclaba personas

Al leer las 59 oficinas se vio que ninguna tenía personal sin equipo, lo que parecía demasiado limpio.
La causa: los equipos se agrupaban por el **nombre** del responsable. Dos consecuencias, ambas
silenciosas:

* dos personas que se llamen igual caían en la misma fila y sus equipos **se sumaban** como si fueran
  de una sola;
* un nombre con un espacio de más o una tilde distinta partía el grupo, y quien quedaba fuera
  **aparecía «sin equipo» teniendo los suyos**.

Ahora el grupo se forma por el **id** del responsable, y el nombre va solo para poder leerlo. La
respuesta lleva `responsable_id` en cada grupo. Medido: las 59 oficinas muestran **exactamente lo
mismo** que antes —27 de uso común en GERENCIA DE ADMINISTRACIÓN TRIBUTARIA, 12 en OF.CENTRO DE
EVALUACIÓN (B)— porque hoy los nombres sí casan; lo que cambia es que mañana dejarán de poder fallar
en silencio.

### «1 personas»

En la ficha de zona, COMPLEJO mostraba **«1 personas · 5 equipos»** para COMPROMISO 1 PADRON DOMINAL.
El plural estaba escrito a mano en cada sitio. Se añadió `plural(n, palabra)` a `formato.ts` y se
usó en la ficha de zona, la de oficina y Zonas y oficinas. El diálogo de desactivar tenía el mismo
problema y además el verbo: «Sus 1 oficinas siguen existiendo» → «Su 1 oficina sigue existiendo».
Medido: **16 pantallas revisadas, 0 plurales mal concordados.**

### Un contraste que era mentira mía

Medí el contraste de los títulos de panel y salió **3,40:1**, por debajo del 4,5:1 que pide WCAG AA.
Era **falso**: el fondo del encabezado de panel se calcula como `oklab(… / 0.6)` —semitransparente y
en un espacio de color que no es sRGB— y mi script lo leía como si fuera opaco. Midiendo bien,
componiendo el alfa y convirtiendo oklab a sRGB, el resultado real es **16,3:1** en títulos y enlaces
y **6,9:1** en el texto secundario. No había problema de contraste; el problema era la medición.

### Verificación

**102 pruebas backend en verde** (4 nuevas en `test_oficina_responsables.py`: dos homónimos en grupos
distintos con sus equipos cruzados bien; un nombre con espacios que no deja a su dueño sin equipo; un
responsable solo con nombre que se agrupa y no se pierde; y que lo que no tiene dueño siga yendo a
uso común).

**59 oficinas revisadas una por una** en el navegador, de las 6 zonas: 0 asteriscos literales, 0
iconos de tamaño 0, 0 equipos de uso común sin su insignia, 0 títulos que no cuadran con el nombre.
**0 peticiones fallidas y 0 errores de consola** en las 59.

Además: ningún panel queda estirado, cada persona con equipos lo dice al lado de su nombre, el rótulo
coincide con la lista, y la ficha de zona mantiene la jerarquía. `tsc` sin errores, ESLint con 0
errores y los 6 warnings de siempre, `verify:clases` en verde.

**No se escribió nada en tu base.**

### Lo que se encontró y no se tocó (son datos tuyos)

Se avisó y quedó pendiente de que lo apruebes:

1. **21 grupos de equipos con el mismo nombre dentro de la misma oficina**, sobre 877 equipos. El caso
   más claro: en GERENCIA DE ADMINISTRACIÓN TRIBUTARIA, «Computadora N°04 - Monitor» aparece dos
   veces, en el mismo conjunto, con dos responsables distintos (GERENCIA DE ADMINISTRACIÓN TRIBUTARIA
   y CESAR PEREZ MEJIA). En pantalla se ve como un equipo repetido.
2. **Equipos cuyo nombre es «OPERATIVO»** (3 en SUB.GERENCIA DE CONTABILIDAD, 2 en S.G TRANSPORTE Y
   SEGURIDAD VIAL): parece que la columna del estado se guardó en la del nombre.
3. **Cuentas de usuario que se llaman como la oficina** —«GERENCIA DE ADMINISTRACIÓN TRIBUTARIA» y
   «SUB GERENCIA DE ADMINISTRACION TRIBUTARIA» aparecen como *personas* y tienen 2 equipos cada una.
   Una de las dos sin tilde: son casi la misma con dos nombres.

---

## BO — La ficha de oficina: pestañas, botón de volver, estados de verdad y borrar

**Lo que se pidió, con dos capturas:** que las listas **no se desborden** porque «se ve muy feo», con
pestañas; lo mismo en uso común; un **botón para volver atrás**; el aviso de uso común **más
disimulado**, que no sea «un anuncio gigante»; un botón de **eliminar permanentemente** antes de
desactivar; que **«Operativo» sea verde** en vez de gris; y que los equipos **digan qué son** —CPU,
mouse— de forma discreta.

### Las pestañas

La causa del desbordamiento no era el tamaño sino el reparto. Medido: «Personas» con 6 filas al lado
de «Equipos por responsable» con 11 dejaba **media pantalla en blanco** bajo la columna corta, y en
GERENCIA DE ADMINISTRACIÓN TRIBUTARIA la diferencia era de **6 contra 38**. Ninguna de las dos columnas
se puede acortar sin dejar de ver algo, así que la solución no era ajustarlas: fue no ponerlas
juntas.

Ahora son tres pestañas —**Personas (9) · Equipos asignados (11) · Uso común (27)**— con el mismo
sistema de pestañas del resto de la aplicación. Cada una usa el ancho entero: **1100 px**, medido, y
solo se ve la que se está mirando.

### El uso común, paginado — porque esa era la única lista que se desbordaba

Antes de elegir el corte se midieron las 59 oficinas:

| lista | mediana | p90 | máximo |
|---|---|---|---|
| Personas | 4 | 9 | 11 |
| Equipos asignados | 5 | 9 | 15 |
| Grupo más grande de una persona | 1 | 4 | 12 |
| **Uso común** | **9** | **18** | **28** |

Solo el uso común llega a un tamaño de muro, y por eso es el único paginado: de diez en diez, con el
mismo paginador de Inventario. **18 de las 59 oficinas** lo ven. Verificado en la de 27: «Mostrando
11 a 20 de 27», y la página 2 trae otra lista.

### El botón de volver

**«Volver a zonas y oficinas»** en la esquina del título. Va a `/panel/organizacion` y no «a la
página anterior»: si se abrió la ficha desde un enlace o desde el historial del navegador, «atrás» no
lleva a ninguna parte.

### El aviso de uso común, discreto

Era un recuadro ámbar de media pantalla para repetir lo que ya decían el título de la pestaña y la
descripción del panel. Ahora es **una línea de texto apagado**: medido, **20 px de alto**, a lo ancho
de la línea, sin fondo ni borde.

Por la misma razón se quitó la insignia «USO COMÚN» que llevaba cada equipo: repetida 27 veces dentro
del panel que ya se titula «Equipos de uso común», no decía nada.

### «Operativo» salía gris. El motivo era otro

Medido antes: la insignia decía **«Estado no reconocido»**, con fondo `rgb(238, 242, 248)`. El mismo
equipo, en Inventario, salía verde. Dos causas, ninguna de ellas la que parecía:

1. **`EstadoBadge` es el catálogo de los *tickets*** (`nuevo`, `en_progreso`, `en_espera`, `cerrado`)
   y los equipos viven en otro, `DISPONIBILIDADES` (`operativo`, `dado_de_baja`…). La ficha pintaba
   el estado del equipo con el componente de ticket, así que **todas** las insignias caían en «Sin
   estado». Ahora usa `DisponibilidadBadge`, como Inventario.
2. La base guarda los estados como los escribe el Excel —**«OPERATIVO» en mayúsculas**— y los
   catálogos están en minúsculas con guion bajo. Sin normalizar, `estadoDe` no encontraba nada
   aunque mirara el sitio correcto.

Medido después: fondo **`rgb(14, 92, 55)`**, verde, con el título **«El equipo está en servicio»**.
Barrido de las 59 oficinas y de las 6 pantallas principales: **0 estados sin reconocer**.

### El tipo del equipo, discreto

Cada equipo muestra su tipo en letra pequeña y apagada, **solo si aporta algo**: en
«DESKTPO-AOAAH4T» dice «CPU», pero en «Computadora N°01 - Monitor» no lo repite, porque el nombre ya
lo dice.

La lista pasó a ser una rejilla de cuatro columnas: con el panel al ancho de la pantalla, la
insignia quedaba pegada al borde derecho y a 800 px del nombre al que pertenecía.

### Eliminar permanentemente

El diálogo de desactivar ofrece abajo, separado por una línea, **«Eliminar definitivamente»**, que
abre **otro** diálogo con icono de aviso y botón rojo. No comparten botón porque no son la misma
puerta: desactivar tiene vuelta atrás, borrar no. Antes solo se desactivaba, así que una zona creada
por error se quedaba para siempre en la lista y quitarla exigía entrar a la base de datos.

El backend ya lo protegía y por eso no es una puerta abierta: **una zona con oficinas no se borra, y
una oficina con equipos no se borra**. El diálogo lo dice antes de intentarlo. Verificado con
«Eliminar para siempre» en rojo, cerrado con «Cancelar» — **no se borró nada**.

### Dos errores de medición míos

- **Conté mal el desbordamiento.** El barrido decía que «Equipos asignados» tenía 25 filas de una
  vez, y casi paginé esa lista también. Estaba sumando los `<li>` de los diez grupos: diez personas
  con dos equipos son diez bloques cortos, no un muro. Al medir la distribución real, el grupo más
  grande de toda la municipalidad tiene 12 equipos.
- **Una oficina dio un falso fallo.** En un barrido de 59, O.G.PLANEAMIENTO Y PRESUPUESTO salió con
  «0 pestañas». Comprobado aislada que carga bien con los mismos 1800 ms: era que el barrido la midió
  a medio cargar. Ahora espera a que la ficha exista.

### Verificación

**59 oficinas revisadas** una por una, recorriendo las tres pestañas de cada una: 0 asteriscos
literales, 0 iconos de tamaño 0, 0 estados sin reconocer, 3 pestañas en todas, botón de volver en
todas, ninguna lista de uso común con más de 10 filas de una vez. **0 peticiones fallidas y 0 errores
de consola.**

Además: el botón de volver aterriza en «Zonas y oficinas»; cambiar de pestaña cambia lo que se ve; las
listas usan el ancho entero; el aviso mide 20 px; el paginador avanza y trae otra lista; y el diálogo
de eliminar avisa que es irreversible y por qué puede no poder borrarse.

**102 pruebas backend en verde.** `tsc` sin errores, ESLint con 0 errores y los 6 warnings de siempre,
`verify:clases` en verde.

**No se escribió nada en tu base**: el diálogo de eliminar se cerró siempre con «Cancelar».

---

## BP — Cuatro fallos que reportó el usuario

**Lo que se reportó:** que en los equipos no se ve el tipo, que no aparece el botón de eliminar oficinas
ni zonas, que al eliminar debería avisar de qué tiene asociado, y que la ficha de zona no tiene
«Volver».

### 1. El tipo del equipo no aparecía en su propia ficha

En Inventario sí estaba —segunda línea, en negrita: «PRINTGDS · **Impresora** · EPSON L6270»—, pero en
la **ficha del equipo** el tipo no salía en ningún sitio: el subtítulo era «marca · modelo ·
oficina» y las cuatro métricas eran estado, completitud, datos pendientes y responsable.

Con nombres como `PRINTGDS` o `DESKTPO-AOAAH4T` no había forma de saber qué eran. El icono sí lo
decía, pero un icono no se lee de lejos.

Ahora el tipo va **en el subtítulo y como métrica «Tipo»**: «Impresora · EPSON L6270 · ASISTENCIA
SOCIAL». Se quitó «Datos pendientes» de las métricas, que ya salía en la barra de completitud y en la
insignia. Verificado sobre `PRINTGDS`.

De paso, el perfil de usuario pintaba el estado del equipo como **texto suelto en gris** —el mismo
fallo de la ronda anterior en otra pantalla—. Ahora usa la insignia, con su color.

### 2. «Eliminar» estaba escondido dentro de «Desactivar»

La ronda anterior lo había puesto dentro del diálogo de desactivar, a dos clics. Eso obliga a
desactivar primero para poder borrar, que es lo contrario de lo que se busca: **desactivar es
reversible** y sirve para «no la quiero ahora»; **borrar** es para «esta nunca debió existir».

Ahora «Eliminar» está en el menú de cada fila de zona y de oficina, en rojo y separado por una línea.
Medido: zonas «Renombrar · Desactivar · Eliminar» y oficinas igual.

### 3. El aviso de qué tiene asociado

Lo pedido era avisar **antes** de borrar. El diálogo ahora pregunta al servidor y enseña los
números:

- **Zona con oficinas**: «Se borrará COMPLEJO… · Oficinas 13 · Personas 34 · Equipos 111» y «No se
  puede borrar todavía: la zona tiene 13 oficinas registradas. Elimina o traslada las oficinas
  primero». Botón deshabilitado.
- **Oficina con equipos**: «Personas 3 · Equipos 5» y el motivo. Botón deshabilitado.
- **Zona vacía** (LEYVA, 0 de todo): «No tiene nada asociado, así que se puede borrar». Botón
  activo. Cerrado con «Cancelar»: **no se borró nada**.

**Por qué pregunta al servidor y no usa los contadores de la fila:** el contador de equipos **filtra
los dados de baja** y el borrado no. El aviso podía decir «0 equipos» y el borrado responder «tiene
3». Para que no puedan discrepar, el aviso y el borrado llaman a la **misma función**
(`bloqueos_borrado_zona` / `bloqueos_borrado_oficina`), y hay una prueba que compara las dos cosas.

El botón queda **deshabilitado** en lugar de fallar al pulsarlo: un botón rojo que rechaza la
pulsación no explica nada.

### 4. El botón de volver faltaba en la zona

Estaba en la ficha de oficina y no en la de zona, sin ninguna razón: son la misma relación y el mismo
origen. Ahora está en las dos.

### Un error de medición mío

La regresión marcó «50 iconos de tamaño 0» en Equipos, 25 en Usuarios y 36 en Tickets. Al mirarlos uno
a uno: **ninguno era un fallo**. Estaban dentro de `display: none`, en las columnas de «solo
impresión». Mi comprobación contaba el tamaño sin mirar si algo los estaba escondiendo.

### Verificación

**107 pruebas backend en verde** (5 nuevas en `test_borrado_organizacion.py`: el aviso y el rechazo
dicen lo mismo; una zona vacía sí se borra; el aviso cuenta los equipos dados de baja que la lista no
cuenta, y en singular; una oficina sin equipos se borra aunque tenga personas; y borrar una zona
vacía no toca nada de fuera).

Las cuatro cosas comprobadas en el navegador contra la instalación real: la ficha de `PRINTGDS`
dice «Impresora»; los dos menús tienen «Eliminar»; los tres casos del aviso (bloqueado, bloqueado y
permitido) se comportan como deben; y el botón de zona lleva a «Zonas y oficinas».

**Regresión:** 7 pantallas y 9 zonas más 12 oficinas — 0 asteriscos literales, 0 estados sin
reconocer, 0 iconos invisibles, botón de volver en todas. **0 peticiones fallidas, 0 errores de
consola.** `tsc` sin errores, ESLint con 0 errores, `verify:clases` en verde.

**No se escribió nada en tu base**: los tres diálogos de borrado se cerraron con «Cancelar».

---

## BQ — El tipo de equipo: mouse, teclado, monitor y los catorce del catálogo

**Lo que se reportó:** que en equipos como mouse, teclado y monitor tampoco sale qué tipo son, y que
sean todos los que se pueden registrar.

### El más grave era un error mío de la ronda anterior

Al añadir el tipo a la ficha de oficina lo puse con una regla que parecía prudente: **no mostrarlo si
el nombre ya lo contenía**, porque «Monitor» debajo de «Computadora N°01 - Monitor» parece repetir.

El resultado fue justo el contrario de lo que se quería. Como **casi todos** tus equipos se llaman
«Computadora N°01 - Mouse», «Computadora N°01 - Teclado» o «Computadora N°01 - Monitor», **la
columna quedaba vacía justo en mouse, teclado y monitor**: 526 de los 877 equipos.

Medido sobre 59 oficinas con la regla nueva: las 59 con todos sus equipos tipados. Los tipos que
salen en las listas son Monitor 181 · CPU 175 · Mouse 126 · Teclado 92 · Impresora 90 · Laptop 51.

Ahora el tipo se enseña siempre. Que la palabra se repita no molesta: es la forma rápida de confirmar
que el tipo guardado es el que se cree.

### Seis de los catorce tipos se veían iguales

El catálogo tiene **catorce** tipos: CPU, Laptop, Monitor, Teclado, Mouse, Impresora, Router, Switch,
Tablet, Celular, Servidor, UPS, Disco duro externo y Sistema de audio. El mapa de iconos solo
reconocía **siete**: los otros seis caían todos en el mismo icono genérico, y Router y Switch
compartían dibujo. Seis equipos distintos se veían igual.

Ahora cada tipo tiene su icono y su color. Medido sobre el selector del alta, que es donde aparecen
los catorce aunque no haya equipos de ese tipo: **15 tarjetas, 15 dibujos distintos, 15 colores
distintos**.

De paso, el mapa reconoce lo que llega escrito de otra manera —«portátil», «ratón»,
«multifuncional», «no-break», «parlante»— y también **«LAPTO»**, que antes caía en el genérico
porque `/laptop/` no encuentra «lapto».

### Un fallo mío que costó dos builds

Cambié el icono genérico en el mapa y **no cambió nada**: la rama de «tipo no reconocido» traía su
propio `HardDrive` escrito a mano, así que el mapa decía una cosa y el dibujo otra. Dos sitios que
deciden lo mismo se desincronizan. Ahora el icono sale siempre del mapa.

Y la primera vez que «arreglé» los iconos, la build siguió sirviendo el bundle viejo por la caché de
Docker: la pantalla seguía igual y parecía que el arreglo no funcionaba. Se comprobó leyendo el
archivo servido dentro del contenedor.

### Verificación

Los **15** tipos (los 14 del catálogo más «Otro») con dibujo y color propios; los seis tipos con
equipos registrados buscados en Inventario con su icono correcto; las 59 oficinas con todos sus
equipos tipados; y 8 pantallas sin asteriscos, sin estados sin reconocer ni iconos invisibles.
**0 peticiones fallidas, 0 errores de consola.** `tsc` sin errores, ESLint con 0 errores,
`verify:clases` en verde.

### Sigue pendiente y no se tocó (son datos tuyos)

Hay **33 equipos con un tipo que no existe en el catálogo**. No los cambié porque son datos:

| tipo guardado | equipos | qué parece ser |
|---|---|---|
| «Por identificar» | 8 | un valor de espera, válido |
| «INOPERATIVO» | 5 | un **estado**, no un tipo |
| «PERONAL» | 4 | nada reconocible |
| «SIN CONEXCION» | 5 | nada reconocible |
| «FALTASTES» / «FALTAN» | 5 | basura de una importación |
| «LAPTO» | 4 | **Laptop**, escrito de otra forma |
| «7422235800» | 1 | un número de teléfono |

Cuatro son corregibles sin criterio discutible («LAPTO» → Laptop; los cinco «INOPERATIVO» son estado,
así que habría que mirar qué son). Los otros necesitan que tú digas qué son. Dime si quieres que los
arranque.

---

## BR — Usuarios: la página entera, de arriba abajo

**Lo que se pidió:** entrar a Usuarios y analizar errores, flujos, pruebas y diseño, para comprobar
que la página funciona bien en flujo y en diseño.

### El hallazgo grave: el directorio no pedía permiso

La pantalla está detrás de `usuarios.ver`, pero **`GET /api/usuarios` no exigía ningún permiso**:
bastaba con estar conectado. Probado con una cuenta de rol `usuario` —la que reporta problemas—:
recibía el directorio entero con nombre, correo, teléfono, rol y oficina de las **267 cuentas**.

La única guarda era «si no tienes oficina, devuelve vacío», que no es un permiso: quien tiene
oficina, que es casi todo el mundo, pasaba de largo. En la ruta ya se importaba
`DependeEditarUsuarios` y se usaba en crear y en restablecer contraseña; faltaba el de «ver».

Corregido, y con prueba que falla sin el cambio.

### No se podía desactivar ni reactivar a nadie

El backend tenía `POST /usuarios/{id}/desactivar` y `PATCH {activo}`, y la pantalla **no llamaba a
ninguno**. Además la lista pedía solo las cuentas activas. O sea que una cuenta desactivada
desaparecía del directorio sin dejar rastro y sin forma de volver: el mismo callejón sin salida que
se corrigió en Zonas y oficinas en la ronda BL.

Ahora el perfil ofrece **Desactivar cuenta** y **Reactivar cuenta**, con una casilla para mostrar las
desactivadas que se recuerda. El aviso de desactivar dice lo que **no** se toca: historial, tickets
y los equipos que esa persona tiene asignados.

Medido: **0 cuentas desactivadas** hoy, así que el cambio no alteró nada de lo que tienes. El ciclo
completo —desactivar, dejar de salir, seguir estando, reactivar, volver— queda fijado por pruebas
de backend, porque en el navegador desactivaría una cuenta tuya.

### El filtro de zona y de oficina

Las 59 oficinas salían siempre, y se podía marcar zona COMPLEJO con oficina de PISCINA para salir
«0 resultados» sin explicación. Se llegaba ahí sin querer porque, al cambiar de zona, la oficina
anterior se quedaba puesta y pasaba a ser de otra zona.

Ahora las oficinas son las de la zona elegida (**59 → 12** en COMPLEJO) y al cambiar de zona la
oficina se suelta.

### El error del servidor se escribía en la esquina

Al crear una cuenta con un correo ya en uso, el diálogo se quedaba abierto pero **impávido**: el
campo del correo sin marcar y la única pista era una pastilla abajo a la derecha, con el formulario
enfrente. Ahora el motivo —«Ya existe una cuenta con ese correo.»— se escribe arriba del formulario,
dentro del diálogo.

### El rol se escribía de dos maneras

El filtro decía **«Técnico TI»** y la tabla aplicaba `capitalize` sobre el valor crudo, así que un
técnico salía **«Tecnico»**: sin tilde y con otro nombre. `capitalize` de CSS pone mayúscula, no
tilde. Ahora hay un solo sitio donde se escribe: `etiquetaRol()`.

### El perfil era un muro de párrafos

Seis `<p>` seguidos —nombre, correo, zona, cargo, teléfono, tickets— sin jerarquía ni rótulos, con
los «No indicado» pegados al dato, de modo que no se distinguía lo que faltaba de lo que valía.

Ahora: avatar, nombre, correo y rol arriba; los seis datos en dos columnas con su rótulo; los equipos
en lista con su tipo y su código; y los botones «Abrir perfil completo» y «Desactivar cuenta».

### Dos cosas más

* **La columna «Ayuda IA» solo estaba en el móvil.** El encabezado de la página promete que cada
  fila dice si la persona tiene activa la ayuda automática —que es lo que explica por qué a alguien
  no le salen sugerencias— y en la tabla no estaba.
* **El alta de equipo ofrecía cualquier persona del municipio como responsable.** Pedía el
  directorio entero, no el de la oficina elegida, en una pantalla que dice «Personas activas de la
  oficina elegida». Medido: antes **26 opciones** sin elegir oficina; ahora **0**, y **3** al elegir
  ASISTENCIA SOCIAL —sus tres personas—. La ficha de equipo ya lo hacía bien; el fallo se notó al
  comparar las dos.

### Verificación

**114 pruebas backend en verde** (7 nuevas en `test_usuarios_permisos.py`: el directorio exige
`usuarios.ver` y una cuenta normal recibe 403; tampoco una cuenta sin oficina; el buscador vacío no
devuelve el directorio; ver el perfil ajeno sigue limitado; desactivar → deja de salir → sigue
estando → reactivar; desactivar no borra la cuenta ni sus equipos; y no se puede desactivar a uno
mismo).

En el navegador, contra la instalación real: tabla y filtro dicen lo mismo; la zona acota las
oficinas y suelta la anterior; el correo repetido se escribe dentro del formulario; el perfil ofrece
desactivar con su confirmación y la casilla de desactivadas se recuerda; el perfil tiene rótulos y
avatar; la tabla tiene «Ayuda IA»; se ve el total (**267 cuentas**); y en móvil no se desborda.
**11 pantallas y las 59 oficinas** sin asteriscos, sin estados sin reconocer, sin iconos invisibles ni
desbordes. **0 peticiones fallidas, 0 errores de consola.** `tsc` sin errores, ESLint con 0 errores,
`verify:clases` en verde.

**No se escribió nada en tu base**: el diálogo de desactivar se cerró con «Cancelar» y el alta con
correo repetido se canceló.

### Lo que vi y no toqué

* **El título de la pestaña lleva el nombre fijo «Mesa de Ayuda TI»** en las veinte pantallas, pero
  el nombre de la institución es configurable en Configuración. Es un detalle igual en todas, así que
  arreglarlo solo aquí no tiene sentido: o se cambia en todas o no se cambia.
* **267 cuentas con 0 desactivadas** significa que la columna de estado es hoy una columna siempre
  idéntica. Se queda: en cuanto alguien se desactive, empieza a valer.

## BS - Cuatro cosas de la pantalla de Usuarios

### 1. El alta: qué se escribe en cada campo

«Correo» y «Cargo» no decían para qué servían. Con uno se inicia sesión; con el otro se localiza a
alguien cuando toca llamarlo. Ahora cada campo lleva debajo qué se pone en él, y el diálogo se reparte
en dos columnas para que los ocho campos entren sin desplazamiento.

Medido: el diálogo mide **753 px** en una ventana de 1100 y **no se desplaza**. Antes se desplazaba y el
último —la oficina— quedaba cortado detrás del pie de botones.

### 2. El buscador

**Lo que no era:** el buscador no se rellena solo. Es un campo controlado (`value` + `onChange`), así que
nada de la aplicación puede escribir en él. Medido, con el perfil abriéndose y cerrándose cuatro veces:
el valor se mantiene exactamente como estaba, **25 filas** antes y después. Buscar un correo que no
existe sí deja la lista a cero, y ese correo no está en la base.

**Lo que sí era, y se arregla en dos partes:**

* **El navegador devolvía la búsqueda vieja.** Los `type="search"` guardan lo escrito y lo vuelven a
  poner al abrir la pantalla: la tabla aparecía filtrada por algo que nadie había escrito en esa
  visita. Con `autoComplete="off"` y un `name` propio deja de hacerlo.
* **Buscar sin resultados no dejaba volver.** Es la razón más normal para buscar y no encontrar —el
  correo de alguien que todavía no tiene cuenta— y había que vaciar los cuatro filtros a mano. El
  estado vacío ofrece ahora «Quitar los filtros»: de 0 filas vuelve a las **25** con el buscador vacío.

### 3. Los espacios y las ubicaciones

Medido, la barra de cuatro filtros estaba descuadrada **26 px**: el buscador no pintaba rótulo visible
—su `etiqueta` solo iba al `aria-label`— y los tres desplegables sí. Su base de línea estaba en 234 y
la de ellos en 260. Con el rótulo del buscador, los cuatro bottoms coinciden en **260 px**.

Las ubicaciones se recortaban a la mitad: «GERENCIA DE ADMINISTRACI…», «SUB GERENCIA DE DESARROL…». La
tabla repartía el ancho a partes iguales; ahora la ubicación tiene el 30 % y los nombres largos salen
enteros. En toda la tabla, **0 celdas** que se salgan de su columna.

### 4. El perfil, más ordenado

Cabecera con avatar, nombre, correo, el rol como insignia y el estado; después tres bloques rotulados
—**Persona**, **Actividad**, **Cuenta**— en lugar de seis líneas sueltas en el mismo peso. Cabe entero:
**724 px** en 1100.

### 5. Lo que salió de paso: las filas no se podían abrir sin ratón

Al comprobar el perfil con el teclado se vio que la fila era un `<tr>` con `onClick` y `cursor-pointer`:
con el ratón abría, y sin ratón no había forma de llegar al detalle. Ahora tiene `tabIndex`, se abre con
Enter o Espacio y se ve el foco. Con corte para que Enter sobre el enlace a la zona navegue a la zona
**sin** abrir además el perfil —el evento sube, y sin el corte se habrían hecho las dos cosas.

Comprobado en las cuatro pantallas con tabla: **74 filas** clicables, **74** con teclado, **0** que se
salgan de su columna. Enter abre el detalle en las tres: dos navegan y una abre el diálogo.

### Una corrección mía

Una prueba intermedia dio **422** en `/tickets/abiertos` y parecía una regresión. No lo era: esas rutas
no existen. Las reales son `/panel/tickets`, `/panel/mis-asignaciones` y `/panel/cerrados`, y lo que
recibía era `/panel/tickets/:id` con `id` = «abiertos». Mi sonda apuntaba a direcciones inventadas.

### Verificación

**114 pruebas backend en verde.** `tsc` sin errores, ESLint con 0 errores (los mismos 6 warnings de
siempre) y `verify:clases` en verde (37/37 y 81 archivos).

En el navegador, contra la instalación real: el alta entra sin desplazarse y cada campo explica qué se
escribe; el buscador no se rellena solo ni lo rellena el navegador; buscar algo inexistente ofrece
volver; los cuatro filtros alineados a 260 px; la ubicación dentro de su celda; el perfil en tres
bloques; la fila se abre con Enter. **10 pantallas: 0 peticiones fallidas, 0 errores de consola.**

**No se escribió nada en tu base**: el alta se canceló y el perfil se cerrado sin tocar nada.

## BT - El perfil de la persona: iconos, color de zona, números parejos y foto

Lo que se pidió: que no haya números dispares, que faltaba contraste y relleno, que no sea todo
blanco, iconos profesionales, color en zona y oficina, mejor diseño y poder subir una foto.

### 1. Los números, que ya no se leen dispares

Antes «0» (tickets), «1 equipo» y «Activada» eran lo mismo con tamaños distintos según cupiera: el
cero grande, el uno pequeño y una palabra al lado. Ahora las tres son **métricas** con la misma caja,
el mismo cuerpo (**24 px**), el mismo icono y **cifras de ancho fijo** —sin eso el 1 se ve más estrecho
que el 8 y la fila parece torcida—, y debajo una línea que dice qué significa ese número: «Ninguno
pendiente», «a su cargo», «Sugiere soluciones». El 0 ya no es un dato pelado: es «ninguno pendiente».

### 2. Iconos y color de zona

Cada dato lleva su dibujo: zona (pin), oficina (edificio), cargo (maletín), teléfono (teléfono), y en
las métricas un ticket, un edificio y el robot de la IA. Los equipos usan `IconoTipoEquipo`, el mismo
mapa de los catorce tipos del catálogo.

La cabecera del perfil lleva una **banda con el color de la zona** y el **anillo del avatar** con el
mismo color. No es un color nuevo: es `--zona-N`, el mismo que usan `ZonaBadge` y `EnlaceOficina`, así
que la zona se reconoce de un vistazo y con el mismo código en toda la aplicación. Sin zona no se
inventa color: se queda el fondo del diálogo, que es lo que ya se veía.

### 3. Relleno: deja de ser un bloque blanco

Los datos ya no son líneas sueltas: son **tarjetas** con fondo de superficie y borde de 1 px. En tema
claro la tarjeta es `#f7f9fc` sobre un diálogo `#ffffff` — dos planos, no un vacío. Antes todo el
diálogo era el mismo blanco y los rótulos flotaban sin nada detrás.

### 4. Contraste: medido, no estimado

Medido componiendo el alfa real de cada capa en un lienzo y leyendo el píxel, que es lo que hace el
navegador al pintar. Los siete textos del perfil:

| texto | tema claro | tema oscuro |
| --- | --- | --- |
| nombre | 16,3:1 | 13,79:1 |
| correo | 6,89:1 | 7,89:1 |
| rótulo de tarjeta | 6,54:1 | 7,41:1 |
| dato | 15,45:1 | 12,95:1 |
| cifra de métrica | 15,45:1 | 12,95:1 |
| rótulo de sección | 6,89:1 | 7,89:1 |
| código de equipo | 6,65:1 | 7,51:1 |

**Los siete por encima de 4,5:1 en los dos temas.** Con esto hay que ser honesto: el texto **ya pasaba**
antes del rediseño —usaba los mismos tokens— así que lo que se corrige aquí no es un incumplimiento,
es que los datos principales pasan a peso fuerte y dejan de apoyarse en el gris secundario.

### 5. Foto de perfil, de extremo a extremo

* **`POST /usuarios/{id}/foto`** acepta la imagen; **`GET`** la sirve; **`DELETE`** la quita.
* **Se mira el contenido, no el nombre del archivo.** Reutiliza la validación de los adjuntos, que
  comprueba los primeros bytes: un PDF con extensión `.png` se rechaza con 422. Es lo que distingue
  esto de un campo de archivo cualquiera —sin esa comprobación, quien tenga `usuarios.editar` podría
  dejar en el servidor un script disfrazado de foto, servido desde el mismo origen que la aplicación—.
* **Límite de 2 MB**, comprobado en el navegador antes de gastar la subida y en el servidor después.
* **Permisos**: la foto de uno mismo siempre; la de otro, quien tenga `usuarios.editar`. Y **ver** la
  foto de otro sigue el mismo límite que ver su perfil: una cuenta normal solo ve la suya.
* **La imagen no se pide con `src`**: esa ruta lleva la cabecera de autorización y un `src` no puede
  mandarla. Se pide como blob y se pinta con una URL temporal, con **caché en el módulo** para que la
  misma persona no se descargue la foto una vez por cada sitio donde sale.
* Cambiarla o quitarla borra el archivo anterior del disco: subir un JPG después de un PNG no deja los
  dos.

No hizo falta migración: el campo es opcional y se lee con `.get()`, sin índice.

### Dos correcciones mías

* Una comprobación intermedia dio que la cabecera **no** llevaba color de zona. Era la sonda: pedía el
  primer `<header>` del diálogo y cogía el de la barra de título, no el del perfil. El color sí estaba.
* Las primeras cifras de contraste en tema oscuro salían **1,18:1** y **2,06:1**, imposibles. La
  función de medición reiniciaba el lienzo en cada capa, así que solo pintaba la última. Corregida y
  con una comprobación de fiabilidad: si el lienzo no entiende un color, `fillStyle` conserva el valor
  anterior y el resultado sería falso en silencio.

### Verificación

**122 pruebas backend en verde** (8 nuevas en `test_usuarios_foto.py`: guarda y sirve; un PDF disfrazado
de PNG se rechaza; un documento no es una foto; nadie cambia la foto de otro; uno mismo sí puede subir
la suya; una cuenta normal no ve la foto ajena pero sí la propia; quitar borra el archivo del disco; y
subir dos veces no deja archivos sueltos).

`tsc` sin errores, ESLint con 0 errores (los mismos 6 warnings) y `verify:clases` en verde (37/37, 84
archivos).

`Avatar` y `PersonaFila` son compartidos por toda la aplicación, así que se pasaron **10 pantallas**:
**335 avatares**, **0 vacíos**, **0 imágenes rotas**, **0 desbordes**, **0 peticiones fallidas** y **0
errores de consola**.

El compilador también cogió una errata mía: había puesto `ativo` donde el componente espera `activo`.

## BU - El buscador «busca algo al azar»

### Lo que es y lo que no es

**La aplicación no escribe en el buscador.** Medido abriendo y cerrando cuatro perfiles, con ratón y
con teclado: el valor no se movió ni una vez, el foco fue al diálogo y volvió al cuerpo, y de **8
peticiones** a `/api/usuarios` solo **1** llevaba `texto=`, la que escribí a mano.

**Pero tampoco lo vigila.** El campo es controlado, así que cualquier valor que aparezca en él se
convierte en filtro sin preguntar. Reproducido con el setter nativo de `HTMLInputElement`, que es
justo lo que hace el autocompletado del navegador: el campo se llenó con `jurasicopar@gmail.com` y la
aplicación salió con `GET /usuarios?texto=jurasicopar@gmail.com` y la lista pasó de **267 cuentas a
0**. Con `autocomplete="off"` y un `name` único puestos, igual.

Eso es lo que se veía: la lista filtrada por un texto que nadie había escrito en ese momento, sin más
pista que el texto dentro del campo.

### Las dos cosas que se cambian

1. **El campo ya no es `type="search"`.** Es `type="text"` con `role="searchbox"`, que es a lo que se
   engancha la memoria de búsqueda del navegador por origen. Se conserva el significado para el
   lector de pantalla y la aspa de limpiar la pone el propio componente.
2. **El filtro puesto se ve y se quita de un clic.** Bajo el campo aparece «Filtra por **ADMIN** ✕».
   Aunque el texto venga de donde venga, ahora se ve qué está filtrando la lista y se quita sin
   vaciar el campo a mano.

No se puede tapar de dónde sale el texto —eso es del navegador— pero sí que parezca que la aplicación
busca sola.

### Una etiqueta de más que salió de la ronda anterior

Al pasar `SearchInput` a pintar su propio rótulo, en Equipos se quedó **duplicado**: la pantalla
tenía su propio `<label htmlFor="buscar-equipos">` y además el que pone el componente. Como ese id
no existe —el real lo genera `useId`— la etiqueta de fuera no iba con nada y se veían dos «Buscar
equipos» encima. Fuera.

### Dos falsas alarmas mías

Informé que la barra de Equipos quedaba **150 px** descentrada. No era así: el buscador y los dos
primeros desplegables están **exactamente alineados** (los tres con `top` = 184). Mi sonda cogía un
desplegable de la **segunda fila** de la rejilla y comparaba bases de líneas que no están en la misma
fila.

### Verificación

**122 pruebas backend en verde**, `tsc` sin errores, ESLint con 0 errores, `verify:clases` en verde.

En el navegador: el campo es `type="text"` con `role="searchbox"`; buscando a mano aparece «Filtra por
ADMIN» y el total y las filas cuadran; el filtro se quita con un clic y vuelven las **267** cuentas;
abrir y cerrar tres perfiles con un filtro puesto no lo mueve; y si el navegador escribe algo, sale la
pastilla con ese texto y se quita en un clic.

Como el campo es compartido, se pasaron **7 pantallas con buscador** (Bandeja, Mis asignaciones,
Equipos, Zonas y oficinas, Usuarios y Conocimiento): todas con `type="text"`, todas con su rótulo, y
**0 peticiones fallidas y 0 errores de consola**.

## BV - Quitar el filtrado automático, y el error de cambiar la foto

### El buscador ya no filtra mientras se escribe

Es lo que se pidió, y además cierra el problema de raíz: si la lista no se filtra hasta confirmar,
**ningún texto que aparezca solo en el campo puede convertirse en filtro**.

Antes cada tecla llamaba a `alCambiar` y saltaba una petición. Ahora hay dos estados —lo que se está
**escribiendo** y lo que está **aplicado**— y se escribe libremente; al confirmar con Enter o con el
botón, lo escrito pasa a aplicado. Mientras haya algo sin aplicar, el campo lleva el borde
discontinuo y debajo sale «Sin buscar todavía · **Buscar «ADMIN»**». La aspa limpia y aplica de una
vez, porque quitar un filtro no necesita confirmación, y Escape también limpia.

El cambio va en `SearchInput`, no pantalla por pantalla: si el comportamiento es que no filtra solo,
tiene que ser en los siete sitios. En la galería de componentes el buscador llevaba `valor=""` fijo y
`alCambiar` vacío, y con el botón de buscar nuevo eso era un callejón sin salida; ahora tiene estado.

Medido en Usuarios: escribiendo `ADMIN` la lista se queda en **267 cuentas** y salen **0 peticiones**.
Al confirmar, **4 cuentas**. Con `LEYVA`: 267 sin Enter, **3** con Enter.

### El error de cambiar la foto: era mío, y grave

La subida llevaba dando **500** desde que se desplegó, y era culpa mía: arreglé la anotación en el
código fuente pero **nunca reconstruí la imagen del backend** — solo la del frontend. El contenedor
seguía con la versión anterior, donde `Annotated["UploadFile", File()]` con
`from __future__ import annotations` deja el tipo sin definir y FastAPI revienta antes de llegar al
servicio.

Lo encontré en los registros del servidor: dos `PydanticUserError` y un `POST .../foto` con
`500 Internal Server Error`. Lo mismo pasaba con `GET /api/openapi.json`.

Comprobado, solo lectura, que **no quedó nada a medias**: **0 cuentas** con el campo `foto` y la
carpeta `/data/uploads/fotos` ni existía. Ningún intento se guardó a medias.

Con la imagen reconstruida, `openapi.json` responde y la subida llega a la validación: mandando un
PDF por la interfaz real responde **422** y en pantalla sale «La foto debe ser una imagen», no un 500
a secas.

**Lo que no vi entonces y debo decirlo:** en la ronda anterior comprobé que las tres rutas de foto
existían en el contenedor y lo di por bueno. Las rutas existían, pero el endpoint no arrancaba. Contar
rutas no es comprobar que funcionen.

### Verificación

**122 pruebas backend en verde**, `tsc` sin errores, ESLint con 0 errores, `verify:clases` en verde.

Las **7 pantallas con buscador**, medidas por número de resultados y contando solo las peticiones que
llevan el parámetro de búsqueda: **ninguna filtra al escribir**, todas avisan de lo pendiente,
todas aplican con Enter y todas limpian con la aspa. Las tres que no usan tabla (Zonas y oficinas,
Conocimiento y Mis avisos del portal) se comprobaron aparte contando tarjetas.

Para la foto no se escribió nada en la base: se mandó un PDF, que el backend rechaza antes de guardar.

## BW - Vuelve a filtrar al escribir, y el navegador deja de rellenar el buscador

### Lo que estaba mal

La ronda pasada interpreté mal el encargo: quitó el filtrado automático. **Se ha deshecho.** Filtrar
mientras se escribe es lo que se quiere —cada letra acorta la lista y así uno se ubica—, y el problema
era otro: que el campo se llenara solo.

### De dónde venía el correo en el buscador

Medido en el código: `setTexto` solo se llama en dos sitios, al teclear y al pulsar «Quitar los
filtros». **La aplicación nunca escribe en ese campo por su cuenta.** Como el campo es controlado,
cualquier valor que aparezca se vuelve filtro —y con el filtrado automático, petición inmediata—, así
que el texto tenía que ponerlo el navegador.

Y el motivo estaba a la vista, en el propio campo:

* El `placeholder` era **«Nombre o correo…»**. **«Correo» es exactamente la palabra con la que el
  navegador decide que un `type="text"` es un campo de dirección** y le ofrece rellenarlo con una
  dirección guardada.
* El `name` era `«…-busqueda»», que apunta al mismo tipo de memoria.

### Las cuatro cosas

1. **El placeholder ya no dice «correo»**: es «Escribe para filtrar…». Sin palabras de correo ni de
   identidad, el navegador no lo toma por un campo de dirección.
2. **El `name` es neutro** («…-filtro»).
3. **`data-1p-ignore`, `data-lpignore` y `data-form-type="other"`**, porque 1Password y LastPass hacen
   lo mismo que el navegador y con más insistencia.
4. **Al pulsar el campo se selecciona todo lo que haya**, para que la siguiente tecla lo sustituya en
   vez de quedarse detrás. Va en `onClick` y no en `onFocus` porque el clic coloca el cursor después
   de que el campo reciba el foco: con `onFocus` la selección salía `[14,14]`, o sea el cursor al final.

### Verificación

**122 pruebas backend en verde**, `tsc` sin errores, ESLint con 0 errores, `verify:clases` en verde.

Volviendo a filtrar al escribir: en Usuarios, escribiendo `ADMIN` la lista pasa de **267 a 4 cuentas**
con **5 peticiones** —una por tecla—, sin ningún aviso de «Sin buscar todavía». La aspa y **Escape**
limpian y devuelven las 267.

Contra el autocompletado: el placeholder y el `name` ya no contienen «correo», «email», «usuario» ni
«login», y las marcas de los gestores están puestas. Metiendo a mano un valor como haría el navegador
—con el setter nativo— y pulsando el campo, queda **seleccionado de 0 a 19**: la siguiente tecla lo
sustituye entero.

Las **7 pantallas con buscador** revisadas una a una: ninguna conserva pistas en el placeholder ni en
el `name`, y todas tienen las marcas. **0 peticiones fallidas y 0 errores de consola.**

## BX - El filtro volvía solo en cada reinicio

### Lo que cambia el diagnóstico

Que el texto **sobreviviera a un reinicio** descarta que fuera el campo quien se llenara al pulsar. Es
que el valor **persistía**.

Descartadas las dos causas de la aplicación, comprobado en el código:

* **No se guarda en `localStorage`**: en Usuarios lo único que se guarda es la preferencia de mostrar
  cuentas desactivadas.
* **No va en la URL**: `texto` arranca siempre en `''` y de los parámetros solo se lee `crear`.

Lo que queda es **el navegador guardando los valores del formulario en tu perfil y reaplicándolos al
cargar**. Chrome y Edge en Windows lo hacen al recargar, al ir «atrás» y al reiniciar el navegador, y
`autocomplete="off"` no lo para: ese atributo controla el autocompletado de formularios, no la
restauración de sesión.

### Cómo se tapa

En **dos sitios**, porque son dos momentos distintos:

1. **El campo no se pinta hasta después del primer render.** Si el `<input>` no existe cuando el
   navegador restaura, no hay dónde escribir. Medido: a los primeros instantes de cargar hay **0
   campos** de búsqueda en el documento; a los 3 s hay **1**.
2. **Al volver de la caché de páginas** —ir «atrás» y volver— el campo ya existe, así que se vacía a
   mano con el **setter nativo** de `HTMLInputElement`. Hace falta el nativo porque al asignar
   `elemento.value` se pasa por el rastreador de React, que cree que el valor no ha cambiado y no
   reacciona.

Solo se toca el valor cuando **difiere del de la aplicación**: un filtro puesto a propósito se
respeta, y teclear no se entera, porque al teclear el valor del campo y el de la aplicación van juntos.

### Verificación

**122 pruebas backend en verde**, `tsc` sin errores, ESLint con 0 errores, `verify:clases` en verde.

Escribir **sigue filtrando al instante**: `ADMIN` lleva la lista de **267 a 4** mientras se teclea.

Tres recargas seguidas: campo vacío y **267 cuentas** en las tres. Ida y vuelta por otra pantalla:
campo vacío. Volver de «atrás»: no aparece nada que no se hubiera escrito. Las **7 pantallas**, campo
vacío al cargar en todas. **0 peticiones fallidas y 0 errores de consola.**

La barra de filtros sigue cuadrada: campo y los tres desplegables con la base en **260 px**.

**Lo que no pude medir aquí:** el navegador de las pruebas no restaura los valores de formulario, así
que el fallo original no se reproduce en él. Lo que sí se comprueba es que la estructura ya no tiene
hueco por donde restaurar, que es lo que lo hacía posible. Si aun así te apareciera, habría que mirar
una extensión o el gestor de contraseñas del navegador.

### De paso

En la tabla de Usuarios se ve ya la **foto de A. JURIDICA** en su avatar: es la primera foto subida
desde que se arregló la imagen del backend en la ronda BV. Confirma que la subida funciona.

## BY - El selector de persona escribía en su propio buscador

### Lo que estaba pasando de verdad

Auditado todo el proceso, el fallo **no estaba en el directorio de Usuarios** sino en otro sitio que
tenía el mismo síntoma: el selector **«A quién afecta»** del registro manual de tickets
(`/panel/tickets/nuevo`).

Reproducido:

1. Se escribe `LEYVA` → aparecen 3 sugerencias.
2. Se elige «DEYSI LEYVA MINAYA» → **el campo se rellena con ese nombre** y sale una petición
   **nueva**: `/api/usuarios/buscar?texto=DEYSI LEYVA MINAYA`, con la lista de sugerencias
   **quedando abierta** mostrando solo a esa misma persona.

La causa es una línea, en el manejador del botón:

```tsx
setPersonaId(persona.id)
setPersonaNombre(persona.nombre)
setTextoPersona(persona.nombre)   // ← el nombre va al campo de búsqueda
```

Y como el campo alimenta la búsqueda, escribir el nombre de la persona elegida **lanza otra búsqueda**.
Si a alguien se le busca por correo y no tiene cuenta, el campo se queda con el correo y la lista
filtrada por él: exactamente «al seleccionar un usuario, el buscador busca solo».

### Lo que se cambia

* **Con una persona ya elegida no se busca.** La consulta queda apagada mientras haya elección, y la
  lista de sugerencias se cierra. El campo sigue mostrando el nombre de la persona elegida, que es lo
  normal en un selector y lo que confirma que está elegida.
* **La lista solo se pinta si la consulta está encendida.** Sin eso, al vaciar el campo la consulta se
  desactiva pero React Query **conserva el último resultado**: la última persona encontrada se quedaba
  colgando bajo un campo vacío. Este segundo fallo lo encontró la prueba de proceso, no la lectura del
  código.
* El campo, que es un `<input>` escrito a mano y no el `SearchInput` común, recibe la misma
  protección: placeholder **sin «correo»** —esa palabra es la que hace que el navegador ofrezca
  rellenarlo solo—, `name` neutro, marcas de gestores de contraseñas, selección al pulsar, y limpieza
  al montar y al volver de «atrás» con el setter nativo.

### El dato de fondo: la cuenta se estaba buscando mal

Leyendo la base, solo lectura:

```
Jorgue Peña  <jurasicpar@gmail.com>   activo=true
```

El correo es **`jurasicpar@gmail.com`**, **sin la «o»** que aparecía en el campo. Buscando
`jurasicopar@gmail.com` salen **0 cuentas** —siempre 0—, y el navegador guardaba ese texto sin
encontrar para devolverlo en cada reinicio. Lo que se veía «buscarse solo» era la búsqueda fallida
de una cuenta escrita con una letra de más.

Comprobado en pantalla: `jurasicpar@gmail.com` → **1 cuenta (Jorgue Peña)**;
`jurasicopar@gmail.com` → **0**, con el aviso y el botón de volver.

### Verificación

**122 pruebas backend en verde**, `tsc` sin errores, ESLint con 0 errores, `verify:clases` en verde.

El selector, paso a paso: elegir → **0 búsquedas** y lista cerrada; elegir a otra persona → igual;
empezar a escribir de nuevo → **deshace la elección** y vuelve a buscar; vaciar → campo vacío y **sin
sugerencias colgando**.

Los filtros encadenados de Usuarios: texto `ADMIN` → 4, más rol administrador → **1** (filtrar nunca
amplía); un texto imposible → 0 filas con el botón de volver y se recuperan las **268** cuentas; la
zona acota las oficinas de 13 a **12** y suelta la oficina anterior; texto y rol juntos → 34 y luego
**0**, con el texto intacto en el campo.

Las **7 pantallas con buscador**: ninguna avisa de nada pendiente, todas tienen aspa y todas limpian.

**0 peticiones fallidas y 0 errores de consola** en todo el recorrido.

**Nota sobre las cifras:** la instalación tiene ya **268** cuentas, no 267 —se creó «Miguel» probando
el alta. Las pruebas leen el total al empezar en vez de llevar el número escrito, para que volver a
crear una cuenta no las haga fallar sin que nada esté roto.