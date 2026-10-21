"""El SLA cuenta en horas de trabajo, no en horas de reloj.

El plazo acordado son 16 h de labor (2 días de 8). Este archivo fija ese
comportamiento con fechas concretas y **con el día de la semana comprobado**, que
es lo que faltaba antes.

La causa del problema era que el reparto del plazo salía de
`sumar_minutos_laborables` —que respeta fines de semana y feriados— mientras que
el tiempo restante salía de `resolver_en - ahora`, que no los respeta. Las dos
cifras de la misma celda medían en relojes distintos: un caso creado un sábado
salía «Quedan 2 días y 4 h» con la barra en 0 %.

La trampa de probarlo «hoy»: esa fila se ve el sábado y distinta el lunes. Una
prueba que usa `utcnow()` puede pasar un sábado y romperse el lunes. Aquí ninguna
fecha se calcula desde «ahora»: todas son fijas y el día de la semana se
comprueba antes de usar la fecha, para que un cambio de calendario no haga que la
prueba mida otra cosa sin que se note.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

# ── Calendario fijo ─────────────────────────────────────────────
#
# Lunes a viernes de 08:00 a 17:00, es decir 9 h al día, y sin feriados, para que
# los números de las pruebas se puedan calcular a mano. El horario real de la
# municipalidad es otro: lo que se prueba es que los dos relojes coinciden, y eso
# no depende de cuántas horas tenga el día.

def _zona_de_la_app():
    """La zona con la que la app calcula, sin suponerla.

    Las pruebas medían con un desfase `-5` y la app usa otro, así que todas las
    fechas caían en la hora equivocada y los números no cuadraban por un motivo
    que no era el que se estaba probando. Preguntárselo a la app es una línea y no
    un día de pruebas que fallan sin explicación.
    """
    from app.core.time import business_tz

    return business_tz()

LUNES = datetime(2026, 3, 2, 8, 0)  # 2 de marzo: lunes, 08:00 en hora local
SABADO = datetime(2026, 3, 7, 12, 0)  # 7 de marzo: sábado, 12:00 en hora local
VIERNES = datetime(2026, 3, 6, 16, 0)  # 6 de marzo: viernes, 16:00 en hora local


def _local(naive: datetime):
    """Las fechas de la prueba, en la zona con la que calcula la app."""
    return naive.replace(tzinfo=_zona_de_la_app())

CALENDARIO_DE_PRUEBA = {
    "dias_laborables": [0, 1, 2, 3, 4],
    "tramos": [{"entrada": "08:00", "salida": "17:00"}],
    "incluir_feriados": False,
}


async def _fijar_calendario() -> None:
    """Deja el calendario en 9 h de lunes a viernes, con la pausa activada.

    El calendario vive en la sección «sla» del documento único de configuración,
    no en una clave propia: escribirlo en `{"clave": "calendario"}` no cambia
    nada y la prueba acaba midiendo el calendario real de la app, que es
    exactamente el error que este archivo viene a cazar.
    """
    from app.core.db import get_db
    from app.services import config_service

    documento = await config_service.obtener()
    seccion_sla = dict(documento.get("sla") or {})
    seccion_sla.update({"calendario": CALENDARIO_DE_PRUEBA, "pausa_fuera_de_horario": True})
    await get_db()["configuracion"].update_one(
        {"_id": config_service.ID_CONFIG}, {"$set": {"sla": seccion_sla}}
    )


def test_las_fechas_de_la_prueba_caen_donde_se_cree():
    """Guardarraíl: si alguien cambia una fecha, esta prueba avisa.

    Sin esto, cambiar el lunes por el martes haría que las pruebas midieran horas
    de otro día —y pasarían por lo mismo, o fallarían sin explicación.
    """
    assert LUNES.weekday() == 0, "la fecha del lunes no es lunes"
    assert VIERNES.weekday() == 4, "la fecha del viernes no es viernes"
    assert SABADO.weekday() == 5, "la fecha del sábado no es sábado"


async def test_lo_que_queda_mas_lo_gastado_es_el_plazo(db):
    """Las dos cifras de la columna salen del mismo reloj.

    Es el invariante que rompe el error: si lo que queda y lo gastado se midieran
    con relojes distintos, la suma no sería el plazo. Con el mismo reloj, la suma
    da el plazo siempre — y eso es lo que hace que la barra y el texto no puedan
    contradecirse.

    El caso nace en «nuevo», así que lo que corre es el plazo de **responder**.
    """
    from app.services import sla_service

    await _fijar_calendario()

    # El plazo más largo del catálogo son 16 h de trabajo.
    inicio = _local(LUNES)
    deadlines = await sla_service.calcular_deadlines("baja", desde=inicio)
    assert deadlines["sla_horas_resolver"] == 16, "el plazo máximo son 16 h de trabajo"

    # 16 h desde el lunes 08:00: el lunes entero (9 h) más 7 h del martes.
    zona = _zona_de_la_app()
    assert deadlines["sla_resolver_en"].astimezone(zona).strftime("%Y-%m-%d %H:%M") == "2026-03-03 15:00"

    # Sin tomar, lo que corre es el de responder, que para «baja» son 8 h.
    estado = await sla_service.estado_sla(
        {"estado": "nuevo", "creado_en": inicio, **deadlines},
        momento=inicio + timedelta(minutes=15),
    )
    assert estado["modo"] == "responder", "un caso sin tomar cuenta contra el plazo de responder"
    assert estado["minutos_restantes"] == 8 * 60 - 15
    assert estado["minutos_transcurridos"] == 15
    assert estado["minutos_restantes"] + estado["minutos_transcurridos"] == 8 * 60, (
        "lo que queda más lo gastado es el plazo: si no, son dos relojes distintos"
    )
    assert estado["estado"] == "seguro"
    assert 0 < estado["progreso"] < 4, "la barra va apenas empezada"
    # Y los dos plazos vienen los dos, por si alguien necesita el que no corre.
    assert estado["minutos_resolver_restantes"] == 16 * 60 - 15

    # Al tomarlo, el mismo caso pasa a contar contra el de resolver.
    tomado = await sla_service.estado_sla(
        {"estado": "en_progreso", "creado_en": inicio, **deadlines},
        momento=inicio + timedelta(minutes=15),
    )
    assert tomado["modo"] == "resolver", "un caso ya tomado cuenta contra el plazo de resolver"
    assert tomado["minutos_restantes"] == 16 * 60 - 15
    assert tomado["minutos_restantes"] + tomado["minutos_transcurridos"] == 16 * 60


async def test_el_plazo_no_se_corre_por_el_fin_de_semana(db):
    """Un caso abierto el viernes conserva el plazo entero hasta el lunes.

    El fin de semana no se cuenta ni hacia dentro ni hacia fuera. Si el plazo
    corriera en horas de reloj, el caso vencería el sábado y el técnico perdería
    el fin de semana sin haber visto un caso. Si el resto se midiera en horas de
    reloj, el sábado saldría «quedan 3 días» de un plazo que son 16 h.
    """
    from app.services import sla_service

    await _fijar_calendario()

    # Viernes 16:00. Queda 1 h el viernes (hasta las 17:00), 9 h el lunes y 6 h el
    # martes: 08:00 + 6 h son las 14:00.
    viernes = _local(VIERNES)
    zona = _zona_de_la_app()
    deadlines = await sla_service.calcular_deadlines("baja", desde=viernes)
    assert deadlines["sla_resolver_en"].astimezone(zona).strftime("%Y-%m-%d %H:%M") == "2026-03-10 14:00", (
        "16 h desde el viernes 16:00 terminan el martes, no el fin de semana"
    )

    # El sábado siguiente el caso sigue vivo y con el plazo entero por gastar.
    estado = await sla_service.estado_sla(
        {"estado": "nuevo", "creado_en": viernes, **deadlines}, momento=_local(SABADO)
    )
    assert estado["minutos_restantes"] == 8 * 60 - 60, "el fin de semana no le quita horas al caso"
    assert estado["estado"] != "vencido", "un caso no vence un sábado por dormir"
    # Solo cuenta la hora que se trabajó el viernes. Si la barra se disparara por
    # el fin de semana, esto sería 100 % o muy cerca: el sábado no se ha trabajado
    # nada, así que el plazo no se gasta.
    assert estado["minutos_transcurridos"] == 60, "solo cuenta la hora del viernes"
    assert estado["progreso"] == pytest.approx(100 * 60 / (8 * 60), abs=0.1)


def test_el_calendario_por_defecto_es_lunes_a_viernes_de_ocho_horas():
    """El calendario que trae el sistema es el de la municipalidad.

    Dos errores que se\notaban en el plazo y que ninguno daba error, por eso esta
    comprobación es literal y no una constante compartida: el calendario se
    escribe aquí también, y si mañana cambia solo en `DEFAULTS` esta prueba tiene
    que avisar en vez de darlo por bueno.

    El día se cuenta con el índice de `datetime.weekday()`, donde **el lunes es 0**.
    Con `[1, 2, 3, 4, 5]` lo que era martes a sábado, y el lunes no contaba como
    día de trabajo: un caso abierto el lunes no empezaba a consumir plazo hasta el
    martes.
    """
    from app.services.config_service import DEFAULTS

    calendario = DEFAULTS["sla"]["calendario"]
    assert calendario["dias_laborables"] == [0, 1, 2, 3, 4], "la semana laboral es de lunes a viernes"

    tramos = calendario["tramos"]
    assert [(t["entrada"], t["salida"]) for t in tramos] == [("08:00", "13:00"), ("14:00", "17:00")], (
        "08:00-13:00, una hora de descanso, 14:00-17:00"
    )
    horas = sum((datetime.strptime(t["salida"], "%H:%M") - datetime.strptime(t["entrada"], "%H:%M")).seconds for t in tramos) / 3600
    assert horas == 8, f"la jornada dura 8 h, no {horas}"
    assert horas * 2 == 16, "las 16 h del plazo máximo son 2 días laborables justos"


async def test_dieciseis_horas_son_dos_dias_laborables(db):
    """El plazo máximo se cumple en dos días, con el calendario de la casa.

    Es la comprobación que hacía falta y que nadie había escrito: que las 16 h del
    plazo máximo caigan **el segundo día laborable**, y no al tercero porque el
    calendario por defecto no contaba el lunes.
    """
    from app.core.db import get_db
    from app.services import sla_service

    # Se deja el calendario del sistema, sin tocarlo.
    await get_db()["configuracion"].update_one({"_id": "config"}, {"$set": {"sla": {}}})

    lunes = _local(LUNES)
    deadlines = await sla_service.calcular_deadlines("baja", desde=lunes)
    fin = deadlines["sla_resolver_en"].astimezone(_zona_de_la_app())

    # Lunes entero: 08:00-13:00 son 5 h y 14:00-17:00 son 3 h, así que el lunes
    # aporta 8. Las 8 que faltan son el martes entero, y el día acaba a las 17:00.
    assert fin.strftime("%Y-%m-%d %H:%M") == "2026-03-03 17:00", (
        "16 h desde el lunes 08:00 terminan el martes a las 17:00, con el lunes entero"
    )
    assert fin.weekday() == 1, "y es el martes, no el miércoles"

    # Y media jornada —8 h— entra en el mismo día laborable.
    media = await sla_service.calcular_deadlines("media", desde=lunes)
    fin_media = media["sla_resolver_en"].astimezone(_zona_de_la_app())
    assert fin_media.strftime("%Y-%m-%d %H:%M") == "2026-03-02 17:00", "8 h de trabajo son el lunes entero"


async def test_un_caso_cerrado_no_dice_vencido(db):
    """Cerrado no es «vencido»: el historial cerrado no lleva alarmas.

    Un caso cerrado dentro del plazo sale `cerrado_en_plazo`; uno que se pasó de
    plazo, `cerrado_tarde`. Con «Vencido» en rojo dentro de «Historial cerrado»
    parecía una alarma abierta cuando el caso ya estaba resuelto y no había nada
    que hacer.
    """
    from app.services import sla_service

    await _fijar_calendario()

    inicio = _local(LUNES)
    deadlines = await sla_service.calcular_deadlines("baja", desde=inicio)
    base = {
        "estado": "cerrado",
        "creado_en": inicio,
        "cerrado_en": inicio + timedelta(hours=6),
        "sla_incumplido": False,
        **deadlines,
    }

    a_time = await sla_service.estado_sla(base)
    assert a_time["estado"] == "cerrado_en_plazo"
    assert a_time["activo"] is False, "un caso cerrado no tiene plazo corriendo"
    assert a_time["minutos_restantes"] is None, "y no se enseña lo que queda de algo que no corre"
    assert a_time["minutos_transcurridos"] == 6 * 60, "lo que sí se dice es cuánto tardó"
    assert a_time["minutos_retraso"] == 0

    tarde = await sla_service.estado_sla({**base, "cerrado_en": inicio + timedelta(days=3), "sla_incumplido": True})
    assert tarde["estado"] == "cerrado_tarde"
    assert tarde["minutos_retraso"] > 0, "y se dice cuánto se pasó de la fecha"
