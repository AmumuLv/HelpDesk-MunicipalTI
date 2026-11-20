"""Subredes IPv4 del contenedor, para ``--forwarded-allow-ips`` de Uvicorn.

El proxy Caddy habla con la API por una red de Docker a la que tambien esta
conectado el propio contenedor. Uvicorn solo debe creer ``X-Forwarded-For`` si
la conexion viene de una de esas redes; con ``*`` cualquiera que alcanzara el
puerto podia cambiar su IP y con ella la clave del limite de peticiones y el
registro de auditoria.

Se calcula en el arranque porque Docker asigna las subredes (por ejemplo
172.19.0.0/16) y pueden cambiar entre equipos. Para fijarla a mano:

    docker network inspect mesa-ayuda_red -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}'

y exportar ``FORWARDED_ALLOW_IPS`` con ese valor (admite varios separados por
coma). Uso:

    python -m app.scripts.redes_proxy
"""

from __future__ import annotations

import fcntl
import ipaddress
import socket
import struct

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891B


def _dato_interfaz(sock: socket.socket, nombre: str, comando: int) -> str:
    peticion = struct.pack("256s", nombre.encode()[:15])
    return socket.inet_ntoa(fcntl.ioctl(sock.fileno(), comando, peticion)[20:24])


def redes() -> list[str]:
    """Subredes de las interfaces IPv4 del contenedor, sin repetir."""
    salida: list[str] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for _, nombre in socket.if_nameindex():
            try:
                direccion = _dato_interfaz(sock, nombre, SIOCGIFADDR)
                mascara = _dato_interfaz(sock, nombre, SIOCGIFNETMASK)
            except OSError:
                continue
            red = str(ipaddress.ip_network(f"{direccion}/{mascara}", strict=False))
            if red not in salida:
                salida.append(red)
    finally:
        sock.close()
    return salida


def main() -> None:
    print(",".join(redes()) or "127.0.0.1")


if __name__ == "__main__":
    main()
