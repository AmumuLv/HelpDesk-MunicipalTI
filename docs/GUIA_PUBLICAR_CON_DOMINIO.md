# Publicar tu mesa de ayuda, paso a paso

Municipalidad Provincial de Casma · HelpDesk-MunicipalTI

Guía preparada el 07/11/2026 para alojar el sistema en una computadora de la municipalidad y acceder desde cualquier lugar mediante un dominio y Cloudflare Tunnel. Los ejemplos de dominio no representan una compra ni disponibilidad confirmada.

## Qué vas a conseguir

Un trabajador podrá entrar desde su oficina, su casa o su celular escribiendo una dirección como https://mesa.soporteticasma.com. Verá el inicio de sesión y utilizará las funciones permitidas para su cuenta.

El recorrido será: navegador de la persona → dominio y Cloudflare → túnel → computadora de la municipalidad → sistema y base de datos.

La información continuará guardándose en la computadora que aloja el sistema. Comprar el dominio no mueve los datos a Cloudflare ni sustituye una copia de seguridad.

## 1. Qué comprar y qué necesitas tener

| Elemento | Qué hacer |
| --- | --- |
| Dominio propio | Comprar un nombre aprobado por la institución y revisar su renovación. |
| Computadora para alojar la web | Usar la computadora prevista, después de comprobar su capacidad y espacio. |
| Internet y electricidad | Mantenerlos disponibles mientras se utilice la web. |
| Cloudflare | Crear la cuenta y comenzar con la opción gratuita disponible; revisar sus condiciones al contratar. |
| Hosting o servidor alquilado | No se necesita inicialmente para este montaje. |
| IP pública fija contratada | No se necesita para esta opción con túnel. |
| Certificado HTTPS comprado aparte | No se necesita para el dominio y subdominio del ejemplo con Universal SSL. |
| MongoDB Atlas | No es necesario contratarlo para utilizar la base de datos local en Docker. |
| UPS y destino de copias | Recomendables para reducir el impacto de cortes eléctricos y fallos del disco. |

Una IP es una dirección de red. Con el túnel no tendrás que indicar la IP de tu casa ni autorizar una por una las computadoras de los trabajadores. La computadora del servidor sí necesita una conexión a Internet que permita funcionar al conector.

Para un servicio institucional, conserva la titularidad del dominio, el correo de recuperación y las credenciales bajo responsabilidad de la municipalidad.

## 2. Compra el dominio

1. Entra a Cloudflare Registrar: https://www.cloudflare.com/products/registrar/.
2. Crea una cuenta con el correo que conservará la institución y confirma ese correo.
3. Activa la verificación en dos pasos y guarda sus códigos de recuperación.
4. Busca el nombre elegido. Ejemplo: soporteticasma.com. Si está ocupado, elige otro nombre autorizado.
5. Revisa el precio del primer año y el de renovación. El importe definitivo es el que muestra el proveedor antes de pagar.
6. Compra el dominio por el periodo elegido y completa la confirmación del correo del titular.
7. Registra quién lo administra y cuándo vence. Si activas renovación automática, conserva un medio de pago vigente.

Si compras el dominio directamente en Cloudflare, utiliza su gestión de DNS. Para esta guía se usará un subdominio de un solo nivel: mesa.TU-DOMINIO.com. No compres otro dominio para añadir «mesa».

## 3. Prepara la computadora de la municipalidad

1. Instala Docker Desktop y completa los requisitos que solicite Windows.
2. Descarga el proyecto desde el GitHub privado y extrae el ZIP. Entra hasta la carpeta que contiene iniciar.cmd y docker-compose.yml.
3. Ejecuta iniciar.cmd. Espera a que termine la preparación; la primera instalación puede tardar.
4. Comprueba la web en http://127.0.0.1:8080 desde esa misma computadora. Esta es la dirección local que utilizaremos para el túnel, si conservas el puerto predeterminado.
5. Si empiezas sin datos, crea la primera cuenta desde la preparación inicial, antes de hacer pública la dirección. Esa cuenta será el administrador principal. Si ya tienes cuentas y datos, consérvalos.
6. Desactiva la suspensión automática y comprueba el espacio libre y la conexión a Internet.

La guía de instalación detallada está en docs/NUEVA_PC.md. No copies el .env en mensajes ni lo subas a GitHub. No borres los volúmenes de Docker: contienen los datos persistentes.

Docker Desktop suele depender del inicio de sesión de Windows. Marcar «iniciar con Windows» no demuestra que el sistema funcione sin intervención tras un reinicio. Comprueba ese caso; si exige abrir una sesión manualmente, TI debe resolver el arranque o preparar un entorno de servidor apropiado antes de ofrecer atención permanente.

