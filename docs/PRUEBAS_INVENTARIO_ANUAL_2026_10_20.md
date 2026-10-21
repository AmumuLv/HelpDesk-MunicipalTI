# Revisión funcional del inventario anual · 20/10/2026

**Resultado final: 38 pruebas de servidor y 6 recorridos de navegador aprobados.**
También se completaron la comprobación de tipos y la compilación de producción.
La limitación de eliminación directa del archivo anual se detalla más abajo.

## Alcance y aislamiento

Se revisó la pantalla actual **Equipos > Inventario anual**, el archivo independiente
por año, la comparación y las rutas de campañas relacionadas con descarga y borrado.
Las pruebas usaron MongoDB, Redis y una API temporales separados de producción.
Los registros de equipos, usuarios y archivos reales no se utilizaron para las pruebas.

## Comprobaciones

| Función | Cobertura |
| --- | --- |
| Registrar Excel | Primera carga, varias revisiones, conservación de cada versión y no modificación del inventario operativo. |
| Registrar CSV | Zona obligatoria, lectura UTF-8, repetición del mismo archivo y corrección de la zona. |
| Validación | Archivos vacíos, dañados, sin equipos o área; años fuera de 2000–2100; patrimonio duplicado; IP inválida o repetida; MAC inválida. |
| Evitar duplicados | Doble clic desde el navegador y peticiones concurrentes al servidor. |
| Recuperación de errores | Rechazo visible con posibilidad de reintento; pérdida de la respuesta después de guardar, tanto Excel como CSV. |
| Consultar versiones | Selección de años y revisiones anteriores, recarga, búsqueda por nombre y patrimonio. |
| Paginación | Más de 25 equipos, avance y retroceso; páginas fuera del rango; búsqueda sin coincidencias. |
| Descargar | Plantilla e inventario guardado; archivos Excel válidos y con sus hojas y datos históricos. |
| Comparar | Altas, ausencias en el destino, traslados, cambios de datos y responsables, sin cambios y revisión más reciente de cada año. |
| Validar comparación | Origen anterior al destino, años faltantes y actualización al cargar otra revisión del mismo año. |
| Permisos | Administrador; denegación a usuario y técnico sin permiso; técnico delegado; autenticación y CSRF en el registro. |
| Presentación | Sin desbordamiento horizontal a 320, 820 y 1440 px, con temas claro y oscuro. |
| Borrar campañas | Campaña abierta/cerrada, inexistente y limpieza del histórico asociado; el inventario operativo se conserva. |

## Fallos encontrados y corregidos

1. **Comparación desactualizada:** registrar una revisión no invalidaba expresamente
   la consulta de comparación. Sin WebSocket podía seguir apareciendo la revisión
   anterior. Ahora se refrescan las comparaciones después del guardado.
2. **Zona corregida de CSV ignorada:** la huella solo consideraba el archivo. Como
   la zona se suministra aparte, cambiarla podía devolver el archivo anterior.
   La identidad de una carga CSV ahora incluye la zona. Se conserva compatibilidad
   con archivos anteriores y se verifica la zona al recuperar respuestas perdidas.
3. **Aviso de error sin anuncio accesible:** el error se veía, pero no se anunciaba
   como alerta. Ahora el mensaje de rechazo tiene `role="alert"`.
4. El campo de zona del CSV queda bloqueado durante el guardado para mantener
   coherencia con el archivo enviado.

## Limitación confirmada: eliminación del archivo anual

**La pantalla actual no tiene un botón ni una ruta para eliminar directamente una
versión de archivo anual.** Esto no se presenta como una prueba aprobada de una
función existente. La API de eliminación disponible corresponde a **campañas**:
elimina la campaña, sus elementos y sus versiones asociadas, sin borrar equipos
del inventario operativo. Un archivo anual independiente tiene `campana_id=null`
y no se elimina mediante esa ruta.

La revisión no añadió una función nueva de borrado de archivos anuales.

## Evidencia reproducible

- Servidor: `backend/tests/test_inventario_anual.py`,
  `backend/tests/test_descarga_y_borrado.py`, la prueba de archivo anual de
  `backend/tests/test_redisenio_general.py`, `backend/tests/test_plantilla_reglas.py`
  y `backend/tests/test_archivo_anual_revision.py`.
- Navegador: `frontend/pruebas/auditoria-inventario-anual.spec.ts`, la prueba
  «Excel anual se registra al primer intento y compara dos años» y la prueba
  «importación anual recupera una respuesta perdida sin recargar ni duplicar».
- Las pruebas antiguas de interfaz que buscaban «Nueva campaña» en esta pantalla
  corresponden a un flujo retirado; no se usaron para certificar el archivo anual actual.

Los archivos con IP/MAC incorrectas o equipos duplicados se rechazan completos;
no deben dejar una versión parcial. La ausencia de un equipo en un año posterior
se informa como diferencia, sin darle una baja operativa automáticamente.
