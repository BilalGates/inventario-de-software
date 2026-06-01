# Inventario Software ENS — Especificación para Claude Code

## Contexto del proyecto

Aplicación local de escritorio para gestionar el inventario mensual de software instalado en todos los ordenadores de la empresa, conforme a los requisitos del ENS (Esquema Nacional de Seguridad, Guía CCN-STIC 105).

Actualmente el proceso es 100% manual: el administrador consulta Panda Adaptive Defense equipo por equipo, copia los listados y los cruza a mano en un Excel por departamento. Este proyecto automatiza ese cruce.

### Quién la usa

Un solo usuario administrador, en local, sin autenticación. La app corre en `localhost` y se abre en el navegador.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| UI | **Streamlit** (corre en localhost, abre en navegador) |
| Base de datos | **MySQL 8.0+** (local) |
| Conector BD | **PyMySQL** + **SQLAlchemy 2.x** |
| Data | **pandas 2.x** |
| Excel I/O | **openpyxl** |
| Python | **3.11+** |

**No usar**: Flask, FastAPI, PyQt, Tkinter, SQLite, ni ningún otro stack. Streamlit + MySQL es la decisión tomada.

---

## Estructura de directorios

```
inventario-software/
├── app.py                        # Punto de entrada Streamlit
├── config.py                     # Configuración DB (desde variables de entorno)
├── requirements.txt
├── README.md                     # Instrucciones de instalación y uso
│
├── database/
│   ├── connection.py             # Pool de conexión SQLAlchemy
│   ├── schema.sql                # DDL completo (CREATE TABLE)
│   └── seed.sql                  # Datos iniciales (departamentos)
│
├── modules/
│   ├── equipos.py                # CRUD de ordenadores
│   ├── software.py               # CRUD del catálogo de software por departamento
│   ├── importacion.py            # Motor de importación y cruce de listas
│   ├── exportacion.py            # Generación de Excel de salida
│   └── autorizado.py             # Software autorizado (apartado separado)
│
├── utils/
│   ├── normalizer.py             # Normalización de nombres y versiones
│   └── parser.py                 # Parseo de texto pegado y ficheros CSV/Excel
│
├── pages/
│   ├── 1_Departamentos.py        # Vista principal: tarjetas de departamentos
│   ├── 2_Equipos.py              # Gestión de equipos por departamento
│   ├── 3_Importar.py             # Importar listado de un equipo
│   ├── 4_Inventario.py           # Ver y editar inventario del departamento
│   ├── 5_Exportar.py             # Exportar Excel
│   └── 6_Autorizado.py           # Software autorizado
│
└── migration/
    └── migrate_excel.py          # Script one-time: migra el Excel actual a MySQL
```

---

## Base de datos — Esquema completo

### Reglas generales de diseño
- **Las versiones SIEMPRE son VARCHAR**, nunca INT ni DECIMAL. Panda exporta versiones como `26.001.21563`, `7.4.2.1737`, `ad 9.0.10` — si se tratan como números los puntos se pierden.
- Todos los nombres de equipo se guardan en dos formas: `nombre` (original, tal como viene) y `nombre_norm` (uppercase, sin espacios extra) para comparación sin distinción de mayúsculas.
- Nombres de software: ídem — `nombre` original y `nombre_norm` para matching.
- Los campos booleanos del ENS (`expuesto_internet`, `soporte_activo`, `permitido`, `en_guia_105`) admiten NULL (= "pendiente de revisar").

### DDL

