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
imágenes e inicia los servicios. Si `.env` ya existe, lo conserva. Abre
`http://localhost`; también puedes entrar por `http://localhost:8080`.
La primera instalación permite crear el administrador desde la web. No hay
cuentas de demostración precargadas en producción.

Configura `GROQ_API_KEY` en el `.env` **del servidor** si quieres activar el chatbot.
El resto del sistema puede iniciar sin esa clave. Después de cambiar el entorno:

```bash
docker compose up -d api worker
```

Si un puerto está ocupado, configura `WEB_PORT`, `API_PORT` o `MONGO_PORT` en `.env`.
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

La revisión comprobó 62 paquetes Python y la auditoría completa npm sin avisos
pendientes después de actualizar dependencias. Se aprobaron 89 pruebas del
servidor (más 4 subpruebas), 16 casos de navegador en cuatro motores/perfiles y
un recorrido HTTPS con certificado de prueba verificado, cookies Secure/HttpOnly,
CORS ajeno rechazado, CSRF obligatorio y cierre de WebSocket tras revocar sesión.
Esto cubre dependencias de aplicación y configuración; no es un escaneo completo
del sistema operativo ni una certificación de seguridad de una instalación remota.

Los ensayos se repiten con:

```bash
docker compose build api worker web proxy
docker compose -f compose.pruebas.yml --profile seguridad up -d --wait api-seguridad web-seguridad proxy-seguridad
python tools/verificar_publicacion.py --ejecutar
python tools/auditar_dependencias.py
```

El perfil seguridad usa datos ficticios y una CA efímera dentro de sus
contenedores. No instala certificados de confianza en Windows. El navegador de
la sonda fija la clave pública del certificado previamente validado por Python.
El antivirus de adjuntos es opcional y no se activó durante estos ensayos;
la revisión de tipo y tamaño de archivos no sustituye un análisis antimalware.

### Auditoría de las imágenes Docker

La revisión de Python y JavaScript no incluye todas las bibliotecas del sistema
operativo ni las que vienen incorporadas en otras herramientas. También se
comprobó este nivel con Docker Scout. Las imágenes reconstruidas de web y proxy
no presentaron avisos altos o críticos en el escaneo realizado; Redis actualizado
tampoco. Esto no significa que todos los servicios estén libres de vulnerabilidades.

La imagen del backend mantiene siete avisos altos en bibliotecas Debian
(`cjson`, `libxml2`, `zlib` y `harfbuzz`) que el escáner señala sin versión
corregida para esa distribución. La imagen oficial MongoDB 8.0 auditada mantiene
avisos altos y críticos en componentes incluidos, entre ellos las herramientas
Go y `js-yaml`. No se deben omitir estos avisos al decidir una publicación en
Internet: requieren revisar alcance, actualizaciones y mitigaciones. MongoDB y
Redis permanecen fuera de los puertos públicos de la configuración de publicación.

Se actualizó Nginx a 1.30.6 y se retiraron curl y módulos dinámicos que esta web
no utiliza. El proxy compila Caddy 2.11.7 con Go 1.26.9 y x/net 0.60.0 sobre un
runtime Alpine mínimo. El backend de producción conserva el usuario sin
privilegios y no incorpora pip ni sus dependencias de instalación en ejecución.
Las imágenes de desarrollo sí mantienen pip para ejecutar las pruebas.

Para repetir el análisis de imágenes locales, sin guardar informes:

```bash
python tools/auditar_imagenes.py mesa-ayuda-api mesa-ayuda-web mesa-ayuda-proxy redis:7-alpine mongo:8.0
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
