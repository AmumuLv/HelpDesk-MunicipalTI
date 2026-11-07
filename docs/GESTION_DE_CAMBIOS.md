# Control de gestión de cambios

Procedimiento operativo para modificaciones de código, configuración, datos,
permisos e infraestructura. Versión 06/11/2026.

## Qué queda registrado y dónde

| Registro | Uso |
| --- | --- |
| Issue o solicitud interna | Problema, solicitante, alcance y criterio de aceptación. |
| Pull request y commit | Diferencias exactas del código y revisión técnica. |
| GitHub Actions | Resultado automático asociado al commit, con sus límites. |
| [Registro de cambios](REGISTRO_DE_CAMBIOS.md) | Qué versión se preparó, evidencia y estado de entrega. |
| Auditoría de la web | Operaciones relevantes sobre usuarios, equipos, tickets y ajustes. |
| Acta interna de publicación | Responsable municipal, fecha, servidor y aceptación de la entrega. |

El historial de Git no contiene la base de datos. La auditoría de la web conserva
una ventana de 15 días; no reemplaza el acta ni la trazabilidad del código.

## Responsables

El solicitante describe la necesidad. El desarrollador implementa y demuestra el
resultado. El revisor comprueba riesgos, permisos y evidencia. El responsable del
servicio autoriza la publicación operativa y la aceptación del riesgo pendiente.
El operador despliega y verifica. Una cuenta principal de la web no obtiene por
ello permisos sobre GitHub, el sistema operativo o Docker.

## Flujo de una modificación

1. **Registrar.** Asigna un ID, por ejemplo `CAM-2026-001`, y describe el problema
   observable. Indica qué debe suceder y qué comportamiento debe conservarse.
2. **Evaluar.** Identifica módulos, roles, datos afectados, migración, privacidad,
   interrupción, coste del proveedor y procedimiento de recuperación.
3. **Preparar.** Trabaja en una rama y utiliza datos ficticios. Una incidencia
   urgente puede reducir el plazo de revisión, no eliminar la evidencia.
4. **Verificar.** Ejecuta controles del área y al menos el cruce de permisos
   afectado. Una prueba omitida se registra como pendiente, no como aprobada.
5. **Revisar.** Usa la plantilla del pull request. El responsable municipal debe
   poder distinguir el cambio preparado de una entrega autorizada al servidor.
6. **Publicar.** Registra commit exacto, configuración modificada sin sus valores
   secretos, migraciones, fecha, operador y comprobaciones del despliegue.
7. **Aceptar o recuperar.** Comprueba ingreso, permisos, operación modificada y
   sincronización. Si falla un criterio crítico, activa la reversión y conserva
   la evidencia para diagnosticarlo.

## Clasificación práctica

| Tipo | Ejemplo | Verificación mínima |
| --- | --- | --- |
| Presentación | Etiqueta o espaciado | Navegación y compilación; no añadir pruebas que solo repitan el texto. |
| Funcional | Importación o cierre de ticket | Escenario completo, errores y compatibilidad con registros anteriores. |
| Seguridad | Roles, sesión o archivos | Intento permitido, denegado y petición directa a la API. |
| Datos/estructura | Nuevo índice o campo | Ensayo de migración, integridad, retención y recuperación. |
| Infraestructura | Dominio, imagen o proxy | Salud, HTTPS, puertos, persistencia y reconexión. |

## Antes de publicar

- El commit incluye los archivos previstos, sin `.env`, claves, adjuntos ni
  exportaciones municipales.
- Las pruebas relevantes aprueban; los controles no ejecutados están identificados.
- La documentación corresponde a los botones y permisos que realmente existen.
- Hay una versión anterior identificada y un plan de recuperación compatible con
  los datos, sin ejecutar una restauración sobre un destino ocupado.
- Si el cambio afecta datos reales, el responsable acuerda la ventana y la
  protección necesaria. Este procedimiento no crea respaldos automáticamente.

## Reversión

Para código sin cambios de estructura, vuelve a construir y desplegar el commit
estable identificado. No uses `reset --hard` para borrar el trabajo de otros.
Revertir código no revierte documentos ya modificados. Una importación parcial o
una migración necesita su propia reconciliación; no se promete un rollback total
si no fue ensayado. Ante cambios incompatibles, detén escrituras y recupera en un
entorno vacío autorizado siguiendo la guía de traslado.

## Plantilla de solicitud

```text
ID y título:
Solicitante / responsable del servicio:
Problema y resultado esperado:
Módulos y roles afectados:
Datos o configuración afectados (sin secretos):
Impacto, privacidad y riesgos:
Pruebas y evidencia:
Commit / PR:
Plan de publicación y comprobación:
Plan de reversión y límite de la reversión:
Estado: propuesto / preparado / validado / autorizado / publicado / revertido
Aceptación institucional y fecha:
```

La plantilla se conserva también en `.github/pull_request_template.md` para
facilitar su aplicación. Es un proceso de gestión; no se añadió una pantalla
incompleta de aprobaciones dentro de la aplicación.

El workflow comprueba las guías, sus enlaces locales y la huella de sus fuentes
en el Word. Si cambia una guía, se regenera el documento antes de publicar;
un Word anterior no se presenta automáticamente como manual de la versión nueva.
