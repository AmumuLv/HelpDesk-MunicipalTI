"""Genera documentos de exposición a partir de la política y los módulos revisados.

Requiere python-docx y python-pptx. No consulta datos de usuarios ni el entorno.
"""
from pathlib import Path
from datetime import date
import ast
import zipfile

from docx import Document
from docx.shared import Inches as DI, Pt as DP, RGBColor as DC
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Inches as PI, Pt as PP
from pptx.dml.color import RGBColor as PC
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'presentacion'
OUT.mkdir(parents=True, exist_ok=True)
FECHA = '2 de noviembre de 2026'

# Cada entrada incluye el texto visible y un guion oral en las notas del orador.
SLIDES = [
('HelpDesk Municipal TI', 'Una plataforma para organizar el soporte de la Municipalidad Provincial de Casma',
 ['Incidencias, inventario y atención en un mismo entorno.', 'Inteligencia interna para analizar; chatbot para orientar.', 'Responsabilidades claras y registros vinculados.'],
 'Presento HelpDesk Municipal TI, una plataforma orientada al área de soporte de la Municipalidad Provincial de Casma. Su propósito es reunir las solicitudes, los equipos y el trabajo técnico para que cada atención tenga seguimiento. La inteligencia artificial complementa ese trabajo: aporta análisis y orientación, mientras las decisiones y los cambios siguen bajo responsabilidad humana.'),
('El problema que abordamos', 'Del aviso disperso a una atención con seguimiento',
 ['¿Quién necesita ayuda y quién la está atendiendo?', '¿Qué equipo pertenece a cada persona u oficina?', '¿Qué problemas se repiten y dónde se concentra la demanda?'],
 'El proyecto responde a una necesidad de organización. Cuando los avisos llegan por diferentes medios, resulta difícil conocer su estado, relacionarlos con un equipo y revisar lo ocurrido después. El sistema permite registrar esas solicitudes y consultarlas con un contexto común. Esto describe el problema que busca resolver; no presento una medición de ahorro que todavía no se haya realizado.'),
('La solución y sus beneficiarios', 'Una experiencia para cada responsabilidad',
 ['Trabajador: reporta y sigue su atención.', 'Técnico: identifica, atiende y documenta.', 'Administrador: organiza recursos y accesos.', 'Principal: protege la continuidad de la administración.'],
 'Cada persona dispone de una experiencia adecuada a su función. El trabajador comunica el problema sin necesitar conocimientos de inventario. El técnico precisa el diagnóstico y el equipo real. Los administradores organizan el servicio. La primera cuenta administrativa tiene una protección especial y es la única que puede incorporar nuevos administradores.'),
('Cómo se organiza la información', 'Zona → oficina → trabajadores y equipos',
 ['La ubicación y la responsabilidad son datos distintos.', 'Una PC de escritorio puede formar un conjunto.', 'Laptops e impresoras pueden ser equipos independientes.', 'Persona, oficina y equipo tienen su propio historial.'],
 'La jerarquía organizativa empieza en las zonas y oficinas. Los trabajadores tienen una ubicación, y los equipos tienen ubicación y responsable cuando corresponde. Un conjunto representa una PC de escritorio; no significa todos los dispositivos de una persona. Una laptop o una impresora independiente mantienen su identidad. El historial de un equipo puede incluir a varios responsables sin convertirlos en la misma persona.'),
('Roles y permisos', 'Las casillas amplían tareas; no cambian el rol',
 ['Usuario: alcance personal y portal de ayuda.', 'Técnico: atención y permisos adicionales autorizados.', 'Administrador: gestión integral del servicio.', 'Principal: administrador protegido, no un cuarto rol operativo.'],
 'El código define tres roles operativos: usuario, técnico y administrador. El principal sigue siendo administrador, con un indicador protegido. Los permisos delegables se aplican a técnicos y se comprueban en el servidor. Dar todas las casillas a un técnico no lo transforma en administrador ni le permite gestionar cuentas técnicas o administrativas.'),
('Protección de las cuentas', 'Una jerarquía que evita tomar el control por delegación',
 ['Solo el principal crea o asciende administradores.', 'El técnico autorizado gestiona únicamente usuarios.', 'Otros administradores no intervienen la cuenta principal.', 'Los administradores conservan facultades operativas amplias.'],
 'El técnico autorizado puede gestionar usuarios y restablecer sus contraseñas, pero no las de técnicos o administradores. Los administradores secundarios conservan su gestión habitual, incluso sobre otros secundarios; la excepción es la cuenta principal y la creación de nuevos administradores. Esta protección no impide que un administrador con permisos de eliminación borre registros operativos.'),
('De un reporte a una solución', 'Reportar → identificar → atender → cerrar',
 ['El trabajador indica el problema y a quién afecta.', 'TI confirma el destinatario y el equipo, si corresponde.', 'Se conversa, documenta y controla el tiempo de atención.', 'Se registra la solución y se cierra el caso.'],
 'El reportante es quien envía la solicitud y el afectado es quien necesita atención, cuando se trata de una persona. Pueden coincidir o ser diferentes. Los reportes de oficina se relacionan con ese ámbito. TI debe comprobar la clasificación y el equipo, porque una categoría como impresora no identifica por sí sola una unidad concreta. Los estados actuales son nuevo, en progreso, en espera y cerrado.'),
('Inventario que acompaña a la atención', 'Ubicación, responsable y antecedentes',
 ['Registro de equipos y componentes de escritorio.', 'Importación y exportación del inventario.', 'Calidad de datos y campos pendientes.', 'Consulta de incidencias y cambios de responsable.'],
 'El inventario permite conocer qué existe, dónde se encuentra y quién lo tiene asignado. La calidad de datos muestra qué información falta para poder completarla. Cuando se registra una incidencia sobre un componente de una PC, se debe conservar el contexto de su conjunto. La reasignación de un equipo no transfiere la identidad ni los tickets personales del trabajador anterior.'),
('Inventario anual y equipo TI', 'Control periódico y organización del trabajo',
 ['Campañas con instantánea, comparación y verificación.', 'Seguimiento de diferencias y cierre de campaña.', 'Horarios, ausencias y disponibilidad del equipo TI.', 'SLA para priorizar y vigilar plazos de atención.'],
 'El inventario anual conserva una referencia de los equipos incluidos y ayuda a comparar, verificar y cerrar la campaña. No reemplaza una revisión física. Los horarios y ausencias apoyan la organización de técnicos, mientras el SLA permite vigilar plazos. La disponibilidad y las sugerencias de asignación son apoyo para la decisión del responsable.'),
('IA interna: el apoyo que ya está integrado', 'Reglas, consultas verificables y análisis estadístico',
 ['Sugiere clasificación, prioridad y atención.', 'Responde consultas reconocidas con datos del sistema.', 'Analiza recurrencia, carga, tendencias y calidad.', 'El técnico acepta, corrige o descarta las sugerencias.'],
 'La inteligencia del proyecto no se limita al chatbot. El motor interno utiliza reglas y consultas a los registros, y combina análisis estadístico o modelos cuando dispone de información suficiente. Permite revisar oficinas con incidencias, carga técnica, datos faltantes y recurrencia. Los indicadores son orientativos: no son diagnósticos ciertos ni probabilidades futuras validadas. Las consultas internas reconocidas no consumen tokens de Groq.'),
('Chatbot TI: conversación con contexto', 'Orientación para técnicos y administradores',
 ['Considera la sección abierta y filtros permitidos.', 'Consulta datos mediante herramientas de lectura acotadas.', 'Guarda conversaciones por cuenta.', 'No crea, modifica ni elimina registros.'],
 'El chatbot utiliza un proveedor externo configurado para conversar y orientar al equipo TI. Puede consultar información permitida del sistema, sin recibir comandos libres ni secretos. No ve todo el código ni la pantalla completa y no aprende automáticamente cada cambio. El contexto se prepara desde el servidor. Actualmente el límite configurado para técnicos es de quince consultas por conversación; este límite no equivale a la cuota del proveedor.'),
('Dos apoyos de IA, funciones distintas', 'Cifras verificables y conversación técnica',
 ['Motor interno: datos, reglas y ayuda local.', 'Chatbot: lenguaje abierto y orientación contextual.', 'Ambos mantienen el alcance de autorización.', 'El servicio básico continúa sin el proveedor externo.'],
 'Si necesito una cifra reconocida por el motor interno, puedo obtenerla mediante una consulta sin acudir al proveedor. Si necesito explicar un procedimiento o explorar un problema técnico, el chatbot aporta conversación. Las recomendaciones no sustituyen la revisión del técnico. Las respuestas sobre normas o requisitos institucionales deben contrastarse con fuentes oficiales vigentes antes de utilizarlas como criterio de decisión.'),
('Reportes y conocimiento compartido', 'La atención también deja información para mejorar',
 ['Informes de tickets, inventario y carga del equipo.', 'Análisis por periodo, oficina y zona.', 'Base de conocimiento con guías reutilizables.', 'Auditoría para revisar movimientos relevantes.'],
 'Los reportes permiten convertir el trabajo registrado en información para gestión. Debemos interpretar el periodo y el alcance: inventario actual no significa inventario histórico, y cantidad de tickets no significa gravedad. La base de conocimiento conserva soluciones reutilizables. La auditoría registra acciones relevantes, pero su retención general actual es de quince días, por lo que no debo presentarla como un registro indefinido.'),
('Cuando cambia un trabajador', 'Cada persona conserva su propia identidad',
 ['Crear una cuenta nueva para el reemplazo.', 'Desactivar la anterior y revocar sus sesiones.', 'Archivo automático después de 30 días de baja.', 'Transferir equipos desde inventario y conservar antecedentes.'],
 'No se cambia el nombre de una cuenta para entregársela a otra persona. Se crea la nueva, se desactiva la anterior y se reasignan los equipos necesarios. Después de treinta días completos la cuenta anterior pasa a archivada; el proceso se comprueba al arrancar el worker y cada hora. En Usuarios puede consultarse con los filtros de estado y reactivarse si regresa. Los tickets mantienen sus referencias originales.'),
('Cómo funciona por dentro', 'Web y datos centralizados en el equipo servidor',
 ['React y TypeScript para la interfaz.', 'FastAPI y MongoDB para reglas y registros.', 'Redis, worker y eventos para tareas y actualización.', 'Docker y volúmenes persistentes para ejecutar y conservar.'],
 'Los navegadores acceden a un servidor central. La interfaz se comunica con la API, que valida permisos y utiliza MongoDB. Redis y el worker apoyan las tareas periódicas; los eventos permiten actualizar cuentas abiertas. Las fotos y adjuntos se guardan en un volumen del servidor, y MongoDB conserva sus referencias. El repositorio contiene código, no las claves ni todos los datos de la instalación.'),
('Demostración y preparación del lanzamiento', 'Un recorrido breve y comprobable',
 ['Mostrar un reporte y su atención desde TI.', 'Consultar equipo, oficina e historial.', 'Comparar la IA interna con el chatbot.', 'Revisar permisos, archivados y reportes.'],
 'Para demostrarlo usaré cuentas autorizadas y datos de demostración en un entorno adecuado. Mostraré el reporte, la atención, el inventario y una consulta de cada asistente. Las pruebas recientes de cuentas y archivo han pasado, pero no equivalen a certificar toda la aplicación. Antes de publicar faltan validar el servidor definitivo, el dominio, HTTPS, recuperación y una revisión de seguridad actualizada.'),
('Valor del proyecto', 'Orden, trazabilidad y apoyo al equipo TI',
 ['Una solicitud puede relacionarse con su contexto real.', 'La información permanece cuando cambian las personas.', 'La IA complementa la atención y el análisis.', 'El siguiente paso es validar su operación institucional.'],
 'El valor principal es relacionar solicitudes, personas, equipos y decisiones en una misma plataforma. El proyecto facilita consultar antecedentes y distribuir responsabilidades. Su impacto debe evaluarse en uso real con indicadores de tiempos, calidad de datos y satisfacción. La meta es una herramienta útil para la municipalidad, con un despliegue administrado y mejoras guiadas por la experiencia del equipo.'),
]

