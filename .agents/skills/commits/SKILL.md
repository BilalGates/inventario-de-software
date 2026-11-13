---
name: commits
description: Agrupar cambios en commits atómicos por unidad funcional y redactar mensajes Conventional Commits. La usa Larry; cárgala también para revisar si un historial es revisable.
---

# commits

## Agrupar por unidad funcional

- Implementación + tipos + tests + docs inseparables → **un** commit.
- Corrección independiente → su propio `fix`.
- Refactor sin cambio de comportamiento → separado de la funcionalidad.
- Docs generales → `docs`; herramientas, configuración, dependencias → `chore`.
- Tamaño no manda: treinta ficheros coherentes = un commit; tres arreglos sin relación = tres.
- Orden por dependencia: esquema/contratos → servicios → interfaz → tests → docs.

## Heurística rápida por ruta

| Ruta | Tipo probable |
|---|---|
| `src/**` nuevo comportamiento | `feat` |
| `src/**` corrige | `fix` |
| solo mueve/extrae | `refactor` |
| `**/__tests__/**`, `*.test.*`, `e2e/**` solos | `test` |
| `docs/**`, `*.md` solos | `docs` |
| `scripts/**`, config, `.github/**`, `.agents/**`, lockfile | `chore` |

El alcance sale de la carpeta de dominio (`src/modules/<x>` → `(x)`).

## Mensaje

`<tipo>(<alcance>): <descripción en imperativo, minúscula, sin punto>`

- Describe el resultado, no los ficheros. ≤ 72 caracteres.
- Cuerpo solo para explicar una decisión o una incompatibilidad (`BREAKING CHANGE:`).
- Prohibido: `wip`, `cambios varios`, `actualiza archivos`, `fix stuff`.

## Seguridad

- Rutas concretas en `git add`; nunca `-A`, `.` ni globs amplios.
- Revisar `git diff --cached --stat` por commit: sin secretos, sin artefactos generados, sin restos de otro grupo.
- Nunca `--no-verify`, `amend`, `rebase`, `push`, `reset --hard`.
