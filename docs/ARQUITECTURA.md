# Arquitectura — Inventario Asserta v2.0

## Decisiones de diseño

### UI: PySide6 (descarte de NiceGUI y Streamlit)

| Framework | Razón del descarte |
|---|---|
| **Streamlit** | Modelo de re-render completo en cada interacción; requiere servidor web; no generaba `.exe` nativo limpio |
| **NiceGUI** | Mismas limitaciones de servidor; la UI web añade latencia; el inventario es local, no necesita navegador |
| **PySide6** | Nativo Windows; `.exe` limpio con PyInstaller; `QTableView` maneja miles de filas sin lag; theming QSS completo |

### ORM: SQLAlchemy + PyMySQL

El driver `mysql-connector-python` fue considerado pero **la lógica de negocio completa ya estaba implementada**
sobre `sqlalchemy.text()`. Migrar implicaría reescribir 1500+ líneas funcionales sin ganancia.
El script `scripts/init_database.py` usa `pymysql` directamente para la inicialización del schema
(antes de que SQLAlchemy esté disponible).

### Tablas: QTableView + QAbstractTableModel

**Nunca `QTableWidget`**. La diferencia es crítica a escala:

| Widget | 200 filas | 5000 filas |
|---|---|---|
| `QTableWidget` | ~80ms render | >2s, lag visible |
| `QTableView` + modelo | ~2ms render | <20ms |

`QTableWidget` almacena un `QTableWidgetItem` por celda. `QTableView` solo renderiza las celdas visibles.

### Operaciones asíncronas: QThread

Toda operación de BD se ejecuta en un `QThread` a través del patrón `Worker`:

```
UI (main thread)                Worker (QThread)
       │                               │
       ├─ run_in_thread(fn) ──────────►│
       │                          fn() + DB ops
       │◄── finished.emit(result) ─────┤
       ├─ _on_data_loaded(result)       │
       │                               │
```

El helper `run_in_thread()` en `ui/components/worker.py` encapsula este patrón en una sola llamada.

### Versiones como VARCHAR

**Regla crítica**: los campos de versión son siempre `str` en Python y `VARCHAR` en BD.

Excel convierte `"1.0"` → número `1` al abrir. Si la BD almacenara `INT` o `FLOAT`,
los re-imports desde Excel corromperían las versiones existentes.

`utils/normalizer.py::clean_version()` convierte cualquier valor entrante (incluidos `float`/`int` de pandas)
a `str` antes de persistir.

## Estructura de carpetas

```
inventario-asserta/
├── main.py                  # Único entry point
├── config.py                # Constantes globales + resolución de rutas (PyInstaller-safe)
│
├── database/
│   ├── connection.py        # SQLAlchemy engine (pool_size=3)
│   ├── schema.sql           # DDL completo
│   └── seed.sql             # Datos iniciales (departamentos)
│
├── migrations/              # Scripts SQL incrementales (001, 002, ...)
│
├── modules/                 # Lógica de negocio (sin dependencias de UI)
│   ├── software.py          # CRUD inventario software + métricas
│   ├── equipos.py           # CRUD equipos / hardware
│   ├── importacion.py       # Motor diff/apply para importaciones Panda
│   ├── autorizado.py        # Software autorizado + promoción automática
│   └── exportacion.py       # Exportación Excel
│
├── utils/
│   ├── normalizer.py        # normalize_nombre(), clean_version()
│   └── parser.py            # Parse de CSV/XLSX/paste para importaciones
│
├── ui/                      # Capa de presentación (PySide6 únicamente)
│   ├── app.py               # QApplication setup
│   ├── main_window.py       # QMainWindow: sidebar + QStackedWidget
│   ├── theme.py             # QSS global (dark theme)
│   ├── components/
│   │   ├── base_table_model.py   # QAbstractTableModel base
│   │   ├── sortable_table.py     # QTableView + proxy sort/filter
│   │   ├── sidebar.py            # Navegación lateral
│   │   ├── metric_card.py        # Tarjeta KPI
│   │   └── worker.py             # run_in_thread() + Worker(QObject)
│   └── pages/
│       ├── dashboard.py          # KPIs + estado departamentos
│       ├── software_inventory.py # Inventario software (empresa/dept)
│       ├── hardware_inventory.py # Equipos + import CSV
│       ├── ens_compliance.py     # Auditoría ENS + informe TXT
│       ├── data_quality.py       # Calidad de datos
│       ├── departments.py        # Vista completa por departamento
│       ├── import_panda.py       # Wizard importación Panda
│       └── settings.py           # Config BD + info app
│
├── scripts/
│   ├── init_database.py     # Inicialización BD (pymysql directo)
│   ├── build_exe.py         # Compilación PyInstaller
│   ├── migrate_excel.py     # Migración histórica desde Excel
│   └── importar_equipos_csv.py
│
└── resources/
    ├── icons/               # app.ico (placeholder)
    ├── Inventario_Equipos_Asserta.csv
    ├── Inventario_Software_ENS_Por_Departamento.xlsx
    └── Inventario_Software.vbs
```

## Flujo de importación Panda

```
Usuario pega texto / sube CSV
          │
   utils/parser.py::parse_paste() / parse_file()
          │  lista de dicts {nombre, fabricante, version (str), ...}
          │
   modules/importacion.py::calcular_diff()
          │  diff = {nuevos, actualizados, cambios_version, eliminados}
          │
   UI muestra previsualización
          │
   modules/importacion.py::aplicar_diff()
          │  INSERT/UPDATE en software + software_equipo
          │  INSERT en importaciones (trazabilidad)
          │  modules/autorizado.py::autorizar_exclusivos_automaticamente()
          │
   Reactivaciones pendientes si software inactivo reaparece
```
