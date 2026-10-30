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
