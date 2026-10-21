import { ArchivoInventarioAnual } from '../../componentes/dominio/ArchivoInventarioAnual'
import { PageHeader, PantallaFormulario } from '../../componentes/base/Estructura'
import { useEffect } from 'react'

export function InventarioAnual() {
  useEffect(() => { document.title = 'Inventario anual' }, [])
  return <PantallaFormulario>
    <PageHeader titulo="Inventario anual" descripcion="Registra el Excel de cada año y compara sus equipos, ubicaciones y responsables." />
    <ArchivoInventarioAnual />
  </PantallaFormulario>
}
