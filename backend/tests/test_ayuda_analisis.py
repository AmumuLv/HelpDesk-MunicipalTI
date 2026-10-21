"""Las preguntas de datos no deben confundirse con ayuda sobre los filtros."""
from app.services.ayuda_analisis import responder_ayuda


def test_periodo_en_consulta_no_sustituye_los_datos_por_una_guia():
    for pregunta in (
        '¿Qué oficina tiene más incidencias en el periodo seleccionado?',
        '¿Qué zona tiene más tickets en el rango de fechas?',
        '¿Cómo se distribuyen los tickets por oficina en este periodo?',
    ):
        assert responder_ayuda(pregunta) is None


def test_pregunta_explicita_sobre_periodo_conserva_la_ayuda():
    for pregunta in ('¿Qué significa el periodo?', '¿Cómo funciona el rango de fechas?', 'Explícame el periodo'):
        assert 'selector Periodo' in responder_ayuda(pregunta)
