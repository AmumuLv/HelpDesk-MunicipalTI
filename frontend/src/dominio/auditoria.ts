export const ENTIDADES_AUDITORIA: Record<string, string> = {
  usuario: 'Cuenta de usuario', zona: 'Zona', oficina: 'Oficina', activo: 'Equipo', conjunto: 'Conjunto de equipos',
  ticket: 'Ticket', articulo: 'Artículo', respuesta_rapida: 'Respuesta rápida', configuracion: 'Configuración',
  permiso: 'Permisos', permisos: 'Permisos', tecnico: 'Técnico', campana: 'Inventario anual', exportacion: 'Reporte',
}

const CAMPOS: Record<string, string> = { titulo: 'Título', cuerpo: 'Contenido', categoria: 'Categoría', resumen: 'Resumen', activo: 'Cuenta activa', nombre: 'Nombre', correo: 'Correo', rol: 'Rol', permisos: 'Permisos', estado: 'Estado', prioridad: 'Prioridad', pasos: 'Pasos', antes: 'Anterior', despues: 'Nuevo' }

function aplanar(datos: Record<string, unknown> | null | undefined, prefijo = ''): Record<string, unknown> {
  const valores: Record<string, unknown> = {}
  for (const [clave, valor] of Object.entries(datos ?? {})) {
    if (['actualizado_en', 'creado_en', '_id'].includes(clave)) continue
    const ruta = prefijo ? `${prefijo} / ${CAMPOS[clave] ?? clave.replaceAll('_', ' ')}` : (CAMPOS[clave] ?? clave.replaceAll('_', ' '))
    if (/password|contrasena|contraseña|token|secret|hash/i.test(clave)) valores[ruta] = '[Protegido]'
    else if (valor && typeof valor === 'object' && !Array.isArray(valor)) Object.assign(valores, aplanar(valor as Record<string, unknown>, ruta))
    else valores[ruta] = valor
  }
  return valores
}

export function cambiosAuditoria(antes: Record<string, unknown> | null | undefined, despues: Record<string, unknown> | null | undefined) {
  const anterior = aplanar(antes)
  const nuevo = aplanar(despues)
  const texto = (valor: unknown): string => {
    if (valor === null || valor === undefined || valor === '') return 'Sin dato'
    if (typeof valor === 'boolean') return valor ? 'Sí' : 'No'
    if (Array.isArray(valor)) return valor.map(texto).join(' · ') || 'Sin elementos'
    if (typeof valor === 'object') return Object.values(aplanar(valor as Record<string, unknown>)).map(texto).join(' · ')
    return String(valor)
  }
  return [...new Set([...Object.keys(anterior), ...Object.keys(nuevo)])]
    .filter((clave) => JSON.stringify(anterior[clave]) !== JSON.stringify(nuevo[clave]))
    .map((clave) => ({ campo: clave, antes: texto(anterior[clave]), despues: texto(nuevo[clave]) }))
}
