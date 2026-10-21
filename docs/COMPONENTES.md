# Componentes reutilizables

Inventario de los componentes de `frontend/src/componentes/`, con su propósito y
un ejemplo de uso. La regla es simple: **si algo se usa en dos pantallas, es un
componente**. Si solo se usa en una, vive en esa pantalla.

Todos comparten el mismo aspecto, el mismo foco visible y los mismos tokens de
color. Ninguno escribe un hexadecimal.

---

## Botón — `Boton.tsx`

El único botón de la aplicación. Un `<button>` suelto solo se acepta dentro de un
componente propio.

| Propiedad | Valores | Para qué |
|---|---|---|
| `variante` | `primario`, `secundario`, `fantasma`, `peligro`, `exito` | Peso visual de la acción |
| `tamano` | `pequeno`, `mediano`, `grande` | Tamaño; el cuerpo nunca baja de 16 px |
| `cargando` | booleano | Muestra el giro y desactiva el botón (evita dobles envíos) |
| `anchoCompleto` | booleano | Para formularios de una columna |
| `icono` | `ReactNode` | Icono a la izquierda del texto |

```tsx
<Boton variante="primario" cargando={guardando} icono={<IconoGuardar size={18} />} onClick={guardar}>
  Guardar cambios
</Boton>
```

---

## Campo — `Campo.tsx`

Etiqueta, control, ayuda y error siempre juntos y siempre conectados por
`aria-describedby`. Tres variantes en un solo componente:

```tsx
// Texto
<Campo etiqueta="Nombre de la zona" required value={nombre} onChange={setNombre} />

// Área de texto
<Campo etiqueta="Descripción" multilinea rows={4} maxLength={600} value={descripcion} onChange={setDescripcion} />

// Lista
<Campo
  etiqueta="Oficina"
  value={oficinaId}
  onChange={setOficinaId}
  opciones={oficinas.map((o) => ({ valor: o.id, etiqueta: o.nombre }))}
  placeholder="Elige una oficina"
/>
```

Propiedades propias: `etiqueta`, `ayuda`, `error`, `required`, `noAplica` y
`acciones` (botones pequeños a la derecha, por ejemplo "Limpiar"). El resto son
las propiedades nativas del elemento (`type`, `value`, `onChange`, `rows`…).

`noAplica` pinta la etiqueta "No aplica" sin bloquear el campo: es la forma
visible de la regla de inventario.

---

## Panel — `Panel.tsx`

La caja de contenido del sistema: mismo borde, mismo relleno, mismo encabezado.
Exporta cuatro piezas que se usan juntas en casi todas las pantallas:

| Componente | Para qué |
|---|---|
| `Panel` | Contenedor con `titulo`, `descripcion`, `acciones` y `sinRelleno` |
| `Cargando` | Estado de carga con la silueta del contenido que aparecerá |
| `Vacio` | Cuando no hay datos: título, explicación y una acción, nunca una pantalla en blanco |
| `Nota` | Aviso en línea con tono `info`, `aviso`, `peligro` o `exito` |

```tsx
<Panel
  titulo="Oficinas de la zona"
  descripcion="Sin cuenta de acceso: solo organizan la información"
  acciones={<Boton onClick={abrirAlta}>Añadir oficina</Boton>}
>
  ...
</Panel>
```

---

## Insignia — `Insignia.tsx`

Etiquetas de estado. Cada estado tiene un nombre en palabras y un color; nunca se
elige el color en la pantalla.

```tsx
<Insignia tono="exito">Completo</Insignia>
<InsigniaEstado estado={ticket.estado} />        {/* Nuevo, En progreso… */}
<InsigniaPrioridad prioridad={ticket.prioridad} />{/* Baja, Crítica… */}
<InsigniaCampo estado="no_aplica" />              {/* Pendiente, No aplica… */}
<InsigniaDisponibilidad estado={tecnico.estado} etiqueta={tecnico.etiqueta} />
```

---

## Tabla — `Tabla.tsx`

Listado de datos con encabezado fijo y estado vacío explicativo. En pantallas
chicas cada columna marcada con `ocultarEnMovil` desaparece.

```tsx
const columnas: Columna<Ticket>[] = [
  { clave: 'codigo', titulo: 'Ticket', render: (t) => <Link to={`/tickets/${t.id}`}>{t.codigo}</Link> },
  { clave: 'oficina', titulo: 'Oficina', ocultarEnMovil: true, render: (t) => t.oficina_nombre },
]

<Tabla etiqueta="Listado de tickets" columnas={columnas} filas={tickets} claveFila={(t) => t.id}
       alPulsarFila={abrir} vacio={{ titulo: 'No hay tickets', icono: <IconoLista size={32} /> }} />
```

`Definiciones` sirve para el bloque de datos en dos columnas (ficha de un equipo).

---

## Modal — `Modal.tsx`

Diálogo accesible: cierra con Escape, atrapa el foco dentro, devuelve el foco al
elemento que lo abrió y bloquea el desplazamiento de fondo. `tamano` va de
`pequeno` a `pantalla`.