```sql
-- ============================================================
-- DEPARTAMENTOS (lista fija, no modificable por el usuario)
-- ============================================================
CREATE TABLE departamentos (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    codigo          VARCHAR(30) UNIQUE NOT NULL,   -- 'gerencia', 'it', 'silicon', 'data_science', 'administracion', 'servidores'
    nombre          VARCHAR(100) NOT NULL,
    prefijo_id      VARCHAR(5) NOT NULL             -- 'GER', 'IT', 'SIL', 'ANA', 'ADM', 'SRV'
);

-- ============================================================
-- EQUIPOS (ordenadores, gestionables: alta/baja)
-- ============================================================
CREATE TABLE equipos (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    departamento_id     INT NOT NULL,
    nombre              VARCHAR(150) NOT NULL,       -- nombre original: 'Assertap17', 'ASS-SILC-04'
    nombre_norm         VARCHAR(150) NOT NULL,       -- UPPER(TRIM(nombre)): 'ASSERTAP17'
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta          DATE NOT NULL DEFAULT (CURRENT_DATE),
    fecha_baja          DATE NULL,
    notas               TEXT NULL,
    CONSTRAINT fk_equipo_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    CONSTRAINT uq_equipo_dept UNIQUE (departamento_id, nombre_norm)
);

-- ============================================================
-- SOFTWARE — catálogo consolidado por departamento
-- ============================================================
CREATE TABLE software (
    id                          INT PRIMARY KEY AUTO_INCREMENT,
    departamento_id             INT NOT NULL,
    codigo                      VARCHAR(20) NULL,        -- 'GER-001', 'IT-042' (se genera automáticamente)
    nombre                      VARCHAR(500) NOT NULL,
    nombre_norm                 VARCHAR(500) NOT NULL,   -- para matching
    fabricante                  VARCHAR(300) NULL,
    tipo                        ENUM('SO', 'Aplicación', 'SaaS', 'BD', 'Seguridad') NULL,
    version_referencia          VARCHAR(200) NULL,       -- siempre VARCHAR
    clasificacion_informacion   VARCHAR(80) NULL DEFAULT 'Media',
    expuesto_internet           BOOLEAN NULL,
    soporte_activo              BOOLEAN NULL,
    permitido                   BOOLEAN NULL,
    en_guia_105                 BOOLEAN NULL,
    observaciones_elena         TEXT NULL,
    observaciones_toni          TEXT NULL,
    fecha_ultima_revision       DATE NULL,
    activo                      BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_alta                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sw_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    CONSTRAINT uq_sw_dept UNIQUE (departamento_id, nombre_norm)
);

-- ============================================================
-- SOFTWARE_EQUIPO — tabla puente (sustituye columna "Dispositivos")
-- ============================================================
CREATE TABLE software_equipo (
    id                      INT PRIMARY KEY AUTO_INCREMENT,
    software_id             INT NOT NULL,
    equipo_id               INT NOT NULL,
    version_detectada       VARCHAR(200) NULL,  -- la versión que tiene ESE equipo (VARCHAR siempre)
    fecha_instalacion       DATE NULL,
    tamano                  VARCHAR(50) NULL,   -- texto tal cual: '1,2 GB', '20,9 MB', '-'
    fecha_ultima_deteccion  DATE NOT NULL,
    presente                BOOLEAN NOT NULL DEFAULT TRUE,  -- FALSE = desinstalado en última revisión
    CONSTRAINT fk_swe_sw FOREIGN KEY (software_id) REFERENCES software(id),
    CONSTRAINT fk_swe_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id),
    CONSTRAINT uq_sw_equipo UNIQUE (software_id, equipo_id)
);

-- ============================================================
-- SOFTWARE_AUTORIZADO — programas de 1-2 máquinas, apartado propio
-- ============================================================
CREATE TABLE software_autorizado (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    departamento_id     INT NULL,
    nombre              VARCHAR(500) NOT NULL,
    fabricante          VARCHAR(300) NULL,
    tipo                VARCHAR(100) NULL,
    version             VARCHAR(200) NULL,   -- VARCHAR siempre
    equipo_id           INT NULL,            -- si el equipo existe en la BD
    usuario_texto       VARCHAR(150) NULL,   -- si no existe en BD (texto libre)
    observaciones       TEXT NULL,
    fecha_alta          DATE NOT NULL DEFAULT (CURRENT_DATE),
    CONSTRAINT fk_sa_dept FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
    CONSTRAINT fk_sa_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id)
);

-- ============================================================
-- IMPORTACIONES — log de auditoría ENS
-- ============================================================
CREATE TABLE importaciones (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    equipo_id           INT NOT NULL,
    fecha_importacion   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metodo              ENUM('paste', 'file') NOT NULL,
    n_total             INT NULL,
    n_nuevos            INT NOT NULL DEFAULT 0,
    n_actualizados      INT NOT NULL DEFAULT 0,
    n_eliminados        INT NOT NULL DEFAULT 0,
    n_cambios_version   INT NOT NULL DEFAULT 0,
    confirmada          BOOLEAN NOT NULL DEFAULT FALSE,
    notas               TEXT NULL,
    CONSTRAINT fk_imp_eq FOREIGN KEY (equipo_id) REFERENCES equipos(id)
);
```

### Datos iniciales (seed.sql)

