---
name: filigrana
description: "Echa un cable con todo: diseño original y arriesgado con el gusto de Bilal (nunca el aspecto por defecto de la IA), código mínimo estilo ponytail, depuración con el diff más pequeño posible, auditorías medidas de rendimiento y limpieza, y delegación a otras sesiones (claude, codex, opencode, agy) eligiendo el modelo según el razonamiento que pide la tarea. Modos: diseña, depura, audita, revisa, delega. Úsala en cualquier tarea de código o UI, al pedir un diseño, una landing, un dashboard, al corregir un bug, al auditar o al pedir una segunda opinión de otro modelo."
argument-hint: "[diseña|depura|audita|revisa|delega] [encargo]"
---

# filigrana

Trabajo fino. Poco código, bien puesto. Diseño con firma propia.

`DIR` = la carpeta de esta skill: `.agents/skills/filigrana` en proyectos con el kit de agentes, `~/.claude/skills/filigrana` en el resto. Los scripts se llaman `node DIR/scripts/<script>.mjs`.

Es la skill central del kit: sustituye a las antiguas `ponytail*`, `depurar`, `rendimiento`, `revision-codigo`, `ui-ux-pro-max`, `design-taste-frontend` y `emil-design-eng`.

## Modos

Si el usuario no nombra el modo, infiérelo del encargo. Carga **solo** la referencia del modo:

| Modo | Cuándo | Lee |
|---|---|---|
| `diseña` | UI nueva, rediseño, landing, dashboard, componente, "hazlo bonito" | `reference/disenar.md` + `reference/gusto.md` (+ `reference/repertorio.md` al elegir dirección) |
| `depura` | bug, test rojo, error de CI, "no funciona" | `reference/depurar.md` |
| `audita` | "audita", "va lento", "limpia", "qué sobra", "qué dejamos para luego" (deuda `ponytail:`) | `reference/auditar.md` |
| `revisa` | revisar un diff o PR | `reference/auditar.md` § Revisión |
| `delega` | segunda opinión, tarea paralela, "pásaselo a codex" | `reference/delegar.md` |

Un encargo puede cruzar modos (construir UI → `diseña`; arreglar un fallo visual → `depura` primero).

## Reglas siempre activas (ponytail)

Antes de escribir una línea, sube la escalera y para en el primer peldaño que aguante:

1. ¿Hace falta? Si es especulativo, no se hace; dilo en una línea.
2. ¿Ya existe en este repo? Helper, tipo, patrón, token → reutiliza. Busca antes de escribir.
3. ¿Lo hace la librería estándar?
4. ¿Lo hace la plataforma? HTML nativo, CSS antes que JS, restricción de BD antes que código.
5. ¿Lo resuelve una dependencia ya instalada? Nunca una nueva para lo que hacen diez líneas.
6. ¿Cabe en una línea?
7. Solo entonces: el mínimo que funciona.

- Entiende el problema **entero** antes de subir la escalera: el diff más corto en el sitio equivocado es un segundo bug.
- Sin abstracciones de una implementación, sin config para valores que no cambian, sin andamiaje "para luego", sin ficheros nuevos si cabe en uno existente.
- Borrar antes que añadir. Aburrido antes que ingenioso.
- Escribe como el código vecino: nombres, idioma, densidad de comentarios.
- Atajo deliberado con techo conocido → comentario `ponytail: <techo>, <cuándo mejorarlo>`.
- Lógica no trivial deja **una** comprobación ejecutable (un test o un assert), no una suite.
- Nunca se simplifica: validación en fronteras de confianza, manejo de errores que evita pérdida de datos, seguridad, accesibilidad, lo pedido explícitamente.
- Entrega: código primero, después como mucho tres líneas — qué se saltó y cuándo añadirlo. Si la explicación es más larga que el código, sobra la explicación (salvo que el usuario la pida).

## Razonamiento → modelo

Clasifica cada tarea o subtarea antes de delegarla:

| Nivel | Tareas típicas |
|---|---|
| `barato` | buscar, listar, resumir, commits, renombrar, preguntas de "dónde está" |
| `medio` | construir algo acotado, tests, depurar con causa clara, traducir |
| `fuerte` | revisión adversarial, auditoría, diseño visual, depurar sin causa tras 2 hipótesis |
| `maximo` | arquitectura, modelo de datos, decisiones difíciles de revertir, concurrencia, seguridad |

- Dentro de esta sesión: subagente nativo (Agent tool) con `model` = `haiku` | `sonnet` | `opus` | `fable` según el nivel.
- Otra sesión / otro motor: `node DIR/scripts/delegar.mjs --nivel <nivel> --motor <claude|codex|opencode|agy> "encargo"`. Solo lectura por defecto. Detalles y qué motor elegir en `reference/delegar.md`.
- Si el proyecto tiene el kit (`.agents/agents/<id>/agent.md`), delega a sus roles con `--agente <id>`: hereda su ficha y su nivel.
- No delegues lo que resuelves en dos llamadas: cada sesión nueva arranca en frío.

## Proyecto

Si el modo `diseña` necesita edición en vivo en el navegador, la skill `impeccable` (si está instalada) tiene su modo `live`.

Si existe `.agents/proyecto.md`, `AGENTS.md`, `CLAUDE.md`, `PRODUCT.md` o `DESIGN.md`, sus reglas mandan sobre esta skill. El gusto de `reference/gusto.md` es el punto de partida cuando el proyecto no ha decidido nada.

## Honestidad

No digas que pasó lo que no ejecutaste. Si algo se saltó o falló, dilo con la salida.
