# Groq: proveedor actual del chatbot TI

## Consultas de datos: motor interno de análisis

Las respuestas nuevas de este asistente aparecen con escritura progresiva local,
en un máximo aproximado de 80 actualizaciones cada 30 ms. No se hacen nuevas
peticiones ni se consumen tokens por la animación. Las conversaciones recuperadas
se muestran completas; se respeta la preferencia de movimiento reducido.

Análisis IA > Consultas de datos tiene una identidad visual propia, verde futurista,
con burbujas de chat, cabecera verde oscura y tonos suaves en el tema claro. El chat
tiene una altura máxima de 760 px (adaptada a la pantalla), desplazamiento en los
mensajes y el compositor fijo al pie. Usa texto de respuesta de 15 px en escritorio
y 14 px en móvil, con mayor separación entre líneas. Presenta la conclusión
primero, fuentes, comparación de hasta cinco resultados y una tabla desplegable.
Las barras comparan cantidades contra el valor mayor, no porcentajes del total.
Compatible con temas claro y oscuro y pantallas desde 320 px.

La guía local de `ayuda_analisis.py` también reconoce saludos, agradecimientos,
«para qué sirve», preguntas sobre SLA, fechas, porcentajes de calidad, permisos
y diferencias con Groq. Responde sin proveedor externo y rotula estas respuestas
como ayuda del sistema, sin presentarlas como cifras consultadas. Las guías no
amplían los permisos ni conceden funciones de escritura.

Las preguntas reconocidas se calculan mediante consultas internas de solo lectura,
sin invocar un modelo externo ni consumir tokens de Groq para redactarlas. No se
les aplica el límite de 15 consultas del chatbot. El chatbot permanece como
orientación conversacional; esta sección se centra en resultados verificables.
Una pregunta no reconocida puede usar el proveedor interno ya configurado para
identificar consultas autorizadas; nunca se aceptan cifras sin respaldo.

Las respuestas distinguen un líder de un empate, muestran las fechas DD/MM/AAAA y
no interpretan volumen de tickets como gravedad. Las tasas por familia muestran
porcentajes humanos y aclaran que son un historial de doce meses, no una predicción.
Inventario actual, disponibilidad y el historial completo de una persona se rotulan
con su alcance real, en vez de atribuirles el periodo de la pantalla.

## Conversaciones guardadas y límite por técnico

Cada cuenta TI tiene su propio historial persistente en `chatbot_conversaciones`.
El selector permite abrir conversaciones anteriores. Nueva conversación conserva
la anterior; el botón de papelera elimina únicamente la conversación seleccionada
de la cuenta actual. Se conservan mensajes, fuentes y contadores al recargar,
navegar o cerrar sesión. Los chats antiguos que solo existían en memoria no pueden
recuperarse si la pestaña ya se cerró antes de esta actualización.

Los técnicos tienen **15 consultas por chat**, configurables mediante
`CHATBOT_LIMITE_CONSULTAS_TECNICO=15` en el entorno del servidor. La comprobación es
atómica en MongoDB y bloquea peticiones simultáneas al mismo chat desde otras
pestañas. Los intentos que llegan al proveedor cuentan, incluso si falla la cuota
externa. Al alcanzar el límite se puede abrir otra conversación. Para acotar el
tamaño almacenado, administradores tienen 100 consultas por chat y cada cuenta
puede guardar hasta 100 conversaciones (debe eliminar alguna para guardar otra).

La API reconstruye el historial desde el servidor y solo envía los seis últimos
mensajes al proveedor; no acepta reemplazar mensajes guardados desde el navegador.
Guardar, abrir o eliminar conversaciones no consulta a Groq. Los avisos de cambios
refrescan el historial de cada cuenta sin enviar mensajes por el canal común.

