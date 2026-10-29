# Instalar en otro equipo desde el repositorio privado

GitHub contiene el código y la configuración de ejemplo. Los usuarios, tickets,
inventarios, fotos y adjuntos se guardan en Docker y **no se sincronizan con Git**.
Dos instalaciones independientes no compartirán cambios automáticamente: para
trabajar simultáneamente con los mismos datos hay que acceder a un único servidor.

## Equipo nuevo, sin trasladar datos

Requisitos: Git y Docker con Compose. En Windows, iniciar Docker Desktop;
el arranque usa PowerShell incluido en Windows. En Linux/macOS, instalar además
Python 3.10 o superior. La cuenta de GitHub debe tener acceso al repositorio privado.

```bash
git clone https://github.com/AmumuLv/HelpDesk-MunicipalTI.git
cd HelpDesk-MunicipalTI
```

En Windows ejecuta `iniciar.cmd` (también puedes abrirlo con doble clic).
En Linux/macOS ejecuta `python3 tools/trasladar.py iniciar`.

El comando crea `.env` si falta, genera un `SECRET_KEY` aleatorio, compila las
imágenes e inicia los servicios. El primer arranque puede tardar varios minutos
mientras compila y carga las firmas del antivirus. Si `.env` ya existe, lo conserva. Abre
`http://localhost`; también puedes entrar por `http://localhost:8080`.
La primera instalación permite crear el administrador desde la web. No hay
cuentas de demostración precargadas en producción.

Configura `GROQ_API_KEY` en el `.env` **del servidor** si quieres activar el chatbot.
El resto del sistema puede iniciar sin esa clave. Después de cambiar el entorno:

```bash
docker compose up -d api worker
```

Si un puerto está ocupado, configura `WEB_PORT` o `API_PORT` en `.env`.
Los puertos 80 y 443 del proxy se ajustan en `docker-compose.yml` si otro servicio los ocupa.
Los navegadores de otros equipos necesitan la dirección del servidor y, para
funciones como el micrófono, HTTPS fuera de localhost.

Si Docker Desktop no puede descargar dependencias de npm y muestra `ETIMEDOUT`,
comprueba su conexión de red. En una instalación con red host habilitada puedes
configurar `BUILD_NETWORK=host` en `.env` y volver a iniciar. Esto solo cambia la
red utilizada al compilar las imágenes, no los puertos de la aplicación.

## Llevar los datos actuales a otro equipo

En el equipo de origen:

```bash
python3 tools/trasladar.py respaldar backups/municipalidad.helpdesk.zip
```

En Windows utiliza en PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/trasladar.ps1 respaldar backups/municipalidad.helpdesk.zip
```

La opción de ejecución se aplica solo a ese proceso, para ejecutar el script local
incluido en el repositorio; no cambia la política global de Windows.

El comando pausa API y worker durante la copia y vuelve a iniciarlos. Guarda la
base MongoDB y los adjuntos, con un manifiesto de integridad SHA-256. No incluye
`.env`, claves de API, caché Redis ni informes exportados que puedan regenerarse.
El ZIP contiene información privada y hashes de contraseñas: llévalo por un medio
privado, fuera de GitHub. `backups/` y `*.helpdesk.zip` están excluidos de Git.

En el equipo nuevo:

1. Clona el repositorio y ejecuta `iniciar.cmd` en Windows o `python3 tools/trasladar.py iniciar` en Linux/macOS.
2. **No crees el administrador ni importes datos todavía.**
3. Copia el ZIP por separado al equipo nuevo.
4. Si utilizas licencias cifradas, conserva el mismo `LICENSE_ENCRYPTION_KEY` en el
   `.env` nuevo. Configura las claves del chatbot por separado; nunca en Git.
5. Ejecuta:

```bash
python3 tools/trasladar.py restaurar backups/municipalidad.helpdesk.zip
```

En Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/trasladar.ps1 restaurar backups/municipalidad.helpdesk.zip
```

La herramienta comprueba los hashes, exige escribir `RESTAURAR` y rechaza una
instalación que ya contenga datos operativos. Se pausa la aplicación durante la
restauración y se recuperan los permisos de los adjuntos. Inicia sesión con las
cuentas restauradas; las sesiones y avisos temporales de Redis no se trasladan.

La herramienta admite el MongoDB incluido en Compose y adjuntos dentro de
`/data/`. Para bases de datos externas se debe utilizar el respaldo propio del
servidor. No uses `docker compose down -v` en producción: elimina los volúmenes.

## Actualizar el código

```bash
git pull --ff-only
```

Después ejecuta `iniciar.cmd` en Windows o `python3 tools/trasladar.py iniciar`
en Linux/macOS.

Haz un respaldo antes de actualizar una instalación con datos. El código aplica
las migraciones pendientes al arrancar y conserva los volúmenes existentes.

## Comprobar el proyecto sin tocar producción

```bash
docker compose -f compose.pruebas.yml run --build --rm tests
docker compose -f compose.pruebas.yml down -v
```

Estos servicios tienen proyecto, red, bases y almacenamiento temporales propios;
no utilizan el `.env` operativo ni las claves de proveedores.

Para las pruebas con navegador y API real:

```bash
docker compose -f compose.pruebas.yml --profile navegador up -d --build --wait api
cd frontend
npm ci
npx playwright install chromium
```

En PowerShell configura `$env:PRUEBA_API_URL='http://127.0.0.1:18100'`; en Linux/macOS
usa `export PRUEBA_API_URL=http://127.0.0.1:18100`. Ejecuta después las suites
de navegador, excluyendo el registro inicial que necesita una base vacía:

```bash
npx playwright test --grep-invert 'primera laptop:|completa y guarda con ubicación existente'
```

