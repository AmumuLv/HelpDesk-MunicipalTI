# Usuarios, permisos, SLA y audio — 16/10/2026

- Alta de usuarios: vista previa de la cuenta y bloques de datos personales, acceso y ubicación; se conservan validación, permisos y contrato de creación.
- Permisos: dos personas por página, búsqueda y conservación de cambios pendientes al navegar entre páginas.
- SLA: edición independiente por prioridad, días y tramos de atención y pausa fuera de horario. Validación en interfaz y API de plazos positivos, prioridades únicas, resolución posterior a respuesta y horarios sin solapamientos. Los tiempos por prioridad se aplican a tickets nuevos.
- Audio: selección de entrada, permiso explícito, medidor de señal, ganancia automática y procesamiento del micrófono. Se impide adjuntar una grabación que no contenga señal. Se liberan las pistas y el contexto de audio al detener o abandonar la vista. Una pausa al hablar no se muestra como fallo si ya se detectó sonido.
- Notificaciones: filtros Todas/Sin leer, cinco avisos por página, actualización, lectura individual sin navegación y marcado general. La caché distingue filtros y se invalida tras marcar lecturas.

Pruebas: creación y edición de cuentas; conservación de permisos entre páginas; SLA persistido y validación de errores, incluidos plazos calculados por el servicio; notificaciones filtradas y paginadas; chat y campana reales. En audio se usa un micrófono simulado de Chromium: además de reproducir, se decodifica el archivo y comprueba amplitud distinta de cero. Otra prueba simula una entrada silenciosa y verifica que no se adjunte. Estas pruebas no comprueban el micrófono físico del usuario ni sus ajustes del sistema operativo.
