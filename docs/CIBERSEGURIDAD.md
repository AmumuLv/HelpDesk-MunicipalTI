# Ciberseguridad y preparación para operar

Mesa de Ayuda TI de la Municipalidad Provincial de Casma. Revisión documental:
06/11/2026. Esta guía distingue los controles del código, las comprobaciones
ejecutadas y las decisiones que corresponden a la institución. No es una
certificación de seguridad ni un informe de penetración del servidor definitivo.

## Qué protege el sistema

Se deben proteger la identidad de los trabajadores, el inventario municipal, los
tickets, sus conversaciones y adjuntos, los informes y la configuración privada.
El riesgo incluye leer información ajena, tomar una cuenta, atribuir bienes a una
persona equivocada, borrar registros, subir archivos dañinos o interrumpir la
atención. Una cuenta con permiso de eliminación sigue teniendo capacidad de
eliminar: la protección del principal no sustituye la autorización institucional.

La referencia de verificación de aplicación es [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/).
Se usa para ordenar revisiones de autenticación, autorización, archivos y datos;
no se afirma haber cumplido todos sus requisitos.

## Controles existentes y límites

| Área | Control del proyecto | Límite que debe conocer TI |
| --- | --- | --- |
| Contraseñas | Hash Argon2id; no se guarda la contraseña en claro. | No hay un segundo factor de autenticación implementado. Usa contraseñas personales y exclusivas. |
| Sesiones | JWT de acceso corto, renovación con token rotado y huella guardada, revocación y versión de cuenta. | El equipo donde se inicia sesión también debe ser confiable. Los tiempos dependen de la configuración del servidor. |
| Intentos de acceso | Límites de frecuencia y bloqueo temporal por intentos fallidos. | No sustituyen la protección de red ni una revisión de ataques distribuidos. |
| Peticiones de escritura | Sesión y token CSRF comprobados en el servidor. | Ocultar un botón en la interfaz no es una barrera suficiente; cada ruta debe mantener la autorización. |
| Roles | Usuario, técnico y administrador; delegación de permisos; principal protegido para gobernar administradores. | El principal es una cuenta de la web, no un administrador protegido frente al sistema operativo, Docker o MongoDB. |
| Datos entre cuentas | Consultas y acciones sujetas a identidad, rol y permiso; cada petición consulta la autoridad vigente. | Una operación ya autorizada y en curso no se cancela automáticamente porque después se retire un permiso. |
| Archivos y fotos | Límite de tamaño, nombre saneado, tipos permitidos, comprobación de contenido y ClamAV si está habilitado. | ClamAV no inspecciona todo el disco ni garantiza detectar toda amenaza. Las importaciones tienen validaciones propias. |
| Fallo del antivirus | Con ClamAV habilitado, detección, error o falta de respuesta impiden guardar la foto o el adjunto. | Deshabilitarlo elimina esa revisión. No debe hacerse para resolver un problema de subida en producción. |
| Navegador | Cabeceras de seguridad y política CSP; documentación de la API cerrada en entorno de producción. | Verificar las cabeceras desde la dirección pública real, no solo desde un contenedor. |
| Transporte | Caddy y perfil público para dominio y cookies seguras. | El arranque local HTTP no acredita HTTPS público; hacen falta DNS, certificado y pruebas externas. |
| Base y caché | MongoDB y Redis en la red interna de Docker, sin puertos publicados en el Compose normal. | El Compose incluido no habilita autenticación propia de MongoDB ni de Redis. La red interna no equivale a autenticación o cifrado. |
| Aislamiento | API y worker sin privilegios adicionales, capacidades reducidas y directorio temporal acotado. | El control del anfitrión o del servicio Docker permite actuar fuera de los permisos de la web. |
| Claves | Variables de entorno y exclusión de `.env` del repositorio; cifrado de licencias si se configura su clave. | Un repositorio privado no es un almacén de secretos. La custodia de claves y el acceso al servidor son responsabilidad operativa. |

