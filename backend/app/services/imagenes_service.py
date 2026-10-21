"""Optimiza nuevas fotos sin modificar archivos ni referencias anteriores."""

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import Validacion


def optimizar(contenido: bytes, mime: str) -> tuple[bytes, str]:
    """JPG/PNG -> WebP 80, hasta 1920 px, con orientación EXIF aplicada."""
    if mime not in {"image/jpeg", "image/png"}:
        return contenido, mime
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(contenido), formats=("JPEG", "PNG")) as origen:
                origen.load()
                imagen = ImageOps.exif_transpose(origen)
                imagen.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                modo = "RGBA" if "A" in imagen.getbands() or "transparency" in imagen.info else "RGB"
                imagen = imagen.convert(modo)
                salida = BytesIO()
                # No se copian EXIF/GPS ni la orientación anterior al nuevo archivo.
                imagen.save(salida, format="WEBP", quality=80, method=6)
                return salida.getvalue(), "image/webp"
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise Validacion("No se pudo procesar la imagen. Comprueba que sea un JPG o PNG válido y vuelve a subirla.") from exc
