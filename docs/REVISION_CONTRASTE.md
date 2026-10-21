# Contraste y navegación

15/10/2026.

- Fondo general más neutro; bordes de paneles y campos más definidos; cabeceras diferenciadas y sombras de paneles y tarjetas más visibles.
- Texto secundario reforzado en los temas claro y oscuro; límites más visibles en navegación.
- Menú contraído: nombres accesibles, etiquetas al pasar el cursor y submenús con fondo opaco, borde y sombra. Se cierran al elegir una opción.
- Corrección de causa: el enlace NavLink usaba una función en `className`. El Slot del tooltip convertía esa función en texto al combinar propiedades y se perdían sus clases, incluidos los colores y el tamaño del enlace. Ahora recibe clases calculadas como texto, conservando los colores y el estado activo.
- Pruebas sobre compilación de producción para ambos temas: contraste de texto e iconos en navegación, etiquetas y submenús (al menos 4,5:1 en los elementos comprobados), presencia de bordes y sombras de tablas, contraer/ampliar y navegación desde submenús.
- Capturas en `docs/muestras-contraste` para revisión visual.
