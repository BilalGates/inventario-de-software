# ADR 0001 — UI con PySide6 (frente a Streamlit / NiceGUI)

- **Estado:** Aceptada
- **Fecha:** 2026-05 (migración v2.0)

## Contexto

La aplicación nació especificada sobre **Streamlit** (ver
[docs/archive/SPEC_streamlit_original.md](../archive/SPEC_streamlit_original.md)).
Es una herramienta **local, monousuario**, para inventario de software/hardware y
auditoría ENS, que debe distribuirse como ejecutable en Windows y manejar tablas
de miles de filas con fluidez.

Limitaciones detectadas con las opciones web:

- **Streamlit**: re-render completo en cada interacción; necesita un servidor web
  y navegador; no produce un `.exe` nativo limpio.
- **NiceGUI**: mismas limitaciones de servidor/navegador; latencia añadida para
  una app que es local.

## Decisión

Usar **PySide6** (Qt) como framework de UI:

- Aplicación de escritorio **nativa** en Windows; `.exe` limpio con PyInstaller.
- `QTableView` + `QAbstractTableModel` renderizan miles de filas sin lag (solo las
  visibles), frente a `QTableWidget`.
- Operaciones de BD en `QThread` (`run_in_thread`) para no congelar la UI.
- Theming completo con QSS.

## Consecuencias

- **+** Rendimiento y experiencia nativa; distribución como binario único.
- **+** La lógica de negocio (`modules/`) queda desacoplada de la UI.
- **−** Curva Qt mayor que Streamlit; UI más verbosa.
- La documentación y el código vigentes asumen **PySide6**. Cualquier referencia a
  Streamlit es histórica.