Las pruebas de campañas verifican ahora el archivo anual actual. El recorrido
comprueba usuarios, técnicos y administradores, incluidos móvil, tableta y
escritorio. Las respuestas de proveedores externos se simulan; no consume sus
cuotas. Para repetir toda la revisión, elimina primero la instalación de pruebas
con el comando siguiente y vuelve a iniciarla: algunas pruebas crean versiones
anuales con años y nombres fijos.

El registro inicial se comprueba aparte. Con la API de demostración detenida
(`docker compose -f compose.pruebas.yml stop api`), inicia otra API sobre una
base de pruebas nueva:

```bash
docker compose -f compose.pruebas.yml run -d --rm --service-ports --name helpdesk-registro-inicial -e MONGO_DB=helpdesk_test_registro api uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Desde `frontend`, conservando `PRUEBA_API_URL`, ejecuta
`npx playwright test pruebas/registro-inicial.spec.ts`. Al terminar, detén ese
contenedor con `docker stop helpdesk-registro-inicial`.

Al terminar, desde la raíz:
`docker compose -f compose.pruebas.yml --profile navegador --profile suite down -v`.
Ese comando solo elimina los servicios efímeros del archivo de pruebas.

## Publicación y secretos

Para Internet se preparó `compose.publico.yml`. Configura `PUBLIC_DOMAIN` en
`.env` con un dominio propio, sin protocolo ni rutas, y dirige su DNS al servidor.
El dominio debe ser accesible en los puertos 80 y 443 para emitir el certificado:

```bash
docker compose -f docker-compose.yml -f compose.publico.yml up -d --build --wait
```

Ese modo habilita cookies Secure, permite CORS únicamente desde el dominio y
retira los puertos directos de MongoDB, API y frontend. El acceso pasa por Caddy.
En el modo local, los puertos de herramientas de API y frontend escuchan solo
en 127.0.0.1; para entrar desde otro equipo se utiliza el proxy, no el puerto 8080.
No actives el modo público sobre HTTP: el navegador no enviaría las cookies Secure.
Antes de abrirlo, verifica el certificado real del dominio y la conexión desde
la red donde se usará. Las pruebas locales con CA propia no certifican ese dominio.

La documentación interactiva y el esquema OpenAPI están desactivados en
producción; se conservan en desarrollo y en la API de pruebas. El chat autentica
el socket en su primer mensaje, sin incluir el token en la URL, y revalida la
sesión y el acceso antes de enviar eventos. La CSP permite scripts propios y
mantiene imágenes, audio y temas; los logs del proxy retiran parámetros de token.

La revisión actual de los 61 paquetes Python de ejecución no encontró
avisos conocidos; la auditoría npm tampoco presentó avisos pendientes.
Los resultados funcionales y sus límites están en la verificación del
24/10/2026 al final de esta guía. No constituyen una certificación de seguridad
de una instalación remota.

Los ensayos se repiten con:

```bash
docker compose build --pull api worker web proxy mongo clamav
docker compose -f compose.pruebas.yml --profile seguridad up -d --wait api-seguridad web-seguridad proxy-seguridad
python tools/verificar_publicacion.py --ejecutar
python tools/auditar_dependencias.py
```

El perfil seguridad usa datos ficticios y una CA efímera dentro de sus
contenedores. No instala certificados de confianza en Windows. El navegador de
la sonda fija la clave pública del certificado previamente validado por Python.
ClamAV se inicia con Docker Compose y `CLAMAV_ENABLED=true` activa el análisis
de adjuntos y fotos. Si no puede comprobar un archivo, la subida se rechaza
con un error temporal; no se guarda sin revisar. Las firmas se conservan en
el volumen `clamav-data` y el servicio las actualiza. El antivirus complementa
los controles de formato, tamaño y permisos; no garantiza detectar todo malware.


### Auditoría de las imágenes Docker

La revisión de Python y JavaScript no incluye todas las bibliotecas del sistema
operativo ni las que vienen incorporadas en otras herramientas. También se
comprobó este nivel con Docker Scout. Las imágenes reconstruidas de web y proxy
no presentaron avisos altos o críticos en el escaneo realizado; Redis actualizado
tampoco. Esto no significa que todos los servicios estén libres de vulnerabilidades.

La imagen del backend mantiene siete avisos altos en bibliotecas Debian
(`cjson`, `libxml2`, `zlib` y `harfbuzz`) que el escáner señala sin versión
corregida para esa distribución. La imagen MongoDB reconstruida con utilidades
y lector YAML actualizados no presenta alertas altas ni críticas en el escaneo
actual. ClamAV conserva dos altas en libxml2 y libcurl; la actualización eliminó
la alerta crítica de Brotli. Estos nueve avisos altos siguen pendientes: el
análisis de archivos y el aislamiento de redes no sustituyen sus parches.
MongoDB y Redis no tienen puertos expuestos en la configuración de publicación.

Se actualizó Nginx a 1.30.6 y se retiraron curl y módulos dinámicos que esta web
no utiliza. El proxy compila Caddy 2.11.7 con Go 1.26.9 y x/net 0.60.0 sobre un
runtime Alpine mínimo. El backend de producción conserva el usuario sin
privilegios y no incorpora pip ni sus dependencias de instalación en ejecución.
Las imágenes de desarrollo sí mantienen pip para ejecutar las pruebas.

Para repetir el análisis de imágenes locales, sin guardar informes:

```bash
python tools/auditar_imagenes.py mesa-ayuda-api mesa-ayuda-web mesa-ayuda-proxy redis:7-alpine mesa-ayuda-mongo mesa-ayuda-clamav
```

El comando fija el identificador de cada imagen al empezar y termina con error
si encuentra avisos altos/críticos o no consigue verificar una imagen. Ejecuta
un único escaneo a la vez para evitar bloquear la caché de Docker Scout.

El repositorio es independiente del Escritorio. Antes de cada publicación:

```bash
python tools/revisar_publicacion.py
git status
```

La comprobación busca credenciales conocidas y valores privados del entorno local
en los archivos publicables, sin imprimir sus valores. No sustituye la revisión
de cambios. Las comprobaciones automatizadas de GitHub no necesitan secretos de
la municipalidad. Configura una rama protegida cuando el repositorio esté creado
si quieres exigir sus comprobaciones antes de fusionar cambios.


## Verificacion del 24/10/2026

Se recorrieron los 140 casos de navegador, repartiendo el primer registro en una
base vacía y los demás flujos en la demo aislada. Se comprobaron altas,
ediciones, borrados, permisos, tickets, fotos, chat, inventario anual, descargas,
sincronización y accesibilidad de los tres roles en tres tamaños de pantalla.
La suite del servidor aprobó 352 de 353 casos y 22 subpruebas; el caso de límite
de login heredaba contadores de otros casos. Se aisló su IP y se corrigieron
las conexiones Redis de las pruebas antes de repetirlo: las 24 verificaciones
de seguridad y reportes pasaron. También pasaron 26 comprobaciones de archivos
y antivirus y 30 de IA local; estos grupos se solapan con la suite principal.
La colección actual contiene 367 casos: los 14 añadidos y el caso corregido
quedaron cubiertos en esas repeticiones específicas. No se repitió toda la
suite tras corregir el aislamiento del caso de login.

Con la imagen nueva de MongoDB, 500 lecturas a concurrencias 5/15/30 y 100 altas
simultáneas no devolvieron errores. A concurrencia 30, el p95 de tickets fue
4,08 segundos en este equipo; esto no garantiza esa capacidad en otro servidor.
Pasaron el reinicio de servicios y la restauración en otra base y volumen,
comparando foto, adjunto, login e idempotencia. El respaldo fue exclusivamente
ficticio y temporal. Las pruebas no modifican los registros de producción.

La imagen MongoDB 8.0.34 conserva el servidor oficial y recompila sus ocho
utilidades y gosu con Go 1.26.9, actualiza x/net a 0.60.0 y el lector YAML a
3.15.2 con suma verificada. La imagen final contiene solamente ese sistema
actualizado; Docker Scout no detectó alertas altas ni críticas en ella.
El backend sigue teniendo siete alertas altas en bibliotecas de Debian sin
versión corregida disponible en esos repositorios; ClamAV conserva dos altas
en libxml2 y libcurl. Sus actualizaciones requieren nueva validación.
Son riesgos pendientes; las medidas de aislamiento no equivalen a un parche.

MongoDB y Redis comparten una red interna exclusiva con la API y el worker.
El antivirus tiene su propia red, sin acceso directo a la base de datos.
MongoDB no publica puertos al equipo anfitrión. Para consultar la base local:
`docker compose exec mongo mongosh`. La web accede mediante su red interna.

API y worker funcionan sin capacidades adicionales y con temporales sin permiso
de ejecución. Los PDF no acceden a recursos HTTP ni a archivos por URL.
La configuración para publicar con dominio y HTTPS sigue en
`compose.publico.yml`; debe aplicarse con un dominio real antes de exponer el
servidor en Internet. Las comprobaciones TLS utilizaron una CA local de prueba.
El linter conserva 16 avisos existentes; TypeScript y lint no devolvieron errores.

## Verificación del 24–25/10/2026: cierre funcional y operación local

Las siguientes comprobaciones se realizaron en `helpdesk-verificacion`, con
cuentas, archivos y bases ficticias. La instalación operativa conserva sus
registros. No se crearon respaldos de datos reales.

### Funciones, permisos e IA integrada

- Backend: corrida completa de **367 casos**, con **366 aprobados, un fallo y
  22 subpruebas aprobadas**. El fallo fue el tiempo límite de diez segundos de
  `ffprobe` al comprobar un WAV válido, durante la ejecución de otras tareas.
  El mismo caso pasó al repetirlo aislado. Se corrigió la clasificación del
  error: un tiempo de espera devuelve **503 `audio_no_disponible`**, no una
  acusación de archivo inválido. No se guarda contenido sin comprobarlo.
- Después de esa corrección pasaron los **cuatro casos de audio**: límites,
  formatos reales, error temporal y reintento sin adjuntos duplicados. Incluyen
  dos regresiones nuevas; la colección actual tiene **369 casos**. No se
  repitió toda la colección después del ajuste: la evidencia final combina
  la corrida completa y las repeticiones dirigidas.
- Chromium: **142 casos distintos cubiertos**. Pasaron tres de instalación
  inicial y 137 de la corrida principal de 139. Sus dos fallos correspondían
  a una respuesta interceptada que se cerraba antes de leerse y a una prueba
  que todavía esperaba dividir equipos cada 16 dispositivos. Se ajustaron las
  pruebas y ambas pasaron al repetirlas, manteniendo las comprobaciones de
  permisos y de totalidad de los equipos.
- Firefox y WebKit: **16 ejecuciones dirigidas aprobadas**, ocho por motor:
  permisos, agrupación por persona, perfiles importados, reintentos, pérdida
  de red, sincronización entre cuentas, HTML como texto y tickets sobre laptop.
  No equivalen a pruebas en un teléfono físico o Safari de un Mac real.
- Pasaron los nueve recorridos completos de accesibilidad de los tres roles
  en celular, tableta y escritorio. También se comprobaron reportes, cuentas,
  edición, borrado, conocimiento, horarios, ausencias, inventario anual,
  valoraciones, sesiones y ayudas internas.
- La IA local se comprobó dentro de la suite: clasificación, fechas,
  consultas autorizadas, fuentes y tratamiento de información insuficiente.
  Esto no certifica la precisión predictiva sobre incidencias reales;
  requiere evaluación con historial etiquetado separado del entrenamiento.

Lint terminó sin errores y con 16 advertencias existentes. Pasaron 41 casos de
estilos, ocho pruebas de herramientas y la comprobación de textos de IA.
Se verificaron 159 llamadas frente a 151 rutas, sin rutas inexistentes, y la
revisión de 408 archivos no encontró problemas de publicación. Las auditorías
de Python (61 paquetes verificados) y npm no detectaron avisos conocidos en
los resultados consultados. La compilación Docker fue correcta.

### Proveedor real y seguridad

Groq rechazó el acceso del usuario común y respondió la orientación técnica
(2.849 tokens informados). La segunda pregunta, sobre el total del inventario
ficticio, alcanzó un límite externo después de solicitar una lectura. La sonda
se detuvo: no se completaron el contraste de la cifra ni las peticiones reales
de borrado y secretos. No se repitieron llamadas para agotar más cuota. Los
ensayos del proveedor usaron datos ficticios; no la base institucional.

ClamAV real aceptó contenido inocuo y rechazó el patrón de prueba EICAR,
en memoria y sin guardar archivos. La configuración sigue rechazando fotos y
adjuntos si no puede comprobarlos. Los servicios de datos no publican puertos.

El escaneo de la API reconstruida tras el ajuste de audio y de ClamAV, repetido
el 25/10, mantiene **ocho hallazgos altos por imagen**:

| Imagen | Hallazgos altos | Paquetes afectados |
| --- | ---: | --- |
| API | 6 | libxml2, cjson y zlib de Debian |
| ClamAV | 2 | libxml2 y libcurl de Alpine |

API y worker compartían las mismas capas de archivos en la comprobación; el
worker hereda esos riesgos del backend. No deben sumarse como vulnerabilidades
distintas. Tampoco son ocho CVE únicos: existe un aviso compartido entre
distribuciones. En el escaneo anterior de esta batería, web, proxy, Redis y
MongoDB no presentaron avisos altos o críticos. No se certifica ausencia de
vulnerabilidades ni se consideran corregidos los ocho hallazgos pendientes.

La sonda HTTPS aislada aprobó cadena y nombre de certificado mediante una CA
de laboratorio, cookies Secure/HttpOnly, CSRF obligatorio, rechazo de CORS
ajeno, CSP, cierre HTTP/WebSocket y ausencia de tokens en el log del proxy.
Tres pantallas funcionaron con HTTPS sin violaciones CSP y conservaron el tema.
No se instalaron certificados de confianza en Windows. La instalación normal
permanece en HTTP local: el titular confirmó que aún no tiene dominio ni
servidor definitivo.

### Recuperación y carga

Con **5.032 equipos ficticios**, pasaron 100 altas simultáneas sin códigos
duplicados y 500 lecturas con concurrencias 5/15/30, sin errores HTTP. Se
generaron PDF de tickets y Excel de inventario completo. Tras reiniciar
MongoDB, Redis y API ficticios se conservaron registros, sesión nueva e
idempotencia. La restauración en otra base y volumen mantuvo idénticos el
adjunto y la foto por sus hashes, además del acceso y el ticket.

El respaldo contenía exclusivamente datos ficticios y se eliminó al terminar.
Es una restauración en el mismo equipo, no un traslado físico a otro dispositivo.
Las primeras mediciones coincidieron parcialmente con auditorías; las cifras
de rendimiento finales deben distinguirse de esa carga adicional.

El ensayo sostenido terminó a los **30,02 minutos**, con seis sesiones:
**10.217 solicitudes, cero errores, 29 tickets ficticios creados y 12
renovaciones de sesión correctas**. El p95 global fue **157,73 ms** y la memoria
final de la API fue **146,5 MiB**, sin crecimiento sostenido observado durante
esta ventana. No fue una prueba de varias horas ni un certificado de capacidad.

Después de terminar la carga y el escaneo, se repitieron otras 500 lecturas
escalonadas sobre los mismos 5.032 equipos ficticios:

| Solicitudes concurrentes | Lecturas | Errores HTTP | p95 del listado de tickets |
| --- | ---: | ---: | ---: |
| 5 | 50 | 0 | 0,51 s |
| 15 | 150 | 0 | 1,69 s |
| 30 | 300 | 0 | 3,24 s |

La latencia aumenta con la concurrencia; no debe confundirse este ensayo con
el número de trabajadores que podría admitir un servidor definitivo. No hubo
compilaciones, escaneos ni suites activas durante esta última medición.

Al terminar se retiraron los contenedores y volúmenes ficticios, los resultados
temporales y 72 capturas generadas por las pruebas. Se conservaron sus fuentes
automáticas y los documentos de presentación solicitados. El respaldo temporal
ficticio ya no existe; la instalación normal sigue en funcionamiento.

### Límites pendientes

Faltan dominio/HTTPS público y capacidad del servidor definitivo, uso en
dispositivos y red municipal reales, traslado físico a otro equipo y aceptación
de trabajadores y técnicos. Las métricas de esta laptop no garantizan capacidad
en otro servidor. Durante la batería intensiva se observó un tiempo de espera
de la comprobación de salud del worker; después volvió a saludable. Ese aviso
no demuestra una caída del proceso, pero aconseja medir recursos y supervisión
en el despliegue elegido.
## Actualización de seguridad del 25/10/2026: ClamAV

Se repitió Docker Scout sobre las imágenes locales del backend y ClamAV. El
resultado inicial fue de seis alertas altas en el backend y dos en ClamAV.
Al consultar los repositorios oficiales desde contenedores temporales, Alpine
ya ofrecía libcurl 8.23.0-r0, que corrige CVE-2026-92392. Se reconstruyó ClamAV
con `docker compose build --pull --no-cache clamav` y se recreó exclusivamente
ese servicio, conservando su volumen de firmas y los registros del sistema.

La imagen nueva de ClamAV tiene identificador
`sha256:a689ff6f7fc2b51b994d280d60c0cccdb956c8fcda3170e1b293be5d95aba55d`.
El análisis posterior muestra una alerta alta, CVE-2026-86140 en libxml2,
sin corrección disponible según el escáner. El total de los dos componentes
revisados baja de ocho a **siete alertas altas**, sin alertas críticas.
El worker comparte las bibliotecas del backend; no constituye un conjunto
adicional de vulnerabilidades distintas.

Las seis alertas del backend siguen afectando a libxml2, cjson y zlib. Una
consulta actualizada de APT en Debian trixie no ofreció versiones superiores
para esos paquetes y Scout sigue indicando «not fixed». No se mezclaron
repositorios inestables ni se retiraron bibliotecas necesarias para ocultar
los avisos. Esta actualización no declara el sistema libre de vulnerabilidades.

Verificación funcional después del arranque: archivo limpio aceptado y patrón
estándar EICAR bloqueado mediante la función real de escaneo del backend, todo
en memoria, sin adjuntos, archivos ni registros persistidos. Durante el arranque
del antivirus se comprobó también el rechazo temporal por indisponibilidad;
tras cargar las firmas ambas pruebas pasaron. Los siete servicios quedaron en
ejecución y todos los que tienen healthcheck quedaron saludables.

## Correcciones nativas del 26/10/2026

Se prepararon imágenes de producción con correcciones del código nativo, sin
reescribir las versiones de los paquetes ni excluir CVE del escáner.

| Hallazgo previo | Componente | Tratamiento aplicado |
| --- | --- | --- |
| CVE-2026-67216 | cJSON del backend | Dependencia retirada de la imagen de producción. |
| CVE-2026-67215 | cJSON del backend | Dependencia retirada de la imagen de producción. |
| CVE-2026-29036 | cJSON del backend | Dependencia retirada de la imagen de producción. |
| CVE-2026-86140 | libxml2 del backend | Parche oficial de límites de búfer, conservando los parches de Debian y la ABI. |
| CVE-2026-85091 | zlib del backend | Biblioteca recompilada desde el commit oficial que corrige el desbordamiento. |
| CVE-2026-74860 | Módulos Python SAX de libxml2 | Componente vulnerable ausente: no están instalados `libxml2` ni `libxml2mod` de Python. La biblioteca nativa se compila sin esos módulos. |
| CVE-2026-86140 | libxml2 de ClamAV | Mismo parche oficial, conservando el parche y la regresión de Alpine para CVE-2026-6732. |

La API solo utiliza `ffprobe` para comprobar audios. La imagen de producción
ahora compila FFmpeg 9.0.2 como analizador de archivos locales, con los formatos
de audio admitidos por la aplicación, sin protocolos de red, RIST ni cJSON.
El ejecutable completo `ffmpeg` se conserva exclusivamente en la imagen de
desarrollo/pruebas para generar los archivos usados por las regresiones.

Las descargas del código y los parches se verifican mediante SHA-256. La
compilación aplica protección de pila, FORTIFY y RELRO. La base Python se fija
a Debian trixie; se incluye explícitamente `libicu76`, necesaria para el XML
compilado con ICU. Los paquetes Python mantienen las mismas versiones que la
instalación previa. API y worker comparten las mismas capas de archivos.

Verificación realizada:

- Biblioteca XML de Debian: 3.360 regresiones, nueve pruebas de recursión y
  280.912 comprobaciones de API sin errores; `make check` terminó correctamente.
- Biblioteca XML de Alpine: `make check` terminó correctamente, incluidas
  324.154 comprobaciones de API y la regresión de CVE-2026-6732. La suite reconoce
  tres ausencias esperadas de corpus externos; no se afirma haber ejecutado
  las suites externas W3C/NIST/Sun/Microsoft que no se descargaron.
- zlib: `make check` terminó con `zlib test OK`.
- La construcción de la imagen del backend ejecuta
  `security/verify_backports.py`: verifica hashes, bibliotecas realmente cargadas,
  XML con DTD, ausencia de cJSON y módulos Python SAX, compresión, PDF, Excel y WAV.
- **49 pruebas funcionales pasaron**, con dos avisos ya existentes, en 215,74 s:
  notas de voz WebM/OGG/M4A/MP3/WAV, límites y reintentos, reportes, importaciones,
  fotos y seguridad de adjuntos. Usaron exclusivamente MongoDB y Redis de prueba.
- ClamAV corregido aceptó contenido limpio y detectó EICAR con las firmas
  actuales, sin crear adjuntos ni modificar registros reales.
- Tras recrear API, worker y ClamAV, los siete servicios quedaron en ejecución
  y sus healthchecks disponibles saludables. La portada y las dos rutas de salud
  (proxy y API directa) respondieron HTTP 200. Se repitieron las comprobaciones
  de bibliotecas y el escaneo desde el backend desplegado. Se retiraron los
  contenedores y volúmenes del proyecto de pruebas; los datos reales se conservaron.

**Resultado bruto de Docker Scout:** tres avisos altos en la API y uno en
ClamAV, sin críticos. Los tres de cJSON desaparecieron. Los cuatro restantes
corresponden a las versiones originales de paquete de XML/zlib que Scout sigue
marcando: tres casos tienen binarios corregidos y uno requiere módulos Python
que no están presentes. El comando de auditoría estricto sigue devolviendo
fallo por esos cuatro avisos; no se ha cambiado para ocultarlos. Esto no es un
resultado de «cero alertas» ni una certificación de ausencia de vulnerabilidades.

Imágenes verificadas:

- API: `sha256:146bcb4fe9e40b3d45d05490bb0b6f5c6f470d22c8b3903f1c497f8699e76568`.
- ClamAV: `sha256:08f9b2d2a30a035c2403600fbd3c2786ce6585d4a3005cdf075e5f56a93b6760`.

Para comprobar los binarios sin acceder a la base de datos:

```powershell
docker run --rm --network none --entrypoint python mesa-ayuda-api /app/security/verify_backports.py
docker run --rm --network none --entrypoint sh mesa-ayuda-clamav -c "sha256sum -c /usr/local/share/helpdesk/libxml2.sha256"
python tools/auditar_imagenes.py mesa-ayuda-api mesa-ayuda-clamav
```

La imagen guarda las huellas y referencias en
`/usr/local/share/helpdesk/security-backports.json` (API) y
`/usr/local/share/helpdesk/libxml2.sha256` más `libxml2-backport.txt` (ClamAV).
Las licencias del código recompilado acompañan a la imagen del backend.

Mantenimiento: estos backports requieren revisión al actualizar las bases.
ClamAV exige la revisión Alpine `libxml2-2.13.9-r2` antes de sustituir la biblioteca;
si cambia, la construcción falla para que se revisen los nuevos parches del
distribuidor. Cuando Debian/Alpine publiquen las correcciones oficiales, se deben
retirar los backports que ya no hagan falta y repetir las comprobaciones.

Referencias de las correcciones:

- [libxml2: corrección oficial de límites](https://github.com/GNOME/libxml2/commit/d1686f91dbda141a752200419d35639fd6b38340).
- [zlib: corrección oficial del desbordamiento](https://github.com/madler/zlib/commit/df84af25dc1942490e1d1c899a07619152a46148).
- [Debian: alcance del fallo de los módulos Python SAX](https://security-tracker.debian.org/tracker/CVE-2026-74860).
- [Alpine: parches y configuración de libxml2](https://gitlab.alpinelinux.org/alpine/aports/-/blob/3.24-stable/main/libxml2/APKBUILD).

## Revisión de la interfaz del 27/10/2026

Docker Desktop estaba apagado al comenzar; se inició y la instalación habitual
volvió a presentar sus siete servicios en ejecución y healthchecks saludables.
Las pruebas autenticadas usaron exclusivamente el proyecto separado
`helpdesk-verificacion`, con cuentas y datos ficticios.

Resultado: seis recorridos de navegador pasaron en Chromium (7,4 minutos), uno
por cada combinación de administrador/técnico/usuario y móvil/escritorio. Se
revisaron 82 visitas a las rutas de esos roles, comprobando consola,
desbordamiento horizontal, foco visible y accesibilidad grave/crítica. Otras
diez pruebas pasaron (57,9 segundos): guardar/recuperar/eliminar chats, límite
de 15 consultas, likes, reporte y conversación, conservación de borradores,
contraste del portal, separación de mensajes entre tickets, valoraciones y
cambios de IA sin recargar. Estas diez pruebas utilizaron respuestas API
simuladas; no consumieron consultas del proveedor de IA.

Además, el acceso TI servido por la instalación real pasó cuatro comprobaciones
(390 y 1440 píxeles, temas claro y oscuro): HTTP 200, sin errores JavaScript,
desbordamientos ni violaciones graves/críticas de axe. TypeScript pasó;
las 159 llamadas contrastadas con las 151 rutas del OpenAPI fueron correctas;
las comprobaciones de clases y textos de IA también pasaron.

No se reprodujeron nuevos fallos funcionales en este alcance. ESLint conserva
16 advertencias: siete relacionadas con efectos de React, ocho de Fast Refresh
y una directiva de exclusión innecesaria. No son 16 fallos funcionales
demostrados. No se modificaron pantallas solo para hacer desaparecer avisos.
Las pruebas no sustituyen una revisión con dispositivos físicos, todos los
datos reales o una llamada al proveedor generativo real. Los registros reales
no se alteraron y el entorno ficticio y la configuración temporal se retiraron.

## Cierre de calidad del 27/10/2026

Se aplicaron correcciones adicionales después de la revisión anterior:

- Se separaron los hooks/contextos de sesión y avisos de sus proveedores React,
  y las funciones auxiliares de sus componentes. Se actualizaron sus importaciones
  sin cambiar los permisos del servidor. ESLint queda con **cero errores y cero
  advertencias**, y `npm run lint` ahora exige `--max-warnings=0`.
- Se estabilizaron los efectos y callbacks del chatbot, la selección de equipos
  y la sincronización de formularios. Un listado de conversaciones atrasado ya
  no provoca lecturas redundantes; un error al refrescar el historial no borra
  de la pantalla el chat recién creado.
- El alta inicial de zonas/oficinas conserva el nombre escrito durante una
  actualización en segundo plano y durante su fallo temporal. Las pruebas
  provocan expresamente una respuesta 503 y verifican el reintento sin perder
  el borrador, antes de registrar laptop, CPU e impresora.
- Los conteos simples de equipos se contestan desde el total de la lectura
  autorizada, evitando una segunda llamada innecesaria a Groq. Este camino
  rechaza peticiones compuestas, históricas o con condiciones que requieran
  interpretación adicional; no deduce el total de los 20 elementos de muestra.
- Si una ronda de Groq ya consumió tokens y la siguiente falla por cuota o red,
  se conservan los tokens confirmados. Una prueba de persistencia comprueba que
  el error no guarde un mensaje ficticio y que el siguiente intento sume el uso.
- Se añadió `libharfbuzz-subset0` para PDF y se corrigió la secuencia de escape
  del docstring de Excel. La selección de pruebas del backend terminó sin los
  dos avisos que presentaba anteriormente.

Resultados verificables:

| Comprobación | Resultado |
| --- | --- |
| TypeScript y ESLint estricto | Aprobados; cero advertencias de ESLint. |
| Compilación de producción Docker | Web, API y worker construidos. |
| Compilación en Windows | Aprobada con temporales aislados por proceso, tras un bloqueo de un archivo temporal global de esbuild; no se modificaron permisos ni la protección del sistema. |
| Navegador, batería con datos ficticios | 141 escenarios: 140 pasaron y uno falló por exigir la grabación exactamente en el segundo 1 o 2. |
| Repetición del escenario de audio | Aprobada después de comprobar tiempo transcurrido positivo; conserva pruebas de señal, amplitud, envío y reproducción en usuario y soporte. No se presenta como una segunda ejecución completa de los 141. |
| Instalación vacía, posterior al ajuste final del formulario | Tres escenarios aprobados, incluida la actualización fallida de oficinas y su recuperación. |
| Backend relacionado con los cambios | 80 pruebas y 14 subpruebas aprobadas, sin advertencias, en 199,58 s. |
| Chatbot, después de ampliar los casos de precisión y consumo | 31 pruebas y 19 subpruebas aprobadas en 6,29 s. |
| Rutas de la interfaz | 158 llamadas contra 151 rutas válidas; se retiró una función no utilizada. |
| Utilidades del proyecto | Ocho pruebas aprobadas; comprobaciones de clases y textos de IA aprobadas. |
| Auditoría npm, incluidas dependencias de desarrollo | Cero vulnerabilidades informadas. |
| HTTPS aislado | Cadena y nombre verificados con CA de prueba; tres pantallas, cero infracciones CSP; cookies Secure/HttpOnly, CSRF, rechazo CORS ajeno, rutas privadas y revocación HTTP/WebSocket aprobados. |

Groq real completó tres pruebas sobre una copia **ficticia**, sin alterar registros:
el recuento exacto fue 29, rechazó borrar tickets y rechazó entregar secretos.
El usuario normal fue rechazado antes de acceder al proveedor. Las tres respuestas
exitosas informaron 7.824 tokens en total; esto no representa el saldo diario ni
todo el consumo de la cuenta. El primer intento, previo a la optimización del
conteo, había alcanzado un límite del proveedor y la sonda se detuvo. No se
activó un plan de pago ni se cambió de proveedor o modelo automáticamente.

Las pruebas de instalación vacía se ejecutan separadamente con
`npm run test:e2e:inicial` y `playwright.inicial.config.ts`; el resto usa
`npm run test:e2e`. En ambos casos debe prepararse la API aislada correspondiente
y definir `PRUEBA_API_URL=http://127.0.0.1:18100`. La configuración espera su
salud antes de comenzar. El trabajo de backend de GitHub Actions dispone de
45 minutos para incluir la compilación y pruebas de las bibliotecas nativas;
esta edición del flujo no equivale a una ejecución remota nueva de Actions.

