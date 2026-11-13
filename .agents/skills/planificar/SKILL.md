---
name: planificar
description: Partir un encargo en tareas pequeñas, ordenadas y con criterio de hecho verificable, asignando cada una al rol adecuado. Cárgala al empezar cualquier trabajo de más de un paso o cuando el encargo sea ambiguo.
---

# planificar

## 1. Entender antes de partir

- Reformula el encargo en **una frase** de resultado ("el usuario puede…", "la consulta X deja de fallar").
- Separa lo que pide de lo que supones. Pregunta solo si la duda cambia el trabajo; si hay un valor por defecto razonable, úsalo y dilo.
- Comprueba el estado real (comandos del perfil del proyecto) en vez de suponerlo.

## 2. Partir

Cada tarea debe ser:

- **Pequeña:** cabe en una entrega revisable (idealmente un commit).
- **Independiente** cuando se pueda, para hacerla en paralelo.
- **Con dueño:** un rol (`steve`, `rahul`, `aniol`, `dani`, `jose`, `luisito`).
- **Con criterio de hecho verificable:** un comando que pasa, un test, una comprobación en el navegador. "Que funcione" no es criterio.

Orden por dependencia: contratos y esquema → servicios → interfaz → verificación → documentación.

## 3. Plantilla

```markdown
**Objetivo:** <una frase>
**Supuestos:** …
| # | Tarea | Rol | Depende de | Hecho cuando |
|---|---|---|---|---|
| 1 | Diseñar tabla X con aislamiento | steve | — | baseline:verificar pasa |
| 2 | Servicio + acción | rahul | 1 | test que ejecuta la consulta pasa |
| 3 | Revisión de aislamiento | aniol | 2 | APTO |
| 4 | Verificación | dani | 3 | tabla en verde |
| 5 | Commits | larry | 4 | commits creados |
**Fuera de alcance:** …
**Riesgos:** …
```

## 4. Durante

- Si una tarea descubre que el plan estaba mal, se replanifica; no se fuerza.
- Lo que aparezca fuera de alcance se anota, no se hace.
- El plan del repositorio (si el proyecto tiene uno) se actualiza en el mismo commit que cierra la tarea.
