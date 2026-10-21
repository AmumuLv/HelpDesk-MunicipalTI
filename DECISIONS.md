# DECISIONES

Supuestos y decisiones tecnicas del sistema, con su motivo.
Cada una es reversible y esta aislada en un solo lugar del codigo.

## 1. PyMongo asíncrono nativo (`AsyncMongoClient`) en lugar de Motor

**Decisión:** PyMongo ≥ 4.13 con `AsyncMongoClient`.
**Motivo:** Motor quedó en mantenimiento y su successor oficial es el propio driver.
**Consecuencia:** `aggregate()` es una corrutina mientras que `find()` no lo es, por lo que
el proyecto centraliza las agregaciones en `app.core.db.agregar()` para no repetir el error
de esperar en el sitio equivocado.

## 2. Réplica set de un nodo

**Decisión:** MongoDB 8 con `--replSet rs0`, inicializado automáticamente por el servicio
`mongo-init` y del que `api` depende con `condition: service_completed_successfully`.
**Motivo:** las importaciones masivas y el "deshacer" por lote usan transacciones
multi-documento, que exigen réplica set.
**Consecuencia:** el despliegue sigue siendo de un solo nodo; en produccion se puede apuntar
`MONGO_URI` a un cluster sin cambiar codigo.

## 3. Las fechas se guardan como texto ISO

**Decisión:** feriados, ausencias y fechas de campaña se almacenan como `"AAAA-MM-DD"`.
**Motivo:** BSON no tiene un tipo "solo fecha" y PyMongo lanza error al codificar
`datetime.date`. Un texto ISO además se compara correctamente en las consultas
(`{"fin": {"$gte": "2026-10-05"}}`) y evita las zonas horarias ambiguas.
**Consecuencia:** los helpers `fecha_iso()` y `a_fecha()` de `app/core/time.py` son el único
punto donde se convierte. Las marcas de tiempo (`creado_en`, `actualizado_en`, deadlines)
siguen siendo `datetime` UTC reales.

## 4. Identificadores en la respuesta: siempre `id`

**Decisión:** la API expone `id`; el nombre interno `_id` se renombra en la capa de rutas con
`app.core.serializacion.normalizar`.
**Motivo:** el frontend necesita un unico nombre de clave en toda la aplicacion.
**Consecuencia:** los servicios siguen hablando el idioma de MongoDB.

## 5. Serialización de respuestas propia

**Decisión:** `JSONApiResponse` con `default=` para `ObjectId`, fechas y modelos, y
`ObjectId` registrado en `ENCODERS_BY_TYPE` de FastAPI.
**Motivo:** las capas de servicio devuelven documentos crudos con `ObjectId`; sin esto,
FastAPI responde 500 al serializar.
**Consecuencia:** ninguna ruta necesita convertir identificadores a mano.

## 6. Permisos: base por rol + matriz delegable, aplicada en el backend

**Decisión:** `PERMISOS_BASE` define lo que el rol puede hacer por naturaleza;
`PERMISOS_DELEGABLES` (20 permisos) empieza **todo en `False`** y lo activa el administrador.
El frontend oculta controles por comodidad, pero ninguna ruta confía en eso: cada endpoint
declara `Depends(requiere("..."))`.
**Supuesto documentado:** el permiso `horarios.editar_propio` también empieza apagado, tal
como pide el requerimiento, de modo que un técnico recién creado no edita su horario hasta que
el administrador lo habilita.
**Consecuencia:** todo cambio de permiso queda en auditoría con el antes y el después.

## 7. El chat depende del origen del ticket, validado en el servidor

**Decisión:** `ticket_service.tiene_chat()` es el único lugar que decide. El endpoint de
mensajes devuelve 403 con código `sin_chat` si el ticket fue creado por el equipo TI.
**Motivo:** la regla es de negocio, no de presentación; ocultarla solo en la interfaz dejaría
el hueco abierto.
**Consecuencia:** si un usuario con cuenta adopta el ticket, se habilita el chat y se registra
el cambio de origen en la línea de tiempo.

## 8. Los campos incompletos avisan, nunca bloquean

**Decisión:** los únicos datos obligatorios de un activo son **tipo** y **oficina**. El resto
tiene tres estados: `pendiente`, `no_aplica` y `no_disponible`. Los dos últimos salen del
denominador de completitud y se muestran distintos de un campo vacío, también en las
exportaciones.
**Motivo:** hay CPU sin código patrimonial y equipos con datos que nadie conoce; obligar
produciría datos falsos.
**Consecuencia:** la completitud es una medida de calidad del inventario, no una puerta.

## 9. Idempotencia de la importación

**Decisión:** el índice único de código patrimonial es **parcial** y solo aplica a valores de
tipo texto (`partialFilterExpression: {codigo_patrimonial: {$type: "string"}}`). Los equipos sin
código se identifican con `clave_natural` = oficina + conjunto + dispositivo + índice.
**Motivo:** muchos equipos no tienen código y `-` significa "no aplica", no "el valor -".
**Consecuencia:** reimportar el mismo archivo actualiza en lugar de duplicar; por eso el
índice necesitó su propia migración (`m005`).

## 10. La IA nunca es un requisito para que funcione el sistema

**Decisión:** la clasificación de categoría y prioridad, la sugerencia de asignación, la
completitud y los SLA se calculan con **reglas y modelos entrenados con datos reales**
(scikit-learn), no con el modelo de lenguaje. El LLM solo aporta resumen, causa raíz y
respuesta sugerida, y si no está disponible el sistema lo dice y sigue funcionando.
**Motivo:** una municipalidad no puede dejar de emitir tickets porque el proveedor de IA esté
caído, y ninguna función crítica puede depender de un servicio externo.
**Consecuencia:** `ia_provider` es una interfaz única; cambiar de proveedor es una variable de
entorno.

## 11. Recomendaciones de IA: la persona decide y puede apagarlas

**Decisión:** cada persona tiene un interruptor individual y persistente. Cuando está apagado,
el backend **no devuelve** sugerencias, pero sigue registrando la señal de aprendizaje en
`ia_eventos` con la marca `recomendacion_visible: false`.
**Motivo:** "la IA explica y propone; el humano decide", y además nadie debe ver
recomendaciones que pidió no ver.
**Consecuencia:** el interruptor global de la institución es independiente y también queda en
auditoría.

## 12. Honestidad estadística

**Decisión:** cuando faltan datos se responde `suficiente_datos: false` con el mínimo
requerido, en lugar de inventar. La predicción de fallas declara su método (`modelo_entrenado`
o `regla_heuristica`), su probabilidad, horizonte, confianza y fecha de actualización.
**Consecuencia:** con pocos equipos el panel muestra "Datos insuficientes (mínimo 30)".

## 13. El horario gobierna todo el sistema

**Decisión:** horario, días libres, ausencias y feriados determinan disponibilidad, cálculo de
SLA, capacidad, carga y los reportes de desempeño, todo normalizado por horas laborables
reales. No existe un "día libre" que se interprete como inactividad.
**Consecuencia:** al asignar a alguien fuera de horario la API pide confirmación explícita.

## 14. Importación por lote transaccional con reversión

**Decisión:** la confirmación se ejecuta dentro de una transacción; cada activo creado queda
marcado con su lote. "Deshacer" borra lo creado solo si ningún equipo fue modificado después y
no tiene tickets asociados.
**Motivo:** un archivo de cientos de filas puede fallar a mitad y dejar el inventario a medias.

## 15. Campañas de inventario sin pérdida de historial

**Decisión:** al crear una campaña se congela una instantánea; los equipos ausentes en el
Excel **nunca se borran**, pasan a "por verificar"; el cierre guarda una versión histórica
consultable y comparable entre años. Los tickets antiguos siguen vinculados al activo aunque
cambie de oficina o se dé de baja.

## 16. Un solo comando para levantar todo

**Decisión:** `docker compose up -d` levanta mongo (con réplica set), redis, api, worker y
web detrás del proxy. Los datos de demostración se cargan con un comando aparte
(`python -m app.scripts.demo cargar`) y quedan marcados con `demo: true`.
**Consecuencia:** nunca se mezclan datos de ejemplo con datos reales; se pueden eliminar con
`demo eliminar`.

## 17. Pruebas sobre Docker

**Decisión:** las pruebas levantan su propio MongoDB en réplica set y su Redis dentro de
contenedores efímeros. Si Docker no está disponible, la suite se omite con un mensaje claro en
lugar de fallar.
**Motivo:** las transacciones y el paralelismo de las pruebas exigen condiciones reales; un mock de
base de datos no detectaría los errores que más duelen en este sistema (índices parciales,
validadores, `await` mal colocado).
**Nota:** las pruebas de integración del frontend usan Playwright contra el stack completo.
## 18. Verificación por fases e inventario estable

Las pruebas automatizadas usan MongoDB y Redis de prueba. Los scripts `humo` y
`verificar_web` sí escriben usuarios, activos, tickets o exportaciones; no son
comprobaciones de solo lectura y deben apuntar a un despliegue desechable, no a
la base municipal. La comprobación web necesita `VERIFICAR_HOST` si se ejecuta
desde un contenedor. El orden usa collation española numérica y desempate por
id. El filtro de responsables consulta cuentas activas y evita duplicar estado.
La caché de esquemas caduca a los dos segundos y las escrituras recalculan
calidad. El repositorio Git está en la carpeta Desktop superior al proyecto,
por lo que los commits se limitan a rutas explícitas de `helpdesk-municipal`.

## 19. Colores, agrupación y atajos del portal

Las zonas existentes reciben `color_indice` de forma estable por orden de
identificador; las nuevas zonas avanzan en ciclo entre los ocho tokens. Como
la API no entrega un ranking de problemas frecuentes, el portal muestra hasta
seis tipos configurados que realmente devuelve la API y no los presenta como
una estadística calculada. El inventario mantiene el orden estable zona,
oficina, conjunto, tipo e id; el selector cambia la presentación de ubicación
sin habilitar reordenamientos que separen equipos de una misma oficina.

## 20. Tipos de respuestas con listas vacías

La captura de formas reales puede devolver listas vacías en ausencia de avisos,
ausencias o campañas. Regenerar los tipos desde esa muestra produjo `unknown`
en varias respuestas y no pasó TypeScript. Se conserva la versión de tipos
validada; no se inventan registros para completar la muestra. La recolección
de formas se genera localmente y se ignora; deberá complementarse con tipos
explícitos para colecciones vacías antes de volver a generar `respuestas-api.ts`.

## 21. Pruebas visuales sin artefactos

Playwright comprueba desbordamiento, foco visible, accesibilidad y errores de
consola en móvil, tableta y escritorio. Las pruebas no guardan capturas; los
resultados generados por Playwright quedan fuera del repositorio.

## 22. Validaciones de formularios alineadas con la API

Los formularios muestran los errores 422 en su campo cuando la API los entrega
con `campo` y `mensaje`, y solo generan un aviso global para errores no ligados
a campos. La exportación mantiene `xlsx` como etiqueta visual, pero envía
`excel`, que es el valor aceptado por el contrato. Se conserva `Enfermedad`
como tipo válido de ausencia, igual que el formulario ya lo ofrecía.

## 23. Flujos de tickets, usuarios y contenido

Cerrar un ticket activo requiere registrar primero su resolución y luego
cerrarlo; reaperturas y cambios de estado respetan las transiciones permitidas
por la API. Las listas de varios estados se serializan como parámetros de
consulta repetidos, tal como los recibe FastAPI.

El restablecimiento de contraseña es una acción de administración separada de
la edición del perfil y revoca las sesiones existentes de la persona objetivo.
Las fechas ISO de filtros de exportación se convierten a fechas antes de
consultar. Campañas y artículos usan los nombres de campo que exige la API; la
lista de artículos evita repetir el mismo título dentro de su categoría.

Los verificadores que escriben zonas, usuarios, activos, tickets o
exportaciones deben ejecutarse contra una base de prueba aislada. Al comprobar
el inventario real, la cantidad de activos debe mantenerse en 875; no se deben
dejar los registros de humo en la base municipal.

## 24. Identificadores repetidos en inventario y vista previa

El código patrimonial, la IP y la MAC repetidos son advertencias, no bloqueos:
pueden ser legítimos y la persona debe poder registrar el equipo de todos
modos. El endpoint de duplicados devuelve las fichas existentes para revisarlas.
`m009` elimina el índice único del código y conserva un índice de búsqueda
normal; la clave natural del activo sigue siendo única para evitar duplicar una
misma fila de importación.

La plantilla oficial queda sin filas ficticias. La hoja `Instrucciones` no se
considera inventario al leer un libro. La importación usa la detección automática
y deja una vista previa con excepciones, sin pedir un paso de mapeo manual. No
se ejecutan verificadores que creen datos contra el Compose municipal activo;
se usa MongoDB/Redis temporales cuando hace falta probar escrituras.

## 25. Alcance de lectura y edición de ausencias

El equipo con `horarios.ver_todos` puede consultar las ausencias de todos los
técnicos y filtrar por persona; quien no tiene ese permiso solo consulta sus
propias ausencias. La API exige `horarios.editar_propio` para registrar o quitar
una ausencia propia y `horarios.editar_todos` para modificar la de otra persona.
La interfaz oculta las acciones que no permite el permiso correspondiente.

## 26. Textos breves de ayuda automática

Los mensajes estáticos de IA visibles en la interfaz viven en
`frontend/src/dominio/textos-ia.ts`; `tools/verificar-textos-ia.mjs` revisa que
no excedan 100 caracteres. Los textos explicativos que produce el backend se
recortan a 90 caracteres. Se evita exponer nombres técnicos del proveedor o del
modelo cuando no ayudan a quien reporta o administra.

## 27. Tema claro y oscuro, con el claro como referencia

**Decisión:** los dos temas existen y el interruptor funciona. El claro
institucional es el tema de referencia y el que se aplica por defecto; el oscuro
existe porque quien trabaja de noche en una sala de monitores lo necesita, y su
elección se guarda en `localStorage` (`ma.tema`).
**Motivo:** se llegó a decidir por una sola paleta clara y el interruptor se
quedó puesto en el código. Resultaba engañoso: aparecía la luna, no producía
ningún cambio visible y el tema acababa determinado por la preferencia del
sistema. Quitar el selector es una cosa; dejar un selector que no funciona es
peor.
**Consecuencia:** `data-tema` en `<html>` es el único interruptor. Los dos temas
redefinen LOS MISMOS tokens, así que ningún componente sabe en cuál está. El
script de arranque de `index.html` lo aplica antes de pintar para que no haya
parpadeo, y escribe `light`/`dark` en `<meta name="color-scheme">` (no «claro» ni
«oscuro»): el navegador descarta los valores que no entiende, y con ellos los
controles nativos se quedan con el aspecto equivocado. Un control que vive sobre
la barra de navegación se pinta con tokens `nav-*`, no con los de la página.

## 28. El relieve lo da la sombra, no el borde

