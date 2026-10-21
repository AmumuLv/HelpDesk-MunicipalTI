# Preparación de HelpDesk-MunicipalTI

Repositorio: [AmumuLv/HelpDesk-MunicipalTI](https://github.com/AmumuLv/HelpDesk-MunicipalTI), con visibilidad **privada** verificada.
El repositorio local tiene su raíz en esta carpeta; no incluye el resto del
Escritorio ni su historial Git anterior.

## Validación completada

| Comprobación | Resultado |
| --- | --- |
| Suite completa del servidor | **274 aprobadas**, más **22 subpruebas** aprobadas; sin fallos ni omisiones. |
| Portal y componentes en navegador | **58 aprobadas**, incluidas sincronización, asistentes, estrellas, reacciones, notificaciones, temas y eliminación anual. |
| Análisis con API real | Tres pruebas aprobadas: panel adaptable, conversación persistente con recuperación de errores y reintento del panel. |
| Administración de usuarios con API real | Aprobada: crear, foto, cambio de correo, restablecimiento de contraseña, historial paginado, desactivar/reactivar y perfil rápido. |
| Herramientas de publicación y traslado | **8 pruebas unitarias** aprobadas. |
| Rutas del frontend | **159 llamadas** detectadas coinciden con las **151 rutas** documentadas. |
| Lint y TypeScript | Sin errores. Se conservan 16 advertencias de mantenimiento de lint. |
| Compilación de producción | API y web compiladas con las dependencias fijadas; instalación del frontend con `npm ci`. |
| Revisión de archivos publicables | Sin credenciales detectadas; `.env`, respaldos, adjuntos, dependencias instaladas y documentos originales de trabajo quedan fuera. |

Las pruebas antiguas se adaptaron a las reglas actuales: un ticket manual parte
de un equipo real de la persona; un usuario reporta por compañeros registrados
de su oficina; el cambio de contraseña de usuarios lo realiza el administrador;
el canal en vivo envía un aviso inicial de sincronización. No se quitaron esas
protecciones ni se deshabilitaron pruebas para obtener un resultado favorable.

Se completó el borrado de una **versión anual independiente**. Exige administrador
y CSRF, pide confirmación en la web, registra auditoría y conserva equipos
operativos, otras versiones y versiones pertenecientes a campañas.

## Traslado verificado en Windows

Se creó y restauró un respaldo en servicios Docker aislados, conservando
**24 usuarios, 48 tickets, 28 equipos y un adjunto ficticio**. Se comprobaron los
hashes del ZIP y el permiso de escritura del adjunto restaurado. El intento de
restaurar sobre una instalación con datos fue rechazado. No se incluyeron claves
del entorno en el respaldo ni se utilizaron datos operativos para esta prueba.

`iniciar.cmd` inicia el sistema en Windows. Las herramientas nativas de
PowerShell permiten respaldar y restaurar; la alternativa Python está incluida
para Linux/macOS y tiene validaciones unitarias. La prueba de traslado con Docker
se realizó con la versión de PowerShell de Windows.

Consulta [Instalar y trasladar](INSTALAR_Y_TRASLADAR.md) para los comandos.
Los datos no viajan mediante `git clone` y dos instalaciones no se sincronizan
entre sí automáticamente. El archivo `.env` y las claves de IA se configuran en
cada servidor, fuera de GitHub.

## Reproducción

- `docker compose -f compose.pruebas.yml run --build --rm tests`.
- `npm run lint`, `npm run typecheck`, `npm run verify:ai-texts` y `npm run verify:clases`, desde `frontend`.
- `npx playwright test pruebas/portal-sencillo.spec.ts`, desde `frontend`.
- Para Análisis y Usuarios, levantar primero el perfil `navegador` del archivo de pruebas y definir `PRUEBA_API_URL=http://127.0.0.1:18100`.
- `python -m unittest discover -s tools -p 'test_*.py'`.
- `python tools/revisar_publicacion.py` y `python tools/verificar_rutas.py`.

Las dependencias Python verificadas se fijan en `backend/constraints.txt` y el
frontend se instala con `npm ci` desde su lockfile. GitHub Actions reproduce las
pruebas del servidor, del portal y las comprobaciones de publicación sin claves
reales de proveedores. Las respuestas de los proveedores externos se simulan en
las pruebas: no se consumieron las cuotas reales del chatbot para validarlas.

Este documento cierra los pendientes de pruebas indicados en la revisión general
anterior. Sus resultados históricos se mantienen para mostrar qué se encontró y
qué se corrigió. Las pruebas automatizadas cubren los flujos descritos; no son una
garantía universal sobre cualquier entorno o servicio externo.
