# Pruebas del relevo de inventario y de la IA

Fecha: 07/11/2026. Base de los cambios: `38ab3c2`.

## Alcance y aislamiento

Se comprueban la importación de un inventario actualizado, el cambio de
responsable, la aplicación de sugerencias de IA y las operaciones cruzadas
entre usuario, técnico, administrador y administrador principal.

Las escrituras de datos del sistema usan exclusivamente el proyecto Docker
`helpdesk-verificacion`, sus volúmenes propios y datos ficticios. La API del
navegador escucha en `127.0.0.1:18100`. Las pruebas del servidor usan otra base
y otro índice de Redis dentro de esa instalación aislada.

No se llama a Groq ni a Gemini. Las pruebas no consumen consultas del chatbot
ni modifican registros de la instalación de trabajo.

## Resultados

La tanda final del servidor aprobó **47 casos distintos en 480,75 segundos**
con la imagen de pruebas reconstruida. Los **cinco recorridos Chromium**
aprobaron en 2,7 minutos contra la API aislada actualizada.

| Comprobación | Resultado |
| --- | --- |
| Importación, relevo y permiso de creación de perfiles | 22 casos aprobados |
| Aplicación de sugerencias de IA y sus permisos | 11 casos aprobados |
| Operaciones cruzadas de los cuatro roles | 7 casos aprobados |
| Reglas de la plantilla, incluido el simulador corregido | 7 casos aprobados |
| Recorridos reales del navegador | 5 aprobados |
| Herramientas de traslado, publicación y contratos de rutas | 13 casos aprobados |
| Lint de la interfaz | Aprobado, sin advertencias |
| Compilación completa en Linux con Node 22 | Aprobada; TypeScript y Vite, 3248 módulos |
| Textos de IA y comprobaciones de estilos | 4 textos y 41/41 comprobaciones aprobados; 128 archivos sin conflictos |
| Documentación y Word | 16 guías y 51 enlaces locales correctos; Word sincronizado e íntegro |

Las guías y el generador también se verificaron con finales de línea de
Windows y de Linux en copias temporales. El Word contiene 16 capítulos y
30 tablas; se comprobó la integridad de sus XML y la ausencia de macros u
objetos incrustados, sin revisión de su paginación visual.

No aparecieron fallos funcionales en estos casos. Al terminar se retiraron
los contenedores, la red y los volúmenes propios de `helpdesk-verificacion`.
Las repeticiones de una misma prueba no se suman como casos adicionales.
Después de retirarlos, la instalación de trabajo conservó sus servicios
saludables; la API confirmó MongoDB y Redis disponibles y la web respondió
con HTTP 200.

## Comportamientos comprobados

### Inventario actualizado y cambio de trabajador

- Reconocimiento del equipo por código patrimonial o MAC, conservando su ID.
- Cambio de responsable sin renombrar la cuenta anterior ni trasladar sus tickets.
- Creación autorizada de un solo perfil por persona dentro del lote, sin
  contraseña ni acceso de inicio de sesión automático.
- Conservación del historial de responsables de cada componente de la PC.
- Reimportación y cambio de orden de las filas sin crear equipos duplicados.
- Rechazo de coincidencias ambiguas, códigos contradictorios y nombres que no
  permiten confirmar que se trata del mismo equipo.
- Distinción entre componentes de una PC, laptops y dispositivos independientes.
- Control del permiso adicional para crear perfiles durante la importación.

### Sugerencias de IA y roles

- Un técnico sin permiso para reasignar no puede usar la IA para eludirlo.
- Un usuario no puede aplicar asignaciones de TI.
- Una asignación válida sigue el servicio normal de tickets y genera su evento
  y aviso correspondientes.
- Se rechazan nombres enviados como identificadores, destinos ajenos a TI,
  cuentas inactivas y tickets eliminados.
- Una ausencia requiere la confirmación normal de asignación.
- Un paquete inválido no deja modificaciones parciales de categoría o prioridad.
- Se comprueban retirada y devolución de permisos con la misma sesión,
  protección del administrador principal y separación de mensajes y notas.

### Botones y recorridos del navegador

Los recorridos comprueban carga del Excel, previsualización del responsable
anterior y nuevo, casilla de creación de perfiles y confirmación; aplicación
de una sugerencia de técnico; cierre y reapertura de tickets; cambios de
permisos con una ventana abierta y actualización entre sesiones.

