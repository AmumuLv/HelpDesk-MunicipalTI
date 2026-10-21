export type EventoTicket = {
  id: string
  tipo: string
  fecha: string
  actor?: { id?: string; nombre?: string; rol?: string }
  resumen?: string
  detalle?: Record<string, unknown>
  origen_ia?: boolean
}

export type HitoTicket = EventoTicket & { titulo: string; tono: 'info' | 'exito' | 'aviso' }

/** Resume la vista del historial sin modificar el registro de auditoría. */
export function hitosDelTicket(eventos: EventoTicket[]): HitoTicket[] {
  const hitos: HitoTicket[] = []
  for (const evento of eventos) {
    let titulo = ''
    let tono: HitoTicket['tono'] = 'info'
    const detalle = evento.detalle || {}
    if (evento.tipo === 'creado') titulo = 'Ticket registrado'
    else if (evento.tipo === 'asignado') {
      const tecnico = typeof detalle.tecnico === 'string' ? detalle.tecnico : evento.resumen?.replace(/^Asignado a\s+/i, '')
      titulo = tecnico && tecnico !== 'sin asignar' ? `Asignado a ${tecnico}` : 'Asignación retirada'
    } else if (evento.tipo === 'estado' || evento.tipo === 'reabierto') {
      const estados: Record<string, string> = { nuevo: 'Nuevo', en_progreso: 'En progreso', en_espera: 'En espera', cerrado: 'Finalizado', resuelto: 'Finalizado' }
      const estado = String(detalle.estado_nuevo || '')
      const reabierto = evento.tipo === 'reabierto' || /reabierto/i.test(evento.resumen || '')
      titulo = reabierto ? 'Ticket reabierto' : estado === 'cerrado' || estado === 'resuelto' ? 'Ticket finalizado' : estados[estado] ? `Estado: ${estados[estado]}` : 'Estado del ticket actualizado'
      tono = reabierto || estado === 'en_espera' ? 'aviso' : estado === 'cerrado' || estado === 'resuelto' ? 'exito' : 'info'
    } else if (evento.tipo === 'actualizado') {
      const antes = detalle.antes as Record<string, unknown> | undefined
      const despues = detalle.despues as Record<string, unknown> | undefined
      const campos = Array.isArray(detalle.campos) ? detalle.campos as string[] : Object.keys(despues || {})
      const cambio = (campo: string) => campos.includes(campo) && (!antes || !despues || JSON.stringify(antes[campo] ?? null) !== JSON.stringify(despues[campo] ?? null))
      const etiquetas = [
        ...(cambio('activo_id') || cambio('conjunto_id') ? ['equipo afectado'] : []),
        ...(cambio('sistema_afectado') ? ['programa o sistema'] : []),
        ...(cambio('asunto') ? ['título'] : []),
        ...(cambio('categoria') ? ['categoría'] : []),
        ...(cambio('prioridad') ? ['prioridad'] : []),
        ...(cambio('descripcion') ? ['descripción'] : []),
      ]
      if (!etiquetas.length) continue
      titulo = etiquetas.length === 1
        ? `${etiquetas[0][0].toUpperCase()}${etiquetas[0].slice(1)} ${etiquetas[0] === 'categoría' || etiquetas[0] === 'prioridad' || etiquetas[0] === 'descripción' ? 'actualizada' : 'actualizado'}`
        : `Se actualizaron: ${etiquetas.slice(0, -1).join(', ')} y ${etiquetas.at(-1)}`
    } else continue
    // Solo se agrupan asignaciones consecutivas al mismo destino. Una reasignación
    // a otra persona, o una asignación tras otro hito, siempre permanece visible.
    const anterior = hitos.at(-1)
    if (evento.tipo === 'asignado' && anterior?.tipo === 'asignado' && anterior.titulo === titulo) continue
    hitos.push({ ...evento, titulo, tono })
  }
  return hitos
}
