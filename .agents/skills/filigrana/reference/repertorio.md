# Repertorio de direcciones

Catálogo curado en lugar de una base de datos de estilos genéricos. Cada dirección es un punto de partida: se ajusta al proyecto, no se copia. Las fuentes están en Google Fonts y tienen `latin-ext`. Los colores van en OKLCH: claro / oscuro.

Formato: **tokens** · **fuentes** · **radio** · **movimiento** · **firma** · **cuándo**.

---

## 1. Editorial suizo
- Papel `oklch(96% .012 85)` / `oklch(17% .004 85)` · tinta `oklch(19% .003 85)` / `oklch(93% .012 85)` · filete `oklch(87% .02 85)` · señal bermellón `oklch(60% .2 35)`.
- Inter Tight 400–600 + JetBrains Mono para etiquetas y cifras.
- 2px · subrayados que crecen (180ms) y nada más.
- **Firma:** rejilla de 12 columnas a la vista con filetes, secciones numeradas `01 —` y cifras tabulares grandes alineadas a la base.
- Dashboards, herramientas internas, informes.

## 2. Monocromo absoluto
- Blanco `oklch(99% 0 0)` / negro `oklch(0% 0 0)` · grises cálidos `oklch(92% .004 90)` · acción = negro (no hay color de marca) · estados desaturados (salvia, ocre, rosa viejo).
- Space Grotesk + Manrope.
- 4–6px · 120–200ms, `cubic-bezier(.22,1,.36,1)`.
- **Firma:** bandas invertidas a sangre (sección negra entera) y el color solo aparece para significar estado.
- SaaS serio, CRM, producto con datos.

## 3. Brutalismo tipográfico
- Blanco crudo `oklch(98% 0 0)` · negro `oklch(10% 0 0)` · un color ácido por proyecto (amarillo `oklch(92% .19 105)` o rojo `oklch(58% .24 28)`).
- Archivo Black / Anton para display + Space Mono.
- 0px · cortes sin transición; hover que invierte colores.
- **Firma:** titulares de 15–25vw (con `clamp`) que se salen del contenedor, bordes de 2–3px y HTML que se ve.
- Portfolios, eventos, marcas jóvenes.

## 4. Blueprint técnico
- Fondo azul cianotipo `oklch(32% .09 255)` o papel milimetrado `oklch(97% .01 230)` · líneas `oklch(80% .05 230 / .4)` · tinta blanca o azul · acento naranja de seguridad `oklch(70% .19 50)`.
- IBM Plex Sans Condensed + IBM Plex Mono.
- 0px · trazos SVG que se dibujan (`stroke-dashoffset`) al entrar en pantalla.
- **Firma:** retícula de fondo visible, cotas y anotaciones con flechas en los elementos, coordenadas en las esquinas.
- Dev tools, infraestructura, hardware, APIs.

## 5. Periódico
- Papel prensa `oklch(95% .015 90)` · tinta `oklch(15% 0 0)` · rojo de cabecera `oklch(50% .19 25)`.
- Newsreader o Libre Caslon (titulares y texto) + Schibsted Grotesk para datos.
- 0px · ninguno salvo la carga escalonada de columnas.
- **Firma:** multicolumna real (`columns`), capitulares, cabecera tipo mancheta con fecha y número de edición, filetes dobles.
- Blogs, changelogs, documentación narrativa, landing de contenido.

## 6. Terminal cálido
- Fondo `oklch(18% .01 60)` · fósforo ámbar `oklch(82% .14 75)` o verde `oklch(85% .17 145)` · texto `oklch(88% .02 75)`.
- JetBrains Mono / Martian Mono para todo; display en Martian Mono expandida.
- 0px · cursor que parpadea solo donde hay foco y escritura carácter a carácter en un único sitio.
- **Firma:** la UI como sesión de terminal: prompts `›`, salidas en bloques, atajos visibles `[⌘K]`.
- CLIs, herramientas para desarrolladores, paneles de operación.

## 7. Cartel Bauhaus
- Crema `oklch(95% .03 90)` · rojo `oklch(56% .21 30)` · azul `oklch(45% .15 260)` · amarillo `oklch(86% .16 95)` · negro.
- Familjen Grotesk o Bricolage Grotesque + DM Mono.
- 0px o círculos perfectos · formas geométricas que rotan o deslizan con scroll (scroll-driven).
- **Firma:** composición con formas primarias grandes como estructura y texto rotado 90°.
- Landings culturales, educación, productos creativos.

## 8. Archivo / ficha
- Cartulina `oklch(93% .03 80)` · tinta sepia `oklch(28% .03 60)` · sello rojo `oklch(52% .17 25)` · etiquetas `oklch(88% .05 95)`.
- Instrument Serif + IBM Plex Mono.
- 2px · fichas que se apilan y deslizan como en un fichero.
- **Firma:** cada elemento es una ficha catalogada con signatura (`REF. 0042/B`), sellos y campos con línea de puntos.
- Inventarios, CRM, colecciones, gestión documental.

## 9. Laboratorio
- Blanco clínico `oklch(99% .003 200)` · gris acero `oklch(60% .01 230)` · verde instrumento `oklch(72% .17 160)` · rojo alarma.
- Geist + Geist Mono.
- 4px · lecturas numéricas que cuentan hasta su valor (solo una vez) y barras que llenan.
- **Firma:** densidad de instrumento: micro-gráficas en cada fila, unidades siempre visibles y la escala de medida como decoración.
- Monitorización, salud, finanzas, IoT.

## 10. Revista de moda
- Hueso `oklch(96% .01 70)` · negro · un color de temporada saturado (`oklch(65% .2 350)` o `oklch(55% .15 150)`).
- Fraunces (ópticos, itálicas extremas) + Hanken Grotesk.
- 0px · imágenes que se revelan con `clip-path` y titulares que cambian de peso al hacer scroll (fuente variable).
- **Firma:** mezcla de tamaños desproporcionada (una palabra a 200px junto a un párrafo de 12px), itálica como gesto y el espacio en blanco como lujo.
- Marca personal, e-commerce de autor, portfolios de diseño.

## 11. Señalética
- Fondo `oklch(22% 0 0)` o amarillo vial `oklch(88% .17 95)` · blanco · códigos de color funcionales (línea 1, 2, 3).
- Big Shoulders Display + Chivo Mono.
- 4px o píldoras completas · los indicadores se desplazan como paneles de aeropuerto (split-flap sobrio).
- **Firma:** el wayfinding como interfaz: flechas grandes, pictogramas, códigos de línea, numeración de andén.
- Logística, transporte, reservas, apps con flujos.

---

## Combinar

Se pueden cruzar dos direcciones (estructura de una + paleta de otra), pero **la firma solo puede ser una**. Si ninguna encaja, inventa una nueva con el mismo formato y, si funciona, añádela aquí.