**Decisión:** en el tema claro la caja blanca se separa del fondo azul suave con
una sombra en dos niveles (`--sombra-tarjeta` en indicadores y fichas,
`--sombra-md` en los paneles) y el borde baja a `--t-borde` (#CBD5E4). Los campos
de formulario no siguen esa regla: usan `--t-input`, más firme, porque su
contorno es la única señal de que se puede escribir ahí.
**Motivo:** con el blanco al frente y el borde como único separador, los bordes
dominaban la pantalla y las tarjetas se leían como una rejilla de casillas. La
sombra da profundidad y el borde vuelve a ser un detalle.
**Consecuencia:** el azul de la acción (#2A61F2) y el texto que va encima
(`--t-accion-texto`: blanco en claro, oscuro en oscuro) están medidos para llegar
a 4.5:1. Los indicadores se comprueban con axe en los dos temas y no arrojan
violaciones graves.

## 29. `cn()` agrupa por propiedad CSS, no por prefijo de Tailwind

**Decisión:** `frontend/src/lib/cn.ts` convierte cada clase en la clave de la
propiedad que realmente escribe, en vez de agruparla por el prefijo.
**Motivo:** Tailwind reparte varias propiedades bajo el mismo prefijo, y hay dos
fallos distintos que salían de la misma simplificación:

1. `text-2xl` (tamaño) y `text-foreground` (color) empezaban las dos por `text-`,
   así que el color se comía el tamaño: un indicador de tono neutro salía con la
   cifra al tamaño del texto y uno con tono de color salía grande.
2. `flex` (display) y `flex-col` (dirección) empezaban las dos por `flex`, así que
   `flex` desaparecía y el contenedor dejaba de ser flex. Lo mismo con `grid` y
   `grid-cols-2`, y con `text-center` frente a un color. El síntoma visible era el
   estado vacío descentrado y las rejillas que no ocupaban su columna.

**Consecuencia:** hay una tabla de raíces polimórficas (`flex`, `grid`, `text`,
`font`, `place`, `align`, `justify`, `overflow`, `min`, `max`) con el sufijo que
pertenece a cada propiedad, y `border` tiene su propia regla porque el orden de
los segmentos decide si es grosor o color. Cuando el sufijo no está en la tabla y
la raíz no declara un valor por defecto, `cn` devuelve `null` y **conserva la
clase**: no se descarta nada que no se pueda asegurar que compite. La variante se
conserva en la clave porque `hover:bg-muted` y `bg-surface` son reglas distintas.
Si un token nuevo colisiona, la tabla es el sitio que hay que ampliar.

## 30. El borrado lógico de un ticket se excluye al listar

**Decisión:** `eliminar` sigue siendo lógico —marca `eliminado`, deja quién y
cuándo, y lo anota en la auditoría—, pero `listar` y `obtener` filtran
`eliminado != true`.
**Motivo:** el borrado lógico sin filtro en la lectura es incoherente: la API
respondía «Ticket eliminado» y el caso seguía en la cola, con su franja de color
y su contador. Además un ticket resuelto que se borra volvía a contar como abierto
en los totales.
**Consecuencia:** `enviar_mensaje` ya excluía los borrados; ahora lo hacen todas
las lecturas. Hay una prueba de regresión que crea un ticket, lo elimina y
comprueba que desaparece de la lista y que su detalle responde 404.

## 31. La insignia de SLA se declara con los valores que emite la API

**Decisión:** `estados.ts` declara el estado de SLA exactamente como lo devuelve
`sla_service.estado_sla`: `seguro`, `atencion`, `critico`, `vencido`,
`cumplido`, `sin_configuracion`.
**Motivo:** la interfaz declaraba `ok`, `por_vencer`, `en_riesgo`, `incumplido` y
`en_pausa`, que no coinciden con ninguno de los seis valores reales, así que
`slaDe` caía siempre en «SLA sin dato»: ninguna insignia de SLA tenía color ni
texto útil en toda la aplicación. Lo mismo pasó con el desplegable de filtro, que
ofrecía `ok`/`por_vencer`/`en_pausa` y el backend solo entiende `riesgo`,
`vencido` e `incumplido`.
**Consecuencia:** el mismo tipo de valores es el que se usa para pintar el color,
el filtro y el significado. Cuando el backend añada un estado, hay que añadirlo en
`estados.ts` o volverá a salir «SLA sin dato» (no se rompe, solo se pierde
información).

## 32. La urgencia se lee de un vistazo, y también se lee con palabras

**Decisión:** cada fila de la bandeja lleva una franja lateral de 3 px en rojo,
ámbar o verde según `tonoUrgenciaTicket`, y encima una leyenda que dice qué
significa cada color.
**Motivo:** recorrer la cola buscando texto obliga a leer columna por columna; el
color da el filtro inicial. Pero el color solo no vale para quien no lo distingue o
usa un lector de pantalla.
**Consecuencia:** la franja es un `box-shadow` interior, no un `border-left`, para
no desplazar las columnas al cambiar de tono; en móvil se repite como borde de la
tarjeta. Las insignias de estado y de SLA siguen diciendo el caso con texto e
icono, así que el color nunca es el único canal.

## 33. Una sugerencia de IA se decide una vez y se guarda el antes

**Decisión:** la recomendación se guarda por clave en
`tickets.ia_sugerencia.decisiones` (`{accion, elegido, anterior, por, en}`) y
`GET /tickets/{id}/ia` la devuelve en `decisiones`. Aplicar **sí cambia el
ticket**: la clave se traduce al campo que corresponde (categoría, prioridad con
recálculo de SLA, técnico sugerido).
**Motivo:** dos fallos que no se veían en el CSS. La interfaz mandaba `clave` y
`valor` y el servicio leía `categoria` y `prioridad`, que llegaban vacías:
«Aplicar» contestaba con éxito sin cambiar nada. Y el servicio recalculaba la
clasificación desde cero sin mirar la decisión, así que la misma sugerencia
reaparecía indefinidamente y había que descartarla otra vez.
**Consecuencia:** al aplicar, la tarjeta se sustituye por una línea que dice el
valor que quedó y cuál había antes; al descartar, por una línea más discreta, en
letra pequeña. Por clave y no con un único estado del ticket, porque se puede
aplicar la categoría y descartar la prioridad. `riesgo_sla` es un dato, no una
decisión, y no lleva botones. Una prioridad escrita a mano que no exista se
ignora: se registra la decisión pero no se guarda un valor que el resto del
sistema no reconoce.

## 34. Una vista guardada declara qué contiene y lo contiene

**Decisión:** el diálogo de «Guardar vista» enumera lo que se va a guardar con su
valor actual, y se guardan filtros, búsqueda y columnas visibles. `DataTable`
acepta `columnasForzadas` para restaurarlas al abrir la vista, y dejan de mandar
en cuanto se toca un filtro a mano.
**Motivo:** el diálogo anunciaba «los filtros y las columnas» pero solo mandaba
filtros, con `columnas` siempre vacío y sin la búsqueda de texto. Guardar algo que
no se guarda, y sin decirlo, es peor que no ofrecer el botón: por eso no se
entendía para qué servía.
**Consecuencia:** el diálogo aclara además que la página no se guarda —al abrir la
vista se muestra desde la primera— y si la vista será compartida según el permiso
`vistas.compartidas`.

## 35. La línea de tiempo lee el detalle, no una ruta inventada

**Decisión:** `Timeline` toma los eventos de `GET /tickets/{id}`, que ya los
devuelve filtrados por rol, en lugar de pedir `/tickets/{id}/eventos`.
**Motivo:** esa segunda ruta no existe en el backend. Cada apertura de ticket
lanzaba un 404 y el componente ocultaba la caja, así que el historial del ticket
—«quién hizo qué y cuándo»— no se había visto nunca, pese a que la API tenía los
datos y el propio comentario del componente decía que venían en el detalle.
**Consecuencia:** una petición menos y el historial visible.

## 36. Resuelto y Cerrado son estados distintos

**Decisión:** se mantienen como estados separados, con la diferencia explícita:
**Resuelto** = hay solución registrada y la persona que lo reportó todavía no la
ha aceptado; **Cerrado** = el caso queda archivado y sale de la cola de trabajo.
**Motivo:** no son sinónimos. En Resuelto el ticket sigue siendo de la persona que
lo reportó: puede reabrirlo dentro de 15 días. En Cerrado el archivo es del
equipo de soporte y reabrirlo exige el permiso `tickets.cerrar_reabrir`. Además
el cierre obliga a pasar por Resuelto, y ambos dejan su propia fecha
(`resuelto_en`, `cerrado_en`), lo que permite medir tiempo de resolución y tiempo
de cierre por separado. Colapsarlos perdería esa medida y relajaría el control de
la reapertura.
**Consecuencia:** la cola por defecto es **Abiertos** (`solo_abiertos`), no
«Todos»: un ticket recién resuelto sale de la lista de trabajo de inmediato, que
era la queja de que siguiera apareciendo entre los activos. Lo terminado vive en
«Cerrados». `?vista=todos` queda como alias de `abiertos` para los enlaces viejos.

## 37. Cerrar y reabrir exige permiso, y la interfaz lo sabe antes de ofrecerlo

**Decisión:** `GET /tickets/{id}` devuelve `puede_cerrar` y `puede_reabrir`, con
la misma regla que aplica `cambiar_estado`: ser el técnico asignado, ser
administrador, o tener `tickets.cerrar_reabrir`. La interfaz usa esas banderas
para no ofrecer el botón, y cuando no puede explica por qué en lugar de dejar que
el servidor responda `403`.
**Motivo:** `tickets.cerrar_reabrir` es delegable y arranca apagado, así que el
caso normal es que un técnico **no** pueda cerrar el ticket de un compañero. El
botón se mostraba igual: se rellenaba el formulario entero para recibir un error.
**Consecuencia:** la regla vive en un solo sitio, `_puede_cerrar`, y la interfaz
no la reimplementa. Hay dos pruebas que la fijan: `puede_cerrar` del asignado
frente al de otro técnico, y el `403 sin_permiso` del servidor.

## 38. La nota de solución se pide en el campo, no se pide al servidor

**Decisión:** para resolver hay que escribir qué se hizo; la interfaz lo comprueba
antes de enviar y muestra el error **en el campo**, sin abrir el diálogo de
confirmación.
**Motivo:** el campo era opcional en la pantalla y obligatorio en el API, así que
se llegaba hasta el final y la respuesta era un `422`. El aviso tello de campo
evita el viaje de ida y vuelta y señala dónde corregir.
**Consecuencia:** el cierre conserva la misma exigencia y sigue pasándose por
Resuelto, con las dos fechas. Reabrir muestra un diálogo de confirmación que nombra
el ticket y el estado al que vuelve, y el desplegable de estados no ofrece la
reapertura: solo se llega por ese botón.

## 39. El equipo del ticket es una columna, no un dato escondido

**Decisión:** la bandeja incluye una columna «Equipo» con el nombre del activo y su
conjunto, visible en escritorio y en la tarjeta de móvil.
**Motivo:** al revisar el historial de casos cerrados, lo que se busca es qué
equipo se reparó, y la tabla no lo mostraba: el dato venía en la respuesta y
nadie lo pintaba.
**Consecuencia:** la columna va con la misma clave que usa el resto de la tabla
(`activo_nombre`, `activo_id`), así que respeta el filtro de columnas
configurables y no requiere campos nuevos en el API.

## 40. La ruta del aviso la decide la interfaz, no el backend

**Decisión:** `CampanaNotificaciones` construye el destino con `ticket_id` según el
rol (`/panel/tickets/{id}` para el equipo TI, `/mis-tickets/{id}` para quien
reporta) e ignora el `enlace` que trae el registro. Si algún registro antiguo no
trae `ticket_id`, se reconoce la forma `/tickets/{id}` y se traduce igual.

**Motivo:** el mismo dato tiene dos rutas según el cascarón, y el backend no sabe
en cuál está quien lee. Guardar una sola ruta en el aviso obliga a que sea
incorrecta para uno de los dos. El `enlace` que se guarda hoy (`/tickets/{id}`)
no corresponde a ninguna ruta del proyecto: al pulsarlo se caía a la ruta `*` y
la persona volvía al inicio sin saber qué había pasado.

**Consecuencia:** el contrato que la interfaz necesita es que **toda** notificación
de ticket lleve `ticket_id`, y hay una prueba que lo fija. El campo `enlace` se
conserva para enlaces que no son de ticket, y deja de ser la fuente de verdad
para el caso de un ticket.

## 41. El menú de la cuenta ofrece destinos, no solo la salida

**Decisión:** el menú de la persona conectada lista Mi perfil, Mis tickets,
Configuración y Usuarios (los dos últimos solo con permiso) antes de «Cerrar
sesión». Al elegir uno se cierra y navega. Para el perfil del panel se añadió
`/panel/perfil`, porque `/perfil` pertenece al cascarón del portal.

**Motivo:** un menú que solo permite salir no es un menú de cuenta, es un
botón con adorno: se abría, no había nada que hacer y se volvía a cerrar. Y
llevar a `/perfil` desde el panel cambiaba de interfaz completa, lo que se percibe
como que el enlace falló.

**Consecuencia:** `PopoverSimple` admite estado controlado (`abierto`,
`alCambiar`) para poder cerrarlo al navegar; sin eso el menú podía quedar abierto
encima de la pantalla nueva.

## 42. La campana existe en los dos cascarones y refresca sola

**Decisión:** el componente vive en `componentes/dominio/CampanaNotificaciones.tsx`
y se usa en panel y portal. `useNotificaciones` consulta cada 30 s. Al abrir un
aviso se marca como leído (`POST /notificaciones/leer?ids=…`), no solo «Marcar
todas». Sin lista se explica cuándo llega un aviso.

**Motivo:** las notificaciones son principalmente para quien reporta el problema,
y el portal no tenía ninguna forma de verlas. El contador nunca cambiaba solo
porque el aviso en vivo por WebSocket no está conectado en la interfaz. Una lista
vacía sin explicación se lee como una función rota.

**Consecuencia:** queda pendiente conectar `/api/ws/notificaciones`; hasta entonces
el refresco cada 30 s cubre el caso y es una sola lectura por persona.

## 43. Un botón de acción lleva marco

**Decisión:** «Limpiar» pasó de la variante `fantasma` (transparente, sin borde) a
`secundario`, con una ✕.

**Motivo:** convive con «Filtros» y «Guardar vista», que sí tienen marco. Sin él
se leía como texto suelto y no como algo pulsable, que es justo la duda que se
plantó al usarlo.

## 44. Los ejes de `translate`, `scale`, `skew`, `space` e `inset` no compiten

**Decisión:** en la tabla de raíces polimórficas de `cn()`, cada eje es una clave
propia: `-translate-x-1/2` y `-translate-y-1/2` conviven, igual que `space-x-*` con
`space-y-*` o `inset-x-*` con `inset-y-*`. Antes caían todos bajo la raíz y se
pisaban entre sí.

**Motivo:** en Tailwind v4 los ejes se escriben en variables distintas
(`--tw-translate-x`, `--tw-translate-y`), así que **no compiten**: la última en
ganar no es la última en el atributo `class`. El fallo era silencioso —nadie ve
un error de compilación, solo una cosa mal maquetada— y `DialogModal` se centra
con `top-1/2 left-1/2` más esas dos medias traslaciones, así que **todos** los
diálogos del panel salían corridos media anchura a la derecha.

**Consecuencia:** `tools/verificar-clases.mjs` carga el módulo real de `cn()`
(lo compila con esbuild y lo importa), lo somete a 37 casos y revisa las llamadas
de `cn()` de todo `src/` avisando de pares de ejes que se pisan. Es una
comprobación permanente, no una revisión manual.

## 45. Una vista guardada se guarda como filtros de URL, no como un objeto suelto

**Decisión:** los filtros que viajan por la URL están en una tabla única
(`FILTROS_URL`) con dos piezas por filtro: cómo se escribe en la URL (`forma`) y
cómo se lee de ella (`lectura`). Al guardar se recorren esas mismas claves; al
aplicar se reconstruye la URL con ellas.

**Motivo:** guardar volcaba el objeto de filtros con `String(valor)` y al aplicar
se hacía `parametros.set(clave, valor)`. Eso rompía con listas (`estado:
['resuelto','cerrado']` quedaba `resuelto,cerrado`) y con booleanos
(`solo_abiertos: true` quedaba `true`, pero el código solo leía `1`). Y el campo
`vista` de la vista rápida se guardaba aparte y no se leía al aplicarla. Con una
sola tabla, guardar y aplicar no pueden volver a separarse: si un filtro no está
en la lista, no se guarda.

**Consecuencia:** la URL que produce una vista guardada es la misma que produce
el filtro a mano, así que se puede compartir y recargar. Al aplicar se invalidan
los tickets para que la tabla se mueva aunque el filtro sea el mismo, y sale un
aviso con el nombre de la vista, porque un botón que no produce ningún cambio
visible parece roto.

## 46. Las pruebas de la suite no dejan base de datos detrás

**Decisión:** la fixture `db` de `conftest.py` borra su base
`mesa_ayuda_test_<aleatorio>` en el `finally`, además de borrarla al empezar.

**Motivo:** cada corrida creaba la suya (el nombre lleva un aleatorio para que dos
corridas simultáneas no choquen) y no la eliminaba: había 37 acumuladas, unos
90 MB, en el mismo Mongo del despliegue.

**Consecuencia:** el Mongo del despliegue queda con las bases que corresponden y
nada más.

## 47. La vista guardada se marca comparando filtros, no guardando un estado

**Decisión:** la marca de «vista aplicada» no es un estado que se active al
pulsar el acceso rápido. Se calcula comparando la huella de los filtros que hay
en pantalla con la huella de cada vista guardada, y se recalcula sola.

**Motivo:** un estado volátil se pierde al recargar o al compartir el enlace, y
además mentiría justo cuando más importa: si alguien abre una URL con filtros y
cambia uno a mano, un estado que sigue «activo» affirmaría que la tabla es la
vista guardada cuando ya no lo es. Con la comparación, en cuanto se toca algo la
marca se apaga sola.

**Consecuencia:** la huella ordena claves y valores antes de comparar, para que
`estado=resuelto&estado=cerrado` y `estado=cerrado&estado=resuelto` sean la misma
vista. La marca no depende solo del color: también cambia el grosor del texto y
lleva `aria-current="true"`. Al guardar, la vista nueva sale marcada porque el
registo recién creado es lo que se está viendo.

## 49. Cada tipo de equipo tiene su esquema de campos

**Decisión:** `ESQUEMAS_POR_TIPO` cubre los 15 tipos del catálogo, no solo los 7
que tenían esquema. Un sistema de audio, un UPS o un celular no preguntan
dirección IP ni MAC; un servidor pregunta lo mismo que una CPU; una tablet
pregunta MAC pero no IP. La migración `010` los inserta con `$setOnInsert`: los
tipos que ya existían no se tocan, para no pisar lo que el administrador haya
ajustado en Configuración.

**Motivo:** los tipos nuevos estaban en el catálogo pero sin esquema, así que
caían en el genérico y el formulario pedía IP y MAC a un amplificador. El alta
debe seguir la plantilla del Excel, que tiene una columna por concepto y no por
tipo: lo que cambia es **qué columnas aplican**.

**Consecuencia:** el esquema es el único lugar que decide qué se pregunta. Si
algún tipo nuevo no tiene entrada, hay que añadirla a la tabla y a la migración;
el frontend solo pinta los campos que el backend devuelve y que tienen etiqueta.

## 50. «Parte de un conjunto» se propone según el tipo

**Decisión:** la casilla viene marcada para CPU, Laptop, Monitor, Teclado, Mouse e
Impresora, y sin marcar para el resto; cambiar de tipo la restablece y limpia los
campos escritos.

**Motivo:** estaba marcada siempre, así que un router, una tablet o un amplificador
acababan dentro de «Computadora N°01» con un conjunto inventado. La idea de conjunto
—agrupar los componentes de una computadora— solo tiene sentido para los equipos de
escritorio.

## 51. «Sin vincular» significa sin cuenta activa, en los dos sitios

**Decisión:** el filtro de Equipos y el contador de la puesta en marcha cuentan lo
mismo: equipos con responsable nombrado en el Excel cuyo `responsable_id` no está
entre los usuarios **activos**. Se resolvió con una lista de ids en vez del
`$lookup` que había, con el mismo resultado y menos trabajo.

**Motivo:** al revisar el filtro parecía un error —decía «sin vincular» y un
responsable enlazado a una cuenta dada de baja contaba como tal—, pero
`db/estado.py` ya usaba esa regla y una prueba la fijaba. Cambiar solo una de las
dos partes habría hecho que el contador de la puesta en marcha y la lista de
Equipos dijieran números distintos, que es peor. Se documentó la regla y se cubrió
con una prueba que compara las dos.

**Consecuencia:** si la cuenta se da de baja, sus equipos vuelven a la lista de
pendientes, que es lo correcto: el enlace ya no sirve para elegir responsable.

## 52. La barra de filtros: todas las celdas con la misma forma

**Decisión:** las seis celdas de Equipos llevan rótulo arriba y control abajo:
Buscar equipos, Zona, Oficina, Tipo, Agrupar por y Responsable del Excel. El
buscador y la casilla dejaron de ser controles sueltos y pasaron a tener rótulo.

**Motivo:** antes el buscador y la casilla ocupaban la fila de los controles sin
rótulo, junto a campos que sí lo tenían. Medido, todo estaba alineado al píxel, pero
a la vista se leía como desalineado porque las celdas no tenían la misma forma. El
problema era de estructura, no de coordenadas.

**Consecuencia:** el buscador admite un `ayuda` que se pinta debajo y queda
anunciado con `aria-describedby`, así que la explicación de qué se busca no ocupa
sitio extra en la barra.

## 53. La fila del equipo enseña el tipo, no el nombre

**Decisión:** la celda del equipo es siempre en el mismo orden: el nombre (o el
tipo si no hay nombre), debajo el **tipo en negrita** seguido de marca, modelo y
código, y debajo el conjunto como distintivo corto.

**Motivo:** el Excel nombra los equipos como quiere —las computadoras con el
nombre en la red, los periféricos con «Computadora N°03 - Monitor»— y con el tipo
en la tercera línea unas filas se leían como nombres y otras como tipos. Da igual
cómo se llame: con el tipo siempre visible, la fila dice qué es.

**Consecuencia:** el conjunto ya no ocupa una línea de texto; es un distintivo, que
es lo que se busca: «este monitor es el de la Computadora N°03» de un vistazo y sin
que la fila crezca.

## 54. Las paletas que se leen como `var()` no van en `@theme`

**Decisión:** `--zona-1..8` y `--icono-*` se declaran en `:root`, no en `@theme`.

**Motivo:** Tailwind v4 **solo emite** las variables de `@theme` que alguna clase
utiliza. Estas se leen siempre desde un `style` en línea (`var(--zona-4)`), nunca
como clase, así que nunca se emitieron: el punto de color de la zona salía
transparente y todas las zonas se veían iguales. El síntoma era «los colores no se
distinguen» y la causa era que el token no existía en el navegador.

**Consecuencia:** cualquier paleta que se lea con `var()` desde un `style` va en
`:root`. La de zonas también tiñe el fondo y el borde de la pastilla, no solo el
punto, que es lo que hace falta para distinguir dos zonas de un vistazo.

## 55. Los estados del equipo van rellenos

**Decisión:** `DisponibilidadBadge` pinta el fondo con el token `-fuerte` de su
color y el texto con `primary-foreground`. Los estados de ticket y los demás
distintivos siguen en tintado suave.

**Motivo:** en una columna con quince filas, dos pastillas claras del mismo tamaño
se leen como la misma: «Operativo» y «Dado de baja» solo cambiaban en un matiz del
fondo. Rellenando, cada estado es una mancha distinta.

**Consecuencia:** el relleno usa el token `-fuerte`, que es oscuro en el tema claro
y claro en el oscuro, y el texto es `primary-foreground` —el mismo par que se usa
en un botón relleno y que ya se probó legible en los dos temas—, así que no hacen
falto seis pares de tokens nuevos. Se añadió además un `destacado` en `Badge` para
poder volver al tintado donde sí conviene.

## 56. Los estados que trae el Excel también se reconocen

**Decisión:** `inoperativo` e `inoperativa` se uncontestan al mapa de
disponibilidad, con icono de apagado.

**Motivo:** el Excel trae su propio vocabulario (`OPERATIVO`, `INOPERATIVO`,
`INOPERATIVA`) y no coincide con el catálogo. Lo que no coincidía caía en «Sin
estado», que es indistinguible de un dato corrupto y no dice nada de si el equipo
funciona: 38 equipos de la municipalidad salían así.

## 57. La completitud se lee como barra, no como número

**Decisión:** la celda «Datos» es una barra de 40 px con la cifra al lado. La
escala tiene cuatro pasos: 100 % verde, 70-99 % azul, 30-69 % ámbar, menos de 30 %
rojo. Al 100 % se sigue escribiendo «Completo».

**Motivo:** una pastilla con «50%» no dice nada sobre la forma de la columna. Con
la barra se ve de un vistazo cuántos equipos están completos, cuántos van por la
mitad y cuántos están casi vacíos, sin leer un número. Y la escala de dos tonos
—completo o incompleto— hacía que un inventario al 90 % se viera igual que uno al
50 %.

**Consecuencia:** el relleno usa el color sólido y la pista un gris neutro, para
que la barra se lea como una barra y no como dos parches del mismo color.

## 58. La paleta de zonas se reparte por la rueda de color

**Decisión:** los ocho tonos de zona se eligen cada 45° en la rueda de color,
alternando claridad: azul, verde azulado, verde, ocre, naranja, granate, violeta y
fucsia. El texto de la pastilla usa `color-mix(in srgb, var(--zona-N) 70%,
var(--color-foreground))`.

**Motivo:** la paleta anterior tenía cuatro tonos azules/naranjas y las zonas
próximas en el listado eran casi del mismo color: COMPLEJO y MERCADO los dos
naranjas, PALACIO y PISCINA los dos azules. Había que leer el nombre para saber
cuál era cuál. Mezclar el color de la zona con el del tema para el texto hace que
en claro se oscurezca y en oscuro se aclare, así que siempre contrasta sin
tener dos paletas.

**Consecuencia:** no cambia el `color_indice` de cada zona —lo asigna una
migración y es estable—, solo el color al que apunta, así que no hay nada que
migrar en la base.

## 59. La barra horizontal se pinta y se pega abajo

**Decisión:** la tabla de escritorio tiene, además de su barra nativa, una pista
propia `sticky bottom-1` con un tirador arrastrable. El tirador se dibuja a mano
y no se deja al del navegador.

**Motivo:** dos problemas. El primero es de sitio: con todas las columnas la
tabla se va a 2.100 px y su barra queda mil píxeles más abajo, así que había que
bajar hasta el final para poder moverla y al principio no se podía. El segundo es
de visibilidad: la barra del navegador es superpuesta en algunos sistemas y no
aparece hasta que pasas el ratón por encima, que es justo lo que se quería quitar.

**Consecuencia:** la pista solo aparece si hay desborde de verdad, ocupa su sitio
en el flujo —se va con la tabla cuando esta sale de pantalla— y no estorba al
desplazamiento vertical con rueda o tactil, que siguen funcionando sobre el
contenedor real.

## 60. La tabla por defecto tiene que caber sin scroll

**Decisión:** las celdas de datos se quedan en una línea con ancho máximo de
11 rem, y cinco rótulos se acortaron (`Tamaño de pantalla` → `Pantalla`,
`Memoria RAM` → `RAM`, `Dirección IP` → `IP`, `Dirección MAC` → `MAC`). La tabla
usa `min-w-full` y no `w-full`.

**Motivo:** con `w-full` y el borde del contenedor la tabla se pasaba 38 px y
aparecía una barra horizontal que no hacía falta. Y con celdas que se parten en
tres líneas, cada fila se estiraba y la tabla se convertía en un muro: con muchas
columnas a la vista había que leerScroll para saber qué había en cada fila.

**Consecuencia:** con las columnas por defecto la tabla mide exactamente lo que
tiene (1.079 de 1.079) y no aparece ninguna barra. Lo que no cabe en una celda se
recorta y se lee con el título al pasar el ratón.

## 61. El encabezado lleva fondo y aire, y conserva las mayúsculas

**Decisión:** la fila de encabezados de `DataTable` lleva `bg-surface-2`, borde
inferior propio, 16 px de aire lateral y 14 px vertical, y los títulos van en
`text-foreground/70` con peso 700 **y en mayúsculas**.

**Motivo:** antes eran títulos de la tinta apagada sobre el mismo blanco de las
filas, sin fondo ni borde que los separara: no se leían como una cabecera sino como
palabras sueltas flotando sobre la tabla. Lo que faltaba no eran las mayúsculas sino
que no había nada detrás. Se probaron en minúsculas y la fila perdió el golpe visual
que hace que «Equipo», «Ubicación» y «Responsable» se distingan de un vistazo sin
tener que leerlas enteras.

**Consecuencia:** cambia en todas las tablas, no solo en la de inventario, y para
bien: la cabecera es un elemento compartido y ahora se lee igual en todas partes.
El color sigue siendo el del tema, así que el orden por columna y su icono
continúan siendo distinguibles sin depender del color.

## 62. La paleta de zonas no admite tonos terrosos

**Decisión:** los seis índices que usa la municipalidad están a 32° o más de
separación en la rueda de color y ninguno es terroso. COMPLEJO pasó de ocre a
violeta. Los dos tonos que quedan libres (cian y ámbar) van a los índices 7 y 8,
que nadie usa.

**Motivo:** COMPLEJO se leía «arena». El motivo era concreto: su tono era un ocre
apagado, el único terroso de la lista, y al mezclarlo con blanco para pintar la
pastilla quedaba como un tono neutro por error —no como un color elegido—. Y
además MERCADO y COMPLEJO eran los dos naranjas y PALACIO y PISCINA los dos
azules: había que leer el nombre para saber cuál era cuál.

**Consecuencia:** el tinte de la pastilla subió del 22 % al 26 % para que el tono se
lea más. No se toca ningún `color_indice`: los asigna una migración y son estables.
Solo cambia el color al que apuntan.

## 63. Un estado crítico se distingue por la forma, no solo por el color

**Decisión:** los estados de tono `destructive` llevan forma de alerta: rectángulo
de esquinas vivas y texto en versalitas, frente a la cápsula de los demás. Además,
la fila de un equipo fuera de servicio pinta una franja roja en el canto izquierdo.

**Motivo:** «Operativo» y «Dado de baja» eran la misma pastilla con distinto color.
En una columna a media pantalla, el color es lo primero que se pierde. La forma es
lo que sigue leyéndose de un vistazo. La franja cubre lo otro: quien va escaneando
nombres no llega a la columna de estado.

**Consecuencia:** la franja se deriva de `disponibilidadDe` —el mismo sitio del que
sale el color de la insignia— y no de comparar el texto con una lista escrita a
mano. Antes se comparaba a mano, el teclado marcado como «Dado de baja» traía otra
clave desde la API y se quedaba sin franja: la insignia decía una cosa y la fila
otra. Con un solo lugar que decide, no pueden contradecirse.

## 64. Una columna vacía es un punto, no un guion

**Decisión:** las celdas sin dato muestran un punto al 40 % de opacidad
(`CeldaVacia`) en vez del guion «—».

**Motivo:** el inventario tiene columnas técnicas que no aplican a todos los
tipos —un mouse no tiene RAM, una impresora no tiene MAC—, así que media tabla era
una columna de rayas. Un guion largo en tinta fuerte es indistinguible de un dato
pendiente y compite con los datos de verdad por la atención.

**Consecuencia:** la retícula no cambia, las filas siguen alineadas y el `title`
sigue diciendo qué significa cada celda.

**Lo que NO se discreta:** la jerarquía de la columna Equipo se probó al revés —el
nombre en negrita y el tipo en versalita pequeña— y no fue la que se quiso. Se
devolvió a su forma anterior: nombre en peso medio, **tipo en negrita** dentro de la
línea de detalle y conjunto en el color de marca. En una tabla de quince filas, el
tipo en negrita y el distintivo de color son lo que deja ver de un vistazo de qué
equipo se trata; una jerarquía más elegante es una jerarquía que no se ve.

## 65. Las pruebas no pueden depender del día de la semana

**Decisión:** `test_disponibilidad_con_horario_y_ausencias` usa un horario de los
siete días y marca el día libre explícito sobre hoy, sea el que sea.

**Motivo:** fijaba un horario de lunes a viernes y pedía que el técnico saliera
«disponible» o «fuera_de_horario». Un sábado sale «dia_libre», que es correcto y
no lo que la prueba pedía: la mitad de las ejecuciones eran un falso negativo. No
era un fallo del código sino de la prueba, y estaba en `HEAD`.

**Consecuencia:** al cubrir los siete días, la comprobación del día libre
explícito pasó a ser real en lugar de saltarse en días laborables, y se añadió el
paso que faltaba: quitar el día libre devuelve al técnico a disponible o fuera de
horario.

## 66. En la tabla manda lo que se ve, no lo que está bien compuesto

**Decisión:** la columna Equipo, el nombre de la oficina y el de responsable van en
peso medio, no en tinta normal. La jerarquía «bonita» —un solo nivel fuerte por
celda, todo lo demás en versalita discreta— se probó y se quitó.

**Motivo:** bajar la oficina a tinta normal se justificó con que era el texto más
fuerte de la fila. El error estaba en el razonamiento: el nombre del equipo tampoco
iba en negrita, así que no sobraba peso, faltaba. Con las dos columnas en peso medio
y el tipo del equipo en negrita dentro de su línea, se lee de un vistazo qué equipo
es, dónde está y de quién es, sin tener que seguir la fila entera.

**Consecuencia:** aplica a `DataTable` y a `EnlaceOficina`, así que todas las tablas
que muestran oficina se ven igual. El detalle de la regla: la jerarquía de un
inventario se juzga sobre la tabla entera, no sobre una celda aislada.

## 67. Un esquema por tipo solo sirve si no incluye lo que no aplica

**Decisión:** el esquema de la impresora pierde `tamano_pantalla`. La migración
`011_esquema_impresora_sin_pantalla` lo quita del esquema guardado, y solo de los
tipos citados y solo si el campo estaba.

**Motivo:** el filtrado por esquema ya funcionaba; lo que estaba mal era el
contenido. La ficha de una impresora pedía el tamaño de una pantalla que no tiene,
que es exactamente el síntoma de un esquema por tipo que no sirve de nada: parece
un formulario genérico con el título cambiado.

**Consecuencia:** a diferencia de la migración `010`, esta **sí corrige** un esquema
que ya existe, porque no es una personalización del administrador sino un error. Solo
toca la lista de campos: cualquier otra edición se respeta, y volver a añadir el
campo es una línea en Configuración. Se añadió a las pruebas que la impresora no
lleva pantalla ni procesador y que monitor y laptop sí la llevan, para que nadie
vuelva a colar un campo que no aplica por descuido.

## 68. Un dato repetido se avisa, no se bloquea

**Decisión:** en «Disponibilidad de los datos», el código patrimonial, la IP y la MAC
avisan cuando ya están en otro equipo: una pastilla «Repetido en N» junto al campo y
un aviso arriba con la lista. La búsqueda se hace **sobre el formulario**, con 600 ms
de retardo, no sobre lo guardado.

**Motivo:** dos razones. La primera es que el aviso anterior solo salía al guardar,
y para entonces ya se había escrito la ficha entera; mirar mientras se escribe es
lo que evita tener que volver atrás. La segunda es más importante: **avisar no es
obligar**. El inventario viene de un Excel de años donde muchos equipos no tienen
código ni IP, y hay Claim de repuestos que comparten propósito. Si esto bloqueara,
dejarían de escribirse los datos que sí existen.

**Consecuencia:** el aviso dice literalmente «No es obligatorio», y el guardado sigue
teniendo su «Guardar de todos modos». Es información para decidir, no un filtro. Los
tres campos son los únicos que se avisan porque son los únicos que identifican un
equipo de forma única; marca, modelo y nombre se repiten a propósito.

## 69. La cabecera de la ficha usa un solo color

**Decisión:** la franja superior y el fondo de la cabecera de `TarjetaPerfil` usan el
color de la zona del equipo. Los encabezados de `Panel` llevan fondo `surface-2/60`.

**Motivo:** la franja era del color de zona y el fondo del color de marca, así que
salía una cabecera mitad y mitad —ámbar y violeta— que no significaba nada: el ojo
leía un color que no iba con ningún otro sitio de la pantalla. Con un solo color,
la ficha se lee como «este equipo es de COMPLEJO» desde el primer golpe de vista.
En los paneles, sin fondo en el encabezado, el título y el contenido están sobre el
mismo blanco separados por una línea y la lectura parece un bloque largo sin
principio.

**Consecuencia:** el fondo del encabezado usa el mismo `surface-2` que la cabecera de
las tablas, para que las dos cosas se lean como una sola convención. Afecta a todas
las pantallas, no solo a la ficha.

## 70. Un enlace con número, o el número que lleva a donde dice

**Decisión:** «Ver los tickets de este equipo» cuenta los tickets abiertos y los
cerrados por separado, y **cada número enlaza a la lista donde ese número es
cierto**: los abiertos a `/panel/tickets?activo_id=…` y los cerrados a
`/panel/cerrados?vista=cerrados&activo_id=…`.

**Motivo:** el filtro por equipo ya funcionaba, pero el enlace contaba todos los
tickets y llevaba a la bandeja de abiertos. Un equipo con un único ticket ya
cerrado prometía «1 ticket» y mostraba una lista vacía. Un enlace que promete un
número y enseña otro es indistinguible de un enlace roto, y es peor que no
enlazar: la persona pierde la confianza en el resto de la página. El
`?vista=cerrados` hace falta porque la página de cerrados abre en «Casos críticos»,
y sin él un ticket cerrado que no es crítico tampoco aparecía.

**Consecuencia:** cuando el equipo no tiene tickets se dice con palabras que es lo
normal, sin enlace a «abrir un ticket»: el alta manual solo admite escribir un
texto, no elegir un equipo del inventario, así que ese enlace llevaría a un
formulario en blanco. La regla general es que **un enlace con número tiene que
llevar a la lista donde ese número es cierto**, o no hay enlace.

## 71. La zona va con la oficina, no suelta en la retícula

**Decisión:** la pastilla de zona se pinta debajo del selector «Oficina y zona»,
con la etiqueta «Zona:», en vez de ocupar su propia casilla de la rejilla del
formulario.

**Motivo:** estaba suelta en una celda al lado del tipo de equipo y dejaba un hueco
que desalineaba la primera fila del formulario. Además, la zona es parte de la
ubicación: puesta al lado del tipo de equipo parecía un dato de una naturaleza
distinta, cuando se deduce justo de la oficina que tiene al lado.

**Consecuencia:** además de quedar donde corresponde, la rejilla deja de tener un
hueco y la primera fila del formulario queda alineada.

## 72. Un desplegable se agrupa, no se concatena

**Decisión:** el selector de oficinas usa `<optgroup>` con un encabezado por zona,
coloreado con el color de esa zona. La opción es solo el nombre de la oficina; la
zona ya no va como sufijo «· COMPLEJO».

**Motivo:** el texto «OFICINA · ZONA» con las dos palabras en mayúsculas y el mismo
punto de separación hace que no se vea dónde acaba una y empieza la otra. Con 59
oficinas era un muro sin por dónde agarrarse. Con grupos, la zona es un encabezado
y el nombre de la oficina se lee solo —que es lo que se está buscando— y el grupo
se reconoce por color antes de leer nada.

**Consecuencia:** `Select` acepta ahora `grupos` además de `opciones`; los
selectores que no los usan no cambian, así que el cambio no obliga a tocar las
decenas de listas desplegables de la aplicación. Los navegadores de escritorio
respetan `color` y `background` en `optgroup`, que es lo que hace que funcione.

## 73. La zona se muestra en la oficina que eliges, no en la que guardaste

**Decisión:** la pastilla de zona debajo del selector se calcula desde la oficina
seleccionada en el formulario; si esa oficina no está en la lista, se usa la zona
del registro.

**Motivo:** estaba atada al dato guardado. Al cambiar a una oficina de otra zona,
la pastilla seguía diciendo la zona antigua mientras el selector decía otra cosa:
dos verdades distintas en la misma fila, y la que cambia al instante es la que
mata.

**Consecuencia:** es una vista previa, no un cambio: la zona del registro solo
cambia al guardar. La diferencia entre lo que se está eligiendo y lo que está
guardado es visible sin abrir nada, que es justo lo que hace falta para decidir.

## 74. «Resuelto» se llama «Atendido» en pantalla

**Decisión:** la etiqueta del estado `resuelto` pasa a **Atendido** en toda la
interfaz. La clave interna no cambia.

**Motivo:** «Resuelto» y «Cerrado» son dos finales casi idénticos y conviven en la
misma columna. La pregunta de siempre es si un ticket cerrado está «resuelto» o no,
y la respuesta es «las dos cosas», que no ayuda a nadie. «Atendido» dice lo que
quiere decir —que hubo una solución— sin parecer un final, que es exactamente lo
que la municipalidad pidió para evitar confusiones en el flujo diario.

**Consecuencia:** los estados son claves, no textos: los 20 tickets guardados usan
`resuelto` en la base y seguirán igual. Cambiar la clave sería una migración sobre
datos reales para no ganar nada. Se ajustaron también los sitios que describían el
estado con la palabra antigua: el filtro «Resuelto o cerrado» de la bandeja, el
texto del diálogo de cierre y el contador del portal.

## 75. Descargar un archivo no es un enlace

**Decisión:** las descargas pasan por el cliente de la API —con `fetch`, la
cabecera de sesión y un `Blob`— mediante el ayudante `descargarDeLaApi`. Nada de
`<a href>` contra rutas autenticadas.

**Motivo:** la API autentica con la cabecera `Authorization` y un enlace normal no
la manda. El botón «Descargar» de las exportaciones pedía la ruta sin token,
recibía un **401** y no bajaba nada —sin mensaje de error, porque el enlace
«funciona» y lo que falla es que no hay archivo—. Un fallo silencioso en un botón de
descarga es el peor tipo de fallo: hace dudar de si el botón está mal o el
servidor, y aquí era del botón.

**Consecuencia:** el botón muestra «Descargando…» mientras va y avisa si algo
falla, en vez de no pasar nada. Se corrigió en los dos sitios donde estaba el patrón
—Reportes y Cerrados— y la plantilla del importador, que ya lo tenía bien, ahora usa
el mismo ayudante.

## 76. Un número sin unidad no se puede leer

**Decisión:** las cifras que dependen de una referencia llevan la referencia en el
rótulo —«de capacidad» en vez de «carga», «del tiempo permitido, ya usado» en vez
de «Transcurrido»— y, cuando el número significa un problema, se añade la frase con
los datos que lo sostienen.

**Motivo:** «163 %» y «100 %» son cifras sin base: no se sabe de qué es el 100, así
que no se pueden valorar. Con la unidad en el rótulo, «188 % de capacidad» ya se
lee; y cuando está sobrecargado, «tiene 7 tickets más de los que puede resolver en
un día» convierte el dato en una decisión.

**Consecuencia:** aplica a la carga del equipo y a la barra de SLA. En la carga, la
franja de urgencia en rojo se mantiene para que el problema siga viéndose de un
golpe de vista, sin leer.

## 77. Un ticket concluido queda «cerrado», y no hay otro final

**Decisión:** se retira el estado `resuelto`. Quedan cinco estados: `nuevo`,
`asignado`, `en_progreso`, `en_espera` y `cerrado`, que es el único final. Desde
cualquier estado abierto se va a `cerrado` en un solo paso, escribiendo la nota de
solución.

**Motivo:** «resuelto» y «cerrado» eran la misma realidad con dos palabras: los dos
significaban «el problema está solucionado», los dos eran finales y los dos se
podían reabrir. Un estado que significa lo mismo que otro no aporta nada y cuesta:
en la cola real los tickets se quedaban en «resuelto» semanas sin que nadie
volviera a cerrarlos, y la pregunta de siempre era si un ticket ya «resuelto» está
también «cerrado» —respuesta: las dos cosas—. En una mesa de ayuda municipal el
técnico termina y el caso se archiva: no hay segundo paso ni segundo actor.

**Consecuencia:** cerrar es un paso, no dos, y el backend deja de hacer el ridersillo
por «resuelto» para validar la nota y avisar a quien reportó. **Las dos fechas se
conservan** —`resuelto_en` y `cerrado_en`—, porque no son el estado sino marcas de
tiempo: de ellas salen los tiempos de resolución, el cumplimiento de SLA, las
valoraciones y las estadísticas de los técnicos. Quitar el estado no toca ninguna de
esas medidas. La migración `012_un_solo_estado_final` trae los tickets ya
guardados y repara las vistas guardadas que filtraban por el estado retirado, que
si no se habrían quedado vacías sin avisar. Reabrir sigue siendo posible desde
`cerrado`, con su límite de quince días para quien reportó.

## 78. Un botón tiene que hacer lo que su nombre dice

**Decisión:** el botón pasa a llamarse **«Descargas (n)»**, el panel se titula
«Archivos que puedes volver a bajar» con el subtítulo *«No genera nada nuevo: son
archivos que ya creaste en Reportes»*, y se añade «Descargar todos» que baja los
listos de uno en uno con una pausa entre ellos. Reportes usa el mismo nombre.

**Motivo:** la descarga **ya funcionaba** —el archivo llegaba con 6.319 bytes y era
un xlsx válido—, pero el botón solo abría una lista. Leído como «bajar la lista de
esos 8 tickets», al pulsarlo no pasaba nada. El fallo no era técnico sino de
veracidad del rótulo: un control que promete una cosa y hace otra enseña a no
fiarse de los controles. Cuando alguien dice que algo «no sirve», lo primero es
mirar si lo que hace coincide con lo que dice, antes de buscar un bug.

**Consecuencia:** «Descargar todos» va archivo por archivo con 350 ms de pausa, no
en paralelo: los navegadores piden permiso para varias descargas seguidas y, si se
lanzan a la vez, las bloquean todas. Si alguno falla, se avisa con su nombre.

## 79. `group-hover` en el propio elemento no hace nada

**Decisión:** las tarjetas KPI del Resumen se marcan al pasar el ratón: se levantan
medio píxel, toman borde de color y la etiqueta y el icono cambian de tinta.

**Motivo:** la tarjeta llevaba `group-hover:shadow-panel` en sí misma. Una variante
`group-*` solo se aplica a un elemento que cuelga de un ancestro marcado `group`, y
la tarjeta no colgaba de ninguno: la clase estaba ahí, muerta, y por eso no había
ninguna reacción. Seis tarjetas idénticas sin decir cuál estaba bajo el puntero es
lo mismo que no tener botones.

**Consecuencia:** el cambio es en el componente `KpiCard`, así que las tarjetas de
porcentaje y las que salen en otras pantallas reaccionan igual. Se evitó
`transition-all`, que hace saltar el contenido al cambiar de tema o de estado; la
transición se limita a `transform`, `box-shadow` y `border-color`.

## 80. Cerrar no es un estado más: es el final, y va aparte

**Decisión:** el desplegable de la ficha se llama «Mover en el flujo» y **no ofrece
«cerrado»**. El cierre se hace con un botón propio, en un bloque rotulado «Terminar
el caso» que explica que al cerrar hay que escribir qué se hizo.

**Motivo:** mezclados, «cerrado» parecía un estado más entre «asignado» y «en
progreso», que es justo lo que destruye el significado de cada palabra. El flujo
describe **en qué punto del trabajo está el caso** —nuevo, asignado, en progreso, en
espera— y cerrar es otra cosa: el final, que además arrastra una consecuencia —la
nota de solución, que lee quien reportó—. Que exija un texto lo convierte en un
acto distinto de mover el caso de sitio.

**Consecuencia:** no es un cambio de backend: la transición a `cerrado` sigue
existiendo y es la que usa el botón. El frontend simplemente no la ofrece en el
desplegable, lo que además elimina la duplicación de antes, donde la nota de
solución se pedía en dos sitios a la vez. El botón dejó de ser «destructivo» en
rojo: cerrar un caso es un trabajo terminado, no un error.

## 81. Un evento por websocket no es una notificación

**Decisión:** al crear un ticket se avisa al técnico asignado y, si no hay, a los
técnicos y administradores activos. En el alta manual se avisa al técnico al que
se le asigne. Quien reporta queda excluido.

**Motivo:** la campana consultaba cada 30 segundos y funcionaba; lo que faltaba era
que **nunca se creara nada para avisar**. Al crear un ticket solo se publicaba un
evento por websocket, sin rastro en ninguna bandeja: si nadie estaba mirando la
lista, el aviso se perdía. Y al asignar sí se notificaba, pero solo si el técnico
era distinto de quien asigna —con un único administrador que reporta y atiende a
la vez, el único destinatario posible era él mismo y nunca se le avisaba—.

**Consecuencia:** un despliegue con una sola cuenta deja de tener la campana
permanentemente vacía, que es lo que hace que alguien deje de mirarla. La prueba
que lo cubre crea un ticket desde el portal y comprueba que llega al técnico con su
código y que **no** va a quien lo reportó: avisar de algo que uno mismo acaba de
hacer es ruido.

## 82. Un estado que nadie mantiene no es un estado: se retira

**Decisión:** el estado «asignado» desaparece. Asignar un técnico pone el caso
«en progreso» en el mismo paso. Quedan cuatro estados: nuevo, en progreso, en
espera y cerrado.

**Motivo:** la pregunta era si «asignado» y «en progreso» hacían lo mismo. Los datos
contestaron: de 14 tickets abiertos había **13 parados en «asignado» y ninguno en
«en progreso»**. El estado no describía una realidad, era un sitio donde los casos
se quedaban. Y no se notaba por tres razones a la vez: asignar lo dejaba ahí y hacía
falta un segundo clic para salir —que nadie daba—, el único contador que medía la
diferencia no se mostraba en ninguna pantalla, y en los informes ambos estados se
contaban igual.

**Consecuencia:** cuatro estados que se leen de un vistazo —nadie lo ha tomado /
hay un técnico con el caso / está parado esperando algo / terminado con su
solución escrita—. La única forma de devolver un caso a la cola sin técnico pasa a
ser «nuevo», que es literalmente lo que significa. En el portal del ciudadano el
progreso baja de cuatro pasos a tres: «le asignaron» y «lo están revisando» le
suenan igual, y por dentro son el mismo paso. La migración deja los casos existentes
en «en progreso», que es donde estaban.

## 83. Un registro borrado no trabaja

**Decisión:** la carga del equipo filtra los tickets eliminados. El «caso en curso» es
el más reciente, no el primero que devuelva la base.

**Motivo:** el borrado es lógico —el documento se queda con `eliminado`— y esa consulta
no lo tenía en cuenta. El síntoma visible era un enlace «Atendiendo TKT-…» que
llevaba a un ticket borrado y devolvía un 404, pero detrás había dos cosas más: el
técnico aparecía «Ocupado» por un caso que ya no existía y su carga iba inflada. Un
error en pantalla delata lo que se ve; la causa de fondo era que el sistema contaba
trabajo que nadie tiene.

**Consecuencia:** además del filtro, el caso en curso se elige por fecha de
actualización. Sin ordenar, Mongo devuelve los documentos en su orden natural y el
panel enseñaba un ticket arbitrario de los que la persona tenía abiertos. La prueba
que lo fija crea un caso, lo asigna, lo marca eliminado y comprueba que la carga baja
a cero, que el técnico deja de estar «ocupado» y que no se ofrece su enlace.

## 48. Los scripts de comprobación no borran datos de la municipalidad

**Decisión:** las comprobaciones con navegador solo leen. Si hay que crear algo
para probar, se identifica con un nombre inequívoco (`zz prueba …`) y se borra al
terminar **solo ese nombre exacto**, nunca por posición ni por «el primero que
encuentre».

**Motivo:** en la verificación del bloque M1–M4, un bucle de limpieza acabó
borrando la vista guardada que había creado la persona usuaria. El guion apuntaba
a un `aria-label` concreto, pero el fallo posible estaba en apoyarse en un bucle
`for(;;)` que vuelve a contar sobre una lista que se actualiza por red: si el
refresco va con retraso, el siguiente clic cae sobre la fila que quedó en su
lugar. Restar datos ajenos es peor que dejar una prueba sin hacer.

**Consecuencia:** las pruebas que necesitan escribir pasan a un entorno aislado
o declaran de antemano qué van a crear y cómo lo reconocen después. Lo que se lee
del despliegue real es solo lectura. Cuando hubo que restituir lo borrado se hizo
por la interfaz, que es la única vía con el token CSRF, y después se comprobó en
el log del servidor quién había hecho cada borrado antes de darlos por perdidos:
en este caso fue la persona usuaria, no el guion.

## 84. Dos controles contiguos, la misma altura

**Decisión:** las pastillas de vista rápida de la bandeja miden 40 px, como los
botones y el campo de búsqueda de la misma franja. Antes medían 34 px.

**Motivo:** el espacio entre bloques ya estaba bien —16 px en todos—, así que el
apiñamiento no venía del hueco. Venía de que dos controles contiguos tenían
alturas distintas: 40 px arriba y 34 px abajo. Una fila con dos alturas se lee
como torcida aunque el separador sea correcto. Se midieron los dos valores en el
navegador antes de decidir; cambiar el hueco a ciegas no habría arreglado nada.

## 85. El encabezado tiene que decir qué se está viendo

**Decisión:** el título de la bandeja sigue a la vista activa, no a la vista
inicial.

**Motivo:** el título salía de un valor por defecto que no cambia al pulsar un
botón, así que decía «Abiertos» encima de la tabla de «Críticos» o «Sin
asignar». La pestaña activa sí era correcta: la contradicción era entre dos
partes de la misma pantalla, y la que miente es la que se lee primero.

## 86. Una celda vacía en una hoja de cálculo no es un dato

**Decisión:** el informe de tickets escribe «Sin zona» y «Sin oficina» donde antes
dejaba la celda en blanco, en los tres formatos.

**Motivo:** un ticket sin zona u oficina no se pierde: se guarda, sale en la
bandeja y aparece en el informe. El problema era otro. En una hoja de cálculo
una celda vacía no distingue «no tiene zona» de «se borró el dato», y encima no
se puede filtrar por ella. El ranking por zona ya agrupaba esos casos como
«Sin zona»; el archivo no, y son la misma pregunta.

**Consecuencia:** la prueba que lo fija registra un caso con una persona no
registrada y comprueba las tres cosas a la vez: que guarda su nombre, que sale en
el informe y que las columnas vacías dicen qué les falta.

## 87. Una fila de atajos no se repite donde ya hay pestañas

**Decisión:** «Historial y casos críticos» ofrece solo las vistas *Críticos* y
*Cerrados*. La bandeja general sigue ofreciendo las cinco.

**Motivo:** esa pantalla ya tiene sus propias pestañas para esas dos consultas, así
que la fila completa de vistas rápidas era una segunda navegación encima de la
primera. Peor: tres de los cinco botones —«Abiertos», «Sin asignar» y «SLA en
riesgo»— son atajos de la cola abierta, o sea que sacaban de la página en la que
estabas. En la bandeja general sí son un atajo útil, y ahí no se toca nada.

**Consecuencia:** `Bandeja` recibe un prop `vistas` con las claves que esa pantalla
ofrece. Si la URL trae una vista que esa lista no contiene, se cae en la vista
inicial de la página en vez de dejar la fila a medias.

## 88. Navegar no es accionar: se miden distinto

**Decisión:** las pastillas de vista rápida miden 36 px, no los 40 px de los botones
de la misma franja.

**Motivo:** primero se alinearon con los botones para que la fila no se viera
torcida, y el resultado fue peor: una fila de dos palmos que pesaba más que la tabla
que estaba debajo. Son dos cosas distintas. «Filtros» y «Limpiar» se pulsan para
hacer algo; las vistas se pulsan para mirar otro sitio. Copiar la medida de los
botones fue tratar la navegación como una acción.

**Consecuencia:** 36 px con `px-3.5` y el texto en peso medio, que es lo que mide el
texto con aire alrededor. La diferencia se marca con el borde y el relleno de la activa,
no con el tamaño. El peso en negrita se queda solo para la vista activa, para que se
lea de un vistazo cuál es.

## 89. El tipo del equipo es un dato, no un adorno del nombre

**Decisión:** el ticket guarda `activo_tipo` y la columna «Equipo» lo enseña en su
propia línea. Si el nombre ya acaba en ese mismo tipo, se quita de ahí.

**Motivo:** la columna mostraba el nombre arriba y el conjunto abajo. En el inventario
importado el conjunto es el prefijo del nombre —«Computadora N°01 - CPU» dentro de
«Computadora N°01»—, así que la segunda línea repetía lo de arriba, y como la columna
es estrecha el «- CPU» era justo lo primero que se cutraba. El resultado era lo peor de
los dos: la línea de abajo no aportaba nada y el dato que sí servía había desaparecido.

**Consecuencia:** el tipo vive en el ticket porque la bandeja no consulta el
inventario, y pedirlo por fila sería una consulta por fila. La migración rellena el
campo en los tickets existentes sin tocar nada más del equipo. El conjunto solo
aparece cuando no es el prefijo del nombre, y el sufijo redundante solo se quita
cuando el final coincide de verdad con el tipo, para no mutilar un nombre en el que el
guion sea parte del texto.

## 90. Un plazo se cuenta en días, no en horas de reloj

**Decisión:** el plazo máximo del SLA son 16 horas laborables —2 días con la jornada de
8 h—. Antes eran 72: nueve días.

**Motivo:** los tiempos del SLA no son horas de reloj, son horas laborables, y esa
distinción era lo que producía las dos cosas malas. Una: la prioridad «baja» daba
nueve días laborables, así que un ticket sin prisa podía pasar más de una semana y
media sin que nadie lo tocara y sin que el sistema marcara nada, porque el contador
compara el retraso contra ese mismo plazo y el plazo lo consentía. Dos: al traducir
horas laborables a tiempo de calendario salían cifras que nadie puede leer —«116 h
5 min restantes»—, que es un plazo que suena a error aunque sea correcto.

**Consecuencia:** la escalera reparte las cuatro prioridades por debajo del tope
conservando el orden: crítica 2 h, alta 4 h, media 8 h, baja 16 h. Sigue siendo
configurable desde Configuración. La migración recalcula el plazo de los tickets
abiertos; **los ya cerrados conservan el plazo con el que se resolvieron**, porque ese
plazo se fijó cuando se creó el ticket y reescribirlo sería falsear lo que ocurrió. El
texto de la columna cuenta en días en cuanto hay un día entero, porque es como se habla
de un plazo.

## 91. Al filtrar por una vista, la decisión se toma por la clave

**Decisión:** la URL de cada vista rápida se decide por su clave, no por mirar qué
filtros trae.

**Motivo:** se comprobó si la vista traía `vista` o `estado` entre sus filtros, y eso
deja fuera a «SLA en riesgo», que filtra por `sla`: se quedaba sin filtro y saltaba a
«Abiertos». El síntoma era «al pulsar SLA en riesgo me manda a Abiertos», y la causa
era una suposición sobre la forma de los datos en lugar de mirar la clave, que es lo
único fiable. Una vista rápida es un nombre, no un objeto con filtros.

**Consecuencia:** se comprueba una por una que cada vista lleva a su URL y deja su
pestaña activa. «Abiertos» es la única que borra la URL, porque es la vista sin filtro.

## 92. Recortar texto sí; recortar una insignia, no

**Decisión:** las celdas con insignias —«Estado y prioridad» y «Afectado»— salen del
recorte automático y se dejan ocupar las líneas que necesiten. El resto de columnas
siguen en una línea con puntos suspensivos.

**Motivo:** `truncate` corta con `overflow: hidden`, que es lo correcto para texto y
no sirve para nada más. Una insignia es un `inline-flex` con relleno y borde: no puede
encogerse por debajo de su contenido, así que cuando la columna se estrecha por debajo
de él, la pastilla se partía a media palabra y con el borde redondeado cortado. Es lo
peor de las dos cosas: no se lee, y además parece un fallo de la aplicación en vez de
un recorte.

**Consecuencia:** `DataTable` acepta `meta.celdaLibre`, declarado en el módulo de
TanStack para que `columnDef.meta` lo reconozca y no haya que andar con conversiones de
tipos. Las dos insignias de «Estado y prioridad» además quedan **apiladas siempre**, no
solo cuando la columna se estrecha: antes el ancho de la columna cambiaba según el
ancho de la ventana, y una columna que cambia de medida al mover la ventana se lee como
algo roto. Lo que sigue igual es el desplazamiento horizontal de la tabla, que es
inherent a tener siete columnas con el menú abierto; lo que ya no ocurre es que una
columna se parta por dentro.

## 93. El recorte pertenece al contenido, no a la celda

**Decisión:** `truncate` deja de ir en el `<td>` y pasa a un envoltorio dentro. La
columna marcada con `meta.celdaLibre` no recorta nada.

**Motivo:** poner el arreglo columna por columna trata el síntoma. La causa era que
`overflow: hidden` en la celda recorta *cualquier cosa* que no sea texto, y la regla
se escribió pensando en texto. Por eso el arreglo va en el `DataTable` compartido,
que cubre Bandeja, Equipos, Usuarios, Auditoría y Galería de una vez, y no solo las
que alguien miró por casualidad. Una vez que el recorte es del contenido, una
insignia simplemente no se recorta, donde aparezca, incluso en una columna que nadie
ha revisado todavía.

**Consecuencia:** lo que no cambia es el efecto buscado del recorte: el texto largo
sigue saliendo con puntos suspensivos, dentro de la celda, y en Equipos se comprobó
sobre nombres reales. Las columnas con insignias —«Afectado» y «Estado y prioridad» en Bandeja, «Ubicación»,
«Estado» y «Datos» en Equipos, «Ubicación» y «Estado» en Usuarios— quedan marcadas.
La verificación es un escaneo que recorre ocho pantallas a seis anchos buscando
elementos que se salgan de su ancestro con `overflow: hidden`, en vez de mirar una
captura: **0**.

## 94. Una celda no puede depender del ancho de su columna

**Decisión:** zona y oficina se muestran con una estructura fija —zona arriba,
oficina debajo— mediante un componente `Ubicacion` compartido. Sin zona se escribe
«Sin zona» como texto y no se escribe «Sin oficina».

**Motivo:** la misma celda se leía de dos maneras según la vista, y la causa era
medible: en «Abiertos» la columna de estado es más ancha que en «Cerrados» —«En
progreso» ocupa 103 px frente a los 79 de «Cerrado»—, la de afectado crecía con ella
y la pastilla «Sin zona» saltaba a una tercera línea. No era un problema de
espacio: era que el contenido se repartía según el hueco que le tocaba.

**Consecuencia:** tres cosas que parecen menesteres y no lo son, y que se decide por
el significado y no por la forma. **«Sin oficina» desaparece cuando no hay zona**:
son dos formas de decir lo mismo —no sabemos dónde está esta persona— y juntas
llenaban la celda de avisos. **Sin zona no hay pastilla, hay texto**: la pastilla con
su punto de color sirve para distinguir una zona de otra, y sin zona no hay color que
distinguir, así que una etiqueta con la misma forma que las de verdad hace creer que
hay un dato donde no lo hay. Y **la raya de color de la oficina solo se pinta cuando
hay un color que rayar**: antes se dibujaba siempre y, sin zona, heredaba el color
del texto, dejando una raya gris junto a «Sin oficina» que parecía un fallo de
pantalla.

> **Corrección posterior (ver § 99):** se revirtió la supresión de «Sin oficina» y de
> la pastilla sin zona. El diseño anterior —oficina con su raya y debajo la pastilla
> con su recuadro— se pidió explícitamente y es el que se quedó. Lo único que se
> mantiene de este apartado es lo que no estaba en discusión: **la estructura fija e
> igual en todas las vistas**, que era el problema real y medible.

## 95. El registro se conserva; lo que se enseña, no

**Decisión:** el historial muestra los estados con el nombre de hoy —«Estado: en
progreso → en espera»— y nunca con el valor interno ni con un estado retirado. El
documento guardado **no se toca**.

**Motivo:** al retirar «asignado» y «resuelto», los eventos antiguos se quedaron con
su nombre viejo, y en pantalla se leía «Estado: asignado -> en_espera» con estados que
no existen en el catálogo. Dos cosas horribles en una línea que promete ser precisa.
Traducir **al mostrar** y no al guardar es lo que permite las dos cosas sin mentir: el
registro sigue diciendo lo que pasó, y quien lo lee no tiene que buscar a qué
corresponde un estado que ya no existe. Cada estado retirado tiene un sustituto claro:
«asignado» era el paso previo a «en progreso», y «resuelto» ya no se distingue de
«cerrado».

**Consecuencia:** también se unifica la flecha —las transiciones viejas usaban «->» y
las nuevas «→»— y los estados se escriben en palabras, sin el guion bajo del valor de
la base, que es como se filtra y no como se escribe para que lo lea alguien. La
prueba comprueba las tres cosas a la vez, incluida que el documento guardado sigue
intacto.

## 96. Un dato que ocupa media pantalla no es un dato: es un aviso

**Decisión:** el «este ticket no tiene conversación» pasa de bloque ancho con color a
línea discreta con icono.

**Motivo:** en la mitad de la columna era **lo más llamativo de la página y lo menos
importante**. Es una comprobación, no un aviso: nada está mal. Y el agravante es que
en el tema activo el color de «informativo» y el de «aviso» son ambos ámbar, así que
un dato se leía como una advertencia. La página bajó de 1494 a 1444 px solo con esto.

**Consecuencia:** la altura de la ficha la ocupaba un dato, y ahora la ocupa el
contenido.

## 97. El nombre del actor no necesita su propio rol al lado

**Decisión:** el historial muestra el rol junto al nombre **solo cuando el nombre no
empieza por él**.

**Motivo:** con el administrador de la municipalidad cada línea decía «Administrador ·
administrador»: el mismo texto dos veces, en todos los eventos de todos los tickets.
No añade nada y ocupa media línea en el bloque más largo de la ficha.

**Consecuencia:** se conserva cuando el rol sí distingue —«Juan Pérez · técnico»—
porque ahí separa a una persona de otra, que es lo que un registro necesita.

## 98. Siete copias de lo mismo no son siete sugerencias

**Decisión:** `sugerir_para_ticket` deduplica por título y trae más candidatos por si
hay repetidos. **Los documentos repetidos no se borran.**

**Motivo:** la base de conocimiento tenía siete copias de cada artículo —28 documentos
para 4 títulos—, y el panel sacaba cuatro líneas idénticas. Cuatro veces la misma
respuesta no es una sugerencia: se lee como que la IA no sabe filtrar, y ocupa el
espacio donde cabrían cuatro soluciones distintas.

**Consecuencia:** el arreglo es del código y no de los datos, porque son datos de la
municipalidad y borrarlos es cosa suya. El código no vuelve a mostrar un título
repetido aunque la base los tenga. Queda pendiente decidir si se limpian los 24
documentos sobrantes.

## 99. Lo que se pidió es lo que se queda

**Decisión:** el diseño de zona y oficina vuelve al anterior —oficina con su raya,
debajo la pastilla de zona con su recuadro— en todas las vistas.

**Motivo:** el diseño anterior se pidió explícitamente tras verlo funcionando. Quitar
«Sin oficina» y el recuadro de «Sin zona» fue una decisión mía, tomada por el
razonamiento de que sobraba información, y salió mal: dos señales de «no sabemos
dónde está» en vez de una. La pastilla con su recuadro y su punto **sí dice algo**: que
el dato falta, y por eso tiene la misma forma que las de verdad.

**Consecuencia:** lo que se conserva del cambio anterior es lo que era un problema
medible y no una opinión: **la estructura fija e igual en todas las vistas**. El
reparto ya no depende de la anchura que deje la columna de estado, que es lo que hacía
que «Abiertos» y «Cerrados» se leyeran distinto.

## 100. Un porqué no es un aviso: se explica en una línea

**Decisión:** en la ficha del ticket y en la pantalla de registrar ticket, los bloques
«sin conversación» y «por qué no hay chat» dejan de ser `Nota tono="info"` y pasan a
una línea discreta con icono y texto atenuado.

**Motivo:** los dos son **porqués**, no avisos: nada está mal, se explica por qué este
caso no abrió conversación. Salían como un bloque ancho con el color del tema, y el
agravante es que en el tema institucional activo `--color-primary` y el de aviso son
ambos ámbar: una explicación se leía como una alarma. En la ficha ocupaba media
columna siendo lo menos importante de la pantalla; en el alta, media columna lateral
en una pantalla cuya única función es que escribas un caso.

**Consecuencia:** el mismo criterio en las dos pantallas, y no por gusto sino porque
es el mismo dato con la misma forma: una comprobación. La ficha bajó de 1494 a 1444 px
solo con esto. El componente `Nota` no se toca —sirve para lo que es un aviso—; lo que
se retira es el uso de un aviso para algo que no lo es.

## 101. El mismo bloque, el mismo canto, en las dos pantallas

**Decisión:** «Qué pasa», en el alta manual, lleva el mismo canto de color de 3 px que
«Descripción», en la ficha del ticket.

**Motivo:** los dos paneles son **la misma tarea**: escribir el texto libre del caso. El
que se reconociera en una pantalla y no en la otra obligaba a volver a familiarizarse
cada vez que se cambia de una a la otra.

**Consecuencia:** el canto va por `className` del `Panel` compartido y no por un
estilo nuevo, para que seguir siendo un rasgo de esta pantalla y no un cambio general
en todos los paneles de la aplicación.

## 102. Acotar la lectura solo donde el texto envuelve

**Decisión:** el ancho de lectura de 68 caracteres se aplica al texto que envuelve, no
al formulario. En el alta manual **se quitó**.

**Motivo:** acotar un párrafo que se parte en líneas no cuesta nada: ocupa lo mismo y
se lee mejor. Acotar una columna de campos deja una franja vacía a la derecha del
recuadro que no es breathing space sino un error de maquetación —parece que algo no
cargó—. Se vio funcionando y se deshizo antes de darlo por bueno, que es más barato
que dejarlo puesto y que el usuario pregunte por qué el panel no llega al borde.

**Consecuencia:** regla para el futuro: el límite de medida va en el texto, nunca en
el contenedor de un formulario.

## 103. Traducir un nombre es fácil; traducir sin perder el cambio, no

**Decisión:** un estado retirado se muestra con el nombre de hoy **salvo que el estado
del que se sale y al que se llega acaben llamándose igual**. En ese caso se deja el
nombre de entonces y se marca «(estado antiguo)».

**Motivo:** la regla de §95 —«el registro se conserva; lo que se enseña, no»— parecía
suficiente, y no lo era. El ticket TKT-2026-000092 tenía el evento
`en_progreso → asignado`, y con la traducción fija se leía **«Estado: en progreso →
en progreso»**: una transición a sí mismo. Es peor que el estado viejo, porque el
estado viejo al menos era verdad y lo nuevo parece un fallo de la pantalla. No salió
de un test: salió de mirar el historial real después de arreglarlo, que es cuando se
comprueba si un arreglo lo estaba de verdad.

**Consecuencia:** la traducción se comprueba antes de aplicarse, no después. Tres
reglas juntas y cada una con su motivo: se escriben en palabras, sin el guion bajo
del valor interno; los retirados llevan el nombre de hoy; y si el nombre de hoy
haría desaparecer el cambio, gana el nombre de entonces con su marca. El registro
guardado no se toca en ningún caso. Los tres casos quedan fijados en la prueba: el que
se traduce bien, el que se marca por el choque de nombres y el que no puede pasar.

## 104. El plazo se cuenta en horas de trabajo, y las dos cifras con el mismo reloj

**Decisión:** el plazo son **16 h de trabajo** como máximo —2 días de 8— y **las dos
cifras de la columna SLA salen del reloj de trabajo**: lo que queda y lo gastado.

**Motivo:** el error no era de cuentas, era de relojes. El reparto del plazo salía de
`sumar_minutos_laborables`, que respeta fines de semana y feriados; el tiempo restante
salía de `resolver_en - ahora`, que no los respeta. Los tickets TKT-2026-000093/94/95
se crearon el sábado y salían **«Quedan 2 días y 4 h» con la barra en 0 %**: la
primera cifra contaba la noche y el fin de semana, la segunda solo las horas de
labor. No era una discrepancia de redondeo, eran dos definiciones distintas de
«tiempo» en la misma celda.

**Consecuencia:** con un solo reloj, `lo que queda + lo gastado = el plazo` siempre, y
eso es lo que impide que el texto y la barra se contradigan. El invariante queda
fijado en una prueba. Además, un caso que vence el viernes **no se muere el sábado**:
antes, con el plazo contado en reloj, el técnico perdía el fin de semana sin haber
visto un caso.

**La trampa de probarlo:** el reparto depende del día de la semana, así que una
prueba con `utcnow()` puede pasar un sábado y romperse el lunes. Las pruebas nuevas
—no hay ninguna previa del SLA— usan fechas fijas (lunes 2 y viernes 6 de marzo de
2026) y **comprueban el día de la semana antes de usarlas**. También preguntan la
zona a la app en vez de suponerla: con un desfase `-5` supuesto, todas las fechas
caían en la hora equivocada y las pruebas medían otra cosa.

## 105. Cerrado no es «vencido»: en el historial cerrado no hay alarmas

**Decisión:** un caso cerrado sale **«Cerrado a tiempo»** (verde) o **«Cerrado con
retraso»** (ámbar), con la línea de debajo diciendo **cuánto tardó** y la barra en tono
neutro.

**Motivo:** antes salía «Cumplido» con una barra casi vacía —que se lee al revés— o
**«Vencido» en rojo con la barra llena**, dentro de una lista que se llama *Historial
cerrado*. Un caso ya resuelto no está vencido: se cerró tarde. La barra roja ahí no
informaba, alarmaba, y no había nada que hacer con esa alarma.

**Consecuencia:** conserva la estética —misma insignia, misma línea pequeña, misma
barra, mismas medidas— y cambia el contenido. El tono `neutro` se añadió a
`BarraProgreso` con ese único uso: barras que describen algo ya pasado no se pintan
de rojo ni de ámbar. El plazo original **se conserva en el dato** (§90): lo que se
retira es enseñarlo como si siguiera corriendo. Los estados `cumplido` y el uso de
`vencido` para cerrados desaparecieron de la lista, y no había ningún otro sitio que
los leyera.

## 106. Las columnas miden lo mismo en todas las vistas

**Decisión:** cada columna declara su ancho en `meta.ancho` y la tabla usa
`table-fixed` con `<colgroup>`.

**Motivo:** con `table-layout: auto` el navegador reparte según lo que hay escrito en
cada momento, y las columnas de la bandeja —que son las mismas en las tres vistas, las
tres usan el mismo componente— se repartían distinto: la del ticket medía 205 px en
«Abiertos» y 192 en «Cerrados», la fila pasaba de 96 a 92 px y el título **«Estado y
prioridad» se partía en dos líneas en una vista y en una en la otra**. No es que una
estuviera mal: es que al saltar de una a otra el ojo tiene que volver a buscar cada
columna.

**En porcentaje y no en píxeles.** Con `table-fixed` y anchos fijos en px, si suman
más que el panel la tabla no encoge: se desborda, y en cuanto la ventana baja de 1440
sale barra horizontal. En porcentaje las columnas bajan todas juntas en la misma
proporción —que es lo que las hace iguales entre vistas— sin barra. Los siete
porcentajes suman 100 a propósito.

**El mínimo de 1110 px y por qué.** Con puro porcentaje, por debajo de 1440 el
contenido se recortaba: «Cerrado con retraso» cortado 16 px a 1280 y 47 px a 1100, y
la fila pasaba a medir 112 px en unas y 96 en otras. Recortar es peor que
desplazar —«hace 15 horas» cortado deja de ser una fecha—, así que la tabla tiene
`min-w-[1110px]`: por debajo de ese ancho sale la barra horizontal, que ya tiene su
tirador pegado, y el texto se ve entero. **Es el precio de la decisión 106**: con
ventana de 1280 hay que desplazar 149 px. Se prefirió desplazar a recortar.

**Detalle que salió del camino:** con `truncate`, la columna no puede encoger por
debajo del texto, así que el navegador la ensanchaba por su cuenta y el ancho
declarado no se cumplía. Hizo falta `celdaLibre` en las columnas de texto y
`line-clamp-1` dentro. Las siete columnas terminan midiendo 190, 157, 168, 190, 145,
123 y 146 px a 1440, y también a 1280 y a 1100.

## 107. El calendario era martes a sábado, con la tarde corrida una hora

**Decisión:** la semana laboral es **lunes a viernes** y la jornada es
**08:00–13:00 + 14:00–17:00** —5 h por la mañana, una hora de descanso, 3 h por la
tarde, 8 h en total—. Corregido en los cuatro sitios donde vive el valor por defecto
y en lo que ya estaba guardado, con la migración 016.

**Motivo:** el error no estaba en el plazo, que ya era de 2 días laborables, sino en
el calendario contra el que se cuenta. Los días guardados eran `[1, 2, 3, 4, 5]` y el
índice es el de `datetime.weekday()`, donde **el lunes es 0**: lo que había era
martes a sábado, con el lunes fuera. Dos consecuencias que se ven sin buscar:

* las 16 h del plazo máximo ocupaban **lunes, martes y miércoles** en lugar de dos
  días, porque el lunes no contaba; y
* una prioridad crítica con 2 h de plazo, abierta el lunes a las 08:00, **no vencía
  hasta el martes a las 18:00**: un día entero de margen que nadie había pedido.

Y la tarde estaba corrida: los tramos guardados eran 08:00-13:00 y **15:00-18:00**,
cuando la jornada entra a las 14:00 y sale a las 17:00. Las dos sumaban 8 h, así que
el día laboral era el correcto y el error no se veía en ninguna cifra —solo en las
horas.

**Consecuencia:** con las dos cosas corregidas, las 16 h del plazo máximo caen **el
segundo día laborable**, que es lo que dice la norma. Comprobado con la app real:
un caso de prioridad baja abierto el lunes a las 08:00 **vence el martes a las
17:00** —el día acaba a las 17:00, no a las 18:00— y uno de prioridad media ese mismo
lunes **vence el lunes a las 17:00**.

**Por qué en cuatro sitios y no en uno.** El valor estaba en `config_service.DEFAULTS`,
en el esquema de la API, en la migración 003 y en el respaldo de `sla_service`. Que
viviera en cuatro copias es parte del problema: el comentario de la migración 003 ya
decía «lunes a viernes» y el valor al lado era martes a sábado, y eso es la clase de
error que sobrevive porque **el comentario miente en la dirección que uno espera**.
Ahora los cuatro dicen lo mismo y hay una prueba que lo comprueba de forma literal.

**Los plazos abiertos se recalculan; los cerrados no.** Como en la migración 014: un
caso ya resuelto conserva el plazo con el que se resolvió, porque ese plazo se fijó
cuando se creó y reescribirlo sería falsear lo que ocurrió.

## 108. «0 min» de retraso no es un dato: es un plazo agotado

**Decisión:** cuando a un caso vencido le quedan cero minutos de trabajo, la línea
de debajo de la insignia dice **«Plazo agotado»**.

**Motivo:** el backend marca «vencido» cuando el resto llega a cero, así que cero ya
es vencido — y un caso que venció el viernes y se mira el sábado tiene cero minutos
de retraso porque el fin de semana no se cuenta. La línea decía literalmente
**«0 min»**: era cierto y no significaba nada. Es la versión corta del mismo
problema del punto 1 de §104, en el otro extremo.

## 109. El SLA muestra el plazo que corresponde al momento del caso

**Decisión:** hay dos plazos por caso —**responder** y **resolver**— y el que se
enseña depende del estado: **`responder` mientras el caso está en «nuevo»**,
**`resolver` en cuanto alguien lo coge**. Ocupan el mismo sitio y se alternan solos.
El que corre viaja en `sla.modo` y toda la cuenta se hace contra él.

**Motivo:** un SLA con dos plazos que enseña siempre el segundo es un SLA con medio
sentido. Lo que importa de un caso sin tomar no es cuánto falta para arreglarlo —eso
depende de que alguien lo coja— sino **cuánto lleva sin que nadie lo coja**. Y en
cuanto alguien lo coge, lo único que importa es cuánto falta para arreglarlo. Los dos
datos son distintos y se alternan en el mismo sitio.

**Consecuencia:** la insignia dice **«Para cogerlo: …»** mientras está sin tomar. Sin
esa palabra, «Quedan 4 h» no dice si son cuatro horas para cogerlo o para
arreglarlo, que es justo lo que cambia según la fila. La barra también se mide contra
el plazo que corre: si corre el de responder y son 4 h, una barra al 50 % es la mitad
de 4 h. Los dos plazos se devuelven igual en sus propios campos para quien necesite el
otro.

## 110. Sin la fecha de aceptación, el SLA de responder no se puede medir

**Decisión:** asignar un caso en «nuevo» guarda `primera_lectura_en`, **solo la
primera vez**, para que reasignar no la mueva. Los casos que no la tienen la
reconstruyen del historial y la interfaz lo dice.

**Motivo:** el plazo de responder se calculaba y se guardaba, pero **el momento en que
alguien se hizo cargo no se guardaba al asignar**: solo cuando alguien movía el estado
a mano. De los 26 tickets de la base, 6 tenían la fecha y 20 no. Es decir, el acuerdo
que promete «responder en 4 h» **no tenía con qué compararse en cuatro casos de cada
cinco** —no por un fallo del cálculo, sino porque no se guardaba el otro término de la
comparación.

El motivo por el que no se guardaba es que asignar no es un cambio de estado (§82):
asignar mueve el caso a «en progreso» por su cuenta, sin pasar por la función que
escribe `primera_lectura_en`. La consecuencia de esa decisión, que era buena, fue
esta.

**Consecuencia:** para los casos anteriores, el momento se busca en el historial —el
primer evento de asignación o de cambio de estado— y se marca `reconstruido` para que
la interfaz pueda decir «Sacado del historial del caso». No es un adorno: avisa de que
la cifra sale del registro y no de un campo del documento, que no es lo mismo. Los
minutos son **laborables**, como todo el SLA.

## 111. Un equipo se elige de una lista; el texto libre no decide

**Decisión:** el equipo de un ticket **se elige siempre de una lista**, nunca se
escribe. Si no hay equipo enlazado, se anota solo el **tipo** y el caso queda sin
equipo.

**Motivo:** el alta manual tenía un cuadro de texto libre que, al guardar, buscaba
lo escrito en el inventario con una coincidencia **sin anclar** —que el texto esté
*dentro* del nombre— y se quedaba con el primero. Medido en el inventario real:

* «CPU» coincide con **6 equipos de 5 zonas distintas**, y el sistema se quedaba con
  uno de PALACIO;
* «COMPUTADORA N°01 - TECLADO» aparece **52 veces** repartidas entre MERCADO, PISCINA,
  PALACIO, SEGURIDAD y COMPLEJO.

Escribiendo el nombre exacto tampoco se sabe cuál es. **Solo el código patrimonial
identifica un equipo**: 461 de 876 lo tienen y ninguno está repetido.

El efecto era peor que un equipo equivocado: el ticket quedaba enlazado a una
máquina ajena, y su historial de fallos, su zona y su conjunto pasaban a ser de
otro. Un nombre inventado de equipo no es un dato aproximado: es un enlace a algo
que no es.

**Consecuencia:** el componente `SelectorEquipo` ofrece los equipos de la persona
afectada —con su zona al lado— y, si no tiene ninguno, lo dice con palabras: *«no
tiene equipos registrados a su nombre»*. El tipo se anota aparte y es **verdadero**:
«es un CPU» ayuda al triage sin inventar una máquina. Para enlazar un equipo que no
es de la persona se hace desde la ficha del caso, donde también se elige de la lista.

**El portal ya lo hacía bien** y no se tocó: él elige de la lista de sus equipos y no
tiene forma de escribir un nombre. El que estaba roto era el alta manual.

## 112. Un tipo se guarda aunque no haya equipo

**Decisión:** `activo_tipo` se rellena con lo que venga aunque no haya `activo_id`.

**Motivo:** es la diferencia entre un dato verdadero y uno falso. «Es un CPU» es
información sobre el caso; «es la computadora N°01 de PALACIO» es una afirmación sobre
el inventario que el técnico no puede verificar y que a veces es mentira.

## Corrección: Maicol sí tiene equipos

En un mensaje anterior se le dijo a la persona usuaria que la usuaria Maicol no tenía
equipos a su cargo. **Era falso**: tiene uno, `Mause17` (Mouse), en PALACIO, dentro
del conjunto «Computadora N°2». Se comprobó contra la API después de montar el
selector, que la devolvió en la lista.

Lo que sí es cierto, y se comprobó dos veces, es que **ni Maicol ni el usuario
administrador tienen zona ni oficina en su ficha**. Por eso sus tickets salen «Sin
zona» aunque su equipo esté en PALACIO: la zona del ticket viene de la persona, que
es lo que determina a qué oficina hay que ir.

Consecuencia de fondo: el fallo del alta manual era más visible de lo que parecía,
porque el equipo real de Maicol **no es un CPU sino un ratón**, y el sistema le
colgó un CPU de PALACIO.

## 113. Un tipo anotado se ve; no se tira por no haber equipo

**Decisión:** cuando no hay equipo enlazado pero sí tipo, la celda muestra el tipo
y debajo **«Sin identificar»**. Solo si no hay ninguno de los dos, «Sin equipo».

**Motivo:** al registrar «Es un CPU» y guardar, la bandeja decía «Sin equipo». El
tipo estaba guardado y no se enseñaba. Eso no es un dato escondido: se lee como
que al registrar el caso se perdió algo, y hace dudar de si el alta salió bien.

La segunda línea dice «Sin identificar» y no se deja el tipo suelto, porque un
«CPU» a secas parece el nombre de un equipo. Aquí no se sabe qué máquina es, y el
texto lo dice.

## 114. En «equipos a cargo», el icono lo decide el tipo y el conjunto no manda

**Decisiones de diseño del selector de equipo:**

- **Rótulo sobre la lista.** Sin él no se sabe que las filas se eligen.
- **Agrupado por conjunto**, que es como están de verdad: en lista plana no se ve
  qué piezas forman la misma máquina.
- **El nombre del conjunto va sin negrita.** Con ella, el contexto pesaba más que
  la elección.
- **El icono sale del tipo.** Había un disco duro en todas las filas, y al lado de
  «Mause17 — Mouse» afirmaba algo falso —el mismo error que el componente evita,
  en pequeño—. Se compara sin acentos ni mayúsculas, con disco duro solo como
  último recurso.
- **La lista de uso común no se pide si la persona no tiene oficina.** La consulta
  quedaba sin filtro de oficina y habría devuelto todos los equipos sin
  responsable, que son 875 de 876. **No puede pasar hoy** —el esquema exige
  `oficina_id` como ObjectId—; queda como red de seguridad.

## 115. La zona se pregunta antes que la oficina

**Decisión:** el alta de equipo pide **zona y luego oficina**. La oficina queda
bloqueada hasta elegir zona, y solo salen las de esa zona. La zona sale con su
número de oficinas al lado.

**Motivo:** antes era un desplegable con las **59 oficinas** del municipio y sin más
información. No había forma de saber en qué zona iba a quedar el equipo —la pregunta
que se hacía al registrar—, y buscar «ALCALDIA» entre 27 oficinas de PALACIO, 12 de
COMPLEJO y 11 de MERCADO es adivinar.

La zona **no se manda al backend**: `crear_activo` la copia de la oficina. Se pregunta
para poder filtrar y para no registrar en una zona sin querer, no porque el servidor
la necesite. Al cambiarla se sueltan oficina y conjunto, que si no el backend
responde «el conjunto pertenece a otra oficina».

## 116. Los conjuntos existentes se ven; un nombre nuevo es la excepción

**Decisión:** el conjunto se elige de un desplegable con los de esa oficina y su
recuento («Computadora N°01 · 4 equipos»). El campo de nombre nuevo solo aparece si
se elige «Crear uno nuevo».

**Motivo:** antes había un cuadro en blanco con la sugerencia del sistema al lado y
**ninguna forma de ver qué conjuntos había**. El estado `conjuntoId` existía en el
componente pero nada lo rellenaba: estaba muerto. El backend ya traía `total_activos`
y no se usaba.

Lo que evita se ve en los datos: en ALCALDIA conviven **`Computadora N°02 · 4
equipos`** y **`Computadora N°2 · 1 equipo`**, que es la misma computadora con dos
nombres. Con 261 conjuntos en el municipio, escribir el nombre a ciegas produce
duplicados casi siempre.

La consulta espera a que haya oficina: sin ella salían los 261, y `listar_conjuntos`
hace **una consulta al inventario por conjunto** para contar equipos y calcular
completitud.

## 117. Un formulario de tres pasos no se cierra por un clic perdido

**Decisión:** el panel del alta de equipo no se cierra al pulsar fuera. `Sheet` tiene
`cerrarFuera`, activo por defecto, y el alta lo apaga. La X y Escape siguen
cerrando.

**Motivo:** se perdían tipo, marca, modelo, código y los tres pasos de progreso por un
clic fuera del panel, sin aviso. Cerrar un formulario lleno es un gesto
deliberado, y quien lo hace ya tiene la X delante.

## 118. El buscador busca lo que se escribió

**Decisión:** lo tecleado se escapa antes de ir a `$regex`.

**Motivo:** el texto iba **tal cual** dentro de la expresión, así que los caracteres
que tienen significado en una expresión cambiaban lo que se buscaba. Comprobado
contra la base:

| tecleado | resultado |
|---|---|
| `a*b` | **17 tickets** — `a*b` es «cero o más a seguido de b», no la palabra |
| `a[bc` | error 500 — expresión inválida |
| `COMPUTADORA N.1` | **9 equipos** — el `.` casaba con el `°` de «N°1» |

Con `re.escape` se busca lo que se escribió. Antes de aplicar esto se dijo que
`PC (recepción)` daba un error 500, y **es falso**: con los paréntesis balanceados la
expresión es válida —un grupo de captura— y devolvía cero resultados en silencio.

## 119. Guardar una vista se explica en tres líneas

**Decisión:** el diálogo dice qué hacer —«Ponle un nombre y aparecerá como un botón
para volver aquí con un clic»— y enumera lo que se guarda con su valor actual. Nada
más.

**Motivo:** la descripción anterior —«Un atajo con lo que estás viendo ahora. Al
pulsarlo se recupera todo esto de golpe»— no decía qué hacer, y la ayuda del campo
de nombre repetía lo mismo que la descripción. Medido: pasó de unas 90 palabras a
**47**.

El detalle de «**pero no su orden**» se comprobó contra el código y se queda porque
es verdad: `guardarVista` manda `columnas: columnasVisibles` —un array, con orden—,
pero `DataTable` lo aplica con `setVisibles(Object.fromEntries(columnas.map(...)))`,
que construye el mapa **en el orden de la definición de columnas**. El orden se
pierde al aplicarlo, aunque se guarde.

## 120. Un cierre, un aviso

**Decisión:** la prueba que cubre el aviso de resolución exige **exactamente uno**,
no «al menos uno». Cerrar otra vez el mismo caso no puede añadir otro.

**Motivo:** en la base municipal hay **cuatro tickets con dos avisos** de «Problema
resuelto» cada uno, dos de ellos con **40 y 17 segundos** de diferencia y con el
ticket cerrado **una sola vez** —`cerrado_en` coincide con el primer aviso y el
segundo no cambió nada—. No es cerrar, reabrir y cerrar: eso dejaría una reapertura
en la línea de tiempo.

Con `no_leidas >= 1` el duplicado pasaba inadvertido: la prueba pedía justo la
condición que deja pasar lo que se quería evitar. La nueva comprueba la
cantidad exacta y **pasa**, así que el fallo era del código anterior a unificar los
estados y **hoy no se reproduce**. Los avisos viejos siguen ahí; borrarlos es una
decisión de la municipalidad, no del código.

## 121. La confirmación del alta no puede contradecir el formulario

**Decisión:** la pantalla de revisar lee el estado de la casilla, no el nombre
guardado. Si «es parte de un conjunto» está desmarcada, sale «No aplica». Y
desmarcarla vacía el conjunto elegido **y** el nombre.

**Motivo:** eran dos estados que se contradecían. La sugerencia del sistema rellena
el nombre solo, y al desmarcar nadie lo vaciaba, así que la confirmación anunciaba un
conjunto que no se iba a guardar. Peor: `conjuntoId` **no se limpiaba**, y como
`guardar` hace `conjuntoId || crearConjunto()`, un equipo se guardaba enlazado a un
conjunto que se había desmarcado a propósito.

La lección es la de siempre: cuando un formulario tiene un interruptor, desmarcarlo
tiene que hacer **lo mismo que no haberlo marcado**. Aquí no lo hacía.

## 122. Marcar «es parte de un conjunto» obliga a decir cuál es

**Decisión:** no se puede guardar con la casilla marcada si no se ha elegido un
conjunto existente ni escrito un nombre. En la revisión sale «Sin elegir».

**Motivo:** la misma contradicción al revés. Se marcaba la casilla, no se elegía
nada, y el equipo se guardaba suelto con la casilla puesta.

No estorba en el camino normal porque la sugerencia del sistema rellena el nombre
automáticamente; solo se nota si esa llamada falla, y entonces el campo aparece
vacío y el botón no deja continuar hasta escribir.

## 123. En una tabla, todas las filas miden lo mismo

**Decisión:** el distintivo del conjunto va en la primera línea, junto al nombre, y
**solo aparece cuando el nombre del equipo no empieza por el del conjunto**.

**Motivo:** el distintivo iba en una tercera línea y las filas tenían dos alturas
—**68 px sin conjunto, 87 px con él**—, que en pantalla se leía como un salto a
mitad de la tabla. El conjunto es raro: **1 de 876 equipos** lo tiene, así que casi
todas las filas pagaban la excepción.

El «solo cuando aporta» no es decoración. Con estos datos el equipo se llama
«Computadora N°01 - Monitor» y su conjunto es «Computadora N°01»: el distintivo
repetía el nombre y, de paso, el nombre se cortaba. Es la misma regla que ya
funcionaba en la columna EQUIPO de la bandeja.

## 124. El código patrimonial no compite con nada por el hueco

**Decisión:** el distintivo va en la primera línea, nunca en la segunda.

**Motivo:** se probó al final de la segunda línea y daba filas iguales, pero
cortaba el **código patrimonial** —«CPU · CYBERLINK CASE…» en vez de «CPU ·
CYBERLINK CASE · 740899500012»—.

El orden de lo que vale la pena en esa celda se decidió con los datos, no con
gusto: el código lo tienen **461 de 876 equipos y ninguno está repetido**, o sea
que es lo único que identifica una máquina. El conjunto lo tiene **1 de 876**. Un
dato que identifica no puede perder contra uno que se repite.

## 125. «Inventario vacío» y «los filtros no dejan pasar nada» son dos cosas

**Decisión:** el estado vacío pregunta primero si hay algún filtro puesto.

**Motivo:** no lo preguntaba. Buscando «zzzznoexiste» salían **dos** estados
vacíos, y el segundo decía *«registra el primer equipo si el inventario está
vacío»* con **876 equipos** en la base. Peor que el texto equivocado: es una
instrucción que no toca el problema, porque buscar otra cosa no se arregla
registrando un equipo.

No se puede saber por el total, porque el que devuelve la API ya viene filtrado:
con cero no distingue las dos situaciones. Se lee de los propios filtros, que es
donde está la respuesta.

## 126. Un aviso, un formato, un sitio

**Decisión:** la alarma de dato repetido es **una sola línea** junto al campo, dice
cuál se repite con enlace a su ficha, y lleva el resto en la explicación.

**Motivo:** eran tres cosas en dos sitios: el número, el nombre en una línea aparte
y un recuadro grande con la lista. Una misma información, tres veces. El recuadro
ocupaba media pantalla y el nombre ya estaba en el campo.

## 127. La alarma va en su línea propia, no junto al desplegable

**Decisión:** la alarma se coloca debajo del campo, no al lado del desplegable de
disponibilidad.

**Motivo:** medido, esa columna mide **327 px** y el desplegable se come 130. Al
lado, «Computadora N°01 - CPU» se cortaba en «Computador…»: el aviso quedaba
inútil justo cuando hacía falta. Debajo tiene todo el ancho, y con el ancho acotado
y el recorte con puntos un nombre enorme no empuja nada.

## 128. El conjunto se cambia desde la ficha del equipo

**Decisión:** la ficha tiene un desplegable de conjunto con los de esa oficina y su
número de equipos. Al cambiar de oficina se suelta, igual que el responsable.

**Motivo:** el alta elegía conjunto pero el equipo ya creado no se podía cambiar.
Un equipo registrado suelto que acababa siendo parte de una computadora no tenía
salida salvo darlo de baja y volver a registrarlo, con todo lo que arrastra: se
pierde el historial de fallos, el responsable y las notas.

La consulta espera a que haya oficina: sin ella salían los **261** conjuntos del
municipio, y el backend hace una consulta al inventario por conjunto.

## 129. El conjunto tiene que ser de la oficina, también al editar

**Decisión:** al editar un equipo, el conjunto se comprueba contra la oficina
**resultante**, que puede ser la que viene en el mismo cambio.

**Motivo:** al crear ya se comprobaba; al editar no. Como la ficha permite cambiar
oficina y conjunto a la vez, un equipo podía quedar en MERCADO con un conjunto de
PALACIO: datos que se contradicen entre sí, y que rompen el agrupado por conjunto.

Es el mismo motivo por el que desmarcar «es parte de un conjunto» en el alta suelta
el conjunto elegido: una elección anulada tiene que soltarlo todo, no solo una
parte.

## 130. Cambiar un caso invalida todo lo que ese cambio cuenta

**Decisión:** asignar, cambiar de estado, cerrar y reabrir invalidan las listas de
tickets, la ficha, los conteos por equipo, la analítica, la campana y las
notificaciones.

**Motivo:** recarga**ban la ficha y nada más. Con `staleTime` de 30 s y
`refetchOnWindowFocus: false` —que es deliberado, para que la bandeja no
parpadee—, todo lo demás se queda con lo viejo. Medido: volver a la bandeja tras
ver un caso hace **0 peticiones**, o sea que se sirve de caché.

El efecto era que **cerrar un ticket lo dejaba así en la cola de abiertos**, y el
resumen y la ficha del equipo seguían contando el caso como pendiente. Los
conteos por equipo tardaban más: 60 segundos de caché propia.

## 131. Una etiqueta dice qué se mide; el valor dice cómo salió

**Decisión:** en «Cuándo se cogió», la etiqueta es «Plazo de respuesta: 4 h» y el
valor lleva el veredicto: «Cumplido» o «50 min tarde».

**Motivo:** la etiqueta era fija —«Dentro del plazo de 4 h»— y el valor variable. Un
caso aceptado **50 minutos tarde** mostraba las dos cosas a la vez, en la misma
casilla: la etiqueta afirmaba que se cumplió el plazo y el número que no. Dos
verdices opuestos en la misma línea se leen como que uno de los dos está mal, y
ninguno lo está.

## 132. Lo pendiente pesa más que lo ya cerrado

**Decisión:** en la ficha del equipo, un ticket abierto es una fila marcada con su
número y un enlace «Ver»; el historial cerrado es una línea discreta debajo.

**Motivo:** eran dos enlaces del mismo peso visual. El abierto —sobre el que hay
que actuar— pesaba igual que un caso cerrado de hace un mes. Y el plural salía
mal: «Ver los 1 tickets abiertos».

## 133. Un gráfico sin etiquetas no es un gráfico

**Decisión:** todo panel de barras lleva su nombre visible, y los tipos que no
existen en el catálogo se marcan como tales.

**Motivo:** «Por tipo de equipo» pintaba quince barras con su porcentaje y el nombre
en blanco, porque leía `fila.tipo` y la API devuelve la etiqueta en `nombre`. Media
pantalla de la página dedicada a medir la calidad del inventario dedicada a un dato
que no se podía leer.

## 134. No se suman porcentajes

**Decisión:** los paneles de porcentaje ya no muestran suma; dicen que cada barra
lleva su valor al lado.

**Motivo:** ponía «Suma: 1.096 %». Sumar el porcentaje de completitud de 59 oficinas
no produce nada: dos oficinas al 50 % no están «al 100 % de algo», están al 50 % cada
una. El número no iba con nada y tenía toda la pinta de ir.

## 135. Una suma, Solo si la suma significa algo

**Decisión:** el panel de datos que faltan dice que son 2.028 **datos**, y explica
que un equipo puede salir en varias barras.

**Motivo:** decía «Suma: 2.028 equipos». El backend cuenta un equipo una vez por
cada campo que le falta, así que la suma nunca son equipos distintos: era un número
que no correspondía con la unidad que tenía escrita al lado.

## 136. Un filtro que no lee la URL no se puede enlazar

**Decisión:** el filtro por tipo del inventario se lee de la URL y se escribe en ella,
como el resto.

**Motivo:** arrancaba siempre vacío y no se escribía nunca. El enlace del ranking por
tipo —y cualquier enlace guardado o pegado— llegaba sin filtrar. Un enlace que no
filtra es peor que no tenerlo: parece funcionar.

## 137. Un dato que no está en el catálogo se señala, no se corrige solo

**Decisión:** el ranking por tipo marca los que no están en el catálogo.

**Motivo:** 8 de 15 «tipos» no son tipos —son estados, avisos del Excel y hasta un
código de patrimonio— y son 33 equipos. Señalarlos convierte la mitad del panel, que
antes era ruido, en una lista de trabajo.

**No se corrigen solos.** Decidir que «LAPTO» es un Laptop y que «INOPERATIVO» iba
en la columna de estado es criterio sobre el inventario real, no una regla que se
pueda aplicar a ciegas. Y son datos de la municipalidad.

## 138. Una cifra sin su definición no se puede leer

**Decisión:** al principio de la página se explica qué es el porcentaje, una sola vez.

**Motivo:** los gráficos decían «0 %» sin más. Un «Monitor · 0 %» se lee como «no
hay monitores con datos», cuando lo que significa es que a ninguno de los 181 le
falta cero campos. Con el número solo, no hay forma de saber si la cifra es
tranquila o alarmista.

Es la misma razón por la que «Chaque barra tiene su valor escrito al lado» existe:
un gráfico hay que poder leerlo sin tener que saber de memoria cómo se calculó.

## 139. Un título de panel dice qué se está mirando

**Decisión:** los cuatro gráficos llevan título y una frase que explica qué miden y
qué se puede hacer con ellos.

**Motivo:** «Por zona» no dice si es el porcentaje de equipos completos, el número
de equipos o los datos que faltan, ni si se puede pulsar. Un título corto es
legible; un título que no dice qué hay debajo obliga a averiguar mirando.

## 140. Un filtro que no está en la URL no se puede deshacer

**Decisión:** los filtros de Calidad van en la URL, como los del inventario.

**Motivo:** se guardaban en el estado del componente. El botón «Atrás» del navegador
no deshacía el filtro —la vista era la misma—, y no se podía compartir ni guardar
una vista filtrada.

Es la segunda vez que aparece esto en el proyecto —el filtro por tipo del inventario
era el primero—, y por eso conviene que sea la norma: **todo filtro que cambie lo
que se ve, vive en la URL**.

## 141. Al filtrar, se dice cuántos elementos quedan

**Decisión:** con un filtro puesto se muestra cuántos equipos entran en él, y aparece
un botón para quitarlo.

**Motivo:** un porcentaje suelto no dice nada sin su denominador. El 0 % de
PISCINA MUNICIPAL es de 36 equipos; el 0 % de MERCADO, de 142. Y quitar el filtro
obligaba a acordarse de qué había puesto uno mismo.

## 142. Cuando dos cifras son verdad y solo una se entiende, se enseñan las dos

**Decisión:** la barra y el indicador grande miden **datos escritos** («de 4.049 casillas
hay 2.021»). El porcentaje de **equipos con todos sus campos escritos** no desaparece: se
queda en el detalle de cada fila y en un indicador aparte.

**Motivo:** el 0 % de PISCINA MUNICIPAL no era un error. Hay 36 equipos y ninguno
completo, así que 0 % era la respuesta correcta a la pregunta que se estaba haciendo. El
fallo era que esa pregunta —«¿qué parte de los equipos está entera?»— no es la que se
quiere responder. Lo que se quiere saber es cuánto de lo que hay está escrito, y esa cifra
nunca es 0 mientras haya algo. Medido: las zonas pasaron de 4 de 5 a **0 de 5** a 0 %, y las
oficinas de casi todas a **0 de 14**.

**La regla:** cuando dos cifras son ciertas y solo una se entiende de un vistazo, gana la
que se entiende —y la otra no se borra, porque también es información—. Ocultarla sería
una pantalla más bonita y menos honesta.

## 143. Pulsar un gráfico abre lo que hay que arreglar, no todo

**Decisión:** los enlaces de zona, tipo y oficina en Calidad llevan `solo_faltantes=1`: el
inventario se abre con solo los equipos incompletos.

**Motivo:** pulsar «PALACIO» y encontrarse los 511 equipos, de los que 414 no tienen ni el
código patrimonial, no es filtrar: es cambiar de pantalla sin ahorrar trabajo. Lo que se
va a hacer con ese dato es completar campos, y para eso la lista tiene que ser la de los
que los tienen huecos.

El filtro ya existía en `inventario_service.listar` (`solo_faltantes`, línea 707) y lo
aceptaba el esquema: faltaba que la pantalla lo ofreciera. **Que el backend tenga algo
listo no significa que esté hecho**; lo que cuenta es si hay forma de llegar a ello.

## 144. Un filtro que llega puesto tiene que poder quitarse

**Decisión:** el interruptor «Solo los que tienen algún dato sin escribir» está en el
inventario, marcado si el filtro llega en la URL, y se puede desmarcar.

**Motivo:** un enlace que trae un filtro puesto y no deja quitarlo es una jaula. Si se
llega desde Calidad y lo que se quiere es ver todo el PALACIO, tiene que poder volverse
atrás desde la propia pantalla, sin acordarse de qué se puso antes.

## 145. Una lista larga se recorta por lo peor y se explica cuántas quedan

**Decisión:** las oficinas muestran las 12 con más datos sin escribir, de peor a mejor, con
un botón para ver las 59. El botón solo existe si hay más de las que se enseñan.

**Motivo:** 59 filas son dos pantallas de alto sin forma de saber cuántas faltan, y además
venían ordenadas por **cantidad de equipos**, no por calidad: la lista empezaba por las
oficinas más grandes, que no son las que hay que ir a arreglar. Recortar por lo peor hace
dos cosas a la vez: la página cabe y lo que se ve es lo que importa. Y decir «se muestran
las 12 con más pendientes de 59» evita el «¿y el resto?» que sale solo.

## 146. Una escala de 0 a 100 tiene que tener un significado en cada extremo

**Decisión:** el porcentaje de Calidad es **datos escritos**, y el detalle de cada fila
dice **«X de Y datos escritos»**. El recuento de «equipos con todo escrito» desaparece de
las filas.

**Motivo:** «PISCINA MUNICIPAL · 36 equipos · 96 sin escribir · 0 completos · 36 %» tiene
dos ceros y un 36 %, y nada indica cuál es el bueno. Con «54 de 150 datos escritos» al
lado del 36 %, el número se demuestra solo; con «0 de 15 datos escritos» al lado del 0 %,
también.

La razón de fondo: **una cifra de 0 a 100 solo sirve si el 0 y el 100 significan lo mismo
que en la vida real**. Aquí el 0 % era «ningún equipo de este grupo está entero» y el
100 % era «está todo escrito»: dos preguntas distintas en la misma barra. Se queda la que
funciona con los dos extremos.

## 147. Una barra a 0 % se dibuja vacía

**Decisión:** en 0 no se pinta nada de la barra. El mínimo de 2 px se aplica solo al tope
del 100 %, para que un 99 % no se salga.

**Motivo:** el mínimo existía «para que la barra se notase», y produce justo lo contrario
de lo que se quería: un 0 % con un trocito de color se lee como «hay algo escrito». Si no
hay nada escrito, la pista vacía **es** el mensaje.

## 148. Dos mandos para lo mismo se quitan: se deja el que tiene nombre

**Decisión:** en las tablas con desborde horizontal se oculta la barra del navegador y se
deja el tirador propio de `DataTable`. Se quitó la prop `mostrarDesplazamiento`.

**Motivo:** en el inventario se veían dos barras horizontales —la gris con flechitas del
navegador y, debajo, la pista redondeada de la aplicación— para desplazar lo mismo. En
las tablas cortas no se notaba porque el desborde no llegaba a aparecer, que es lo que
hizo que pasara tanto tiempo sin Verse.

Se queda el tirador propio porque es el que está diseñado: tiene tooltip, permite
arrastrar el pulgar y saltar a la posición con un clic en la pista. La regla general: si
hay dos formas de hacer la misma cosa, se conserva la que tiene nombre y se quita la que
aparece por defecto.

## 149. Lo que se puede pulsar tiene que decirse al pasar por encima

**Decisión:** las filas pulsables de los gráficos se pintan de crema al pasar el ratón,
ganan una marca dorada a la izquierda y una flecha a la derecha. Las que no hacen nada se
quedan sin nada de eso.

**Motivo:** el hover era `muted/60`, un gris tan parecido al de la pista que no se veía:
había cinco zonas pulsables y ninguna decía cuál. Un elemento que abre otra pantalla tiene
que señalar que es pulsable **antes** de que se pulse, no después.

Y el detalle de no marcar las que no son pulsables: si todo se resalta al pasar por encima,
resaltarse deja de significar «esto se abre».

## 150. La columna que responde «¿y esto qué va a pasar?» no puede ser la última

**Decisión:** en la previsualización de la importación, «Acción» va de primera y **pegada al
canto izquierdo**, y el encabezado de la tabla queda fijo al bajar.

**Motivo:** estaba en la columna 20 de 20, y con 1.744 px de tabla en 1.066 de hueco **nunca
se veía sin arrastrar hasta el final**. Es la pregunta de esa pantalla entera —crear,
actualizar u omitir— y era la única que no se podía contestar mirando la tabla. Fijarla al
canto izquierdo hace que siga ahí al desplazar, que es cuando hace falta.

De paso, hoja y número se fundieron en una columna: «ZONA COMPLEJO» estaba escrito tres
veces seguidas en cada fila, y tres columnas para un dato son dos que sobran.

## 151. Un aviso repetido 39 veces no informa: se agrupa y se cuenta

**Decisión:** las advertencias de la importación se agrupan por mensaje, con la cantidad de
filas afectadas y sus números.

**Motivo:** se hacía una tarjeta por fila y eran **58 tarjetas para 2 frases distintas**. El
segundo mensaje quedaba enterrado bajo 38 repeticiones del primero, y nadie iba a leer 38
veces lo mismo. Lo que sirve antes de abrir el Excel es «esto le pasa a 36 filas, son la 3,
la 4, la 7…».

La regla: **un dato repetido no es más información, es la misma información ocupando sitio**.
Si un aviso sale idéntico en 39 filas, se dice una vez y se cuentan las 39.

## 152. Una comprobación que no puede fallar no es una comprobación

**Decisión:** se quitaron el aviso «el desglose no coincide con el total», la cifra
«Filas contadas: 39 / 39» y la condición que comparaba `filas.length` con `total_filas`
en el botón de importar.

**Motivo:** el backend arma `total_filas = len(filas)`. Los dos números son la misma
variable, así que la comparación **siempre sale cierta**: el aviso en rojo no se veía nunca
y el botón nunca se apagaba por eso. Parecían una red de seguridad y no eran nada.

Peor que no servir de nada: si el backend llegara a devolver una muestra —que es lo que
habría que hacer con los 877 equipos—, ese guardia no avisaría, dejaría el botón apagado sin
explicación y nadie sabría por qué no se puede importar. Una comprobación vacía estorba
cuando empieza a ser cierta por casualidad.

## 153. Dos rutas al mismo dato, la misma llave

**Decisión:** `GET /importacion/{lote_id}` exige `equipos.importar`, como ya lo exigía
`GET /importacion/{lote_id}/resumen`. Con prueba que lo cubre.

**Motivo:** la ficha del lote solo exigía estar conectado. Cualquier cuenta de la
aplicación —una persona que únicamente reporta tickets— podía abrir el análisis del archivo
que importó el municipio: su nombre, sus hojas y la estructura de sus columnas.

El problema no es que faltara un permiso en una ruta, es que **había dos rutas al mismo
dato con distinta puerta**. Cuando eso pasa, la que está mal no se sabe cuál es. La regla
que queda: si dos endpoints devuelven la misma cosa, los dos comprueban lo mismo.

## 154. Una lista que se corta y no se puede seguir no es una lista

**Decisión:** la previsualización de la importación pagina de 100 en 100, con Primera,
Anterior, Siguiente y Última, y dice en qué página estás.

**Motivo:** antes se pintaban 100 filas de 875 y se informaba con «Muestra de 100 de 875».
Era una lista con final y sin medio: **solo se podía revisar el 11 % del archivo**, y esta
pantalla existe justo para revisar antes de importar. Una revisión parcial se lee como
completa, que es el peor estado posible.

Subir el tope de 30 a 100 en la ronda anterior no arreglaba nada, solo hacía la lista un poco
menos corta. Lo que hace falta para revisar un archivo entero es poder recorrerlo entero.

## 155. Un número que parece un error se explica o no se muestra

**Decisión:** el titular del resultado lleva los números y lo que significan: «Se
actualizaron 875 equipos que ya estaban», con la frase de que actualizar no es duplicar.

**Motivo:** decía «Inventario importado» sobre «Se crearon 0 equipos y se actualizaron
875». Un 0 en «creados» se lee como «no se hizo nada» y el titular verde remata la lectura.
Lo que había pasado era lo normal de una reimportación: los equipos ya estaban.

La regla: **un número que por sí solo parezca un fallo necesita su explicación al lado**.
Si no cabe en el titular, va debajo, pero va.

## 156. Lo que el sistema hace en silencio, se dice

**Decisión:** el resultado muestra las zonas, oficinas y conjuntos que la importación creó,
aunque fueran cero.

**Motivo:** `confirmar` devolvía `zonas_creadas`, `oficinas_creadas` y `conjuntos_creados` y
la pantalla no los miraba. Si el archivo traía una zona que no existía, **se creaba sin que
nadie se enterara** hasta aparecer en otra pantalla. Importar no es solo cambiar datos: crea
estructura, y lo que crea hay que contarlo.

## 157. Un aviso verde al lado de un bloque rojo se contradice

**Decisión:** el aviso flotante del resultado va en verde si no hubo errores y en amarillo si
los hubo.

**Motivo:** salía con tilde verde y el texto «Importación terminada con errores», al lado de
una lista roja de fallos. Un aviso tiene que poder leerse solo: si el color y el texto no
dicen lo mismo, uno de los dos está mintiendo.

## 158. Un paso obligatorio que no se puede aceptar no es un paso: es una jaula

**Decisión:** el bloque de responsables del Excel tiene tres salidas, no dos: confirmar
todo, **vincular todas como nuevas de una vez** y **continuar sin vincular**.

**Motivo:** solo se podía elegir una por una o cerrar la página. Con el Excel municipal,
que trae decenas de nombres, la primera opción es una hora de desplegables y la segunda
equivale a perder el resultado. Faltaba la salida obvia: seguir sin tocarlo.

Vincular un responsable equivocado se corrige desde la ficha del equipo en un clic.
Quedarse atascado en una lista de cuarenta desplegables no tiene arreglo, y por eso la
salida de seguir sin vincular es igual de importante que la de hacerlo bien.

Las tres acciones van **encima** de la lista: con la lista a la vista occupies casi una
pantalla, y quien solo quería continuar tenía que bajar hasta el final a buscar el botón.

## 159. Volver atrás tiene que poder deshacerse: si no, es una trampa

**Decisión:** el `Stepper` recibe la prop `alcanzado`: el último paso que se sabe que se
completó, aparte del que se está viendo.

**Motivo:** al activar el Stepper para poder retroceder, el paso «Resultado» quedaba
**deshabilitado**, porque el componente solo marcaba como hechos los pasos que estaban
por detrás del actual. Se podía volver al archivo y no se podía volver al resultado.

El componente tenía además un campo `hecho` declarado en su tipo y **nunca usado**. La
regla que queda: **una acción de retroceso sin su camino de vuelta no es una acción de
retroceso**, es una trampa. Si se puede ir atrás, se puede venir.

## 160. Un botón que no aparece debería explicar por qué

**Decisión:** cuando la importación no se puede deshacer, el botón «Deshacer» no se
muestra pero sí se explica la razón y qué hacer en su lugar.

**Motivo:** «Deshacer la importación» solo existe si no hubo actualizaciones —deshacer
solo tiene sentido cuando lo único que se hizo fue crear—. En el caso real del usuario
fueron 875 actualizaciones, así que el botón desaparecía sin más.

Un botón que se va sin explicación parece un fallo o un castigo. La ausencia también
necesita motivo: si no se puede deshacer, hay que decir por qué y dónde corregir.

## 161. Dos botones que hacen lo mismo son uno, y se distinguen por lo que no hacen

**Decisión:** el bloque de responsables pasa de tres botones a dos con recuadro:
«Continuar sin vincular» y «Confirmar y crear N perfiles nuevos».

**Motivo:** «Confirmar 263 personas» —con todo ya marcado en «crear»— y «Vincular todas como
nuevas» terminaban en el mismo sitio. Offering dos caminos idénticos no da libertad, da la
impresión de que hay dos opciones cuando solo hay una.

Los que quedan se separan por lo que **no** hacen: el primero no crea ninguna cuenta, el
segundo sí. Esa es la decisión real —¿quiero que existan estas personas o no?— y por eso el
recuadro de cada botón dice qué va a pasar con los equipos, no solo cuál es el botón.

## 162. Un botón que decide por ti lo que no debería

**Decisión:** ningún nombre del Excel viene preseleccionado como «crear perfil». Solo se
preseleccionan las coincidencias **exactas**, que no crean nada.

**Motivo:** todo nombre que no estuviera en ninguna cuenta salía marcado como «crear». Con
el archivo municipal eran **263 personas decididas de antemano**, y el botón de confirmar
solo formalizaba una decisión que ya estaba tomada. Crear una cuenta no es un detalle: a
partir de ahí alguien puede reportar tickets con ese nombre.

Medido: de 22 casos de prueba, **0 preseleccionados como «crear»**; antes 21 de 23.

## 163. Un botón global no puede pisar lo que elegiste a mano

**Decisión:** el botón de confirmación rellena **solo los que siguen vacíos**, con «crear».

**Motivo:** el botón anterior ponía «crear» en las 263 filas, incluidas las que el usuario
acababa de emparejar con una cuenta real. Elegías cuatro coincidencias a mano, pulsabas el
botón para resolver el resto, y las cuatro volvían a «crear». El usuario lo reportó tal cual:
«si yo cambio alguna como confirmar una coincidencia y los demás los dejo como crear perfil
sin credenciales no puedo continuar simplemente».

La regla: **una acción que actúa sobre todo el conjunto nunca debe pisar lo que alguien
eligió dentro de ese conjunto**. Si hay que rellenar lo que falta, se rellena lo que falta.

## 164. Lo que el sistema va a hacer por sorpresa se explica antes

**Decisión:** el bloque explica, en un recuadro, qué significa «crear un perfil sin
credenciales» y que no pueden entrar al sistema.

**Motivo:** la pregunta «¿qué es esto y cuándo se usa?» es la reacción correcta a un botón
que crea 263 cuentas. Sin explicación, la única forma de no surprises es no tocar nada y
quedarse con el trabajo a medias.

La respuesta, en la propia pantalla: añade a la persona a Usuarios para que sus equipos
dejen de estar sin dueño, **no puede entrar al sistema** porque se crea sin correo ni
contraseña, y hasta que alguien le asigne una cuenta solo sirve como responsable.

## 165. Si solo hay campañas cerradas, se muestra la primera

**Decisión:** si no hay ninguna campaña abierta, se selecciona automáticamente la primera de
la lista.

**Motivo:** solo se elegía la que estaba **abierta**. Con la campaña del municipio ya cerrada,
la pantalla quedaba con el chip y el histórico y nada más: ni indicadores, ni lista, ni una
palabra explicando por qué. **Una pantalla vacía sin explicación parece rota**, y quien llega
no tiene forma de saber que lo que tiene que hacer es pulsar el chip.

La regla: **si hay algo que mirar, se muestra de entrada**. Que se vea es lo que permite
entender que está cerrado y que por eso no se puede seguir verificando.

## 166. Una lista que no tiene final no es una lista

**Decisión:** paginación de 25 con Primera, Anterior, Siguiente y Última, en la lista de
equipos de la campaña.

**Motivo:** se veían **25 equipos de 875** y no había ningún control para moverse. El
trabajo de sala se paraba en el equipo número 26 y no había forma ni de notar que quedaban
850 detrás. Con 35 páginas, llegar a la última tiene que ser un clic.

## 167. Un botón que no puede hacer nada se quita, y se dice por qué

**Decisión:** en una campaña cerrada los botones «Encontrado» y «Ausente» no se pintan —solo
la palabra «Verificación cerrada»— y aparece arriba un aviso explicando que los cambios ya
se aplicaron al cerrarla.

**Motivo:** el backend los aceptaba y guardaba el cambio, pero `cerrar` **ya se había
ejecutado**: nadie volvería a volcar esos cambios al inventario. Los indicadores subirían a
«875 verificados» en una campaña archivada y el trabajo se perdía en silencio.

La regla: **un control que el sistema no puede honrar es peor que ninguno**, porque ocupa
sitio, parece funcionar y traga el trabajo. Y lo que sí importa —por qué— va escrito, no
deducido.

## 168. Lo que nadie llegó a mirar no se puede marcar como ausente

**Decisión:** el diálogo de cierre enseña cuántos están verificados y cuántos sin verificar,
y dice que **los pendientes no se marcan como ausentes**.

**Motivo:** el diálogo prometía «los equipos que no se localizaron quedarán marcados para
seguimiento», y eso no era cierto: `cerrar` solo marca los que alguien marcó como ausente.
Los que nunca se llegaron a buscar se quedan como están.

Y no es un detalle de redacción: **no se puede afirmar que un equipo no está donde dice si
nadie fue a mirarlo**. Con la campaña del municipio, 875 pendientes y ninguno verificado, se
cerró y los 875 quedaron «pendiente» para siempre, sin que la pantalla lo dijera.

La regla: **un diálogo de confirmación dice qué va a pasar exactamente, con los números
delante**. «Se cierren 875 equipos» es una acción; «se marcan los que no se localizaron» es
una promesa que no se estaba cumpliendo.

## 169. En una sala se busca el sitio, no el equipo

**Decisión:** el buscador de la campaña busca por nombre, código, **oficina, zona y
responsable**, y escapa el texto con `re.escape`.

**Motivo:** solo miraba el nombre y el código del equipo. Buscando «PISCINA» salían cero
resultados aunque la zona PISCINA MUNICIPAL tuviera 36 equipos en la campaña: en una sala lo
que se sabe es dónde está el equipo, no cómo se llama. Medido después: 36 equipos.

El `re.escape` es el mismo criterio que ya se aplicaba en la búsqueda del inventario y por el
mismo motivo: `a*b` —un asterisco es perfectamente normal al teclear un código— dejaba la
regex sin cerrar. La regla ya escrita: **todo lo tecleado se escapa antes de ser expresión
regular**.

## 170. Un número de personas creadas no es un comprobante

**Decisión:** el resultado de vincular responsables del Excel devuelve un **detalle por
persona**, y la pantalla final lo muestra entero.

**Motivo:** solo volvían dos contadores y el bloque se sustituía por «No quedan responsables
del Excel sin vincular». Se sabía **cuántas** personas se crearon, pero no **quiénas**, ni en
qué zona. Con el archivo municipal son cientos: un número no confirma nada y no deja revisar
si lo hecho era lo que se quería.

La regla: **una acción que crea registros tiene que dejar ver los registros**. El detalle
lleva nombre del Excel, nombre asignado, si se creó o se vinculó, oficina, zona, tipo de
coincidencia con su similitud y cuántos equipos quedan con esa persona.

## 171. La decisión irreversible se marca; el botón solo la aplica

**Decisión:** dos casillas excluyentes —«crear los que faltan» y «no vincular a nadie»— y un
único botón «Continuar».

**Motivo:** eran dos botones grandes que actuaban los dos al instante. Eran fáciles de
confundir justo en el momento de decidir si se crean 263 cuentas, y el error sale caro: una
cuenta creada es alguien que puede reportar tickets con ese nombre.

Con casillas, la decisión **se puede leer y deshacer** antes de aplicarla. Y la tercera
situación —no marcar ninguna— es la que hace útil el bloque: se avanza con lo elegido a mano y
**no se crea nada por sorpresa**. Antes, la única forma de no crear cuentas era no tocar el
bloque.

La exclusividad tiene un precio: marcada una, la otra queda inhabilitada y hay que desmarcar
para cambiarlas. Como eso no es evidente, **la casilla inhabilitada lo dice**. Un control que no
responde sin explicar por qué parece roto.

## 172. Lo que se hizo en bloque se marca para revisión, no se da por bueno

**Decisión:** la pantalla final resalta los casos que **podrían** estar mal, con el motivo
escrito: nombre del Excel igual al de la oficina, coincidencia parecida con su porcentaje, y
perfil creado sin cuenta.

**Motivo:** vincular responsables en bloque es una decisión que se toma a ciegas sobre cientos
de nombres. La mayoría están bien; las que no, no se notan nunca porque quedan enterradas en
una lista verde de «todo correcto».

Se marcan **tres** y solo tres, y ninguna es un error comprobado: son las que un humano puede
rechazar de un vistazo. Las coincidencias exactas no se señalan porque no hay nada que mirar.
El bloque dice «podrían estar mal», no «están mal»: afirmar lo segundo sin comprobarlo sería
mentir.

## 173. Un campo que se deduce de otro no se escribe dos veces

**Decisión:** el año de la campaña se toma de la fecha de inicio. Desaparece el campo «Año».

**Motivo:** había un campo numérico «Año» y las fechas iban fijas al año completo, sin poder
tocarlas. Ahora hay calendario —una verificación empieza y acaba un día concreto— y con las
dos cosas se podía escribir **año 2026 y fechas de 2025**: nada lo impedía y la campaña se
archivaba bajo un año que no era el suyo.

La regla: **un dato que se deduce de otro no se pide dos veces**. Si aparece en dos sitios, en
algun momento no coincidirán.

## 174. «Solo algunas zonas» se explica con un número, no con una descripción

**Decisión:** el alcance se elige con opciones explicadas, y el diálogo pide al backend
**cuántos equipos entran** antes de crearla.

**Motivo:** era un desplegable con tres palabras sin explicación, y el efecto —cuántas
máquinas hay que ir a mirar en la sala— solo se descubría **después de crearla**, cuando
salía el error de alcance vacío. Para entonces ya se había escrito el nombre.

Un contador en vivo responde a la pregunta de verdad: no «¿qué incluye esta opción?» sino
«¿cuánto trabajo me voy a meter?». Además avisa antes de escribir nada, no al final.

## 175. El filtro no ofrece lo que no existe en la campaña

**Decisión:** los desplegables de zona y oficina se construyen a partir del `alcance` de la
campaña, y el panel dice cuál es.

**Motivo:** el backend **excluía** `zona_ids` y `oficina_ids` de la lista de campañas, así que
la pantalla no tenía forma de saber el alcance. Al filtrar una campaña de dos zonas salían
las siete, y elegir una tercera devolvía cero resultados sin explicación: parecía un fallo
de datos.

La regla: **un filtro ofrece lo que hay, no lo que podría haber**. Si el alcance está
acotado, decirlo también: que el número de opciones no es un capricho del diseño.

## 176. Marcar a mano tiene que ser reversible

**Decisión:** una fila ya marcada ofrece un botón **«Pendiente»** para deshacer la marca.

**Motivo:** solo había «Encontrado» y «Ausente», y los dos llevaban a un estado definitivo.
Marcar por error un equipo como ausente no tenía vuelta atrás: la fila se quedaba así hasta
que la campaña se cerrara. El backend ya aceptaba `pendiente`; faltaba el botón.

En una sala se va marcando con el dedo, con prisas y sin pantalla delante. **Una acción hecha
a mano, que se puede equivocar, tiene que poder deshacerse.** El botón va primero, a la
izquierda, porque es el que evita un error y no el que lo produce.

## 177. Una tabla que deja hueco a la derecha está rota

**Decisión:** las tablas de `DataTable` llevan `w-full` **siempre**, con independencia de que
todas las columnas declaren ancho.

**Motivo:** `w-full` estaba dentro de `conAnchosFijos && 'table-fixed w-full …'`, y esa
condición exige que **todas** las columnas visibles declaren `ancho`. La columna «Menú» de
Equipos no lo hacía, así que la tabla entera pasaba a reparto automático y se encogía al
contenido: medido, 1.028 px dentro de 1.181 —**153 px de vacío**— y, al ocultar columnas,
**1.114 px**.

La regla: **el ancho se define una vez, no por columnas**. Una columna sin ancho declarado no
puede desactivar el estirado de la tabla entera. Se le declara su ancho (`68px` para «Menú»)
y el problema desaparece de raíz.

**2 px** de hueco quedan: es el borde del panel.

## 178. Una barra de desplazamiento no puede estar debajo de 100 filas

**Decisión:** la tabla de previsualización de Importar tiene altura acotada
(`min(60vh, 620px)`) y se desplaza dentro en los dos ejes.

**Motivo:** el contenedor solo tenía desplazamiento horizontal, así que la barra para ir de
izquierda a derecha quedaba al final de las 100 filas. Para usarla había que bajar hasta el
final, que es justo lo contrario de lo que se busca al mirar una tabla ancha.

Acotando la altura, las dos barras quedan siempre a la vista. De rebote el encabezado —que ya
era `sticky`— acompaña al desplazamiento vertical, y al ir por la fila 700 se siguen viendo
los nombres de las columnas.

La regla: **si un control hace falta para usar la pantalla, no puede estar más lejos que los
datos**. Si está debajo del elemento que controla, está fuera de la pantalla.

## 179. Las capas fijas se ordenan, o la de abajo tapa a la de arriba

**Decisión:** `thead` a `z-20` y la celda de cabecera fija a `z-30`, por encima de las `z-10` de
los datos.

**Motivo:** al acotar la altura apareció que la celda fija de la primera columna —la insignia
«Se creará»— se pintaba encima del encabezado. Con el mismo `z` gana el que llega después en
el documento, y las celdas de datos llegan después que el `thead`. El síntoma era desconcertante:
la columna parecía llamarse «Se creará» en vez de «Acción».

La regla: **cuando dos elementos se fijan, el que va por delante tiene que declarar un orden
superior**. Un `z` igual no significa «a la vez»: significa «gana el último».


## 180. El inventario anual descubre lo que no está registrado

**Decisión:** la campaña de inventario anual tiene dos mitades y se enseñan las dos. Se sube el
Excel de lo que hay en la sala, se compara contra el inventario registrado, y lo que aparece en el
archivo y no en el inventario son **equipos nuevos**: se marcan y, al cerrar la campaña, se crean
en el inventario con la oficina y la zona de su hoja. El inventario del año que sigue arranca de lo
registrado, nunca de cero.

**Motivo:** el backend tenía el recorrido —documentado como _«modo actualizar: compara el Excel del
año nuevo contra el inventario actual»_— y la pantalla no lo mencionaba. Peor: el recorrido estaba
roto en las tres piezas que importaban. Se podían **detectar** equipos nuevos, pero no se podían
**registrar**:

| Pieza | Estado real |
|---|---|
| `importar_excel` comparaba y detectaba los nuevos | funcionaba |
| `aceptar_cambios` los aceptaba | **los tiraba en silencio**: buscaba el item por id, no lo encontraba porque los nuevos no eran items, y hacía `continue` |
| `cerrar` los aplicaba al inventario | **no los creaba**: no había rama para un equipo sin `activo_id` |

`nuevos_creados` estaba inicializado a cero y nunca se incrementaba: la firma de una función
terminada a medias.

La regla: **una función que el backend ofrece y la pantalla no usa no está hecha**. Y una variable
de contador que nunca se incrementa avisa de que el camino que la rodea está sin cerrar.

## 181. Aceptar no es crear: hay que decirlo

**Decisión:** marcar un equipo nuevo **no crea nada todavía**. Lo marca como «va a registrarse» y la
creación ocurre al cerrar la campaña. El botón dice «Marcar», no «Crear» ni «Registrar», y el
diálogo de cierre dice cuántos equipos van a entrar.

**Motivo:** quien usa esta pantalla está en una sala, con el Excel delante. Si marcar crea un equipo
y eso resulta que al cerrar se deshace —porque alguien cancela el cierre, o el equipo no tenía
oficina válida— se ha creado y borrado un equipo sin que nadie lo pidiera. La diferencia entre
«marcar» y «crear» no es de vocabulario: es de cuándo ocurre el efecto.

## 182. Un equipo que no existe no puede estar verificado

**Decisión:** `verificados` cuenta solo los equipos **registrados** a los que alguien los buscó en
la sala. Los equipos nuevos, marcados o sin decidir, van en sus propias cifras
(`nuevos_aceptados`, `nuevos_sin_decidir`) y quedan fuera del numerador y del denominador del
progreso.

**Motivo:** `verificados` era «todo lo que no estaba pendiente». Al marcar dos equipos nuevos —que es
lo único que se puede hacer con ellos— la pantalla ponía «Verificados 2» y un 67 % de progreso sin
que nadie hubiera buscado nada: esos equipos no estaban en ninguna sala, se acababan de descubrir en
un archivo. El número no era un poco optimista: describía una actividad que no había ocurrido.

La regla: **un indicador tiene que medir la cosa que dice medir**. «Verificados» midiendo
«resueltos» solo cuadra mientras todo lo que se resuelve esté verificado, y en cuanto hay una
segunda acción que no es verificar, deja de cuadrar sin que nadie se dé cuenta.

## 183. Solo `cerrada` está cerrada

**Decisión:** una campaña está cerrada si su estado es `cerrada`. `abierta` y `verificacion` son las
dos formas de seguir trabajando en ella.

**Motivo:** `verificacion` es lo que el backend pone **sola** en cuanto marcas el primer equipo. La
pantalla usaba `estado !== 'abierta'`, así que marcar un equipo dejaba la campaña entera
inservible: desaparecían los botones de verificar, el de cerrar y el de subir el Excel, y salía un
aviso de que «verificar ahora no cambiaría nada». Era falso —el backend solo bloquea con `cerrada`— y,
en el municipio, dos campañas de 877 equipos con un único equipo confirmado quedaban bloqueadas. Es la
razón de que la pantalla «no cumpliera su función».

La regla: **un estado intermedio no es un estado final**. Si el backend tiene tres estados y solo uno
cierra el ciclo, la pantalla tiene que distinguir los tres, no tractar «lo que no es el primero» como
el último.

## 184. Un índice único con `null` en la clave solo admite un `null`

**Decisión:** `uq_item_campana_activo` pasa a ser un índice **parcial**: la unicidad se aplica solo a
los items con `activo_id` real. Migración `017`.

**Motivo:** el índice era único sobre `(campana_id, activo_id)`. En Mongo un índice único trata
`null` **como un valor**, no como «no hay valor»: todos los equipos nuevos de una campaña compartían la
clave `(campana_id, null)` y **el segundo reventaba** la subida del Excel entera con `E11000
duplicate key`, un 500 sin explicación. Es decir, la función solo registraría **un** equipo nuevo por
campaña, justo al revés de lo que se le pedía.

La regla: **un índice único necesita una condición, no solo unas columnas**. La unicidad de «un
equipo, una vez en la campaña» solo habla de los items que ya son un equipo. Aplicarla a los que aún
no lo son no evita ningún duplicado real: impide que exista más de un `null`.

## 185. Recargar el mismo archivo tiene que dar el mismo resultado

**Decisión:** un equipo nuevo que se vuelve a detectar en otra subida del mismo archivo se queda como
«nuevo», con su item, y **refresca** tipo, nombre, código y oficina con los del archivo.

**Motivo:** dos fallos encadenados. El primero: el item se emparejaba y se comparaba contra una
instantánea vacía —un equipo nuevo no tiene datos previos—, así que salía como «con cambios». En
pantalla decía que un equipo registrado había cambiado de datos, siendo que no estaba registrado. El
segundo: aunque se corrigiera el Excel y se volviera a subir, el resumen seguía enseñando los valores
de la primera subida.

La regla: **una operación repetida tiene que ser idempotente en lo que muestra**. Si volver a hacer
lo mismo puede dar un resultado distinto, la pantalla está describiendo el historial en vez de la
realidad.

## 186. El tipo de equipo sale de «Tipo de equipo», no de «Dispositivo»

**Decisión:** el tipo del equipo nuevo sale de la columna mapeada como `tipo_equipo`; `dispositivo`
solo se usa cuando no hay tipo.

**Motivo:** en el Excel municipal, «Tipo de equipo» es `CPU` / `Impresora` y «Dispositivo» es `PC
NUEVA DE LA SALA`. Se leía `dispositivo` porque `tipo` no existe en `CAMPOS_BASE` —y por eso tampoco
en `mapeo`—, así que el equipo se iba a registrar con «PC NUEVA DE LA SALA» como tipo. Un equipo con
el tipo mal no aparece en los filtros por tipo ni en los esquemas de calidad: es un equipo mal creado
que no se nota hasta que alguien lo busca.

La regla: **el mapeo de columnas es la fuente de la verdad sobre la forma del archivo**, y hay que
mirarlo antes de asumir el nombre de un campo.

## 187. «Detectar» y «decidir» son dos cifras, y el cierre necesita las tres

**Decisión:** `nuevos_aceptados`, `nuevos_sin_decidir` y `nuevos_descartados` van por separado, y el
diálogo de cierre dice cuántos equipos se van a registrar y cuántos se quedan sin decidir.

**Motivo:** `nuevos` mezclaba lo detectado con lo decidido. El diálogo solo podía decir «se registrarán
N equipos» —donde N no existía— o no decir nada de lo importante. La pregunta que se hace al cerrar es
doble: _¿cuántos entran?_ y _¿me queda alguno por decidir?_; una sola cifra tiene que mentir en una de
las dos.

La regla: **un contador que mezcla dos preguntas no responde a ninguna**. Si al cerrar hay que elegir
entre decir la verdad a medias o no decir nada, es que el número estaba mal partido.

## 188. La campaña que se abre se elige por criterio, no por azar

**Decisión:** `campana_activa` devuelve primero la campaña `abierta` más reciente y, si no hay
ninguna, la `verificacion` más reciente.

**Motivo:** era un `find_one` sin orden sobre `{abierta, verificacion}`: la que salía dependía del
orden natural de la colección. En el municipio abría una campaña de 877 equipos ya empezada en vez de
la única `abierta`, que era la que se estaba creando.

La regla: **una consulta sin orden es una decisión que se delega al almacenamiento**. Si el resultado
importa, el orden se escribe.
## 189. La campaña de inventario anual nace vacía

**Decisión:** crear una campaña ya no congela una instantánea del inventario. Se crea con cero
equipos y se llena al subir el Excel de la sala.

**Motivo:** el usuario lo reportó como un fallo, y con razón: al crear una campaña aparecían
los 877 equipos que ya estaban en el inventario, sin que nadie hubiera subido nada todavía. La
lista de la campaña era **idéntica** a la del inventario, y no había forma de entender qué quedaba
por descubrir. Para descubrir equipos nuevos, lo único que importa es lo que hay en la sala, y eso
solo se sabe con el archivo.

Consecuencias:

* Desaparece el error «no hay equipos en el alcance elegido»: que el inventario esté vacío ya no
  impide crear una campaña, porque la campaña se llena con lo que se suba.
* El alcance se sigue guardando, pero para otra cosa: saber qué equipos registrados **no** aparecen
  en el archivo.
* Los equipos de la campaña pasan a ser los que salen del archivo (y los registrados del alcance que
  no aparecen en él), no una copia del inventario.
* El emparejamiento de cada fila se hace contra **`activos`**, no contra los items de la campaña: si
  solo se miraran los items —que al empezar están vacíos— todas las filas saldrían como equipo nuevo
  y los 877 ya registrados aparecerían como nuevos.

La regla: **una lista que se copia de otra no es un trabajo nuevo**. Si al empezar por lo único que
existe el resultado es indistinguible de no haber hecho nada, la pantalla no está ofreciendo
descubrir nada.

## 190. Una comparación es de una campaña y no sobrevive a cambiar de campaña

**Decisión:** al cambiar de campaña, la comparación, el archivo subido y los errores se borran.

**Motivo:** el resultado de la última subida se quedaba pegado. Al crear una campaña nueva, o al
cambiar de chip, el panel seguía enseñando los equipos nuevos, modificados y ausentes **del archivo de
la campaña anterior**, con su nombre de archivo arriba. Las cifras no correspondían a la campaña
abierta y la única forma de deshacerlas era recargar la página.

La regla: **un resultado pertenece a lo que se calculó sobre**. Si la pantalla lo muestra al lado de
otra cosa, está afirmando que son lo mismo.

## 191. Un año cerrado se descarga en el Excel del municipio

**Decisión:** cada año del histórico se descarga como `.xlsx` con **una hoja por zona** y las 16
columnas de la plantilla oficial. El inventario actual también se descarga, con los filtros que se
están viendo.

**Motivo:** no había ninguna forma de sacar el inventario. La plantilla oficial se podía bajar pero
vacía, y `exportar_inventario` —que existe— devuelve filas en JSON, no un archivo. Para el municipio,
que trabaja en Excel, «descargar» significa exactamente eso.

La regla del formato: **ida y vuelta**. El archivo que sale tiene que poder volver a subirse tal cual,
así que usa las columnas de la plantilla y una hoja por zona, que es la convención que ya entiende el
asistente de importación.

## 192. Un año guardado que no se puede descargar no existe

**Decisión:** la versión de cada campaña cerrada guarda los **datos completos** de sus equipos, no
solo código, nombre, oficina y responsable.

**Motivo:** guardaba seis campos sueltos. Eso impedía descargar el año: el Excel necesita la marca,
el modelo, la RAM, la zona, el estado… que no estaban. Lo único que sí había era el `activo_id`, así
que reconstruir el año obligaba a leer el inventario de hoy: **al descargar 2026 salía 2027 con otro
nombre**. Un archivo histórico que muestra el presente con la fecha de antes es peor que no tener
archivo.

Las versiones anteriores a esto se reconstruyen leyendo el inventario actual de los equipos que
siguen existiendo, y se deja constancia: es lo mejor que hay, pero no es el estado de aquel año.

La regla: **un histórico solo es histórico si guarda el pasado, no una referencia a él**.

## 193. La papelera está pegada a su campaña y el diálogo dice qué no se borra

**Decisión:** botón de eliminar junto a cada campaña, y un diálogo que enumera qué se borra y, en
negrita, que los equipos del inventario no se borran.

**Motivo:** en una pantalla de inventario, «Eliminar» sin explicación se lee como «va a borrar
equipos». Es justo lo que la gente va a temer, y basta con decirlo para que el botón sea usable. El
botón va **fuera** del que selecciona la campaña —un botón dentro de un botón no existe en HTML, y si
se construye encima con un `div` el clic para elegir la campaña acaba borrándola—.

**Nunca borra un equipo.** La campaña es un trabajo de revisión; lo que se registró al cerrarla ya
está en `activos`. Sí se borran los equipos nuevos pendientes que la campaña detectó pero nadie
aceptó: nunca llegaron a ser equipos y su lista volvería a salir en la próxima comparación.

La regla: **una acción irreversible declara su alcance antes de ejecutarse, y el alcance incluye lo
que no hace**.
## 194. Una campaña vacía no manda a importar el inventario

**Decisión:** el estado vacío de una campaña ofrece **Subir el Excel de la sala**, que abre el selector de archivo del panel de arriba. Ya no existe el enlace a Importar.

**Motivo:** ese botón llevaba a la pantalla de importación del inventario, y era un callejón sin salida con un riesgo añadido:

* Importar es **otra operación**: da de alta equipos en todo el municipio y **actualiza los que ya existen**, que es justo lo que conviene no hacer sin querer mientras se trabaja con esos equipos.
* **No llena la campaña.** La campaña se llena con el Excel de la sala, que se sube en la misma pantalla.
* Con la campaña naciendo vacía, ese mensaje salía en **todas** las campañas nuevas: el usuario caía en una pantalla que refresca 877 equipos sin avisar y de la que no era dueño.

La regla: **un botón de salida tiene que llevar a la operación que resuelve lo que falta**. Si lo que falta es el archivo de la sala, el botón abre el archivo de la sala.

## 195. «Actualizar» es sobrescribir, y eso se dice antes de hacerlo

**Decisión:** la previsualización de la importación avisa, con el número delante, de cuántos equipos **se van a sobrescribir** porque ya estaban en el inventario. Cuando todas las filas válidas actualizan, dice además que esto es una reimportación y no un alta.

**Motivo:** el número existía desde siempre, con la etiqueta «Actualizaciones», que se lee como «habrá novedades». No lo es. Importar **reescribe** los datos de los equipos que ya están: la marca, el modelo, el responsable que alguien escribió a mano. La explicación buena —«actualizar significa que ya estaba y se refrescaron sus datos»— estaba en el **resultado**, que llega cuando ya no hay nada que hacer. El aviso va antes, que es donde se decide.

La regla: **el aviso de un efecto irreversible va antes de aplicarlo, no después**. Después solo sirve para explicar lo que ya pasó.

## 196. Un filtro que no se puede aplicar no es un error

**Decisión:** un id de filtro mal formado se ignora en vez de devolver `422`. Un id bien formado que no existe filtra a cero, como cualquier filtro.

**Motivo:** los filtros vienen de la barra de direcciones: un marcador guardado de hace meses, una URL editada a mano, un enlace de Calidad con la zona equivocada. Con el id validado como si fuera uno de ruta, `?zona_id=x` devolvía `422` en dos endpoints y la pantalla se quedaba a medias con dos peticiones fallidas en la consola y sin explicar nada.

Hay dos piezas: `IdFiltro` en los esquemas y que `id_opcional` devuelva lo que venga. Los ids de **ruta** y de **cuerpo** siguen validándose igual: un identificador obligatorio que no lo es, es un error de quien llama, y se le dice.

La regla: **no es lo mismo un dato que no vale y un dato que no se puede aplicar**. Lo primero se dice; lo segundo se ignora.

## 197. El total de una campaña se cuenta, no se guarda

**Decisión:** `total_items` de la lista de campañas es el recuento vivo, no el que se escribió al crearla.

**Motivo:** `total_items` se guardaba en el documento al crear la campaña. Como ahora nace vacía, se quedaba en 0 para siempre: en el municipio había una campaña con **196 equipos ya subidos** que seguía diciendo que tenía 0. `{**campana, **_resumen(...)}` pone el resumen encima del documento, así que basta con que `_resumen` devuelva el número contado.

La regla: **un contador que depende de una acción posterior no se escribe al crear la entidad**. Se cuenta cuando se lee.

## 198. El año de la campaña se ve, y avisa si el nombre lo contradice

**Decisión:** el chip de campaña muestra `nombre · año · estado`. Si el nombre contiene un año y las fechas dicen otro, el diálogo de creación lo dice con los dos números y cuál manda.

**Motivo:** el año sale de la fecha de inicio, no del nombre —decisión propia, 173—, y eso no se veía en ninguna parte. En el municipio hay dos campañas, «Inventario 2026» y «inventario 2027», y **las dos están archivadas como 2026** porque el calendario viene precargado con el año en curso. Sin el año a la vista eran dos campañas indistinguibles; con él, el problema se ve en el chip, antes de cerrar nada.

El nombre no manda sobre el año —el año es de las fechas—, pero tampoco puede contradecirlas sin avisar.

La regla: **un dato que se deduce de otro y no se escribe puede contradecirlo**. Si el texto dice una cosa y el sistema otra, hay que mostrar las dos y decir cuál gana.
## 199. Desactivar es una puerta, y una puerta tiene vuelta atrás

**Decisión:** la pantalla pide también lo desactivado, lo marca, y ofrece **Reactivar** al lado de
**Desactivar**.

**Motivo:** el backend sirve solo lo activo por defecto (`solo_activas=True`), y la pantalla pedía
exactamente eso y solo ofrecía desactivar. El resultado: **al desactivar una oficina desaparecía de
la pantalla sin dejar rastro y no había forma de recuperarla desde la aplicación** — había que entrar
a la base de datos. Una pantalla de configuración con un botón sin vuelta no es una puerta, es una
trampa. En el municipio ya había cuatro elementos desactivados que nadie podía volver a activar sin
SQL.

La regla: **una acción reversible tiene que ofrecer la inversa en el mismo sitio**. Si no, no es
reversible: es un borrado con otro nombre.

## 200. Desactivar avisa de lo que se lleva, no solo de lo que conserva

**Decisión:** el diálogo de desactivar dice tres cosas: qué se desactiva, que deja de ofrecerse al
elegir zona, oficina o responsable en todo el sistema y que sus equipos se quedan sin oficina a la que
asignarse, y que es reversible desde ahí mismo.

**Motivo:** decía «los registros históricos se conservarán», que era la mitad de la verdad. Lo que
importa no es lo que se conserva, es lo que **deja de funcionar**: una oficina desactivada desaparece
de todos los desplegables del sistema, y sus equipos se quedan sin oficina a la que asignarse.

La regla: **un aviso declara el alcance, y el alcance incluye lo que no hace**. Decir solo lo que se
conserva invita a leer «no pasa nada».

## 201. Ciento dieciocho botones para tres acciones

**Decisión:** las acciones de fila van a un menú, como en Inventario.

**Motivo:** cada una de las 59 oficinas tenía **Renombrar** y **Desactivar** sueltos: 118 botones para
tres acciones distintas. La pantalla era un muro de botones y las oficinas —que son el contenido— se
leían de reojo. Medido: 66 botones «Renombrar» sueltos en la página, ahora **0** y 43 menús.

La regla: **una acción que se repite en cada fila no es una acción de la fila, es una acción de la
tabla**. Y en una fila, un menú.

## 202. Con 59 oficinas, buscar no es opcional

**Decisión:** buscador de zona **y** de oficina. Buscar el nombre de una oficina trae la zona que la
contiene. Y si no hay coincidencias, se dice y se ofrece limpiar.

**Motivo:** llegar a una oficina era recorrer cinco listas a ojo. Y con el buscador aparece un caso que
no existía antes: buscar el nombre de una zona y no ver nada. Sin mensaje, se lee como «no hay zonas».

La regla: **un filtro tiene que explicar por qué no pasa nada**, y ofrecer la salida.

## 203. Una zona con 27 oficinas no ocupa cinco pantallas

**Decisión:** las oficinas de cada zona van **paginadas de diez en diez**, con una página por zona.

**Motivo:** PALACIO tiene 27 oficinas y MERCADO 11. Con todo a la vista la página era un muro de 59
filas en dos columnas desiguales, y el 80 % de lo que se veía eran oficinas de una zona que no se
estaba tocando. Se probó primero con un botón «Ver las N más», que mejoraba el alto pero no el
salto: de 10 a 27 de golpe, con la página descuadrada y sin saber cuántas quedaban.

Con páginas se avanza de diez en diez, se sabe cuántas quedan —«Mostrando 11 a 13 de 13»— y se vuelve
sin buscar. **Cada zona lleva su propia página**: si el estado fuera compartido, al paginar PALACIO
cambiaría MERCADO, que está al lado.

Dos detalles que solo aparecen al implementarlo:

* **La página se acota a las que existen.** Al buscar, o al dejar de mostrar las desactivadas, una
  zona puede quedarse con menos oficinas: si estuviera en la 3 de 2, la lista saldría en blanco sin
  explicación. Con el acotado, vuelve a la última que existe.
* **Buscando se ven todas las oficinas de la zona, sin paginación.** El buscador es para encontrar
  una en concreto; esconder las demás detrás de un «Siguiente» sería devolver el problema que el
  buscador resolvió.

La regla: **lo que se muestra por defecto es lo que se suele necesitar**, y la navegación de lo que
sobra se hace en pasos medidos, no de una vez.

## 204. «Mostrar desactivados» es una preferencia, no un estado de la pantalla

**Decisión:** la casilla se guarda en `localStorage` (`org.ver-desactivados`) y se aplica desde el
primer dibujado.

**Motivo:** al salir de Zonas y oficinas y volver, los desactivados reaparecían solos y había que
desmarcarlos otra vez. Desmarcar es una decisión de quien mira —«ahora no quiero ver eso»—, no un
estado que deba reiniciarse al cambiar de pantalla.

Se lee **fuera de `useState`** a propósito: dentro, el valor guardado se aplicaría después del primer
dibujado y la pantalla aparecería un instante con los desactivados para luego quitarlos. Y si el valor
guardado llega corrupto, lo que no sea «false» se trata como marcado, porque una preferencia ilegible
no puede tumbar la pantalla. Verificado: desmarcado → 0 · tras recargar → 0 · tras venir de otra
pantalla → 0.

No va en la URL a propósito: nadie va a pegar un enlace con «y enséñame también lo que está apagado».

## 205. Un equipo sin responsable no es un equipo de nadie

**Decisión:** la ficha de oficina separa los equipos de uso común, los marca con su propia insignia y
explica en una línea que se pueden asignar.

**Motivo:** son dos cosas distintas y se leían igual. Una impresora compartida es **de la oficina**; un
monitor al que se le olvidó asignar dueño es un descuido. Sin decirlo, quien mira no puede saber cuál
de los dos es cuál, y el descuido se lleva en silencio.

Además, cada persona de la lista dice cuántos equipos tiene, o «Sin equipo». Antes, responder «quién de
esta oficina tiene equipos» obligaba a comparar mentalmente dos listas distintas.

Los vacíos también dejaron de ser el mismo texto en tres sitios. «No hay tickets abiertos» es una
buena noticia y se lee en verde; decirlo como «no hay registros» lo convertía en un fallo aparente.

## 206. Los equipos se agrupan por id de responsable, nunca por nombre

**Decisión:** `GET /oficinas/{id}` agrupa por `responsable_id` y lleva el nombre solo para leerlo. Cada
grupo devuelve `responsable_id`, `responsable` y `equipos`.

**Motivo:** con el nombre como clave, dos fallos silenciosos:

* dos personas que se llamen igual caían en la misma fila y sus equipos **se sumaban** como si fueran de
  una sola persona;
* un nombre con un espacio de más o una tilde distinta partía el grupo, y quien quedaba fuera
  **aparecía «sin equipo» teniendo los suyos**.

Ninguno de los dos da error: solo un número que no cuenta. Al recorrer las 59 oficinas no apareció
ningún caso —los nombres hoy sí casan—, lo que es exactamente el motivo para no dejarlo así.

El nombre sigue siendo la reserva para los grupos sin id, que sí existen: la importación del Excel
deja el equipo con el nombre escrito cuando la persona no aparece en el sistema. Esos equipos se
agrupan y **no** van a uso común, porque son de alguien concreto aunque todavía no tenga cuenta —
ocultarlos ahí haría creer que no tienen dueño.

## 207. El plural se calcula, no se escribe a mano

**Decisión:** `plural(n, palabra)` en `formato.ts`, usado en la ficha de zona, la de oficina y Zonas y
oficinas.

**Motivo:** el plural estaba concatenado en cada sitio y se colaba de formas distintas. En la zona
COMPLEJO, COMPROMISO 1 PADRON DOMINAL mostraba **«1 personas · 5 equipos»**. El diálogo de desactivar
tenía el problema doble: «Sus 1 oficinas siguen existiendo» —mal el plural y el verbo—, ahora «Su 1
oficina sigue existiendo».

Regla: **un número y su palabra van juntos**, porque es de las cosas que más se notan cuando salen
mal. Medido: 16 pantallas revisadas, 0 plurales mal concordados.

## 208. Medir el contraste componiendo el alfa, no leyendo el color

**Decisión:** al medir contraste hay que convertir el color a sRGB y componerlo sobre el fondo real,
incluida la opacidad.

**Motivo:** el encabezado de panel se calcula como `oklab(… / 0.6)` —semitransparente y en un espacio
de color que no es sRGB—. Leerlo como si fuera opaco dio un contraste de **3,40:1** y casi se «corrige»
un problema inexistente. Midiendo bien, el resultado real es **16,3:1** en títulos y enlaces y **6,9:1**
en el texto secundario.

Queda escrito porque el error es fácil de repetir y **el arreglo parece una tontería** cuando se
encuentra: parece que el problema era la pantalla, y no era la medición.

## 209. Tres pestañas en vez de dos columnas

**Decisión:** en la ficha de oficina, «Personas», «Equipos asignados» y «Uso común» son pestañas.

**Motivo:** no era un problema de tamaño sino de reparto. Medido: «Personas» con 6 filas al lado de
«Equipos por responsable» con 11 dejaba media pantalla en blanco bajo la columna corta, y en
GERENCIA DE ADMINISTRACIÓN TRIBUTARIA la diferencia era de 6 contra 38. Ninguna de las dos columnas
se puede acortar sin dejar de ver algo, así que la única salida es no ponerlas juntas.

Se usa el mismo sistema de pestañas del resto de la aplicación, y cada pestaña lleva su número para
saber qué hay en la que no se está mirando.

## 210. El uso común se pagina de diez en diez

**Decisión:** los equipos de uso común van paginados, con el mismo paginador de Inventario y de
Zonas y oficinas.

**Motivo:** medido sobre las 59 oficinas —de uso común, mediana 9, percentil 90 18, **máximo 28**— es
la única lista que se desborda de verdad. «Personas» llega a 11 y el grupo más grande a 12, que no
son un muro.

Solo lleva paginador si lo necesita: de las 59 oficinas, **18** lo ven.

## 211. Un recuadro ámbar para decir «no son de nadie» es un anuncio

**Decisión:** el aviso de uso común es una línea de texto apagado, sin fondo ni borde.

**Motivo:** era una `Nota` de tema ámbar y ocupaba media pantalla para repetir lo que ya decían el
título de la pestaña y la descripción del panel. Un aviso grande invita a leer algo que no es una
alerta. Medido: de bloque a **20 px de alto**, a lo ancho de la línea.

Por la misma razón se quitó la insignia «USO COMÚN» de cada equipo: repetida 27 veces dentro del
panel que ya se titula «Equipos de uso común», no informaba de nada.

## 212. El estado de un equipo se pinta con el catálogo de equipos

**Decisión:** la ficha de oficina usa `DisponibilidadBadge`, no `EstadoBadge`. Y `estadoDe` busca en
los dos catálogos.

**Motivo:** eran catálogos distintos. `EstadoBadge` es el de los **tickets** (`nuevo`, `en_progreso`,
`en_espera`, `cerrado`) y los equipos viven en `DISPONIBILIDADES` (`operativo`, `dado_de_baja`…). La
ficha pintaba el estado del equipo con el componente de ticket, así que **todas** las insignias
caían en «Estado no reconocido» y salían **gris**: el mismo equipo aparecía verde en Inventario y
gris en su propia oficina, sin que nada fallara.

Medido antes y después, con el `title` de la insignia, que es el texto de la definición:
antes «Estado no reconocido» y fondo `rgb(238, 242, 248)`; ahora «El equipo está en servicio» y
fondo `rgb(14, 92, 55)`.

La normalización de la clave hizo falta también: la base guarda los estados como los escribe el
Excel —«OPERATIVO», en mayúsculas— y los catálogos están en minúsculas con guion bajo. Sin eso,
`estadoDe` no encontraba nada aunque mirara el catálogo correcto. Se busca en los dos sitios, y si
aun así no aparece, el texto que se ve es el que vino: si alguien escribió «FUNDIDO», se lee
«FUNDIDO», no «fundido».

## 213. Borrar y desactivar no son la misma puerta

**Decisión:** el diálogo de desactivar ofrece abajo «Eliminar definitivamente», que abre **otro**
diálogo de confirmación, en rojo y con icono de aviso.

**Motivo:** desactivar es reversible y borrar no. Con solo desactivar, una zona u oficina creada
por error se quedaba para siempre en la lista, marcada, y la única forma de quitarla era entrar a
la base de datos.

No comparten botón: uno es «Desactivar» y el otro «Eliminar para siempre», separados por una línea.
El backend ya lo protegía y por eso el botón no es una puerta abierta: una zona con oficinas no se
borra, y una oficina con equipos no se borra. El diálogo dice por qué antes de intentarlo.

## 214. El tipo del equipo, en letra pequeña al lado del nombre

**Decisión:** cada equipo muestra su tipo en una columna propia, apagada y en letra pequeña; solo si
aporta algo.

**Motivo:** el icono ya dice algo —un monitor, un teclado— pero no se distingue un «Monitor» suelto
del de un conjunto, y en «DESKTPO-AOAAH4T» no dice nada. Con el tipo al lado la lista se lee sin
abrir cada equipo.

Si el nombre ya contiene el tipo —«Computadora N°01 - Monitor»— no se repite: «Monitor» debajo de
«Monitor» sobra.

La lista es una rejilla de cuatro columnas y no una fila de `flex` porque, con el panel al ancho de
la pantalla, la insignia quedaba pegada al borde derecho y a 800 px del nombre al que pertenece.
En columnas, el tipo y el estado se leen en vertical sin seguir la fila con la vista.

## 215. El tipo del equipo, en su propia métrica

**Decisión:** la ficha del equipo muestra el tipo en el subtítulo de la tarjeta y como métrica
«Tipo». Deja de usarse «Datos pendientes», que ya sale en la barra de completitud y en la insignia.

**Motivo:** el tipo no aparecía **en ningún sitio** de la ficha. El subtítulo era marca, modelo y
oficina, y las cuatro métricas eran estado, completitud, datos pendientes y responsable. Con
nombres como «PRINTGDS» o «DESKTPO-AOAAH4T» no había forma de saber que era una impresora: el icono
sí lo decía, pero un icono no se lee de lejos. Verificado sobre `PRINTGDS`: subtítulo «Impresora ·
EPSON L6270 · ASISTENCIA SOCIAL».

## 216. «Eliminar» va en el menú de la fila, no escondido dentro de desactivar

**Decisión:** el menú de cada fila de zona y de oficina tiene «Eliminar», en rojo, al final y
separado por una línea. El diálogo de desactivar ya no lo ofrece.

**Motivo:** antes estaba dentro del diálogo de desactivar, a dos clics. Eso obligaba a desactivar
primero para poder borrar, que es justo lo contrario de lo que se busca: desactivar es reversible y
sirve para «no la quiero ahora»; borrar es para «esta nunca debió existir». Meter la puerta
irreversible dentro de la reversible la esconde.

## 217. El aviso de borrado lo cuenta el servidor, no la lista

**Decisión:** `GET /{zonas|oficinas}/{id}/borrado` devuelve qué hay detrás, y `DELETE` usa la **misma**
función. El diálogo lo pide al abrirse y deshabilita el botón si hay algo que lo bloquee.

**Motivo:** los contadores de la lista no servían. El de equipos **filtra los dados de baja** y el
borrado no, así que el aviso podía decir «0 equipos» y el borrado responder «tiene 3». La prueba
`test_el_aviso_de_oficina_cuenta_los_equipos_dados_de_baja` fija justo ese caso.

Que el botón quede deshabilitado y no que falle al pulsarlo es a propósito: un botón rojo que
rechaza la pulsación no explica nada.

Los mensajes usan plural real —«1 oficina registrada», «13 oficinas registradas»— y no
«oficina(s)», que es lo que salía antes.

## 218. También en la zona se vuelve a «Zonas y oficinas»

**Decisión:** la ficha de zona lleva el mismo botón «Volver a zonas y oficinas» que la de oficina.

**Motivo:** estaba en la de oficina y no en la de zona, sin ninguna razón: son la misma relación y el
mismo origen. Entrar en una zona sin forma de salir con un clic es no tener el botón.

## 219. El tipo se enseña siempre, aunque el nombre ya lo diga

**Decisión:** el tipo del equipo se muestra siempre en las listas. Antes se ocultaba cuando el nombre
ya lo contenía.

**Motivo:** la regla parecía prudente —«Monitor» debajo de «Computadora N°01 - Monitor» sobra— y
salió justo al revés. Como **casi todos** los equipos del municipio se llaman «Computadora N°01 -
Mouse», «Computadora N°01 - Teclado» o «Computadora N°01 - Monitor», la columna quedaba vacía
precisamente en mouse, teclado y monitor, que son 526 de los 877 equipos.

Que la palabra se repita no es un estorbo: es la forma rápida de confirmar que el tipo guardado es el
que se cree, y sin columna no hay nada que confirmar.

## 220. Un icono por cada tipo del catálogo, no solo los que ya conocía

**Decisión:** el mapa de iconos cubre los **catorce tipos del catálogo**, cada uno con su dibujo y su
color. Los tipos que no se reconocen usan una caja neutra, no un disco.

**Motivo:** antes solo reconocía siete tipos —laptop, monitor, impresora, red, teclado, mouse y CPU—..
Los otros seis del catálogo (Tablet, Celular, Servidor, UPS, Disco duro externo y Sistema de audio)
**caían todos en el mismo icono genérico**: seis equipos distintos se veían iguales. Router y Switch
compartían dibujo.

Medido sobre el selector del alta, que es donde aparecen los catorce: 15 tarjetas (los 14 más
«Otro»), **15 dibujos distintos y 15 colores distintos**.

También reconoce lo que llega escrito de otra manera, porque el tipo viene del Excel: «portátil»,
«ratón», «multifuncional», «no-break», «parlante». Y **«LAPTO»**, que antes caía en el genérico
porque `/laptop/` no encuentra «lapto».

**El icono sale siempre del mapa.** La rama de «tipo no reconocido» traía su propio `HardDrive`
escrito a mano, así que cambiar el icono genérico en el mapa no cambiaba nada: «Otro» seguía
dibujándose igual que «Disco duro externo». Dos sitios que deciden lo mismo se desincronizan;
probado porque pasó.

## 221. El directorio de usuarios pide `usuarios.ver`, como su pantalla

**Decisión:** `GET /usuarios` exige `usuarios.ver`. Y `/usuarios/buscar` con el texto vacío no
devuelve nada.

**Motivo:** la pantalla de Usuarios está detrás de `usuarios.ver`, pero el endpoint **no exigía
ningún permiso**: bastaba con estar conectado. Una persona con cuenta de rol `usuario` —la que
reporta problemas— recibía el directorio entero: nombre, correo, teléfono, rol y oficina de las **267
cuentas**. La única guarda era «si no tienes oficina, devuelve vacío», que no es un permiso: quien
tiene oficina, que es casi todo el mundo, pasaba de largo.

En la ruta ya se importaba `DependeEditarUsuarios` y se usaba en crear y en restablecer contraseña;
faltaba el equivalente de «ver».

El buscador vacío tampoco: un desplegable de 40 nombres sin escribir una letra no es buscar, es
volcar el directorio en la pantalla del registro manual de tickets, al que llega la gente de la calle.

## 222. Una cuenta se puede desactivar **y** reactivar

**Decisión:** el perfil ofrece «Desactivar cuenta» y «Reactivar cuenta», y la lista tiene casilla
para mostrar las desactivadas, guardada en `localStorage`.

**Motivo:** el backend tenía `POST /usuarios/{id}/desactivar` y `PATCH {activo}`, y la pantalla no
llamaba a ninguno. Además la lista pedía solo las activas. El resultado: una cuenta desactivada
desaparecía del directorio **sin dejar rastro y sin forma de volver** — el mismo callejón sin salida
que se corrigió en Zonas y oficinas en la ronda BL.

Se usa el `PATCH` para los dos sentidos: el `POST` de desactivar solo sabe apagar, y dos caminos
para lo mismo son dos caminos que se desincronizan.

El aviso de desactivar dice lo que **no** se toca —historial, tickets y equipos— igual que se hizo
con las zonas.

## 223. El filtro de oficina se acota a la zona, y se suelta al cambiarla

**Decisión:** las oficinas del filtro son las de la zona elegida; al cambiar de zona, la oficina
anterior se suelta. Si aun así llegaran a ser incompatibles, se dice por qué.

**Motivo:** las 59 oficinas salían siempre. Se podía marcar zona COMPLEJO y oficina de PISCINA y
salir «0 resultados» sin explicación, y era fácil llegar ahí sin querer: al cambiar de zona la
oficina anterior se quedaba puesta y pasaba a ser de otra zona.

## 224. El motivo del rechazo se escribe dentro del diálogo

**Decisión:** cuando el servidor rechaza un alta y el motivo no viene por campo, se escribe arriba
del formulario, además del aviso.

**Motivo:** con un correo ya en uso, el formulario se quedaba igual de limpio y el campo no se
marcaba; la única pista era una pastilla en la esquina de la pantalla, con el diálogo abierto
delante. Un rechazo que hay que ir a buscar a otra parte de la pantalla no guía.

## 225. Un rótulo por dato, y el rol escrito en un solo sitio

**Decisión:** `etiquetaRol()` y `ROLES` en `formato.ts`; el perfil del usuario es una lista de
datos con rótulo en dos columnas, con avatar y rol.

**Motivo:** el filtro decía «Técnico TI» y la tabla aplicaba `capitalize` sobre el valor crudo, así
que un técnico salía **«Tecnico»**: sin tilde y con otro nombre. `capitalize` de CSS pone mayúscula,
no tilde.

El perfil eran seis `<p>` seguidos con los «No indicado» pegados al dato, sin jerarquía ni rótulos:
no se distinguía lo que falta de lo que vale.

## 226. La ayuda automática también es columna de la tabla

**Decisión:** la columna «Ayuda IA» sale en la tabla, no solo en la tarjeta del móvil.

**Motivo:** el encabezado de la página promete que cada fila dice si la persona tiene activa la
ayuda automática —es lo que explica por qué a alguien no le salen sugerencias— y la tabla no lo
decía. Solo estaba en la tarjeta, que se ve al girar el móvil.

## 227. Los responsables del alta de equipo son los de esa oficina

**Decisión:** el desplegable de responsable del alta de equipo pide el directorio filtrado por la
oficina elegida, y solo cuando ya hay oficina.

**Motivo:** pedía el directorio entero, así que ofrecía las primeras 25 cuentas de la municipalidad
sin relación con la oficina, en una pantalla que dice «Personas activas de la oficina elegida» y en la
que la oficina es obligatoria. Con 267 cuentas, quien se iba a hacer cargo del equipo tenía que
buscarse entre nombres de otras oficinas. Medido: antes 26 opciones sin elegir oficina; ahora **0**,
y **3** —las tres personas de ASISTENCIA SOCIAL— al elegirla.

La ficha de equipo ya lo hacía bien, que es por lo que el fallo se notó al comparar las dos.

## 228. El buscador pinta su rótulo y no acepta nada del navegador

**Decisión:** `SearchInput` pinta un `<label>` visible, como `Input` y `Select`, y lleva
`autoComplete="off"` con un `name` propio.

**Motivo:** solo mandaba `etiqueta` al `aria-label`, así que era el único control de la aplicación sin
rótulo a la vista. Medido: en la barra de cuatro filtros de Usuarios su base de línea quedaba en
**234 px** y la de los tres desplegables en **260 px** — **26 px** descuadrada, que es justo la altura de
un rótulo.

El `autoComplete="off"` va por otro motivo: los `type="search"` guardan lo escrito y el navegador lo
vuelve a poner al abrir la pantalla, de modo que la tabla aparece filtrada por algo que nadie escribió
en esa visita.

## 229. Buscar sin resultados ofrece quitar los filtros

**Decisión:** cuando hay filtros puestos y la lista sale vacía, el estado vacío ofrece un botón
«Quitar los filtros» que limpia los cuatro.

**Motivo:** buscar el correo de alguien que todavía no tiene cuenta es la razón más normal para buscar
y no encontrar, y ahí no había forma de volver: había que vaciar los cuatro controles a mano. El campo
tenía su aspa, pero descubrirla presupone que se sabe que está ahí.

## 230. El alta de usuario va en dos columnas y cada campo explica para qué sirve

**Decisión:** el diálogo de alta pasa de `sm` a `md` y reparte los campos en 2 + 1 + 3 columnas. Los
rótulos dicen «Correo institucional», «Teléfono o anexo» y «Cargo o puesto», y cada campo lleva debajo
qué se escribe ahí.

**Motivo:** «Correo» y «Cargo» no dicen qué se escribe en ellos: con uno se inicia sesión y con el otro
se busca a la persona cuando toca llamarla. Y con ocho campos en una sola columna el cuerpo se
desplazaba, con el último —la oficina— cortado detrás del pie de botones. Medido: el diálogo mide
**753 px** en una ventana de 1100 y **ya no se desplaza**.

## 231. La ubicación tiene el 30 % del ancho de la tabla

**Decisión:** las columnas de Usuarios declaran ancho (30/11/30/13/16) para que la ubicación no se
recorte.

**Motivo:** sin anchos la tabla reparte a partes iguales y la columna que lleva la oficina **y** la
pastilla de zona debajo se quedaba en «GERENCIA DE ADMINISTRACI…» y «SUB GERENCIA DE DESARROL…». En una
pantalla cuyo propósito es saber dónde está cada persona, esa es la columna que no puede recortarse.

Se declaran las cinco porque la tabla solo usa `<colgroup>` cuando **todas** lo hacen: una columna sin
ancho y la declaración entera se ignoran.

## 232. Las filas de tabla se abren con el teclado

**Decisión:** una fila pulsable recibe `tabIndex={0}` y abre con Enter o Espacio, con su contorno de
foco. Si el foco está en algo interactivo **dentro** de la fila —un enlace a la oficina, un enlace a la
zona, la casilla de seleccionar— la fila no actúa.

**Motivo:** era un `<tr>` con `onClick` y `cursor-pointer`: con el ratón abría y sin ratón no había
forma de llegar al detalle. Ese corte importa porque el evento sube: al pulsar Enter sobre el enlace a
la zona se habría navegado a la zona **y** abierto el detalle a la vez.

## 233. El perfil se lee por bloques, no como una lista de datos

**Decisión:** el perfil del usuario se ordena en cabecera (avatar, nombre, correo, rol como insignia,
estado), luego «Persona» en dos columnas con su rótulo, luego «Actividad» con los tickets y los
equipos a su cargo, y por último «Cuenta», en un recuadro aparte con las acciones.

**Motivo:** no es lo mismo lo que **es** de la persona —quién es y dónde está— que lo que tiene —sus
tickets, sus equipos— que lo que se le puede hacer. Antes eran seis `<p>` seguidos en el mismo peso,
con los «No indicado» pegados al dato, y no se distinguía lo que falta de lo que vale.

## 234. El perfil se dibuja en un componente, y el diálogo y la página usan el mismo

**Decisión:** `CuerpoPerfilUsuario` monta cabecera, datos, actividad y equipos. El diálogo de Usuarios
lo usa y le pasa las acciones por un hueco; la página de perfil completo lo reutiliza.

**Motivo:** eran dos montajes del mismo dato y se veían distinto. Un componente dibujado una vez se
compara consigo mismo.

## 235. Las tres cifras del perfil son la misma caja

**Decisión:** tickets, equipos y ayuda IA son «métricas» con el mismo cuerpo (24 px), la misma caja, el
mismo icono y `tabular-nums`, y una línea debajo que dice qué significa ese número.

**Motivo:** «0», «1 equipo» y «Activada» salían con tamaños distintos según cupiera, y el cero
—que es el dato más importante, que no hay nada pendiente— era el más pequeño de los tres. Sin
`tabular-nums` el 1 ocupa menos que el 8 y la fila se ve torcida.

## 236. La cabecera del perfil lleva el color de la zona

**Decisión:** una banda con degradado del color de la zona y el anillo del avatar con ese mismo color.
Sin zona, nada de color.

**Motivo:** es el código que ya usan `ZonaBadge` y `EnlaceOficina`. No se inventó un color para el
perfil: se pone el de la zona, que es el que ya identifica a la persona en toda la aplicación. Sin zona
no hay color que signifique nada, y se deja el fondo del diálogo en vez de poner uno decorativo.

## 237. La foto de perfil se valida por su contenido

**Decisión:** se acepta con `validar()` de los adjuntos —que mira los primeros bytes— y además se exige
que sea una imagen. Límite de 2 MB. Se guarda como archivo y el documento solo guarda el nombre.

**Motivo:** sin mirar el contenido, un PDF con extensión `.png` se guardaría y se serviría **desde el
mismo origen que la aplicación**. No hace falta hackear nada: basta con tener `usuarios.editar`.
Por eso se reutiliza la función de adjuntos en vez de escribir una comprobación nueva, y por eso hay
pruebas para el PDF disfrazado.

Tampoco va dentro del documento: pesa cientos de KB y el documento de usuario se lee en cada lista.

## 238. La foto no se pide con `src`, y su caché es del módulo

**Decisión:** la imagen se pide con `api.archivo` —igual que las descargas— y se pinta con
`URL.createObjectURL`, con el caché en el módulo y `olvidarFoto()` para invalidarlo.

**Motivo:** la ruta lleva la cabecera de autorización y un `src` no puede mandarla. Y el caché en el
módulo es lo que evita que la misma persona baje la foto una vez por cada sitio donde sale: diálogo,
fila de la tabla y perfil completo. El precio es tener que olvidarla a mano, y por eso hay un sitio
único que lo hace.

## 239. Cambiar la foto borra el archivo anterior

**Decisión:** al guardar, se borran los archivos de la cuenta que no sean el nuevo.

**Motivo:** el nombre del archivo lleva la extensión del formato. Subir un JPEG después de un PNG
dejaba los dos en disco, y el segundo ya no lo servía nadie.

## 240. Cambiar la foto pide el mismo permiso que cambiar sus datos

**Decisión:** la propia foto, siempre; la de otro, `usuarios.editar`. Y **ver** la foto de otro sigue
el límite de `GET /usuarios/{id}`: una cuenta normal solo ve la suya.

**Motivo:** si la foto fuera la puerta trasera, cualquiera con permiso de editar una cuenta dejaría un
archivo servido desde el servidor sin poder consultar siquiera el perfil.

## 241. El buscador no es `type="search"`

**Decisión:** `SearchInput` usa `type="text"` con `role="searchbox"`, `inputMode="search"`,
`autocomplete="off"` y un `name` único.

**Motivo:** medido. La aplicación no escribe nunca en el campo —abrir y cerrar cuatro perfiles no lo
movió— pero el navegador sí puede, y como el campo es controlado lo que aparezca se convierte en
filtro: reproducido con el setter nativo de `HTMLInputElement`, el campo se llenó solo y salió
`GET /usuarios?texto=…` con la lista a **0 de 267**. `type="search"` es exactamente el tipo de campo al
que se engancha esa memoria del navegador, y con `autocomplete="off"` no basta.

`role="searchbox"` mantiene lo único que se pierde al no ser un `type="search"`: el significado para
el lector de pantalla.

## 242. El filtro puesto se dice y se quita de un clic

**Decisión:** *retirado en la ronda BV.* La pastilla de filtro sustituyó a la que ahora pone
`SearchInput` («Sin buscar todavía · Buscar «…»»). Se queda el aviso del componente y se va esta.

**Motivo de retirarla:** duplicaba lo que el campo ya dice, y con el filtrado automático fuera —decisión
244— el caso para el que existía —«la lista está filtrada por algo que no escribí»— ya no puede darse
por el mismo camino.

## 243. Un solo rótulo por campo

**Decisión:** cuando `SearchInput` pasó a pintar su rótulo, se quitó el que tenía la pantalla de
Equipos encima.

**Motivo:** quedaron dos «Buscar equipos» apilados, y el de fuera apuntaba con `htmlFor` a un id
—«buscar-equipos»— que no existe, porque el real lo genera `useId`. Una etiqueta que no apunta a su
campo no es un adorno: es ruido para el lector de pantalla. Se quitó al cambiar el componente, no
después.

## 244. ~~El buscador no filtra mientras se escribe~~ — deshecho en la ronda BW

**Esta decisión estaba mal y se quitó.** Interpreté el encargo «no quiero que se filtre
automáticamente» como una queja del filtrado automático, cuando lo que molestaba era que el campo se
llenara solo. Filtrar al teclear es lo que se quiere.

Lo que sí se conserva de aquí: el `type="text"` con `role="searchbox"` y el `autocomplete="off"`.

## 245. El backend se reconstruye, no solo el frontend

**Decisión:** comprobar que un endpoint nuevo funciona incluye reconstruir la imagen del backend y
mandarle una petición **al contenedor**, no solo dar por bueno que las rutas estén registradas.

**Motivo:** la subida de foto estuvo dando 500 desde que se desplegó porque arreglé la anotación en el
fuente y **nunca reconstruí la imagen de la API** —solo la del frontend—, así que el contenedor
seguía con la versión anterior. En la ronda anterior comprobé que las tres rutas existían dentro del
contenedor y lo di por bueno: las rutas existían, pero el endpoint reventaba antes de llegar al
servicio. Contar rutas no es comprobar que funcionen; la prueba es mandarle una petición y mirar qué
contesta.

## 246. El buscador se filtra al escribir y el navegador no lo rellena

**Decisión:** vuelve el filtrado automático. Y el campo deja de dar pistas al autocompletado:
placeholder sin palabras de correo, `name` neutro, marcas para 1Password y LastPass, y al pulsarlo se
selecciona todo lo que haya.

**Motivo:** medido en el código, `setTexto` solo se llama al teclear y al quitar filtros —la aplicación
**nunca** escribe en ese campo por su cuenta—, así que el correo que aparecía lo ponía el navegador. Y
el motivo estaba en el propio campo: el placeholder era **«Nombre o correo…»**, y **«correo» es la
palabra con la que el navegador decide que un `type="text"` es un campo de dirección** y le ofrece
rellenarlo con una guardada. Con el filtro automático, ese texto se convertía en filtro y saltaba una
petición de inmediato.

La selección al pulsar va en `onClick`, no en `onFocus`: el clic coloca el cursor **después** de que el
campo reciba el foco. Con `onFocus` la selección se veía `[14,14]`, o sea el cursor al final y sin nada
seleccionado.

## 247. El buscador no existe hasta después del primer render

**Decisión:** `SearchInput` no pinta el `<input>` hasta que ha pasado un efecto. Además, al volver de
la caché de páginas (`pageshow`) vacía el campo con el **setter nativo** de `HTMLInputElement` si su
valor no coincide con el de la aplicación.

**Motivo:** el navegador guarda los valores del formulario y los reaplica al cargar, al ir «atrás» y
al reiniciar, y `autocomplete="off"` no lo para —ese atributo es del autocompletado de formularios, no
de la restauración de sesión—. Medido que la aplicación no guarda el término en ninguna parte, así que
el correo que reaparecía filtrando la lista venía de ahí, y con el filtrado automático saltaba una
petición al cargar la página.

Se tapa en dos sitios porque son dos momentos: **al cargar** se evita que haya dónde restaurar —si el
`<input>` todavía no existe, no hay nada que rellenar—, y **al volver de «atrás»** el campo ya existe
y hay que vaciarlo. El setter nativo es necesario porque al asignar `elemento.value` se pasa por el
rastreador de React, que cree que el valor no cambió.

Solo se toca cuando el valor **difiere del de la aplicación**, para que un filtro puesto a propósito se
respete y para que teclear no se entere.

**Lo que no se pudo comprobar:** el navegador de las pruebas no restaura valores de formulario, así que
el fallo original no se reproduce ahí. Lo que sí se comprueba es que ya no hay hueco por donde
restaurar, que es lo que lo hacía posible.

## 248. Elegir a una persona no relanza su propia búsqueda

**Decisión:** en el selector «A quién afecta» del registro manual, la consulta se apaga mientras haya
una persona elegida y la lista de sugerencias solo se pinta si la consulta está encendida.

**Motivo:** el manejador del botón escribía el nombre de la persona elegida en el campo de búsqueda, y
como el campo alimenta la consulta, elegir disparaba una búsqueda nueva. Medido: elegir a
«DEYSI LEYVA MINAYA» salía con `/api/usuarios/buscar?texto=DEYSI LEYVA MINAYA` y dejaba la lista
abierta mostrando solo a esa misma persona. A alguien que se busca por correo y no tiene cuenta, el
campo se quedaba con el correo y la lista filtrada por él.

La segunda mitad —no pintar la lista si la consulta está apagada— la encontró la prueba de proceso y no
la lectura del código: al vaciar el campo, la consulta se desactiva pero **React Query conserva el
último resultado**, así que la última persona encontrada se quedaba colgando bajo un campo vacío. Con
un filtro apagado no se pinta nada, aunque haya datos de antes.

El campo sigue mostrando el nombre de la persona elegida: eso es lo que confirma que está elegida, y
es lo que espera cualquiera que use un selector.

## 249. Un campo de búsqueda escrito a mano recibe la misma protección

**Decisión:** el `<input>` de «A quién afecta» lleva placeholder sin «correo», `name` neutro, marcas de
1Password y LastPass, selección al pulsar, y limpieza al montar y al volver de «atrás».

**Motivo:** es un `<input>` propio y no el `SearchInput` común, así que no heredaba nada de lo que se
corrigió en las rondas anteriores: seguía con «Escribe el nombre o el **correo**…», que es exactamente
la palabra que hace que el navegador ofrezca rellenarlo solo. Que un campo se escriba a mano no puede
significar que se quede fuera de las reglas.