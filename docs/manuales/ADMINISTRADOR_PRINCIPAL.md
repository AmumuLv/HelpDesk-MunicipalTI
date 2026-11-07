# Manual del administrador principal

Revisión: 06/11/2026. «Superadministrador» se utiliza aquí como nombre explicativo
de la cuenta principal. El sistema tiene tres roles operativos: **usuario**,
**técnico** y **administrador**. El principal mantiene el rol administrador con
una protección especial; no existe un cuarto rol delegable llamado superadmin.

## Cómo se obtiene la protección

En una instalación vacía, la primera cuenta del asistente inicial es el
administrador principal. En una instalación anterior, la migración correspondiente
protege al administrador activo más antiguo por fecha de creación y, en empate,
por identificador. Un índice único evita dos titulares principales.

El formulario de usuarios no permite asignar esa protección ni transferirla.
No debes crear una cuenta nueva suponiendo que por su nombre será la principal.
Consulta [ROLES_Y_PERMISOS.md](../ROLES_Y_PERMISOS.md) para el criterio exacto.

## Facultades y límites

| Acción | Comportamiento |
| --- | --- |
| Operar la Mesa de Ayuda | Conserva las funciones normales de administrador. |
| Crear o promover administradores | Solo la cuenta principal puede hacerlo. |
| Gestionar técnicos y usuarios | Disponible dentro de los controles habituales. |
| Delegar permisos a técnicos | También lo hacen los demás administradores; la titularidad no absorbe esa función. |
| Editar sus datos y foto | Disponible mediante el flujo propio. |
| Cambiar su contraseña | Requiere la contraseña actual en el flujo personal. |
| Desactivarlo o bajar su rol desde la web | No está permitido, ni desde otro administrador ni desde su propia cuenta. |
| Restablecer su contraseña desde otro administrador | No está permitido. |
| Transferir la titularidad mediante un botón | No existe esa función. |

La protección también impide a otros administradores cambiar el correo o la foto
del titular o tomar control cerrando sus sesiones. El perfil básico puede seguir
consultándose con los permisos del directorio.

## Crear un administrador de forma controlada

1. Verifica que la persona necesita autoridad administrativa y autorización
   institucional, no solo un permiso técnico concreto.
2. Inicia sesión con la cuenta principal y abre **Usuarios**.
3. Crea la cuenta con rol **Administrador** o edita el rol de una persona
   existente si realmente corresponde un ascenso de esa misma persona.
4. Revisa nombre, correo y rol antes de confirmar.
5. Comprueba el acceso con la cuenta nueva y registra quién autorizó el cambio.

Cada administrador utiliza su propia cuenta. No compartas la contraseña principal
como forma de permitir una tarea ocasional. Un técnico puede recibir funciones
adicionales sin convertirse en administrador.

## Custodia y recuperación

Conserva el acceso al correo y los medios de recuperación institucionales que se
acuerden para esta cuenta. Revisa sus sesiones, usa una contraseña exclusiva y
cierra sesión cuando termines. No la incluyas en manuales, Excel, respaldos del
código ni consultas a las IA.

Si se pierde el acceso, otro administrador secundario no puede restablecer esta
contraseña. La recuperación necesita intervención autorizada del responsable del
servidor y debe documentarse como un cambio excepcional. Este manual no propone
editar MongoDB directamente como procedimiento de operación cotidiana.

## Lo que esta protección no resuelve

La cuenta principal evita perder el control administrativo por las acciones de
otra cuenta web. No protege automáticamente cada ticket, archivo o equipo frente
a un administrador que conserva permisos de eliminación. Tampoco bloquea a quien
tiene control del sistema operativo, Docker o acceso directo a la base de datos.

Por ello necesita responsables definidos para el servidor, actualizaciones,
copias y restauración, auditoría y protección de credenciales. Conserva la
separación entre una cuenta dada de baja y el perfil de su reemplazo. Los
[procedimientos del administrador](ADMINISTRADOR.md) también se aplican al titular.