## 4. Crea la conexión con Cloudflare Tunnel

Este procedimiento instala cloudflared directamente en Windows, en la misma computadora donde funciona Docker. No instala una VPN en los equipos de los trabajadores.

1. Entra al panel de Cloudflare con la cuenta que administra el dominio.
2. Busca Networking → Tunnels. El panel puede presentar nombres distintos al actualizarse; utiliza la guía oficial de creación de túneles si cambia el menú.
3. Selecciona Create tunnel y el conector Cloudflared.
4. Escribe un nombre, por ejemplo helpdesk-casma.
5. Selecciona Windows y sigue las instrucciones de descarga e instalación del conector.
6. Abre PowerShell como administrador en la computadora del servidor y ejecuta el comando de instalación del servicio que te muestre Cloudflare.
7. Espera a que el túnel aparezca conectado o saludable.

Ese comando contiene una credencial del túnel. Guárdala de forma privada. Si no conecta, pide a TI revisar la conectividad de salida requerida por cloudflared; no desactives el firewall para intentar solucionarlo.

## 5. Une el dominio con tu página

En las rutas del túnel selecciona Add route → Published application. Completa estos campos:

| Campo | Qué escribir |
| --- | --- |
| Subdominio | mesa |
| Dominio | El dominio que realmente compraste. |
| Path o ruta | Vacío. |
| Tipo del servicio | HTTP |
| Dirección del servicio | 127.0.0.1:8080 |

Guarda la ruta. La dirección pública será https://mesa.TU-DOMINIO.com. Cloudflare crea el registro DNS correspondiente al publicar la ruta. Espera a que el dominio y el certificado estén activos.

HTTP en la dirección local no significa que los trabajadores deban navegar sin HTTPS: el navegador utiliza HTTPS hacia Cloudflare y el túnel transporta el tráfico hasta el conector. El último tramo es local a la misma computadora.

Utiliza una ruta de aplicación pública. No necesitas una ruta de red privada ni instalar WARP en los celulares y computadoras de los trabajadores.

Si cambiaste WEB_PORT, sustituye 8080 por el puerto real. Si instalas cloudflared dentro de Docker o en otra computadora, 127.0.0.1 ya no representa este mismo destino: hay que adaptar la dirección antes de continuar. No conectes el túnel directamente al puerto de MongoDB.

## 6. Configura el dominio en el proyecto

En el .env de la computadora del servidor modifica solamente estas variables. Sustituye el dominio de ejemplo por el tuyo, exactamente igual al publicado en Cloudflare:

```env
CORS_ORIGINS=https://mesa.TU-DOMINIO.com
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

Conserva las claves internas, contraseñas y demás configuración existente. Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
docker compose up -d --force-recreate api worker
docker compose ps
```

Este procedimiento usa Nginx por el puerto local 8080. No combines estos pasos con el modo de publicación directa que solicita certificados mediante puertos abiertos del router. No necesitas activar otro montaje público para que funcione este túnel.

En Cloudflare comprueba que el certificado esté activo y habilita Always Use HTTPS para que las visitas por HTTP pasen a HTTPS. Después inicia sesión por la dirección pública HTTPS; con cookies seguras, el acceso local por HTTP deja de ser la referencia para comprobar el inicio de sesión.

Mantén la política normal de caché: no actives una regla de «guardar todo en caché» sobre /api, sesiones, archivos privados o conversaciones.

## 7. Haz las pruebas con el dominio real

Primero usa tu celular con datos móviles y el Wi-Fi apagado. Así verificas que no estás entrando solamente por la red de la municipalidad. Utiliza cuentas y registros ficticios identificados como pruebas.

| Prueba | Qué debe ocurrir | Resultado / fecha |
| --- | --- | --- |
| Abrir el dominio desde datos móviles | Aparece el inicio de sesión mediante HTTPS, sin aviso de certificado. | Pendiente |
| Acceder desde casa | Abre sin VPN y permite entrar con una cuenta autorizada. | Pendiente |
| Usuario, técnico, administrador y principal | Cada cuenta ve y utiliza solo lo permitido para ella. | Pendiente |
| Crear y atender un ticket ficticio | Se conserva reportante, persona u oficina afectada y seguimiento correcto. | Pendiente |
| Dos cuentas abiertas | Mensajes y cambios previstos aparecen sin recargar. | Pendiente |
| Fotos y adjuntos | Se cargan y descargan respetando los permisos. | Pendiente |
| Reportes e inventario | Los filtros y las exportaciones muestran los datos correctos. | Pendiente |
| IA interna y chatbot | Responden según sus permisos; el chatbot respeta su proveedor y límites. | Pendiente |
| Varias cuentas a la vez | Las acciones responden sin errores ni duplicados; se registran los tiempos. | Pendiente |
| Cerrar sesión | La cuenta pierde el acceso y puede volver a entrar correctamente. | Pendiente |
| Reiniciar la computadora | Docker, el sistema y el túnel recuperan el servicio sin intervención manual. | Pendiente |
| Corte breve de Internet controlado | Al recuperarse la conexión, la página y las conversaciones se reconectan. | Pendiente |
| Copia y restauración aislada | Una copia se restaura en una base de pruebas y conserva datos y archivos. | Pendiente |

