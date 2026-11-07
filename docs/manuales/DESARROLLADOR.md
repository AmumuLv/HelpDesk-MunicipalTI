# Manual del desarrollador

Versión de la guía: 06/11/2026. Repositorio HelpDesk-MunicipalTI.

## Qué se está manteniendo

Una aplicación de soporte municipal con React y TypeScript, API FastAPI,
MongoDB, Redis y un worker ARQ. El proxy Caddy entrega la web y la API bajo el
mismo origen. El frontend compilado se sirve con Nginx. La IA interna y el
chatbot tienen responsabilidades diferentes: véase [IA del sistema](../IA_DEL_SISTEMA.md).

## Dónde modificar cada cosa

| Carpeta | Responsabilidad |
| --- | --- |
| `frontend/src/paginas` | Pantallas y formularios de cada área. |
| `frontend/src/componentes` | Controles, tablas, diálogos y componentes compartidos. |
| `frontend/src/api` | Cliente HTTP, contratos TypeScript y llamadas a servicios. |
| `backend/app/api/routes` | Entrada HTTP, sesión, permisos y validación del contrato. |
| `backend/app/schemas` | Modelos de entrada y salida. |
| `backend/app/services` | Reglas de negocio, consultas y operaciones. |
| `backend/app/domain` | Roles, permisos, tipos e índices base. |
| `backend/app/core` | Configuración, conexión, seguridad, fechas y errores. |
| `backend/app/migrations` | Evolución versionada de la base. |
| `backend/app/worker` | Colas y tareas periódicas. |
| `backend/tests` y `frontend/pruebas` | Pruebas de servidor y navegador. |
| `deploy` y `tools` | Contenedores, proxy y herramientas de operación. |

## Preparar desarrollo sin utilizar datos reales

1. Obtén el repositorio privado autorizado e instala Docker, Node.js 22 y Python
   para las herramientas que necesites ejecutar en el host.
2. Prepara un entorno de desarrollo separado. No copies `.env`, adjuntos ni
   respaldos municipales a un entorno de demostración compartido.
3. Inicia la API ficticia desde la raíz:

```powershell
docker compose -f compose.pruebas.yml --profile navegador up -d --wait api
```

4. Desde `frontend`, instala dependencias con `npm ci`. Para desarrollo manual
   contra esa API:

```powershell
$env:VITE_API_TARGET='http://127.0.0.1:18100'
npm run dev
```

5. Usa exclusivamente las cuentas ficticias preparadas por
   `app.scripts.preparar_pruebas`. No ejecutes ese preparador dentro de la API
   operativa. Playwright levanta su propio Vite en el puerto 4321.

La instalación operativa se explica en [Instalación técnica](../INSTALACION_TECNICA.md).
Desarrollo con recarga no es la forma de publicar el servicio.

La API ficticia monta el código del backend. Después de editar Python, reinicia
ese servicio con `docker compose -f compose.pruebas.yml restart api` desde la raíz.
No inicies un segundo Uvicorn en el puerto que ya ocupa la API. Un cambio de
dependencias requiere reconstruir su imagen de pruebas.

## Reglas que una mejora debe conservar

- La autorización se comprueba en el servidor con el usuario vigente. Ocultar un
  botón no autoriza ni impide por sí solo una petición.
- Solo existen los roles `usuario`, `tecnico` y `administrador`. El principal es
  un administrador con un indicador protegido, no un cuarto rol.
- Una persona nueva recibe otro identificador. No se renombra la cuenta anterior
  para representar al reemplazo ni se trasladan sus tickets personales.
- Un equipo conserva su identificador aunque cambie de responsable. La posición
  de una fila del Excel no es una identidad patrimonial.
- Los conjuntos representan PC de escritorio. Laptops y dispositivos independientes
  no se convierten en conjuntos para facilitar una pantalla.
- El estado final actual es `cerrado`. Los datos legados requieren compatibilidad;
  no se reintroduce `resuelto` en formularios nuevos.
- Las fechas se almacenan con zona horaria; los intervalos de negocio se calculan
  en `America/Lima`. Una fecha de API ISO no obliga a mostrarla así al usuario.
- Las mutaciones deben producir la invalidación o el aviso necesario para que
  otras sesiones vean el cambio. Comprueba también el caso de permiso retirado
  mientras un formulario está abierto.
