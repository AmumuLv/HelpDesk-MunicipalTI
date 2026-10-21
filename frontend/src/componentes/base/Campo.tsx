/**
 * Campos de formulario.
 *
 * Un solo lugar para texto, área, selección, casilla e interruptor. Etiqueta,
 * ayuda y error siempre conectados con `aria-describedby`, y el error pegado al
 * campo, nunca como aviso suelto.
 */

import { ChevronDown, Search, X, Check } from 'lucide-react'
import {
  forwardRef,
  useEffect,
  useId,
  useRef,
  useState,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'

import { cn } from '../../lib/cn'

type Base = {
  /** Si se omite, el campo queda sin encabezado visible. */
  etiqueta?: string
  ayuda?: ReactNode
  error?: string
  requerido?: boolean
  className?: string
  /** Marca el campo como «No aplica» sin bloquear el formulario. */
  noAplica?: boolean
  acciones?: ReactNode
  /** Alto de 40 px en el panel; 48 px en el portal táctil. */
  tamano?: 'md' | 'tactil'
}

export type PropsEntrada = Base & Omit<InputHTMLAttributes<HTMLInputElement>, keyof Base | 'className' | 'size'>
export type PropsArea = Base & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, keyof Base | 'className' | 'rows'> & { filas?: number }
export type OpcionSeleccion = { valor: string; etiqueta: string; desactivado?: boolean }

/**
 * Grupo de opciones bajo un encabezado.
 *
 * Sirve para que en la lista se vea **de qué grupo viene cada cosa**. Con las
 * oficinas de una municipalidad, sin agrupar, el desplegable es un muro de
 * «OFICINA · ZONA» donde no se distingue dónde acaba el nombre de la oficina y
 * empieza el de la zona: las dos van en mayúsculas, con el mismo punto de
 * separación, y el ojo no tiene por dónde agarrarse. Con grupos, la zona es un
 * encabezado y el nombre de la oficina se lee solo.
 */
export type GrupoSeleccion = {
  etiqueta: string
  opciones: OpcionSeleccion[]
  /** Un color de CSS para el encabezado, por ejemplo el de la zona. */
  color?: string
}

export type PropsSeleccion = Base &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, keyof Base | 'className'> & {
    opciones?: OpcionSeleccion[]
    /** Cuando se pasan grupos, se ignoran `opciones` y se pinta la lista agrupada. */
    grupos?: GrupoSeleccion[]
    placeholder?: string
  }

const ALTO = { md: 'h-[var(--spacing-control)]', tactil: 'h-[var(--spacing-control-touch)]' } as const

const BASE_CONTROL =
  'w-full rounded-[var(--radius-control)] border border-input bg-surface px-3 text-foreground font-sans ' +
  'placeholder:text-muted-foreground transition-colors duration-[var(--transition-ui)] ' +
  'focus-visible:outline-none focus-visible:border-accion focus-visible:ring-2 focus-visible:ring-accion/30 focus-visible:bg-surface ' +
  'hover:border-accion/50 hover:bg-surface ' +
  'disabled:cursor-not-allowed disabled:opacity-50'

/** Atributos que comparten todos los controles. */
function useComunes({ ayuda, error, requerido, tamano = 'md' }: Base) {
  const id = useId()
  return {
    id,
    nombre: id,
    ariaDescritoPor: [ayuda ? `${id}-ayuda` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined,
    error,
    requerido,
    clases: `${BASE_CONTROL} ${ALTO[tamano]}${error ? ' border-destructive' : ''}`,
    // React espera un booleano o los literales "true"/"false" aqui, no texto
    invalido: error ? ('true' as const) : undefined,
  }
}

/** Encabezado con la etiqueta del campo y, si toca, la marca de "No aplica". */
function EncabezadoCampo({ etiqueta, requerido, noAplica, id }: Base & { id: string }) {
  // Sin etiqueta no se dibuja el encabezado: una fila vacía empuja el contenido
  if (!etiqueta) return null
  return (
    <div className="flex items-baseline justify-between gap-2">
      <label htmlFor={id} className="text-sm font-semibold">
        {etiqueta}
        {requerido ? (
          <span className="ml-0.5 text-destructive-strong" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {noAplica ? (
        <span className="rounded bg-muted px-1.5 py-0.5 text-2xs font-medium text-muted-foreground">No aplica</span>
      ) : null}
    </div>
  )
}

function Pie({ ayuda, error, acciones, id }: Base & { id: string }) {
  if (!ayuda && !error && !acciones) return null
  return (
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0 flex-1 text-sm">
        {error ? (
          <p id={`${id}-error`} role="alert" className="font-semibold text-destructive-strong">
            {error}
          </p>
        ) : ayuda ? (
          <p id={`${id}-ayuda`} className="text-muted-foreground">
            {ayuda}
          </p>
        ) : null}
      </div>
      {acciones ? <div className="flex shrink-0 gap-1.5">{acciones}</div> : null}
    </div>
  )
}

/* ══ Entrada de texto ══ */

export const Input = forwardRef<HTMLInputElement, PropsEntrada>(function Input(
  { etiqueta, ayuda, error, requerido, noAplica, acciones, className, tamano = 'md', ...props },
  ref,
) {
  const comunes = useComunes({ etiqueta, ayuda, error, requerido, tamano })
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <EncabezadoCampo etiqueta={etiqueta} requerido={requerido} noAplica={noAplica} id={comunes.id} />
      <input
        {...props}
        id={comunes.id}
        name={props.name ?? comunes.nombre}
        aria-describedby={comunes.ariaDescritoPor}
        aria-invalid={comunes.invalido}
        aria-required={requerido || undefined}
        required={requerido || undefined}
        className={comunes.clases}
        ref={ref}
      />
      <Pie ayuda={ayuda} error={error} acciones={acciones} etiqueta={etiqueta} id={comunes.id} />
    </div>
  )
})

/* ══ Área de texto ══ */

export const Textarea = forwardRef<HTMLTextAreaElement, PropsArea>(function Textarea(
  { etiqueta, ayuda, error, requerido, noAplica, acciones, className, tamano = 'tactil', filas = 3, ...props },
  ref,
) {
  const comunes = useComunes({ etiqueta, ayuda, error, requerido, tamano })
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <EncabezadoCampo etiqueta={etiqueta} requerido={requerido} noAplica={noAplica} id={comunes.id} />
      <textarea
        {...props}
        id={comunes.id}
        name={props.name ?? comunes.nombre}
        aria-describedby={comunes.ariaDescritoPor}
        aria-invalid={comunes.invalido}
        aria-required={requerido || undefined}
        required={requerido || undefined}
        rows={filas}
        className={`${BASE_CONTROL}${error ? ' border-destructive' : ''} min-h-24 resize-y py-2.5`}
        ref={ref}
      />
      <Pie ayuda={ayuda} error={error} acciones={acciones} etiqueta={etiqueta} id={comunes.id} />
    </div>
  )
})

/* ══ Lista desplegable ══ */

export const Select = forwardRef<HTMLSelectElement, PropsSeleccion>(function Select(
  { etiqueta, ayuda, error, requerido, noAplica, acciones, className, opciones, grupos, placeholder, tamano = 'md', ...props },
  ref,
) {
  const comunes = useComunes({ etiqueta, ayuda, error, requerido, tamano })
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <EncabezadoCampo etiqueta={etiqueta} requerido={requerido} noAplica={noAplica} id={comunes.id} />
      <div className="relative">
        <select
          {...props}
          id={comunes.id}
          name={props.name ?? comunes.nombre}
          aria-describedby={comunes.ariaDescritoPor}
          aria-invalid={comunes.invalido}
          aria-required={requerido || undefined}
          required={requerido || undefined}
          className={`${comunes.clases} appearance-none pr-9`}
          ref={ref}
        >
          {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
          {grupos?.length
            ? grupos.map((grupo) => (
                <optgroup
                  key={grupo.etiqueta}
                  label={grupo.etiqueta}
                  // El encabezado del grupo lleva el color de la zona. Los
                  // navegadores de escritorio respetan `color` y `background` en
                  // `optgroup`, así que el grupo se reconoce de un vistazo igual
                  // que en el resto de la aplicación.
                  style={grupo.color ? { color: grupo.color, backgroundColor: `color-mix(in srgb, ${grupo.color} 12%, var(--color-surface))` } : undefined}
                >
                  {grupo.opciones.map((opcion) => (
                    <option key={opcion.valor} value={opcion.valor} disabled={opcion.desactivado}>
                      {opcion.etiqueta}
                    </option>
                  ))}
                </optgroup>
              ))
            : opciones?.map((opcion) => (
                <option key={opcion.valor} value={opcion.valor} disabled={opcion.desactivado}>
                  {opcion.etiqueta}
                </option>
              ))}
        </select>
        <ChevronDown
          size={16}
          className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
      </div>
      <Pie ayuda={ayuda} error={error} acciones={acciones} etiqueta={etiqueta} id={comunes.id} />
    </div>
  )
})

/* ══ Casilla de verificación ══ */

export function Checkbox({
  etiqueta,
  descripcion,
  valor,
  alCambiar,
  disabled,
  className,
}: {
  etiqueta: ReactNode
  descripcion?: ReactNode
  valor: boolean
  alCambiar: (valor: boolean) => void
  disabled?: boolean
  className?: string
}) {
  const id = useId()
  const idDesc = `${id}-desc`
  return (
    <div className={cn('flex items-start gap-2.5', className)}>
      <div className="relative mt-0.5 size-[18px] shrink-0">
        <input
          id={id}
          type="checkbox"
          checked={valor}
          disabled={disabled}
          onChange={(evento) => alCambiar(evento.target.checked)}
          aria-describedby={descripcion ? idDesc : undefined}
          className="peer absolute inset-0 size-full cursor-pointer opacity-0"
        />
        <div className="pointer-events-none flex size-full items-center justify-center rounded-[4px] border border-input bg-surface transition-colors duration-[var(--transition-ui)] peer-checked:border-accion peer-checked:bg-accion peer-focus-visible:ring-2 peer-focus-visible:ring-accion peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background peer-disabled:opacity-50">
          <Check size={12} strokeWidth={3} className={cn("text-primary-foreground opacity-0 transition-opacity", valor && "opacity-100")} />
        </div>
      </div>
      <span className="min-w-0 flex-1">
        <label htmlFor={id} className={cn('cursor-pointer text-sm', disabled && 'cursor-not-allowed opacity-60')}>
          {etiqueta}
        </label>
        {descripcion ? (
          <span id={idDesc} className="block text-sm text-muted-foreground">
            {descripcion}
          </span>
        ) : null}
      </span>
    </div>
  )
}

/* ══ Interruptor ══ */

export function Switch({
  etiqueta,
  descripcion,
  valor,
  alCambiar,
  disabled,
  cargando,
  className,
}: {
  etiqueta: ReactNode
  descripcion?: ReactNode
  valor: boolean
  alCambiar: (valor: boolean) => void
  disabled?: boolean
  cargando?: boolean
  className?: string
}) {
  const id = useId()
  const idDesc = descripcion ? `${id}-desc` : undefined
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <span className="min-w-0 flex-1">
        <label htmlFor={id} className="block cursor-pointer text-sm font-semibold">
          {etiqueta}
        </label>
        {descripcion ? (
          <span id={idDesc} className="mt-0.5 block text-sm text-muted-foreground">
            {descripcion}
          </span>
        ) : null}
      </span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={valor}
        aria-describedby={idDesc}
        disabled={disabled || cargando}
        onClick={() => alCambiar(!valor)}
        className={cn(
          'relative mt-0.5 h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors duration-[var(--transition-ui-slow)]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accion focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          'disabled:cursor-not-allowed disabled:opacity-50',
          valor ? 'bg-accion' : 'bg-muted border-border hover:border-accion/40',
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            'pointer-events-none absolute top-0.5 left-0.5 size-4 rounded-full transition-all duration-[var(--transition-ui-slow)]',
            valor ? 'translate-x-5 bg-primary-foreground' : 'translate-x-0 bg-muted-foreground shadow-sm',
          )}
        />
      </button>
    </div>
  )
}

/* ══ Buscador con botón de limpiar ══ */

/**
 * Buscador que **filtra mientras se escribe**, y al que el navegador no le rellena nada.
 *
 * Filtra al teclear porque así se localiza mejor: cada letra acorta la lista. Se probó la
 * contraria —que solo filtrara al confirmar— y no es lo que se quiere.
 *
 * Lo que sí había que tapar era otra cosa: el navegador metía un correo en el campo y la
 * lista se filtraba por él sin que nadie lo hubiera escrito. Medido: la aplicación no
 * escribe nunca ahí —`setTexto` solo se llama al teclear y al limpiar—, así que el texto
 * tenía que venir del navegador. Y el motivo estaba a la vista: el placeholder era
 * «Nombre o correo…», y **«correo» es la palabra con la que el navegador decide que un
 * `type="text"` es un campo de correo** y le ofrece rellenarlo con una dirección guardada.
 *
 * De ahí las cuatro cosas de este campo:
 *
 * - **El placeholder no dice «correo» ni «email»**, que es lo que lo delata.
 * - **El `name` es neutro** («filtro»), sin rastro de dirección ni de búsqueda guardada.
 * - **`data-1p-ignore` y `data-lpignore`** para los gestores de contraseñas, que hacen lo
 *   mismo que el navegador y con más insistencia.
 * - **Al recibir el foco se selecciona lo que haya**, para que la siguiente tecla lo
 *   sustituya en vez de quedar detrás.
 */
export function SearchInput({
  valor,
  alCambiar,
  placeholder = 'Escribe para filtrar…',
  etiqueta,
  ayuda,
  className,
  autoFocus,
  onEnter,
  bloqueado = false,
}: {
  valor: string
  alCambiar: (valor: string) => void
  placeholder?: string
  etiqueta: string
  /** Se pinta debajo: qué se puede escribir y qué se encuentra con ello. */
  ayuda?: ReactNode
  className?: string
  autoFocus?: boolean
  onEnter?: () => void
  /** Mantiene el filtro sin admitir cambios mientras hay un diálogo abierto. */
  bloqueado?: boolean
}) {
  const id = useId()
  const idAyuda = ayuda ? `${id}-ayuda` : undefined
  const referencia = useRef<HTMLInputElement>(null)

  /*
    El navegador **guarda el texto de los campos y lo vuelve a poner**: Chrome y Edge en
    Windows lo reaplican al recargar, al ir «atrás» y al reiniciar el navegador, y lo
    hacen aunque el campo diga `autocomplete="off"`, que solo controla el autocompletado
    de formularios, no la restauración de sesión.

    Medido en el código, la aplicación no guarda el término en ninguna parte —`texto`
    arranca en `''` y la URL no lo lleva—, así que lo que reaparece al recargar viene
    del navegador. Y como el campo es controlado y filtra al teclear, ese texto
    reaparecido se convertía en filtro: la página cargaba ya filtrada por un correo que
    nadie había escrito en esa visita.

    Aquí se tapa en dos sitios, porque hay dos momentos distintos:

    1. **El campo no se pinta hasta después del primer render.** Si el `<input>` no
       existe cuando el navegador restaura, no hay dónde escribir. Con eso se tapa la
       restauración al cargar, que es la que se repite en cada reinicio.
    2. **Al volver de la caché del navegador** —ir «atrás» y volver—, el campo ya existe
       y hay que vaciarlo a mano. Se hace con el **setter nativo** de
       `HTMLInputElement`, porque si se asigna `elemento.value` pasa por el rastreador
       de React y este cree que el valor no ha cambiado.

    Solo se toca el valor cuando **difiere del de la aplicación**, así que un filtro
    puesto a propósito —por URL, por ejemplo— se respeta, y teclear no se entera: al
    teclear, el valor del campo y el de la aplicación van juntos.
  */
  const [listo, setListo] = useState(false)
  useEffect(() => {
    setListo(true)

    const vaciar = () => {
      const elemento = referencia.current
      if (!elemento || elemento.value === valor) return
      const nativo = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
      if (nativo) nativo.call(elemento, valor)
      else elemento.value = valor
    }

    vaciar()
    // Volver de «atrás» devuelve la página desde la caché y con el texto puesto.
    const alVolver = () => vaciar()
    window.addEventListener('pageshow', alVolver)
    return () => window.removeEventListener('pageshow', alVolver)
  }, [valor])

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {/*
        Rótulo visible, como `Select` y `Input`.

        Antes el buscador no pintaba ninguno: `etiqueta` solo iba al `aria-label`, así
        que en una barra de cuatro filtros el buscador quedaba **26 px más arriba**
        que los otros tres, que sí llevan su rótulo encima. Medido, no era impresión.

        Se usa un `<label>` propio y no `EncabezadoCampo` porque este campo no tiene
        los adornos de un formulario (asterisco de obligatorio, «no aplica»), pero el
        texto, el peso y el sitio son los mismos: así se lee igual en toda la
        aplicación.
      */}
      <label htmlFor={id} className="text-sm font-medium">
        {etiqueta}
      </label>
      <div className="relative">
        <Search
          size={16}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        {/*
          El campo entra después del primer render. Es lo que impide que el navegador
          tenga dónde restaurar un término guardado: si el `<input>` todavía no existe
          cuando restaura, no hay nada que rellenar. El espacio en blanco es de un
          fotograma y el rótulo y el marco ya están puestos, así que no se ve un hueco.
        */}
        {listo ? (
          <input
            ref={referencia}
            id={id}
          /*
            `type="text"` y no `type="search"`, a propósito.

            Medido: con `type="search"` el navegador guarda lo escrito en ese campo por
            origen y lo vuelve a ofrecer, y el campo es controlado, así que si el
            navegador lo rellena **la aplicación lo acepta como filtro** y lanza la
            petición con ese texto. `role="searchbox"` mantiene el significado para el
            lector de pantalla, que es lo único que se pierde por no ser un `search`.
          */
          type="text"
          role="searchbox"
          inputMode="search"
          value={valor}
          // Fuera del buscador nadie puede editarlo, tampoco el autocompletado.
          readOnly={bloqueado}
          autoFocus={autoFocus}
          name={`${id}-filtro`}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          // Gestores de contraseñas: 1Password y LastPass respetan estas marcas y no
          // tocan el campo.
          data-1p-ignore="true"
          data-lpignore="true"
          data-form-type="other"
          onChange={(evento) => {
            const entrada = evento.nativeEvent as InputEvent
            // El autocompletado puede emitir un input real sobre un campo sin foco.
            // Solo una edición en el buscador debe cambiar los filtros.
            if (
              document.activeElement !== evento.currentTarget ||
              bloqueado ||
              !entrada.isTrusted ||
              !entrada.inputType ||
              entrada.inputType === 'insertReplacementText'
            ) {
              // Restaura también el rastreador de React: si solo se usa el setter
              // nativo, un segundo intento con el mismo correo puede pasar inadvertido.
              evento.currentTarget.value = valor
              return
            }
            alCambiar(evento.currentTarget.value)
          }}
          /*
            Si el campo llega con algo puesto —porque el navegador lo metió—, al
            pulsarlo se selecciona todo y la siguiente tecla lo sustituye en lugar de
            quedar detrás.

            Va en `onClick` y no en `onFocus` a propósito: el clic **coloca el cursor**
            después de que el campo reciba el foco, así que seleccionar en `onFocus` no
            llega a verse. Medido: con `onFocus` la selección salía `[14,14]`, es decir
            el cursor al final y sin nada seleccionado.
          */
          onClick={(evento) => {
            if (evento.currentTarget.value) evento.currentTarget.select()
          }}
          onKeyDown={(evento) => {
            if (evento.key === 'Enter') {
              evento.preventDefault()
              onEnter?.()
            } else if (evento.key === 'Escape' && valor) {
              evento.preventDefault()
              alCambiar('')
            }
          }}
          placeholder={placeholder}
          aria-label={etiqueta}
          aria-describedby={idAyuda}
          className={`${BASE_CONTROL} h-[var(--spacing-control)] pr-9 pl-9`}
          />
        ) : null}
        {listo && valor ? (
          <button
            type="button"
            onClick={() => alCambiar('')}
            aria-label="Limpiar la búsqueda"
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X size={14} aria-hidden="true" />
          </button>
        ) : null}
      </div>
      {ayuda ? (
        <span id={idAyuda} className="text-sm text-muted-foreground">
          {ayuda}
        </span>
      ) : null}
    </div>
  )
}