SECCIONES = [
('1. Presentación ejecutiva', [
 'HelpDesk Municipal TI es una plataforma web de mesa de ayuda orientada a la Municipalidad Provincial de Casma. Integra registro y seguimiento de incidencias, inventario, organización institucional, trabajo del equipo TI, conocimiento y análisis. Su propósito es que las solicitudes de soporte puedan relacionarse con las personas, oficinas y equipos involucrados.',
 'Este informe describe la implementación revisada al 02/11/2026. Distingue las funciones existentes de las condiciones de despliegue aún pendientes. No acredita una certificación de seguridad, una adopción institucional definitiva ni una reducción de tiempos que no se haya medido.',
 'El punto fuerte es la relación entre los módulos: un ticket no queda aislado, sino vinculado a su contexto; el inventario acompaña la atención; la IA interna ayuda a consultar y priorizar; y el chatbot aporta orientación conversacional bajo permisos de lectura.'
 ]),
('2. Objetivo, alcance y forma de uso', [
 'El objetivo general es organizar la atención técnica institucional con seguimiento y responsabilidades identificables. Como objetivos específicos, se busca centralizar solicitudes, conocer la asignación del inventario, documentar soluciones, vigilar plazos y ofrecer información de apoyo a las decisiones del área TI.',
 'El trabajador utiliza el portal para reportar un problema, consultar sus casos y conversar con soporte cuando el flujo del ticket lo habilita. El técnico utiliza el panel para confirmar el diagnóstico y el equipo, atender, documentar y cerrar. El administrador organiza personas, equipos y configuración. El principal conserva las protecciones especiales de titularidad.',
 'El sistema es una herramienta de soporte e inventario. No debe presentarse como reemplazo de todos los sistemas municipales, de un control biométrico de asistencia, de una revisión patrimonial física ni de la decisión técnica profesional.'
 ]),
('3. Jerarquía organizativa y jerarquía de acceso', [
 'La estructura organizativa es Zona → Oficina. Las personas pueden estar relacionadas con una oficina y una zona; los equipos registran ubicación y, cuando corresponde, un responsable. Esas relaciones permiten consultar la actividad del lugar y los equipos vinculados. Estar en una oficina no concede permisos administrativos.',
 'La jerarquía de acceso utiliza tres roles operativos: usuario, técnico y administrador. El administrador principal conserva el rol administrador y añade un indicador protegido. Por tanto, puede hablarse de cuatro perfiles de autoridad para explicar el funcionamiento, pero no de cuatro valores de rol en el código.',
 'La asignación física de un equipo y el rol de la cuenta son independientes. Un técnico puede tener equipos propios y un usuario puede ser responsable de varios dispositivos; eso no altera su autoridad sobre las funciones del sistema.',
 'Un conjunto representa exclusivamente una PC de escritorio. El usuario puede tener un conjunto y, además, una laptop u otros equipos independientes. Los dispositivos compartidos pertenecen al contexto de la oficina y no deben atribuirse a una persona solo porque ella envió el aviso.'
 ]),
('4. Usuario: alcance y límites', [
 'El usuario dispone de perfil personal, cambio de contraseña mediante el flujo personal, acceso a sus solicitudes, creación de reportes, respuestas, adjuntos, valoración y reapertura de casos propios conforme a las reglas de cada operación. Puede consultar la base de conocimiento, sus equipos y la vista permitida de equipos de oficina, y elegir su preferencia de ayuda automática.',
 'El portal permite distinguir si la solicitud corresponde a la propia persona, a un compañero o a la oficina. La elección inicial del trabajador orienta el registro; TI debe confirmar el destinatario y el equipo real. Elegir una categoría como impresora no identifica de forma inequívoca una de varias impresoras.',
 'El usuario no obtiene herramientas de administración por tener permisos adicionales guardados por error. La función que calcula los permisos efectivos solo aplica la matriz delegada al rol técnico. Tampoco puede crear cuentas técnicas o administrativas, otorgar permisos o convertir su perfil en otro rol.'
 ]),
('5. Técnico: atención y delegación controlada', [
 'El técnico tiene funciones base para operar tickets, asignarse casos, cambiar estados, dejar notas internas, responder y documentar la atención. Puede consultar inventario, organización, directorio, equipo TI y horarios dentro del alcance de las rutas. También puede crear artículos de conocimiento conforme a los controles del módulo.',
 'Las tareas adicionales se habilitan individualmente en Configuración → Permisos por rol. Están desactivadas inicialmente. Activarlas no transforma al técnico en administrador ni le permite delegarlas a otras personas. El servidor consulta la cuenta vigente para autorizar las peticiones; ocultar un botón en el navegador es solo una ayuda visual.',
 'Con Gestionar cuentas de usuarios puede crear, editar, desactivar, reactivar y restablecer contraseñas de cuentas de rol usuario. No puede crear técnicos o administradores ni gestionar sus cuentas, contraseñas, fotografías o sesiones. Conserva la edición básica de su propio perfil y su cambio personal de contraseña.',
 'Con todos los permisos delegables, mantiene estas restricciones jerárquicas, pero puede ejecutar acciones operativas amplias e incluso destructivas autorizadas. Por ello se recomienda habilitar las funciones necesarias para su responsabilidad real y retirar las que deje de necesitar.'
 ]),
('6. Administrador y administrador principal', [
 'El administrador conserva gestión integral de tickets, inventario, organización, cuentas, configuración, reportes y delegación de permisos a técnicos. Puede crear técnicos y usuarios. Los administradores secundarios conservan gestión sobre otros administradores secundarios, incluyendo los cambios admitidos de datos, contraseña, estado y degradación de rol.',
 'Solo el principal puede crear nuevas cuentas administrativas o ascender una cuenta a administrador. En una instalación vacía es la primera cuenta creada mediante el asistente de instalación. En instalaciones existentes, la migración selecciona al administrador activo más antiguo; un índice parcial único impide dos principales.',
 'Otras cuentas no pueden modificar los datos, correo, contraseña o foto del principal ni consultar o cerrar sus sesiones. El principal puede actualizar su propio perfil y cambiar la contraseña aportando la actual. El flujo de restablecimiento administrativo no permite restablecer la contraseña del principal, incluso desde su propia cuenta.',
 'La cuenta principal no se puede desactivar ni degradar desde la aplicación. No existe un botón para transferir esta titularidad. Si se pierde el acceso, la recuperación requiere intervención autorizada desde el servidor.',
 'La protección es de identidad y continuidad de acceso. No elimina los permisos de borrado operativos de los administradores ni protege contra el control directo del servidor o de MongoDB. Es una distinción importante al explicar la seguridad al responsable institucional.'
 ]),
('7. Cómo se aplica la autorización', [
 'La API identifica la sesión y consulta el documento vigente de la cuenta. A partir del rol calcula permisos base y, para técnicos, los adicionales reconocidos. Las rutas y servicios verifican la operación y el objetivo. Una petición enviada manualmente debe someterse a esas comprobaciones aunque el botón no aparezca en la interfaz.',
 'El cambio de permisos se aplica en las peticiones siguientes sin convertir el token existente en una autorización permanente. En las escrituras sensibles de cuentas, las condiciones incluyen el rol y la protección principal observados; si la jerarquía cambió durante la operación, se devuelve un conflicto para evitar aplicar una autorización obsoleta.',
 'Las entradas de creación y edición no aceptan asignar el indicador protegido como una opción normal. Las pruebas contemplan intentos de escalada, falsificación del indicador, cambios de rol concurrentes y unicidad de la cuenta principal. Estos controles no sustituyen proteger el sistema operativo, Docker, el repositorio privado y los secretos del servidor.'
 ]),
('8. Flujo de tickets y significado de los participantes', [
 'Reportante es quien envía la solicitud. Afectado es la persona que requiere la atención, cuando el caso es personal. Si reporta para sí mismo, ambos identificadores pueden coincidir sin que existan dos tickets. Si reporta para un compañero, el autor sigue siendo el reportante y el compañero es el afectado.',
 'Cuando el problema pertenece a la oficina, el ámbito y los equipos compartidos deben reflejar ese contexto. La categoría describe el tipo de problema; no decide por sí sola la propiedad del equipo. TI debe comprobar el vínculo durante la edición y evitar interpretar automáticamente un reporte ambiguo como incidencia personal.',
 'El flujo actual utiliza Nuevo, En progreso, En espera y Cerrado. La asignación de un técnico lleva el caso a En progreso; no hay un estado operativo separado llamado Asignado. Al finalizar se registra la solución y se cierra, sin un paso adicional llamado Resuelto. Se mantiene lectura compatible de datos antiguos cuando corresponde.',
 'La conversación y los adjuntos permiten precisar lo que el trabajador no supo identificar. Las notas internas apoyan el trabajo de TI y tienen su propio alcance. El SLA permite vigilar plazos de atención según la configuración y el calendario; el historial registra los acontecimientos relevantes del caso.'
 ]),
('9. Cambio de trabajador, desactivación y archivo', [
 'Cada persona debe tener su propia identidad. Cuando un trabajador se retira, se desactiva su cuenta y se crea otra para el reemplazo. Cambiar el nombre de la misma cuenta para entregarla a alguien distinto mantiene el mismo identificador interno y puede atribuir el historial de forma confusa.',
 'Al desactivar se registra la fecha de baja, se invalidan sesiones y se conserva la identidad. Tras treinta días completos de baja, el worker archiva automáticamente la cuenta; comprueba al iniciar y después cada hora. Para bajas antiguas sin fecha conocida, el plazo comienza en la primera comprobación. El principal queda excluido.',
 'En Usuarios, el filtro Estado permite ver Activos, Desactivados, Archivados o Todos. La ficha del archivado conserva sus referencias y muestra fechas de baja y archivo. Quien tenga autorización sobre esa cuenta puede reactivarla; se limpian las fechas de baja y archivo y debe iniciarse una nueva sesión.',
 'Los equipos no se transfieren ni se eliminan automáticamente al archivar. TI los reasigna desde inventario para dejar constancia del cambio. Los tickets personales anteriores conservan sus referencias originales, mientras el historial del equipo u oficina puede reunir incidencias de diferentes personas claramente identificadas.',
 'Archivo de cuenta no equivale a conservación indefinida de toda la auditoría. La tarea general actual elimina registros de auditoría de más de quince días. Antes de usarla como evidencia de largo plazo, la institución debe definir y configurar su política de retención. El historial propio de tickets y asignaciones es distinto de esa colección de auditoría.'
 ]),
('10. Módulos incluidos en el proyecto', [
 'Resumen: presenta indicadores del servicio. Tickets: concentra casos abiertos, asignaciones, historial cerrado, atención y edición. Inventario: registro de equipos, ubicación, responsable, características, conjuntos y antecedentes. Calidad: identifica información pendiente y ayuda a completarla sin confundir dato ausente con equipo averiado.',
 'Importación: procesa los formatos admitidos de inventario y valida la información antes de incorporarla. Inventario anual: crea campañas con una instantánea, comparación con Excel, verificación física guiada, seguimiento de diferencias y cierre. Una campaña no sustituye comprobar físicamente el inventario.',
 'Zonas y oficinas: mantiene la estructura institucional y permite consultar recursos e incidencias por ubicación. Usuarios: administra las identidades y su ciclo de vida. Equipo TI: presenta perfiles, disponibilidad, horarios y ausencias para organizar el trabajo.',
 'Base de conocimiento: conserva artículos, categorías, plantillas y respuestas reutilizables según permisos. Reportes: ofrece salidas de tickets, inventario, carga técnica, analítica y movimientos, con filtros y exportaciones admitidas por cada informe. Auditoría: permite revisar acciones relevantes dentro de la retención configurada.',
 'Configuración: incluye datos institucionales, ayudas automáticas, SLA y horarios, notificaciones, permisos y opciones del sistema. Mi perfil: datos personales, fotografía, preferencias y seguridad. La interfaz incluye temas claro y oscuro y adaptación a tamaños de pantalla.'
 ]),
('11. Inteligencia interna: funciones, valor y límites', [
 'El motor interno combina reglas de clasificación, consultas autorizadas y herramientas de análisis estadístico o modelos cuando dispone de información suficiente. Sugiere categoría, prioridad y asignación; utiliza el contexto disponible para apoyar la atención y conserva señales de aceptación, corrección o descarte. La persona decide si aplica una propuesta.',
 'En Análisis IA, las consultas de datos reconocidas calculan resultados con registros del sistema. Incluyen preguntas por oficinas y zonas, recurrencia, carga, fechas, calidad y otros alcances implementados. Las respuestas muestran su contexto y fuentes. La ayuda local explica funciones y puede responder preguntas sobre el uso del módulo.',
 'Estas consultas reconocidas funcionan sin invocar Groq ni consumir sus tokens, y no comparten el límite de quince consultas del chatbot. El proveedor generativo opcional del motor interno está desactivado según la configuración documentada; las reglas y consultas siguen funcionando.',
 'Los paneles apoyan el análisis de tendencias, riesgo de SLA, causas recurrentes, carga técnica y calidad del inventario. El indicador de fallas es orientativo y depende de la cantidad y calidad de datos; no es una probabilidad futura validada. Una oficina con más tickets no es necesariamente la de mayor gravedad.',
 'La escritura progresiva es un efecto visual local y no supone una llamada adicional al proveedor por cada letra. La IA interna no tiene comprensión universal: si una pregunta no está reconocida, puede requerir reformulación o utilizar el chatbot para orientación abierta.'
 ]),
('12. Chatbot externo TI: contexto y acceso de lectura', [
 'El chatbot está dirigido a técnicos y administradores y utiliza el proveedor externo configurado, actualmente documentado como Groq. Recibe la ruta abierta y filtros permitidos, además de contexto funcional preparado por el servidor. No obtiene una vista ilimitada del repositorio, la pantalla completa ni los formularios sin guardar.',
 'Las herramientas de consulta ofrecen lecturas acotadas de tickets, inventario, organización, directorio, campañas y otros ámbitos autorizados. El servidor comprueba permisos y usa proyecciones de campos permitidos. No permite elegir cualquier colección, ejecutar comandos libres ni realizar escrituras.',
 'No se proporcionan contraseñas, hashes, claves API o sesiones. Las consultas excluyen contenidos privados definidos por el servicio, como cuerpos de conversaciones, notas internas y archivos adjuntos. Aun así, cierta información autorizada se transmite a un proveedor externo: no debe describirse como un procesamiento íntegramente local.',
 'Las conversaciones se guardan por cuenta y se pueden retomar o eliminar. El límite configurado para técnicos es de quince consultas por conversación; para administradores, cien. Cada cuenta puede conservar hasta cien conversaciones. Abrir otra conversación no reinicia la cuota externa. No se incluyen cifras comerciales del proveedor porque deben revisarse en su consola vigente.',
 'La orientación abarca soporte técnico y contexto funcional municipal. Las respuestas sobre normativa, requisitos legales o datos institucionales vigentes requieren contraste con fuentes oficiales. El contexto del proyecto se prepara explícitamente: no es un entrenamiento continuo automático ni garantiza que cada respuesta sea correcta.'
 ]),
('13. Arquitectura, almacenamiento y actualización', [
 'El navegador utiliza una interfaz React con TypeScript. La API FastAPI concentra reglas, sesiones y autorización. MongoDB conserva registros y relaciones; Redis apoya caché, colas y avisos. El worker ejecuta tareas como revisión de SLA, limpieza, modelos y archivo de cuentas. Docker Compose organiza los servicios y los volúmenes persistentes.',
 'Las fotografías de perfil se guardan como archivos en /data/uploads/fotos; los adjuntos y notas de voz, bajo /data/uploads. MongoDB conserva sus referencias y metadatos. Las exportaciones se generan bajo /data/exports. Los volúmenes pertenecen al equipo servidor; descargar el código desde GitHub no descarga las oficinas, cuentas, archivos o base de datos de una instalación.',
 'La actualización entre cuentas se apoya en cambios de MongoDB, Redis y WebSocket autenticado para refrescar la información visible. Su funcionamiento requiere servicios y conexión disponibles; una interrupción de red puede retrasar los cambios. No debe prometerse simultaneidad absoluta bajo cualquier condición.',
 'Las fotos y adjuntos pasan por el control antivirus configurado antes de almacenarse. Los controles de formato, tamaño y acceso complementan esa revisión. El espacio disponible depende del almacenamiento y límites del despliegue, y debe supervisarse junto con la memoria, las colas y los datos persistentes.'
 ]),
('14. Pruebas verificadas y preparación institucional', [
 'La documentación de roles registra cincuenta y cinco casos del servidor y tres recorridos de navegador aprobados en la revisión de jerarquía del 30/10/2026. Los catorce casos de jerarquía repetidos están incluidos en esos cincuenta y cinco y no se deben sumar como casos únicos adicionales.',
 'En la incorporación del archivo de cuentas se verificaron catorce casos de jerarquía y dos casos nuevos de archivo. Estos últimos comprueban el plazo, los filtros, conservación del ticket, reactivación, tratamiento de bajas sin fecha y exclusión del principal. Se aprobó la compilación de producción y los servicios locales respondieron correctamente. En la creación de este informe se revisaron fuentes; no se ejecutó una auditoría general nueva.',
 'Quedan por validar las condiciones del servidor definitivo, dominio, HTTPS público, disponibilidad desde las ubicaciones autorizadas, recuperación y operación institucional. La seguridad debe volver a analizarse con las imágenes y dependencias del despliegue real. No se afirma que existan cero vulnerabilidades ni que las pruebas locales certifiquen el futuro entorno público.',
 'Para la operación se recomienda identificar responsables de administración y recuperación, acordar el catálogo de oficinas, capacitar al equipo, definir retención y conservación, y medir tiempos de atención, calidad de datos y satisfacción. Estas son recomendaciones para el lanzamiento, no funciones pendientes presentadas como ya entregadas.'
 ]),
('15. Guía de exposición y demostración', [
 'Duración sugerida: entre doce y quince minutos, ajustando la explicación a la audiencia. Las diapositivas incluyen notas del orador con un guion que puede leerse desde la vista del moderador. Para una exposición breve, priorizar las diapositivas 1, 3, 4, 5, 7, 10, 11, 14 y 17.',
 'Demostración sugerida: entrar con una cuenta de usuario autorizada; mostrar un reporte; cambiar al panel TI; identificar destinatario y equipo; revisar conversación y solución; abrir el historial del equipo u oficina; realizar una consulta reconocida de la IA interna; mostrar orientación del chatbot; consultar un reporte y el filtro de archivados.',
 'Preparar datos ficticios o un entorno autorizado para la demostración. Evitar mostrar correos personales, contraseñas, claves o el archivo de entorno. Si el proveedor externo está sin cuota, presentar su función con las diapositivas y continuar con el motor interno. La exposición no requiere borrar datos ni cambiar permisos reales.',
 'Respuesta de cierre sugerida: «El proyecto reúne la atención, el inventario y el análisis en un mismo flujo. La información permanece cuando cambian las personas y la IA ayuda al equipo sin asumir sus decisiones. El siguiente paso es validar su operación en el entorno institucional definitivo».'
 ]),
]