Estos límites locales no amplían ni reinician la cuota del proveedor. Groq publica
para el plan gratuito de `openai/gpt-oss-20b` 200.000 tokens/día, 8.000 tokens/minuto,
1.000 solicitudes/día y 30 solicitudes/minuto, compartidos por organización.
Una pregunta puede consumir varias solicitudes. La cuota exacta se revisa en
https://console.groq.com/dashboard/limits y la referencia publicada es
https://console.groq.com/docs/rate-limits.

## Conocimiento y alcance

El contexto funcional se mantiene en `backend/app/services/conocimiento_proyecto.py`
y en la guía de `chatbot_service.py`. Incluye los flujos reales de tickets,
inventario, conjuntos, laptops, calidad, usuarios, organización, perfiles, equipo TI,
reportes, conocimiento, configuración y sincronización. Se seleccionan los apartados
relacionados con la pregunta y mensajes recientes para reducir consumo de tokens.
Cuando se cambie un flujo de la web también debe actualizarse esta guía.

El asistente está instruido para atender únicamente el proyecto, soporte técnico,
Casma, información del Perú y gestión y normativa municipal peruana. Conserva
respuestas breves, naturales y dirigidas a técnicos o administradores. Esta
delimitación conversacional no sustituye los permisos aplicados por el servidor.

No recibe todo el repositorio ni conoce automáticamente todos los registros.
Consulta datos mediante operaciones de lectura predeterminadas y autorizadas.
No entrena con la base de datos ni accede a archivos de entorno o credenciales.

## Contexto de pantalla y consultas reales con Groq

Cada consulta incluye la ruta abierta y una lista permitida de filtros (fechas,
periodo, estado e identificadores). No se envían parámetros arbitrarios de la URL,
tokens, formularios sin guardar ni el contenido completo de la pantalla. El chat
muestra qué sección está tomando como contexto. Se permiten preguntas generales;
la herramienta puede ignorar los filtros visibles cuando la pregunta lo requiere.

Groq dispone de `consultar_sistema`: tickets y sus recuentos, rankings históricos
por equipo, oficina o estado, inventario, conjuntos, directorio, organización,
metadatos de reportes, campañas, ausencias sin motivos, resúmenes de conocimiento
y configuración funcional del administrador. Cada lectura comprueba permisos y
usa proyecciones inclusivas; no puede pedir una colección, pipeline o comando libre.
Los reportes personales y ausencias conservan su restricción por cuenta.
No se envían contraseñas, hashes, claves API, sesiones, cuerpos de conversaciones,
notas internas, adjuntos ni correos de contacto. Los campos libres enviados se
limitan y filtran para retirar patrones de credenciales.

Hay un máximo de dos tandas de tres lecturas por pregunta, con una redacción final.
Las listas muestran hasta 20 resultados; los totales se cuentan sobre toda la
consulta. Las operaciones tienen un límite de tiempo. No hay herramientas para
crear, editar, eliminar, ejecutar comandos o generar archivos. El proveedor recibe
los resultados necesarios de las lecturas autorizadas, no una copia de la base.
El uso de tokens suma las llamadas de herramientas y la respuesta final.

Las fechas visibles usan DD/MM/AAAA. Las herramientas usan ISO internamente y
consultan días completos de America/Lima, con rango de hasta 366 días. Las fechas
pedidas prevalecen sobre las de pantalla; sin rango se usa el visible o 30 días.
Un ticket exacto puede consultarse sin restringir su fecha. Un ranking por equipo
cuenta tickets realmente vinculados y declara los casos sin vínculo; no confunde
ese recuento histórico con una predicción por familia de equipos.

Para consultas municipales intenta obtener contexto de los portales oficiales de
Casma. Para normativas orienta además a El Peruano y SPIJ, distinguiendo un enlace
de referencia de una norma cuyo texto y vigencia se hayan verificado. No hay un
buscador jurídico en tiempo real: debe reconocer cuando falta el texto oficial y
pedir número, año o contenido pertinente, sin inventar artículos o requisitos.

