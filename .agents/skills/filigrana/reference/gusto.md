# Gusto de Bilal

Perfil sacado de sus proyectos (dashboard-suministros «Editorial suizo», Vantia). Es el punto de partida cuando el proyecto no ha decidido nada. **Edítalo cuando cambie el gusto**: manda sobre cualquier otra skill de diseño.

## Lo que es

- **El riesgo va en la tipografía, la composición y un único color con significado. Nunca en la decoración.**
- Base neutra y cálida (papel, tinta, negro) + **un solo color señal**. El color se reserva para significar estado o acción, no para adornar.
- **Filetes de 1px en vez de cajas con sombra.** La estructura la dan los bordes; la sombra solo marca lo que flota (menús, diálogos).
- Radios pequeños: 0–4px en editorial, 4–8px como máximo en producto. Nunca `rounded-2xl` en tarjetas.
- Números tabulares (`font-variant-numeric: tabular-nums`). Una cifra grande no es importante por ser grande: el peso se lo da la composición.
- Etiquetas en mono, pequeñas, en versalitas o en mayúsculas con tracking; secciones numeradas (01, 02…).
- Movimiento rápido y seco: 120–240ms, `cubic-bezier(.22,1,.36,1)`, **sin rebotes ni springs**. Respeta `prefers-reduced-motion`.
- Gráficas hechas a mano (SVG: ticks, marcadores, rejillas de puntos, sparklines) antes que una librería genérica de charts.
- Iconos de trazo y con moderación. **Nada de emojis.**
- Claro y oscuro siempre. El oscuro es negro puro o casi negro cálido (`#000`, `#121211`). **Nunca navy ni slate.**
- Siempre tokens semánticos en CSS variables; ningún color suelto en los componentes.
- Interfaces en español (y catalán): fuentes con soporte `latin-ext`.

## Tokens de referencia

Editorial suizo (dashboard-suministros):
```css
--papel: #f4f1ea; --tinta: #141413; --filete: #d9d4c7;
--senal: #e2401c;  /* bermellón, único acento */
--ok: #4a6b3a; --aviso: #a8781c;  /* oliva, ocre */
/* oscuro */ --papel: #121211; --tinta: #ece8de; --senal: #ff5a33;
--radio: 2px;
```
Monocromo (Vantia):
```css
--accion: #111111;  /* primario negro, no azul */
--texto: #171717; --borde: #e8e8e6; --borde-fuerte: #dadad8; --suave: #fafaf9;
--exito: #6f9483; --aviso: #d87932; --peligro: #c76e78;  /* desaturados */
/* oscuro */ --fondo: #000; --superficie: #0c0c0c; --borde: #1e1e1e;
```

## Fuentes que ya ha elegido

- Space Grotesk (títulos) + Manrope (texto), para landing.
- Inter Tight (títulos) + JetBrains Mono (etiquetas y números), para producto.
- Inter solo si hay un motivo explícito (ya está en el proyecto). **Nunca como elección por defecto.**

## Anti-lista (nunca)

Gradientes morados, azules o "aurora" · orbs, blobs, bokeh, mallas de fondo · glassmorphism por todas partes · hero centrado sobre fondo oscuro con glow · tres tarjetas iguales de features con icono arriba · tarjetas dentro de tarjetas · `shadow-lg/xl` como estructura · `rounded-2xl` o más · azul Tailwind/Atlassian o violeta de stock como primario · paleta slate · beige plano sin intención · gris claro para el texto "por elegancia" · `transition: all` · micro-animaciones en bucle · rebotes · emojis como iconos · texto por debajo de 11px · tipografía escalada al viewport sin `clamp` · librerías de charts con su estilo por defecto.
