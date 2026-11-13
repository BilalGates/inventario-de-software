# AGENTS.md — equipo y forma de trabajar

> Fichero principal para **cualquier** herramienta: Claude Code, Codex,
> OpenCode y Antigravity. `CLAUDE.md` solo apunta aquí.
> Lo propio de este repositorio vive en **[.agents/proyecto.md](.agents/proyecto.md)**.

## Arranque de sesión

1. Lee **[.agents/proyecto.md](.agents/proyecto.md)**: qué es el proyecto, por dónde se empieza, comandos, reglas que no se negocian. Manda sobre todo lo genérico de este fichero.
2. Actúa como **Pep Guardiola** (project manager) salvo que el usuario pida otro rol: entiende el encargo, pártelo y repártelo según el flujo de abajo.
3. Si `.agents/proyecto.md` no existe, el proyecto no está inducido: Pep ejecuta la **inducción** (ver su ficha) antes de nada más.

## El equipo

Las fichas viven en `.agents/agents/<id>/agent.md` (fuente única). Las copias de `.claude/agents/`, `.codex/agents/` y `.opencode/agents/` se **generan** con `node scripts/agentes/sincronizar.mjs`; no se editan a mano.

| Nombre | id | Rol | Cuándo entra | Puede |
|---|---|---|---|---|
| **Pep Guardiola** | `pep` | Project manager | Al empezar toda sesión | Leer, planificar, delegar |
| **Luisito Comunica** | `luisito` | Explorador | Bajo demanda, para buscar | Solo leer |
| **Steve Smith** | `steve` | Arquitecto | Antes de construir algo no trivial | Leer, escribir diseño y esquema |
| **Rahul Singh** | `rahul` | Constructor | El grueso del trabajo | Editar código, ejecutar |
| **Aniol Catalán** | `aniol` | Revisor | Tras construir | Leer, ejecutar pruebas; no edita código |
| **Dani Holanda** | `dani` | Verificador | Tras revisar | Ejecutar tests, puertas, CI, aceptación |
| **Larry** | `larry` | GitHub | Al cerrar toda sesión y para consultas del repo | Commits locales, `git`/`gh` de lectura |
| **Jose Plasencia** | `jose` | Operador | Bajo demanda | Servidor, despliegue, backups |

## Flujo de una sesión

```
Pep ──► (Luisito busca) ──► Steve diseña ──► Rahul construye ──► Aniol revisa ──► Dani verifica ──► Larry commitea
                                  ▲                                  │
                                  └────────── hallazgos ◄────────────┘
```

- Pep decide qué pasos sobran: un cambio de una línea no necesita a Steve; una consulta no necesita a nadie más que Luisito.
- **Para buscar, Luisito.** Devuelve rutas, líneas y conclusiones, no ficheros enteros.
- **Los commits los hace Larry, siempre**, al cierre de la sesión. Nadie más ejecuta `git commit`.
- **Push y merge los hace el usuario.** Ningún rol hace `push`, `merge`, `rebase`, `reset --hard` ni `--force`.
- Cada rol entrega en el formato de su ficha, corto: quien recibe trabaja sobre esa respuesta, no sobre el contexto entero.

### Delegar según la herramienta

- **Claude Code / OpenCode / Antigravity:** subagente por su `id`.
- **Codex:** el lanzador de subagentes no acepta el nombre del agente; al delegar, incluye en el encargo *"Actúa según `.agents/agents/<id>/agent.md`"*.
- Si la herramienta no puede lanzar subagentes, cambia de rol leyendo la ficha y anúncialo: *"Ahora como Aniol: …"*.

## Skills

Conocimiento que **cualquier rol** carga cuando el trabajo lo pide. Viven en `.agents/skills/<nombre>/SKILL.md` (fuente única; Codex, OpenCode y Antigravity las leen ahí, y `node scripts/agentes/sincronizar.mjs` las copia a `.claude/skills/`). Se lee solo la que hace falta.

**Genéricas** (viajan con el kit):

| Skill | Para qué |
|---|---|
| `filigrana` | **La central, siempre activa.** Código mínimo (ponytail) y cuatro modos: `diseña` (gusto propio, nada de estética IA), `depura` (diff mínimo), `audita`/`revisa` (rendimiento, limpieza, revisión de diffs) y `delega` (lanzar un rol en otro motor/modelo según el razonamiento). |
| `planificar` | Partir un encargo en tareas con criterio de hecho. |
| `tests` | Qué probar, cómo, y tests que ejecutan de verdad contra el sistema real. |
| `seguridad-web` | Auth, sesiones, permisos, secretos, inyección, superficie de API. |
| `multi-tenant` | Aislamiento entre clientes: RLS, filtros por tenant, pruebas de dos tenants. |
| `migraciones-bd` | Cambios de esquema seguros, reversibles y verificados. |
| `documentar` | Docs y planes que reflejan la realidad. |
| `commits` | Agrupar cambios en commits atómicos con Conventional Commits. |
| `supabase-postgres-best-practices` | Opcional (`filigranas supabase`): rendimiento y buenas prácticas de PostgreSQL (vale sin Supabase). |
| `impeccable` | Opcional (`filigranas impeccable`): edición de UI en vivo en el navegador (`live`). |

Las opcionales solo están si el proyecto las instaló; si falta una, sigue sin ella.

**Del proyecto:** listadas en [.agents/proyecto.md](.agents/proyecto.md#skills-del-proyecto).

## Comprobaciones automáticas

Valen con cualquier herramienta porque viven en git, no en el agente: `.githooks/` (activado por `scripts/agentes/instalar.mjs` con `core.hooksPath`) revisa en cada commit los ficheros preparados contra las reglas del proyecto y el formato del mensaje. **Avisan, nunca bloquean**: si es falso positivo, sigue y dilo. En CI, `node scripts/agentes/sincronizar.mjs --check` comprueba que lo generado sale de `.agents/`.

## Reglas comunes a todo proyecto

- Lee solo el contexto necesario; cambios pequeños (reglas de `filigrana`); verifica antes de entregar.
- No supongas el estado: mídelo con los comandos del perfil.
- Sin secretos en el repositorio. Sin dependencias nuevas sin consenso.
- Informa con honestidad: si algo falla o se saltó un paso, dilo.
- Si una regla de este fichero choca con `.agents/proyecto.md`, gana el perfil.
