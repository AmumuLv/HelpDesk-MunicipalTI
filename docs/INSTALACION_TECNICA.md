# Referencia técnica de instalación

Para la explicación sencilla, empieza por [PC nueva](NUEVA_PC.md). Esta referencia es para TI.

## Linux y macOS

Requiere Docker Compose y Python 3.10 o superior. Descarga el repositorio autorizado o extráelo. Desde su raíz:

```bash
python3 tools/trasladar.py iniciar
```

Crea `.env` si falta, genera `SECRET_KEY` y ejecuta `docker compose up -d --build --wait`. Conserva el entorno y los volúmenes de una instalación existente.

Para trasladar datos, con destino vacío:

```bash
python3 tools/trasladar.py respaldar backups/municipalidad.helpdesk.zip
python3 tools/trasladar.py restaurar backups/municipalidad.helpdesk.zip
```

El primer comando se ejecuta en origen y el segundo en destino. Nunca sobre una base con registros reales preexistentes.

## Puertos y conexión

- El proxy local utiliza 80 y 443; el acceso habitual es `http://localhost`.
- El frontend directo utiliza `127.0.0.1:8080`, modificable mediante `WEB_PORT`.
- La API directa utiliza `127.0.0.1:8000`, modificable mediante `API_PORT`.
- Cambiar `WEB_PORT` no resuelve un conflicto del puerto 80 del proxy. Libera ese puerto o ajusta el mapeo del proxy conscientemente en Compose.
- Desde otros equipos se utiliza la dirección del servidor y el proxy. Los puertos directos anteriores solo escuchan en la propia PC.

Para errores de descarga, verifica conexión y red de Docker. Si el entorno tiene red host habilitada, `BUILD_NETWORK=host` es una alternativa de construcción; no cambia los puertos de acceso de la web.

## Configuración pública

Completa `PUBLIC_DOMAIN` en `.env`, sin protocolo ni rutas, y configura DNS y acceso al servidor. Para el modo público previsto:

```bash
docker compose -f docker-compose.yml -f compose.publico.yml up -d --build --wait
```

Este modo configura el proxy y cookies seguras para el dominio y restringe puertos directos. El certificado requiere que el dominio y los puertos necesarios sean accesibles. Valida HTTPS real y la conexión desde las redes previstas antes de entregar el servicio. Una prueba local no certifica el dominio definitivo.

## Secretos, claves y archivos

El programa está en GitHub; la base y las subidas están en volúmenes de Docker. Conserva la configuración privada por separado. Una copia del repositorio no es una copia de los datos.

`SECRET_KEY` se genera en el primer inicio. El iniciador no reemplaza un `.env` existente. La clave original de cifrado de licencias debe acompañar cualquier restauración que contenga licencias cifradas. Las claves de proveedores se configuran de nuevo en destino; no van en el paquete de traslado.

Los paquetes se verifican con SHA-256 y se rechaza un destino ocupado. Esta comprobación detecta alteraciones accidentales; no equivale a una firma de procedencia. Restaura solo paquetes confiables y custódialos como información privada.

Consulta las rutas y los volúmenes en [Almacenamiento](ALMACENAMIENTO.md).

## Repetir las comprobaciones

Pruebas unitarias del traslado, sin utilizar los datos reales:

```bash
python -m unittest discover -s tools -p test_trasladar.py -v
```

Pruebas del diagnóstico con HTTP simulado, dentro de la imagen de pruebas:

```bash
docker compose -f compose.pruebas.yml run --no-deps --rm tests python -m unittest tests.test_diagnostico -v
```

Ensayo real de Windows con dos instalaciones ficticias, puertos 18220–18223 e imágenes locales ya construidas:

```powershell
python tools/verificar_traslado.py --ejecutar
```

Requiere Python solo en la PC de pruebas. La instalación habitual de Windows mediante `iniciar.cmd` no lo necesita. El ensayo no usa `.env` operativo, no consulta proveedores externos y retira sus contenedores, volúmenes y archivos temporales. Si ya existe un ensayo con esos nombres, se detiene para no modificarlo.

## Revision del 03/11/2026

Pasaron **6 pruebas unitarias del traslado**, **5 del diagnóstico** y el recorrido real de PowerShell entre dos proyectos Docker separados:

1. Inicio de dos instalaciones vacías desde carpetas con espacios, sin Git y con `.env` generado automáticamente.
2. Creación e ingreso del primer administrador protegido, más zona, oficina y equipo ficticios.
3. Copia de MongoDB y archivos sin incluir el `.env`.
4. Rechazo de un archivo alterado; restauración correcta de la cuenta principal, oficina, equipo y ticket. La foto y el adjunto conservaron su SHA-256.
5. Rechazo al intentar restaurar nuevamente sobre el destino ocupado.
6. Segundo arranque con conservación del `.env`, la cuenta y los registros.

El recorrido utilizó el script de Windows que emplea `iniciar.cmd`, bases y volúmenes propios e imágenes locales ya construidas. El antivirus estaba desactivado en el entorno ficticio; no se consultó ningún proveedor de IA. Al terminar se retiraron los servicios y archivos del ensayo. No se copiaron registros reales.

Se corrigieron la recuperación ante una parada parcialmente fallida y el intento de reanudación aunque falle la limpieza temporal. El diagnóstico ya no necesita una cuenta ficticia ni modifica preferencias o genera exportaciones. El iniciador de Windows conserva la ventana abierta si falla para que pueda leerse el error.

También se reconstruyeron API y worker y se comprobó el nuevo diagnóstico en la instalación local: API, MongoDB y Redis disponibles. Se revisaron sintaxis y enlaces de las guías.

La comprobación se limita al arranque y traslado en esta laptop. No sustituye una instalación física en la PC nueva: allí deben comprobarse Docker/WSL, espacio, memoria, puertos, permisos y descargas de todas las imágenes por primera vez. Tampoco certifica un dominio público. La revisión de vulnerabilidades se realiza aparte con las imágenes actuales; no se presenta un número histórico de alertas como si fuera un análisis nuevo.
