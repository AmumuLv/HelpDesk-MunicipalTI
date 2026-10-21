type Tono = 'favorable' | 'carga' | 'neutro'

export function BarraProgreso({
  etiqueta,
  valor,
  tono = 'favorable',
  rotuloVisible = true,
}: {
  etiqueta: string
  valor: number
  tono?: Tono
  /**
   * Si es `false`, la etiqueta solo vive en el título emergente y en el nombre
   * accesible de la barra, no escrita encima.
   *
   * En una tabla ancha no cabe: la etiqueta se comía media celda y la barra
   * acababa cutradísima. El porcentaje y la barra ya dicen lo mismo, y el
   * rótulo sigue estando si alguien pasa el ratón o lee con lector de pantalla.
   */
  rotuloVisible?: boolean
}) {
  const porcentaje = Math.max(0, Math.min(100, Math.round(valor)))
  const clase =
    tono === 'neutro'
      ? // Sin tono de alarma. Es para barras que describen algo ya pasado —un
        // caso cerrado—: que se pinten de rojo y ámbar convierte un dato de
        // historial en una advertencia que nadie tiene que resolver.
        'bg-muted-foreground/35'
      : tono === 'carga'
        ? porcentaje < 60 ? 'bg-success' : porcentaje < 85 ? 'bg-warning' : 'bg-destructive'
        : porcentaje >= 80 ? 'bg-success' : porcentaje >= 50 ? 'bg-warning' : 'bg-destructive'

  return (
    <div className="flex flex-col gap-1" title={etiqueta}>
      {rotuloVisible ? (
        <div className="flex items-center justify-between gap-2 text-sm">
          <span>{etiqueta}</span>
          <span className="font-semibold tabular-nums">{porcentaje}%</span>
        </div>
      ) : (
        <span className="text-2xs font-semibold tabular-nums text-muted-foreground">
          {porcentaje}% del plazo
        </span>
      )}
      <div
        role="progressbar"
        aria-label={etiqueta}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={porcentaje}
        className="h-2 overflow-hidden rounded-full bg-muted"
      >
        <div className={`h-full rounded-full ${clase}`} style={{ width: `${porcentaje}%` }} />
      </div>
    </div>
  )
}