MATRIZ = [
['Acción', 'Principal', 'Administrador', 'Técnico', 'Usuario'],
['Atender y operar tickets', 'Sí', 'Sí', 'Base + alcance', 'Sus casos'],
['Crear usuarios / gestionar sus cuentas', 'Sí', 'Sí', 'Con delegación', 'No'],
['Crear o gestionar técnicos', 'Sí', 'Sí', 'No', 'No'],
['Crear / ascender administradores', 'Sí', 'No', 'No', 'No'],
['Gestionar administradores secundarios', 'Sí', 'Sí', 'No', 'No'],
['Asignar permisos a técnicos', 'Sí', 'Sí', 'No', 'No'],
['Modificar al principal', 'Perfil propio', 'No', 'No', 'No'],
['Desactivar / degradar al principal', 'No', 'No', 'No', 'No'],
['Restablecer contraseñas de usuarios', 'Sí', 'Sí', 'Con delegación', 'No'],
['Cambiar su contraseña con la actual', 'Sí', 'Sí', 'Sí', 'Sí'],
['Crear / editar / eliminar equipos', 'Sí', 'Sí', 'Según delegación', 'No'],
['Análisis y exportaciones', 'Sí', 'Sí', 'Según delegación', 'No'],
['Chatbot TI de lectura', 'Sí', 'Sí', 'Sí', 'No'],
['Reactivar cuentas archivadas', 'Sí', 'Sí', 'Solo usuarios; delegación', 'No'],
]