```sql
INSERT INTO departamentos (codigo, nombre, prefijo_id) VALUES
('gerencia',        'Gerencia',                  'GER'),
('it',              'IT',                        'IT'),
('silicon',         'Silicon',                   'SIL'),
('data_science',    'Data Science / Analytics',  'ANA'),
('administracion',  'Administración',             'ADM'),
('servidores',      'Servidores',                 'SRV');
```

---

## Módulo utils/normalizer.py

### Función `normalize_nombre(nombre: str) -> str`
Normaliza nombres de software y equipos para comparación. Pasos exactos:
1. `unicodedata.normalize('NFC', nombre)` — unifica variantes unicode
2. `.strip()` — elimina espacios al inicio y final
3. `.upper()` — todo a mayúsculas
4. `re.sub(r'\s+', ' ', ...)` — colapsa múltiples espacios en uno

No eliminar paréntesis, guiones ni otros caracteres especiales porque forman parte del nombre (`Adobe Acrobat (64-bit)`, `7-Zip 23.01 (x64 edition)`).

### Función `clean_version(raw) -> str | None`
El problema: Excel convierte `26.001.21563` en el entero `26001211563` al leer la celda como número. Hay que detectar y limpiar.

```python
def clean_version(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        # Es un número: puede ser versión corrompida o serial de fecha
        # Si es un int grande típico de versiones corruptas, lo dejamos como str
        return str(int(raw))
    val = str(raw).strip()
    return val if val not in ('', '-', '–', 'nan') else None
```

> **Nota**: Las versiones corruptas como `2500121288` se guardan tal cual como string. Cuando el usuario revise el catálogo importado desde el Excel antiguo, las verá y podrá corregirlas manualmente. No intentar reconstruir los puntos automáticamente (demasiado ambiguo).

### Función `normalize_equipo_nombre(nombre: str) -> str`
Igual que `normalize_nombre`. El UNIQUE en BD se hace sobre `nombre_norm = UPPER(TRIM(nombre))`.

---

## Módulo utils/parser.py

### Formato de Panda Adaptive Defense (input del usuario)

Cuando el administrador copia de Panda, el formato es texto separado por tabuladores con estas columnas **en este orden**:

```
Nombre | Editor | Fecha de instalación | Tamaño | Versión
```

Ejemplo real pegado:
```
Adobe Acrobat Reader - Español	Adobe Systems Incorporated	18/05/2026	1,2 GB	26.001.21563
AnyDesk	AnyDesk Software GmbH	10/03/2026	2 MB	ad 9.0.10
Anaconda3 2022.05 (Python 3.9.12 64-bit)	Anaconda, Inc.	30/01/2025	-	2022.05
```

Características a manejar:
- Separador: tabulador `\t`
- La primera fila **puede** ser cabecera (`Nombre`, `Editor`, etc.) o puede no estar. Detectar si la primera fila es cabecera comprobando si contiene la palabra "Nombre".
- Fecha: formato `dd/mm/yyyy`. Parsear con `datetime.strptime(val, '%d/%m/%Y')`. Si falla, dejar NULL.
- Tamaño: texto libre (`1,2 GB`, `20,9 MB`, `829,9 MB`, `-`, `–`). Guardar como string tal cual. Si es `-` o `–`, guardar NULL.
- Versión: guardar **siempre como string**, no convertir a número.
- Líneas vacías: ignorar.

### Función `parse_paste(text: str) -> list[dict]`

```python
def parse_paste(text: str) -> list[dict]:
    """
    Parsea texto pegado desde Panda Adaptive Defense.
    Retorna lista de dicts con claves: nombre, fabricante, fecha_instalacion, tamano, version
    """
```

### Función `parse_file(file_bytes: bytes, filename: str) -> list[dict]`

Acepta `.csv` y `.xlsx`. Misma estructura de columnas que el pegado. Para CSV probar separadores `,` y `;` y `\t`. Para Excel leer la primera hoja.

Auto-detectar si la primera fila es cabecera: si todas las celdas de la primera fila son strings sin fechas ni tamaños, es cabecera.

Devuelve la misma estructura de dicts que `parse_paste`.

---

## Motor de importación (modules/importacion.py)

### Función principal `calcular_diff(equipo_id, programas: list[dict], db) -> dict`

Esta función **no escribe en BD**, solo calcula qué cambiaría. El resultado se muestra al usuario para que confirme antes de aplicar.

