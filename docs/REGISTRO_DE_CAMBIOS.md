# Registro de cambios y entregas

Este registro describe cambios preparados y entregados. La columna de estado
evita confundir un archivo editado con una publicación operativa autorizada.
Los commits contienen la diferencia exacta; las pruebas repetidas no se suman
como casos nuevos.

| Referencia | Alcance | Estado y evidencia |
| --- | --- | --- |
| `fc5de05` | Protección de cuentas y ubicaciones, archivo, importación por permisos, traslado y cruces de roles; corrección del historial al liberar y reasignar. | Publicado en GitHub privado en la ronda anterior. Comprobación local registrada: 60 casos de servidor, 3 recorridos de navegador y 13 de herramientas. El estado actual de Actions se consulta en GitHub; no se deduce de este texto. |
| `CAM-2026-001` | Relevo desde Excel, controles de aplicación de IA, documentación por rol, arquitectura, datos, seguridad y procedimiento de cambios. | Validado y aplicado localmente el 07/11/2026: 120 casos distintos de servidor, cinco recorridos de navegador y construcción de las tres imágenes aprobados. Evidencia y límites en [Entrega y puesta en marcha](ENTREGA_Y_PUESTA_EN_MARCHA.md). Aprobación institucional, auditoría actual de imágenes y despliegue definitivo pendientes. |

## Seguimiento técnico e institucional

| Referencia | Qué revisar | Situación |
| --- | --- | --- |
| `SEG-001` | Imágenes actuales, incluidos paquetes nativos y mitigaciones compiladas | Auditoría pendiente; no hay recuento actualizado verificado en esta ronda. |
| `OPE-001` | Servidor, dominio, TLS, exposición y recuperación | Requiere el entorno definitivo y la aceptación de TI. |
| `DAT-001` | Retención de auditoría y chats, tratamiento por proveedores externos | Definición institucional pendiente; los plazos actuales no se presentan como aprobación legal. |
| `DAT-002` | Herencia general de responsable desde una PC a componentes que no tenían dueño | Refuerzo de trazabilidad pendiente: esa operación heredada usa una actualización masiva sin intervalos individuales. El nuevo flujo de importación sí asigna y registra cada componente expresamente; no reconstruye periodos antiguos. |

## Qué completar en cada publicación operativa

Registra fecha, commit exacto, servidor, operador, autorización del responsable,
migraciones aplicadas, pruebas de aceptación, incidencias y decisión de continuar
o revertir. No incluyas contraseñas, tokens, archivos de inventario reales ni
datos personales innecesarios.
