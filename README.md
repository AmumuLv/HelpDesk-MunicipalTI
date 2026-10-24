# HelpDesk-MunicipalTI

**Instalar, actualizar o trasladar a otro equipo:** consulta la [guía de instalación y traslado](docs/INSTALAR_Y_TRASLADAR.md).

Archivos y espacio utilizado: [guía de almacenamiento](docs/ALMACENAMIENTO.md).

Inicio rápido en Windows con Git y Docker Desktop:

```bash
iniciar.cmd
```

En Linux/macOS: `python3 tools/trasladar.py iniciar` (Python 3.10+). El código se guarda en GitHub; los datos y adjuntos se trasladan mediante un respaldo privado. El archivo `.env` nunca se publica.

Sistema institucional para que una municipalidad atenda los problemas de
computación de sus oficinas: inventario de equipos, tickets reportados en dos
pasos, chat solo cuando lo reporta una persona, horarios y carga real del equipo
de soporte, archivo de inventario por año y análisis con datos verificables.

Todo se levanta con un solo comando y funciona aunque el proveedor de IA esté
caído: ninguna función crítica depende de un servicio externo.

---

## Levantar el sistema

Requisitos: Docker y Docker Compose.

En Windows puedes usar directamente `iniciar.cmd`. El siguiente método manual
requiere Python para generar la clave; no es necesario si usas el iniciador.

```bash
cp .env.example .env
# Edita .env y coloca un SECRET_KEY largo y aleatorio:
python -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose up -d
```

| Servicio | Dirección | Qué es |
|---|---|---|
| Proxy | http://localhost | Punto de entrada: web y API en el mismo origen |
| Interfaz | http://localhost:8080 | La web por separado (útil para depurar) |
| API | http://localhost:8000/api | La API sin interfaz |
| MongoDB | mongo:27017 | Réplica set de un nodo (transacciones) |
| Redis | redis:6379 | Sesiones, avisos en vivo y colas |

La primera vez, entra a http://localhost y la propia aplicación te guía: crear la
cuenta de administrador, importar el Excel de inventario, dar de alta a las
personas y al equipo de soporte.

### Conectar con MongoDB Compass (opcional)

El puerto de Mongo se publica únicamente en el propio equipo
(`127.0.0.1:27018`), nunca en la red local. Se usa 27018 y no 27017 porque ese
puerto suele estar ocupado por un MongoDB instalado directamente en Windows
(servicio `MongoDB Server`), que es una base **distinta** y no contiene los datos
del sistema.

El réplica set se anuncia con el nombre interno de Docker (`mongo:27017`), que
Windows no puede resolver, así que la conexión debe ser directa:

| Campo de Compass | Valor |
|---|---|
| Host | `127.0.0.1:27018` |
| Direct Connection | activado |
| Cadena de conexión | `mongodb://127.0.0.1:27018/?directConnection=true` |
| Base de datos | `mesa_ayuda` |

Para cambiar el puerto sin tocar el archivo, define `MONGO_PORT` en `.env`.

### Datos de demostración (opcional)

```bash
docker compose exec api python -m app.scripts.demo cargar     # carga datos de ejemplo
docker compose exec api python -m app.scripts.demo eliminar    # los borra
```

Los datos de demostración quedan marcados con `demo: true` y nunca se mezclan con
los reales.

### Servicios opcionales

```bash
docker compose --profile backup up -d     # respaldos programados de MongoDB
docker compose --profile antivirus up -d  # análisis de adjuntos con ClamAV
```

### Desarrollo