```
Resultado = {
    'nuevos':           [lista de programas no encontrados en el catálogo del dept],
    'actualizados':     [ya existen en catálogo + ya enlazados a este equipo, misma versión],
    'cambios_version':  [ya existen en catálogo + ya enlazados, pero versión distinta],
    'eliminados':       [estaban enlazados a este equipo y NO aparecen en la nueva lista],
    'nuevos_en_catalogo': [no existían en el catálogo del dept (subset de 'nuevos')]
}
```

Algoritmo exacto:
1. Obtener `departamento_id` del equipo.
2. Cargar TODO el catálogo del departamento como dict `{nombre_norm: software_row}`.
3. Cargar TODOS los `software_equipo` activos de este equipo como set de `software_id`.
4. Para cada programa del input:
   - `nombre_norm = normalize_nombre(programa['nombre'])`
   - Si `nombre_norm` está en el catálogo del dept → `software_id` conocido.
     - Si ya tiene enlace a este equipo → comparar versión → `actualizados` o `cambios_version`.
     - Si NO tiene enlace → `nuevos` (van a crear un enlace a catálogo existente).
   - Si NO está en catálogo → `nuevos` + `nuevos_en_catalogo` (se creará fila en `software` Y enlace).
5. Los `software_id` que estaban enlazados a este equipo y NO han aparecido en el input → `eliminados`.

### Función `aplicar_diff(equipo_id, programas, diff, db, metodo) -> int`

Aplica el diff calculado. Escribe en BD. Retorna el `id` de la importación registrada.

Pasos:
1. Para `nuevos_en_catalogo`: INSERT en `software` con `nombre`, `fabricante` (del input), resto de campos ENS a NULL. Generar `codigo` automáticamente (prefijo + siguiente número: `ANA-138`).
2. Para todos los `nuevos`: INSERT en `software_equipo` con `presente=TRUE`, `fecha_ultima_deteccion=hoy`.
3. Para `actualizados`: UPDATE `software_equipo` SET `fecha_ultima_deteccion=hoy` (sin cambiar versión).
4. Para `cambios_version`: UPDATE `software_equipo` SET `version_detectada=nueva`, `fecha_ultima_deteccion=hoy`. También UPDATE `software.version_referencia` si la nueva versión es más reciente (comparación de string, best effort).
5. Para `eliminados`: UPDATE `software_equipo` SET `presente=FALSE` (NO borrar — preservar histórico).
6. INSERT en `importaciones` con todos los contadores y `confirmada=TRUE`.

---

## Páginas de la aplicación (Streamlit)

### `app.py` — Página principal
Muestra 6 tarjetas, una por departamento, con el nombre y el número de equipos activos y el número de software en catálogo. Al hacer clic en una tarjeta se guarda el `departamento_id` en `st.session_state` y se redirige a la página de Inventario.

### `pages/1_Departamentos.py`
Vista idéntica a `app.py`. Es la página de inicio real.

### `pages/2_Equipos.py`
Requiere `st.session_state['departamento_id']` seleccionado.

Muestra:
- Nombre del departamento como título.
- Tabla con los equipos del departamento: Nombre, Activo (sí/no), Fecha alta, Fecha baja, Notas.
- Botón **"+ Añadir equipo"**: abre formulario inline con campos Nombre y Notas. Al guardar, inserta en `equipos` normalizando el nombre.
- Por cada equipo: botón **"Dar de baja"** (pone `activo=FALSE`, `fecha_baja=hoy`). NO borrar registros.
- Advertencia si se intenta añadir un equipo cuyo `nombre_norm` ya existe (activo o no).

### `pages/3_Importar.py`
Requiere `departamento_id` en session_state.

Flujo en 3 pasos dentro de la misma página (usar `st.session_state` para el paso actual):

**Paso 1 — Seleccionar equipo**
- Selectbox con los equipos activos del departamento.
- Opción "+ Crear equipo nuevo" en el mismo selectbox → muestra campo de texto para el nombre.
- Botón Siguiente.

**Paso 2 — Cargar listado**
- Dos tabs: `📋 Pegar texto` y `📁 Subir fichero`.
  - Tab Pegar: `st.text_area` grande con placeholder explicando el formato.
  - Tab Subir: `st.file_uploader` que acepta `.csv` y `.xlsx`.
- Botón **"Analizar"**: parsea el input y llama a `calcular_diff`. Si hay errores de parseo, mostrarlos aquí.

**Paso 3 — Revisar y confirmar**

Mostrar el resultado del diff en 4 secciones expandibles (`st.expander`):

