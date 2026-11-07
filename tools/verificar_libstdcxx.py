"""Reproduce nueve casos de GCC CVE-2026-95619 en contenedores desechables.

No consulta la base de datos ni modifica contenedores operativos. No demuestra
ausencia de otras vulnerabilidades ni sustituye la auditoría de imágenes.
Casos oficiales: gcc-mirror/gcc, commit 200183d4ab5d57575f3dfebc6af3baf649910b9e.
"""
import argparse
import json
import subprocess
import uuid

CODIGO = '''import ctypes
lib = ctypes.CDLL("libstdc++.so.6")
new = getattr(lib, "_ZnwmSt11align_val_tRKSt9nothrow_t")
new.argtypes = [ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p]
new.restype = ctypes.c_void_p
nothrow = ctypes.addressof(ctypes.c_ubyte.in_dll(lib, "_ZSt7nothrow"))
maximum = ctypes.c_size_t(-1).value
cases = [(maximum-8,32), (maximum,8), (maximum,32), (maximum,1024),
         (maximum,65536), (maximum-1,16), (maximum-1025,1024),
         (maximum-1024,1024), (maximum-65536,65536)]
for size, alignment in cases:
    assert new(size, alignment, nothrow) is None, "Impossible allocation accepted"
print("PASS: 9 upstream aligned-allocation cases")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('imagenes', nargs='+', help='Imágenes locales Linux con Python y libstdc++')
    args = parser.parse_args()
    for imagen in args.imagenes:
        if imagen.startswith('-') or '://' in imagen:
            parser.error('Indica una imagen local, no opciones ni URLs.')
        nombre = 'helpdesk-libstdcxx-' + uuid.uuid4().hex
        try:
            resultado = subprocess.run(
                ['docker', 'run', '--rm', '--pull=never', '--name', nombre, '--network', 'none',
                 '--read-only', '--entrypoint', 'python', imagen, '-c', CODIGO],
                capture_output=True, text=True, timeout=60, check=True,
            )
            assert 'PASS: 9 upstream' in resultado.stdout
            print(json.dumps({'imagen': imagen, 'casos': 9, 'resultado': 'aprobado'}))
        finally:
            # Solo el contenedor propio; --rm puede haberlo retirado ya.
            subprocess.run(['docker', 'rm', '-f', nombre], capture_output=True, timeout=15)


if __name__ == '__main__':
    main()