En `.env` del servidor:

```dotenv
CHATBOT_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
```

Coloca tu clave en `GROQ_API_KEY`. No uses variables VITE para credenciales.
Las comillas son opcionales para una clave sin espacios. No compartas la clave.

Recrear servicios tras configurar la clave: `docker compose up -d api worker`.
Si cambia el codigo: reconstruir primero las imagenes de API, worker y web.

Groq usa la misma guia del sistema, contexto municipal y consultas autorizadas.
Solo tecnicos y administradores acceden; no recibe herramientas de escritura.
La IA del portal del usuario y los modelos estadisticos no cambian.
La clave nunca se envia al navegador. El proveedor recibe la pregunta, hasta seis
mensajes previos y contexto autorizado, incluidos resumenes de guias relacionados.
No se envia la base de datos completa ni se entrena el modelo con ella.

Se muestran tokens consumidos por conversacion, no un saldo diario inventado.
Las cuotas reales y su renovacion se consultan en Groq Console:
https://console.groq.com/dashboard/limits
Documentacion: https://console.groq.com/docs/rate-limits
Usa una cuenta Free; la aplicacion no activa facturacion ni cambia a un proveedor
alternativo al agotar la cuota. La gratuidad depende del plan de tu cuenta.
Gemini queda disponible solo mediante seleccion explicita: CHATBOT_PROVIDER=gemini.

---

## Referencia anterior: Gemini (solo si se selecciona explicitamente)

# Chatbot de consultas para TI

Disponible mediante el botón azul del panel para técnicos y administradores.
No aparece en el portal de usuarios. No reemplaza el chat de los tickets ni el
modelo estadístico de predicciones. No dispone de herramientas de escritura,
comandos, acceso libre a MongoDB ni acciones para modificar registros.

## Configurar Gemini

1. Crear una clave en Google AI Studio: https://aistudio.google.com/apikey.
2. En el archivo `.env` del servidor, agregar `GEMINI_API_KEY` con la clave.
   No publicarla en GitHub, chats, capturas ni variables `VITE_*`.
3. Establecer `GEMINI_MODEL=gemini-3-flash-preview` o el identificador de un modelo
   disponible en la cuenta. Revisar cuotas y condiciones de uso de esa cuenta.
4. Recrear los servicios: `docker compose up -d api worker`.
5. Abrir el botón «Asistente TI» y hacer una consulta. Sin clave, se muestra
   «Falta configurar la clave»; no se simula una conexión exitosa.

La integración utiliza la API REST `generateContent` de Google:
https://ai.google.dev/api/generate-content.
La clave viaja únicamente del servidor a Google mediante `x-goog-api-key`.
No se cambia `AI_PROVIDER`: los usuarios y la IA interna conservan su configuración.

## Alcance y datos

- Orientación técnica general y explicación de los flujos implementados.
- Consultas predefinidas de analítica verifican los permisos del técnico antes
  de obtener datos. El periodo inicial es de 30 días y se declara en el contexto.
- Las cifras proceden de consultas del sistema, no del conocimiento del modelo.
- Se sugieren guías accesibles según los permisos, incluyendo guías internas.
  Solo se envían sus títulos; no sus cuerpos, que podrían contener credenciales.
- Google recibe la pregunta, los últimos seis mensajes, la guía de funcionamiento
  y los resultados de las consultas autorizadas. No se envían contraseñas ni
  archivos adjuntos automáticamente. Evitar pegar secretos en las preguntas.
- La conversación se guarda por cuenta en MongoDB. «Nueva consulta» inicia otra;
  la papelera elimina la seleccionada. Salir de la cuenta conserva su historial privado.
- Diez peticiones por minuto por cuenta; pregunta de hasta 1500 caracteres.
  Los errores de cuota, conexión o configuración se muestran sin revelar claves.

## Modelo interno

