from app.core.ids import clave


def componente_escritorio(tipo):
    return clave(tipo or '').lower() in {'cpu', 'monitor', 'teclado', 'mouse', 'computadora', 'pc'}


def equipo_informatico(tipo):
    return clave(tipo or '').lower() in {'cpu', 'laptop', 'portatil', 'computadora', 'pc'}