- No añadas claves, contraseñas, tokens, archivos personales ni datos de producción
  a ejemplos, fixtures, logs o al repositorio.

## Cambiar una colección

Agrega una migración nueva `mNNN_descripcion.py`; no reescribas una ya aplicada.
El ejecutor registra versiones en `_migraciones` y se ejecuta al iniciar la API.
Describe campos, compatibilidad con documentos anteriores, índice necesario y
forma de recuperación. Una migración no es automáticamente reversible.

Una transacción solo protege las operaciones que utilizan su sesión de MongoDB.
La mera presencia de `start_transaction()` alrededor de llamadas no convierte
todas las escrituras en atómicas. La importación informa resultados por fila;
no debe presentarse como un reemplazo total del inventario.

## Mantener las dependencias nativas

El Dockerfile compila mitigaciones para bibliotecas nativas y ejecuta
`security/verify_backports.py`. Sus fuentes, versiones, parches y hashes forman
parte de la entrega: no se elimina una comprobación de integridad para conseguir
que una imagen termine de construir.

Los parches de seguridad fijados se documentan en
[su procedencia](../../backend/security/patches/README.md). Conserva los finales
de línea LF y los hashes esperados al trasladar desde Windows. Una descarga
fallida, un formato externo que cambió y una vulnerabilidad nueva son problemas
distintos; analiza la causa antes de sustituir una dependencia o un hash.

La base Python está fijada por versión y digest porque `pyexpat` se reconstruye
para esa misma versión de CPython. Una actualización debe revisar conjuntamente
la imagen, las fuentes y hashes de la extensión y las pruebas; no basta con
cambiar una etiqueta o eliminar la comprobación de versión.

Después de modificar este bloque, reconstruye la imagen y ejecuta las pruebas
nativas. La prueba funcional no reemplaza una auditoría actual de CVE; los
escáneres pueden seguir avisando sobre versiones de paquetes cuyos binarios
fueron parcheados. La evaluación debe conservar el aviso y su evidencia de
mitigación, sin ocultarlo como si nunca hubiera existido.

## Comprobar un cambio

Desde la raíz, servidor y herramientas:

```powershell
docker compose -f compose.pruebas.yml run --rm tests
python -m unittest discover -s tools -p 'test_*.py'
python tools/verificar_rutas.py
```

Desde `frontend`:

```powershell
npm ci
npm run lint
npm run typecheck
npm run build
npm run verify:ai-texts
npm run verify:clases
```

Para navegador, deja iniciada la API ficticia, instala Chromium con
`npx playwright install chromium` y ejecuta desde `frontend`:

```powershell
$env:PRUEBA_API_URL='http://127.0.0.1:18100'
$env:PRUEBA_NAVEGADORES='chromium'
npx playwright test pruebas/flujos-combinados-roles.spec.ts --reporter=list
```

Escoge además regresiones del área modificada. Los escenarios de primer arranque,
HTTPS y restauración tienen preparación propia; consulta sus guías antes de
mezclarlos con una base ya sembrada. Los ejemplos de proveedor no autorizan
consumir cuotas reales sin necesidad.

## Entregar y retirar el entorno ficticio

Registra alcance, pruebas, riesgos y reversión en el
[control de cambios](../GESTION_DE_CAMBIOS.md). Comprueba el contenido exacto del
commit. `tools/revisar_publicacion.py` verifica publicación y puede leer el entorno
local para contrastar secretos; nunca imprimas sus valores ni adjuntes ese archivo.

Si cambia una guía del expediente, regenera también el Word. La comprobación de
CI detecta que el documento no corresponda a sus fuentes. Con `uv` instalado:

```powershell
uv run --no-project --python 3.11 --with python-docx tools/generar_manuales.py
python tools/verificar_manuales.py
```

`python-docx` se utiliza para documentación; no es una dependencia nueva de la API.

Cuando terminen las pruebas, el siguiente comando elimina los servicios y
volúmenes del proyecto ficticio, no los de `mesa-ayuda`:

```powershell
docker compose -f compose.pruebas.yml --profile '*' down --volumes --remove-orphans
```

No uses `docker compose down -v` en una instalación con datos municipales.