La auditoría de las imágenes actualizadas conserva **cuatro avisos altos brutos**:
tres en API/worker y uno en ClamAV; la web no presenta altos ni críticos. Son
los casos de XML/zlib ya documentados, con binarios parcheados o módulos Python
ausentes. La verificación de hashes, bibliotecas cargadas, XML, compresión,
PDF/Excel, WAV y EICAR se repitió en el backend desplegado. Los repositorios
estables consultados todavía no ofrecían nuevas revisiones de esos paquetes.
No se han excluido avisos del escáner para anunciar falsamente cero alertas.

Antes de una publicación definitiva siguen pendientes el servidor y dominio
reales, su certificado y renovación, capacidad en ese servidor, aceptación con
dispositivos/red municipal y validación estadística de predicciones contra
historial real revisado por TI. Las pruebas locales y sintéticas no certifican
ausencia absoluta de fallos ni precisión predictiva universal.

El ajuste final del alta también pasó las tres pruebas con el fallo 503 y su
recuperación (55,0 s). La web final se volvió a construir y desplegar; sus cuatro
comprobaciones de acceso real (claro/oscuro y móvil/escritorio) dieron HTTP 200,
sin errores JavaScript, desbordamientos ni accesibilidad grave/crítica.
Su imagen final, `sha256:613997e0868344ab286567e157bb1ecafa7c7914f5664de1c2efb7f7dc324be3`,
no presenta avisos altos ni críticos en Scout. La API desplegada y auditada es
`sha256:1a6a87bd97ee0a956ee2ea0f22cffba80ffab58b4fccd50c27ccf84d1d354b50`;
el worker comparte sus mismas capas. Los siete servicios locales quedaron
operativos y se comprobaron los accesos HTTP y el escaneo de archivos sin
modificar los registros de producción.