def sombrear(celda, color):
    pr = celda._tc.get_or_add_tcPr()
    e = OxmlElement('w:shd'); e.set(qn('w:fill'), color); pr.append(e)

doc = Document()
sec = doc.sections[0]
sec.top_margin = sec.bottom_margin = DI(.75)
sec.left_margin = sec.right_margin = DI(.8)
sec.header.paragraphs[0].text = 'HELPDESK MUNICIPAL TI  |  MUNICIPALIDAD PROVINCIAL DE CASMA'
normal = doc.styles['Normal']; normal.font.name = 'Calibri'; normal.font.size = DP(11)
normal.paragraph_format.space_after = DP(8)
normal.paragraph_format.line_spacing = 1.14
for name in ['Title', 'Heading 1', 'Heading 2']:
    doc.styles[name].font.name = 'Calibri'
    doc.styles[name].font.color.rgb = DC.from_string('163C66')
footer = sec.footer.paragraphs[0]
footer.text = 'Informe funcional • 02/11/2026                                      Página '
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE'); footer._p.append(field)
doc.add_paragraph('DOCUMENTO DE PRESENTACIÓN', 'Subtitle')
doc.add_heading('HelpDesk Municipal TI', 0)
doc.add_paragraph('Jerarquías, roles, permisos y funcionamiento integral del proyecto', 'Subtitle')
doc.add_paragraph('Municipalidad Provincial de Casma')
doc.add_paragraph(FECHA)
doc.add_paragraph('Informe para exposición y consulta del equipo TI. Elaborado a partir del código y la documentación del proyecto; no contiene credenciales ni registros personales.')
doc.add_heading('Contenido', 1)
for titulo, _ in SECCIONES:
    doc.add_paragraph(titulo)
