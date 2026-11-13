---
name: multi-tenant
description: Aislamiento entre clientes en un SaaS con base de datos compartida — RLS, contexto de tenant, filtros explícitos, claves compuestas, caché, ficheros, jobs y pruebas con dos tenants. Cárgala al diseñar, construir o revisar cualquier cosa que lea o escriba datos de clientes.
---

# multi-tenant

La pregunta única: **¿puede el tenant A ver, modificar o borrar algo del tenant B?**

## Base de datos

- Columna de tenant `NOT NULL` con FK en **toda** tabla de negocio, también en las hijas (heredar el tenant por JOIN es el fallo clásico).
- Tablas hijas con FK **compuesta** `(tenant_id, padre_id)`: una FK simple permite apuntar a una fila de otro tenant.
- RLS habilitado **y forzado**; política única de tenant generada por un procedimiento común, no escrita a mano.
- Nunca políticas permisivas abiertas (`USING (true)`): se combinan con OR y anulan al resto.
- Tenant leído del contexto de sesión (`SET LOCAL` en transacción), nunca de un parámetro del cliente. El rol de aplicación sin `BYPASSRLS`.
- Índices con la columna de tenant primero.

## Aplicación

- Filtrar por tenant en la consulta **además** de RLS (defensa en profundidad).
- Todo acceso dentro del contexto de tenant; el camino de sistema solo en procesos auditados, nunca desde una petición de usuario.
- Con pooler de conexiones en modo transacción, solo `SET LOCAL` dentro de transacción: un `SET` de sesión se filtra entre peticiones.

## Superficies que se olvidan

- **Caché:** la clave incluye el tenant.
- **Ficheros:** clave prefijada por tenant; validar tenant antes de firmar URL.
- **Jobs:** el payload lleva el tenant y el handler opera dentro de su contexto.
- **Tiempo real y notificaciones:** canales filtrados por tenant.
- **Fugas indirectas:** errores que confirman existencia, contadores globales, autocompletados, búsquedas sin filtrar.
- **Soporte/plataforma:** el acceso del operador entra en **un** tenant concreto, con motivo y auditoría; nunca una consulta que mezcle tenants.

## Prueba mínima de un módulo

1. Como A: crear dato. Como A: leerlo → **se ve** (si no, tu consulta no prueba nada: un cero visible no es un cero existente).
2. Como B: leer, actualizar y borrar ese id → vacío / denegado.
3. Como B: pasar el id de A por la URL o el payload → denegado sin revelar que existe.
