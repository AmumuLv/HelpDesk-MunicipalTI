# Roles y protección de la cuenta principal

La primera cuenta creada en la instalación es el **administrador principal**.
Mantiene el rol operativo `administrador` y un indicador protegido; no es una
casilla delegable ni una opción que se pueda enviar desde un formulario.

| Operación | Administrador principal | Administrador | Técnico con `usuarios.editar` | Usuario |
| --- | --- | --- | --- | --- |
| Crear cuentas de usuarios | Sí | Sí | Sí | No |
| Crear técnicos | Sí | Sí | No | No |
| Crear o ascender a administrador | Sí | No | No | No |
| Editar o desactivar usuarios | Sí | Sí | Sí | No |
| Restablecer contraseñas de usuarios | Sí | Sí | Sí | No |
| Gestionar técnicos | Sí | Sí | No | No |
| Gestionar otros administradores secundarios | Sí | Sí | No | No |
| Asignar permisos a técnicos | Sí | Sí | No | No |
| Modificar la cuenta principal | Solo sus propios datos | No | No | No |

El titular conserva sus datos, foto y cambio de contraseña con la contraseña
actual. Nadie puede desactivarlo, degradar su rol ni quitar su protección desde
la web. Otros administradores no pueden sustituir su correo, contraseña o foto,
ni consultar o cerrar sus sesiones para tomar control de esa cuenta. El perfil
básico puede consultarse con los permisos habituales del directorio.

Las demás cuentas de administrador conservan configuración, permisos, tickets,
inventario, organización, reportes y gestión de cuentas. La excepción es crear
otros administradores o intervenir al principal. Pueden seguir gestionando entre
sí sus cuentas secundarias; el principal permanece disponible para recuperar la
administración. No se ha introducido la restricción anterior que reservaba toda
la asignación de permisos a una sola persona.

## Qué significa dar todos los permisos a un técnico

Los permisos adicionales amplían funciones, pero **no cambian el rol**. Con todas
las casillas activadas puede ejecutar las operaciones delegables de inventario,
tickets, organización o reportes. En cuentas solo gestiona usuarios: no puede
crear técnicos ni administradores, modificar otra cuenta técnica o administrativa,
restablecer sus contraseñas ni delegar permisos. Conserva su propio perfil y el
cambio de su contraseña mediante el flujo personal.

Al retirar `usuarios.editar`, las siguientes peticiones del técnico dejan de
autorizar la gestión de usuarios, aunque conserve su token de sesión. El servidor
lee el rol y los permisos vigentes desde MongoDB; no acepta autoridad enviada en
el cuerpo del formulario. Una matriz de permisos guardada por error en una cuenta
de usuario no le concede funciones de técnico.

Las cuentas se desactivan: esa acción no borra sus tickets ni los equipos que
tienen asignados. Los permisos destructivos sobre tickets o inventario siguen
siendo destructivos cuando se conceden a un técnico.

## Ubicación, altas y equipos de cuentas dadas de baja

- Editar el perfil propio no permite a un usuario o técnico cambiar su oficina o
  zona. La ubicación se administra con los permisos y límites de la jerarquía:
  un técnico autorizado gestiona usuarios, y un administrador gestiona técnicos.
  El administrador conserva la edición de su propia ubicación.
- Las cuentas se crean desde Usuarios. El registro manual de tickets selecciona
  una persona existente y no crea cuentas como efecto lateral, ni siquiera si la
  petición del ticket termina rechazada.
- No se asignan equipos nuevos a cuentas desactivadas o archivadas, tampoco por
  cambios masivos ni incorporando componentes a sus conjuntos. Los vínculos
  históricos se conservan y se pueden corregir otros datos del equipo, liberarlo
  o reasignarlo a una persona activa.
- En los cambios masivos solo se modifican los campos enviados. Cambiar el estado
  no elimina al responsable; dejarlo sin responsable requiere indicarlo expresamente.
  Se valida que la oficina exista antes de guardar: un destino inexistente no deja
  cambios parciales de estado o responsable.

Estas restricciones se comprueban en el servidor. Las regresiones de autorización,
asignación, conservación del historial y reactivación están en
`backend/tests/test_regresiones_permisos_asignacion.py`.

