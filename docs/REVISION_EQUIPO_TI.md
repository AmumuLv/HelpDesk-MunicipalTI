# Equipo TI — revisión del 14 de octubre de 2026

## Jornada y datos compartidos

El horario inicial es lunes a viernes de 08:00 a 13:00 y de 14:00 a 17:00: ocho horas laborables, con una hora de descanso. Sábado y domingo son no laborables. El índice interno es 0 = lunes y 6 = domingo. No se añaden feriados entre semana automáticamente.

La cuenta de Usuarios es la fuente de nombre, foto, correo, teléfono, anexo, cargo, oficina y zona. La lista de Equipo TI y el perfil técnico usan esos mismos datos; no mantienen una segunda copia de contacto. Las modificaciones y fotos invalidan también las consultas de Equipo TI.

La migración 018 corrige los horarios iniciales antiguos (semana desplazada o tarde de 15:00 a 18:00), completa los perfiles TI faltantes y guarda el horario previo. Los horarios personalizados se conservan. El editor permite revisar un integrante cada vez, aplicar el horario base y guardar con validación de horas y solapamientos.

## Disponibilidad y ausencias

- «Ausentes hoy» cuenta ausencias registradas, sin confundirlas con trabajo en curso, espera o fuera de horario.
- Las 13:00 y las 17:00 son límites de salida; a esas horas el integrante deja de estar dentro del turno. Una ausencia prevalece sobre la disponibilidad.
- Una ausencia incluye el día inicial y el final. La API comprueba el destinatario, los permisos, el orden de fechas y las coincidencias con otra ausencia.
- El registro y la eliminación actualizan lista, perfil, disponibilidad y calendario. La eliminación pide confirmación.
- El cálculo de horas recorta cada ausencia al periodo consultado, excluye días no laborables y no descuenta dos veces una jornada aunque haya datos antiguos solapados.
- Las ausencias afectan la disponibilidad y las horas disponibles del técnico; los tickets asignados se conservan. El SLA de los tickets sigue el calendario institucional, no una pausa automática por ausencia personal.

## Calendario y perfil

La lista de treinta días repetidos se reemplaza por una semana navegable, de lunes a domingo, con filtro por persona. Cada día muestra turnos, horas disponibles, ausencia o día no laborable y los tickets abiertos con vencimiento en esa fecha local. Los pendientes junto al nombre son la carga actual, no una predicción futura. Los tickets cerrados o eliminados no cuentan como pendientes.

El perfil TI tiene pestañas Resumen, Trabajo pendiente, Horario, Ausencias y Calendario. Los datos esenciales y la foto están en el resumen; el enlace a Usuarios permite gestionar la información personal según permisos. La cola de trabajo se pagina de diez en diez.

## Pruebas

Se verifican quince pruebas de API: cinco nuevas de Equipo TI, tres de disponibilidad/asignación/ausencias, seis de SLA y una regresión del horario inicial de Usuarios. La migración incluye pruebas de conservación de horarios personalizados y creación de perfiles faltantes.

`frontend/pruebas/equipo-ti-flujos.spec.ts` recorre contra la web compilada de demostración:

1. Alta de un técnico y actualización de cargo/foto desde Usuarios.
2. Lectura de los mismos datos y foto en Equipo TI.
3. Edición de lunes, guardado y lectura desde la otra vista de horarios.
4. Aplicación del horario base con fin de semana no laborable.
5. Registro de una ausencia, cambio de disponibilidad y reflejo en el calendario.
6. Navegación semanal, eliminación confirmada y recálculo de disponibilidad.
7. Revisión en escritorio y móvil sin desbordamiento horizontal.

La API usa bases aisladas que se eliminan al terminar; el navegador usa cuentas de demostración que se desactivan al finalizar.

Capturas: [Perfil](capturas/equipo-ti-perfil.png), [Calendario](capturas/equipo-ti-calendario.png), [Horario móvil](capturas/equipo-ti-horario-movil.png).

Resultado: pasaron las quince pruebas de API seleccionadas, la repetición de la migración con un perfil faltante y las dos pruebas de navegador contra Nginx (Equipo TI y regresión de Usuarios). ESLint y la compilación con TypeScript y Vite pasaron. La API, el proceso de tareas y la web del entorno principal se actualizaron con la misma revisión.
