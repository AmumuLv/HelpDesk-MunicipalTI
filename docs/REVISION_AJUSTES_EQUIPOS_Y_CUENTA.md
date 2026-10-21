# Ajustes de resumen, equipos y cuenta

- «Necesitan atención ya» utiliza DataTable y el formato de identificación, persona, ubicación, estado/prioridad y SLA de Tickets.
- Se distingue el número del conjunto del número individual de cada equipo. Al registrar se muestran el número previsto, la cantidad actual y la cantidad resultante; por ejemplo, tres equipos registrados y cuatro al guardar.
- Cada equipo conserva `numero_equipo`. Un contador atómico por conjunto impide reservar números duplicados. El número definitivo se asigna al guardar; si otra persona registra antes, puede variar respecto de la previsión. Cambiar datos dentro del mismo conjunto conserva el número; trasladar a otro conjunto asigna uno de ese destino.
- La migración numera los componentes anteriores en orden de creación e identificador, conserva números existentes y añade una restricción de unicidad. Los números reservados no se reutilizan al retirar equipos.
- La ficha muestra el número individual y los números de los demás componentes, sin volver a repetir el nombre del equipo actual.
- Cabecera y menú de cuenta usan AvatarCuenta, con la misma foto autenticada que Mi perfil. Subir o quitar una foto actualiza también el perfil consultado por estos avatares.
- El título de la zona vuelve a ser «Resumen de zona» y la tarjeta mantiene el nombre real, como COMPLEJO.
- La oficina es un enlace en el encabezado, tarjeta y datos de la ficha de equipo.
- Al abrir una notificación se refrescan el ticket y su conversación, incluso cuando ya se está viendo esa misma ruta.

Pruebas: tres equipos existentes → alta del cuarto → consulta y edición conservando N°4; migración repetible y asignaciones concurrentes; integración del importador; registro desde navegador hasta la ficha y enlace a oficina; foto cargada en cabecera y menú; contraste y recorridos de usuarios, notificaciones y chat.