- 🟢 **Nuevos en catálogo** (N programas): tabla con Nombre, Fabricante, Versión. Aviso: "Se añadirán al catálogo de [Departamento] y se marcarán como instalados en [Equipo]."
- 🔵 **Ya en catálogo, nuevos en equipo** (N programas): tabla. "Se registrará que [Equipo] tiene este software."
- 🟡 **Cambio de versión** (N programas): tabla con Nombre, Versión anterior → Versión nueva.
- 🔴 **Ya no detectados** (N programas): tabla. "Se marcarán como no presentes en [Equipo]."

Si el diff está vacío (sin cambios), mostrar mensaje "No hay cambios respecto a la última importación."

Botón **"Confirmar e importar"** → llama a `aplicar_diff` → muestra resumen y botón para volver.

### `pages/4_Inventario.py`
Vista principal del inventario de un departamento. Tabla con todas las columnas del catálogo + columna dinámica **"Dispositivos"** (generada en consulta: nombres de equipos donde `presente=TRUE`, separados por coma).

Filtros en sidebar:
- Por tipo (SO / Aplicación / SaaS / BD / Seguridad)
- Por equipo (multiselect)
- Por `permitido` (Sí / No / Pendiente)
- Por `en_guia_105` (Sí / No / Pendiente)
- Texto libre (busca en nombre y fabricante)

Cada fila tiene botón **"Editar"** que abre un modal (`st.dialog` si Streamlit ≥ 1.29, sino expander inline) para editar los campos ENS: tipo, clasificación, expuesto, soporte, permitido, en_guia_105, observaciones, fecha revisión. No editar nombre/fabricante/código desde aquí.

### `pages/5_Exportar.py`

Opciones de exportación (checkboxes + selects):
- Departamento(s) a incluir (multiselect, por defecto el activo en session_state)
- Incluir columna "Dispositivos" (sí/no) — formato compatible con Excel actual
- Incluir detalle por equipo en hojas separadas (sí/no) — hoja extra por cada equipo con su versión específica
- Filtro de `permitido`: todos / solo permitidos / solo no-permitidos

Botón **"Generar Excel"** → genera el fichero con `openpyxl` → `st.download_button`.

Formato del Excel generado: una hoja por departamento con el mismo esquema de columnas del Excel original (`ID Software`, `Nombre del Software`, `Fabricante / Proveedor`, `Tipo`, `Versión Actual`, `Clasificación Información Tratada`, `Dispositivos`, `¿Expuesto a Internet?`, `¿Soporte Activo?`, `Fecha Última Revisión`, `Permitido`, `En Guia 105`, `Observaciones Elena`, `Observaciones Toni`).

### `pages/6_Autorizado.py`
Software autorizado — independiente de departamentos o ligado opcionalmente.

Tabla con: Nombre, Fabricante, Tipo, Versión, Equipo/Usuario, Departamento, Observaciones, Fecha alta.

Botón **"+ Añadir"**: formulario con todos los campos. El campo Equipo puede ser un selectbox de equipos existentes O texto libre (para equipos no dados de alta).

Botón **"Eliminar"** por fila (con confirmación — usar `st.session_state` toggle, NO `window.confirm` ni `st.experimental_get_query_params`).

---

## Script de migración (migration/migrate_excel.py)

Script de ejecución única. Lee el fichero `Inventario_Software_ENS_Por_Departamento.xlsx` y migra todos los datos a MySQL.

### Mapeo de hojas → departamentos

| Hoja Excel | `departamento.codigo` |
|---|---|
| Terminales_Gerencia | gerencia |
| Terminales_Administrativos | administracion |
| Terminales_IT | it |
| Terminales_Analytics | data_science |
| Terminales_Silicon | silicon |
| Servidores | servidores |
| SW_Autorizado | → tabla `software_autorizado` |

### Limpieza durante migración

