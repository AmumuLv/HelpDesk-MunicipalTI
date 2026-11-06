# Poner tu sistema en otra PC, paso a paso

**Esta es la opción que elegiste: empezar desde cero, sin llevar los datos de tu laptop.**

Piensa en esto así: vas a llevar **el programa**, como si llevaras un cuaderno nuevo. Los nombres, equipos y tickets de la PC anterior no vienen escritos dentro.

## 1. Abre Docker

En la PC nueva, instala **Docker Desktop** si todavía no lo tiene. Ábrelo y espera a que indique que está funcionando.

Si te pide reiniciar Windows o activar WSL 2, completa lo que te indique y abre Docker otra vez. Necesitas Internet durante la instalación.

## 2. Descarga el programa

1. Entra al [repositorio privado del proyecto](https://github.com/AmumuLv/HelpDesk-MunicipalTI) con tu cuenta de GitHub autorizada.
2. Pulsa **Code → Download ZIP**.
3. Busca el ZIP descargado. Haz clic derecho → **Extraer todo**.
4. Abre la carpeta que se creó. Si hay otra carpeta dentro, entra hasta encontrar **`iniciar.cmd`** y **`docker-compose.yml`**.

**No ejecutes el programa dentro del ZIP.** Primero debes extraerlo. No necesitas instalar Git, Python, Node ni MongoDB por separado para este método en Windows.

## 3. Abre `iniciar.cmd`

Haz doble clic en **`iniciar.cmd`**. Se abrirá una ventana que prepara el programa.

- Deja Docker abierto.
- Espera sin cerrar esa ventana. La primera vez tarda más porque descarga y construye las piezas del sistema y prepara el antivirus.
- El archivo **`.env` se crea solo**. También se genera sola la clave interna del sistema.
- Si aparece un error, la ventana queda abierta para que puedas leerlo.

No tienes que «subir» la carpeta a Docker. **Este archivo hace la preparación por ti.**

## 4. Abre la página

Cuando termine, abre Chrome o Edge y escribe arriba, en la barra de direcciones:

**http://localhost**

Si esa dirección no abre, prueba **http://localhost:8080**. Si tampoco abre, revisa la ayuda de abajo.

## 5. Crea tu primera cuenta

En una instalación vacía aparecerá la preparación inicial. Si necesitas abrirla directamente, entra a:

**http://localhost/instalacion**

Si abriste la web con el puerto 8080, usa **http://localhost:8080/instalacion**.

Escribe el nombre, correo y contraseña de la persona responsable. **Esa será la cuenta de administrador principal.** No hay una contraseña de fábrica ni una cuenta anterior que debas usar.

Después podrás crear oficinas, trabajadores, técnicos e importar tu inventario.

## 6. Comprueba que quedó bien

- Puedes entrar con la cuenta que acabas de crear.
- Puedes cerrar sesión y volver a entrar.
- Al cerrar y volver a abrir el navegador, tu cuenta sigue existiendo.

**Ya puedes empezar.** El chatbot se configura después si quieres utilizarlo; no necesitas su clave para entrar o registrar información.

## Otro día, ¿cómo lo abro?

Abre **Docker Desktop**, espera a que esté listo y entra a **http://localhost**. Los servicios están configurados para reiniciarse con Docker. Si la página no abre, ejecuta otra vez **`iniciar.cmd`**.

Apagar la PC o cerrar el navegador no borra tus datos. No uses opciones de Docker para borrar los volúmenes: allí está guardada la información.

## Si algo sale mal

| Lo que ves | Qué hacer |
| --- | --- |
| Docker no está iniciado o dice que no puede conectar | Abre Docker Desktop y espera antes de repetir `iniciar.cmd`. |
| Error de descarga, conexión o tiempo de espera | Revisa Internet y vuelve a abrir `iniciar.cmd`. No borres `.env` para intentarlo otra vez. |
| «Puerto ocupado», «port is already allocated» o «address already in use» | Otra aplicación usa un puerto necesario. Conserva el mensaje y pide a TI que libere ese puerto o ajuste la instalación. |
| La página pide una cuenta que ya existe en lugar de crear la primera | Esa PC ya tiene una instalación con datos. No borres nada: pide a TI que revise cuál instalación se está abriendo. |
| No aparece `iniciar.cmd` | Entra a la carpeta extraída correcta. Windows puede mostrarlo solo como `iniciar`, de tipo archivo de comandos. |

## Dos cosas para recordar

**Instalarlo en otra PC no sincroniza las dos.** Cada instalación tiene sus propios datos. Para trabajar todos con la misma información, todos deben entrar a la dirección de un mismo servidor.

**`localhost` significa «esta misma PC».** La dirección para entrar desde tu casa o desde otras computadoras se configura después con el servidor, el dominio y HTTPS.

¿Quieres llevar también las cuentas y archivos anteriores? Sigue la [guía de traslado con datos](INSTALAR_Y_TRASLADAR.md#llevar-los-datos-actuales-a-otro-equipo). Es un camino diferente: no crees una cuenta nueva antes de restaurar.
