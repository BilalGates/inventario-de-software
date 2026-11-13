# Auditar: rendimiento y limpieza

Sin medida no hay hallazgo. Cada propuesta lleva su número de antes y la forma de medir el después.

## 1. Detectar el stack y medir

Lee `package.json` / `pyproject.toml` / el perfil del proyecto y ejecuta solo lo que aplique (con los scripts del proyecto si existen):

| Qué | Comando |
|---|---|
| Tipos | `npx tsc --noEmit` |
| Código, exports y dependencias muertas | `npx knip` (o `npx knip --production`) |
| Tamaño de bundle | `next build` (tabla de rutas, First Load JS) · `npx vite-bundle-visualizer` · `du -sh dist` |
| React | `npx -y react-doctor@latest .` |
| Ficheros más grandes | `git ls-files '*.ts' '*.tsx' '*.js' '*.py' \| xargs wc -l \| sort -rn \| head -15` |
| Dependencias | `npm ls --depth=0`, y duplicados con `npm dedupe --dry-run` |
| Web real | `npx lighthouse <url> --only-categories=performance --output=json --quiet` (si hay URL) |
| Base de datos | `EXPLAIN (ANALYZE, BUFFERS)` de las consultas de los listados reales |
| UI genérica | `node DIR/scripts/detectar-slop.mjs src` |
| Python | `ruff check`, `vulture`, `python -X importtime` |

Un comando que no se puede ejecutar (sin red, sin credenciales, demasiado lento) se marca **NO MEDIDO** con el motivo. No se inventa la cifra.

## 2. Qué buscar

**Rendimiento**
- Esperas en serie que son independientes → `Promise.all` (solo si de verdad lo son).
- N+1: consulta dentro de un bucle → una consulta con `JOIN` / `IN`.
- Listados sin paginar, `SELECT *` de tablas anchas, índices que no cubren el filtro y el orden reales.
- Datos traídos en `useEffect` que podrían venir del servidor; estado derivado copiado a `useState`; componentes cliente que podrían ser de servidor.
- Dependencias pesadas en la carga inicial (mapas, editores, charts) → `import()` diferido.
- Imágenes sin dimensiones ni formato moderno; fuentes sin `display: swap` ni subset.
- `transition: all`, animaciones de `width`/`top` en lugar de `transform`.

**Limpieza** (etiquetas ponytail)
- `delete:` código muerto, flags sin uso, features especulativas.
- `stdlib:` lo que la librería estándar ya hace.
- `native:` dependencia o JS para lo que hace la plataforma (`Intl`, `<dialog>`, `<details>`, CSS).
- `yagni:` interfaz con una implementación, factoría con un producto, capa con un único llamador, config que nadie cambia.
- `shrink:` misma lógica en menos líneas.

## 3. Segunda opinión (auditorías completas)

Lanza un segundo auditor de otro modelo en paralelo, en solo lectura, mientras mides:
```bash
node DIR/scripts/delegar.mjs --motor codex --nivel fuerte "Audita este repo buscando problemas de rendimiento y complejidad innecesaria. Devuelve como mucho 15 hallazgos, una línea cada uno: [perf|delete|stdlib|native|yagni|shrink] qué — ruta:línea — propuesta mínima. Sin código."
```
Cruza sus hallazgos con los tuyos: **los que coinciden suben de confianza**, los que solo dice él se verifican antes de incluirlos.

## 4. Informe

Ordenado por impacto/esfuerzo, de mayor a menor:

```
| # | Tipo | Hallazgo | Ruta | Medida antes | Propuesta mínima | Confianza |
|---|------|----------|------|--------------|------------------|-----------|
| 1 | perf | N+1 en listado de pedidos | src/…:42 | 51 consultas/página | 1 consulta con IN | alta (2 modelos) |
```
Cierra con: `net: -N líneas, -M dependencias, -K kB de JS inicial (estimado)` y la lista **NO MEDIDO**.

**No apliques nada** si no lo piden. Al aplicar: un hallazgo cada vez, con la medida de antes y de después y los tests en verde entre uno y otro.

## Revisión (modo `revisa`, sobre un diff)

1. Lee `git diff <base>...HEAD` (o la PR), lo que llama al código cambiado y lo que este llama. Revisa contra **lo que se pretendía**, no contra lo que tú habrías hecho.
2. Por orden: **corrección** (casos límite, nulos, concurrencia, `async` sin `await`, efectos dobles, off-by-one) → **seguridad** (permisos solo en la UI, inyección, secretos, ids del cliente; skills `seguridad-web` y `multi-tenant` si las hay) → **datos** (consultas sin test que las ejecute, transacciones que faltan, migraciones irreversibles) → **reglas del proyecto** → **rendimiento** → **complejidad** (etiquetas ponytail) → estilo, solo si el linter no lo cubre y afecta a la lectura.
   - No pidas reescrituras fuera del alcance; anótalas aparte. No mezcles preferencias con defectos. No repitas lo que ya marca una herramienta.
3. Si el cambio es grande o toca datos, permisos o dinero: segunda opinión con `delegar.mjs --motor codex --nivel fuerte` (o `--agente aniol` si el proyecto tiene el kit).
4. Formato por hallazgo: `[P0–P3] ruta:línea — qué pasa — escenario (entrada/estado concreto → resultado incorrecto) — arreglo mínimo`. Un hallazgo sin prueba se marca como **sospecha**. Cierra con el veredicto **APTO / NO APTO** y `net: -N líneas posibles`.

## Deuda ponytail ("qué dejamos para luego")

Los atajos deliberados llevan `ponytail: <techo>, <cuándo mejorarlo>`. Para listarlos:
```bash
grep -rnE '(#|//|--) ?ponytail:' . --exclude-dir={node_modules,.git,.next,dist,build}
```
Una línea por marca: `ruta:línea — qué se simplificó — techo — disparador`. Las que no nombran disparador se marcan `sin-disparador`: son las que se pudren. Cierra con `N marcas, M sin disparador`.
