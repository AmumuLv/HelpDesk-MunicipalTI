"""Descarga la tipografia Atkinson Hyperlegible a formato woff2.

La interfaz la sirve desde `public/fuentes/` para no depender de una CDN externa
en una municipalidad con internet limitado.
"""

from __future__ import annotations

import pathlib
import re
import urllib.request

DESTINO = pathlib.Path(__file__).resolve().parent / "frontend" / "public" / "fuentes"
DESTINO.mkdir(parents=True, exist_ok=True)

URL_CSS = (
    "https://fonts.googleapis.com/css2"
    "?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap"
)
# Un agente de navegador moderno: Google devuelve woff2 en lugar de ttf
AGENTE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

peticion = urllib.request.Request(URL_CSS, headers={"User-Agent": AGENTE})
css = urllib.request.urlopen(peticion, timeout=60).read().decode("utf-8")

# Cada bloque @font-face lleva su url en woff2 y un comentario con el estilo
bloques = re.findall(r"@font-face\s*\{(.*?)\}", css, re.DOTALL)
print(f"bloques encontrados: {len(bloques)}")

for bloque in bloques:
    estilo = re.search(r"font-style:\s*(\w+)", bloque)
    peso = re.search(r"font-weight:\s*(\d+)", bloque)
    url = re.search(r"url\((https://[^)]+\.woff2)\)", bloque)
    if not url:
        continue
    nombre = f"atkinson-hyperlegible-{peso.group(1) if peso else '400'}"
    if estilo and estilo.group(1) == "italic":
        nombre += "-italic"
    nombre += ".woff2"

    destino = DESTINO / nombre
    if destino.exists():
        print("ya existe:", nombre)
        continue
    datos = urllib.request.urlopen(urllib.request.Request(url.group(1), headers={"User-Agent": AGENTE}), timeout=60).read()
    destino.write_bytes(datos)
    print("descargado:", nombre, len(datos), "bytes")

print("\nlisto en", DESTINO)