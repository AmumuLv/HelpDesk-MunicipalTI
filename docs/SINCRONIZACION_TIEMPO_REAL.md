# Actualización entre cuentas abiertas

La API observa las escrituras confirmadas del replica set de MongoDB mediante un change stream. Así también detecta importaciones, cambios masivos y escrituras del worker, sin depender de que cada formulario emita su propio aviso.

Los cambios se agrupan durante 200 ms y se publican en Redis. El WebSocket autenticado de cada sesión recibe solo los dominios que debe refrescar y, cuando corresponde, los identificadores de fotos a invalidar. No se transmiten documentos, nombres, contraseñas, contenidos de tickets ni datos de auditoría por el canal común. Cada consulta HTTP vuelve a aplicar los permisos de la cuenta.

Se actualizan tickets, inventario, conjuntos, usuarios, oficinas, zonas, perfiles, fotos, horarios, ausencias, conocimiento, configuración, importaciones, inventarios anuales y reportes. Las notificaciones personales siguen llegando solo a sus destinatarios. Los cambios de foto eliminan el blob anterior del caché para descargar la versión vigente.

La interfaz agrupa los avisos y limita los refrescos a una tanda cada 800 ms. Solo consulta pantallas observadas; las consultas inactivas quedan pendientes para la próxima visita. No genera nuevas respuestas del chatbot ni borra conversaciones, filtros, mensajes en redacción o formularios modificados.

Cada conexión recibe un aviso de sincronización después de suscribirse y un latido cada 20 segundos sin actividad. Si se interrumpe, reconecta con espera progresiva y recupera el estado actual, incluidas las fotos. Al volver a una pestaña también recupera los cambios. Mientras el socket está desconectado, una pestaña visible comprueba los datos cada 15 segundos. Sin red no puede recibir cambios; se recuperan al restablecerse la conexión.

Los contadores internos de lectura de artículos y la actividad técnica de las sesiones no generan cascadas de refrescos. Se conserva el registro original de movimientos.

Requiere MongoDB en replica set y Redis, ya incluidos en Docker Compose. El observador se inicia con la API después de las migraciones y se cancela al apagarla. Si pierde MongoDB o Redis, reintenta y emite una sincronización completa al recuperarse.