doc.add_paragraph('Anexos: matriz comparativa, catálogo de permisos delegables, casos prácticos y fuentes internas.')
doc.add_page_break()
for titulo, parrafos in SECCIONES:
    doc.add_heading(titulo, 1)
    for texto in parrafos:
        doc.add_paragraph(texto)

doc.add_page_break()
doc.add_heading('Anexo A. Matriz comparativa de autoridad', 1)
doc.add_paragraph('Los permisos delegables no sustituyen las restricciones sobre la cuenta objetivo. «Sí» no elimina las validaciones de la operación, las dependencias o los límites de seguridad.')
tabla = doc.add_table(rows=0, cols=5); tabla.style = 'Light Shading Accent 1'
for n, fila in enumerate(MATRIZ):
    celdas = tabla.add_row().cells
    for c, texto in zip(celdas, fila):
        c.text = texto
        if n == 0: sombrear(c, 'DCEAF6')

doc.add_heading('Anexo B. Catálogo completo de permisos delegables', 1)
arbol = ast.parse((ROOT/'backend/app/domain/permissions.py').read_text(encoding='utf-8'))
permisos = next(ast.literal_eval(n.value) for n in arbol.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'PERMISOS_DELEGABLES')
grupo = None
for clave, datos in permisos.items():
    if datos['grupo'] != grupo:
        grupo = datos['grupo']; doc.add_heading(grupo, 2)
    p = doc.add_paragraph()
    p.add_run(datos['etiqueta'] + ' — ').bold = True
    p.add_run(datos['descripcion'] + f' Clave: {clave}.')
