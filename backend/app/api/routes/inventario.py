"""Rutas de inventario: conjuntos, activos, calidad, campos, sugerencias y responsables."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import DependeUsuario, DependeUsuarioCsrf, id_opcional, requiere
from app.core.errors import Prohibido, Validacion
from app.core.ids import id_requerido
from app.core.serializacion import normalizar
from app.domain.constants import (
    CAMPO_NO_APLICA,
    CAMPO_NO_DISPONIBLE,
    CAMPO_PENDIENTE,
    CAMPOS_BASE,
    ESTADOS_CAMPO,
)
from app.schemas.inventario import (
    ActivoActualizar,
    ActivoCrear,
    CambioCamposMasivo,
    CambioEstadoCampo,
    CambioMasivo,
    CambioResponsable,
    ConjuntoActualizar,
    ConjuntoCrear,
    FiltrosInventario,
    OpcionesAvanzadasMasivo,
)
from app.services import calidad_service, catalogo_service, inventario_service

router = APIRouter(tags=["inventario"])

DependeCrearEquipo = Annotated[None, Depends(requiere("equipos.crear"))]
DependeEditarEquipo = Annotated[None, Depends(requiere("equipos.editar"))]
DependeEliminarEquipo = Annotated[None, Depends(requiere("equipos.eliminar"))]
DependeMasivo = Annotated[None, Depends(requiere("equipos.acciones_masivas"))]
DependeOpcionesAvanzadas = Annotated[None, Depends(requiere("equipos.opciones_avanzadas"))]
DependeMarcarNoAplica = Annotated[None, Depends(requiere("equipos.marcar_no_aplica"))]
DependeVerEquipos = Annotated[None, Depends(requiere("equipos.ver"))]


# ── Conjuntos ────────────────────────────────────────────────
@router.get("/conjuntos")
async def listar_conjuntos(
    sesion: DependeUsuario,
    zona_id: str | None = None,
    oficina_id: str | None = None,
    texto: str | None = None,
):
    return {
        "items": normalizar(
            await inventario_service.listar_conjuntos(
                zona_id=id_opcional(zona_id, "zona"),
                oficina_id=id_opcional(oficina_id, "oficina"),
                texto=texto,
            )
        )
    }


@router.post("/conjuntos", status_code=201)
async def crear_conjunto(datos: ConjuntoCrear, sesion: DependeUsuarioCsrf, _: DependeCrearEquipo):
    conjunto = await inventario_service.crear_conjunto(datos.model_dump(), usuario=sesion.como_dict())
    return normalizar(conjunto)


@router.get("/conjuntos/siguiente-nombre")
async def siguiente_nombre_conjunto(oficina_id: str, sesion: DependeUsuario, base: str = "Computadora"):
    return {"nombre": await inventario_service.numeracion_sugerida(id_requerido(oficina_id, "oficina"), base)}


@router.patch("/conjuntos/{conjunto_id}")
async def actualizar_conjunto(conjunto_id: str, datos: ConjuntoActualizar, sesion: DependeUsuarioCsrf, _: DependeEditarEquipo):
    conjunto = await inventario_service.actualizar_conjunto(
        id_requerido(conjunto_id, "conjunto"), datos.model_dump(exclude_unset=True), usuario=sesion.como_dict()
    )
    return normalizar(conjunto)


@router.post("/conjuntos/{conjunto_id}/responsable")
async def responsable_conjunto(conjunto_id: str, datos: CambioResponsable, sesion: DependeUsuarioCsrf, _: DependeEditarEquipo):
    return await inventario_service.cambiar_responsable(
        "conjunto",
        id_requerido(conjunto_id, "conjunto"),
        datos.responsable_id,
        usuario=sesion.como_dict(),
        motivo=datos.motivo,
        confirmar_transferencia=datos.confirmar_transferencia,
    )


# ── Activos ──────────────────────────────────────────────────
@router.get("/activos")
async def listar_activos(sesion: DependeUsuario, filtros: Annotated[FiltrosInventario, Query()]):
    consulta = filtros.model_dump()
    return await inventario_service.listar(consulta)


@router.post("/activos", status_code=201)
async def crear_activo(datos: ActivoCrear, sesion: DependeUsuarioCsrf, _: DependeCrearEquipo):
    activo = await inventario_service.crear_activo(datos.model_dump(), usuario=sesion.como_dict())
    return await inventario_service.detalle(activo["_id"], usuario=sesion.como_dict())


@router.get("/activos/excel")
async def descargar_activos_excel(
    sesion: DependeUsuario,
    _: DependeEditarEquipo,
    zona_id: str | None = None,
    oficina_id: str | None = None,
    tipo: str | None = None,
    estado: str | None = None,
    texto: str | None = None,
    solo_faltantes: bool = False,
    solo_uso_comun: bool = False,
):
    """
    El inventario registrado en el Excel del municipio: una hoja por zona.

    Acepta los mismos filtros que el listado, así que lo que se descarga es lo que se
    está viendo con los filtros puestos y no «todo» por sorpresa. El archivo usa las
    columnas de la plantilla oficial, de modo que se puede volver a subir tal cual.
    """
    contenido, total, nombre = await inventario_service.exportar_excel(
        {
            "zona_id": zona_id,
            "oficina_id": oficina_id,
            "tipo": tipo,
            "estado": estado,
            "texto": texto,
            "solo_faltantes": solo_faltantes,
            "solo_uso_comun": solo_uso_comun,
        }
    )
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}.xlsx"',
            "X-Total-Equipos": str(total),
        },
    )


@router.get("/activos/plantilla-manual")
async def plantilla_registro_manual(oficina_id: str, sesion: DependeUsuario, _: DependeCrearEquipo):
    """Sugiere el siguiente nombre de conjunto y los componentes habituales."""
    from app.services import catalogo_service

    oficina = id_requerido(oficina_id, "oficina")
    componentes = await catalogo_service.listar("componentes_conjunto")
    return {
        "nombre_conjunto": await inventario_service.numeracion_sugerida(oficina, "Computadora"),
        "componentes_sugeridos": componentes,
        "tipos_disponibles": await catalogo_service.tipos_existentes(),
    }


@router.get("/activos/duplicados")
async def duplicados_activos(
    sesion: DependeUsuario,
    codigo_patrimonial: str | None = Query(default=None, max_length=60),
    direccion_ip: str | None = Query(default=None, max_length=45),
    direccion_mac: str | None = Query(default=None, max_length=40),
    excluir_id: str | None = None,
):
    return {
        "items": normalizar(
            await inventario_service.buscar_duplicados(
                codigo_patrimonial=codigo_patrimonial,
                direccion_ip=direccion_ip,
                direccion_mac=direccion_mac,
                excluir_id=id_opcional(excluir_id, "activo"),
            )
        )
    }


@router.get("/activos/{activo_id}")
async def obtener_activo(activo_id: str, sesion: DependeUsuario):
    return await inventario_service.detalle(id_requerido(activo_id, "activo"), usuario=sesion.como_dict())


@router.patch("/activos/{activo_id}")
async def actualizar_activo(activo_id: str, datos: ActivoActualizar, sesion: DependeUsuarioCsrf, _: DependeEditarEquipo):
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("opciones_avanzadas") is True or cambios.get("detalle_avanzado"):
        sesion.exigir("equipos.opciones_avanzadas")
    activo = await inventario_service.actualizar_activo(
        id_requerido(activo_id, "activo"), cambios, usuario=sesion.como_dict()
    )
    return await inventario_service.detalle(activo["_id"], usuario=sesion.como_dict())


@router.delete("/activos/{activo_id}")
async def eliminar_activo(activo_id: str, sesion: DependeUsuarioCsrf, _: DependeEliminarEquipo, motivo: str | None = None):
    await inventario_service.eliminar_activo(id_requerido(activo_id, "activo"), usuario=sesion.como_dict(), motivo=motivo)
    return {"mensaje": "Equipo dado de baja."}


@router.post("/activos/{activo_id}/campos")
async def marcar_campos(activo_id: str, datos: CambioEstadoCampo, sesion: DependeUsuarioCsrf, _: DependeMarcarNoAplica):
    resultado = await inventario_service.marcar_campos(
        [id_requerido(activo_id, "activo")],
        datos.campos,
        datos.estado,
        usuario=sesion.como_dict(),
        motivo=datos.motivo,
        nota=datos.nota,
    )
    return {"resultado": resultado, "activo": await inventario_service.detalle(id_requerido(activo_id, "activo"), usuario=sesion.como_dict())}


@router.post("/activos/campos-masivo")
async def marcar_campos_masivo(datos: CambioCamposMasivo, sesion: DependeUsuarioCsrf, _: DependeMarcarNoAplica):
    """Accion masiva: marcar un campo como 'No aplica' en varios equipos a la vez."""
    return await inventario_service.marcar_campos(
        list(datos.activo_ids),
        datos.campos,
        datos.estado,
        usuario=sesion.como_dict(),
        motivo=datos.motivo,
        nota=datos.nota,
    )


@router.post("/activos/opciones-avanzadas-masivo")
async def opciones_avanzadas_masivo(datos: OpcionesAvanzadasMasivo, sesion: DependeUsuarioCsrf, _: DependeOpcionesAvanzadas):
    return await inventario_service.activar_opciones_avanzadas(
        list(datos.activo_ids), datos.activar, usuario=sesion.como_dict()
    )


@router.delete("/activos/{activo_id}/detalle-avanzado")
async def borrar_detalle(activo_id: str, sesion: DependeUsuarioCsrf, _: DependeOpcionesAvanzadas):
    await inventario_service.borrar_detalle_avanzado(id_requerido(activo_id, "activo"), usuario=sesion.como_dict())
    return {"mensaje": "Detalle avanzado eliminado."}


@router.post("/activos/{activo_id}/responsable")
async def responsable_activo(activo_id: str, datos: CambioResponsable, sesion: DependeUsuarioCsrf, _: DependeEditarEquipo):
    return await inventario_service.cambiar_responsable(
        "activo",
        id_requerido(activo_id, "activo"),
        datos.responsable_id,
        usuario=sesion.como_dict(),
        motivo=datos.motivo,
        confirmar_transferencia=datos.confirmar_transferencia,
    )


@router.post("/activos/cambio-masivo")
async def cambio_masivo(datos: CambioMasivo, sesion: DependeUsuarioCsrf, _: DependeMasivo):
    return await inventario_service.cambio_masivo(datos.model_dump(), usuario=sesion.como_dict())


@router.get("/activos/{activo_id}/componentes")
async def historial_componentes(activo_id: str, sesion: DependeUsuario):
    activo = await inventario_service.detalle(id_requerido(activo_id, "activo"), usuario=sesion.como_dict())
    return {"items": activo.get("historial_componentes", [])}


@router.get("/equipos/mis")
async def mis_equipos(sesion: DependeUsuario):
    """Portal del usuario: sus equipos y los de uso comun de su oficina."""
    return await inventario_service.equipos_de_usuario(sesion.id)


@router.get("/equipos/por-codigo")
async def buscar_por_codigo(sesion: DependeUsuario, texto: str = Query("", max_length=120), limite: int = Query(20, ge=1, le=50)):
    return {"items": await inventario_service.equipos_por_codigo(texto, limite=limite)}


@router.get("/equipos/de-persona/{usuario_id}")
async def equipos_de_persona(usuario_id: str, sesion: DependeUsuario, _: DependeVerEquipos):
    """Los equipos de otra persona, para poder registrarle un caso.

    El portal usa `/mis`, que es el de quien pregunta. Al registrar un caso de
    otra persona hace falta lo mismo para ella, y **elegir de una lista** es lo
    que evita tener que escribir el nombre del equipo: escribirlo busca por texto
    sin anclar y «CPU» engancha un equipo cualquiera del edificio.

    Requiere permiso de ver inventario, que es el mismo que hace falta para
    entrar en Equipos.
    """
    return await inventario_service.equipos_de_usuario(id_requerido(usuario_id, "usuario"))


@router.get("/equipos/buscar")
async def buscar_equipos(
    sesion: DependeUsuario,
    texto: str = Query("", max_length=120),
    zona_id: str | None = None,
    limite: int = Query(25, ge=1, le=50),
):
    if sesion.rol == "usuario" and not texto:
        return {"items": []}
    return {"items": await inventario_service.buscar(texto, limite=limite, zona_id=id_opcional(zona_id, "zona"))}


# ── Sugerencias de autocompletado ────────────────────────────
@router.get("/equipos/sugerencias")
async def sugerencias(
    sesion: DependeUsuario,
    campo: str = Query(..., max_length=60),
    tipo: str | None = None,
    marca: str | None = None,
    limite: int = Query(12, ge=1, le=40),
):
    if campo not in {'marca', 'modelo', 'procesador', 'memoria_ram', 'almacenamiento', 'tamano_pantalla', 'propiedad', 'estado'}:
        raise Validacion("Campo sin sugerencias disponibles.")
    valores = await catalogo_service.sugerencias(campo, tipo=tipo, marca=marca, limite=limite)
    if not valores and campo in {"marca", "modelo", "tamano_pantalla", "propiedad", "estado"}:
        from app.migrations.m002_catalogos import CATALOGOS

        base = {"marca": [], "modelo": [], "tamano_pantalla": ['15"', '17"', '19"', '22"', '24"'], "propiedad": CATALOGOS["propiedades"], "estado": CATALOGOS["estados_activo"]}.get(
            campo, []
        )
        valores = [{"valor": v, "frecuencia": 0, "marca": None, "frecuencia_marca": 0, "ejemplo_completo": None, "es_base": True} for v in base]
    return {"campo": campo, "tipo": tipo, "marca": marca, "valores": valores}


@router.get("/equipos/catalogos")
async def catalogos(sesion: DependeUsuario):
    return await catalogo_service.todos()


# ── Calidad del inventario ───────────────────────────────────
@router.get("/calidad-inventario")
async def calidad(
    sesion: DependeUsuario,
    zona_id: str | None = None,
    oficina_id: str | None = None,
    tipo: str | None = None,
):
    return await calidad_service.resumen(
        zona_id=id_opcional(zona_id, "zona"),
        oficina_id=id_opcional(oficina_id, "oficina"),
        tipo=tipo,
    )


@router.get("/calidad-inventario/esquema/{tipo}")
async def esquema(tipo: str, sesion: DependeUsuario):
    return await catalogo_service.esquema(tipo)


@router.get("/calidad-inventario/estados-campo")
async def estados_campo(sesion: DependeUsuario):
    return {
        "estados": list(ESTADOS_CAMPO),
        "por_defecto": CAMPO_PENDIENTE,
        "no_aplica": {"clave": CAMPO_NO_APLICA, "motivos": await catalogo_service.listar("motivos_no_aplica")},
        "no_disponible": {"clave": CAMPO_NO_DISPONIBLE, "motivos": await catalogo_service.listar("motivos_no_disponible")},
        "campos": list(CAMPOS_BASE),
    }
