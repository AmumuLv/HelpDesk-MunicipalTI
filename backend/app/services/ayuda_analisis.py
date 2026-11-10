"""Orientación funcional local de Consultas de datos, sin llamadas a proveedores."""
import re
import unicodedata
from app.services.conocimiento_proyecto import trata_importacion_relevo


def _ayuda_importacion_relevo(texto):
    if not trata_importacion_relevo(texto):
        return None
    # «Puedes» también aparece al pedir recuentos o listados reales. Esas
    # preguntas deben seguir el camino de consultas y sus permisos.
    if re.search(r'\b(?:cuantos?|cuantas?|total(?:es)?|cantidad(?:es)?)\b', texto):
        return None
    tutorial = re.search(r'\b(?:como|que significa|que es|explica\w*)\b', texto)
    if re.search(r'\b(?:lista(?:me|do|r)?|muestra(?:me)?|enumera\w*|cuales|quienes)\b', texto) and not tutorial:
        return None
    if (re.search(r'\bque equipos? (?:tiene|tienen|se |fue)|\bcomo (?:estan?|quedo|quedaron|se (?:distribuy|repart|encuentra))\b', texto)
            or re.match(r'^(?:los )?equipos? (?:de|del) ', texto)):
        return None
    # Crear una cuenta desde Usuarios es distinto de importar un relevo.
    if not re.search(r'\bexcel\b|\bimport(?:a(?!nte)|[oe])|relevo|reemplaz|equip|inventario|responsable|reasign|traspas|transfer', texto):
        return None
    if re.match(r'^(?:crea|asigna|transfiere|reasigna|importa|borra|elimina)\b', texto):
        return 'Puedo explicarte el procedimiento, pero no cambiar usuarios ni equipos desde el chat. Para aplicar un relevo usa **Equipos → Importar**, revisa los equipos y el cambio de responsable en la vista previa, y confirma con una cuenta autorizada.'
    if 'inventario anual' in texto:
        return '**Inventario anual** conserva y compara una instantánea; cargar allí un archivo no reasigna los equipos. Para actualizar quién los recibe, usa **Equipos → Importar**: conserva sus identificadores y cambia el responsable en las filas correspondientes. Revisa «Se actualizará» y el cambio de persona antes de confirmar.'
    if re.search(r'sin (?:activar|marcar)|no (?:activo|activas|marco|marcas)|desmarc|opcion desactiv', texto):
        return 'Si no activas **Crear los perfiles que faltan y asignarles sus equipos**, el nombre de una persona nueva puede quedar pendiente de vincular. En el bloque de **personas del Excel** puedes elegir una cuenta existente o crear su perfil con los permisos correspondientes.\n\nNo des por completado el relevo hasta revisar que las filas reconocidas estén vinculadas al responsable correcto. Crear el perfil no crea su correo ni su contraseña.'
    if re.search(r'contrasena|credencial|iniciar sesion|acceso|correo', texto):
        return 'El Excel puede crear el **perfil del trabajador** y vincularle los equipos de sus filas válidas si activas **Crear los perfiles que faltan y asignarles sus equipos**. Requiere importar y `usuarios.editar`.\n\nEse perfil no trae correo, contraseña ni privilegios administrativos. Configura su acceso desde **Usuarios** si necesita iniciar sesión; no reutilices las credenciales de la persona anterior.'
    if re.search(r'patrimoni|\bmac\b|identificador|numero de serie|reconoc|duplic', texto):
        return 'La importación reconoce el mismo equipo por su **código patrimonial** o su **MAC real**, cuando corresponde. Sin ambos, necesita una coincidencia única por nombre estable, ubicación, conjunto y tipo. El número de serie no es un identificador mapeado en este importador.\n\nSi hay datos repetidos, contradictorios o varias coincidencias, la fila queda para revisión y se omite. No inventes identificadores: comprueba en la vista previa que figure **Se actualizará** y el responsable anterior → nuevo.'
    return 'La importación de **Equipos → Importar** puede cambiar al responsable de los mismos equipos. Conserva sus identificadores en el Excel, escribe el nuevo responsable y revisa **Se actualizará** con **persona anterior → persona nueva** antes de confirmar. No hace falta moverlos después uno por uno.\n\nSi la persona no existe, activa **Crear los perfiles que faltan y asignarles sus equipos**; requiere permiso de importación y `usuarios.editar`. Crea un perfil, sin correo ni contraseña. Solo se reasignan las filas válidas reconocidas: las omitidas o ausentes no se trasladan por suposición.\n\nLos equipos conservan su identidad e historial; los tickets mantienen al reportante y afectado originales. Crear una cuenta nueva o desactivar la anterior, por sí solos, no transfiere equipos.'


