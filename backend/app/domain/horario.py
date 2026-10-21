"""Horario inicial del personal TI; 0 = lunes y 6 = domingo."""


def horario_base() -> dict:
    return {"dias": {
        str(dia): {"libre": dia >= 5, "tramos": [
            {"entrada": "08:00", "salida": "13:00"},
            {"entrada": "14:00", "salida": "17:00"},
        ] if dia < 5 else []}
        for dia in range(7)
    }}
