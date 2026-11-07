# Cambiar al trabajador sin duplicar sus equipos

El trabajador y el equipo tienen identidades distintas. Cuando otra persona recibe
una PC o una laptop, se cambia el responsable del equipo existente; no se cambia
el nombre de la cuenta anterior para convertirla en la cuenta del reemplazo.

## Qué hace la importación

| Dato del nuevo Excel | Resultado |
| --- | --- |
| Código patrimonial que identifica un solo equipo | Actualiza ese mismo equipo, aunque cambie el orden de las filas. |
| MAC única, sin patrimonio o con patrimonio compatible | Reconoce el equipo por su MAC. |
| Sin patrimonio ni MAC | Usa un nombre estable y la ubicación, conjunto y tipo, siempre que exista una coincidencia única. |
| Varios equipos posibles, patrimonio repetido o código y MAC contradictorios | Marca la fila para revisión y la omite. No elige el primer equipo encontrado. |
| Equipo realmente nuevo y distinguible | Propone crear un equipo. |
| Responsable nuevo, con creación de perfiles autorizada | Crea un único perfil por persona y oficina y le asigna las filas correspondientes. |

El código patrimonial pertenece a cada componente físico. No copies el código del
CPU al monitor, teclado o mouse. La MAC se usa solo cuando corresponde al equipo;
no inventes una MAC para distinguir un periférico. El importador actual no tiene
un campo de número de serie mapeado: esa columna no sustituye al patrimonio o a
la MAC en este flujo.

## Pasos para el administrador o técnico autorizado

1. Parte del inventario actualizado y conserva las columnas de la
   [plantilla oficial](PLANTILLA_INVENTARIO.md).
2. Conserva el patrimonio, la MAC y los nombres que identifican al mismo equipo.
   Cambia el responsable por el nombre completo del trabajador que lo recibe.
   Incluye todos los componentes de la PC cuando se entrega el conjunto completo.
3. Abre **Equipos → Importar**, carga el Excel y revisa la previsualización.
4. Comprueba **Se actualizará** y el cambio **persona anterior → persona nueva**.
   Una entrega de equipos existentes no debería convertirse en varias altas.
5. Si la persona todavía no está registrada, activa **Crear los perfiles que
   faltan y asignarles sus equipos**. Requiere permiso para importar y también
   `usuarios.editar`. Está desactivado inicialmente.
6. Corrige o excluye las filas con error y aplica la importación. Revisa el
   resultado: equipos creados, actualizados, omitidos y perfiles creados.
7. En **Usuarios**, abre el perfil nuevo y configura su acceso si necesita entrar.
   El Excel no crea correo, contraseña ni privilegios administrativos.
8. Desactiva la cuenta anterior si la persona ya salió. Tras treinta días de
   baja, el worker la archiva conservando referencias e historial.

Si no activas la creación de perfiles, el nombre nuevo puede quedar pendiente de
vincular. Usa el bloque de **personas del Excel** del resultado para seleccionar
una cuenta existente o crear su perfil. Los nombres parecidos y los homónimos
necesitan revisión humana; no se fusionan cuentas automáticamente.

Si regresa la misma persona que estaba archivada, revisa y reactiva su perfil
antes de importar. La baja de una cuenta no demuestra que haya llegado otra
persona, y el nombre por sí solo no permite distinguir homónimos con certeza.

## Qué se conserva

- El identificador interno del equipo y su clave de identidad, incluso al cambiar
  el responsable o reordenar el Excel.
- Los tickets conservan al reportante y afectado originales. El reemplazo no
  hereda la identidad, sesiones ni credenciales del trabajador anterior.
- El historial del equipo registra los cambios de responsable con sus periodos.
- Si todos los componentes activos de un conjunto tienen el mismo responsable,
  la PC se vincula también a esa persona. Un relevo parcial no fuerza el cambio
  de los componentes que siguen asignados a otra persona.
- Volver a importar el mismo archivo no crea otro perfil por cada componente.

El historial patrimonial puede incluir incidencias anteriores del equipo para
que TI conozca sus antecedentes. Eso no cambia quién reportó cada incidencia.

## Límites que deben revisarse antes de aplicar

**Importar reescribe los datos de las filas válidas.** Mantén actualizado el Excel:
una marca, modelo o dato técnico antiguo puede sustituir una corrección reciente
hecha en la web. El patrimonio y la MAC ya reconocidos se conservan cuando se
omiten en la fila; para corregirlos o retirarlos expresamente, revisa la ficha.

La importación permite resultados parciales: una fila fallida no revierte las
otras. No se presenta como una transacción atómica. El resultado informa las
filas omitidas y los errores. Un lote que actualizó equipos existentes **no tiene
Deshacer automático**, porque no conserva una instantánea anterior recuperable.

Un periférico sin identificador, con un nombre cambiado y situado junto a varios
iguales no se puede reconocer con certeza. Añade su identificación real o corrige
el vínculo desde la ficha; no inventes códigos para obligar a que coincida.

Un patrimonio o MAC que aparece por primera vez tampoco demuestra que deba
reemplazar a un equipo antiguo sin código. Si la fila tiene un nombre distinto,
queda para revisión aunque solo haya un equipo del mismo tipo en esa oficina.
Completar un identificador pendiente sí está permitido cuando coincide el nombre
estable y único del equipo existente. Un equipo reconocido por un patrimonio o
MAC ya registrado puede cambiar de nombre sin perder su identidad.

**Inventario anual** conserva y compara instantáneas. Cargar allí un archivo no
traspasa automáticamente los equipos ni sustituye esta importación operativa.

## Verificación conservada en el proyecto

`backend/tests/test_importacion_relevo.py` comprueba el relevo de una PC con cuatro
componentes, creación de un único perfil, conservación de tickets e identificadores,
reimportación, reordenamiento con altas nuevas, reconocimiento por MAC, nombres
estables y rechazo de identidades ambiguas sin crear perfiles como efecto lateral.

Los límites de autorización se comprueban también en
`backend/tests/test_importacion_permiso_perfiles.py`. Los resultados de la última
ejecución deben consultarse en la entrega; la existencia del archivo de pruebas
no significa por sí sola que se hayan ejecutado.