Gemini aporta lenguaje y orientación; no se presenta como un modelo entrenado
con la base municipal. Las predicciones y gráficos continúan con los modelos
estadísticos existentes y sus mínimos de datos. La mejora del asistente consiste
en responder con contexto verificado, consultas limitadas por permisos y fuentes,
sin prometer exactitud de predicciones ni un entrenamiento que no se realizó.

Ademas, las sugerencias de categoria en el detalle de tickets para TI se contrastan
con el catalogo activo. Si no hay coincidencia vigente, no se propone una categoria
inventada y se reduce la confianza de esa clasificacion a cero. Este ajuste no
cambia las sugerencias del portal del usuario.

## Interfaz del asistente

Diseno azul con cabecera propia, fondo de puntos y accesos de consulta.
Una sola zona desplazable para mensajes mantiene visible el compositor.
Compatible con temas claro y oscuro y pantallas desde 320 px.
Las respuestas muestran negritas y comandos sin interpretar HTML.

El chatbot conversa con el técnico o administrador identificado por la sesión, como apoyo del equipo TI. Responde con párrafos breves y adapta la explicación al historial; reserva las listas numeradas para procedimientos que necesitan orden. Distingue al profesional que consulta del trabajador afectado y pide una aclaración concreta si falta información para recomendar una comprobación. Sigue siendo de solo lectura.
Enter envia y Shift + Enter permite escribir otra linea.

## Consumo, continuidad y fuentes

El pie del chatbot muestra consultas y tokens usados en esta conversacion, segun los metadatos de uso del proveedor seleccionado. Si el proveedor no devuelve metadatos, muestra sin datos o parcial; no calcula un saldo supuesto. El uso y las cuotas generales se consultan en la consola del proveedor seleccionado. Nueva consulta reinicia el contador de la conversacion.

Al cerrar y volver a abrir, se muestra el último mensaje. Las conversaciones se guardan en MongoDB por cuenta y pueden retomarse después de recargar o iniciar sesión nuevamente; solo su propietario puede consultarlas o eliminarlas mediante estas rutas.

Consultas municipales intentan leer los portales oficiales gob.pe/municasma y municasma.gob.pe con cache de diez minutos. Si no es posible verificar datos actuales, debe indicarlo. Las guias aportan titulo y resumen, filtrando posibles credenciales; no se envian cuerpos completos. Los recuentos y consultas internas respetan permisos. No se permite editar registros.

Consultas de datos (antes Asistente del servicio) permanece en Analisis para cifras estructuradas por periodo. Gemini es orientacion conversacional y municipal. Los modelos estadisticos internos siguen encargandose de predicciones y graficos.
# Ajustes de visualización y equipos

- Las respuestas nuevas aparecen con un efecto de escritura local, en bloques y con un máximo aproximado de 80 actualizaciones. Usa una sola consulta a Gemini. Al volver a abrir el chat se muestra la respuesta completa; se respeta la preferencia de movimiento reducido.
- «Datos que faltan» muestra el porcentaje sobre las casillas esperadas y su cantidad. Cada campo también indica qué porcentaje de los equipos carece de ese dato; estas barras no suman 100%, porque un equipo puede tener varios datos pendientes.
- Un conjunto representa una PC de escritorio y sus componentes. Laptops e impresoras se registran como equipos independientes. Los programas pueden vincularse al conjunto de escritorio o directamente a una laptop; el formateo puede vincularse al CPU o a la laptop.
- En el portal se elige «Para mí», «Para un compañero» o «Para la oficina». Los reportes propios no piden equipos; para un compañero solo se elige su nombre. En oficina se muestran tipos únicos de equipos compartidos, con iconos y «No lo sé», sin nombres técnicos ni dispositivos concretos. TI identifica y vincula el equipo exacto al editar el ticket.
- No se modifica en bloque el inventario antiguo ni sus historiales. Los registros nuevos y las selecciones de tickets respetan esta distinción.

