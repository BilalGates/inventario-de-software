# Diseñar

Objetivo: que nadie pueda decir "esto lo ha hecho una IA". Lo original y arriesgado, pero usable.

## 0. Contexto (antes de nada)

1. Lee lo que ya hay: `PRODUCT.md`, `DESIGN.md`, `.agents/proyecto.md`, tokens (`globals.css`, `@theme`, config de Tailwind), un componente representativo. **Si el proyecto ya tiene identidad, se respeta y se lleva más lejos; no se sustituye.**
2. Lee `gusto.md`. Si el proyecto no ha decidido nada, ese es el punto de partida.

## 1. Lectura en una línea

`Leo esto como: <tipo de página> para <audiencia>, registro <marca|producto>, tono <…>, hacia <dirección>.`

- **Marca** (landing, portfolio, campaña): el diseño ES el producto. Se arriesga más.
- **Producto** (dashboard, admin, herramienta): el diseño SIRVE al producto. Se arriesga en tipografía, rejilla y datos, no en la legibilidad.

Solo si la lectura es genuinamente ambigua: **una** pregunta. Si no, declara la lectura y sigue.

## 2. Diales

| Dial | Base | Marca | Producto |
|---|---|---|---|
| VARIANCE (1 simetría … 10 caos) | 8 | 8–10 | 6–7 |
| MOTION (1 estático … 10 cine) | 4 | 4–6 | 2–4 |
| DENSITY (1 galería … 10 cabina) | 5 | 3–4 | 6–8 |

Se cambian si el usuario lo pide ("más loco", "más calmado"). MOTION nunca significa rebotes: significa más coreografía (entradas escalonadas, scroll-driven), siempre seco.

## 3. Direcciones (con varios modelos)

En trabajos nuevos o rediseños grandes, **tres direcciones** antes de construir:

- Elige tres entradas de `repertorio.md` que encajen con la lectura (o inventa una cuando ninguna encaje). Al menos una ha de ser incómoda.
- Lanza en paralelo, en solo lectura, una por motor (modelos distintos producen propuestas realmente distintas):
  ```bash
  node DIR/scripts/delegar.mjs --motor codex --nivel fuerte "<encargo de dirección>" &
  node DIR/scripts/delegar.mjs --motor agy   --nivel fuerte "<encargo de dirección>" &
  ```
  y la tercera la haces tú (o `--motor claude`).
- Encargo de dirección: contexto + lectura + dirección asignada + "Devuelve SOLO: tokens (OKLCH, claro y oscuro), pareja tipográfica con escala, rejilla, 3 decisiones de composición, la firma, el movimiento. Sin código de componentes. Prohibido: <anti-lista de gusto.md>".
- Presenta las tres en una tabla corta y deja elegir (o mezcla con criterio). En cambios pequeños se salta este paso: decide tú y sigue.

## 4. Firma obligatoria

Cada diseño declara **un** movimiento arriesgado y lo ejecuta en serio, por ejemplo:
- escala tipográfica extrema (un titular de 9–10 columnas contra texto de 13px)
- rejilla rota o asimétrica, columnas desplazadas, contenido que cruza el margen
- filetes y numeración editorial en lugar de cajas
- los datos como gráfica (cifras tabulares gigantes como textura, ticks, regletas)
- un único color señal usado con violencia en un solo punto
- tipografía como imagen (sin fotos ni ilustraciones)
- la navegación como índice de libro, la tabla como pieza protagonista

## 5. Prueba de genericidad

Antes de entregar: **si cambias el logo y el diseño serviría para cualquier SaaS, rehazlo.** Y: ¿qué tres elementos son los mismos que en cualquier plantilla de shadcn? Cámbialos.

## 6. Construir

- Tokens primero (CSS variables semánticas, claro y oscuro), componentes después. Ningún color suelto.
- Tipografía: máximo 3 familias, contraste entre pasos ≥1.25, `clamp()` para títulos, `text-wrap: balance` en h1–h3, 65–75ch en texto corrido, tracking de display ≥ -0.04em.
- Composición con CSS Grid y subgrid; container queries antes que breakpoints cuando el componente vive en sitios distintos.
- Movimiento: solo `transform` y `opacity`, con propiedad concreta y nunca `transition: all`. Scroll-driven animations y View Transitions nativas antes que librerías. `prefers-reduced-motion` siempre.
  - **¿Debe animarse?** Lo que se usa cientos de veces al día (atajos de teclado, cambiar de pestaña, abrir el menú de comandos) no se anima, o se anima en ≤120ms.
  - Botones: `:active { transform: scale(.97) }`. Nunca se entra desde `scale(0)`: empieza en `.95` con opacidad 0.
  - Popovers y menús crecen desde su disparador (`transform-origin` hacia el botón), no desde el centro.
  - Entradas con `@starting-style` + transición CSS (se pueden interrumpir) antes que keyframes.
  - La salida, más rápida que la entrada (≈ 2/3). Escalonado de listas 30–50ms por elemento, máximo 6–8 elementos.
  - Hover solo en `@media (hover: hover)`: en táctil se queda pegado.
- Gráficas: SVG a mano para lo simple; si hace falta una librería, se reestiliza entera con los tokens.
- Ponytail también aquí: el componente que ya existe se reutiliza; nada de una librería de UI nueva para dos botones.

## 7. Suelos innegociables

Contraste AA (4.5:1 texto, 3:1 grande y UI) · foco visible y propio · objetivos táctiles ≥44px · nada por debajo de 11px · `prefers-reduced-motion` · alt en imágenes con contenido · sin saltos de layout (dimensiones reservadas) · claro y oscuro · funciona a 360px de ancho.

## 8. Cerrar

1. `node DIR/scripts/detectar-slop.mjs <carpeta>`: arregla lo que marque o justifica en una línea por qué se queda.
2. Mírala de verdad: captura en el navegador (Chrome o el skill `run`), en claro, en oscuro y en móvil. Lo que no se ha visto no está terminado.
3. Entrega: lectura, dirección, firma, tokens nuevos, y qué se comprobó visualmente.
