---
name: tests
description: Qué probar y cómo — tests que ejecutan de verdad el código contra el sistema real, casos límite, aislamiento entre tenants y e2e. Cárgala al escribir o revisar tests, o cuando un cambio necesite demostrar que funciona.
---

# tests

## Principio

Un test vale por **lo que haría fallar**. Si no puede fallar ante el bug que te preocupa, no protege nada.

## Qué probar, por prioridad

1. **Lo que el tipado no ve:** consultas SQL (nombres de columna, joins), contratos con APIs externas, serialización. *Toda consulta nueva o migrada necesita un test que la ejecute contra el esquema real*, aunque la aserción sea floja (`resolves`, un conteo conocido).
2. **Aislamiento y permisos:** con dos tenants/usuarios — crear como A, leer como B, comprobar vacío; y comprobar antes que A sí lo ve (un cero visible no es un cero existente).
3. **Reglas de negocio** con sus casos límite: vacío, uno, muchos, máximo, nulo, duplicado, orden distinto, repetición (idempotencia).
4. **Regresiones:** cada bug arreglado deja su test.
5. **Flujos críticos de interfaz** en e2e: login, alta, la acción principal del producto.

## Cómo

- Arrange / Act / Assert, un comportamiento por test, nombre que lo describe en una frase.
- Datos propios del test; no depender del orden ni de datos de otro test.
- Mock solo en la frontera (red externa, reloj, correo). No mockees la base de datos para probar consultas.
- Selectores e2e por rol y texto accesible, exactos.
- Tests lentos o con red: márcalos y que el perfil diga cuándo se ejecutan.

## Antes de dar por bueno

- Míralo fallar al menos una vez (rompe el código a propósito o escribe el test antes).
- Ejecuta la suite del módulo, no solo el test nuevo.
- Informa qué se ejecutó y qué no.
