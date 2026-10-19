# Migración desde la versión de escritorio (PySide6)

La migración **solo lee** las tablas MySQL de la versión anterior; no las modifica, de modo que
la base de datos anterior queda intacta. El código de la aplicación de escritorio se retiró el 2026-10-19 (sigue en el historial de git).

## Procedimiento

1. **Copia de seguridad** de la BD actual (`mysqldump`). Es el punto de recuperación.
2. Crear un usuario MySQL **de solo lectura** sobre la BD anterior.
3. Instalar el servicio (ver [deployment.md](deployment.md)); crea la BD nueva vacía.
4. Simulación (no escribe nada, muestra el informe):
   ```powershell
   cd backend
   $env:INV_ENV_FILE="C:\ProgramData\InventarioAsserta\inventario.env"
   .venv\Scripts\python -m app.legacy_import --legacy-url "mysql+pymysql://lector:***@localhost:3306/inventario_software" --dry-run
   ```
5. Revisar el informe: `legacy.equipos` debe coincidir con `new.devices` (+ los ya migrados).
6. Ejecutar sin `--dry-run`. Es idempotente: repetirla no duplica.
7. Verificar en la app: número de dispositivos (activos y retirados), departamentos,
   inventarios históricos (Auditoría › Inventarios mensuales, estado "Histórico importado").

## Mapeo

| Origen | Destino | Notas |
|---|---|---|
| `departamentos` | `departments` | `servidores` no es un departamento: sus equipos pasan a tipo Servidor sin departamento (asígnelos) |
| `equipos` | `devices` + `device_assignments` | Bajas → `retired`. RAM/disco de texto ("16 GB") → bytes. `responsable` (texto libre) se guarda en observaciones, no se inventa un UPN |
| `software_importaciones` + `software_instalado` (confirmadas) | `software_installations` (fuente `panda`) y un inventario mensual `legacy` por periodo | Solo la última importación confirmada de cada equipo queda como software vigente; las `superseded` se ignoran |
| `software_autorizado` (activas) | `software_policies` `authorized` (equipo › departamento › global) | Marcadas con su id de origen |
| `software` (catálogo ENS por departamento) | Clasificación ENS y notas del producto | **No** se interpreta como autorización |

## Reversión

La BD nueva es independiente: para volver atrás basta con seguir usando la aplicación de
escritorio (sus tablas no se tocan) y desinstalar el servicio. Para repetir la migración desde
cero: parar el servicio, borrar `C:\ProgramData\InventarioAsserta\inventario.db`, arrancar y migrar.

## Verificación de no pérdida

`backend/tests/test_legacy_import.py` comprueba con un esquema legacy representativo que todos
los equipos (activos y retirados) se migran, que las tablas origen no cambian y que la segunda
ejecución no duplica. **Pendiente**: ejecutar la simulación contra la BD real y anotar las cifras
en [progress.md](progress.md).
