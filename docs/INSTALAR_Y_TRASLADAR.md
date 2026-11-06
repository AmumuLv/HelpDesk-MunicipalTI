# Instalar o trasladar el sistema sin enredarse

## Primero: elige qué quieres llevar

| Quiero… | Qué debo hacer |
| --- | --- |
| Empezar de nuevo, sin las cuentas ni los equipos anteriores | Sigue [los 6 pasos para una PC nueva](NUEVA_PC.md). **Esta es la opción que elegiste para la otra PC.** |
| Conservar cuentas, oficinas, inventario, tickets y archivos | Sigue «Llevar los datos actuales» más abajo. |
| Solo entrar desde otra computadora y ver los mismos datos | Abre la dirección del servidor existente. No necesitas instalar otra base de datos. |

**El ZIP de GitHub trae el programa. Un archivo de traslado lleva los datos. Son dos cosas diferentes.**

## Equipo nuevo, sin trasladar datos

Abre Docker Desktop → descarga el ZIP de GitHub → **Extraer todo** → abre **`iniciar.cmd`** → entra a **http://localhost** → crea el administrador principal.

El iniciador crea `.env` y su clave interna automáticamente. No tienes que copiar el `.env` de tu laptop ni instalar MongoDB a mano.

Consulta [la guía con cada clic explicado](NUEVA_PC.md) si es tu primera vez.

## Llevar los datos actuales a otro equipo

**Usa esta parte solo si quieres conservar la información anterior.** Necesitas el programa funcionando en ambas PC. El destino debe estar vacío: no crees allí la primera cuenta ni importes información antes de restaurar.

### A. En la PC anterior: crea el paquete de datos

1. Abre Docker Desktop y comprueba que puedes entrar al sistema.
2. Abre la carpeta del proyecto, donde está `iniciar.cmd`.
3. Pulsa la barra de direcciones de esa carpeta, escribe **`powershell`** y presiona Enter. Se abre una ventana situada en esa carpeta.
4. Copia esta línea completa y presiona Enter:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\trasladar.ps1 respaldar .\backups\municipalidad.helpdesk.zip
```

Espera a que termine. Durante la copia, la web deja de atender peticiones por un momento; la herramienta vuelve a iniciar los servicios al terminar o al intentar recuperarse de un error.

El archivo aparecerá dentro de **`backups`**, con el nombre **`municipalidad.helpdesk.zip`**. Si ya hay uno con ese nombre, usa otro nombre para no sobrescribirlo.

### B. Lleva el programa y el paquete

1. En la PC nueva, instala y abre Docker Desktop.
2. Descarga y extrae el programa, como se explica en [PC nueva](NUEVA_PC.md).
3. Ejecuta `iniciar.cmd` y espera a que termine.
4. **Todavía no crees un administrador.** Vas a recuperar las cuentas anteriores.
5. Copia `municipalidad.helpdesk.zip` a una carpeta llamada **`backups`** dentro del proyecto nuevo. Créala si no existe.

El paquete contiene información privada y hashes de contraseñas. Llévalo por un medio privado; no lo subas a GitHub ni lo publiques.

Si registraste licencias cifradas de software, TI también debe poner el mismo valor de **`LICENSE_ENCRYPTION_KEY` original** en el `.env` de destino por un medio privado y ejecutar `docker compose up -d api worker` para aplicar el cambio. La copia de datos no incluye esa clave. Sin ella no se podrán descifrar esas licencias. Para una instalación desde cero esto no es necesario.

### C. En la PC nueva: abre el paquete

Abre PowerShell desde la carpeta nueva, igual que en el paso A. Copia:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\trasladar.ps1 restaurar .\backups\municipalidad.helpdesk.zip
```

Cuando lo pida, escribe **`RESTAURAR`** en mayúsculas y presiona Enter.

La herramienta comprueba que el paquete no se haya alterado y que el destino esté vacío. Si encuentra datos anteriores, se detiene en lugar de mezclarlos.

### D. Comprueba antes de dejar de usar la PC anterior

Abre **http://localhost** en la PC nueva y revisa:

- Puedes iniciar sesión con tu **cuenta y contraseña anteriores**.
- Aparecen tus oficinas, trabajadores y equipos.
- Puedes abrir un ticket anterior.
- Se puede ver una foto y descargar un adjunto que ya existían.
- Al cerrar el navegador y volver a entrar, siguen los datos.

La cuenta principal conserva su protección. Las sesiones de navegador no se llevan: entra de nuevo. No borres la instalación anterior hasta comprobar el destino.

## ¿Qué se lleva y qué no?

| Contenido | ¿Viaja en el paquete de datos? |
| --- | --- |
| Cuentas, oficinas, equipos, tickets y conversaciones guardadas en MongoDB | Sí |
| Fotos, adjuntos y notas de voz del directorio de subidas | Sí |
| `.env`, claves del chatbot y clave de licencias | No; se configuran por separado |
| Caché y colas temporales de Redis | No |
| Exportaciones descargables que se pueden generar otra vez | No |

Esta herramienta está preparada para el MongoDB incluido en Docker y las subidas dentro de `/data/`. Si utilizas una base externa, TI debe preparar el traslado para esa base.

## El chatbot es opcional

Puedes usar el sistema sin una clave externa. Si quieres activar el chatbot, configura **`GROQ_API_KEY`** en el `.env` de la PC nueva, con la ayuda de TI. Después, desde la carpeta del proyecto, ejecuta:

```powershell
docker compose up -d api worker
```

Las claves no se escriben en GitHub ni se comparten en capturas. La [guía del chatbot](CHATBOT_TI.md) explica su funcionamiento.

## Comprobación para TI

Estos comandos consultan el estado sin crear usuarios ni modificar registros:

```powershell
docker compose ps
docker compose exec api python -m app.scripts.diagnostico
```

El diagnóstico comprueba API, MongoDB y Redis. También debes verificar la entrada a la web y los archivos con el navegador.

**No ejecutes `docker compose down -v` en la instalación real.** La opción `-v` elimina los volúmenes que guardan los datos.

## Actualizar el código

Si descargaste por ZIP, conserva la carpeta de instalación y su `.env`; TI debe reemplazar el código con la versión nueva sin cambiar las claves ni los volúmenes. Luego ejecuta `iniciar.cmd`. No instales versiones diferentes a la vez sobre los mismos datos.

Si utilizas Git, ejecuta desde la carpeta del proyecto:

```powershell
git pull --ff-only
.\iniciar.cmd
```

En una instalación con información importante, prepara antes una copia privada de traslado. No hace falta copiar datos para una instalación nueva que empezará vacía.

## Publicación y secretos

Instalar el programa no publica la web en Internet. Para entrar desde casa u otra red hacen falta el servidor encendido, la conexión, el dominio y HTTPS configurados. `localhost` solo abre la PC donde estás.

La configuración pública y los comandos para TI están en [Referencia técnica de instalación](INSTALACION_TECNICA.md). MongoDB y Redis no se abren a Internet.

## Revisión del traslado del 03/11/2026

El ensayo se realiza con instalaciones ficticias separadas, sin copiar ni alterar la información operativa. Los resultados y sus límites se detallan en la [referencia técnica](INSTALACION_TECNICA.md#revision-del-03112026).