def responder_ayuda(pregunta):
    texto = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower()) if not unicodedata.combining(c)).strip(' ¿?¡!.')
    concepto = bool(re.search(r'que (?:es|son|significa)|explica|como (?:funciona|se calcula|interpreto)', texto))
    if concepto and re.search(r'horas? (?:programad|trabajad)|jornada programada', texto):
        return 'Las horas programadas salen del horario registrado, con sus ausencias y feriados. No indican cuánto tiempo trabajó una persona ni cuánto dedicó a un ticket. Los tiempos de resolución son otro dato y solo se promedian cuando están registrados.'
    if concepto and re.search(r'sin responsable|pendiente de vincular|uso comun', texto):
        return 'Un equipo sin una cuenta responsable vinculada puede ser compartido por la oficina o tener pendiente su vinculación a una persona. La consulta distingue esos casos cuando existen datos para hacerlo; no significa que el equipo esté abandonado. Puedes revisar sus registros desde el enlace del resultado.'
    if concepto and re.search(r'guias?.*(?:valorad|utilidad)|valoracion.*guia', texto):
        return 'Las guías se comparan por sus valoraciones de utilidad y por cuántas personas votaron. Sin votos significa «Sin datos», no cero. Son valoraciones acumuladas; no demuestran por sí solas que una guía resolviera un ticket.'
    if concepto and 'auditoria' in texto:
        return 'La auditoría conserva quién realizó un cambio, qué registro afectó y cuándo. Esta consulta es exclusiva de administradores y muestra los últimos 15 días conservados, sin valores privados de los cambios. Si no hay registros antiguos, no puedo reconstruirlos ni afirmar que no hubo cambios.'
    importacion = _ayuda_importacion_relevo(texto)
    if importacion:
        return importacion
    explica = bool(re.search(r'que (?:es|significa)|explica|como (?:se calcula|interpreto|leo)', texto))
    if explica:
        conceptos = [
            (r'tiempo.*(?:medio|promedio)|resolucion', 'El tiempo medio suma los minutos de resolución registrados y los divide entre los tickets que tienen ese dato. Un ticket sin tiempo informado no cuenta en ese promedio. No es un tiempo garantizado para el siguiente caso.'),
            (r'satisfaccion|valoracion|calificacion', 'La satisfacción es el promedio de las valoraciones recibidas, en una escala de 1 a 5. Solo cuenta a quienes calificaron: una ausencia de valoraciones significa «sin datos», no cero ni mala atención.'),
            (r'precision|clasificacion', 'La precisión indica qué porcentaje de las clasificaciones evaluadas fue confirmado como correcto. Tener una categoría escrita no demuestra que sea correcta. Sin evaluaciones no se puede calcular la precisión; una muestra pequeña tampoco representa todos los casos.'),
            (r'variacion|comparacion|periodo anterior', 'La variación compara la cantidad de tickets creados con el intervalo anterior de la misma duración. Se calcula como (actual − anterior) ÷ anterior × 100. Si antes hubo cero tickets no calculo ese porcentaje. Una subida significa más reportes, no necesariamente peor servicio.'),
            (r'tickets?.*cerrad|cerrad.*tickets?', 'En este análisis, «cerrados» cuenta los tickets creados dentro de las fechas elegidas que actualmente están cerrados. Es distinto de contar todos los tickets que se cerraron durante esas fechas, porque algunos pudieron crearse antes.'),
            (r'familia|tipo de equipo|tasa de falla', 'Aquí una familia es un tipo de dispositivo, como laptop, monitor o impresora. El porcentaje cuenta cuántos dispositivos de ese tipo tuvieron alguna incidencia durante los últimos doce meses. Si un equipo tuvo cinco tickets, sigue contando como un solo equipo afectado. Este historial no predice fallas futuras.'),
        ]
        for patron, explicacion in conceptos:
            if re.search(patron, texto):
                return explicacion
    if re.fullmatch(r'hola|buenos dias|buenas tardes|buenas noches|buenas', texto):
        return 'Hola. Soy tu asistente de análisis interno. Puedo revisar tickets, inventario y disponibilidad de TI con datos del sistema. Puedes empezar con «¿Qué oficina tiene más incidencias?» o preguntarme para qué sirve cada indicador.'
    if re.fullmatch(r'gracias|muchas gracias|ok|entendido|perfecto', texto):
        return 'Cuando necesites revisar otra cifra, escribe tu pregunta o elige una consulta sugerida. Mantendré el periodo seleccionado salvo que indiques otro.'
    if re.search(r'para que sirve (?:esta |la |nuestra |el |este )?(?:web|pagina|sistema)|que es (?:esta |la )?(?:web|mesa de ayuda)', texto):
        return 'Esta mesa de ayuda organiza el soporte TI de la municipalidad: registra incidencias, permite conversar con soporte, asigna técnicos y conserva el resultado de la atención. También administra equipos, responsables, oficinas y guías de conocimiento.\n\nEn Análisis puedes revisar indicadores y hacer consultas internas. El chatbot TI complementa estas funciones con orientación técnica; ninguno de los dos asistentes modifica registros por su cuenta.'
    if re.search(r'para que sirves|para que sirve (?:(?:este|el|la) )?(?:asistente|modulo|analisis|ia|consulta)|^para que sirve$|que (puedes hacer|haces|funciones tienes|eres)|como (te uso|usarte|funcionas|uso (este|el) asistente)|que (datos|informacion) (puedes|puedo) consultar|que puedo preguntar', texto):
        return 'Te ayudo a consultar los datos de la mesa de ayuda: tickets pendientes con enlaces, calidad del inventario, responsables, PC incompletas, comparación de inventarios anuales, carga y horarios de TI y guías de conocimiento. Los administradores también pueden revisar los cambios conservados en auditoría.\n\nElige una pregunta o búscala por tema. Las consultas reconocidas se calculan en el sistema, sin gastar tokens de Groq. Muestro las fechas, los datos usados y sus límites. Solo consulto información permitida para tu cuenta; no cambio registros.'
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