Se retiraron los contenedores y volúmenes ficticios, el archivo de resultados
temporal y 74 capturas automáticas de este cierre. Se conservaron los casos de
prueba y sus fixtures de código. Los datos y archivos de producción no se borraron.

## Flujo de reportes personales y de oficina (28/10/2026)

- El portal presenta primero tres tarjetas con iconos: Para mí, Para un compañero y Para la oficina (algo compartido). No hace preguntas adicionales sobre la propiedad de una impresora ni deduce el propietario por la categoría; TI identifica el equipo.
- En la ficha TI, un reporte personal muestra una sola vez quién reportó y «Para sí mismo». Un reporte de oficina indica que afecta a la oficina; el origen deja de describirlo como personal. El portal también muestra el destino del reporte.
- Cuando TI identifica un equipo compartido al editar, el destino pasa a oficina dentro de la misma actualización auditada. Se conserva quién reportó y la persona de contacto. No se asigna automáticamente una de varias impresoras.
- Se mantiene el bloqueo del origen de equipos ya identificados para evitar cambios accidentales a equipos ajenos. Esta mejora no habilita cambiar libremente de persona u oficina.
- Historial: Zonas y oficinas → abrir una zona → abrir la oficina → Historial de tickets. Por defecto incluye abiertos y cerrados; se puede filtrar a abiertos o cerrados. Incluye reportes de la oficina y personales de sus trabajadores, ordenados por creación del más reciente al más antiguo.
- El historial de un equipo concreto requiere vincular el ticket a ese equipo. Elegir solo un tipo, por ejemplo Impresora, no crea esa vinculación.

