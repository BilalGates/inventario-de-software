# ADR 0002 — Versiones tratadas como texto

- **Estado:** Aceptada
- **Fecha:** 2026-05 (migración v2.0); refuerzo 2026-06

## Contexto

Panda Adaptive Defense y los Excel de inventario exportan versiones como
`26.001.21563`, `7.4.2.1737`, `ad 9.0.10`, `2022.05`, `2.10`. Si se tratan como
número:

- Excel/pandas convierten `"1.0"` → `1`, `"2.10"` → `2.1` (se pierden punto/cero).
- Comparar versiones como número o **lexicográficamente** da resultados erróneos:
  `"9.0" > "10.0"` es `True` en orden de texto.

## Decisión

Las versiones son **siempre `str` en Python y `VARCHAR(200)` en BD**:

- `version_referencia`, `software_equipo.version_detectada`,
  `software_autorizado.version` son `VARCHAR`.
- `utils/normalizer.py::clean_version()` convierte cualquier entrada (incluidos
  `int`/`float` de pandas) a texto, preservando el valor.
- **Prohibidas las comparaciones de orden** (`>`, `<`) sobre versiones. Para
  decidir si la versión de referencia debe cambiar se usa
  `utils/normalizer.py::version_changed(old, new)`, que compara **igualdad** del
  texto limpio (no ordena).

## Consecuencias

- **+** No se corrompen versiones al importar/re-importar.
- **+** Se elimina el bug previo de comparación lexicográfica en
  `modules/importacion.py` (la referencia podía no actualizarse, p. ej. de
  `"10.0"` a `"9.0"`).
- **Semántica:** `version_referencia` refleja la **última** versión detectada en
  un cambio, no "la mayor" (que es indecidible de forma fiable con texto). Si en
  el futuro se quisiera "la mayor", habría que un parser de versiones explícito
  y bien testado; de momento se prioriza no corromper datos.
- Tests en `tests/test_normalizer.py` fijan este comportamiento.