Fuentes de implementación: `backend/app/core/security.py`, `backend/app/api/deps.py`,
`backend/app/domain/permissions.py`, `backend/app/services/auth_service.py`,
`backend/app/services/adjuntos_service.py`, `docker-compose.yml`,
`compose.publico.yml` y `deploy/Caddyfile`.

## Auditoría, historial y conservación

La auditoría central muestra cambios relevantes y alertas del equipo TI. La
política actual conserva esos registros **quince días** mediante la migración
022 y la limpieza del worker. No almacena toda la navegación ni duplica cada
mensaje del chat. Los mensajes y eventos conservan su historial en el ticket.

La interfaz no ofrece editar una entrada de auditoría, pero esa colección no
está protegida como almacenamiento inmutable frente a quien administra la base.
No se debe presentar como evidencia inviolable ni como archivo de conservación
legal de largo plazo. Un fallo al escribir auditoría se registra en los logs y
no detiene automáticamente la operación de negocio.

Las exportaciones generadas se limpian después de siete días; las copias ya
descargadas en los equipos de los usuarios quedan fuera de ese proceso. Una
cuenta dada de baja se **archiva** tras treinta días, conservando su identidad,
sus vínculos y sus antecedentes: no se elimina automáticamente a la persona.

Antes de operar formalmente, la municipalidad debe aprobar la conservación de
datos, las personas autorizadas para consultar registros y el destino de las
evidencias que deban conservarse más tiempo. No cambies una retención copiando
solo el texto de un manual: requiere un cambio controlado de configuración,
código o migración, según el mecanismo existente.

## IA y datos personales

El motor interno y el chatbot tienen funciones distintas. El chatbot puede
enviar al proveedor externo el contexto y los resultados de lectura preparados
por el servidor; no significa que toda la base se copie ni que el proveedor vea
todos los archivos. Las contraseñas, claves de API y licencias no deben formar
parte de ese contexto ni introducirse manualmente en una pregunta.

La información escrita en una descripción puede contener datos sensibles aunque
su campo se llame «texto». Los filtros de campos no garantizan detectar todos
los secretos escritos libremente. La institución debe decidir qué información
puede enviarse a un proveedor, revisar sus condiciones y limitar los datos a lo
necesario. Si esa autorización no existe, mantén deshabilitada la conexión externa
y utiliza los flujos internos permitidos.