Validación del cambio: seis pruebas de servidor en test_destinos_reales_ticket.py y cuatro escenarios de navegador (destino personal/oficina, orientación de impresora y consulta del historial con filtros), sin datos reales. Se conserva el código de pruebas automáticas.

## Identificación y filtro de equipos compartidos (29/10/2026)

En la edición del ticket, TI confirma el registro con dos tarjetas: Equipo de la persona (muestra el trabajador afectado) y Equipo compartido de la oficina (muestra la oficina). La lista se filtra por la tarjeta. Al guardar el equipo real, el destino se actualiza en ambos sentidos y se audita; quien reportó nunca cambia. Si reportaron por un compañero, se conserva ese compañero como afectado. La corrección expresa de TI permite cambiar de origen incluso en un equipo ya identificado, manteniendo los límites de persona y oficina. Sin esa corrección expresa, las llamadas existentes conservan el bloqueo. No se cambia el propietario del equipo.

Registro de un equipo compartido: Equipos → Inventario → Registrar equipo; seleccionar zona y oficina y dejar Responsable sin asignar. Para consultar: Inventario → Oficina → Asignación: Compartidos de la oficina. El filtro usa la ausencia de responsable, igual que la ficha de oficina. También se consultan en Zonas y oficinas → oficina → Equipos de uso común. Tener un responsable asignado hace que el equipo figure como personal para este flujo.

