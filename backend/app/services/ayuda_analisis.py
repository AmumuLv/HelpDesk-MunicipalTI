"""Orientación funcional local de Consultas de datos, sin llamadas a proveedores."""
import re
import unicodedata


def responder_ayuda(pregunta):
    texto = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower()) if not unicodedata.combining(c)).strip(' ¿?¡!.')
    if re.fullmatch(r'hola|buenos dias|buenas tardes|buenas noches|buenas', texto):
        return 'Hola. Soy tu asistente de análisis interno. Puedo revisar tickets, inventario y disponibilidad de TI con datos del sistema. Puedes empezar con «¿Qué oficina tiene más incidencias?» o preguntarme para qué sirve cada indicador.'
    if re.fullmatch(r'gracias|muchas gracias|ok|entendido|perfecto', texto):
        return 'Cuando necesites revisar otra cifra, escribe tu pregunta o elige una consulta sugerida. Mantendré el periodo seleccionado salvo que indiques otro.'
    if re.search(r'para que sirve (?:esta |la |nuestra |el |este )?(?:web|pagina|sistema)|que es (?:esta |la )?(?:web|mesa de ayuda)', texto):
        return 'Esta mesa de ayuda organiza el soporte TI de la municipalidad: registra incidencias, permite conversar con soporte, asigna técnicos y conserva el resultado de la atención. También administra equipos, responsables, oficinas y guías de conocimiento.\n\nEn Análisis puedes revisar indicadores y hacer consultas internas. El chatbot TI complementa estas funciones con orientación técnica; ninguno de los dos asistentes modifica registros por su cuenta.'
    if re.search(r'para que sirves|para que sirve (?:(?:este|el|la) )?(?:asistente|modulo|analisis|ia|consulta)|^para que sirve$|que (puedes hacer|haces|funciones tienes|eres)|como (te uso|usarte|funcionas|uso (este|el) asistente)|que (datos|informacion) (puedes|puedo) consultar|que puedo preguntar', texto):
        return 'Te ayudo a entender los datos de la mesa de ayuda: dónde se concentran los tickets, qué problemas se repiten, cómo está disponible el equipo TI y qué equipos tiene una persona. Las consultas reconocidas se calculan en el sistema, sin gastar tokens de Groq.\n\nEscribe una pregunta concreta o elige una sugerencia. Por ejemplo: «¿Qué zona tiene más tickets?», «¿Qué técnico está disponible?» o «Equipos de [nombre del trabajador]». Puedes seguir conversando en el mismo chat. Solo consulto información permitida para tu cuenta; no cambio registros.'
    if re.search(r'(que es|que significa|explica|para que sirve).*sla|como.*(calcula|funciona).*sla', texto):
        return 'El SLA es el plazo de atención configurado para responder y resolver un ticket. Depende de su prioridad, los horarios laborables y las pausas que tenga habilitadas el sistema.\n\n«En tiempo» indica que sigue dentro del plazo; «Vencido» indica que lo superó. Para saber las horas exactas de tu institución, revisa Configuración > SLA: no son las mismas para todas las prioridades.'
    if re.search(r'(que significa|como interpreto|explica|que son|por que).*(faltante|completitud|calidad|0%|100%)', texto):
        return 'En datos faltantes, 0% significa que no hay campos pendientes; cuanto más baja la cifra, mejor. En completitud ocurre al revés: 100% significa que están completos los datos que sí corresponden al equipo.\n\nUn mismo equipo puede tener varios campos pendientes y aparecer en varias barras. Por eso los porcentajes por campo no se suman. Los campos marcados como «No aplica» se excluyen del cálculo correspondiente.'
    if re.search(r'(diferencia|distinto|compar).*(chatbot|groq)|(?:usas|consumes|gastas).*(tokens|groq)|(?:tienes|hay).*(limite|cupo)', texto):
        return 'Este asistente está centrado en consultas estructuradas del sistema. Las preguntas reconocidas se responden directamente con los datos internos y no usan tokens de Groq ni el límite de 15 consultas del chatbot.\n\nEl chatbot TI sirve para orientación técnica y conversación más amplia. Aquí puedes revisar resultados, sus fuentes y tablas; las funciones disponibles dependen de tus permisos.'
    if re.search(r'(que (?:es|significa)|como (?:funciona|uso|se usa|selecciono|elijo)|explica(?:me)?).*(periodo|rango|fecha)|que significa.*(?:30d|90d|365d)', texto):
        return 'El selector Periodo indica el rango usado para las consultas históricas, salvo que la pregunta especifique otro periodo reconocido, como «este mes» o «últimos 90 días». Las fechas se presentan como día/mes/año.\n\nLa disponibilidad de TI y el inventario describen el estado actual. El historial por familia de equipos usa los últimos doce meses y lo indica en la respuesta; no es una predicción futura.'
    if re.search(r'(puedes|vas a).*(editar|eliminar|crear|modificar|cerrar|asignar)|que permisos tienes', texto):
        return 'Solo tengo funciones de consulta. Puedo mostrar datos y ayudarte a interpretarlos, pero no crear, editar, eliminar, asignar ni cerrar tickets o equipos. Cada consulta comprueba los permisos de tu cuenta.'
    return None
