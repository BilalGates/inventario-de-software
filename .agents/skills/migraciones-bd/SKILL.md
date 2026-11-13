---
name: migraciones-bd
description: Cambios de esquema seguros — migraciones aditivas, reversibles, sin bloqueos largos, con datos existentes en cuenta y verificadas contra el esquema real. Cárgala al crear o alterar tablas, columnas, índices, funciones o políticas.
---

# migraciones-bd

## Antes de escribir

- Dónde vive el esquema vivo y cómo se aplica (lo dice el perfil del proyecto). Abre solo el fichero de la tabla afectada.
- ¿Hay datos en producción? Una migración sobre tabla vacía y otra sobre millones de filas no son la misma migración.

## Reglas

- **Aditivo primero.** Añadir columna nullable → rellenar → poner `NOT NULL`. Renombrar = añadir nuevo + copiar + migrar lecturas + borrar viejo, en pasos.
- **Sin bloqueos largos:** índices `CONCURRENTLY` en tablas grandes; evitar reescrituras de tabla en caliente.
- **Toda tabla nueva sale protegida en el mismo bloque:** claves, FK (compuestas si hay tenant), aislamiento, índices. Una tabla sin protección es trabajo a medias.
- **Idempotente** cuando el sistema de migraciones lo permita (`IF NOT EXISTS`), y con fichero de reparación si producción ya tiene una versión anterior.
- **Reversible:** escribe cómo se deshace, aunque sea a mano.
- Versiones y códigos como texto (`varchar`), nunca numéricos.
- `SECURITY DEFINER` solo si es imprescindible, con `search_path` fijado y justificación.
- Funciones heredadas: léelas enteras y explica qué hacen antes de cambiarlas.

## Verificar

- El verificador de esquema del proyecto, si existe.
- Aplicar en una base limpia y sobre una copia con datos.
- Test que **ejecuta** las consultas afectadas contra el esquema resultante.
- Con RLS forzado, consultar con contexto de tenant: sin él todo sale vacío.