Validación del ajuste de destino: 8 pruebas de servidor y 4 de navegador aprobadas. El historial de oficinas utiliza el rótulo Solo cerrados.

## Verificación de seguridad y preparación de GitHub (29/10/2026)

Se analizaron las imágenes locales actuales con Docker Scout y su información de vulnerabilidades disponible al ejecutar la revisión. El resultado cambió respecto al informe del 27/10: no debe reutilizarse el total anterior de cuatro avisos.

| Componente | Imagen verificada (prefijo SHA-256) | Críticos | Hallazgos altos |
| --- | --- | --- | --- |
| API y worker | API 34fd80eaf802; worker ceaac84040fb | 0 | 5 por imagen, agrupadas una sola vez por tener capas idénticas |
| ClamAV | 08f9b2d2a30a | 0 | 1 |
| MongoDB | 1e7292430959 | 0 | 1 |
| Proxy Caddy | 1f9490a80b42 | 0 | 2 (la misma CVE en dos módulos) |
| Web | 745cf3ce6ce7 | 0 | 0 |
| Redis | 57e4255cc971 | 0 | 0 |

Son 9 coincidencias altas por componente agrupado, correspondientes a 7 identificadores CVE distintos. API/worker se cuenta como un grupo; si se cuentan ambos contenedores por separado, se duplican sus cinco coincidencias. El análisis se filtró a altas y críticas: esta tabla no certifica ausencia de avisos medios o bajos.

