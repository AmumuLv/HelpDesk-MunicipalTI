# Manual del administrador

Revisión: 06/11/2026. El administrador conserva la gestión de tickets, inventario,
organización, equipo TI, reportes, conocimiento y configuración. Solo el
administrador principal puede crear o promover otros administradores; los demás
no pueden intervenir la cuenta principal.

## Preparar la operación

1. Revisa **Zonas y oficinas** y registra la estructura real de la institución.
2. En **Usuarios**, crea o completa los perfiles de trabajadores y técnicos,
   asignando su oficina y datos correctos.
3. En **Equipo TI**, revisa horarios, disponibilidad y ausencias.
4. En **Configuración**, revisa institución, ayudas automáticas, SLA y horarios,
   notificaciones y permisos por persona.
5. Registra o importa los equipos y verifica sus responsables antes de habilitar
   el trabajo diario.

El primer arranque de una instalación vacía se realiza con el asistente inicial
de la web; la primera cuenta queda protegida como principal. No hace falta volver
a crear esa cuenta en instalaciones que ya están inicializadas.

## Administrar cuentas

1. Abre **Usuarios**, utiliza los filtros de rol, zona, oficina y estado.
2. Pulsa **Nuevo usuario** para registrar una persona nueva o abre su ficha para
   corregir sus datos. Verifica el correo y el rol antes de guardar.
3. Para una baja, utiliza **Desactivar cuenta** y confirma la persona elegida.
4. Para devolver el acceso, filtra por **Desactivados** o **Archivados**, abre la
   ficha y pulsa **Reactivar cuenta**.
5. Restablece una contraseña solo tras verificar la identidad del solicitante y
   entrega la nueva contraseña por el canal institucional autorizado.

Desactivar impide usar la cuenta y conserva sus tickets, equipos e historial.
Tras al menos treinta días de baja, el proceso programado la marca como archivada;
no es una eliminación de sus datos. El tiempo efectivo depende de que el worker
esté funcionando. **Usuarios → Estado de las cuentas → Archivados** permite
localizar esas personas. Una reactivación conserva su identidad y requiere que
vuelva a iniciar sesión.

No cambies el nombre de una cuenta anterior para dársela a otro trabajador. Crea
un perfil nuevo y reasigna los equipos; los reportes anteriores siguen vinculados
al identificador anterior. Tampoco se asignan nuevos equipos a una cuenta de baja.
Un perfil importado sin correo ni contraseña no es todavía una cuenta de acceso.

Los administradores secundarios pueden gestionar otras cuentas secundarias dentro
de la política actual; la protección del principal no impide que un administrador
elimine registros operativos para los que conserva permiso.

## Delegar permisos a técnicos

1. Abre **Configuración → Permisos por rol**.
2. Busca al técnico por su nombre.
3. Marca únicamente las funciones necesarias y guarda los cambios de esa persona.
4. Comprueba con la cuenta del técnico el acceso que se acaba de conceder o retirar.

El rol no cambia al activar permisos adicionales. Un técnico autorizado para
usuarios solo administra cuentas con rol usuario; nunca puede convertirlas en
administradores. No se debe conceder eliminación de tickets o equipos por
comodidad: esas acciones siguen siendo destructivas.

Los permisos vigentes se verifican en el servidor. Al retirarlos, las siguientes
peticiones dejan de autorizarse incluso si el técnico conserva una sesión o un
formulario abierto. La interfaz se actualiza con la sincronización disponible;
una operación ya autorizada y en curso no equivale a una petición nueva.

## Inventario y relevo de trabajadores

En **Equipos → Inventario** registra bienes individuales y PC de escritorio
correctamente identificados. Usa el código patrimonial o los identificadores
físicos fiables del bien; el nombre del responsable no es la identidad del equipo.
En una oficina, un bien compartido no debe asignarse por conveniencia al empleado
que lo reportó.

Antes de aplicar un nuevo archivo en **Equipos → Importar**, revisa altas,
actualizaciones, coincidencias y responsables. La información dudosa debe
corregirse o resolverse en la previsualización antes de confirmar. No cambies
códigos patrimoniales ni números de serie solo porque cambió el trabajador.
La operación de relevo debe conservar el identificador del equipo y registrar el
cambio de responsable, sin trasladar la autoría de los tickets anteriores.

Consulta la [plantilla oficial](../PLANTILLA_INVENTARIO.md) y el comportamiento
del lote mostrado por la aplicación. No supongas que una coincidencia de nombres
demuestra que dos filas representan el mismo equipo.
El [procedimiento de relevo e importación](../RELEVO_E_IMPORTACION.md) detalla cómo
revisar un Excel actualizado sin reutilizar la identidad del trabajador anterior.

En **Inventario anual**, registra cada revisión con su año, consulta las versiones
y utiliza **Comparar años**. Esa copia histórica no reemplaza el inventario
operativo. **Eliminar versión** borra únicamente la versión anual elegida, no los
bienes operativos; la confirmación advierte que no se puede deshacer.

## Supervisar el servicio

Revisa abiertos y asignaciones para distribuir la atención. El cierre requiere
un resultado; los filtros de **Cerrados** permiten recuperar esos casos. Las
fichas de persona, oficina y patrimonio ofrecen los antecedentes relacionados.
Un reporte de oficina sigue teniendo un reportante; ese dato no lo convierte en
un problema personal de quien pulsó enviar.

En **Reportes**, selecciona el informe, los filtros y el formato disponibles;
revisa el periodo antes de descargar. Los informes de inventario describen bienes
y los informes de tickets describen incidencias: no sumes ambas cantidades como
si midieran lo mismo. En **Análisis IA** valida el universo y el periodo de cada
indicador. **Auditoría** permite revisar las operaciones registradas; no sustituye
una copia de seguridad ni impide por sí sola una acción autorizada.

La configuración de ayudas automáticas gobierna recomendaciones y aprendizaje
según lo implementado. Las claves de proveedores se administran en el servidor,
no se introducen en una conversación. Los archivos y fotos ocupan el
[almacenamiento del servidor](../ALMACENAMIENTO.md).

## Cierre de jornada y cambios

Registra las incidencias pendientes, verifica que no se dejó una importación a
medias y cierra tu sesión en equipos compartidos. Antes de un cambio de permisos,
SLA o datos masivos identifica el motivo, el responsable y la comprobación
posterior. Una actualización del software debe seguir el procedimiento de gestión
de cambios y validarse primero con datos ficticios.

Consulta los límites completos en [ROLES_Y_PERMISOS.md](../ROLES_Y_PERMISOS.md)
y la operación diaria en el [manual del técnico](TECNICO.md).
Antes de habilitar acceso público, completa las comprobaciones de
[Ciberseguridad](../CIBERSEGURIDAD.md) con el responsable del servidor.
