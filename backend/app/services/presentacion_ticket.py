"""Títulos breves a partir de lo reportado, sin inventar diagnósticos."""

import re
import unicodedata


CATEGORIA_POR_TIPO = {
    'Sistema/programa': 'Sistema / Programa',
    'SIGA/Casita/Servidor': 'Sistema / Programa',
    'Carpeta compartida': 'Accesos y permisos',
    'Impresora': 'Impresora',
    'Huella dactilar': 'Hardware',
    'Internet/red': 'Internet / Red',
    'No enciende': 'Hardware',
}


def limitar_titulo(texto: str, limite: int = 70) -> str:
    texto = ' '.join(texto.split()).strip(' "“”')
    return texto if len(texto) <= limite else texto[:limite - 1].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'


def titulo_reporte(tipo: str | None, descripcion: str | None) -> str:
    return limitar_titulo(_titulo_base(tipo, descripcion))


def _frases_relevantes(descripcion: str) -> list[str]:
    frases = [f.strip(' ,;') for f in re.split(r'[.!?](?:\s|$)|\n', descripcion) if len(f.split()) >= 3]
    claves = r'\b(error|falla|funciona|instalar|acceso|abre|enciende|conecta|lento|bloqueado|problema|siga|casita|servidor|guardar|imprime|huella|internet|carpeta|pantalla|teclado|mouse|correo)\b'
    return sorted(dict.fromkeys(frases), key=lambda frase: len(re.findall(claves, frase.lower())) + 2 * bool(re.search(r'\bno\b|sin |atasc', frase.lower())), reverse=True)


def _titulo_base(tipo: str | None, descripcion: str | None) -> str:
    original = ' '.join((descripcion or '').split())
    texto = ''.join(c for c in unicodedata.normalize('NFKD', original.lower()) if not unicodedata.combining(c))
    # Solo se afirma una acción o un síntoma que la persona realmente escribió.
    if tipo not in {'Impresora', 'Huella dactilar', 'Internet/red', 'Carpeta compartida', 'No enciende'} and re.search(r'\b(office|word|excel|power\s*point)\b', texto):
        if re.search(r'\b(instalar|instalen|instalacion)\b', texto):
            return 'Instalación de Office'
        if re.search(r'\b(desinstalar|quitar)\b', texto):
            return 'Desinstalación de Office'
        if 'no abre' in texto or 'no puedo abrir' in texto:
            return 'Office no abre'
        return 'Problema con Office'
    if tipo == 'Impresora' or re.search(r'\b(impresora|imprime|imprimir|escanear)\b', texto):
        if re.search(r'atasc|atorad', texto):
            return 'Papel atascado en la impresora'
        if 'no imprime' in texto:
            return 'La impresora no imprime'
        if 'no escanea' in texto or 'no puedo escanear' in texto:
            return 'No se puede escanear'
        return 'Problema con la impresora'
    if tipo == 'Huella dactilar' or 'huella' in texto:
        if 'registrar' in texto:
            return 'No se puede registrar la huella' if 'no ' in texto else 'Registro de huella dactilar'
        if 'no reconoce' in texto:
            return 'El lector no reconoce la huella'
        return 'Problema con el lector de huella'
    if tipo == 'Internet/red':
        if 'lento' in texto or 'lenta' in texto:
            return 'Internet lento'
        return 'Sin conexión a internet' if re.search(r'sin internet|no (?:hay|tengo|tiene) internet', texto) else 'Problema de conexión a internet'
    if tipo == 'Carpeta compartida':
        return 'No se puede abrir la carpeta compartida' if re.search(r'no abre|no puedo (?:abrir|entrar)|no conecta', texto) else 'Problema con la carpeta compartida'
    if tipo == 'No enciende':
        for nombre, patron in [('El monitor', r'monitor|pantalla'), ('El teclado', r'teclado'), ('El mouse', r'mouse|mause|raton')]:
            if re.search(rf'(?:{patron})\s+(?:no funciona|no responde|falla)', texto):
                return f'{nombre} no funciona'
        if re.search(r'no prende|no enciende|no arranca', texto):
            return 'El equipo no enciende'
    if tipo == 'SIGA/Casita/Servidor':
        sistema = 'SIGA' if re.search(r'\bsiga\b', texto) else 'Casita' if 'casita' in texto else 'el servidor'
        if re.search(r'no puedo entrar|no (?:abre|carga)|no permite (?:entrar|acceder)', texto):
            return f'No se puede acceder a {sistema}'
        if re.search(r'se (?:colgo|cuelga)|no responde', texto):
            return f'{sistema.capitalize() if sistema == "el servidor" else sistema} no responde'
    if re.search(r'formatear|formateo', texto) and not re.search(r'no (?:quiero|necesito) formatear', texto):
        return 'Solicitud de formateo del equipo'
    if tipo == 'Otro' and re.search(r'correo|contrasena|cuenta', texto):
        if re.search(r'restable|cambiar|cambio', texto) and 'contrasena' in texto:
            return 'Solicitud de restablecimiento de contraseña'
        if re.search(r'no puedo entrar|no abre|no puedo acceder', texto):
            return 'Problema de acceso al correo o cuenta'
    if original:
        frases = _frases_relevantes(descripcion or '')
        primera = frases[0] if frases else original
        return re.sub(r'^(?:por favor[ ,]*|necesito que (?:vengan a )?ayudarme (?:porque )?)', '', primera, flags=re.I).strip() or original
    return 'Problema reportado'