Anota lo que falla, la cuenta utilizada y la hora. Corrige y repite el caso antes de darlo por aprobado. Las pruebas destructivas o de restauración deben hacerse aisladas de la base operativa. No elimines datos reales para comprobar botones.

## 8. Haz un piloto y decide el lanzamiento

1. Cierra la evaluación de seguridad pendiente. El dominio y HTTPS no corrigen por sí solos los avisos de bibliotecas.
2. Invita a un grupo pequeño de trabajadores y técnicos para un piloto de varios días.
3. Registra dificultades de uso, errores y tiempos de respuesta con la computadora definitiva.
4. Corrige los problemas y repite los recorridos afectados.
5. Define quién administra cuentas, atiende incidentes, recibe alertas y revisa las copias de seguridad.
6. Confirma con el responsable de TI que las pruebas aprobaron y autoriza la difusión de la dirección.

El historial técnico de la revisión local está en docs/REVISION_INTEGRAL_2026_11_07.md. Las pruebas de esta guía quedan pendientes hasta ejecutarlas en el dominio y la computadora definitiva; no representan una publicación ya realizada.

## 9. Qué cuidar después del lanzamiento

| Frecuencia | Actividad |
| --- | --- |
| Cada día de operación | Comprobar que abre la web, revisar avisos de errores y confirmar la copia prevista. |
| Periódicamente | Revisar espacio libre, actualizaciones de seguridad, cuentas activas y funcionamiento del antivirus. |
| Después de un cambio importante | Probar los recorridos afectados y registrar versión, fecha y responsable. |
| Según el plan de recuperación | Restaurar una copia en un entorno aislado y comprobar su utilidad. |
| Antes del vencimiento | Renovar el dominio y comprobar el correo y medio de pago. |

Define con TI cuánto tiempo de información se puede perder y cuánto puede durar una interrupción; esos objetivos determinan la frecuencia y conservación de las copias. Conserva al menos una copia protegida fuera del disco de la computadora que aloja el sistema.

Si se apaga esa computadora o se pierde su Internet, la web no estará disponible desde fuera. El dominio no sustituye el servidor ni ofrece continuidad por sí solo.

## Si algo no funciona

| Lo que ves | Qué revisar primero |
| --- | --- |
| No abre ni en 127.0.0.1:8080 | Docker, estado de los servicios y puerto local configurado. |
| Abre localmente, pero Cloudflare indica error 502 | Túnel conectado, servicio HTTP y destino 127.0.0.1:8080. |
| El dominio no existe o no tiene certificado | Dominio activo, correo del titular confirmado, ruta DNS y certificado activo. |
| La sesión no se mantiene | Dominio exacto en CORS_ORIGINS, HTTPS, cookies seguras y recreación de API/worker. |
| No llegan cambios o mensajes | Conexión del navegador, WebSocket, API y ruta del túnel; registrar el error para TI. |
| Funciona hasta reiniciar Windows | Arranque real de Docker y del servicio cloudflared, incluso antes de abrir sesión. |

## Ficha de entrega

| Dato | Completar |
| --- | --- |
| Dominio comprado y dirección final | __________________________________ |
| Responsable del dominio y correo institucional | __________________________________ |
| Vencimiento y renovación | __________________________________ |
| Computadora y ubicación del servidor | __________________________________ |
| Nombre del túnel | __________________________________ |
| Responsable de operación y copias | __________________________________ |
| Fecha y resultado del piloto | __________________________________ |
| Versión del proyecto y autorización de lanzamiento | __________________________________ |

Esta ficha no debe contener contraseñas, claves de IA ni la credencial del túnel.

## Fuentes y ayuda

- [Registrar un dominio en Cloudflare](https://developers.cloudflare.com/registrar/get-started/register-domain/).
- [Cómo funciona Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/concepts/).
- [Crear un túnel y publicar una aplicación](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/).
- [Certificados gratuitos Universal SSL](https://developers.cloudflare.com/ssl/edge-certificates/universal-ssl/).

Los nombres de los menús, precios y condiciones pueden cambiar. Consulta el panel del proveedor al comprar y configurar.