- API/worker: CVE-2026-74860 y CVE-2026-86140 (libxml2), CVE-2026-85091 (zlib), más los avisos nuevos CVE-2026-118370 y CVE-2026-117610 (Expat). Scout no indica versión corregida para los paquetes Debian analizados.
- ClamAV: CVE-2026-86140 (libxml2). El escáner sigue sin indicar una revisión corregida del paquete Alpine analizado.
- MongoDB: CVE-2026-111497 en Brotli 1.1.0-2build2. Scout lo marca CISA KEV e informa 1.1.0-2ubuntu0.1 como versión corregida. Requiere actualización y verificación; no se corrigió en esta tarea de revisión.
- Proxy: CVE-2026-116587 aparece en go-jose/v4 4.1.5 y go-jose/v3 3.0.5. Scout informa corrección en v4 4.1.6 y ninguna para v3. Requiere revisar ambas dependencias; no basta con actualizar una para declarar solucionado el hallazgo.

Las verificaciones nativas en el backend desplegado aprobaron hashes, bibliotecas cargadas, XML/DTD, ausencia de cJSON y bindings Python SAX, zlib, PDF/Excel y ffprobe. También aprobó el hash del libxml2 parcheado de ClamAV. Es evidencia de las correcciones previas de XML/zlib y de la no aplicabilidad del binding ausente; no cubre las alertas nuevas de Expat, Brotli o go-jose ni elimina automáticamente los avisos del escáner.

El antivirus aceptó contenido limpio y bloqueó EICAR mediante el flujo de la API, exclusivamente en memoria, sin archivos ni registros nuevos. La auditoría npm completa, incluidas dependencias de desarrollo, informó cero vulnerabilidades. HTTP local comprobado: web y salud 200; tickets sin sesión 401; /.env y /.git/config 404; cabeceras CSP, DENY y nosniff presentes.

La revisión de archivos publicables comprobó 416 archivos sin problemas de publicación ni coincidencias de credenciales del entorno. GitHub confirmó repositorio privado y permiso de escritura mediante la conexión Git local. El conector GitHub no tenía acceso a este repositorio y devolvió 404; no se cambiaron permisos ni visibilidad.

No se modificaron registros ni archivos de producción. El dominio, HTTPS y la capacidad del entorno definitivo siguen pendientes de que el titular facilite ese entorno. Antes de publicarlo, revisar los avisos altos nuevos y repetir la auditoría tras aplicar sus correcciones.
