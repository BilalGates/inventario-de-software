# Seguridad

## Exposición histórica en el repositorio público — ACCIÓN PENDIENTE

Revisión del historial de Git (sin reescribirlo):

| Hallazgo | Commits | Riesgo |
|---|---|---|
| `dist/…/_internal/.env` versionado con **`DB_USER=root` y su contraseña** de MySQL | `22831f9` (y posteriores hasta su borrado) | Cualquiera puede leer esa contraseña en el historial público |
| Ficheros reales de inventario: `Inventario Equipos Informaticos Asserta(Equipos Asserta).csv`, `Inventario_Software_ENS_Por_Departamento.xlsx`, `Inventario_Software.vbs` (también dentro de `dist/` y `build/`) | p. ej. `361f592`, `2f78396`, `54ac4fc` | Nombres de equipos, series, MAC y software interno publicados |
| Ejecutables y artefactos de compilación (`build/`, `dist/`) | varios | Pueden contener los datos anteriores embebidos |

Procedimiento recomendado (requiere coordinación; **no se ha ejecutado**):

1. **Rotar ya** la contraseña de `root` de MySQL en cualquier instancia donde se usara, y no usar
   `root` en aplicaciones. Esto es lo único urgente: borrar el historial no invalida una clave filtrada.
2. Valorar si el repositorio debe pasar a **privado**.
3. Si se decide limpiar el historial: copia de seguridad del repo, `git filter-repo` para eliminar
   `.env`, `*.csv`/`*.xlsx`/`*.vbs` reales, `build/` y `dist/`; *force push* coordinado; pedir a
   GitHub la purga de cachés; avisar a quien tenga clones.
4. Considerar comprometidos los datos de inventario publicados (informar según proceda).

## Controles de la versión 2.0

- **Autenticación**: `local` (solo `127.0.0.1`, comprobado en configuración y por petición) o
  Microsoft Entra ID (tokens validados: firma JWKS, emisor, audiencia, caducidad, tenant). Sin
  contraseñas propias. `dev` está prohibido en producción.
- **Autorización en el backend** por rol: administrador › técnico IT › auditor (solo lectura).
- **Secretos** solo en variables de entorno / `inventario.env` en ProgramData con ACL de
  Administradores y SYSTEM. La configuración de fuentes editable desde la UI rechaza claves no
  previstas. Los logs redactan *bearer tokens*, secretos y contraseñas.
- **Graph**: permiso mínimo `DeviceManagementManagedDevices.Read.All`, TLS con verificación de
  certificados (httpx por defecto), certificado preferible a secreto.
- **Auditoría**: cada cambio administrativo y cada ejecución generan un evento encadenado por
  hash; `GET /api/audit/verify` detecta manipulaciones. En MySQL, retire `UPDATE`/`DELETE` sobre
  `audit_events` al usuario de la aplicación.
- **Exportaciones** CSV/XLSX neutralizan fórmulas (`=`, `+`, `-`, `@`).
- **Cabeceras**: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Cache-Control: no-store` en la API, HSTS en producción. `/api/docs` deshabilitado en producción.
- **Datos de desarrollo**: solo sintéticos (`app.demo_data`, dominio `demo.invalid`); las pruebas
  no usan datos reales.

## Pendiente / limitaciones conocidas

- En modo `local` cualquier proceso del propio equipo puede llamar a la API (no hay login).
  Aceptable para un equipo de uso exclusivo de IT; para uso compartido, use `entra`.
- HTTPS no aplica a 127.0.0.1; es obligatorio si se expone en red.
- Cifrado en reposo de la BD SQLite: depende de BitLocker en el equipo.
