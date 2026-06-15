# Seguridad y datos sensibles — Inventario Asserta

Esta aplicación maneja **inventario interno de Asserta** (nombres de equipos,
números de serie, direcciones MAC, software instalado por departamento, notas de
auditoría ENS). Esos datos son sensibles y **no deben acabar en el repositorio**.

---

## 1. Qué NUNCA debe subirse al repositorio

| Tipo | Ejemplos | Estado |
|---|---|---|
| Credenciales | `.env` | Ignorado (`.gitignore`) |
| Datos reales de inventario | `resources/*.csv`, `resources/*.xlsx`, `resources/*.vbs` | Ignorado |
| Datos privados | `resources/private/`, `exports/` | Ignorado |
| Backups / dumps reales | `backups/`, `*.sql.gz`, `*_backup.sql`, `*.dump` | Ignorado |
| Binarios compilados | `build/`, `dist/`, `*.exe`, `*.spec` | Ignorado |
| Logs | `*.log`, `logs/` | Ignorado |
| Bases de datos locales | `*.db`, `*.sqlite`, `*.sqlite3` | Ignorado |

> ✅ **Sí se versiona**: `database/*.sql` y `migrations/*.sql` (son **schema/DDL**,
> no datos), y los ejemplos **anónimos** de `resources/sample/`.

### Datos de ejemplo

Si necesitas datos para probar, usa los de [`resources/sample/`](../resources/sample/)
(totalmente anónimos). **No** sustituyas su contenido por datos reales.

---

## 2. Cómo configurar `.env`

1. Copia la plantilla:
   ```powershell
   copy .env.example .env
   ```
2. Edita `.env` con tu conexión MySQL local. Usa un **usuario dedicado** con
   contraseña (no `root`). Ver [OPERACION.md](OPERACION.md#crear-usuarios-mysql).
3. `.env` está en `.gitignore`: nunca se sube. No lo fuerces con `git add -f`.

La app **se niega a arrancar** con una configuración insegura (usuario `root` o
contraseña vacía). Para desarrollo local desechable puedes saltarte esa
comprobación con `ALLOW_INSECURE_LOCAL_DB=true` (no recomendado).

> El instalador/`build_exe.py` **ya no empaqueta `.env`** dentro del `.exe`. El
> `.env` debe colocarse junto al ejecutable distribuido, nunca dentro del binario.

---

## 3. Cómo tratar los datos de inventario

- Los ficheros reales de inventario viven **fuera del repositorio** (carpeta de
  trabajo del administrador, unidad compartida segura, etc.).
- Para la importación histórica inicial, coloca temporalmente el Excel/CSV reales
  en `resources/` (están ignorados) o pásalos por ruta al script de importación;
  **no** los añadas a git.
- Las exportaciones (`exports/`) y los backups (`backups/`) contienen datos reales:
  trátalos como confidenciales y manténlos fuera del repo.

---

## 4. Ficheros sensibles que YA están versionados (acción pendiente)

Históricamente se commitearon ficheros que ahora están en `.gitignore` pero
**siguen trackeados** (el `.gitignore` no desversiona lo ya añadido). Conviene
sacarlos del control de versiones. Estos comandos **no borran el fichero del
disco**, solo dejan de seguirlo en git:

```powershell
# Datos reales de inventario
git rm --cached "resources/Inventario_Equipos_Asserta.csv"
git rm --cached "resources/Inventario_Software_ENS_Por_Departamento.xlsx"
git rm --cached "resources/Inventario_Software.vbs"

# Binarios compilados
git rm --cached -r build/

# Artefactos de Python compilados (también versionados por error)
git rm --cached -r database/__pycache__ modules/__pycache__ scripts/__pycache__ utils/__pycache__

# Después, commitea el cambio (deja los ficheros en disco, fuera de git)
git commit -m "chore: dejar de versionar datos internos y binarios compilados"
```

> ⚠️ Tras esto, los ficheros **siguen en el historial** de commits anteriores.
> Si contienen datos que deben desaparecer por completo, hay que reescribir el
> historial (sección 5).

---

## 5. Limpiar el historial si ya se subieron datos sensibles

Si datos reales (o un `.env` con credenciales) llegaron a commits anteriores,
hay que **purgar el historial** con [`git-filter-repo`](https://github.com/newren/git-filter-repo):

```bash
# 1) Instalar git-filter-repo (pip install git-filter-repo)
# 2) Trabajar sobre un CLONE FRESCO del repositorio (filter-repo reescribe todo)
git clone <url> inventario-clean && cd inventario-clean

# 3) Eliminar del historial los ficheros sensibles
git filter-repo \
  --path resources/Inventario_Equipos_Asserta.csv \
  --path resources/Inventario_Software_ENS_Por_Departamento.xlsx \
  --path resources/Inventario_Software.vbs \
  --path .env \
  --path-glob 'build/*' \
  --invert-paths
```

> 🔴 **NO ejecutes esto sin coordinación.** Reescribir el historial:
> - cambia todos los hashes de commit,
> - obliga a **todo el equipo** a re-clonar,
> - requiere un `git push --force` coordinado y un aviso previo.
>
> **Nunca hagas `git push --force` / `--force-with-lease` por tu cuenta.** Acuerda
> antes una ventana, avisa a quien tenga clones, y rota cualquier credencial que
> haya estado expuesta (cámbiala en MySQL), porque purgar el historial **no
> invalida** una contraseña ya filtrada.

---

## 6. Checklist rápido antes de publicar / hacer release

- [ ] No hay `.env` ni datos reales en `git status`.
- [ ] `resources/` no contiene datos reales versionados (solo `sample/`).
- [ ] El release **no** incluye `.env`, `exports/`, `logs/` ni recursos internos.
- [ ] Las credenciales expuestas en el pasado se han rotado.
- [ ] Ningún `git push --force` sin coordinación previa.
