"""Lectura acotada de informacion publica oficial, sin URLs aportadas por la IA."""
from html.parser import HTMLParser
from time import monotonic
import asyncio

import httpx

URL_OFICIAL = 'https://www.gob.pe/municasma'
WEB_MUNICIPAL = 'https://municasma.gob.pe/'
_cache = (0.0, '')


class TextoPublico(HTMLParser):
    def __init__(self):
        super().__init__()
        self.omitir = 0
        self.textos = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'svg'}:
            self.omitir += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'svg'}:
            self.omitir = max(0, self.omitir - 1)

    def handle_data(self, data):
        if not self.omitir and data.strip():
            self.textos.append(data.strip())


async def informacion_oficial():
    global _cache
    ahora = monotonic()
    if ahora - _cache[0] < 600:
        return _cache[1]
    texto = ''
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as cliente:
            respuestas = await asyncio.gather(*(cliente.get(url, headers={'Accept': 'text/html'}) for url in (URL_OFICIAL, WEB_MUNICIPAL)), return_exceptions=True)
        for url, respuesta in zip((URL_OFICIAL, WEB_MUNICIPAL), respuestas):
            if isinstance(respuesta, httpx.Response) and respuesta.status_code == 200 and 'text/html' in respuesta.headers.get('content-type', ''):
                parser = TextoPublico()
                parser.feed(respuesta.text[:200000])
                texto += '\nFuente: ' + url + '\n' + '\n'.join(parser.textos)[:7000]
    except (httpx.HTTPError, ValueError):
        pass
    _cache = (ahora, texto)
    return texto
