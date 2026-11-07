# Guía de uso y verificación de usabilidad

Revisión: 06/11/2026. Esta guía explica las convenciones de la web y cómo comprobar
que una tarea se entiende. No acredita conformidad completa con una norma de
accesibilidad ni reemplaza la evaluación con trabajadores reales.

## Convenciones de la interfaz

| Elemento | Uso |
| --- | --- |
| Azul | Navegación y acciones habituales. |
| Dorado | Énfasis y determinadas acciones destacadas; no indica permiso adicional. |
| Rojo | Peligro, eliminación, baja o un error que debe revisarse. |
| Verde | Confirmación o resultado positivo. |
| Botón deshabilitado | Falta un dato, hay una operación en curso o la acción no está disponible. Revisa su mensaje asociado. |
| Selector de tema | Cambia entre apariencia clara y oscura. |
| Campana | Notificaciones de la cuenta; cada aviso puede llevar al caso relacionado. |

El texto, el icono y el estado deben explicar la acción; no se debe depender solo
del color. Los nombres largos pueden abreviarse en una tabla: abre la ficha o el
detalle para revisarlos completos.

En el panel TI, la barra lateral puede mostrarse expandida, contraída u oculta;
utiliza su control para recuperarla. Los grupos despliegan sus apartados. En
pantallas pequeñas la navegación es un menú que se abre y cierra. Un enlace
ausente puede responder a permisos, no a una pérdida de datos.

## Formularios, filtros y confirmaciones

Completa los campos obligatorios y revisa el mensaje junto al campo si no se
puede guardar. Usa la búsqueda para encontrar una persona real y selecciónala:
un texto escrito no siempre representa una selección confirmada. Para volver
atrás sin guardar utiliza **Cancelar** cuando el formulario lo ofrece.

Los filtros limitan el resultado. Ante una lista vacía revisa primero estado,
zona, oficina, búsqueda y página. En **Usuarios**, **Archivados** es un filtro
distinto de **Activos**. En informes revisa las fechas de origen y destino y el
contenido que anuncia el formato antes de descargarlo.

En acciones destructivas comprueba el nombre, el alcance y la confirmación. Por
ejemplo, eliminar una versión anual no elimina el inventario operativo, mientras
que eliminar un bien o ticket tiene un alcance diferente. No pulses repetidamente
si aparece un indicador de guardado.

## Teclado y pantallas

1. Usa **Tab** y **Mayús + Tab** para recorrer controles. El foco debe verse y
   seguir un orden que permita completar la tarea.
2. Usa **Entrar** o **Espacio** según el control para activarlo; utiliza las
   flechas en selectores cuando corresponda.
3. Abre un diálogo, revisa que tenga título y un control para cerrarlo, y comprueba
   que puedas volver a la tarea sin perder el contexto.
4. Prueba el tema claro y oscuro y amplía el navegador. Los textos, estados y
   acciones importantes deben seguir legibles.
5. En móvil comprueba que el menú, los campos, los botones y el envío del reporte
   se puedan utilizar sin depender de pasar el mouse.

Estas comprobaciones describen criterios de aceptación. La cobertura automática
se consulta en las suites del proyecto; no implica que todos los dispositivos,
lectores de pantalla o configuraciones hayan sido evaluados.

## Tareas para validar con una persona nueva

| Persona | Tarea | Resultado esperado |
| --- | --- | --- |
| Trabajador sin conocimientos técnicos | Reportar un problema propio | Lo envía sin elegir códigos ni equipos de inventario. |
| Trabajador | Reportar por un compañero | Identifica al compañero sin ver un selector de sus bienes. |
| Trabajador | Avisar de una impresora compartida | Elige oficina y tipo Impresora, o No lo sé, sin distinguir una unidad exacta. |
| Técnico | Identificar y cerrar un caso | Corrige el destino real, conserva al reportante y deja el resultado de atención. |
| Técnico | Trabajar con un permiso retirado | No puede completar la siguiente operación protegida aunque mantenga el formulario abierto. |
| Administrador | Dar de baja y reemplazar a un trabajador | Conserva la identidad anterior, crea la nueva y reasigna bienes sin mezclar autorías. |
| Administrador | Archivar un Excel anual y compararlo | Reconoce que ese archivo no modifica el inventario operativo. |
| Principal | Crear un administrador secundario | Lo hace con una cuenta independiente y conserva su protección. |

En cada ejercicio registra si la persona terminó sin ayuda, dónde se detuvo y
qué interpretación tuvo de los controles. Antes de añadir texto explicativo,
revisa si el nombre del campo, el orden de opciones o la agrupación pueden
eliminar la confusión. Un problema que requiere explicación repetida debe
registrarse como una mejora de interacción.

## Conexión, permisos y privacidad

Las actualizaciones entre cuentas dependen de la conexión. Si falla un envío,
consulta primero si el registro ya existe antes de repetirlo. Si terminó la
sesión, vuelve a iniciar sesión; si cambió un permiso, pide al administrador que
revise la autorización, no utilices otra cuenta.

Comparte capturas de un error solo con quien atiende el caso y oculta información
personal innecesaria. No incluyas contraseñas en los ejercicios. Consulta el
[manual del usuario](USUARIO.md), el [del técnico](TECNICO.md) o el
[del administrador](ADMINISTRADOR.md) según la tarea.
