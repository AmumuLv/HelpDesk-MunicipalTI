const REGlas: { patron: RegExp; token: string }[] = [
  { patron: /sistema de audio|audio|parlante|altavoz|bocina|microfono|micrófono|mic/, token: '--icono-audio' },
  { patron: /disco duro externo|disco externo|almacenamiento externo|dd externo/, token: '--icono-disco' },
  { patron: /ups|no-?break|respaldo de energia|respaldo de energía|bateria|batería/, token: '--icono-ups' },
  { patron: /servidor|server|blade/, token: '--icono-servidor' },
  { patron: /tablet|tableta/, token: '--icono-tablet' },
  { patron: /celular|movil|móvil|telefono|teléfono|smartphone/, token: '--icono-celular' },
  { patron: /switch/, token: '--icono-switch' },
  { patron: /router|wi-?fi|red|accespoint/, token: '--icono-router' },
  { patron: /impresora|multifuncional|impresor|scanner|escáner/, token: '--icono-impresora' },
  { patron: /monitor|pantalla|proyector|display|videotarjeta/, token: '--icono-monitor' },
  { patron: /teclado|keyboard/, token: '--icono-teclado' },
  { patron: /mouse|raton|ratón|ratita/, token: '--icono-mouse' },
  // `lapto` va explícito: «LAPTO» es lo que traen algunos equipos del Excel y
  // `/laptop/` no lo encuentra, así que antes salía con el icono genérico.
  { patron: /laptop|portatil|portátil|notebook|lapto/, token: '--icono-laptop' },
  { patron: /cpu|computadora|equipo|desktop|escritorio|\bpc\b/, token: '--icono-cpu' },
]

export function colorTipoEquipo(tipo?: string | null): string {
  const valor = (tipo ?? '').toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  const encontrado = REGlas.find((regla) => regla.patron.test(valor))
  return encontrado ? encontrado.token : '--icono-default'
}

