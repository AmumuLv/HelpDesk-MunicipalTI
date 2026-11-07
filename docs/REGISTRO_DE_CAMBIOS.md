# Registro de cambios y entregas

Este registro describe cambios preparados y entregados. La columna de estado
evita confundir un archivo editado con una publicación operativa autorizada.
Los commits contienen la diferencia exacta; las pruebas repetidas no se suman
como casos nuevos.

| Referencia | Alcance | Estado y evidencia |
| --- | --- | --- |
| `fc5de05` | Protección de cuentas y ubicaciones, archivo, importación por permisos, traslado y cruces de roles; corrección del historial al liberar y reasignar. | Publicado en GitHub privado en la ronda anterior. Comprobación local registrada: 60 casos de servidor, 3 recorridos de navegador y 13 de herramientas. El estado actual de Actions se consulta en GitHub; no se deduce de este texto. |
| `CAM-2026-001` | Relevo desde Excel, controles de aplicación de IA, documentación por rol, arquitectura, datos, seguridad y procedimiento de cambios. | Validado y aplicado localmente el 07/11/2026: 120 casos distintos de servidor, cinco recorridos de navegador y construcción de las tres imágenes aprobados. Evidencia y límites en [Entrega y puesta en marcha](ENTREGA_Y_PUESTA_EN_MARCHA.md). Aprobación institucional, auditoría actual de imágenes y despliegue definitivo pendientes. |
| `CAM-2026-002` | Trazabilidad de componentes, edición masiva, consulta real del chatbot y filtros, auditoría sin resultados falsamente limpios y dependencia de desarrollo corregida. | Validado y aplicado localmente el 07/11/2026. Suite completa de 451 casos y 44 subpruebas; 32 comprobaciones del chatbot posteriores (cinco nuevas); 159 casos de navegador consolidados y tres de instalación vacía. Carga, reinicio y restauración con datos ficticios aprobados. Detalles y límites en [Revisión integral](REVISION_INTEGRAL_2026_11_07.md). La auditoría completa de imágenes y el entorno definitivo siguen pendientes. |

## Seguimiento técnico e institucional

| Referencia | Qué revisar | Situación |
| --- | --- | --- |
| `SEG-001` | Imágenes actuales, incluidos paquetes nativos y mitigaciones compiladas | Scout 1.29.0 verificó ocho avisos altos en API y los mismos ocho en worker, sin críticos en el filtro aplicado. Son avisos repetidos entre imágenes, no dieciséis CVE distintos. Otras imágenes y evaluación completa de mitigaciones pendientes; ver revisión integral. |
| `OPE-001` | Servidor, dominio, TLS, exposición y recuperación | Requiere el entorno definitivo y la aceptación de TI. |
| `DAT-001` | Retención de auditoría y chats, tratamiento por proveedores externos | Definición institucional pendiente; los plazos actuales no se presentan como aprobación legal. |
| `DAT-002` | Herencia general de responsable desde una PC a componentes que no tenían dueño | Corregida y validada en CAM-2026-002: se registra cada componente heredado y el cambio implícito al vincular otra PC. Se respetan responsables particulares y no se reconstruyen periodos antiguos sin evidencia. |

## Qué completar en cada publicación operativa

Registra fecha, commit exacto, servidor, operador, autorización del responsable,
migraciones aplicadas, pruebas de aceptación, incidencias y decisión de continuar
o revertir. No incluyas contraseñas, tokens, archivos de inventario reales ni
datos personales innecesarios.