```bash
# Backend con recarga automática
docker compose build api && docker compose up -d --force-recreate api
docker compose exec api uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Interfaz con recarga automática (proxy a la API del host)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## Verificar antes de publicar

Las pruebas se ejecutan en servicios separados, sin datos ni claves reales:

```bash
docker compose -f compose.pruebas.yml run --build --rm tests
docker compose -f compose.pruebas.yml down -v
python tools/revisar_publicacion.py
python tools/verificar_rutas.py
cd frontend
npm ci
npm run lint
npm run build
npx playwright install chromium
npx playwright test pruebas/portal-sencillo.spec.ts
```

GitHub Actions ejecuta la suite del servidor, la compilacion, el portal simulado
y las comprobaciones de publicacion. La guia de traslado explica como preparar
la API efimera para las pruebas de navegador con datos ficticios.

La revisión funcional del 23/10/2026 comprobó 286 pruebas del servidor y 22
subpruebas, 135 casos de navegador entre la revisión y sus repeticiones, 41
pruebas de estilos y 8 de las herramientas de traslado y rutas. Se verificaron
usuarios, técnicos y administradores: tickets, permisos, perfiles, adjuntos,
inventario, organización, horarios, conocimiento, reportes y sincronización.
Incluye 123 recorridos de pantalla en celular, tableta y escritorio.

Se corrigieron el registro de programas en laptops independientes, consultas de
exportaciones sin permiso, el foco del teclado, el contraste de zonas, la
conservación de la selección anual y las rutas temporales de Windows al
restaurar. Las pruebas de navegador usan Chromium, respuestas de IA simuladas y
micrófono ficticio; no certifican proveedores externos ni todos los navegadores.
La compilación pasa; lint conserva 16 advertencias previas y ningún error.

La ampliación de resiliencia añadió 13 casos del servidor. La corrida general
aprobó 293 casos y 22 subpruebas; después de la optimización del SLA pasaron 44
casos dirigidos, incluidos los nuevos casos de calendario. Se verificaron 12
casos distintos en Chromium y Edge; la sincronización por WebSocket se repitió
dos veces por navegador, exigiendo que el cambio remoto aparezca en menos de
cuatro segundos desde la respuesta del servidor.

En la instalación aislada se crearon 5.000 equipos ficticios y 100 tickets
concurrentes sin códigos duplicados. Las 500 lecturas con concurrencias de 5,
15 y 30 terminaron sin errores HTTP. Tras reutilizar calendario y feriados solo
dentro de cada operación, el percentil 95 del grupo de 30 bajó de 24,0 a 3,1
segundos en esta laptop. Es una medición local, no una garantía de capacidad.
Se comprobaron PDF, Excel completo, reinicios, primer arranque y restauración
real en otra base y volumen, conservando idénticos la foto y el adjunto de
prueba. Firefox y WebKit quedaron sin verificar porque sus descargas agotaron
el tiempo de espera. Los ensayos no consumen consultas de proveedores de IA.

Para repetir los ensayos de concurrencia y recuperación sin tocar la instalación
normal:

```powershell
docker compose -f compose.pruebas.yml --profile navegador up -d --wait api
$env:PRUEBA_API_URL='http://127.0.0.1:18100'
$env:PRUEBA_NAVEGADORES='chromium,msedge'
cd frontend
npx playwright test pruebas/resiliencia.spec.ts
cd ..
python tools/verificar_resiliencia.py --ejecutar
docker compose -f compose.pruebas.yml --profile navegador --profile suite --profile restauracion down -v
```

Edge debe estar instalado; se puede elegir solo `chromium`. Firefox y WebKit son
opcionales mediante `PRUEBA_NAVEGADORES`, después de instalarlos con Playwright.
Ejecuta el ensayo operativo después de terminar las otras pruebas: reinicia los
servicios aislados, genera 5.000 equipos ficticios y comprueba un traslado real a
otra base y volumen. El archivo temporal de traslado se elimina al terminar.
El último comando elimina exclusivamente los volúmenes de pruebas.


---

## Estructura

```
backend/            API FastAPI, servicios de dominio y worker de tareas
  app/
    api/routes/     Rutas HTTP por área
    services/       Reglas de negocio (donde vive cada decisión)
    domain/         Esquema de datos, permisos y catálogos
    migrations/     Cambios de base de datos versionados
    core/           Configuración, seguridad, fechas, identificadores
    scripts/        Operaciones de consola (migraciones, salud, humo, demo)
  tests/            Pruebas de integración sobre Docker
frontend/           Interfaz React 19 + TypeScript + Vite + Tailwind v4
  src/componentes/  Componentes reutilizables de la interfaz
  src/paginas/      Una pantalla por archivo
  src/api/          Cliente HTTP único y servicios del dominio
deploy/             Caddyfile, configuración de Nginx y script de respaldo
docs/               Guías esenciales de instalación, almacenamiento, IA e inventario
```

---

## Comandos de operación

```bash
# Estado del sistema (colecciones, índices, migraciones)
docker compose exec api python -m app.scripts.salud

# Aplicar migraciones pendientes
docker compose exec api python -m app.scripts.migraciones