doc.add_paragraph('Todos empiezan desactivados para el técnico. Los administradores tienen autoridad general, con las excepciones jerárquicas aplicadas por los servicios de cuentas.')

doc.add_heading('Anexo C. Casos para explicar la jerarquía', 1)
casos = [
('Un técnico recibe todas las casillas', 'Continúa siendo técnico. Puede ejecutar las operaciones delegables, pero en cuentas solo gestiona usuarios. No puede otorgarse un rol superior.'),
('Un administrador intenta crear otro administrador', 'La API rechaza la operación si no es el principal. Puede seguir creando usuarios y técnicos.'),
('Un administrador intenta desactivar a otro secundario', 'La política actual conserva esa facultad de gestión. La cuenta principal permanece protegida. No debe explicarse como si todos los administradores estuvieran protegidos entre sí.'),
('Un técnico deja de tener permiso para gestionar usuarios', 'Las peticiones siguientes se comprueban contra sus permisos actuales y pierden esa autorización. No necesita conservarse el acceso hasta que caduque el token.'),
('Un trabajador se retira y llega un reemplazo', 'Se crean identidades distintas, se desactiva la anterior y se transfieren los equipos necesarios desde inventario. Al archivarse, los tickets previos mantienen sus referencias.'),
('Se pierde la contraseña del principal', 'No se restablece desde otro administrador. Hace falta un procedimiento autorizado en el servidor. La continuidad exige custodiar y definir esa recuperación.'),
('Se pregunta a la IA que elimine un ticket', 'El chatbot carece de herramientas de escritura. La eliminación solo puede realizarse en el módulo correspondiente por una cuenta autorizada.'),
('Se pide conservar auditoría durante meses', 'La retención general actual es de quince días. Hace falta acordar y ajustar la política antes de ofrecer conservación prolongada. Archivar una cuenta no amplía esa retención.'),
]
for titulo, texto in casos:
    doc.add_heading(titulo, 2); doc.add_paragraph(texto)

