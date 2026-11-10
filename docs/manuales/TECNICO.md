# Manual del técnico TI

Revisión: 06/11/2026. El menú y las acciones disponibles dependen de los permisos
que un administrador te haya concedido. Tener todas las casillas activadas no
convierte tu cuenta en administradora.

## Iniciar la jornada

1. En el acceso selecciona **Equipo TI** e inicia sesión con tu cuenta personal.
2. Consulta **Resumen**, **Tickets → Abiertos** y **Mis asignaciones**.
3. Revisa la campana de notificaciones y tu disponibilidad en **Equipo TI**.
4. Abre tu perfil para revisar contacto, horario y foto cuando corresponda.

Los estados de disponibilidad y las ausencias permiten organizar la atención;
no son una ficha de asistencia con firma. No se debe prometer ese registro como
una función existente. El cambio de foto está integrado en el perfil de TI.
Puedes cambiar tu contraseña desde el flujo personal con la contraseña actual.
La oficina o zona propia se administran con los permisos de gestión de cuentas.

## Atender un reporte del portal

1. Abre el ticket y revisa **Reportó**, el destinatario, la oficina, la descripción
   y la conversación. Quien envía un reporte puede ser distinto de quien necesita
   ayuda; un reporte compartido afecta a la oficina.
2. En **Gestionar ticket**, utiliza **Asignar a** y **Asignar** cuando corresponda.
   Asignarte un caso o reasignarlo a otro técnico está sujeto a los controles del
   servidor; no debe hacerse desde una cuenta ajena.
3. Identifica el equipo real. En **Incidencia reportada → Editar**, revisa título,
   categoría y el destino de inventario. Distingue equipos personales de equipos
   compartidos y guarda la corrección antes del cierre.
4. Conversa con el reportante para aclarar el síntoma. Usa **Notas internas** para
   información de TI que no deba aparecer en la conversación del usuario.
5. Actualiza el avance cuando cambie la situación. Utiliza **En espera** cuando
   proceda y revisa el SLA como referencia del plazo de atención.
6. Pulsa **Cerrar ticket**, escribe el **Resultado de la atención** y confirma.
   El registro queda **cerrado**; no existe un paso operativo separado de
   «resuelto» que debas buscar.

Reabrir, eliminar o reasignar casos depende de tus permisos. Un intento rechazado
no se resuelve repitiendo la petición ni cambiando de URL: solicita autorización
al administrador. Si otra persona editó el ticket y aparece un conflicto, revisa
los datos actuales antes de guardar de nuevo.

## Registrar un caso directamente desde TI

1. Abre el registro de nuevo ticket del panel.
2. Busca y selecciona a una persona existente; no basta con escribir un nombre.
3. Indica asunto, descripción, categoría y prioridad.
4. Selecciona el destino real disponible para esa persona o su oficina. No se
   registran equipos genéricos inventados para completar el formulario.
5. Asigna un técnico si corresponde y confirma el registro.

Un caso registrado como detectado por TI tiene origen técnico y no abre la misma
conversación con el usuario que un reporte enviado desde el portal. Revisa el
origen antes de buscar el chat. Crear un ticket no crea una cuenta de usuario;
las altas se realizan desde **Usuarios** con autorización.

## Identificar equipos y consultar antecedentes

Un **conjunto** es una PC de escritorio: CPU, monitor, mouse y teclado. Una laptop
es un equipo individual, igual que una impresora u otro dispositivo independiente.
Un usuario puede tener una PC y además varios equipos individuales.

Para un problema de programas, correo o sistemas selecciona la computadora
afectada que ofrezca el selector; no atribuyas una falla de software a un mouse o
monitor. Un formateo puede corresponder a una CPU o a una laptop. El nombre del
programa complementa la categoría y el vínculo al inventario; no crea un bien.

Al elegir la PC completa, la columna **Equipo** muestra su nombre, por ejemplo
**Computadora N°2**, y **PC de escritorio**. Al elegir un componente muestra el
equipo individual y conserva su relación con la PC. Revisa el mismo vínculo
después de guardar y en el historial de cerrados.

Desde la ficha del equipo o conjunto consulta sus antecedentes. Desde
**Usuarios → ficha de la persona** o **Zonas y oficinas → ficha de la oficina**
consulta los tickets relacionados, con los filtros de estado y equipo disponibles.
Los casos abiertos y cerrados se distinguen por su estado; comprueba los filtros
antes de concluir que faltan registros.

## Inventario, calidad e importación

Con los permisos habilitados puedes registrar o editar bienes reales, revisar
los campos que faltan en **Equipos → Calidad** y usar operaciones masivas. Un
porcentaje de datos faltantes de **0 %** indica que no faltan los datos evaluados
en ese indicador; no acredita por sí solo una inspección física del bien.

En **Equipos → Importar**, descarga la plantilla oficial, carga el archivo,
revisa la previsualización y aplica solo el lote validado. Revisa especialmente
los equipos que se actualizarán y los responsables pendientes. Importar requiere
`equipos.importar`; crear perfiles faltantes exige además `usuarios.editar`.
La plantilla está explicada en [PLANTILLA_INVENTARIO.md](../PLANTILLA_INVENTARIO.md).
Para cambios de trabajador utiliza el [procedimiento de relevo e importación](../RELEVO_E_IMPORTACION.md):
revisa la identidad del bien y el responsable anterior antes de confirmar.

**Inventario anual** es un archivo histórico independiente del inventario
operativo. Registra el año y el archivo, consulta sus versiones y compara dos
años. Guardar allí el Excel no actualiza los equipos de trabajo. El acceso exige
`equipos.campanas`; eliminar una versión anual está reservado al administrador.

## Usuarios, conocimiento y consultas

Con `usuarios.editar` puedes crear, editar, desactivar y restablecer contraseñas
de **usuarios**. No puedes crear técnicos o administradores, gestionar esas
cuentas ni delegar permisos. Un trabajador que reemplaza a otro necesita una
identidad propia; conserva el perfil anterior y reasigna los bienes, sin cambiar
su nombre por el del reemplazo.

La **Base de conocimiento** reúne instrucciones reutilizables; editarla depende
del permiso concedido. **Análisis IA**, las consultas de datos y **Reportes**
ayudan a revisar la operación según tus accesos. El chatbot es un apoyo de
consulta: valida los datos, el periodo y el diagnóstico antes de actuar. No pegues
credenciales ni consideres una respuesta de IA una autorización para cambiar algo.

La referencia de límites está en [ROLES_Y_PERMISOS.md](../ROLES_Y_PERMISOS.md).
Las precauciones operativas están en [Ciberseguridad](../CIBERSEGURIDAD.md).