# Crear el primer administrador por consola
docker compose exec api python -m app.scripts.admin_crear \
  --nombre "Ana Pérez" --email ana@muni.gob.pe --password "ClaveSegura1"

# Diagnóstico rápido de la API
docker compose exec api python -m app.scripts.diagnostico
```

---

## Reportes disponibles

| Reporte principal | Contenido y alcance |
| --- | --- |
| Tickets del periodo | Casos creados en las fechas elegidas, personas, equipos, técnicos y estado actual. |
| Inventario por zona | Equipos y responsables actuales; hojas de Excel y secciones PDF por zona. |
| Carga del equipo TI | Casos creados en el periodo por técnico actual, finalizados de esos casos y pendientes actuales de todo su historial. |
| Resumen de atención | Cuatro indicadores, comparación anterior, oficinas, plazos, problemas frecuentes, técnicos y zonas. |
| Movimientos importantes | Quién cambió qué y cuándo; cambios relevantes y alertas de seguridad. |

PDF sirve para presentar y leer; Excel y CSV conservan los datos para trabajar.
El resumen PDF se centra en atención; Excel y CSV también incluyen métricas del
asistente y familias de equipos con su alcance de doce meses. Los vencidos y los
casos por vencer se presentan por separado, sin contarlos dos veces.

Las fichas de ticket y equipo, los pendientes de calidad y la verificación de
inventario se exportan desde sus módulos; no duplican opciones en el menú de
reportes. Las fichas de ticket se generan solo en PDF. Las muestras de prueba
no se guardan en la instalación operativa.

## Cómo decide el sistema

Las reglas se explican en el código donde se aplican. Las cinco más importantes:

1. **El chat depende del origen del ticket, y lo decide el backend.** Si lo
   reporta una persona (para sí o para un compañero) hay conversación. Si lo
   registra el equipo TI, hay línea de tiempo y notas internas, sin chat. El
   endpoint devuelve 403 con el código `sin_chat` si alguien intenta escribir.

2. **En el inventario solo son obligatorios el tipo y la oficina.** El resto de
   campos tiene tres estados: Pendiente, No aplica y No disponible. Los dos
   últimos salen del denominador de completitud y quedan registrados con su
   motivo, sin borrar nada.

3. **Los permisos delegables empiezan todos apagados** y los activa el
   administrador uno por uno. Cada cambio queda en la auditoría con el valor
   anterior. La interfaz oculta lo que no está permitido, pero la validación
   real siempre es del servidor.

4. **La IA es opcional en todo momento.** La clasificación, la asignación, los
   SLA y la completitud se calculan con reglas y con datos reales. Si no hay
   modelo de lenguaje, el sistema lo dice y sigue funcionando. Cuando faltan
   datos para una predicción, responde `suficiente_datos: false` con el mínimo
   necesario en vez de mostrar una cifra inventada.

5. **El horario gobierna los tiempos.** Días libres, ausencias, feriados y
   tramos descartan el reloj del SLA, así que el cumplimiento mide el servicio y
   no la presencia en la oficina.

---

## Respaldos

En Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/trasladar.ps1 respaldar backups/municipalidad.helpdesk.zip
```

En Linux/macOS:

```bash
python3 tools/trasladar.py respaldar backups/municipalidad.helpdesk.zip
# Solo en una instalacion de destino nueva y vacia:
python3 tools/trasladar.py restaurar backups/municipalidad.helpdesk.zip
```

Incluye MongoDB y adjuntos, valida integridad y conserva los servicios que estaban
activos. No incluye el entorno ni claves. Consulta la guia de instalacion y
traslado antes de restaurar; el respaldo contiene datos privados.

El perfil opcional `backup` mantiene respaldos programados de MongoDB. Su bucle
es continuo; no se utiliza como comando de respaldo inmediato.


---

## Accesibilidad y diseño

- Tipografía Atkinson Hyperlegible, pensada para leer mucho; servida desde el
  propio servidor, sin CDN.
- Colores definidos con tokens semánticos en OKLCH: ningún componente escribe
  hexadecimales.
- Tema claro institucional con colores semánticos y contraste verificado.
- Navegación completa por teclado, foco visible siempre, diálogos que atrapan el
  foco y devuelven la atención al cerrarse, y textos alternativos en los
  gráficos (cada dato se puede leer también como tabla).
- El cuerpo del texto nunca baja de 16 px y las tablas se convierten en listas
  en pantallas pequeñas.
