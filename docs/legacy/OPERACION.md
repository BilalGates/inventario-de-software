# Operación — Inventario Asserta

Guía de instalación, inicialización, ejecución, importación, exportación, build
y backups. Para seguridad de datos ver [SEGURIDAD.md](SEGURIDAD.md); para el
modelo de datos ver [MODELO_DATOS.md](MODELO_DATOS.md).

---

## 1. Requisitos

- Python **3.11+** (el entorno de desarrollo usa 3.12).
- MySQL **8.0+**.
- Windows 10/11 (para el `.exe`; el desarrollo funciona en cualquier SO).

---

## 2. Instalación local (desarrollo)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # ejecución
pip install -r requirements-dev.txt      # + tests y lint (opcional)
```

Diagnóstico del entorno en cualquier momento:

```powershell
python scripts/check_environment.py
```

---

## 3. Configurar `.env`

```powershell
copy .env.example .env
# Editar .env con la conexión MySQL (usuario dedicado, NO root)
```

Variables:

| Variable | Descripción |
|---|---|
| `DB_HOST` / `DB_PORT` | Host y puerto MySQL |
| `DB_NAME` | Base de datos (por defecto `inventario_software`) |
| `DB_USER` / `DB_PASSWORD` | Usuario de aplicación y su contraseña |
| `ALLOW_INSECURE_LOCAL_DB` | `true` solo para desarrollo local con root/clave vacía (no recomendado) |

> La app **no arranca** con `root` o contraseña vacía salvo que
> `ALLOW_INSECURE_LOCAL_DB=true`.

### Crear usuarios MySQL

Crea dos usuarios con privilegios mínimos. El **migrador** tiene DDL (crea
tablas/columnas); la **app** solo DML (lee/escribe datos).

```sql
-- Base de datos (si aún no existe)
CREATE DATABASE IF NOT EXISTS inventario_software
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Usuario de APLICACIÓN: solo datos (DML)
CREATE USER IF NOT EXISTS 'inventario_app'@'localhost'
    IDENTIFIED BY 'PON_UNA_CONTRASENA_FUERTE';
GRANT SELECT, INSERT, UPDATE, DELETE
    ON inventario_software.* TO 'inventario_app'@'localhost';

-- Usuario MIGRADOR: cambios de estructura (DDL) + datos
CREATE USER IF NOT EXISTS 'inventario_migrator'@'localhost'
    IDENTIFIED BY 'OTRA_CONTRASENA_FUERTE';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
    ON inventario_software.* TO 'inventario_migrator'@'localhost';

FLUSH PRIVILEGES;
```

- Para **inicializar/migrar** la BD, usa en `.env` el usuario `inventario_migrator`
  (necesita DDL y, si la base aún no existe, privilegio para crearla — usa root
  solo para ese primer `CREATE DATABASE` si lo prefieres).
- Para el **uso diario** de la app, usa `inventario_app`.

---

## 4. Inicializar la base de datos

`schema.sql` (estado base) + `seed.sql` (departamentos) + migraciones pendientes:

```powershell
python main.py --init-db
```

Importación histórica inicial (solo la primera vez, lee `resources/`):

```powershell
python main.py --init-db --import-historical
```

> Diferencia `database/schema.sql` vs `migrations/`: ver
> [MODELO_DATOS.md](MODELO_DATOS.md#schema-base-vs-migraciones).

---

## 5. Migraciones

El runner versionado registra cada migración en la tabla `schema_version` y
aplica solo las pendientes (idempotente, no las aplica dos veces):

```powershell
python scripts/migrate_db.py            # aplica pendientes
python scripts/migrate_db.py --list     # muestra aplicadas / pendientes
```

`python main.py --init-db` también aplica las migraciones pendientes
automáticamente.

---

## 6. Ejecutar la aplicación

```powershell
python main.py
```

---

## 7. Importación de software (Panda Adaptive Defense)

1. App → **Importar Panda**.
2. Pestaña *Pegar texto* (copia el listado de Panda) o *Subir fichero* (`.csv`/`.xlsx`).
3. Pulsa **Analizar**: se muestra el *diff* (nuevos / en catálogo / cambio de
   versión / no detectados) **sin escribir nada todavía**.
4. **Confirmar e importar**: aplica los cambios y registra la importación.

Ejemplo anónimo para probar: pega el contenido de
[`resources/sample/panda_export_SAMPLE.txt`](../resources/sample/panda_export_SAMPLE.txt).

Importación de hardware desde CSV:

```powershell
python scripts/importar_equipos_csv.py --file resources/sample/Inventario_Equipos_SAMPLE.csv
```

---

## 8. Exportaciones

Desde las páginas de inventario/departamentos se generan Excel por departamento.
Los ficheros generados (`exports/`) contienen datos reales: trátalos como
confidenciales y mantenlos fuera del repositorio.

---

## 9. Build a ejecutable (PyInstaller)

```powershell
python scripts/build_exe.py
```

- Genera `dist/InventarioAsserta/`.
- **No** empaqueta `.env` (credenciales) ni la raíz de `resources/` (datos reales);
  solo `resources/icons`, `resources/sample`, `database/` y `migrations/`.
- Coloca el `.env` **junto** al `.exe` distribuido.

Contenido recomendado de un **release**: binario + documentación + `migrations/`.
**Nunca**: `.env`, `exports/`, `logs/`, ni recursos internos con datos reales.

---

## 10. Backups y restauración

Requieren `mysqldump` / `mysql` en el PATH. Usan la conexión de `.env`.

```powershell
# Backup -> backups/<db>_<timestamp>.sql  (carpeta ignorada por git)
python scripts/backup_db.py

# Restaurar (DESTRUCTIVO: sobrescribe la BD; pide confirmación)
python scripts/restore_db.py --file backups/inventario_software_AAAAMMDD_HHMMSS.sql
```

---

## 11. Tests y lint (desarrollo)

```powershell
pip install -r requirements-dev.txt
ruff check .
pytest -q
```
