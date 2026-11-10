"""Catálogo de lecturas adicionales del asistente, con argumentos acotados."""
import re

from app.core.errors import Validacion
from app.core.ids import clave
from app.services import analisis_inventario, analisis_operacion, analisis_conocimiento


MODULOS = (analisis_inventario, analisis_operacion, analisis_conocimiento)
CONSULTAS = {nombre: config for modulo in MODULOS for nombre, config in modulo.CONSULTAS.items()}


def detectar(pregunta):
    if re.search(r'^(?:que (?:es|son|significa)|para que sirve|como (?:funciona|se calcula|interpreto))\b', clave(pregunta).lower()):
        return None
    for modulo in MODULOS:
        resultado = modulo.detectar(pregunta)
        if resultado:
            return resultado
    return None


def argumentos_seguros(nombre, argumentos):
    """No admite operadores, claves inesperadas ni estructuras MongoDB."""
    if not isinstance(argumentos, dict):
        raise Validacion('Los argumentos de la consulta no son válidos.')
    esquema = CONSULTAS[nombre].get('esquema') or {}
    propiedades = esquema.get('properties') or {}
    if set(argumentos) - set(propiedades):
        raise Validacion('Esta consulta recibió filtros que no admite. Reformula la pregunta.')
    if set(esquema.get('required') or []) - set(argumentos):
        raise Validacion('Faltan datos para consultar. Indica los valores solicitados.')
    for clave, valor in argumentos.items():
        regla = propiedades[clave]
        tipo = regla.get('type')
        valido = ((tipo == 'integer' and isinstance(valor, int) and not isinstance(valor, bool))
                  or (tipo == 'string' and isinstance(valor, str))
                  or (tipo == 'boolean' and isinstance(valor, bool)))
        if not valido:
            raise Validacion('El valor de «' + clave + '» no tiene el formato requerido.')
        if isinstance(valor, str):
            if not regla.get('minLength', 0) <= len(valor) <= min(250, regla.get('maxLength', 250)):
                raise Validacion('El texto de «' + clave + '» es demasiado largo o está incompleto.')
            if regla.get('pattern') and not re.fullmatch(regla['pattern'], valor):
                raise Validacion('El formato de «' + clave + '» no es válido.')
        if tipo == 'integer' and not regla.get('minimum', -10**9) <= valor <= regla.get('maximum', 10**9):
            raise Validacion('El valor de «' + clave + '» está fuera del rango permitido.')
        if regla.get('enum') and valor not in regla['enum']:
            raise Validacion('El valor de «' + clave + '» no es una opción válida.')
    return dict(argumentos)


def preguntas():
    return [(pregunta, nombre, config.get('grupo', 'Entender'))
            for nombre, config in CONSULTAS.items() for pregunta in config.get('preguntas', [])]


def contexto_seguro(nombre, argumentos):
    """Reconstruye el contexto usando el mismo esquema que una pregunta nueva."""
    if nombre not in CONSULTAS:
        return {}
    try:
        return argumentos_seguros(nombre, argumentos or {})
    except Validacion:
        return {}
