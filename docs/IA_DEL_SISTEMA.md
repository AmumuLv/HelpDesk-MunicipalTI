# IA del sistema y chatbot TI

Revisión del código: 06/11/2026. Esta guía describe las funciones implementadas;
no supone que existan claves de proveedores ni que una cuota gratuita esté disponible.

## Qué aporta cada uno

| Función | Motor integrado | Chatbot TI |
| --- | --- | --- |
| Objetivo | Clasificar, proponer atención y calcular indicadores verificables | Conversar sobre el sistema, Casma y problemas técnicos |
| Dónde aparece | Reporte, ficha del ticket, Análisis IA y Consultas de datos | Ventana Asistente TI para técnicos y administradores |
| Cómo responde | Reglas, consultas programadas, estadísticas y modelos de scikit-learn cuando hay muestra | Modelo generativo externo; Groq o Gemini según configuración |
| Sin Internet/proveedor | Conserva las reglas y consultas internas; necesita MongoDB y Redis disponibles | No puede generar una respuesta normal del proveedor |
| Tokens externos | Las consultas reconocidas y reglas no usan tokens del chatbot | Sí; incluye pregunta, contexto, historial enviado y respuesta |
| Cambios operativos | Una persona puede aplicar una sugerencia mediante los servicios normales | No tiene herramientas para crear, editar ni borrar registros |
| Historial de conversación | `conversaciones_ia`, separado por cuenta | `chatbot_conversaciones`, separado por cuenta |

Son dos capacidades distintas. **Conviene conservar el motor interno y dejar el
chatbot como apoyo opcional.** No hacen falta dos proveedores de pago: el motor
interno funciona con `AI_PROVIDER=desactivado`, y el chatbot puede utilizar un solo
proveedor elegido. El chat del ticket entre trabajador y técnico es una tercera
función de comunicación humana, independiente de ambos asistentes.

## Motor integrado: recorrido de una sugerencia

1. El sistema analiza el tipo de problema, texto, urgencia y equipo vinculado.
2. Propone categoría/prioridad y artículos relacionados; la asignación considera
   disponibilidad, carga, horario, ausencias y especialidad de TI.
3. La persona revisa y pulsa **Aplicar**, **Editar** o **Descartar**, cuando el
   control corresponde al tipo de sugerencia y a sus permisos.
4. Aplicar categoría/prioridad pasa por la edición normal del ticket. Aplicar un
   técnico pasa por la asignación normal: valida identidad del destino, permisos,
   disponibilidad, conflictos, primera atención y notificaciones.
5. Se registra la decisión para no volver a ofrecerla como pendiente.

El nombre del técnico sirve para mostrarlo; el identificador se envía al aplicar.
No se escribe un nombre libre para asignarlo. Si está fuera de horario o ausente,
se utiliza la confirmación habitual de **Asignar a**; la sugerencia no confirma
ese supuesto automáticamente ni queda marcada como aplicada si se rechaza.

Ocultar las recomendaciones personales no borra los registros anteriores. El
aprendizaje de decisiones tiene una opción global independiente; si está activo,
puede registrar señales aunque la persona oculte las sugerencias. Esto no entrena
Groq/Gemini ni modifica sus parámetros.

## Consultas de datos y modelos

Las preguntas reconocidas en Consultas de datos se traducen a herramientas
predeterminadas: oficinas/zonas con incidencias, causas, disponibilidad, equipos
y tickets por persona o conjuntos. Los permisos se vuelven a comprobar y la
respuesta incluye el periodo y sus fuentes. La ayuda sobre el propio módulo
tampoco necesita un proveedor. Una pregunta no reconocida puede no tener respuesta
en este módulo; para orientación abierta se usa el chatbot.

`ml_service.py` combina modelos estadísticos con reglas orientativas. La muestra
mínima declarada es de 30 para entrenamiento y de 14 para pronósticos; además se
necesitan las condiciones y características que exige cada cálculo. Tener ese
número de registros por sí solo no garantiza un modelo útil. Cuando no alcanza
la información se indica **Datos insuficientes** o el método heurístico utilizado.
Los valores de riesgo son indicadores para revisar con TI, no probabilidades de
fallo futuro validadas ni diagnósticos confirmados.

