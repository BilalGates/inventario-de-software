# Estado del trabajo — Inventario Asserta 2.0

Rama: `feature/inventario-2.0`. Última actualización: 2026-10-15.

## Completado y verificado

- Auditoría del repositorio (estructura, esquema, deuda técnica, historial público → [security.md](security.md)).
- Modelo de datos nuevo + migración Alembic (validada: SQLite ida/vuelta, sin deriva; DDL MySQL generado).
- Motor de sincronización idempotente con salvaguardas (parciales, caídas anómalas, por equipo).
- Conector Intune/Graph (paginación, reintentos, Retry-After, 401/403, certificado o secreto) — **con respuestas simuladas**.
- Ingesta Panda por fichero y carpeta supervisada; CSV de Intune.
- Conciliación de dispositivos con casos de revisión y fusión manual.
- Dispositivos, departamentos (CRUD, desactivación, movimientos masivos con historial), usuarios.
- Catálogo de software, alias, fusión, políticas y excepciones con trazabilidad.
- Alertas, cambios, inventarios mensuales (borrador → revisión), comparación, informe Excel.
- Auditoría encadenada por hash con verificación y exportación.
- Worker: cola, programación mensual, latido, recuperación de ejecuciones colgadas.
- Interfaz web completa (claro/oscuro, responsive) y servicio de Windows (`app.server` probado en
  primer plano en modo producción/local).
- Migración legacy no destructiva e idempotente (probada con esquema representativo).
- Script `Inventario_Programas_Intune.ps1` analizado e integrado: su CSV se importa solo desde `Escritorio\Inventario_Intune`.
- Corrección en el parser legacy: la cabecera "Versión" se importaba como programa.

## Pruebas (2026-10-15)

| Suite | Resultado |
|---|---|
| Backend `pytest` | 59 pruebas OK (conectores simulados, motor, API, RBAC, Entra JWT, migraciones, legacy, worker, modo local) |
| Backend `ruff` | sin errores |
| Frontend `vitest` | 12 pruebas OK · `tsc` sin errores · build OK |
| E2E Playwright | 3 flujos OK contra API + worker reales (departamento → dispositivo → Panda → autorización → alerta → inventario mensual → verificación de auditoría; movimiento masivo; Intune sin credenciales) |
| CI | `.github/workflows/ci.yml`: backend y frontend+E2E (pendiente de su primera ejecución en GitHub) |

**Instalado y verificado en el equipo de IT (2026-10-16):** arranque automático por tarea programada en http://127.0.0.1:8180; interfaz, API y reinicio automático comprobados.

## Bloqueado (requiere acción externa)

| Tarea | Falta |
|---|---|
| Validar Intune real (cifras, estrategia `per_app`/`per_device`, RAM) | Registro de aplicación + permiso `DeviceManagementManagedDevices.Read.All` + credencial |
| Validar cifras con un CSV real del script | Ejecutar el script una vez con el servicio instalado (se importa solo) |
| Conector API de Panda/WatchGuard | Confirmar licencia de API y credenciales |
| Migrar datos reales | Simulación `--dry-run` contra la BD MySQL actual con usuario de solo lectura |
| Quitar el servicio de Windows fallido (reintenta cada 5 min) | `deploy\windows\uninstall-service.ps1` como administrador |
| Remediar la exposición histórica | Rotar la contraseña de MySQL `root`; decidir sobre limpieza del historial |
| Entra ID multiusuario | Solo si se decide abrir el acceso a más personas |

## Pendiente (siguiente iteración)

- Mejoras: vista de versiones desplegadas por producto en el panel, informes programados por correo, P2 (licencias, garantías, Jira Assets).