El perfil del técnico permite guardar sus datos de contacto, incluso sin el permiso
para administrar usuarios. En su propia ficha, Zona y Oficina quedan bloqueadas
y no se envían al guardar. Un técnico autorizado conserva esos controles al
gestionar a un usuario. Lo comprueba `frontend/pruebas/perfil-ubicacion-segura.spec.ts`.

Importar equipos no concede permiso para crear personas: la opción heredada de
crear perfiles faltantes exige también `usuarios.editar`, antes de reservar o
modificar el lote. La importación normal sigue disponible con `equipos.importar`.
Los perfiles creados desde el Excel no incluyen correo ni contraseña. Los casos
de autorización están en `backend/tests/test_importacion_permiso_perfiles.py`.

## Instalaciones existentes y límites

La migración `027_administrador_principal` protege al administrador activo más
antiguo por fecha de creación y, en empate, por identificador. No cambia el rol ni
los permisos de los demás. En una instalación vacía el asistente inicial crea la
cuenta protegida. Un índice parcial único impide tener dos cuentas principales.

No existe un botón web para transferir la titularidad. Si se pierde el acceso,
la recuperación necesita intervención autorizada desde el servidor; otro
administrador secundario no puede restablecer la contraseña del principal.

**Proteger una cuenta no protege todos los registros frente a un administrador.**
Los administradores mantienen sus permisos de eliminación de tickets, equipos y
otros registros operativos. Para impedir esas acciones habría que restringirlos,
lo cual está fuera de esta política que conserva sus facultades. Los controles
de la web tampoco sustituyen la seguridad del equipo que ejecuta Docker o de
quien tiene acceso directo a MongoDB.

## Verificación

### Cruces entre cuentas y sesiones

El 06/11/2026 aprobaron 60 casos del servidor y tres recorridos combinados de
navegador con datos ficticios. Se usan sesiones del principal, administrador
secundario, técnico y usuario; en el recorrido de atención se mantienen tres
vistas abiertas para comprobar las actualizaciones sin recargar. También aprobaron 13 pruebas de herramientas
y la comprobación de 158 llamadas frontend frente a las 151 rutas del OpenAPI.

Las nuevas secuencias se conservan en `backend/tests/test_flujos_combinados_roles.py`
y `frontend/pruebas/flujos-combinados-roles.spec.ts`. Cubren:

- Conceder, retirar y devolver permisos mientras se utiliza el mismo token,
  incluido un formulario de alta abierto y operaciones sobre equipos y tickets.
- Bajar a un técnico a usuario: pierde los accesos de TI aunque conserve la
  sesión y una matriz de permisos antigua.
- Desactivar, archivar, sustituir y reactivar a un trabajador: se conservan sus
  identificadores y tickets; el reemplazo tiene identidad y reportes distintos.
- Reasignar un equipo o conjunto de A a B, liberarlo y asignarlo a C: solo queda
  abierto el último periodo. Repetir la asignación o liberación no duplica tramos.
- Editar el asunto, agregar una nota interna y conversar simultáneamente: se
  conservan los cambios y la nota privada no aparece para el usuario.
- Rechazar la intervención sobre el principal mientras este edita sus datos.
- Asignar, cerrar, notificar y reabrir un mismo ticket entre tres vistas abiertas.
- Ascender a un usuario mientras un técnico lo edita: sus controles se retiran,
  el siguiente intento se rechaza y el administrador secundario mantiene su gestión.

La suite existente añade disputas por asignación y cierre, envíos repetidos,
versiones antiguas y accesos a registros ajenos. Los permisos de una petición
nueva se evalúan con los datos vigentes; estas pruebas no exigen cancelar una
operación que ya estuviera autorizada y en curso. Los antecedentes del patrimonio
siguen disponibles para TI según sus permisos, sin cambiar quién reportó el caso.

La prueba de liberación reprodujo un defecto antes de la corrección: el periodo
del responsable anterior quedaba abierto. Ahora se cierra también al dejar el
equipo sin responsable y el nuevo periodo empieza en ese mismo instante. Se
conservan el formato del historial y la identidad de los tickets; esta corrección
no reescribe historiales antiguos ni modifica registros reales durante las pruebas.

El workflow de GitHub ejecuta la suite backend y los tres cruces de navegador en
servicios aislados en cada push o pull request. Estos resultados no sustituyen
una prueba en el servidor definitivo ni garantizan todas las combinaciones posibles.

