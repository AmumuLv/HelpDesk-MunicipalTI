# Preparar otra PC

El repositorio privado contiene el programa, las pruebas automáticas y las instrucciones. No contiene `.env`, contraseñas, cuentas, inventario, fotos ni adjuntos de la instalación actual.

## 1. Preparar Windows

- Instala Git y Docker Desktop con Docker Compose y WSL 2.
- Abre Docker Desktop y espera a que el motor esté disponible.
- Ten acceso al repositorio con tu cuenta autorizada de GitHub. No pegues tokens en los comandos ni en archivos del proyecto.
- Necesitas Internet para descargar y compilar las imágenes. La primera instalación puede tardar bastante; incluye compilaciones y comprobaciones de seguridad.

## 2. Descargar e iniciar

En PowerShell:

```powershell
git clone https://github.com/AmumuLv/HelpDesk-MunicipalTI.git
cd HelpDesk-MunicipalTI
.\iniciar.cmd
```

El iniciador crea `.env` con una clave aleatoria y levanta Docker. Si falla una descarga, corrige la conexión y vuelve a ejecutar `iniciar.cmd`; conserva `.env` y los volúmenes existentes.

Abre `http://localhost`.

## 3. Elegir cómo empezar

**Instalación nueva:** crea el administrador desde `http://localhost/instalacion`. Esa primera cuenta es el administrador principal protegido y autoriza los siguientes administradores. La base estará vacía. Consulta [Roles y permisos](ROLES_Y_PERMISOS.md).

**Conservar la información actual:** no crees el administrador ni registres datos en el destino. Sigue [Llevar los datos actuales a otro equipo](INSTALAR_Y_TRASLADAR.md#llevar-los-datos-actuales-a-otro-equipo). Esa operación incluye cuentas, inventario y adjuntos, y requiere un archivo privado fuera de GitHub. No copies las carpetas internas de Docker mientras MongoDB esté funcionando.

Configura las claves del chatbot directamente en el `.env` de destino. Si hay licencias cifradas, necesitas conservar también el `LICENSE_ENCRYPTION_KEY` original por un medio privado. Después de configurar el entorno:

```powershell
docker compose up -d api worker
```

El sistema puede funcionar sin clave del chatbot. Nunca publiques `.env` ni lo adjuntes a una incidencia de GitHub.

## 4. Comprobar el destino

```powershell
docker compose ps
docker compose exec api python -m app.scripts.diagnostico
```

Comprueba el inicio de sesión y, si restauraste información, que aparezcan tus registros y se puedan abrir sus fotos y adjuntos. Conserva la instalación de origen hasta validar el destino. No uses `docker compose down -v`: elimina los volúmenes.

Dos instalaciones locales tienen datos independientes. Para que todas las personas trabajen con la misma información deben abrir la web de un único servidor; GitHub no sincroniza las bases de datos.

## Acceso desde fuera de la PC

Esta preparación permite instalar y utilizar la web localmente. Para Internet faltan el dominio, la configuración de acceso al servidor y la validación de HTTPS real: sigue [Publicación y secretos](INSTALAR_Y_TRASLADAR.md#publicación-y-secretos). No abras MongoDB ni Redis a Internet.

La revisión de seguridad del 29/10/2026 y sus seis alertas altas brutas restantes están documentadas en la guía de instalación. Los parches se incluyen en el código de construcción; una instalación nueva debe completar esas compilaciones y verificaciones. El resultado de ese análisis no garantiza que no aparezcan avisos nuevos.