doc.add_heading('Anexo D. Fuentes internas revisadas', 1)
fuentes = [
 'backend/app/domain/permissions.py: permisos base y las 20 capacidades delegables.',
 'backend/app/services/usuario_service.py y auth_service.py: gestión de cuentas, sesiones, bajas y archivo.',
 'backend/app/migrations/m027_administrador_principal.py: selección y unicidad del principal.',
 'backend/app/worker/main.py: archivo horario y retención general de auditoría de quince días.',
 'backend/app/domain/constants.py: roles y estados vigentes de tickets.',
 'backend/app/services/ia_service.py, analitica_service.py y ml_service.py: reglas, análisis e indicadores.',
 'backend/app/services/campana_service.py y reportes_service.py: campañas y exportaciones.',
 'frontend/src/Rutas.tsx: módulos y pantallas disponibles.',
 'docs/ROLES_Y_PERMISOS.md, docs/CHATBOT_TI.md y docs/ALMACENAMIENTO.md: políticas y operación documentadas.',
 'backend/tests/test_jerarquia_cuentas.py y test_archivo_usuarios.py: pruebas específicas de esta política.',
]
for texto in fuentes: doc.add_paragraph(texto, 'List Bullet')
doc.add_paragraph('Los datos comerciales de proveedores y la validez de normas externas no se verificaron para este documento. Los resultados de pruebas citados corresponden a las ejecuciones descritas, no a una nueva suite general realizada al generar el informe.')
docx = OUT/'Informe_jerarquias_y_proyecto_HelpDesk_MunicipalTI.docx'
doc.save(docx)