### Rondas anteriores

En una revisión posterior del 05/11/2026 se comprobaron 100 casos distintos dirigidos
del backend, 4 casos del preparador HTTPS y 154 casos distintos del navegador.
La primera ejecución de navegador dejó 152 aprobados y detectó el selector Estado
sin opciones y un cierre prematuro de la prueba de reactivación. Tras corregirlos,
aprobaron los 14 casos repetidos de cuentas, jerarquía e inventario anual. La
comparación anual se pudo repetir sobre la misma base ficticia sin contaminación.
Los recuentos son consolidados: las repeticiones no se suman como pruebas nuevas.
Pasaron también lint, compilación, comprobaciones HTTPS locales y la verificación
de imágenes y archivos del backend tras aplicar las correcciones a Docker.

El 05/11/2026 se cerró la verificación de las correcciones de oficina, altas
indirectas y responsables archivados: 414 casos distintos del backend y 151
del navegador aprobados, usando datos ficticios. El resultado del servidor se
consolidó entre ejecuciones: 173 casos en un grupo completo, 228 terminados antes
de una interrupción, 8 casos de fotos repetidos al retomar y 5 nuevos de importación.
Los 8 se repitieron completos; no se contaron dos veces los que ya habían pasado.
También se repitieron los otros 8 casos existentes de importación y 4 recorridos
de cuentas en navegador tras los últimos ajustes. No se suman otra vez al total.
Pasaron la compilación de producción, la revisión de los archivos frontend
modificados y la comprobación de imágenes y salud tras actualizar Docker local.
No equivale a comprobar todas las combinaciones posibles ni al despliegue público.

La suite `backend/tests/test_jerarquia_cuentas.py` comprueba las llamadas reales
a la API: técnico con todas las casillas, límites entre roles, retirada de
permisos, intentos de falsificar el indicador y el rol, cuenta principal,
arranque simultáneo, unicidad y migración. También reproduce un cambio de rol
entre la autorización y la escritura: editar correo o restablecer contraseña se
rechaza si la cuenta fue promovida durante esa operación.

`frontend/pruebas/jerarquia-cuentas.spec.ts` recorre las interfaces de principal,
administrador normal y técnico con permisos, incluido un restablecimiento de
contraseña de usuario desde el navegador. Todos esos ensayos usan datos ficticios
en servicios aislados.

El 30/10/2026 aprobaron 55 casos del servidor de jerarquía, permisos, perfiles,
fotos y gobernanza, y los tres recorridos en Chromium. Los 14 casos de jerarquía
se repitieron después de separar el contexto de autorización de cuentas del
contexto de auditoría habitual; están incluidos en los 55 y no se suman dos veces.
También aprobaron la comprobación de tipos, lint de los archivos modificados y
la compilación de producción dentro de Docker. No es una certificación de
ausencia universal de errores ni del futuro despliegue en Internet.


## Baja y archivo de trabajadores

Crear una cuenta distinta para cada persona; no reutilizar la identidad del trabajador anterior.
Al desactivar, se registra la fecha de baja y se revocan sus sesiones. Tras 30 días completos,
el worker archiva la cuenta automáticamente (comprueba al iniciar y cada hora).
En Usuarios, el filtro Estado permite consultar Activos, Desactivados, Archivados o Todos.
Los archivados conservan su ficha, tickets y referencias de inventario; no se borran ni se
transfieren automáticamente sus equipos. La reasignación se realiza desde inventario.
Reactivar la cuenta limpia las fechas de baja/archivo y requiere un nuevo inicio de sesión.
Para bajas antiguas sin fecha conocida, los 30 días empiezan en la primera comprobación.
La cuenta principal está excluida. Los permisos para reactivar son los mismos que para
administrar la cuenta. La retención general de auditoría sigue su política independiente.

La ficha completa distingue Activa, Desactivada y Archivada y muestra las fechas
de baja y archivo cuando existen. Reactivar está disponible según la jerarquía,
con confirmación; durante el guardado se bloquean los envíos repetidos. Al quitar
los filtros del directorio también se restablece Estado a Activos.

La guía de la IA describe esta jerarquía y el archivo. Sus consultas de directorio
solo incluyen personas activas; un resultado vacío no implica que el historial se
haya eliminado. Para revisar las bajas orienta al filtro Estado de Usuarios.