Si se habilita un proveedor compatible en `AI_PROVIDER`, puede ampliar ciertos
resúmenes o preguntas no reconocidas. Esa opción es independiente de
`CHATBOT_PROVIDER`: no es necesaria para el funcionamiento básico y puede enviar
texto o resultados al servidor configurado en `AI_BASE_URL`. No debe habilitarse
un destino externo sin revisar ese tratamiento de datos.

## Chatbot: qué conoce y qué puede leer

El servidor prepara guías del proyecto, contexto seleccionado de la conversación,
ruta actual y una lista permitida de filtros. No recibe el escritorio completo,
todos los archivos del repositorio ni las pestañas del IDE. La documentación
incluida en `conocimiento_proyecto.py` se mantiene con el código: cambiar una
pantalla no actualiza mágicamente todo ese conocimiento.

Con Groq, `consultar_sistema` permite lecturas estructuradas de recursos permitidos
(tickets, rankings, equipos, conjuntos, personas, oficinas y zonas). Los argumentos
se validan; no se ejecuta SQL, JavaScript ni consultas MongoDB libres generadas
por el modelo. Se aplican permisos, proyecciones de campos, límites de resultados
y tiempo de consulta. Una lista de hasta 20 registros no representa el total:
los rankings deben venir de la agregación correspondiente.

La ruta Gemini utiliza el contexto y consultas preparadas previamente por el
servidor; no implementa el mismo ciclo de herramientas de Groq. Seleccionar otro
proveedor no garantiza idéntica precisión o cobertura de consultas. El sistema no
cambia de proveedor ni activa un plan de pago por sí solo.

Para información municipal se puede añadir contenido del portal oficial. Conocer
un enlace de El Peruano o SPIJ no significa haber leído una norma vigente: el
chatbot no tiene una búsqueda jurídica general en tiempo real. Toda normativa,
autoridad, tasa o requisito utilizado en una decisión oficial debe verificarse
en la fuente correspondiente.

## Privacidad y límites

El proveedor externo recibe los mensajes/contexto y los resultados seleccionados
para responder. Estos pueden incluir nombres, oficinas, equipos y datos de
incidencias según los permisos del solicitante. No se envían deliberadamente
hashes de contraseñas, claves del entorno ni secretos de licencias. Los filtros y
redactores no garantizan detectar un secreto escrito por una persona dentro de
texto libre: no deben pegarse contraseñas, claves o información reservada en el chat,
descripciones o resúmenes de guías.

Las conversaciones son de la cuenta que las creó; el servidor usa su historial
guardado. Se pueden retomar o eliminar. El límite por conversación de técnico
viene de `CHATBOT_LIMITE_CONSULTAS_TECNICO` (valor predeterminado: 15; acotado de 1 a
100). Los administradores tienen un tope de 100 y cada cuenta puede conservar
hasta 100 conversaciones. Existe además un límite de frecuencia por cuenta.
La reserva de una consulta se hace antes de llamar al proveedor: un intento
fallido también puede consumir una consulta de la conversación.

El contador de tokens muestra lo informado por el proveedor; **sin datos** no
significa consumo cero. Los límites del proveedor son diferentes de los límites
de esta aplicación y deben revisarse en su consola. Crear otro chat no aumenta
la cuota externa del proyecto.

## Decisión de diseño

Se conservan las dos funciones actuales. Si se desea reducir opciones visuales,
una mejora posterior es un acceso común con dos acciones: **Consultar datos** y
**Orientación TI**, dejando claro cuál envía información al proveedor. Esta
unificación de entrada es una propuesta; no se ha eliminado ni sustituido un
módulo en esta revisión.

## Referencias para mantenimiento

- Recomendaciones: `backend/app/services/ia_service.py` y
  `frontend/src/componentes/dominio/AIPanel.tsx`.
- Datos/modelos: `analitica_chat.py`, `analitica_service.py`, `ml_service.py`.
- Conversación externa: `chatbot_service.py`, `consultas_chatbot.py`,
  `conversaciones_chatbot.py` y `conocimiento_proyecto.py`.
- Pruebas de autorización al aplicar: `backend/tests/test_ia_aplicar_permisos.py`.
- [Guía de configuración del chatbot](CHATBOT_TI.md),
  [roles y permisos](ROLES_Y_PERMISOS.md) y
  [arquitectura y escalabilidad](ARQUITECTURA_Y_ESCALABILIDAD.md).

Las pruebas nuevas de esta revisión no requieren consumir consultas reales de un
proveedor. La calidad de respuesta del proveedor y su cuota se validan aparte.