# Presentación panorámica: azul nocturno, tarjetas de alto contraste y acentos cian.
prs = Presentation(); prs.slide_width = PI(13.333); prs.slide_height = PI(7.5)
NAVY='091729'; PANEL='122A43'; WHITE='F3F8FF'; MUTED='B9CBDF'; CYAN='48D8ED'; GOLD='EBC16B'

def cuadro(slide, x, y, w, h, color, round=False):
    sh=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if round else MSO_SHAPE.RECTANGLE, PI(x),PI(y),PI(w),PI(h))
    sh.fill.solid(); sh.fill.fore_color.rgb=PC.from_string(color); sh.line.fill.background()
    return sh

def texto(slide, x,y,w,h, content, size=22, color=WHITE, bold=False):
    sh=slide.shapes.add_textbox(PI(x),PI(y),PI(w),PI(h))
    tf=sh.text_frame; tf.word_wrap=True
    tf.margin_left=tf.margin_right=PI(.01); tf.margin_top=PI(.01); tf.margin_bottom=0
    for i, line in enumerate(content.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text=line; p.font.name='Aptos'; p.font.size=PP(size); p.font.bold=bold; p.font.color.rgb=PC.from_string(color)
        p.space_after=PP(6)
    return sh

for idx, (titulo, subtitulo, puntos, guion) in enumerate(SLIDES,1):
    sl=prs.slides.add_slide(prs.slide_layouts[6])
    sl.background.fill.solid(); sl.background.fill.fore_color.rgb=PC.from_string(NAVY)
    cuadro(sl,0,0,13.333,.075,CYAN)
    texto(sl,.65,.33,11.9,.35,'MUNICIPALIDAD PROVINCIAL DE CASMA  /  SOPORTE TI',11,CYAN,True)
    texto(sl,.65,1.02,12.0,1.0,titulo,34,WHITE,True)
    texto(sl,.65,2.05,11.9,.75,subtitulo,21,MUTED)
    # Dos columnas: lectura breve, sin listas largas proyectadas.
    for n,punto in enumerate(puntos):
        x=.65+(n%2)*6.13; y=3.05+(n//2)*1.5
        cuadro(sl,x,y,5.9,1.27,PANEL,True)
        texto(sl,x+.22,y+.15,.45,.45,f'{n+1:02}',16,CYAN,True)
        texto(sl,x+.87,y+.17,4.73,.94,punto,20)
    cuadro(sl,.65,6.81,12,.012,'25445F')
    texto(sl,.65,7.0,11,.25,'HELPDESK MUNICIPAL TI  •  Presentación funcional  •  02/11/2026',10,MUTED)
    texto(sl,12.0,6.97,.7,.3,f'{idx:02} / {len(SLIDES)}',10,GOLD)
    sl.notes_slide.notes_text_frame.text = f'GUION DEL EXPOSITOR\n\n{guion}\n\nTiempo sugerido: 35–50 segundos. Diapositiva {idx} de {len(SLIDES)}.'

pptx = OUT/'Presentacion_HelpDesk_MunicipalTI.pptx'
prs.save(pptx)

# Verifica integridad, contenido, guiones y límites geométricos del documento.
for ruta in (docx,pptx):
    with zipfile.ZipFile(ruta) as z:
        assert z.testzip() is None
assert len(Presentation(pptx).slides)==17
assert len(Document(docx).paragraphs)>150
for slide in Presentation(pptx).slides:
    assert 'GUION DEL EXPOSITOR' in slide.notes_slide.notes_text_frame.text
    for shape in slide.shapes:
        assert shape.left>=0 and shape.top>=0
        assert shape.left+shape.width<=prs.slide_width+PI(.01)
        assert shape.top+shape.height<=prs.slide_height+PI(.01)
print(f'Informe: {docx.name}; {len(doc.paragraphs)} párrafos; {len(permisos)} permisos delegables.')
print(f'Presentación: {pptx.name}; {len(prs.slides)} diapositivas con guion del expositor.')
