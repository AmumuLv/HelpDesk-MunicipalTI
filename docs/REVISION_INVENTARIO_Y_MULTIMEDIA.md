# Inventario y chat — 16/10/2026

- Oficinas: fecha de creación descendente, con identificador como desempate.
- Inventario anual: pantalla de archivos y comparativas; se retira el acceso a campañas físicas. Sus datos y API se conservan para no perder versiones anteriores.
- Importación anual: la nueva versión entra inmediatamente en la caché. Ante un fallo de conexión o respuesta del servidor, se comprueba año y SHA-256 para reconocer un archivo ya guardado sin duplicarlo ni exigir recargar. Los errores de validación se mantienen visibles.
- Equipos: presentación por defecto; edición explícita, confirmación al descartar y vuelta a presentación después de guardar. Los controles de disponibilidad y edición avanzada quedan en edición.
- Chat de usuarios y soporte: fotos, archivos de audio y grabación de voz; hasta cinco adjuntos por mensaje, 15 MB cada uno. Grabaciones de hasta dos minutos. El micrófono requiere permiso y HTTPS o localhost; sigue disponible adjuntar un audio.
- Los archivos se descargan mediante peticiones autenticadas y se visualizan con URLs temporales. Se comprueba propiedad antes de vincularlos al mensaje; no se admite reutilizar archivos de otro mensaje o de otra cuenta.

Validación: pruebas de servidor sobre autorización, adjuntos sin texto, firmas de archivos y orden de oficinas; pruebas de navegador sobre recuperación de importación, separación de presentación y edición, grabación, reproducción, persistencia y recepción por soporte. Se simula una pérdida de respuesta después del guardado y un micrófono de Chromium; no se requiere hardware de grabación para la prueba.
