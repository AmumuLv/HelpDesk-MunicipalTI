# Parches nativos verificados

Estas copias fijan los mismos cambios y hashes que ya comprobaba el Dockerfile.
No se desactiva ninguna comprobación de integridad, prueba nativa o validación TLS.
Las licencias MIT de los proyectos están incluidas y la imagen conserva también
las licencias de las bibliotecas que compila.

## Procedencia y hashes conservados

| Archivo | Commit oficial | SHA-256 del archivo incluido |
| --- | --- | --- |
| `expat-empty.patch` | [libexpat bfc28346fa3efeb8ca56c17437d24a7344e5feab](https://github.com/libexpat/libexpat/commit/bfc28346fa3efeb8ca56c17437d24a7344e5feab) | `96ea42cc30d4fd99ea62a7fd84d339bef7dc01135f5774b094a09274a0a54f49` |
| `expat-prefix.patch` | [libexpat 621cb2c78b253ee023a86bc91d6ddb048481c04c](https://github.com/libexpat/libexpat/commit/621cb2c78b253ee023a86bc91d6ddb048481c04c) | `3b78184a2176ce725d21b233912033fa333466f4a5a2a17a10128002826f99fb` |
| `expat-attributes.patch` | [libexpat 1bac53c4fc460a03cd9860f39501c7979f6750ae](https://github.com/libexpat/libexpat/commit/1bac53c4fc460a03cd9860f39501c7979f6750ae) | `28ebac139e59e1909e50eecfd834fc4baf9dcf7dc627b4e3a81af872fd818f15` |
| `libxml2-bounds.patch` | [GNOME d1686f91dbda141a752200419d35639fd6b38340](https://github.com/GNOME/libxml2/commit/d1686f91dbda141a752200419d35639fd6b38340) | `5e51f8dcadfe3294a15d9e8644d61e8d92bd5b9e72c10cf13ef010eccfbfa4df` |

## Por qué se conservan en el repositorio

El 07/11/2026, las respuestas `.patch` de GitHub para los tres commits de Expat
ya no tenían el hash previsto. Se verificó que eran parches de texto reales y
que la única diferencia era la longitud de los identificadores abreviados de
blob en las líneas `index`: GitHub pasó de nueve a diez caracteres.

Al restituir únicamente esas abreviaturas a nueve caracteres, los tres archivos
coincidieron exactamente con sus SHA-256 anteriores. No cambiaron autor, mensaje,
contexto, líneas añadidas ni eliminadas. El parche GNOME coincidía directamente
con su hash previsto y se incluyó sin modificarlo.

También se descargaron los blobs de `expat/lib/xmlparse.c` de cada commit y su
padre desde el repositorio oficial. Sus identificadores se verificaron con el
formato canónico Git `SHA1("blob " + longitud + NUL + contenido)`:

| Cambio | Blob anterior | Blob posterior |
| --- | --- | --- |
| Inicialización vacía | `a370c7d7de51fcbdffc0a2a29365504e3eb2d545` | `5a8da9c3b4f7073b9c6d12e74e3010f04a255d73` |
| Prefijos | `a04ffde0732b5c5d64b7df6f5e51ba386908553b` | `84a1fc13537ce80e557909bad84df67e998b7f53` |
| Atributos | `84a1fc13537ce80e557909bad84df67e998b7f53` | `14b4b0013696fbbc71120f0ec971085d42b0008c` |

El Dockerfile copia estas versiones y vuelve a verificar sus hashes antes de
aplicarlas. Los archivos `.patch` se guardan con LF mediante `.gitattributes`,
también al clonar desde Windows. Se aplica `patch --batch --forward --fuzz=0`
para evitar inversiones automáticas y coincidencias aproximadas. Se mantienen
las pruebas de las bibliotecas y `verify_backports.py` durante la construcción.

## Licencias y futuras actualizaciones

- `LICENSE.Expat.txt` procede de `expat/COPYING` del commit Expat indicado arriba.
- `LICENSE.libxml2.txt` procede de `Copyright` del commit GNOME indicado arriba.
- No actualices un hash solo porque una descarga dejó de coincidir. Comprueba el
  cambio upstream, la procedencia, las diferencias exactas y las pruebas.
- Estos backports no son un informe de vulnerabilidades de toda la imagen. Los
  avisos por versión de paquete y la biblioteca realmente cargada se evalúan por
  separado y se registran sin ocultar resultados del escáner.