`Confirmacion` es la variante para acciones con consecuencia (dar de baja, cerrar
una campaña) y lleva su propio botón de cancelar.

```tsx
<Modal
  abierto={abierto}
  titulo="Marcar como resuelto"
  descripcion="Escribe una sola frase de cómo se resolvió. Es la que verá la persona."
  onCerrar={cerrar}
  pie={
    <>
      <Boton onClick={cerrar}>Cancelar</Boton>
      <Boton variante="primario" disabled={nota.length < 5} onClick={resolver}>Resolver</Boton>
    </>
  }
>
  <Campo etiqueta="Nota de resolución" multilinea required value={nota} onChange={setNota} />
</Modal>
```

---

## Selector — `Selector.tsx`

Dos controles de elección:

- **`SelectorMultiple`**: lista con búsqueda e iniciales, para elegir a quién
  afecta un problema o qué equipo tiene la falla. `maximo={1}` lo convierte en
  elección única.
- **`OpcionesExclusivas`**: botones grandes en tarjetas, para el paso 1 del
  reporte y para la urgencia.

```tsx
<SelectorMultiple
  etiqueta="¿A quién afecta?"
  descripcion={`Compañeros de ${usuario.oficina_nombre}`}
  elementos={personas.map((p) => ({ id: p.id, nombre: p.nombre, detalle: p.cargo, iniciales: p.iniciales }))}
  seleccionados={afectadoId}
  onCambiar={setAfectadoId}
  maximo={1}
  vacio="Tu oficina todavía no tiene cuentas registradas."
/>
```

---

## Migas — `Migas.tsx`

`Migas` dibuja la ruta (Zona › Oficina › Usuario) y `EncabezadoPagina` es el
encabezado de toda pantalla: migas, título, descripción y acciones. Toda pantalla
empieza con `EncabezadoPagina`, nunca con un `<h1>` suelto.

---

## Gráfico — `Grafico.tsx`

Gráficos en SVG, sin librerías. Recibe un bloque del panel analítico y decide
solo: si `suficiente_datos` es `false`, muestra el mínimo de registros que hace
falta en vez de dibujar una curva.

```tsx
<Grafico bloque={panel.ranking_oficinas} alto={220} />
```

---

## Iconos — `iconos.tsx`

Un solo archivo con los iconos de Lucide y su nombre en español
(`IconoBandeja`, `IconoEscudo`, `IconoRayo`…). Para añadir uno: se reexporta en
`iconos.tsx` y se crea el alias. **Ningún componente importa iconos de otra
librería y no hay emojis en ninguna pantalla.**

---

## Avisos — `AvisosProveedor.tsx`

Un solo lugar para comunicar el resultado de una acción. Los mensajes del backend
se muestran tal cual, porque ya están escritos en lenguaje claro.

```tsx
const { exito, errorApi } = useAvisos()

await guardar()
exito('Guardado.')

try {
  await accion()
} catch (fallo) {
  errorApi(fallo, 'No pudimos guardar')  // muestra el mensaje del servidor
}
```

---

## Proveedores

| Proveedor | Responsabilidad |
|---|---|
| `ProveedorSesion` | Entra, sale, renueva el token y expone `puede(permiso)`, `esAdmin`, `esTecnico` |
| `ProveedorAvisos` | Avisos flotantes accesibles (`role="status"` y `role="alert"`) |

`ProveedorSesion` guarda el token en `sessionStorage` (se pierde al cerrar la
pestaña) y el refresco viaja en cookie `httpOnly`. Cuando el token expira, el
cliente HTTP renueva una sola vez y, si no puede, avisa al proveedor para que la
pantalla vuelva al acceso.

---

## Cliente HTTP — `api/cliente.ts`

Un solo punto de salida hacia la API:

- Añade `Authorization` y `X-CSRF-Token` automáticamente.
- Convierte cualquier error (de red o del servidor) en `ErrorPeticion` con el
  mensaje que ya escribió el backend.
- Renueva la sesión una sola vez ante un 401 antes de rendirse.
- `rutaApi()` une la base sin duplicar el prefijo, y por eso las descargas
  funcionan tal cual las entrega el backend.

`api/servicios.ts` agrupa las rutas por pantalla. Ningún componente escribe una
URL a mano.

---

## Reglas que no se rompen

1. Los componentes propios usan propiedades en español (`titulo`, `descripcion`,
   `acciones`); los controles nativos usan las del HTML (`value`, `type`,
   `required`, `rows`).
2. Todo color viene de un token semántico. Si hace falta un color nuevo, se
   añade al `@theme` de `estilos/tokens.css`, nunca a un componente.
3. Todo texto visible está en español claro y sin jerga técnica.
4. Si un componente necesita un icono, es un icono de Lucide. Cero emojis.
5. Cada estado vacío dice qué falta y, si aplica, ofrece la acción para resolverlo.