El marco peruano incluye la Ley 29733 y su reglamento aprobado por el
[Decreto Supremo 016-2024-JUS](https://busquedas.elperuano.pe/dispositivo/SE/2349653-1).
El responsable institucional debe validar finalidad, acceso, conservación,
transferencias y respuesta a incidentes aplicables al servicio. Esta guía no
certifica cumplimiento legal ni reemplaza esa evaluación.

Las sugerencias internas no autorizan acciones por sí mismas. La aceptación
humana debe pasar por los mismos controles del servicio que una edición o
asignación normal. El chatbot de consulta no debe recibir herramientas de
escritura como efecto de una instrucción en la conversación.

## Gestión operativa de seguridad

La organización puede estructurar su operación con las seis funciones de
[NIST CSF 2.0](https://www.nist.gov/cyberframework):

| Función | Aplicación práctica en esta Mesa de Ayuda |
| --- | --- |
| Gobernar | Nombrar dueño del servicio, responsable del servidor y autoridad que aprueba accesos y cambios. |
| Identificar | Mantener inventario de componentes, datos, dependencias, dominios y proveedores externos. |
| Proteger | Aplicar mínimos permisos, proteger credenciales, actualizar componentes y comprobar restauración. |
| Detectar | Revisar salud, capacidad de disco, accesos fallidos, auditoría y alertas de dependencias. |
| Responder | Tener un contacto y un procedimiento para contener accesos o archivos sospechosos. |
| Recuperar | Restaurar en un entorno controlado, validar integridad y documentar el retorno a servicio. |

Estas actividades son continuas; no terminan al aprobar una batería de pruebas.

## Puerta de salida antes de publicar en Internet

| Comprobación | Evidencia necesaria | Responsable |
| --- | --- | --- |
| Dominio y HTTPS real | DNS correcto; certificado confiable; acceso desde otra red; cookies y redirección verificadas. | Responsable de red/servidor |
| Superficie expuesta | Solo los puertos públicos previstos; MongoDB, Redis y puertos directos sin acceso público. | Responsable de servidor |
| Datos y secretos | `.env` custodiado, claves fuera de Git, permisos del equipo y acceso Docker restringidos. | Responsable de servidor |
| Cuentas | Principal identificado; cuentas personales; revisión de técnicos y administradores; bajas probadas. | Responsable del servicio |
| Dependencias e imágenes | Análisis actual con fecha, digest de imagen, avisos, correcciones y excepciones justificadas. | Mantenimiento del proyecto |
| Archivos | Antivirus activo y firmas actualizadas; prueba de rechazo y de indisponibilidad del servicio. | Mantenimiento/servidor |
| Recuperación | Política de copia aprobada y restauración verificada fuera de los datos reales de trabajo. | Responsable de servidor |
| Rendimiento | Medición en el servidor previsto con carga representativa y espacio disponible. | Mantenimiento/servidor |
| Privacidad y proveedor IA | Uso de datos y proveedor autorizado; información al personal y responsables definidos. | Autoridad institucional |
| Aceptación | Casos de usuario, técnico y administrador revisados; incidencias pendientes clasificadas. | Responsable del servicio |

No hay dominio ni servidor definitivo validados en esta documentación. Un número
histórico de vulnerabilidades o una comprobación local no debe marcar ninguna
fila como aprobada. Registra el resultado vigente en el expediente de entrega.
Si el analizador necesita una sesión de Docker u otra dependencia, el estado es
**sin verificar** hasta completar la ejecución; no equivale a cero alertas.

## Qué hacer ante un incidente

1. Identifica el servicio, el momento y la cuenta afectada; conserva el código
   del ticket y los mensajes técnicos necesarios sin difundir secretos.
2. Comunica el incidente al responsable designado y aplica la contención
   autorizada: revocar una sesión o desactivar una cuenta operativa, aislar un
   equipo o restringir temporalmente el acceso público según el caso.
3. Conserva las evidencias antes de una limpieza o restauración. No borres datos
   para ocultar el problema ni pegues tokens en un informe compartido.
4. Evalúa alcance, registros afectados y obligaciones de comunicación con la
   autoridad institucional competente.
5. Corrige y prueba en un entorno separado. Valida accesos, integridad y archivos
   antes de reabrir el servicio.
6. Documenta causa, acciones, responsables y prevención en el control de cambios.

## Comprobaciones técnicas reproducibles

Las suites se ejecutan con datos ficticios en los servicios de prueba. Las
lecturas de dependencias e imágenes revisan la instalación indicada; no implican
modificar datos de usuarios.

```powershell
docker compose -f compose.pruebas.yml run --rm tests python -m pytest tests/test_seguridad_publicacion.py tests/test_adjuntos_seguridad.py tests/test_jerarquia_cuentas.py
python tools/auditar_dependencias.py
python tools/auditar_imagenes.py mesa-ayuda-api mesa-ayuda-worker mesa-ayuda-clamav mesa-ayuda-mongo mesa-ayuda-web mesa-ayuda-proxy redis:7-alpine
```

No ejecutes pruebas de altas, bajas o carga contra la instalación municipal.
La prueba HTTPS aislada requiere preparar primero sus servicios como se explica
en [la referencia técnica de instalación](INSTALACION_TECNICA.md). Las ubicaciones
y los volúmenes están en [Almacenamiento](ALMACENAMIENTO.md); los límites de
cuentas, en [Roles y permisos](ROLES_Y_PERMISOS.md).
