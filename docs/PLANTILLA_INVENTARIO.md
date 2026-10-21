# Plantilla de inventario

Usa `plantilla-inventario.xlsx` de esta carpeta o descarga la plantilla desde Importar inventario. No se necesita un archivo diferente para el inventario anual.

## Estructura

- Un archivo por año. El año se selecciona al registrar el Inventario Anual.
- Una hoja por zona, con su nombre real: PALACIO, COMPLEJO, etc. No crees una hoja por oficina.
- Una fila por dispositivo físico. No combines celdas ni agregues subtotales entre equipos.
- La columna AREA es la oficina. Repite el área y el conjunto en cada fila; también se admite heredarlos de la fila anterior dentro de la misma oficina.
- Las hojas Instrucciones y Detalle avanzado no representan zonas. El detalle avanzado es opcional para la importación operativa.

## Columnas

| Columna | Qué registrar |
|---|---|
| AREA | Oficina a la que pertenece el dispositivo. |
| Tipo de equipo | Identificador del conjunto o equipo: COMPUTADORA N°01, COMPUTADORA N°02, LAPTOP N°01, IMPRESORA N°01. |
| Dispositivo | CPU, Monitor, Teclado, Mouse, Laptop o Impresora. MAUSE se normaliza a Mouse. |
| Código patrimonial | Código individual, único, como texto para conservar ceros iniciales. Nunca copies el del CPU al mouse o monitor. |
| Marca / Modelo | Datos propios del dispositivo de esa fila. |
| Tamaño Pantalla | Para monitores o laptops, si corresponde. |
| Nombre Equipo | Nombre del equipo en la red; para dispositivos sin nombre puede quedar vacío. |
| Procesador / Memoria RAM / Almacenamiento | Para CPU y laptops; no corresponden a teclados o mouse. |
| Direccion IP | IPv4 de cuatro números entre 0 y 255. En impresoras por USB se acepta CABLE USB. |
| Direccion MAC | 12 caracteres hexadecimales: E0:B8:9E:3F:90:EE. También acepta guiones, sin separadores o formato e0b8.9e3f.90ee. |
| Propiedad | MUNICIPALIDAD o PERSONAL. |
| Estado | Estado real del dispositivo, conforme al catálogo del sistema, por ejemplo OPERATIVO. |
| Responsable | Nombre completo de la persona. Vacío significa uso común de la oficina, no una cuenta nueva con el nombre de la oficina. |

## Conjuntos y equipos sin patrimonio

Una computadora normalmente ocupa cuatro filas: CPU, Monitor, Teclado y Mouse, todas con el mismo AREA y Tipo de equipo. COMPUTADORA N°01 puede existir en oficinas diferentes. En una misma oficina, usa otro número para otra computadora.

| AREA | Tipo de equipo | Dispositivo | Propiedad | Responsable |
|---|---|---|---|---|
| SOPORTE | COMPUTADORA N°01 | CPU | MUNICIPALIDAD | Persona asignada |
| SOPORTE | COMPUTADORA N°01 | Monitor | MUNICIPALIDAD | Persona asignada |
| SOPORTE | COMPUTADORA N°01 | Teclado | MUNICIPALIDAD | Persona asignada |
| SOPORTE | COMPUTADORA N°01 | Mouse | MUNICIPALIDAD | Persona asignada |
| SOPORTE | COMPUTADORA N°02 | Mouse | MUNICIPALIDAD | Otra persona |

Los dos mouse se distinguen por el conjunto aunque no tengan patrimonio. Dos dispositivos idénticos sin patrimonio dentro del mismo conjunto necesitan un nombre que los distinga. No inventes códigos patrimoniales para identificarlos.

Los equipos PERSONAL no requieren patrimonio: el sistema lo excluye aunque el archivo incluya uno. Un equipo municipal sin código puede registrarse, pero su patrimonio queda pendiente de revisar.

## IP, MAC y datos desconocidos

No repitas IP o MAC entre dispositivos distintos del archivo. No copies la red del CPU a sus periféricos. La importación operativa revisa también los equipos activos existentes y permite reimportar el mismo equipo sin considerarlo otro. La regla actual de IP es global: no distingue subredes independientes.

CABLE USB no se considera una IP repetida. No inventes una MAC para una impresora conectada solo por USB.

Vacío significa dato pendiente. No aplica significa que el dato no corresponde al dispositivo. En la importación operativa revisa y confirma las sugerencias de No aplica; en equipos personales el patrimonio se excluye automáticamente.

## Antes de importar

1. Revisa nombres de oficinas, conjuntos y dispositivos.
2. Guarda patrimonios como texto y comprueba que no se repitan.
3. Verifica IP y MAC directamente en el dispositivo. No cambies una O por un 0 sin comprobarlo.
4. Deja Responsable vacío solo si el equipo es de uso común de la oficina.
5. En Inventario Anual corrige los errores de red y los duplicados antes de registrar; el mensaje indica hoja y fila. No se guarda una versión parcial.
6. En importación operativa revisa la vista previa: las filas con conflictos de IP/MAC se omiten; las demás pueden registrarse. Corrige y vuelve a importar las omitidas.

Inventario Anual guarda una versión histórica: no modifica el inventario operativo. Las comparaciones sin patrimonio dependen de ubicación, conjunto, tipo y nombre; cambiar estos identificadores puede aparecer como una baja y un alta.