Las escrituras de esos recorridos van a la API real de pruebas. En el caso de
IA se controla la sugerencia de lectura para que el resultado sea repetible;
la autorización y la aplicación se ejecutan contra el servidor real.

## Corrección realizada durante la revisión

La ejecución anterior de GitHub detectó un simulador de base de datos
desactualizado en `backend/tests/test_plantilla_reglas.py`. No admitía las
consultas nuevas de identificación de equipos. Se actualizó únicamente ese
simulador para representar un cursor asíncrono y las colecciones consultadas;
se conservó la comprobación real de las reglas de importación.

Sus siete casos aprobaron tanto en ejecución directa como dentro de la
tanda final de pytest. No se cambió la lógica de producción para acomodarla
a una prueba.

## Comprobaciones de construcción y seguridad

Se reconstruyó la imagen de pruebas a partir del Dockerfile actual: la imagen
local anterior era del 27/10/2026. Una primera tanda de 40 casos ya aprobó con
el código actual montado en aquella imagen; sus casos se repitieron con la imagen
actualizada y no se suman dos veces. La antigua imagen de pruebas tampoco
incluía las evidencias de Expat que exige el verificador nativo actual; no
se usó ese resultado para evaluar la imagen de producción.

El verificador nativo de la imagen de producción aprobó los hashes y las
bibliotecas cargadas, la regresión de Expat, XML/DTD, zlib, PDF, Excel y ffprobe.
Esto comprueba integridad y regresiones concretas de los parches; no sustituye
un análisis actualizado de vulnerabilidades de todas las imágenes.

En Windows, TypeScript aprobó, pero esbuild encontró acceso denegado al borrar
un archivo temporal en dos intentos, incluso con una carpeta temporal
independiente. La compilación completa en Linux con Node 22 aprobó en
138,5 segundos, ejecutando realmente el comando sin reutilizar su resultado
de caché. La construcción y exportación de la imagen temporal finalizaron
con código 0; se retiró únicamente su etiqueta de prueba. No se desactivaron
controles de seguridad ni se cambió código para resolver el bloqueo de Windows.

## Cómo repetir las pruebas

Desde la raíz del proyecto:

```powershell
$env:COMPOSE_PROJECT_NAME = 'helpdesk-verificacion'
docker compose -f compose.pruebas.yml build tests
docker compose -f compose.pruebas.yml run --rm tests python -m pytest tests/test_importacion_relevo.py tests/test_importacion_excel.py tests/test_importacion_y_perfiles.py tests/test_importacion_permiso_perfiles.py tests/test_ia_aplicar_permisos.py tests/test_flujos_combinados_roles.py tests/test_plantilla_reglas.py -ra --tb=short --show-capture=no -p no:cacheprovider
docker compose -f compose.pruebas.yml --profile navegador up -d --wait --wait-timeout 120 api
```

En otra terminal, dentro de `frontend`:

```powershell
$env:COMPOSE_PROJECT_NAME = 'helpdesk-verificacion'
$env:PRUEBA_API_URL = 'http://127.0.0.1:18100'
$env:PRUEBA_NAVEGADORES = 'chromium'
npx playwright test pruebas/flujos-combinados-roles.spec.ts pruebas/ia-aplicar-sugerencia.spec.ts pruebas/importacion-relevo.spec.ts --reporter=list
```

Las pruebas necesitan las dependencias de desarrollo y Chromium instalados.
Después de terminar y comprobar que el nombre del proyecto es
`helpdesk-verificacion`, retirar únicamente ese entorno ficticio:

```powershell
docker compose -f compose.pruebas.yml --profile '*' down --volumes --remove-orphans
```

## Límites de esta revisión

Los resultados describen los casos ejecutados; no prueban que sea imposible
encontrar otros errores. No incluyen consultas a proveedores generativos,
carga prolongada ni el servidor, dominio o HTTPS definitivos.

Se mantienen los límites documentados de la importación parcial, de deshacer
lotes que actualizan equipos existentes y de la trazabilidad heredada indicada
como `DAT-002` en [Registro de cambios](REGISTRO_DE_CAMBIOS.md).
