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
