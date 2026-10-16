# Decisiones de arquitectura

Las decisiones de la versión de escritorio están en [legacy/adr/](legacy/adr/). Se mantienen
vigentes: versiones como texto (ADR 0002) y sin borrados físicos.

### D1 — Aplicación web servida como servicio de Windows (2026-10-15)
Petición expresa: dejar la app de escritorio y usarla desde el navegador, como servicio que
arranca en el equipo de IT. Un único proceso (`app.server`) sirve API + interfaz y ejecuta el
worker; `pywin32` lo envuelve como servicio. Sin IIS ni contenedores: un solo equipo, un usuario.

### D2 — FastAPI + SQLAlchemy 2 + Alembic
Se reutiliza Python y SQLAlchemy de la versión anterior y el parser de Panda probado. Alembic
sustituye a las migraciones SQL manuales para el esquema nuevo.

### D3 — React SPA con Vite en lugar de Next.js
No hay necesidad de SSR; una SPA estática servida por la propia API evita ejecutar Node en
producción. Mismo stack de componentes (React, TypeScript, Tailwind).

### D4 — Cola en base de datos en vez de Celery/Redis
Volumen de decenas de equipos. La tabla `inventory_runs` es cola e historial a la vez; el
reclamo usa `SELECT … FOR UPDATE SKIP LOCKED` en MySQL. Menos piezas que operar.

### D5 — SQLite por defecto en modo local; MySQL para multiusuario
Para un servicio monousuario, SQLite evita gestionar un servidor y credenciales. El modelo es
portable y las migraciones se validan en ambos (DDL de MySQL generado en los tests). Con
acceso Entra (multiusuario) se exige MySQL.

### D6 — Modo de autenticación `local` restringido a 127.0.0.1
Sin login para el uso en el propio equipo, pero imposible de exponer en red: la configuración
lo rechaza y cada petición se valida por IP de origen.

### D7 — Esquema nuevo en paralelo a las tablas legacy
La migración solo lee el esquema anterior: reversible y sin riesgo para la app de escritorio.

### D8 — Identidad de dispositivo y conciliación conservadora
`uid` propio; conciliación por id de Intune/Entra › número de serie (filtrando series de
relleno) › hostname solo si no contradice. Ante ambigüedad, caso de revisión y nunca fusión
automática.

### D9 — Completitud separada: parque vs. software por equipo
Las ausencias de dispositivos solo se infieren de extracciones completas de una fuente API; las
desinstalaciones, solo en equipos cuyo software se leyó íntegro y sin anomalías.

### D10 — Normalización conservadora + alias
Solo se unifica ruido tipográfico y la versión repetida al final del nombre. Lo demás, con alias
y fusiones manuales auditadas.

### D11 — Rollup WebAssembly en el build del frontend
La política de Windows del equipo de desarrollo bloquea el binario nativo de Rollup; se fuerza
`@rollup/wasm-node` (mismo resultado, algo más lento).

### D12 — Tarea programada + supervisor en lugar de servicio de Windows (2026-10-16)
El servicio con pywin32 cae al arrancar con Python 3.12.0 (violación de acceso en
python312.dll, reproducible y previa al código de la aplicación). Se sustituye por una tarea
programada al iniciar sesión, sin administrador, que lanza `app.supervisor` (reinicia la
aplicación si termina). Diferencia: arranca al iniciar sesión, no al encender el equipo;
suficiente para un equipo de uso personal de IT.