- **Versiones numéricas**: usar `clean_version()` de `utils/normalizer.py`. Guardar como string.
- **Fabricante sucio**: si el valor es `${AppPublisher}` → guardar NULL. Si contiene `\` (ej. `Google\Chrome`) → guardar NULL y loguear warning.
- **Columna Dispositivos**: split por `,`, strip de cada elemento, normalizar nombre, buscar/crear en tabla `equipos`.
- **Fechas**: openpyxl las lee como `datetime` correctamente → convertir a `date`.
- **Campos booleanos ENS** (`Sí`/`No`/vacío): `'Sí'` → TRUE, `'No'` → FALSE, vacío/None → NULL.
- **Clasificación Información Tratada**: `None` o vacío → `'Media'` (valor por defecto).

### Columnas del Excel antiguo → tabla `software`

| Excel | Campo BD |
|---|---|
| ID Software | codigo |
| Nombre del Software | nombre + nombre_norm |
| Fabricante / Proveedor | fabricante |
| Tipo | tipo |
| Versión Actual | version_referencia (VARCHAR) |
| Clasificación Información Tratada | clasificacion_informacion |
| ¿Expuesto a Internet? | expuesto_internet |
| ¿Soporte Activo? | soporte_activo |
| Fecha Última Revisión | fecha_ultima_revision |
| Permitido | permitido |
| En Guia 105 | en_guia_105 |
| Observaciones Elena | observaciones_elena |
| Observaciones Toni | observaciones_toni |

Los dispositivos de la columna "Dispositivos" → tabla `software_equipo` con `presente=TRUE`, `fecha_ultima_deteccion=fecha_ultima_revision` del software, `version_detectada=version_referencia`.

### Hoja SW_Autorizado → tabla `software_autorizado`

| Excel | Campo BD |
|---|---|
| Nombre del Software | nombre |
| Fabricante / Proveedor | fabricante |
| Tipo | tipo |
| Versión Actual | version |
| Usuario | usuario_texto (si no coincide con ningún equipo) ó equipo_id |

### Output del script

Al terminar, imprimir resumen:
```
=== Migración completada ===
Departamentos: 6
Equipos creados: 30
Software (catálogo): 672 entradas
Software_equipo (links): 2.341
Software_autorizado: 1
Warnings: 4 (ver migrate_warnings.log)
```

Guardar un `migrate_warnings.log` con todas las anomalías encontradas (versiones corruptas, fabricantes nulos, etc.).

---

## config.py

```python
import os

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv("DB_NAME", "inventario_software"),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
}
```

El usuario configura las variables de entorno antes de lanzar. En el README explicar cómo hacerlo.

---

## requirements.txt

```
streamlit>=1.35.0
sqlalchemy>=2.0
pymysql>=1.1
pandas>=2.0
openpyxl>=3.1
python-dotenv>=1.0
```

---

## README.md — debe incluir

1. Requisitos previos: Python 3.11+, MySQL 8.0+.
2. Instalación paso a paso:
   ```bash
   pip install -r requirements.txt
   mysql -u root -p < database/schema.sql
   mysql -u root -p inventario_software < database/seed.sql
   ```
3. Configurar variables de entorno (`.env` file o export).
4. Migración inicial (ejecutar una sola vez):
   ```bash
   python migration/migrate_excel.py --file ruta/al/Inventario_Software_ENS.xlsx
   ```
5. Lanzar la app:
   ```bash
   streamlit run app.py
   ```

---

## Restricciones y decisiones de diseño

- **No usar `window.confirm`** ni confirmaciones nativas del navegador. Todas las confirmaciones destructivas se implementan con toggle de `st.session_state` y un segundo clic.
- **No borrar registros** de equipos ni de software_equipo. Siempre soft-delete (`activo=FALSE`, `presente=FALSE`).
- Los departamentos están fijados en seed.sql y **no se modifican desde la UI**.
- El campo `codigo` del software (`GER-001`) se genera automáticamente como `prefijo + número secuencial por departamento`, con zero-padding a 3 dígitos (GER-001, GER-002... GER-099, GER-100).
- Streamlit multipage: usar la convención de carpeta `pages/` con prefijo numérico en el nombre de fichero para controlar el orden en el sidebar.
- La sesión de departamento activo se guarda en `st.session_state['departamento_id']` y `st.session_state['departamento_nombre']`. Inicializar en `app.py` si no existe.

---

## Flujo de trabajo mensual típico (referencia para pruebas)

1. Abrir la app → Seleccionar departamento (ej. Silicon).
2. Ir a Importar → Seleccionar equipo `ASS-SILC-04`.
3. Pegar el listado copiado de Panda Adaptive Defense.
4. Revisar diff: nuevos, eliminados, cambios de versión.
5. Confirmar.
6. Repetir para cada equipo del departamento.
7. Ir a Inventario → filtrar por `permitido=NULL` para revisar los programas nuevos sin clasificar.
8. Rellenar campos ENS (tipo, expuesto, soportado, permitido, guía 105).
9. Exportar Excel del departamento.

---

*Fin de la especificación. Última actualización: mayo 2026.*
