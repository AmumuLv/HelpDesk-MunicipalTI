import pytest

from app.migrations import m009_codigo_patrimonial_no_unico


class _Cursor:
    def __init__(self, filas):
        self.filas = filas

    async def to_list(self, length):
        return self.filas[:length]


class _Activos:
    def __init__(self, duplicados):
        self.duplicados = duplicados
        self.indices = {"ix_activos_codigo": {}}
        self.indices_eliminados = []
        self.indices_creados = []

    def aggregate(self, pipeline):
        return _Cursor(self.duplicados)

    async def index_information(self):
        return self.indices

    async def drop_index(self, nombre):
        self.indices_eliminados.append(nombre)

    async def create_index(self, campos, **opciones):
        self.indices_creados.append((campos, opciones))


class _DB:
    def __init__(self, activos):
        self.activos = activos

    def __getitem__(self, nombre):
        assert nombre == "activos"
        return self.activos


async def test_rollback_preserva_indice_si_hay_codigos_repetidos():
    activos = _Activos([{"_id": "TI-001", "total": 2}])

    with pytest.raises(RuntimeError, match="códigos repetidos"):
        await m009_codigo_patrimonial_no_unico.revertir(_DB(activos))

    assert activos.indices_eliminados == []
    assert activos.indices_creados == []


async def test_rollback_restaura_indice_unico_si_no_hay_repetidos():
    activos = _Activos([])

    await m009_codigo_patrimonial_no_unico.revertir(_DB(activos))

    assert activos.indices_eliminados == ["ix_activos_codigo"]
    assert activos.indices_creados == [
        (
            [("codigo_patrimonial", 1)],
            {
                "name": "uq_activos_codigo",
                "unique": True,
                "partialFilterExpression": {
                    "codigo_patrimonial": {"$type": "string"}
                },
            },
        )
    ]
