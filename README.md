# Inventario de Software Asserta

## Descripción

Aplicación local para gestionar el inventario de software y equipos informáticos de Asserta.
Permite importar software por dispositivo, revisar cambios, controlar software autorizado y consultar el estado de importaciones.
Incluye dashboard, exportación completa a Excel, auditoría de reactivaciones y reportes de calidad de datos.

## Requisitos

- Python 3.x.
- MySQL 8.x.
- Dependencias Python definidas en `requirements.txt`: Streamlit, SQLAlchemy, PyMySQL, pandas, openpyxl y python-dotenv.

## Instalación

Comandos compatibles con PowerShell desde la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Crear la base inicial:

```powershell
mysql -u root -p < database\schema.sql
mysql -u root -p inventario_software < database\seed.sql
```

Lanzar la aplicación:

```powershell
streamlit run app.py
```

## Configuración

La conexión a MySQL se lee desde variables de entorno o desde un archivo `.env` en la raíz del proyecto:

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=inventario_software
DB_USER=root
DB_PASSWORD=
```

## Primera Importación

1. Crear la base y cargar departamentos con `database/schema.sql` y `database/seed.sql`.
2. Si partes del Excel histórico de software, ejecutar:

```powershell
python migration\migrate_excel.py --file Inventario_Software_ENS_Por_Departamento.xlsx
```

3. Ejecutar las migraciones de `migrations/`.
4. Importar el inventario hardware:

```powershell
python scripts\importar_equipos_csv.py
```

5. Abrir Streamlit y usar `Inventario de software` para entrar en cada departamento.

## Qué Hace Cada Página

- `app.py`: dashboard de inicio, alertas y exportación completa `Inventario_Asserta_Completo_{fecha}.xlsx`.
- `pages/1_Inventario_de_software.py`: índice ligero de departamentos.
- `pages/10_Direccion.py` a `pages/15_Servidores.py`: una página dedicada por departamento con inventario, importación, exportación, dispositivos y reactivaciones.
- `pages/2_Estado_Importaciones.py`: estado global de importaciones por equipo.
- `pages/3_Software_Empresa.py`: búsqueda global de software con vista básica o detallada.
- `pages/4_Calidad_Datos.py`: reporte de versiones sospechosas, fabricantes vacíos y software común no autorizado.
- `pages/5_Equipos.py`: vista global de dispositivos activos.
- `pages/6_Software_Autorizado.py`: software autorizado agrupado por programa y detalle editable.

## Ejecutar Migraciones

Las migraciones SQL están en `migrations/` y deben ejecutarse en orden:

```powershell
mysql -u root -p inventario_software < migrations\001_equipos_hardware.sql
mysql -u root -p inventario_software < migrations\002_reactivacion_pendiente.sql
```

Si no tienes el cliente `mysql` en el PATH, puedes aplicar el mismo contenido desde cualquier cliente MySQL conectado a la base `inventario_software`.

## Notas Operativas

- No se hacen borrados físicos: las bajas se guardan como `activo = FALSE`.
- Los dispositivos archivados no aparecen en listados normales, filtros ni exportaciones.
- Los listados de software tienen vista básica y detallada; las observaciones se muestran en una sola columna.
- Las confirmaciones se hacen con componentes nativos de Streamlit.
