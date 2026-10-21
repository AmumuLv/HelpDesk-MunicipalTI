# Inventario anual: diseño y navegación

La pantalla organiza el trabajo en tres acciones: registrar un archivo, consultar los inventarios guardados y comparar años. Los accesos superiores llevan a cada sección.

- Resumen de años y versiones disponibles.
- Selección del archivo con nombre, tamaño y año de destino visibles antes de registrarlo.
- Instrucciones del archivo desplegables.
- Acceso rápido por año y selector de versiones; se muestran cantidad de equipos, autor y fecha del registro.
- Comparación con totales destacados, diferencias agrupadas y criterio desplegable. Que un equipo no aparezca en el destino no lo elimina del inventario operativo.
- Estilos azul suave para tema claro y oscuro, adaptados a móvil.

Se conserva la lógica de registro, validación, búsqueda, descarga y comparación. El archivo anual sigue siendo independiente del inventario operativo.

Validación del diseño: prueba de navegador con respuestas simuladas para seleccionar otro año y comparar; comprobación de desbordamiento a 320, 820 y 1440 píxeles en ambos temas; sin infracciones graves o críticas de axe en el módulo. Esta comprobación visual complementa la auditoría funcional anterior, documentada en `PRUEBAS_INVENTARIO_ANUAL_2026_10_20.md`.
