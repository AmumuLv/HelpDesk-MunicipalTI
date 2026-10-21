from app.services.ia_service import _limitar_explicacion


def test_explicaciones_ia_no_superan_90_caracteres():
    texto = _limitar_explicacion("Una explicacion extensa " * 10)

    assert texto is not None
    assert len(texto) <= 90
    assert texto.endswith("...")


def test_explicaciones_ia_sin_espacios_tampoco_superan_90_caracteres():
    texto = _limitar_explicacion("x" * 120)

    assert texto is not None
    assert len(texto) <= 90
    assert texto.endswith("...")


def test_explicaciones_ia_conservan_texto_corto():
    assert _limitar_explicacion("Sugerencia aproximada.") == "Sugerencia aproximada."
