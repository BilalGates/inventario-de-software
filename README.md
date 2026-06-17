# Inventario Asserta

Herramienta interna de IT para gestionar el inventario de **software y hardware** de los equipos de Asserta.
Permite importar software desde Panda Adaptive Defense, revisar cambios, controlar software autorizado
y auditar el cumplimiento ENS (CCN-STIC Guía 105).

## Requisitos

- Python 3.11+
- MySQL 8.0+
- Windows 10/11 (para el `.exe` compilado)

## Instalación para desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copiar y editar las credenciales de BD:

```powershell
copy .env.example .env
# Editar .env con los datos de conexión MySQL
```

Inicializar la base de datos:

```powershell
python main.py --init-db
```

Importar datos históricos desde el Excel (primera vez):

```powershell
python main.py --init-db --import-historical
```

Arrancar la aplicación:

```powershell
python main.py
```

## Compilar a .exe

```powershell
python scripts/build_exe.py
```

El ejecutable se genera en `dist/InventarioAsserta/InventarioAsserta.exe`.

## Módulos

| Módulo | Descripción |
|---|---|
| **Inicio** | Dashboard con KPIs, estado por departamento y alertas |
| **Inventario Software** | Tabla completa con filtros por departamento y ENS, edición inline |
| **Inventario Hardware** | Gestión de equipos con importación desde CSV |
| **Auditoría ENS** | Cumplimiento CCN-STIC Guía 105 con informe exportable |
| **Calidad de Datos** | Versiones sospechosas, fabricantes vacíos, software huérfano |
| **Departamentos** | Vista completa por departamento: inventario, importar, exportar, dispositivos, reactivaciones |
| **Importar Panda** | Wizard de importación desde Panda Adaptive Defense (paste o archivo) |
| **Configuración** | Credenciales BD, prueba de conexión, información de la app |

## Departamentos de Asserta

`Gerencia` · `IT` · `Silicon` · `Data Science/Analytics` · `Administración` · `Servidores`

## Configuración (.env)

Copia `.env.example` a `.env` y usa un **usuario de BD dedicado** (no `root`):

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=inventario_software
DB_USER=inventario_app
DB_PASSWORD=tu_contraseña
# Solo desarrollo local desechable; deja false en cualquier entorno real:
ALLOW_INSECURE_LOCAL_DB=false
```

> ⚠️ La app **no arranca** con `root` o contraseña vacía salvo que
> `ALLOW_INSECURE_LOCAL_DB=true`. Cómo crear los usuarios `inventario_app`
> (datos) e `inventario_migrator` (DDL): ver [docs/OPERACION.md](docs/OPERACION.md).

## Primera puesta en marcha

1. Crear la BD con `python main.py --init-db`
2. Importar histórico: `python main.py --init-db --import-historical`
   - Lee `resources/Inventario_Software_ENS_Por_Departamento.xlsx`
   - Lee `resources/Inventario_Equipos_Asserta.csv`
3. Abrir la app: `python main.py`

## Seguridad de datos

Esta herramienta maneja **inventario interno** (equipos, series, MAC, software por
departamento). Reglas básicas:

- **No subas datos reales al repo.** `.env`, `resources/*.csv|*.xlsx|*.vbs`,
  `exports/`, `logs/`, `backups/` y los binarios están en `.gitignore`. Para
  pruebas usa los ejemplos anónimos de [`resources/sample/`](resources/sample/).
- **Usa un usuario MySQL dedicado** (no `root`); la app bloquea conexiones inseguras.
- **Nunca `git push --force`** sin coordinación.

Detalle completo (qué no subir, configurar `.env`, limpiar el historial con
`git-filter-repo`): [docs/SEGURIDAD.md](docs/SEGURIDAD.md).

## Documentación

| Tema | Documento |
|---|---|
| Arquitectura | [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) |
| Modelo de datos | [docs/MODELO_DATOS.md](docs/MODELO_DATOS.md) |
| Operación (instalar, migrar, build, backups) | [docs/OPERACION.md](docs/OPERACION.md) |
| Seguridad | [docs/SEGURIDAD.md](docs/SEGURIDAD.md) |
| Decisiones (ADR) | [docs/adr/](docs/adr/) |

## Notas operativas

- **Versiones siempre como texto** — nunca `int`/`float`. El campo `version_referencia` es `VARCHAR(200)`.
- **Sin borrados físicos** — las bajas se guardan como `activo = FALSE`.
- **QTableView** en todas las tablas — nunca `QTableWidget`. Soporte fluido hasta 5000+ filas.
- **QThread** para toda operación de BD — la UI nunca se congela.
